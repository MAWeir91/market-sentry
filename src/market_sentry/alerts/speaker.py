"""Optional local speech output for voice-ready alert messages."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from market_sentry.alerts.events import AlertEvent

AlertSpeechItem = AlertEvent | str


@dataclass(frozen=True)
class SpeakerResult:
    """Result from attempting to speak alert messages."""

    success: bool
    message_count: int
    error: str | None = None


class AlertSpeaker(Protocol):
    """Speaker contract for alert messages or alert events."""

    def speak(self, items: Iterable[AlertSpeechItem]) -> SpeakerResult:
        """Speak or accept alert messages."""
        ...


def alert_message(item: AlertSpeechItem) -> str:
    """Return the existing voice-ready message for an alert item."""

    if isinstance(item, AlertEvent):
        return item.message
    return str(item)


def collect_alert_messages(items: Iterable[AlertSpeechItem]) -> tuple[str, ...]:
    """Normalize alert events or strings into message text."""

    return tuple(alert_message(item) for item in items)


def build_spoken_script(messages: Iterable[str]) -> str:
    """Combine alert messages into one readable spoken script."""

    cleaned_messages = tuple(message.strip() for message in messages if message.strip())
    return " ".join(cleaned_messages)


class NoOpSpeaker:
    """Safe speaker that accepts messages without audio playback."""

    def speak(self, items: Iterable[AlertSpeechItem]) -> SpeakerResult:
        messages = collect_alert_messages(items)
        return SpeakerResult(success=True, message_count=len(messages))


class LocalTTSSpeaker:
    """Local text-to-speech speaker using optional pyttsx3."""

    def __init__(self, engine_factory: Callable[[], object] | None = None) -> None:
        self._engine_factory = engine_factory

    def speak(self, items: Iterable[AlertSpeechItem]) -> SpeakerResult:
        messages = collect_alert_messages(items)
        if not messages:
            return SpeakerResult(success=True, message_count=0)

        try:
            engine = self._create_engine()
            spoken_script = build_spoken_script(messages)
            engine.say(spoken_script)
            engine.runAndWait()
        except ImportError:
            return SpeakerResult(
                success=False,
                message_count=len(messages),
                error=(
                    "Voice playback unavailable: install voice dependencies with "
                    'python -m pip install -e ".[voice]"'
                ),
            )
        except Exception as exc:
            return SpeakerResult(
                success=False,
                message_count=len(messages),
                error=f"Voice playback unavailable: {exc}",
            )

        return SpeakerResult(success=True, message_count=len(messages))

    def _create_engine(self) -> object:
        if self._engine_factory is not None:
            return self._engine_factory()

        import pyttsx3

        return pyttsx3.init()
