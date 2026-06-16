"""Alert generation from scanner results."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from market_sentry.alerts.cooldowns import AlertCooldownManager
from market_sentry.alerts.events import AlertEvent, AlertEventType, EVENT_PRIORITIES
from market_sentry.alerts.formatter import format_alert_message
from market_sentry.scanner.models import ScannerResult, ScannerTier


HIGH_SCORE_THRESHOLD = 90.0

TIER_EVENT_TYPES: dict[ScannerTier, AlertEventType] = {
    ScannerTier.EARLY_HEAT: AlertEventType.TIER_1_EARLY_HEAT,
    ScannerTier.ACTIVE_MOMENTUM: AlertEventType.TIER_2_ACTIVE_MOMENTUM,
    ScannerTier.MAJOR_RUNNER: AlertEventType.TIER_3_MAJOR_RUNNER,
    ScannerTier.EXTREME_RUNNER: AlertEventType.TIER_4_EXTREME_RUNNER,
}


def _event_types_for_result(scanner_result: ScannerResult) -> list[AlertEventType]:
    if not scanner_result.qualified or scanner_result.tier is None:
        return []

    event_types = [TIER_EVENT_TYPES[scanner_result.tier]]
    if scanner_result.score >= HIGH_SCORE_THRESHOLD:
        event_types.append(AlertEventType.HIGH_SCORE)
    return event_types


def generate_alerts(
    scanner_results: Iterable[ScannerResult],
    cooldown_manager: AlertCooldownManager | None = None,
    created_at: datetime | None = None,
) -> list[AlertEvent]:
    """Generate voice-ready alert events from qualified scanner results only."""

    event_time = created_at or datetime.now(timezone.utc)
    alerts: list[AlertEvent] = []

    for scanner_result in scanner_results:
        for event_type in _event_types_for_result(scanner_result):
            if cooldown_manager is not None and not cooldown_manager.allow_alert(
                scanner_result.symbol,
                event_type,
                event_time,
            ):
                continue

            alerts.append(
                AlertEvent(
                    symbol=scanner_result.symbol,
                    event_type=event_type,
                    priority=EVENT_PRIORITIES[event_type],
                    message=format_alert_message(scanner_result, event_type),
                    scanner_result=scanner_result,
                    created_at=event_time,
                    metadata={"score": scanner_result.score},
                )
            )

    return alerts
