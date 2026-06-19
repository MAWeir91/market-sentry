"""Command-line runner for the local mock Market Sentry scanner."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import sleep
from typing import Sequence

from market_sentry.alerts import (
    AlertCooldownManager,
    AlertEvent,
    AlertSpeaker,
    LocalTTSSpeaker,
    generate_alerts,
)
from market_sentry.config import load_config
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.provider import MarketDataProvider
from market_sentry.live_readiness import (
    LiveReadinessReport,
    evaluate_live_readiness,
)
from market_sentry.local_json_preflight_cli import (
    JsonHistoricalSessionMetadataFileSourceError,
    is_manual_local_json_preflight_success,
    render_manual_local_json_preflight_error,
    render_manual_local_json_preflight_report,
    run_manual_local_json_preflight,
)
from market_sentry.local_json_preflight_report_export import (
    render_manual_local_json_preflight_export_error,
    write_manual_local_json_preflight_report,
)
from market_sentry.scanner import ScannerEngine, ScannerResult

DEFAULT_INTERVAL_SECONDS = 30.0
MIN_INTERVAL_SECONDS = 5.0
PROVIDER_REPORT_LABELS = {
    "mock": "Mock Scanner Report",
    "fixture": "Fixture Scanner Report",
    "composed_fixture": "Composed Fixture Scanner Report",
}


def get_provider_display_label(provider_name: str) -> str:
    """Return the report label for active offline providers."""

    return PROVIDER_REPORT_LABELS.get(provider_name.strip().lower(), "Scanner Report")


def format_share_count(value: int) -> str:
    """Format share counts for compact terminal output."""

    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f}K"
    return str(value)


def _format_optional_price(value: float | None) -> str:
    if value is None or value <= 0:
        return "N/A"
    return f"${value:.2f}"


def _format_optional_percent(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return "N/A"
    if signed and value > 0:
        return f"+{value:.1f}%"
    return f"{value:.1f}%"


def _format_optional_rotation(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}x"


def _format_result(result: ScannerResult) -> list[str]:
    candidate = result.candidate
    tier_label = result.tier.label if result.tier is not None else "None"
    status = "QUALIFIED" if result.qualified else "REJECTED"
    lines = [
        f"{result.symbol} | {status} | {tier_label} | Score: {result.score:.2f}",
        (
            f"  Price: ${candidate.price:.2f} | "
            f"Gain: {candidate.daily_gain_percent:.1f}% | "
            f"RelVol: {candidate.relative_volume:.1f}x | "
            f"Float: {format_share_count(candidate.float_shares)} | "
            f"Volume: {format_share_count(candidate.daily_volume)}"
        ),
        (
            f"  Rotation: {_format_optional_rotation(candidate.rotation)} | "
            f"15m: {_format_optional_percent(candidate.change_15m_pct, signed=True)} | "
            f"HOD: {_format_optional_price(candidate.high_of_day)} | "
            f"HOD Dist: {_format_optional_percent(candidate.distance_from_high_pct)}"
        ),
        "  Reasons:",
    ]
    for reason in result.reasons:
        marker = "PASS" if reason.passed else "FAIL"
        lines.append(f"    [{marker}] {reason.code}: {reason.message}")
    return lines


def _format_alert(alert: AlertEvent) -> str:
    return f"[{alert.priority.name}] {alert.message}"


def render_report(
    results: Iterable[ScannerResult],
    alerts: Iterable[AlertEvent] = (),
    scan_label: str | None = None,
    report_label: str = PROVIDER_REPORT_LABELS["mock"],
) -> str:
    """Render scanner results and voice-ready alerts for terminal output."""

    result_list = list(results)
    alert_list = list(alerts)
    qualified_results = [result for result in result_list if result.qualified]
    rejected_results = [result for result in result_list if not result.qualified]

    lines = ["Market Sentry", report_label]
    if scan_label is not None:
        lines.append(scan_label)
    lines.extend(["", "Qualified Results", "-----------------"])

    if qualified_results:
        for index, result in enumerate(qualified_results):
            if index:
                lines.append("")
            lines.extend(_format_result(result))
    else:
        lines.append("No qualified candidates.")

    lines.extend(["", "Rejected Results", "----------------"])

    if rejected_results:
        for index, result in enumerate(rejected_results):
            if index:
                lines.append("")
            lines.extend(_format_result(result))
    else:
        lines.append("No rejected candidates.")

    lines.extend(["", "Voice-Ready Alerts", "------------------"])

    if alert_list:
        lines.extend(_format_alert(alert) for alert in alert_list)
    else:
        lines.append("No voice-ready alerts.")

    return "\n".join(lines)


def render_live_readiness_report(report: LiveReadinessReport) -> str:
    """Render a secret-safe live-readiness preflight report."""

    lines = [
        "Market Sentry Live Readiness",
        f"Status: {report.status.value}",
        "",
    ]
    for check in report.checks:
        marker = "PASS" if check.passed else "FAIL"
        lines.append(f"[{marker}] {check.name.value} - {check.message}")
    lines.extend(
        [
            "",
            f"Summary: {report.summary}",
            "Note: This preflight does not call APIs and does not activate live_composed.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the small Market Sentry CLI surface."""

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--live-readiness", action="store_true")
    parser.add_argument("--relative-volume-configured", action="store_true")
    parser.add_argument("--local-json-preflight", type=Path, default=None)
    parser.add_argument("--local-json-preflight-report", type=Path, default=None)
    speak_group = parser.add_mutually_exclusive_group()
    speak_group.add_argument("--speak", action="store_true", dest="speak")
    speak_group.add_argument("--no-speak", action="store_false", dest="speak")
    parser.set_defaults(speak=False)
    return parser.parse_args(argv)


