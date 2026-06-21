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
from market_sentry.config import LIVE_COMPOSED_PROVIDER
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.json_historical_rvol_bundle import JsonHistoricalRvolBundleError
from market_sentry.data.json_historical_session_metadata_writer import (
    JsonHistoricalSessionMetadataWriteError,
)
from market_sentry.data.provider import MarketDataProvider
from market_sentry.live_readiness import (
    LiveReadinessReport,
    evaluate_live_readiness,
)
from market_sentry.local_rvol_session_seed_cli import (
    LOCAL_RVOL_SESSION_SEED_EXPECTED_ERRORS,
    LocalRvolSessionSeedCommandError,
    LocalRvolSessionSeedCommandRequest,
    render_local_rvol_session_seed_command_error,
    render_local_rvol_session_seed_error,
    render_local_rvol_session_seed_success_report,
    run_local_rvol_session_seed,
    validate_local_rvol_session_seed_command,
)
from market_sentry.manual_explicit_alpaca_rvol_capture_preflight_cli import (
    MANUAL_EXPLICIT_ALPACA_CAPTURE_EXPECTED_ERRORS,
    ManualExplicitAlpacaRvolCaptureCommandError,
    ManualExplicitAlpacaRvolCaptureCommandRequest,
    is_manual_explicit_alpaca_rvol_capture_success,
    render_manual_explicit_alpaca_rvol_capture_command_error,
    render_manual_explicit_alpaca_rvol_capture_error,
    render_manual_explicit_alpaca_rvol_capture_stopped_report,
    run_manual_explicit_alpaca_rvol_capture_preflight,
    validate_manual_explicit_alpaca_rvol_capture_command,
)
from market_sentry.local_json_bundle_preflight_cli import (
    MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS,
    is_manual_local_json_bundle_preflight_success,
    render_manual_local_json_bundle_preflight_error,
    render_manual_local_json_bundle_preflight_report,
    run_manual_local_json_bundle_preflight,
)
from market_sentry.local_json_bundle_preflight_report_export import (
    render_manual_local_json_bundle_preflight_export_error,
    write_manual_local_json_bundle_preflight_report,
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
    "live_composed": (
        "Live Composed One-Shot Scanner Report\n"
        "(live Alpaca snapshots + live FMP float + explicit local RVOL artifacts)"
    ),
}
LOCAL_RVOL_SESSION_SEED_OPERATIONAL_ERRORS = LOCAL_RVOL_SESSION_SEED_EXPECTED_ERRORS + (
    json.JSONDecodeError,
    JsonHistoricalSessionMetadataWriteError,
)


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
            (
                "Note: This preflight validates local configuration only. It does "
                "not read or preflight artifacts, call APIs, or activate live_composed."
            ),
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
    parser.add_argument(
        "--local-json-bundle-preflight",
        type=Path,
        nargs=2,
        default=None,
        metavar=("METADATA_PATH", "BUNDLE_PATH"),
    )
    parser.add_argument("--local-json-bundle-preflight-report", type=Path, default=None)
    parser.add_argument(
        "--manual-alpaca-rvol-capture",
        type=Path,
        nargs=3,
        default=None,
        metavar=("METADATA_INPUT_PATH", "METADATA_OUTPUT_PATH", "BUNDLE_OUTPUT_PATH"),
    )
    parser.add_argument("--manual-alpaca-rvol-capture-report", type=Path, default=None)
    parser.add_argument(
        "--manual-alpaca-rvol-capture-confirm-live-data",
        action="store_true",
    )
    parser.add_argument("--manual-alpaca-rvol-capture-symbol", default=None)
    parser.add_argument("--manual-alpaca-rvol-capture-historical-start", default=None)
    parser.add_argument("--manual-alpaca-rvol-capture-historical-end", default=None)
    parser.add_argument(
        "--manual-alpaca-rvol-capture-historical-max-pages",
        type=int,
        default=None,
    )
    parser.add_argument("--manual-alpaca-rvol-capture-current-start", default=None)
    parser.add_argument("--manual-alpaca-rvol-capture-current-end", default=None)
    parser.add_argument(
        "--manual-alpaca-rvol-capture-current-max-pages",
        type=int,
        default=None,
    )
    parser.add_argument("--manual-alpaca-rvol-capture-current-session-id", default=None)
    parser.add_argument("--manual-alpaca-rvol-capture-bucket", default=None)
    parser.add_argument("--manual-alpaca-rvol-capture-cutoff", default=None)
    parser.add_argument(
        "--manual-alpaca-rvol-capture-minimum-historical-sessions",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--manual-alpaca-rvol-capture-timeframe",
        default="1Min",
    )
    parser.add_argument(
        "--manual-alpaca-rvol-capture-page-limit",
        type=int,
        default=1000,
    )
    parser.add_argument(
        "--manual-alpaca-rvol-capture-sort",
        choices=("asc", "desc"),
        default="asc",
    )
    parser.add_argument(
        "--local-rvol-session-seed",
        type=Path,
        nargs=2,
        default=None,
        metavar=("PLAN_PATH", "METADATA_OUTPUT_PATH"),
    )
    speak_group = parser.add_mutually_exclusive_group()
    speak_group.add_argument("--speak", action="store_true", dest="speak")
    speak_group.add_argument("--no-speak", action="store_false", dest="speak")
    parser.set_defaults(speak=False)
    return parser.parse_args(argv)


