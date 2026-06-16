import builtins

from market_sentry.alerts import (
    AlertEventType,
    LocalTTSSpeaker,
    NoOpSpeaker,
    SpeakerResult,
    collect_alert_messages,
)
from market_sentry.alerts.speaker import build_spoken_script
from market_sentry.alerts.formatter import format_alert_message
from market_sentry.scanner.engine import evaluate_candidate
from market_sentry.scanner.models import StockCandidate


def scanner_alert() -> object:
    from market_sentry.alerts import AlertEvent, AlertPriority

    scanner_result = evaluate_candidate(
        StockCandidate(
            symbol="VOICE",
            price=6.25,
            float_shares=1_500_000,
            daily_gain_percent=55.0,
            relative_volume=6.0,
            daily_volume=2_500_000,
        )
    )
    return AlertEvent(
        symbol="VOICE",
        event_type=AlertEventType.TIER_3_MAJOR_RUNNER,
        priority=AlertPriority.HIGH,
        message=format_alert_message(
            scanner_result,
            AlertEventType.TIER_3_MAJOR_RUNNER,
        ),
        scanner_result=scanner_result,
    )


def test_no_op_speaker_accepts_alert_events_and_messages_without_audio() -> None:
    speaker = NoOpSpeaker()

    result = speaker.speak([scanner_alert(), "Plain voice-ready message."])

    assert result == SpeakerResult(success=True, message_count=2)


def test_speaker_abstraction_can_process_multiple_messages_through_fake() -> None:
    class RecordingSpeaker:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def speak(self, items) -> SpeakerResult:
            self.messages.extend(collect_alert_messages(items))
            return SpeakerResult(success=True, message_count=len(self.messages))

    speaker = RecordingSpeaker()

    result = speaker.speak([scanner_alert(), "Second message."])

    assert result.success is True
    assert result.message_count == 2
    assert speaker.messages[0].startswith("VOICE major runner.")
    assert speaker.messages[1] == "Second message."


def test_build_spoken_script_combines_messages_into_readable_script() -> None:
    script = build_spoken_script(
        ["First alert message.", "Second alert message.", "  Third alert message.  "]
    )

    assert script == "First alert message. Second alert message. Third alert message."


def test_local_tts_speaker_handles_missing_optional_dependency(monkeypatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pyttsx3":
            raise ImportError("missing optional dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = LocalTTSSpeaker().speak(["Test message."])

    assert result.success is False
    assert result.message_count == 1
    assert result.error is not None
    assert "Voice playback unavailable" in result.error
    assert ".[voice]" in result.error


def test_local_tts_speaker_uses_injected_engine_without_real_audio() -> None:
    class FakeEngine:
        def __init__(self) -> None:
            self.spoken: list[str] = []
            self.run_count = 0

        def say(self, message: str) -> None:
            self.spoken.append(message)

        def runAndWait(self) -> None:
            self.run_count += 1

    engine = FakeEngine()

    result = LocalTTSSpeaker(engine_factory=lambda: engine).speak(
        ["First message.", "Second message."]
    )

    assert result == SpeakerResult(success=True, message_count=2)
    assert engine.spoken == ["First message. Second message."]
    assert engine.run_count == 1


def test_local_tts_speaker_fails_gracefully_on_engine_error() -> None:
    def failing_engine():
        raise RuntimeError("no voice available")

    result = LocalTTSSpeaker(engine_factory=failing_engine).speak(["Message."])

    assert result.success is False
    assert result.message_count == 1
    assert result.error == "Voice playback unavailable: no voice available"
