"""Command-line runner for the local mock Market Sentry scanner."""

from __future__ import annotations

from collections.abc import Iterable

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


def render_report(results: Iterable[ScannerResult]) -> str:
    """Render scanner results as a readable deterministic terminal report."""

    result_list = list(results)
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

    return "\n".join(lines)


def main() -> None:
    """Run the local mock provider through the scanner and print a report."""

    provider = MockMarketDataProvider()
    candidates = provider.get_candidates()
    results = ScannerEngine().scan(candidates)
    print(render_report(results))


if __name__ == "__main__":
    main()
