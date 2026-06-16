import ast
import inspect
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from market_sentry.alerts import (
    HIGH_SCORE_THRESHOLD,
    AlertCooldownManager,
    AlertEventType,
    AlertPriority,
    generate_alerts,
)
from market_sentry.alerts import generator
from market_sentry.scanner.engine import evaluate_candidate
from market_sentry.scanner.models import StockCandidate


def result_for(
    symbol: str,
    gain: float,
    relative_volume: float,
    daily_volume: int,
):
    return evaluate_candidate(
        StockCandidate(
            symbol=symbol,
            price=5.00,
            float_shares=2_000_000,
            daily_gain_percent=gain,
            relative_volume=relative_volume,
            daily_volume=daily_volume,
        )
    )


def event_types(alerts) -> list[AlertEventType]:
    return [alert.event_type for alert in alerts]


def test_alert_generator_creates_alerts_from_qualified_results() -> None:
    result = result_for("TWO", 25.0, 3.0, 1_000_000)

    alerts = generate_alerts([result])

    assert len(alerts) == 1
    assert alerts[0].symbol == "TWO"
    assert alerts[0].event_type == AlertEventType.TIER_2_ACTIVE_MOMENTUM
    assert alerts[0].priority == AlertPriority.MEDIUM
    assert "active momentum" in alerts[0].message


def test_alert_generator_ignores_rejected_results() -> None:
    rejected = evaluate_candidate(
        StockCandidate(
            symbol="FAIL",
            price=0.20,
            float_shares=2_000_000,
            daily_gain_percent=100.0,
            relative_volume=10.0,
            daily_volume=5_000_000,
        )
    )

    assert generate_alerts([rejected]) == []


def test_tier_1_maps_to_tier_1_event_type() -> None:
    alerts = generate_alerts([result_for("ONE", 10.0, 2.0, 500_000)])

    assert event_types(alerts) == [AlertEventType.TIER_1_EARLY_HEAT]


def test_tier_2_maps_to_tier_2_event_type() -> None:
    alerts = generate_alerts([result_for("TWO", 25.0, 3.0, 1_000_000)])

    assert event_types(alerts) == [AlertEventType.TIER_2_ACTIVE_MOMENTUM]


def test_tier_3_maps_to_tier_3_event_type() -> None:
    alerts = generate_alerts([result_for("THREE", 50.0, 5.0, 2_000_000)])

    assert event_types(alerts) == [AlertEventType.TIER_3_MAJOR_RUNNER]


def test_tier_4_maps_to_tier_4_event_type() -> None:
    result = result_for("FOUR", 100.0, 10.0, 5_000_000)
    lower_score_result = replace(result, score=89.9)

    alerts = generate_alerts([lower_score_result])

    assert event_types(alerts) == [AlertEventType.TIER_4_EXTREME_RUNNER]
    assert alerts[0].priority == AlertPriority.CRITICAL


def test_high_score_results_create_high_score_alert() -> None:
    result = result_for("XTRM", 118.0, 12.5, 6_400_000)

    alerts = generate_alerts([result])

    assert HIGH_SCORE_THRESHOLD == 90.0
    assert event_types(alerts) == [
        AlertEventType.TIER_4_EXTREME_RUNNER,
        AlertEventType.HIGH_SCORE,
    ]


def test_generator_applies_cooldowns_with_injected_timestamps() -> None:
    result = result_for("XTRM", 118.0, 12.5, 6_400_000)
    manager = AlertCooldownManager()
    now = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)

    first_alerts = generate_alerts([result], manager, created_at=now)
    repeated_alerts = generate_alerts(
        [result],
        manager,
        created_at=now + timedelta(seconds=30),
    )
    later_alerts = generate_alerts(
        [result],
        manager,
        created_at=now + timedelta(minutes=5),
    )

    assert event_types(first_alerts) == [
        AlertEventType.TIER_4_EXTREME_RUNNER,
        AlertEventType.HIGH_SCORE,
    ]
    assert repeated_alerts == []
    assert event_types(later_alerts) == [
        AlertEventType.TIER_4_EXTREME_RUNNER,
        AlertEventType.HIGH_SCORE,
    ]


def test_alert_layer_has_no_external_api_voice_playback_or_trading_behavior() -> None:
    source = inspect.getsource(generator)
    tree = ast.parse(source)
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert not {"http", "requests", "socket", "urllib", "os", "pyttsx3"} & imported_modules
    assert "api_key" not in source.lower()
    assert "broker" not in source.lower()
    assert "text_to_speech" not in source.lower()
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()
