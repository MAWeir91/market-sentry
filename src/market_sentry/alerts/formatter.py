"""Voice-friendly alert message formatting."""

from __future__ import annotations

from market_sentry.alerts.events import AlertEventType
from market_sentry.scanner.models import ScannerResult


def _format_float_words(value: int) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f} million"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f} thousand"
    return str(value)


def _activity_label(event_type: AlertEventType) -> str:
    labels = {
        AlertEventType.NEW_QUALIFIED: "new qualified scanner candidate",
        AlertEventType.TIER_1_EARLY_HEAT: "early heat",
        AlertEventType.TIER_2_ACTIVE_MOMENTUM: "active momentum",
        AlertEventType.TIER_3_MAJOR_RUNNER: "major runner",
        AlertEventType.TIER_4_EXTREME_RUNNER: "extreme runner",
        AlertEventType.HIGH_SCORE: "high scanner score",
    }
    return labels[event_type]


def format_alert_message(
    scanner_result: ScannerResult,
    event_type: AlertEventType,
) -> str:
    """Build a concise voice-ready market activity message."""

    candidate = scanner_result.candidate
    activity = _activity_label(event_type)

    if event_type is AlertEventType.HIGH_SCORE:
        return (
            f"{scanner_result.symbol} high scanner score. "
            f"Score {scanner_result.score:.1f}. "
            f"Up {candidate.daily_gain_percent:.1f} percent with "
            f"{candidate.relative_volume:.1f} relative volume."
        )

    return (
        f"{scanner_result.symbol} {activity}. "
        f"Up {candidate.daily_gain_percent:.1f} percent with "
        f"{candidate.relative_volume:.1f} relative volume. "
        f"Float {_format_float_words(candidate.float_shares)}. "
        f"Score {scanner_result.score:.1f}."
    )
