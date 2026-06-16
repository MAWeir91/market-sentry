"""Structured alert event models for voice-ready scanner alerts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Any, Mapping

from market_sentry.scanner.models import ScannerResult


class AlertEventType(Enum):
    """Alert event types produced from scanner results."""

    NEW_QUALIFIED = "NEW_QUALIFIED"
    TIER_1_EARLY_HEAT = "TIER_1_EARLY_HEAT"
    TIER_2_ACTIVE_MOMENTUM = "TIER_2_ACTIVE_MOMENTUM"
    TIER_3_MAJOR_RUNNER = "TIER_3_MAJOR_RUNNER"
    TIER_4_EXTREME_RUNNER = "TIER_4_EXTREME_RUNNER"
    HIGH_SCORE = "HIGH_SCORE"


class AlertPriority(IntEnum):
    """Alert priorities ordered from least to most urgent."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


EVENT_PRIORITIES: Mapping[AlertEventType, AlertPriority] = MappingProxyType(
    {
        AlertEventType.NEW_QUALIFIED: AlertPriority.LOW,
        AlertEventType.TIER_1_EARLY_HEAT: AlertPriority.LOW,
        AlertEventType.TIER_2_ACTIVE_MOMENTUM: AlertPriority.MEDIUM,
        AlertEventType.TIER_3_MAJOR_RUNNER: AlertPriority.HIGH,
        AlertEventType.TIER_4_EXTREME_RUNNER: AlertPriority.CRITICAL,
        AlertEventType.HIGH_SCORE: AlertPriority.HIGH,
    }
)


@dataclass(frozen=True)
class AlertEvent:
    """A structured voice-ready alert derived from a scanner result."""

    symbol: str
    event_type: AlertEventType
    priority: AlertPriority
    message: str
    scanner_result: ScannerResult
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)
