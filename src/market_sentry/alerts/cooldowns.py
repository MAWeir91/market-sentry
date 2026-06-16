"""In-memory alert cooldown tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Mapping

from market_sentry.alerts.events import AlertEventType


DEFAULT_COOLDOWNS: Mapping[AlertEventType, timedelta] = MappingProxyType(
    {
        AlertEventType.NEW_QUALIFIED: timedelta(minutes=10),
        AlertEventType.TIER_1_EARLY_HEAT: timedelta(minutes=10),
        AlertEventType.TIER_2_ACTIVE_MOMENTUM: timedelta(minutes=5),
        AlertEventType.TIER_3_MAJOR_RUNNER: timedelta(minutes=3),
        AlertEventType.TIER_4_EXTREME_RUNNER: timedelta(minutes=1),
        AlertEventType.HIGH_SCORE: timedelta(minutes=5),
    }
)


@dataclass
class AlertCooldownManager:
    """Track alert cooldowns in memory by symbol and event type."""

    cooldowns: Mapping[AlertEventType, timedelta] = field(
        default_factory=lambda: DEFAULT_COOLDOWNS
    )
    _last_alerted_at: dict[tuple[str, AlertEventType], datetime] = field(
        default_factory=dict
    )

    def is_allowed(
        self,
        symbol: str,
        event_type: AlertEventType,
        now: datetime,
    ) -> bool:
        """Return whether an alert is outside its cooldown window."""

        key = self._key(symbol, event_type)
        last_alerted_at = self._last_alerted_at.get(key)
        if last_alerted_at is None:
            return True
        return now - last_alerted_at >= self.cooldowns[event_type]

    def record_alert(
        self,
        symbol: str,
        event_type: AlertEventType,
        now: datetime,
    ) -> None:
        """Record that an alert was emitted at a supplied timestamp."""

        self._last_alerted_at[self._key(symbol, event_type)] = now

    def allow_alert(
        self,
        symbol: str,
        event_type: AlertEventType,
        now: datetime,
    ) -> bool:
        """Return true and record the alert when cooldown permits it."""

        if not self.is_allowed(symbol, event_type, now):
            return False
        self.record_alert(symbol, event_type, now)
        return True

    @staticmethod
    def _key(symbol: str, event_type: AlertEventType) -> tuple[str, AlertEventType]:
        return (symbol.upper(), event_type)
