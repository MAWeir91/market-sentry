from datetime import datetime, timezone

from market_sentry.alerts import AlertEvent, AlertEventType, AlertPriority, EVENT_PRIORITIES
from market_sentry.scanner.engine import evaluate_candidate
from market_sentry.scanner.models import StockCandidate


def test_alert_event_model_can_be_created() -> None:
    scanner_result = evaluate_candidate(
        StockCandidate(
            symbol="ALRT",
            price=4.20,
            float_shares=2_000_000,
            daily_gain_percent=28.0,
            relative_volume=3.4,
            daily_volume=1_200_000,
        )
    )
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    event = AlertEvent(
        symbol="ALRT",
        event_type=AlertEventType.TIER_2_ACTIVE_MOMENTUM,
        priority=AlertPriority.MEDIUM,
        message="ALRT active momentum. Up 28.0 percent.",
        scanner_result=scanner_result,
        created_at=created_at,
        metadata={"score": scanner_result.score},
    )

    assert event.symbol == "ALRT"
    assert event.event_type == AlertEventType.TIER_2_ACTIVE_MOMENTUM
    assert event.priority == AlertPriority.MEDIUM
    assert event.scanner_result == scanner_result
    assert event.created_at == created_at
    assert event.metadata["score"] == scanner_result.score


def test_alert_priorities_are_correct() -> None:
    assert AlertPriority.LOW < AlertPriority.MEDIUM < AlertPriority.HIGH
    assert AlertPriority.HIGH < AlertPriority.CRITICAL
    assert EVENT_PRIORITIES[AlertEventType.NEW_QUALIFIED] == AlertPriority.LOW
    assert EVENT_PRIORITIES[AlertEventType.TIER_1_EARLY_HEAT] == AlertPriority.LOW
    assert (
        EVENT_PRIORITIES[AlertEventType.TIER_2_ACTIVE_MOMENTUM]
        == AlertPriority.MEDIUM
    )
    assert EVENT_PRIORITIES[AlertEventType.TIER_3_MAJOR_RUNNER] == AlertPriority.HIGH
    assert (
        EVENT_PRIORITIES[AlertEventType.TIER_4_EXTREME_RUNNER]
        == AlertPriority.CRITICAL
    )
    assert EVENT_PRIORITIES[AlertEventType.HIGH_SCORE] == AlertPriority.HIGH