def _has_local_json_preflight_arg(raw_argv: Sequence[str]) -> bool:
    return any(
        item == "--local-json-preflight"
        or item.startswith("--local-json-preflight=")
        or item == "--local-json-bundle-preflight"
        or item.startswith("--local-json-bundle-preflight=")
        or item == "--manual-alpaca-rvol-capture"
        or item.startswith("--manual-alpaca-rvol-capture=")
        or item == "--local-rvol-session-seed"
        or item.startswith("--local-rvol-session-seed=")
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


def _has_manual_capture_option(raw_argv: Sequence[str]) -> bool:
    manual_options = {
        "--manual-alpaca-rvol-capture-report",
        "--manual-alpaca-rvol-capture-confirm-live-data",
        "--manual-alpaca-rvol-capture-symbol",
        "--manual-alpaca-rvol-capture-historical-start",
        "--manual-alpaca-rvol-capture-historical-end",
        "--manual-alpaca-rvol-capture-historical-max-pages",
        "--manual-alpaca-rvol-capture-current-start",
        "--manual-alpaca-rvol-capture-current-end",
        "--manual-alpaca-rvol-capture-current-max-pages",
        "--manual-alpaca-rvol-capture-current-session-id",
        "--manual-alpaca-rvol-capture-bucket",
        "--manual-alpaca-rvol-capture-cutoff",
        "--manual-alpaca-rvol-capture-minimum-historical-sessions",
        "--manual-alpaca-rvol-capture-timeframe",
        "--manual-alpaca-rvol-capture-page-limit",
        "--manual-alpaca-rvol-capture-sort",
    }
    return any(
        item in manual_options
        or any(item.startswith(f"{option}=") for option in manual_options)
        for item in raw_argv
    )


def _seed_command_conflicts(
    raw_argv: Sequence[str],
    args: argparse.Namespace,
) -> list[str]:
    conflict_flags = {
        "--loop",
        "--live-readiness",
        "--relative-volume-configured",
        "--speak",
        "--no-speak",
        "--local-json-preflight",
        "--local-json-preflight-report",
        "--local-json-bundle-preflight",
        "--local-json-bundle-preflight-report",
        "--manual-alpaca-rvol-capture",
        "--manual-alpaca-rvol-capture-report",
        "--manual-alpaca-rvol-capture-confirm-live-data",
        "--manual-alpaca-rvol-capture-symbol",
        "--manual-alpaca-rvol-capture-historical-start",
        "--manual-alpaca-rvol-capture-historical-end",
        "--manual-alpaca-rvol-capture-historical-max-pages",
        "--manual-alpaca-rvol-capture-current-start",
        "--manual-alpaca-rvol-capture-current-end",
        "--manual-alpaca-rvol-capture-current-max-pages",
        "--manual-alpaca-rvol-capture-current-session-id",
        "--manual-alpaca-rvol-capture-bucket",
        "--manual-alpaca-rvol-capture-cutoff",
        "--manual-alpaca-rvol-capture-minimum-historical-sessions",
        "--manual-alpaca-rvol-capture-timeframe",
        "--manual-alpaca-rvol-capture-page-limit",
        "--manual-alpaca-rvol-capture-sort",
    }
    conflicts: list[str] = []
    seen: set[str] = set()
    interval_conflicts = args.interval != DEFAULT_INTERVAL_SECONDS

    for item in raw_argv:
        conflict = None
        if item in conflict_flags:
            conflict = item
        elif any(item.startswith(f"{flag}=") for flag in conflict_flags):
            conflict = item.split("=", maxsplit=1)[0]
        elif item == "--interval" or item.startswith("--interval="):
            if interval_conflicts:
                conflict = "--interval"

        if conflict is not None and conflict not in seen:
            conflicts.append(conflict)
            seen.add(conflict)

    return conflicts


def _manual_capture_conflicts(
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


def _render_local_json_bundle_report_dependency_error(report_path: Path) -> str:
    return "\n".join(
        [
            "Market Sentry Local JSON Bundle Preflight",
            "Metadata Path: N/A",
            "Bundle Path: N/A",
            f"Report Path: {report_path}",
            "Result: COMMAND_ERROR",
            (
                "Error: --local-json-bundle-preflight-report requires "
                "--local-json-bundle-preflight"
            ),
        ]
    )


def _render_manual_capture_report_dependency_error(report_path: Path) -> str:
    return "\n".join(
        [
            "Market Sentry Manual Alpaca RVOL Capture Preflight",
            "Metadata Input Path: N/A",
            "Metadata Path: N/A",
            "Bundle Path: N/A",
            f"Report Path: {report_path}",
            "Result: COMMAND_ERROR",
            (
                "Error: --manual-alpaca-rvol-capture-report requires "
                "--manual-alpaca-rvol-capture"
            ),
        ]
    )


def _render_manual_capture_option_dependency_error() -> str:
    return "\n".join(
        [
            "Market Sentry Manual Alpaca RVOL Capture Preflight",
            "Metadata Input Path: N/A",
            "Metadata Path: N/A",
            "Bundle Path: N/A",
            "Report Path: N/A",
            "Result: COMMAND_ERROR",
            "Error: manual Alpaca capture options require --manual-alpaca-rvol-capture",
        ]
    )


def _render_local_json_preflight_mode_exclusivity_error() -> str:
    return "\n".join(
        [
            "Market Sentry Local JSON Preflight",
            "Path: N/A",
            "Result: COMMAND_ERROR",
            (
                "Error: --local-json-preflight and --local-json-bundle-preflight "
                "cannot be combined"
            ),
        ]
    )


def _render_manual_capture_mode_exclusivity_error() -> str:
    return "\n".join(
        [
            "Market Sentry Manual Alpaca RVOL Capture Preflight",
            "Metadata Input Path: N/A",
            "Metadata Path: N/A",
            "Bundle Path: N/A",
            "Report Path: N/A",
            "Result: COMMAND_ERROR",
            (
                "Error: --manual-alpaca-rvol-capture cannot be combined with "
                "local JSON preflight modes"
            ),
        ]
    )


def _render_local_json_bundle_conflict_error(
    metadata_path: Path,
    bundle_path: Path,
    conflicts: Sequence[str],
) -> str:
    return "\n".join(
        [
            "Market Sentry Local JSON Bundle Preflight",
            f"Metadata Path: {metadata_path}",
            f"Bundle Path: {bundle_path}",
            "Result: COMMAND_ERROR",
            (
                "Error: --local-json-bundle-preflight cannot be combined with: "
                f"{', '.join(conflicts)}"
            ),
        ]
    )


def _render_manual_capture_conflict_error(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
    conflicts: Sequence[str],
) -> str:
    return "\n".join(
        [
            "Market Sentry Manual Alpaca RVOL Capture Preflight",
            f"Metadata Input Path: {command.metadata_input_path}",
            f"Metadata Path: {command.metadata_output_path}",
            f"Bundle Path: {command.bundle_output_path}",
            f"Report Path: {command.report_output_path or 'N/A'}",
            "Result: COMMAND_ERROR",
            (
                "Error: --manual-alpaca-rvol-capture cannot be combined with: "
                f"{', '.join(conflicts)}"
            ),
        ]
    )


def _render_local_rvol_session_seed_conflict_error(
    command: LocalRvolSessionSeedCommandRequest,
    conflicts: Sequence[str],
) -> str:
    return "\n".join(
        [
            "Market Sentry Local RVOL Session Seed",
            f"Plan Path: {command.plan_path}",
            f"Metadata Path: {command.metadata_output_path}",
            "Result: COMMAND_ERROR",
            (
                "Error: --local-rvol-session-seed cannot be combined with: "
                f"{', '.join(conflicts)}"
            ),
        ]
    )


def _render_local_json_bundle_report_same_metadata_error(
    metadata_path: Path,
    bundle_path: Path,
    report_path: Path,
) -> str:
    return "\n".join(
        [
            "Market Sentry Local JSON Bundle Preflight",
            f"Metadata Path: {metadata_path}",
            f"Bundle Path: {bundle_path}",
            f"Report Path: {report_path}",
            "Result: COMMAND_ERROR",
            (
                "Error: --local-json-bundle-preflight-report must differ from "
                "metadata path"
            ),
        ]
    )


def _render_local_json_bundle_report_same_bundle_error(
    metadata_path: Path,
    bundle_path: Path,
    report_path: Path,
) -> str:
    return "\n".join(
        [
            "Market Sentry Local JSON Bundle Preflight",
            f"Metadata Path: {metadata_path}",
            f"Bundle Path: {bundle_path}",
            f"Report Path: {report_path}",
            "Result: COMMAND_ERROR",
            (
                "Error: --local-json-bundle-preflight-report must differ from "
                "bundle path"
            ),
        ]
    )


def _render_live_composed_loop_error() -> str:
    return "\n".join(
        [
            "Market Sentry Live Composed Scanner",
            "Result: COMMAND_ERROR",
            "Error: --loop is not available for live_composed in Phase 18A",
            (
                "Note: Phase 18A permits one-shot live-composed scans only. "
                "RVOL comes from explicit local artifacts."
            ),
        ]
    )


def _build_manual_capture_command_request(
    args: argparse.Namespace,
) -> ManualExplicitAlpacaRvolCaptureCommandRequest:
    paths = args.manual_alpaca_rvol_capture
    metadata_input_path = paths[0]
    metadata_output_path = paths[1]
    bundle_output_path = paths[2]
    return ManualExplicitAlpacaRvolCaptureCommandRequest(
        metadata_input_path=metadata_input_path,
        metadata_output_path=metadata_output_path,
        bundle_output_path=bundle_output_path,
        report_output_path=args.manual_alpaca_rvol_capture_report,
        confirm_live_data=args.manual_alpaca_rvol_capture_confirm_live_data,
        symbol=args.manual_alpaca_rvol_capture_symbol,
        historical_start=args.manual_alpaca_rvol_capture_historical_start,
        historical_end=args.manual_alpaca_rvol_capture_historical_end,
        historical_max_pages=args.manual_alpaca_rvol_capture_historical_max_pages,
        current_start=args.manual_alpaca_rvol_capture_current_start,
        current_end=args.manual_alpaca_rvol_capture_current_end,
        current_max_pages=args.manual_alpaca_rvol_capture_current_max_pages,
        current_session_id=args.manual_alpaca_rvol_capture_current_session_id,
        bucket=args.manual_alpaca_rvol_capture_bucket,
        cutoff=args.manual_alpaca_rvol_capture_cutoff,
        minimum_historical_sessions=(
            args.manual_alpaca_rvol_capture_minimum_historical_sessions
        ),
        timeframe=args.manual_alpaca_rvol_capture_timeframe,
        page_limit=args.manual_alpaca_rvol_capture_page_limit,
        sort=args.manual_alpaca_rvol_capture_sort,
    )


def _build_local_rvol_session_seed_command_request(
    args: argparse.Namespace,
) -> LocalRvolSessionSeedCommandRequest:
    paths = args.local_rvol_session_seed
    return LocalRvolSessionSeedCommandRequest(
        plan_path=paths[0],
        metadata_output_path=paths[1],
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
    bundle_paths = args.local_json_bundle_preflight
    bundle_metadata_path = bundle_paths[0] if bundle_paths is not None else None
    bundle_path = bundle_paths[1] if bundle_paths is not None else None
    manual_paths = args.manual_alpaca_rvol_capture
    seed_paths = args.local_rvol_session_seed

    if seed_paths is not None:
        command = _build_local_rvol_session_seed_command_request(args)
        conflicts = _seed_command_conflicts(raw_argv, args)
        if conflicts:
            print(_render_local_rvol_session_seed_conflict_error(command, conflicts))
            return 2

        try:
            validate_local_rvol_session_seed_command(command)
            result = run_local_rvol_session_seed(command)
        except LocalRvolSessionSeedCommandError as exc:
            print(render_local_rvol_session_seed_command_error(command, exc))
            return 2
        except LOCAL_RVOL_SESSION_SEED_OPERATIONAL_ERRORS as exc:
            print(render_local_rvol_session_seed_error(command, exc))
            return 1

        print(render_local_rvol_session_seed_success_report(command, result))
        return 0

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

    if (
        args.local_json_bundle_preflight_report is not None
        and args.local_json_bundle_preflight is None
    ):
        print(
            _render_local_json_bundle_report_dependency_error(
                args.local_json_bundle_preflight_report,
            )
        )
        return 2

    if (
        args.manual_alpaca_rvol_capture_report is not None
        and manual_paths is None
    ):
        print(
            _render_manual_capture_report_dependency_error(
                args.manual_alpaca_rvol_capture_report,
            )
        )
        return 2

    if manual_paths is None and _has_manual_capture_option(raw_argv):
        print(_render_manual_capture_option_dependency_error())
        return 2

    if manual_paths is not None and (
        args.local_json_preflight is not None or bundle_paths is not None
    ):
        print(_render_manual_capture_mode_exclusivity_error())
        return 2

    if args.local_json_preflight is not None and bundle_paths is not None:
        print(_render_local_json_preflight_mode_exclusivity_error())
        return 2

    if manual_paths is not None:
        command = _build_manual_capture_command_request(args)
        conflicts = _manual_capture_conflicts(raw_argv, args)
        if conflicts:
            print(_render_manual_capture_conflict_error(command, conflicts))
            return 2

        try:
            validate_manual_explicit_alpaca_rvol_capture_command(command)
            config = load_config()
            result = run_manual_explicit_alpaca_rvol_capture_preflight(
                command,
                config,
            )
        except ManualExplicitAlpacaRvolCaptureCommandError as exc:
            print(render_manual_explicit_alpaca_rvol_capture_command_error(command, exc))
            return 2
        except MANUAL_EXPLICIT_ALPACA_CAPTURE_EXPECTED_ERRORS as exc:
            print(render_manual_explicit_alpaca_rvol_capture_error(command, exc))
            return 1

        if result.preflight_result is None or result.report is None:
            print(
                render_manual_explicit_alpaca_rvol_capture_stopped_report(
                    result,
                    command,
                )
            )
            return 1

        print(result.report)
        return 0 if is_manual_explicit_alpaca_rvol_capture_success(result) else 1

    if bundle_paths is not None:
        conflicts = _local_json_preflight_conflicts(raw_argv, args)
        if conflicts:
            print(
                _render_local_json_bundle_conflict_error(
                    bundle_metadata_path,
                    bundle_path,
                    conflicts,
                )
            )
            return 2

        if (
            args.local_json_bundle_preflight_report is not None
            and args.local_json_bundle_preflight_report == bundle_metadata_path
        ):
            print(
                _render_local_json_bundle_report_same_metadata_error(
                    bundle_metadata_path,
                    bundle_path,
                    args.local_json_bundle_preflight_report,
                )
            )
            return 2

        if (
            args.local_json_bundle_preflight_report is not None
            and args.local_json_bundle_preflight_report == bundle_path
        ):
            print(
                _render_local_json_bundle_report_same_bundle_error(
                    bundle_metadata_path,
                    bundle_path,
                    args.local_json_bundle_preflight_report,
                )
            )
            return 2

        exit_code = 1
        try:
            result = run_manual_local_json_bundle_preflight(
                bundle_metadata_path,
                bundle_path,
            )
        except MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS as exc:
            report = render_manual_local_json_bundle_preflight_error(
                bundle_metadata_path,
                bundle_path,
                exc,
            )
        else:
            report = render_manual_local_json_bundle_preflight_report(
                bundle_metadata_path,
                bundle_path,
                result,
            )
            exit_code = (
                0 if is_manual_local_json_bundle_preflight_success(result) else 1
            )

        if args.local_json_bundle_preflight_report is not None:
            try:
                write_manual_local_json_bundle_preflight_report(
                    args.local_json_bundle_preflight_report,
                    report,
                )
            except OSError as exc:
                print(
                    render_manual_local_json_bundle_preflight_export_error(
                        bundle_metadata_path,
                        bundle_path,
                        args.local_json_bundle_preflight_report,
                        exc,
                    )
                )
                return 1

        print(report)
        return exit_code

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
    except ProviderConfigurationError as exc:
        print(f"Provider configuration error: {exc}")
        return 1

    if args.loop and config.provider.strip().lower() == LIVE_COMPOSED_PROVIDER:
        print(_render_live_composed_loop_error())
        return 2

    try:
        provider = create_market_data_provider(config)
    except (
        ProviderConfigurationError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        JsonHistoricalSessionMetadataFileSourceError,
        JsonHistoricalRvolBundleError,
    ) as exc:
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
