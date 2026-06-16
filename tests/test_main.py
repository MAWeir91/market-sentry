import ast
import inspect

import market_sentry.__main__ as package_main
from market_sentry.alerts import SpeakerResult, collect_alert_messages, generate_alerts
from market_sentry.data import MockMarketDataProvider
from market_sentry.main import format_share_count, main, render_report
from market_sentry.scanner import ScannerEngine


class RecordingSpeaker:
    def __init__(self, result: SpeakerResult | None = None) -> None:
        self.messages: list[str] = []
        self.result = result

    def speak(self, items) -> SpeakerResult:
        self.messages.extend(collect_alert_messages(items))
        return self.result or SpeakerResult(
            success=True,
            message_count=len(self.messages),
        )


def test_format_share_count_uses_readable_units() -> None:
    assert format_share_count(750_000) == "750K"
    assert format_share_count(1_400_000) == "1.4M"
    assert format_share_count(10_000_000) == "10.0M"


def test_render_report_includes_meaningful_scanner_content() -> None:
    provider = MockMarketDataProvider()
    results = ScannerEngine().scan(provider.get_candidates())
    alerts = generate_alerts(results)

    report = render_report(results, alerts)

    assert "Market Sentry" in report
    assert "Mock Scanner Report" in report
    assert "Qualified Results" in report
    assert "Rejected Results" in report
    assert "Voice-Ready Alerts" in report
    assert "XTRM" in report
    assert "LOWP" in report
    assert "Tier 4: Extreme Runner" in report
    assert "Score:" in report
    assert "$11.40" in report
    assert "118.0%" in report
    assert "12.5x" in report
    assert "1.3M" in report
    assert "6.4M" in report
    assert "Rotation:" in report
    assert "15m:" in report
    assert "HOD:" in report
    assert "HOD Dist:" in report
    assert "Rotation: 4.9x" in report
    assert "15m: +14.8%" in report
    assert "HOD: $11.55" in report
    assert "HOD Dist: 1.3%" in report
    assert "15m: N/A" in report
    assert "HOD: N/A" in report
    assert "PRICE_BELOW_MIN" in report
    assert "[PASS]" in report
    assert "[FAIL]" in report
    assert "[CRITICAL] XTRM extreme runner." in report
    assert "[HIGH] XTRM high scanner score." in report


def test_render_report_shows_qualified_results_before_rejected_results() -> None:
    provider = MockMarketDataProvider()
    results = ScannerEngine().scan(provider.get_candidates())
    alerts = generate_alerts(results)
    report = render_report(results, alerts)

    assert report.index("Qualified Results") < report.index("Rejected Results")
    assert report.index("Rejected Results") < report.index("Voice-Ready Alerts")
    assert report.index("XTRM") < report.index("LOWP")


def test_render_report_shows_no_alerts_message_when_empty() -> None:
    provider = MockMarketDataProvider()
    results = ScannerEngine().scan(provider.get_candidates())

    report = render_report(results)

    assert "Voice-Ready Alerts" in report
    assert "No voice-ready alerts." in report


def test_voice_ready_alerts_are_generated_from_qualified_results_only() -> None:
    provider = MockMarketDataProvider()
    results = ScannerEngine().scan(provider.get_candidates())
    report = render_report(results, generate_alerts(results))
    alert_section = report.split("Voice-Ready Alerts", maxsplit=1)[1]

    assert "XTRM extreme runner" in alert_section
    assert "MRUN major runner" in alert_section
    assert "AMOM active momentum" in alert_section
    assert "EHT early heat" in alert_section
    assert "LOWP" not in alert_section
    assert "SLOW" not in alert_section
    assert any(
        priority in alert_section
        for priority in ("[LOW]", "[MEDIUM]", "[HIGH]", "[CRITICAL]")
    )


def test_voice_ready_alert_messages_avoid_trading_advice_language() -> None:
    provider = MockMarketDataProvider()
    results = ScannerEngine().scan(provider.get_candidates())
    report = render_report(results, generate_alerts(results))
    alert_section = report.split("Voice-Ready Alerts", maxsplit=1)[1].lower()
    banned_terms = {"buy", "sell", "enter", "exit", "guaranteed", "safe trade"}

    assert not any(term in alert_section for term in banned_terms)


def test_main_prints_mock_scanner_report(capsys) -> None:
    main([])

    output = capsys.readouterr().out

    assert "Market Sentry" in output
    assert "Qualified Results" in output
    assert "Rejected Results" in output
    assert "Voice-Ready Alerts" in output
    assert "Mock Scanner Report" in output


def test_cli_default_does_not_attempt_speech_playback(capsys) -> None:
    speaker = RecordingSpeaker()

    main([], speaker=speaker)

    output = capsys.readouterr().out
    assert "Market Sentry" in output
    assert "Voice-Ready Alerts" in output
    assert speaker.messages == []


def test_cli_no_speak_does_not_attempt_speech_playback(capsys) -> None:
    speaker = RecordingSpeaker()

    main(["--no-speak"], speaker=speaker)

    output = capsys.readouterr().out
    assert "Market Sentry" in output
    assert "Voice-Ready Alerts" in output
    assert speaker.messages == []


def test_cli_speak_routes_alert_messages_to_injected_speaker(capsys) -> None:
    speaker = RecordingSpeaker()

    main(["--speak"], speaker=speaker)

    output = capsys.readouterr().out
    assert "Market Sentry" in output
    assert "Voice-Ready Alerts" in output
    assert speaker.messages
    assert speaker.messages[0].startswith("XTRM extreme runner.")


def test_report_prints_even_when_speech_playback_fails(capsys) -> None:
    speaker = RecordingSpeaker(
        SpeakerResult(
            success=False,
            message_count=1,
            error="Voice playback unavailable: test failure",
        )
    )

    main(["--speak"], speaker=speaker)

    output = capsys.readouterr().out
    assert "Market Sentry" in output
    assert "Voice-Ready Alerts" in output
    assert "Voice playback unavailable: test failure" in output


def test_package_main_delegates_to_main() -> None:
    source = inspect.getsource(package_main)

    assert "from market_sentry.main import main" in source
    assert "main()" in source


def test_cli_runner_has_no_external_api_or_trading_behavior() -> None:
    import market_sentry.main as runner

    source = inspect.getsource(runner)
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

    assert not {"http", "requests", "socket", "urllib", "os"} & imported_modules
    assert "api_key" not in source.lower()
    assert "broker" not in source.lower()
    assert "text_to_speech" not in source.lower()
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()