def _has_local_json_preflight_arg(raw_argv: Sequence[str]) -> bool:
    return any(
        item == "--local-json-preflight"
        or item.startswith("--local-json-preflight=")
        for item in raw_argv
    )


def _local_json_preflight_parse_argv(raw_argv: Sequence[str]) -> list[str]:
    if (
        _has_local_json_preflight_arg(raw_argv)
        and "--speak" in raw_argv
        and "--no-speak" in raw_argv
    ):
        return [item for item in raw_argv if item not in {"--speak", "--no-speak"}]
    return list(raw_argv)


def _local_json_preflight_conflicts(
    raw_argv: Sequence[str],
    args: argparse.Namespace,
) -> list[str]:
    conflict_flags = {
        "--loop",
        "--live-readiness",
        "--relative-volume-configured",
        "--speak",
        "--no-speak",
    }
    conflicts: list[str] = []
    seen: set[str] = set()
    interval_conflicts = args.interval != DEFAULT_INTERVAL_SECONDS

    for item in raw_argv:
        conflict = None
        if item in conflict_flags:
            conflict = item
        elif item == "--interval" or item.startswith("--interval="):
            if interval_conflicts:
                conflict = "--interval"

        if conflict is not None and conflict not in seen:
            conflicts.append(conflict)
            seen.add(conflict)

    return conflicts


def _render_local_json_preflight_command_error(
    path: Path,
    conflicts: Sequence[str],
) -> str:
    return "\n".join(
        [
            "Market Sentry Local JSON Preflight",
            f"Path: {path}",
            "Result: COMMAND_ERROR",
            (
                "Error: --local-json-preflight cannot be combined with: "
                f"{', '.join(conflicts)}"
            ),
        ]
    )


def _render_local_json_preflight_report_dependency_error(report_path: Path) -> str:
    return "\n".join(
        [
            "Market Sentry Local JSON Preflight",
            "Path: N/A",
            f"Report Path: {report_path}",
            "Result: COMMAND_ERROR",
            "Error: --local-json-preflight-report requires --local-json-preflight",
        ]
    )


def _render_local_json_preflight_same_path_error(
    input_path: Path,
    report_path: Path,
) -> str:
    return "\n".join(
        [
            "Market Sentry Local JSON Preflight",
            f"Path: {input_path}",
            f"Report Path: {report_path}",
            "Result: COMMAND_ERROR",
            (
                "Error: --local-json-preflight-report must differ from "
                "--local-json-preflight"
            ),
        ]
    )


def normalize_interval(interval_seconds: float) -> float:
    """Return an interval that respects the Phase 8 minimum."""

    return max(interval_seconds, MIN_INTERVAL_SECONDS)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _format_scan_label(iteration: int, scan_time: datetime) -> str:
    return f"Scan Iteration: {iteration} | Scan Time: {scan_time:%Y-%m-%d %H:%M:%S}"


