"""Command-line runner for the local mock Market Sentry scanner."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from typing import Sequence

from market_sentry.alerts import AlertEvent, AlertSpeaker, LocalTTSSpeaker, generate_alerts
from market_sentry.data import MockMarketDataProvider
from market_sentry.scanner import ScannerEngine, ScannerResult


def format_share_count(value: int) -> str:
    """Format share counts for compact terminal output."""

    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f}K"
    return str(value)


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
) -> str:
    """Render scanner results and voice-ready alerts for terminal output."""

    result_list = list(results)
    alert_list = list(alerts)
    qualified_results = [result for result in result_list if result.qualified]
    rejected_results = [result for result in result_list if not result.qualified]

    lines = [
        "Market Sentry",
        "Mock Scanner Report",
        "",
        "Qualified Results",
        "-----------------",
    ]

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
    """Parse the small Phase 6 CLI surface."""

    parser = argparse.ArgumentParser(add_help=False)
    speak_group = parser.add_mutually_exclusive_group()
    speak_group.add_argument("--speak", action="store_true", dest="speak")
    speak_group.add_argument("--no-speak", action="store_false", dest="speak")
    parser.set_defaults(speak=False)
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    speaker: AlertSpeaker | None = None,
) -> None:
    """Run the local mock provider through the scanner and print a report."""

    args = parse_args(argv)
    provider = MockMarketDataProvider()
    candidates = provider.get_candidates()
    results = ScannerEngine().scan(candidates)
    alerts = generate_alerts(results)
    print(render_report(results, alerts))

    if args.speak:
        voice_speaker = speaker or LocalTTSSpeaker()
        speech_result = voice_speaker.speak(alerts)
        if not speech_result.success and speech_result.error is not None:
            print(f"\n{speech_result.error}")


if __name__ == "__main__":
    main()
