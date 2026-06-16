"""Voice-ready alert event layer for scanner results."""

from market_sentry.alerts.cooldowns import AlertCooldownManager, DEFAULT_COOLDOWNS
from market_sentry.alerts.events import (
    EVENT_PRIORITIES,
    AlertEvent,
    AlertEventType,
    AlertPriority,
)
from market_sentry.alerts.formatter import format_alert_message
from market_sentry.alerts.generator import (
    HIGH_SCORE_THRESHOLD,
    TIER_EVENT_TYPES,
    generate_alerts,
)
from market_sentry.alerts.speaker import (
    AlertSpeaker,
    AlertSpeechItem,
    LocalTTSSpeaker,
    NoOpSpeaker,
    SpeakerResult,
    collect_alert_messages,
)

__all__ = [
    "DEFAULT_COOLDOWNS",
    "EVENT_PRIORITIES",
    "HIGH_SCORE_THRESHOLD",
    "TIER_EVENT_TYPES",
    "AlertCooldownManager",
    "AlertEvent",
    "AlertEventType",
    "AlertPriority",
    "AlertSpeaker",
    "AlertSpeechItem",
    "LocalTTSSpeaker",
    "NoOpSpeaker",
    "SpeakerResult",
    "collect_alert_messages",
    "format_alert_message",
    "generate_alerts",
]