def _run_scan(
    *,
    provider: MarketDataProvider,
    speak: bool = False,
    speaker: AlertSpeaker | None = None,
    cooldown_manager: AlertCooldownManager | None = None,
    scan_time: datetime | None = None,
    scan_label: str | None = None,
    report_label: str = PROVIDER_REPORT_LABELS["mock"],
) -> None:
    candidates = provider.get_candidates()
    results = ScannerEngine().scan(candidates)
    display_alerts = generate_alerts(results)

    event_time = scan_time or _now_utc()
    speak_alerts = display_alerts
    if cooldown_manager is not None:
        speak_alerts = generate_alerts(
            results,
            cooldown_manager=cooldown_manager,
            created_at=event_time,
        )

    print(
        render_report(
            results,
            display_alerts,
            scan_label=scan_label,
            report_label=report_label,
        )
    )

    if speak:
        voice_speaker = speaker or LocalTTSSpeaker()
        speech_result = voice_speaker.speak(speak_alerts)
        if not speech_result.success and speech_result.error is not None:
            print(f"\n{speech_result.error}")


def run_loop(
    *,
    provider: MarketDataProvider,
    interval_seconds: float,
    speak: bool = False,
    speaker: AlertSpeaker | None = None,
    sleep_fn=sleep,
    now_fn=_now_utc,
    max_iterations: int | None = None,
    report_label: str = PROVIDER_REPORT_LABELS["mock"],
) -> None:
    """Run repeated mock scans until interrupted or test limit is reached."""

    cooldown_manager = AlertCooldownManager()
    iteration = 1

    try:
        while max_iterations is None or iteration <= max_iterations:
            scan_time = now_fn()
            _run_scan(
                provider=provider,
                speak=speak,
                speaker=speaker,
                cooldown_manager=cooldown_manager if speak else None,
                scan_time=scan_time,
                scan_label=_format_scan_label(iteration, scan_time),
                report_label=report_label,
            )

            iteration += 1
            if max_iterations is not None and iteration > max_iterations:
                break
            sleep_fn(interval_seconds)
    except KeyboardInterrupt:
        print("\nMarket Sentry loop stopped.")


def main(
    argv: Sequence[str] | None = None,
    speaker: AlertSpeaker | None = None,
    sleep_fn=sleep,
    now_fn=_now_utc,
    max_iterations: int | None = None,
) -> int:
    """Run the local mock provider through the scanner and print a report."""

    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(_local_json_preflight_parse_argv(raw_argv))
    interval_seconds = normalize_interval(args.interval)

    if (
        args.local_json_preflight_report is not None
        and args.local_json_preflight is None
    ):
        print(
            _render_local_json_preflight_report_dependency_error(
                args.local_json_preflight_report,
            )
        )
        return 2

    if args.local_json_preflight is not None:
        conflicts = _local_json_preflight_conflicts(raw_argv, args)
        if conflicts:
            print(
                _render_local_json_preflight_command_error(
                    args.local_json_preflight,
                    conflicts,
                )
            )
            return 2

        if (
            args.local_json_preflight_report is not None
            and args.local_json_preflight == args.local_json_preflight_report
        ):
            print(
                _render_local_json_preflight_same_path_error(
                    args.local_json_preflight,
                    args.local_json_preflight_report,
                )
            )
            return 2

        exit_code = 1
        try:
            result = run_manual_local_json_preflight(args.local_json_preflight)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            JsonHistoricalSessionMetadataFileSourceError,
        ) as exc:
            report = render_manual_local_json_preflight_error(
                args.local_json_preflight,
                exc,
            )
        else:
            report = render_manual_local_json_preflight_report(
                args.local_json_preflight,
                result,
            )
            exit_code = 0 if is_manual_local_json_preflight_success(result) else 1

        if args.local_json_preflight_report is not None:
            try:
                write_manual_local_json_preflight_report(
                    args.local_json_preflight_report,
                    report,
                )
            except OSError as exc:
                print(
                    render_manual_local_json_preflight_export_error(
                        args.local_json_preflight,
                        args.local_json_preflight_report,
                        exc,
                    )
                )
                return 1

        print(report)
        return exit_code

    if args.live_readiness:
        config = load_config()
        report = evaluate_live_readiness(
            config,
            relative_volume_configured=args.relative_volume_configured,
        )
        print(render_live_readiness_report(report))
        return 0 if report.ready else 1

    try:
        config = load_config()
        provider = create_market_data_provider(config)
    except ProviderConfigurationError as exc:
        print(f"Provider configuration error: {exc}")
        return 1

    if args.loop:
        run_loop(
            provider=provider,
            interval_seconds=interval_seconds,
            speak=args.speak,
            speaker=speaker,
            sleep_fn=sleep_fn,
            now_fn=now_fn,
            max_iterations=max_iterations,
            report_label=get_provider_display_label(config.provider),
        )
        return 0

    _run_scan(
        provider=provider,
        speak=args.speak,
        speaker=speaker,
        report_label=get_provider_display_label(config.provider),
    )
    return 0


if __name__ == "__main__":
    main()
