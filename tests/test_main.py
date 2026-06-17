import ast
import inspect
from datetime import datetime, timedelta, timezone

import market_sentry.__main__ as package_main
from market_sentry.alerts import SpeakerResult, collect_alert_messages, generate_alerts
from market_sentry.config import AppConfig
from market_sentry.data import MockMarketDataProvider
from market_sentry.main import (
    DEFAULT_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    format_share_count,
    get_provider_display_label,
    main,
    normalize_interval,
    parse_args,
    render_live_readiness_report,
    render_report,
)
from market_sentry.live_readiness import evaluate_live_readiness
from market_sentry.scanner import ScannerEngine


class RecordingSpeaker:
    def __init__(self, result: SpeakerResult | None = None) -> None:
        self.messages: list[str] = []
        self.result = result
        self.calls = 0

    def speak(self, items) -> SpeakerResult:
        self.calls += 1
        messages = collect_alert_messages(items)
        self.messages.extend(messages)
        return self.result or SpeakerResult(
            success=True,
            message_count=len(messages),
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
    exit_code = main([])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Market Sentry" in output
    assert "Qualified Results" in output
    assert "Rejected Results" in output
    assert "Voice-Ready Alerts" in output
    assert "Mock Scanner Report" in output


def test_render_live_readiness_report_includes_stable_content() -> None:
    report = evaluate_live_readiness(AppConfig())

    rendered = render_live_readiness_report(report)

    assert "Market Sentry Live Readiness" in rendered
    assert "Status: NOT_READY" in rendered
    assert "[FAIL] PROVIDER_SELECTED" in rendered
    assert "[FAIL] RELATIVE_VOLUME_SOURCE_PRESENT" in rendered
    assert "Summary: Live readiness checks failed:" in rendered
    assert "does not call APIs" in rendered
    assert "does not activate live_composed" in rendered


def test_live_readiness_cli_prints_report_and_exits_one(capsys) -> None:
    exit_code = main(["--live-readiness"])

    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Market Sentry Live Readiness" in output
    assert "Status: NOT_READY" in output
    assert "PROVIDER_SELECTED" in output
    assert "RELATIVE_VOLUME_SOURCE_PRESENT" in output
    assert "Mock Scanner Report" not in output
    assert "Qualified Results" not in output


def test_live_readiness_cli_does_not_create_market_data_provider(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    def fail_provider_creation(_config):
        raise AssertionError("readiness path should not create providers")

    monkeypatch.setattr(runner, "create_market_data_provider", fail_provider_creation)

    exit_code = main(["--live-readiness"])

    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Market Sentry Live Readiness" in output


def test_live_readiness_cli_exits_zero_when_preconditions_pass(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "live_composed")
    monkeypatch.setenv("MARKET_SENTRY_ALLOW_LIVE_DATA", "true")
    monkeypatch.setenv("MARKET_SENTRY_WATCHLIST", "AAPL")
    monkeypatch.setenv("ALPACA_API_KEY", "placeholder-key")
    monkeypatch.setenv("ALPACA_API_SECRET", "placeholder-secret")
    monkeypatch.setenv("FMP_API_KEY", "placeholder-fmp-key")

    exit_code = main(["--live-readiness", "--relative-volume-configured"])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Status: READY" in output
    assert "[PASS] PROVIDER_SELECTED" in output
    assert "[PASS] RELATIVE_VOLUME_SOURCE_PRESENT" in output
    assert "placeholder-key" not in output
    assert "placeholder-secret" not in output
    assert "placeholder-fmp-key" not in output


def test_live_readiness_cli_rvol_check_fails_without_explicit_flag(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "live_composed")
    monkeypatch.setenv("MARKET_SENTRY_ALLOW_LIVE_DATA", "true")
    monkeypatch.setenv("MARKET_SENTRY_WATCHLIST", "AAPL")
    monkeypatch.setenv("ALPACA_API_KEY", "placeholder-key")
    monkeypatch.setenv("ALPACA_API_SECRET", "placeholder-secret")
    monkeypatch.setenv("FMP_API_KEY", "placeholder-fmp-key")

    exit_code = main(["--live-readiness"])

    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Status: NOT_READY" in output
    assert "[FAIL] RELATIVE_VOLUME_SOURCE_PRESENT" in output
    assert "[PASS] PROVIDER_SELECTED" in output


def test_live_readiness_cli_output_is_secret_safe(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "live_composed")
    monkeypatch.setenv("MARKET_SENTRY_ALLOW_LIVE_DATA", "true")
    monkeypatch.setenv("MARKET_SENTRY_WATCHLIST", "AAPL")
    monkeypatch.setenv("ALPACA_API_KEY", "visible-key-should-not-print")
    monkeypatch.setenv("ALPACA_API_SECRET", "visible-secret-should-not-print")
    monkeypatch.setenv("FMP_API_KEY", "visible-fmp-should-not-print")

    exit_code = main(["--live-readiness", "--relative-volume-configured"])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "visible-key-should-not-print" not in output
    assert "visible-secret-should-not-print" not in output
    assert "visible-fmp-should-not-print" not in output
    assert "Alpaca API key is present." in output
    assert "Alpaca API secret is present." in output
    assert "FMP API key is present." in output


def test_provider_display_label_maps_active_offline_providers() -> None:
    assert get_provider_display_label("mock") == "Mock Scanner Report"
    assert get_provider_display_label(" FIXTURE ") == "Fixture Scanner Report"
    assert (
        get_provider_display_label(" COMPOSED_FIXTURE ")
        == "Composed Fixture Scanner Report"
    )


def test_parse_args_has_default_interval_and_single_run_mode() -> None:
    args = parse_args([])

    assert args.loop is False
    assert args.speak is False
    assert args.interval == DEFAULT_INTERVAL_SECONDS
    assert args.live_readiness is False
    assert args.relative_volume_configured is False


def test_parse_args_supports_live_readiness_flags() -> None:
    args = parse_args(["--live-readiness", "--relative-volume-configured"])

    assert args.live_readiness is True
    assert args.relative_volume_configured is True


def test_interval_below_minimum_clamps_to_five_seconds() -> None:
    assert normalize_interval(1) == MIN_INTERVAL_SECONDS
    assert normalize_interval(5) == MIN_INTERVAL_SECONDS
    assert normalize_interval(30) == 30


def test_loop_mode_runs_finite_iterations_without_long_sleep(capsys) -> None:
    sleeps: list[float] = []
    now = datetime(2026, 6, 16, 14, 30, tzinfo=timezone.utc)

    exit_code = main(
        ["--loop", "--interval", "30"],
        sleep_fn=sleeps.append,
        now_fn=lambda: now,
        max_iterations=2,
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.count("Market Sentry") == 2
    assert "Scan Iteration: 1" in output
    assert "Scan Iteration: 2" in output
    assert sleeps == [30.0]


def test_loop_mode_clamps_interval_before_sleeping(capsys) -> None:
    sleeps: list[float] = []
    now = datetime(2026, 6, 16, 14, 30, tzinfo=timezone.utc)

    exit_code = main(
        ["--loop", "--interval", "1"],
        sleep_fn=sleeps.append,
        now_fn=lambda: now,
        max_iterations=2,
    )

    capsys.readouterr()

    assert exit_code == 0
    assert sleeps == [5.0]


def test_keyboard_interrupt_exits_loop_cleanly(capsys) -> None:
    now = datetime(2026, 6, 16, 14, 30, tzinfo=timezone.utc)

    def interrupting_sleep(_seconds: float) -> None:
        raise KeyboardInterrupt

    exit_code = main(
        ["--loop", "--interval", "5"],
        sleep_fn=interrupting_sleep,
        now_fn=lambda: now,
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Market Sentry loop stopped." in output
    assert "Traceback" not in output


def test_loop_speak_uses_speaker_path_and_cooldowns_suppress_repeats(capsys) -> None:
    speaker = RecordingSpeaker()
    now = datetime(2026, 6, 16, 14, 30, tzinfo=timezone.utc)

    exit_code = main(
        ["--loop", "--interval", "5", "--speak"],
        speaker=speaker,
        sleep_fn=lambda _seconds: None,
        now_fn=lambda: now,
        max_iterations=2,
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Scan Iteration: 1" in output
    assert "Scan Iteration: 2" in output
    assert speaker.calls == 2
    assert len(speaker.messages) == 5
    assert speaker.messages[0].startswith("XTRM extreme runner.")


def test_loop_speak_allows_alerts_after_cooldown_expires(capsys) -> None:
    speaker = RecordingSpeaker()
    times = iter(
        [
            datetime(2026, 6, 16, 14, 30, tzinfo=timezone.utc),
            datetime(2026, 6, 16, 14, 40, tzinfo=timezone.utc),
        ]
    )

    exit_code = main(
        ["--loop", "--interval", "5", "--speak"],
        speaker=speaker,
        sleep_fn=lambda _seconds: None,
        now_fn=lambda: next(times),
        max_iterations=2,
    )

    capsys.readouterr()

    assert exit_code == 0
    assert speaker.calls == 2
    assert len(speaker.messages) == 10


def test_loop_no_speak_does_not_use_speaker_path(capsys) -> None:
    speaker = RecordingSpeaker()
    now = datetime(2026, 6, 16, 14, 30, tzinfo=timezone.utc)

    exit_code = main(
        ["--loop", "--interval", "5", "--no-speak"],
        speaker=speaker,
        sleep_fn=lambda _seconds: None,
        now_fn=lambda: now,
        max_iterations=2,
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Scan Iteration: 1" in output
    assert "Scan Iteration: 2" in output
    assert speaker.messages == []
    assert speaker.calls == 0


def test_cli_default_does_not_attempt_speech_playback(capsys) -> None:
    speaker = RecordingSpeaker()

    exit_code = main([], speaker=speaker)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Market Sentry" in output
    assert "Voice-Ready Alerts" in output
    assert speaker.messages == []


def test_cli_no_speak_does_not_attempt_speech_playback(capsys) -> None:
    speaker = RecordingSpeaker()

    exit_code = main(["--no-speak"], speaker=speaker)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Market Sentry" in output
    assert "Voice-Ready Alerts" in output
    assert speaker.messages == []


def test_cli_speak_routes_alert_messages_to_injected_speaker(capsys) -> None:
    speaker = RecordingSpeaker()

    exit_code = main(["--speak"], speaker=speaker)

    output = capsys.readouterr().out
    assert exit_code == 0
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

    exit_code = main(["--speak"], speaker=speaker)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Market Sentry" in output
    assert "Voice-Ready Alerts" in output
    assert "Voice playback unavailable: test failure" in output


def test_package_main_delegates_to_main() -> None:
    source = inspect.getsource(package_main)

    assert "from market_sentry.main import main" in source
    assert "SystemExit(main())" in source


def test_runtime_explicit_mock_provider_works(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "mock")

    exit_code = main([])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Market Sentry" in output
    assert "Mock Scanner Report" in output
    assert "Qualified Results" in output


def test_runtime_fixture_provider_uses_fixture_report_label(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "fixture")

    exit_code = main([])

    output = capsys.readouterr().out
    header = output.split("Qualified Results", maxsplit=1)[0]

    assert exit_code == 0
    assert "Market Sentry" in output
    assert "Fixture Scanner Report" in header
    assert "Mock Scanner Report" not in header
    assert "XTRM" in output


def test_runtime_composed_fixture_provider_uses_composed_fixture_report_label(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "composed_fixture")

    exit_code = main([])

    output = capsys.readouterr().out
    header = output.split("Qualified Results", maxsplit=1)[0]
    header_lines = header.splitlines()

    assert exit_code == 0
    assert "Market Sentry" in output
    assert header_lines[1] == "Composed Fixture Scanner Report"
    assert "CMPX" in output


def test_loop_mode_uses_fixture_report_label(monkeypatch, capsys) -> None:
    sleeps: list[float] = []
    now = datetime(2026, 6, 16, 14, 30, tzinfo=timezone.utc)
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "fixture")

    exit_code = main(
        ["--loop", "--interval", "5"],
        sleep_fn=sleeps.append,
        now_fn=lambda: now,
        max_iterations=1,
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Fixture Scanner Report" in output
    assert "Mock Scanner Report" not in output
    assert "Scan Iteration: 1" in output
    assert sleeps == []


def test_fixture_voice_mode_still_uses_injected_speaker(monkeypatch, capsys) -> None:
    speaker = RecordingSpeaker()
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "fixture")

    exit_code = main(["--speak"], speaker=speaker)

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Fixture Scanner Report" in output
    assert speaker.messages
    assert speaker.messages[0].startswith("XTRM extreme runner.")


def test_composed_fixture_voice_mode_still_uses_injected_speaker(monkeypatch, capsys) -> None:
    speaker = RecordingSpeaker()
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "composed_fixture")

    exit_code = main(["--speak"], speaker=speaker)

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Composed Fixture Scanner Report" in output
    assert speaker.messages
    assert speaker.messages[0].startswith("CMPX")


def test_runtime_alpaca_placeholder_fails_cleanly(monkeypatch, capsys) -> None:
    speaker = RecordingSpeaker()
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "alpaca")

    exit_code = main(["--speak"], speaker=speaker)

    output = capsys.readouterr().out

    assert exit_code == 1
    assert (
        "Provider configuration error: Alpaca provider is a future placeholder. "
        "Live API implementation is not present yet."
    ) in output
    assert "Market Sentry" not in output
    assert "Mock Scanner Report" not in output
    assert "Fixture Scanner Report" not in output
    assert "Composed Fixture Scanner Report" not in output
    assert "Traceback" not in output
    assert speaker.calls == 0


def test_runtime_live_composed_failed_gate_fails_cleanly_without_report(
    monkeypatch,
    capsys,
) -> None:
    speaker = RecordingSpeaker()
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "live_composed")

    exit_code = main(["--speak"], speaker=speaker)

    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Provider configuration error:" in output
    assert "live_composed is not enabled." in output
    assert "LIVE_DATA_NOT_ALLOWED" in output
    assert "MISSING_WATCHLIST" in output
    assert "MISSING_ALPACA_API_KEY" in output
    assert "MISSING_ALPACA_API_SECRET" in output
    assert "MISSING_FMP_API_KEY" in output
    assert "Market Sentry" not in output
    assert "Mock Scanner Report" not in output
    assert "Fixture Scanner Report" not in output
    assert "Composed Fixture Scanner Report" not in output
    assert "Qualified Results" not in output
    assert "Traceback" not in output
    assert speaker.calls == 0


def test_runtime_live_composed_gate_passing_placeholder_fails_cleanly(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "live_composed")
    monkeypatch.setenv("MARKET_SENTRY_ALLOW_LIVE_DATA", "true")
    monkeypatch.setenv("MARKET_SENTRY_WATCHLIST", "AAPL")
    monkeypatch.setenv("ALPACA_API_KEY", "visible-key-should-not-print")
    monkeypatch.setenv("ALPACA_API_SECRET", "visible-secret-should-not-print")
    monkeypatch.setenv("FMP_API_KEY", "visible-fmp-should-not-print")

    exit_code = main([])

    output = capsys.readouterr().out

    assert exit_code == 1
    assert (
        "Provider configuration error: live_composed is reserved for a future "
        "live provider and is not active yet."
    ) in output
    assert "visible-key-should-not-print" not in output
    assert "visible-secret-should-not-print" not in output
    assert "visible-fmp-should-not-print" not in output
    assert "Market Sentry" not in output
    assert "Qualified Results" not in output
    assert "Traceback" not in output


def test_runtime_unknown_provider_fails_cleanly(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "bad_provider")

    exit_code = main([])

    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Provider configuration error: Unknown market data provider: bad_provider" in output
    assert "Market Sentry" not in output
    assert "Mock Scanner Report" not in output
    assert "Fixture Scanner Report" not in output
    assert "Composed Fixture Scanner Report" not in output
    assert "Traceback" not in output


def test_provider_error_does_not_enter_loop(monkeypatch, capsys) -> None:
    sleeps: list[float] = []
    speaker = RecordingSpeaker()
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "alpaca")

    exit_code = main(
        ["--loop", "--interval", "5", "--speak"],
        speaker=speaker,
        sleep_fn=sleeps.append,
        max_iterations=2,
    )

    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Provider configuration error:" in output
    assert "Scan Iteration:" not in output
    assert sleeps == []
    assert speaker.calls == 0


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
    assert "StdlibHttpTransport" not in source
    assert "AlpacaSnapshotFetcher" not in source
    assert "FMPFloatFetcher" not in source
    assert ".send(" not in source
    assert "api_key" not in source.lower()
    assert "broker" not in source.lower()
    assert "text_to_speech" not in source.lower()
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()
