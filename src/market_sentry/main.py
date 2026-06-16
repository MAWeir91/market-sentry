"""Command-line runner for the local mock Market Sentry scanner."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import datetime, timezone
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
from market_sentry.scanner import ScannerEngine, ScannerResult

DEFAULT_INTERVAL_SECONDS = 30.0
MIN_INTERVAL_SECONDS = 5.0
PROVIDER_REPORT_LABELS = {
    "mock": "Mock Scanner Report",
    "fixture": "Fixture Scanner Report",
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the small Market Sentry CLI surface."""

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    speak_group = parser.add_mutually_exclusive_group()
    speak_group.add_argument("--speak", action="store_true", dest="speak")
    speak_group.add_argument("--no-speak", action="store_false", dest="speak")
    parser.set_defaults(speak=False)
    return parser.parse_args(argv)


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

    args = parse_args(argv)
    interval_seconds = normalize_interval(args.interval)

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
