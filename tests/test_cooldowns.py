from datetime import datetime, timedelta, timezone

from market_sentry.alerts import AlertCooldownManager, AlertEventType


def test_cooldown_manager_allows_first_alert() -> None:
    manager = AlertCooldownManager()
    now = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)

    assert manager.allow_alert("XTRM", AlertEventType.TIER_4_EXTREME_RUNNER, now)


def test_cooldown_manager_suppresses_repeated_alert_within_cooldown() -> None:
    manager = AlertCooldownManager()
    now = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)

    assert manager.allow_alert("XTRM", AlertEventType.HIGH_SCORE, now)
    assert not manager.allow_alert(
        "XTRM",
        AlertEventType.HIGH_SCORE,
        now + timedelta(minutes=4, seconds=59),
    )


def test_cooldown_manager_allows_alert_after_cooldown_expires() -> None:
    manager = AlertCooldownManager()
    now = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)

    assert manager.allow_alert("XTRM", AlertEventType.HIGH_SCORE, now)
    assert manager.allow_alert(
        "XTRM",
        AlertEventType.HIGH_SCORE,
        now + timedelta(minutes=5),
    )


def test_cooldown_logic_uses_symbol_and_event_type_key() -> None:
    manager = AlertCooldownManager()
    now = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)

    assert manager.allow_alert("XTRM", AlertEventType.TIER_4_EXTREME_RUNNER, now)
    assert manager.allow_alert("XTRM", AlertEventType.HIGH_SCORE, now)
    assert manager.allow_alert("MRUN", AlertEventType.TIER_4_EXTREME_RUNNER, now)
