import ast
import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import market_sentry.__main__ as package_main
import pytest
from market_sentry.alerts import SpeakerResult, collect_alert_messages, generate_alerts
from market_sentry.config import AppConfig
from market_sentry.data import MockMarketDataProvider
from market_sentry.data.json_historical_session_metadata_source import (
    JsonHistoricalSessionMetadataFileSourceError,
)
from market_sentry.data.json_historical_rvol_bundle import JsonHistoricalRvolBundleError
from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    get_local_json_metadata_preflight_scenario,
)
from market_sentry.data.local_json_metadata_preflight_scenario_harness import (
    run_local_json_metadata_preflight_scenario,
)
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
    assert "does not read or preflight artifacts" in rendered
    assert "call APIs" in rendered
    assert "or activate live_composed" in rendered


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
    monkeypatch.setenv("MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH", "rvol.json")

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
    monkeypatch.setenv("MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH", "rvol.json")

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
    monkeypatch.setenv("MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH", "rvol.json")

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
    assert args.local_json_preflight is None
    assert args.local_json_preflight_report is None
    assert args.local_json_bundle_preflight is None
    assert args.local_json_bundle_preflight_report is None


def test_parse_args_supports_local_json_preflight_path() -> None:
    args = parse_args(["--local-json-preflight", "metadata.json"])

    assert args.local_json_preflight == Path("metadata.json")


def test_parse_args_supports_local_json_preflight_report_path() -> None:
    args = parse_args(["--local-json-preflight-report", "report.txt"])

    assert args.local_json_preflight_report == Path("report.txt")


def test_parse_args_supports_local_json_bundle_preflight_paths() -> None:
    args = parse_args(
        [
            "--local-json-bundle-preflight",
            "metadata.json",
            "bundle.json",
        ]
    )

    assert args.local_json_bundle_preflight == [
        Path("metadata.json"),
        Path("bundle.json"),
    ]


def test_parse_args_supports_local_json_bundle_preflight_report_path() -> None:
    args = parse_args(["--local-json-bundle-preflight-report", "bundle-report.txt"])

    assert args.local_json_bundle_preflight_report == Path("bundle-report.txt")


def test_parse_args_supports_manual_alpaca_rvol_capture_values() -> None:
    args = parse_args(
        [
            "--manual-alpaca-rvol-capture",
            "seed.json",
            "metadata.json",
            "bundle.json",
            "--manual-alpaca-rvol-capture-report",
            "report.txt",
            "--manual-alpaca-rvol-capture-confirm-live-data",
            "--manual-alpaca-rvol-capture-symbol",
            "RVOL",
            "--manual-alpaca-rvol-capture-historical-start",
            "2026-01-02T09:30:00Z",
            "--manual-alpaca-rvol-capture-historical-end",
            "2026-01-21T10:00:00Z",
            "--manual-alpaca-rvol-capture-historical-max-pages",
            "5",
            "--manual-alpaca-rvol-capture-current-start",
            "2026-01-31T09:30:00Z",
            "--manual-alpaca-rvol-capture-current-end",
            "2026-01-31T09:35:00Z",
            "--manual-alpaca-rvol-capture-current-max-pages",
            "2",
            "--manual-alpaca-rvol-capture-current-session-id",
            "CURRENT-001",
            "--manual-alpaca-rvol-capture-bucket",
            "09:35",
            "--manual-alpaca-rvol-capture-cutoff",
            "2026-01-31T09:35:00Z",
            "--manual-alpaca-rvol-capture-minimum-historical-sessions",
            "20",
            "--manual-alpaca-rvol-capture-timeframe",
            "5Min",
            "--manual-alpaca-rvol-capture-page-limit",
            "500",
            "--manual-alpaca-rvol-capture-sort",
            "desc",
        ]
    )

    assert args.manual_alpaca_rvol_capture == [
        Path("seed.json"),
        Path("metadata.json"),
        Path("bundle.json"),
    ]
    assert args.manual_alpaca_rvol_capture_report == Path("report.txt")
    assert args.manual_alpaca_rvol_capture_confirm_live_data is True
    assert args.manual_alpaca_rvol_capture_symbol == "RVOL"
    assert args.manual_alpaca_rvol_capture_historical_max_pages == 5
    assert args.manual_alpaca_rvol_capture_current_max_pages == 2
    assert args.manual_alpaca_rvol_capture_timeframe == "5Min"
    assert args.manual_alpaca_rvol_capture_page_limit == 500
    assert args.manual_alpaca_rvol_capture_sort == "desc"


def test_parse_args_supports_local_rvol_session_seed_paths() -> None:
    args = parse_args(
        [
            "--local-rvol-session-seed",
            "plan.json",
            "metadata.json",
        ]
    )

    assert args.local_rvol_session_seed == [
        Path("plan.json"),
        Path("metadata.json"),
    ]


def test_parse_args_supports_local_rvol_artifact_preflight_path() -> None:
    args = parse_args(["--local-rvol-artifact-preflight", "manifest.json"])

    assert args.local_rvol_artifact_preflight == Path("manifest.json")


def test_parse_args_supports_local_rvol_artifact_manifest_writer_values() -> None:
    args = parse_args(
        [
            "--local-rvol-artifact-manifest-write",
            "manifest.json",
            "--local-rvol-artifact",
            "AAPL",
            "aapl-meta.json",
            "aapl-bundle.json",
            "--local-rvol-artifact",
            "MSFT",
            "msft-meta.json",
            "msft-bundle.json",
        ]
    )

    assert args.local_rvol_artifact_manifest_write == Path("manifest.json")
    assert args.local_rvol_artifact == [
        ["AAPL", "aapl-meta.json", "aapl-bundle.json"],
        ["MSFT", "msft-meta.json", "msft-bundle.json"],
    ]


def test_parse_args_manual_alpaca_rvol_capture_defaults() -> None:
    args = parse_args([])

    assert args.manual_alpaca_rvol_capture is None
    assert args.manual_alpaca_rvol_capture_report is None
    assert args.manual_alpaca_rvol_capture_confirm_live_data is False
    assert args.manual_alpaca_rvol_capture_timeframe == "1Min"
    assert args.manual_alpaca_rvol_capture_page_limit == 1000
    assert args.manual_alpaca_rvol_capture_sort == "asc"
    assert args.local_rvol_session_seed is None
    assert args.local_rvol_artifact_preflight is None
    assert args.local_rvol_artifact_manifest_write is None
    assert args.local_rvol_artifact is None


def test_parse_args_supports_live_readiness_flags() -> None:
    args = parse_args(["--live-readiness", "--relative-volume-configured"])

    assert args.live_readiness is True
    assert args.relative_volume_configured is True


def test_parse_args_keeps_existing_voice_flag_exclusivity_without_local_preflight() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--speak", "--no-speak"])


def _manual_capture_argv(*extra: str) -> list[str]:
    return [
        "--manual-alpaca-rvol-capture",
        "seed.json",
        "metadata.json",
        "bundle.json",
        "--manual-alpaca-rvol-capture-confirm-live-data",
        "--manual-alpaca-rvol-capture-symbol",
        "RVOL",
        "--manual-alpaca-rvol-capture-historical-start",
        "2026-01-02T09:30:00Z",
        "--manual-alpaca-rvol-capture-historical-end",
        "2026-01-21T10:00:00Z",
        "--manual-alpaca-rvol-capture-historical-max-pages",
        "5",
        "--manual-alpaca-rvol-capture-current-start",
        "2026-01-31T09:30:00Z",
        "--manual-alpaca-rvol-capture-current-end",
        "2026-01-31T09:35:00Z",
        "--manual-alpaca-rvol-capture-current-max-pages",
        "2",
        "--manual-alpaca-rvol-capture-current-session-id",
        "CURRENT-001",
        "--manual-alpaca-rvol-capture-bucket",
        "09:35",
        "--manual-alpaca-rvol-capture-cutoff",
        "2026-01-31T09:35:00Z",
        "--manual-alpaca-rvol-capture-minimum-historical-sessions",
        "20",
        *extra,
    ]


def _local_rvol_session_seed_argv(*extra: str) -> list[str]:
    return [
        "--local-rvol-session-seed",
        "plan.json",
        "metadata.json",
        *extra,
    ]


def _local_rvol_artifact_audit_argv(*extra: str) -> list[str]:
    return [
        "--local-rvol-artifact-preflight",
        "manifest.json",
        *extra,
    ]


def _local_rvol_artifact_manifest_writer_argv(*extra: str) -> list[str]:
    return [
        "--local-rvol-artifact-manifest-write",
        "manifest.json",
        "--local-rvol-artifact",
        "AAPL",
        "aapl-meta.json",
        "aapl-bundle.json",
        *extra,
    ]


def _session_seed_plan_payload(**overrides) -> dict[str, object]:
    value = {
        "schema_version": 1,
        "symbol": "rvol",
        "bucket": "regular",
        "current_session_id": "2026-06-18",
        "sessions": [
            {
                "session_id": "2026-06-17",
                "session_start_timestamp": "2026-06-17T13:30:00Z",
                "session_end_timestamp": "2026-06-17T20:00:00Z",
                "cutoff_timestamp": "2026-06-17T14:00:00Z",
                "is_complete": True,
            }
        ],
    }
    value.update(overrides)
    return value


def _fail_if_runtime_work_runs(monkeypatch) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("local preflight should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("local preflight should not create providers"),
    )
    monkeypatch.setattr(
        runner,
        "_run_scan",
        lambda **_kwargs: pytest.fail("local preflight should not scan"),
    )
    monkeypatch.setattr(
        runner,
        "evaluate_live_readiness",
        lambda *_args, **_kwargs: pytest.fail(
            "local preflight should not run readiness"
        ),
    )


def test_local_rvol_session_seed_success_runs_before_config(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    plan_path = tmp_path / "plan.json"
    metadata_path = tmp_path / "metadata.json"
    plan_path.write_text(json.dumps(_session_seed_plan_payload()), encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("session seed should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("session seed should not create providers"),
    )
    monkeypatch.setattr(
        runner,
        "_run_scan",
        lambda **_kwargs: pytest.fail("session seed should not scan"),
    )

    exit_code = main(
        ["--local-rvol-session-seed", str(plan_path), str(metadata_path)]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Market Sentry Local RVOL Session Seed" in output
    assert f"Plan Path: {plan_path}" in output
    assert f"Metadata Path: {metadata_path}" in output
    assert "Input Mode: EXPLICIT_SESSION_PLAN" in output
    assert "Result: WRITTEN" in output
    assert "does not infer calendars or call APIs" in output
    assert metadata_path.exists()


def test_local_rvol_session_seed_same_path_returns_command_error(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("session seed command error should not load config"),
    )
    exit_code = main(["--local-rvol-session-seed", "same.json", "same.json"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Result: COMMAND_ERROR" in output
    assert "PLAN_PATH_EQUALS_METADATA_OUTPUT" in output


def test_local_rvol_session_seed_invalid_plan_returns_operational_error(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    plan_path = tmp_path / "plan.json"
    metadata_path = tmp_path / "metadata.json"
    plan_path.write_text(
        json.dumps(_session_seed_plan_payload(sessions=[])),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("session seed operational error should not load config"),
    )

    exit_code = main(
        ["--local-rvol-session-seed", str(plan_path), str(metadata_path)]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Result: ERROR" in output
    assert "LocalRvolSessionSeedPlanError" in output
    assert "EMPTY_SESSIONS" in output
    assert not metadata_path.exists()


def test_local_rvol_session_seed_conflicts_preserve_raw_order(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("session seed conflict should not load config"),
    )
    exit_code = main(
        [
            "--no-speak",
            "--local-rvol-session-seed",
            "plan.json",
            "metadata.json",
            "--loop",
            "--speak",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Result: COMMAND_ERROR" in output
    assert (
        "Error: --local-rvol-session-seed cannot be combined with: "
        "--no-speak, --loop, --speak"
    ) in output


def test_local_rvol_artifact_audit_success_runs_before_config(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    result = object()
    calls = []
    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("artifact audit should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("artifact audit should not create providers"),
    )
    monkeypatch.setattr(
        runner,
        "_run_scan",
        lambda **_kwargs: pytest.fail("artifact audit should not scan"),
    )
    monkeypatch.setattr(
        runner,
        "evaluate_live_readiness",
        lambda *_args, **_kwargs: pytest.fail("artifact audit should not run readiness"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_audit",
        lambda command: calls.append(command) or result,
    )
    monkeypatch.setattr(
        runner,
        "render_local_rvol_artifact_audit_report",
        lambda command, value: "artifact audit report",
    )
    monkeypatch.setattr(
        runner,
        "is_local_rvol_artifact_audit_success",
        lambda value: True,
    )

    exit_code = main(["--local-rvol-artifact-preflight", "manifest.json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output == "artifact audit report\n"
    assert calls
    assert calls[0].manifest_path == Path("manifest.json")


def test_local_rvol_artifact_audit_operation_error_before_config(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("artifact audit operation error should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_audit",
        lambda _command: (_ for _ in ()).throw(FileNotFoundError("missing")),
    )

    exit_code = main(["--local-rvol-artifact-preflight", "missing-manifest.json"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Market Sentry Local RVOL Artifact Preflight" in output
    assert "Manifest Path: missing-manifest.json" in output
    assert "Result: ERROR" in output
    assert "Error Type: FileNotFoundError" in output
    assert "missing" in output


def test_local_rvol_artifact_audit_failed_result_exits_one_without_config(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    result = object()
    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("artifact audit failed result should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_audit",
        lambda _command: result,
    )
    monkeypatch.setattr(
        runner,
        "render_local_rvol_artifact_audit_report",
        lambda _command, _result: "failed artifact audit report",
    )
    monkeypatch.setattr(
        runner,
        "is_local_rvol_artifact_audit_success",
        lambda _result: False,
    )

    exit_code = main(["--local-rvol-artifact-preflight", "manifest.json"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert output == "failed artifact audit report\n"


def test_local_rvol_artifact_audit_conflicts_preserve_raw_order(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("artifact audit conflict should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_audit",
        lambda _command: pytest.fail("artifact audit helper should not run"),
    )

    exit_code = main(
        [
            "--no-speak",
            "--local-rvol-artifact-preflight",
            "manifest.json",
            "--loop",
            "--speak",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local RVOL Artifact Preflight" in output
    assert "Result: COMMAND_ERROR" in output
    assert (
        "Error: --local-rvol-artifact-preflight cannot be combined with: "
        "--no-speak, --loop, --speak"
    ) in output


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        (["--loop"], "--loop"),
        (["--interval", "10"], "--interval"),
        (["--interval=10"], "--interval"),
        (["--live-readiness"], "--live-readiness"),
        (["--relative-volume-configured"], "--relative-volume-configured"),
        (["--speak"], "--speak"),
        (["--no-speak"], "--no-speak"),
        (["--local-json-preflight", "metadata.json"], "--local-json-preflight"),
        (["--local-json-preflight-report", "report.txt"], "--local-json-preflight-report"),
        (
            ["--local-json-bundle-preflight", "metadata.json", "bundle.json"],
            "--local-json-bundle-preflight",
        ),
        (
            ["--local-json-bundle-preflight-report", "bundle-report.txt"],
            "--local-json-bundle-preflight-report",
        ),
        (
            ["--manual-alpaca-rvol-capture", "seed.json", "meta.json", "bundle.json"],
            "--manual-alpaca-rvol-capture",
        ),
        (
            ["--manual-alpaca-rvol-capture-report", "report.txt"],
            "--manual-alpaca-rvol-capture-report",
        ),
        (
            ["--manual-alpaca-rvol-capture-confirm-live-data"],
            "--manual-alpaca-rvol-capture-confirm-live-data",
        ),
        (
            ["--manual-alpaca-rvol-capture-symbol", "RVOL"],
            "--manual-alpaca-rvol-capture-symbol",
        ),
        (
            ["--manual-alpaca-rvol-capture-historical-start", "2026-01-02T09:30:00Z"],
            "--manual-alpaca-rvol-capture-historical-start",
        ),
        (
            ["--manual-alpaca-rvol-capture-historical-end", "2026-01-21T10:00:00Z"],
            "--manual-alpaca-rvol-capture-historical-end",
        ),
        (
            ["--manual-alpaca-rvol-capture-historical-max-pages", "5"],
            "--manual-alpaca-rvol-capture-historical-max-pages",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-start", "2026-01-31T09:30:00Z"],
            "--manual-alpaca-rvol-capture-current-start",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-end", "2026-01-31T09:35:00Z"],
            "--manual-alpaca-rvol-capture-current-end",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-max-pages", "5"],
            "--manual-alpaca-rvol-capture-current-max-pages",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-session-id", "CURRENT-001"],
            "--manual-alpaca-rvol-capture-current-session-id",
        ),
        (
            ["--manual-alpaca-rvol-capture-bucket", "09:35"],
            "--manual-alpaca-rvol-capture-bucket",
        ),
        (
            ["--manual-alpaca-rvol-capture-cutoff", "2026-01-31T09:35:00Z"],
            "--manual-alpaca-rvol-capture-cutoff",
        ),
        (
            ["--manual-alpaca-rvol-capture-minimum-historical-sessions", "20"],
            "--manual-alpaca-rvol-capture-minimum-historical-sessions",
        ),
        (
            ["--manual-alpaca-rvol-capture-timeframe", "5Min"],
            "--manual-alpaca-rvol-capture-timeframe",
        ),
        (
            ["--manual-alpaca-rvol-capture-page-limit", "500"],
            "--manual-alpaca-rvol-capture-page-limit",
        ),
        (
            ["--manual-alpaca-rvol-capture-sort", "desc"],
            "--manual-alpaca-rvol-capture-sort",
        ),
    ],
)
def test_local_rvol_artifact_audit_rejects_all_documented_conflicts(
    monkeypatch,
    capsys,
    extra,
    expected,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("artifact audit conflict should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_audit",
        lambda _command: pytest.fail("artifact audit helper should not run"),
    )

    exit_code = main(_local_rvol_artifact_audit_argv(*extra))
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local RVOL Artifact Preflight" in output
    assert "Result: COMMAND_ERROR" in output
    assert expected in output


def test_session_seed_rejects_artifact_audit_with_phase_18b_ownership(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("seed/audit conflict should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_session_seed",
        lambda _command: pytest.fail("seed helper should not run"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_audit",
        lambda _command: pytest.fail("artifact audit helper should not run"),
    )

    exit_code = main(
        [
            "--local-rvol-session-seed",
            "plan.json",
            "metadata.json",
            "--local-rvol-artifact-preflight",
            "manifest.json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local RVOL Session Seed" in output
    assert "--local-rvol-artifact-preflight" in output


def test_local_rvol_artifact_manifest_writer_success_runs_before_config(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    result = object()
    calls = []
    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manifest writer should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("manifest writer should not create providers"),
    )
    monkeypatch.setattr(
        runner,
        "_run_scan",
        lambda **_kwargs: pytest.fail("manifest writer should not scan"),
    )
    monkeypatch.setattr(
        runner,
        "evaluate_live_readiness",
        lambda *_args, **_kwargs: pytest.fail("manifest writer should not run readiness"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_manifest_writer",
        lambda command: calls.append(command) or result,
    )
    monkeypatch.setattr(
        runner,
        "render_local_rvol_artifact_manifest_writer_success_report",
        lambda command, value: "manifest writer report",
    )

    exit_code = main(
        [
            "--local-rvol-artifact-manifest-write",
            "manifest.json",
            "--local-rvol-artifact",
            "AAPL",
            "meta.json",
            "bundle.json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output == "manifest writer report\n"
    assert calls[0].output_path == Path("manifest.json")
    assert calls[0].artifact_declarations == (("AAPL", "meta.json", "bundle.json"),)


def test_local_rvol_artifact_manifest_writer_only_artifact_dependency_error(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manifest writer dependency error should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_manifest_writer",
        lambda _command: pytest.fail("manifest writer helper should not run"),
    )

    exit_code = main(["--local-rvol-artifact", "AAPL", "meta.json", "bundle.json"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local RVOL Artifact Manifest Writer" in output
    assert "Result: COMMAND_ERROR" in output
    assert (
        "--local-rvol-artifact requires --local-rvol-artifact-manifest-write"
        in output
    )


def test_local_rvol_artifact_manifest_writer_no_artifacts_error(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    output_path = tmp_path / "manifest.json"
    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manifest writer command error should not load config"),
    )

    exit_code = main(["--local-rvol-artifact-manifest-write", str(output_path)])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "MISSING_ARTIFACTS" in output
    assert not output_path.exists()


@pytest.mark.parametrize(
    ("argv_tail", "expected"),
    [
        (
            ["--local-rvol-artifact", "AAPL", "same.json", "same.json"],
            "SAME_ARTIFACT_PATH:AAPL",
        ),
        (
            [
                "--local-rvol-artifact",
                "AAPL",
                "a-meta.json",
                "a-bundle.json",
                "--local-rvol-artifact",
                "aapl",
                "b-meta.json",
                "b-bundle.json",
            ],
            "DUPLICATE_SYMBOL:AAPL",
        ),
        (
            ["--local-rvol-artifact", "AAPL", "manifest.json", "bundle.json"],
            "OUTPUT_PATH_CONFLICT:AAPL",
        ),
    ],
)
def test_local_rvol_artifact_manifest_writer_validation_errors_write_nothing(
    monkeypatch,
    capsys,
    tmp_path,
    argv_tail,
    expected,
) -> None:
    import market_sentry.main as runner

    output_path = tmp_path / "manifest.json"
    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manifest writer validation error should not load config"),
    )
    tail = [
        str(output_path) if item == "manifest.json" else item
        for item in argv_tail
    ]

    exit_code = main(
        [
            "--local-rvol-artifact-manifest-write",
            str(output_path),
            *tail,
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert expected in output
    assert not output_path.exists()


def test_local_rvol_artifact_manifest_writer_os_error_is_operational(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manifest writer OS error should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_manifest_writer",
        lambda _command: (_ for _ in ()).throw(OSError("disk unavailable")),
    )

    exit_code = main(_local_rvol_artifact_manifest_writer_argv())
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Result: ERROR" in output
    assert "Error Type: OSError" in output
    assert "disk unavailable" in output


def test_local_rvol_artifact_manifest_writer_conflicts_preserve_raw_order(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manifest writer conflict should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_manifest_writer",
        lambda _command: pytest.fail("manifest writer helper should not run"),
    )

    exit_code = main(
        [
            "--no-speak",
            "--local-rvol-artifact-manifest-write",
            "manifest.json",
            "--local-rvol-artifact",
            "AAPL",
            "meta.json",
            "bundle.json",
            "--loop",
            "--speak",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local RVOL Artifact Manifest Writer" in output
    assert (
        "Error: --local-rvol-artifact-manifest-write cannot be combined with: "
        "--no-speak, --loop, --speak"
    ) in output


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        (["--loop"], "--loop"),
        (["--interval", "10"], "--interval"),
        (["--interval=10"], "--interval"),
        (["--live-readiness"], "--live-readiness"),
        (["--relative-volume-configured"], "--relative-volume-configured"),
        (["--speak"], "--speak"),
        (["--no-speak"], "--no-speak"),
        (["--local-json-preflight", "metadata.json"], "--local-json-preflight"),
        (["--local-json-preflight-report", "report.txt"], "--local-json-preflight-report"),
        (
            ["--local-json-bundle-preflight", "metadata.json", "bundle.json"],
            "--local-json-bundle-preflight",
        ),
        (
            ["--local-json-bundle-preflight-report", "bundle-report.txt"],
            "--local-json-bundle-preflight-report",
        ),
        (
            ["--manual-alpaca-rvol-capture", "seed.json", "meta.json", "bundle.json"],
            "--manual-alpaca-rvol-capture",
        ),
        (
            ["--manual-alpaca-rvol-capture-report", "report.txt"],
            "--manual-alpaca-rvol-capture-report",
        ),
        (
            ["--manual-alpaca-rvol-capture-confirm-live-data"],
            "--manual-alpaca-rvol-capture-confirm-live-data",
        ),
        (
            ["--manual-alpaca-rvol-capture-symbol", "RVOL"],
            "--manual-alpaca-rvol-capture-symbol",
        ),
        (
            ["--manual-alpaca-rvol-capture-historical-start", "2026-01-02T09:30:00Z"],
            "--manual-alpaca-rvol-capture-historical-start",
        ),
        (
            ["--manual-alpaca-rvol-capture-historical-end", "2026-01-21T10:00:00Z"],
            "--manual-alpaca-rvol-capture-historical-end",
        ),
        (
            ["--manual-alpaca-rvol-capture-historical-max-pages", "5"],
            "--manual-alpaca-rvol-capture-historical-max-pages",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-start", "2026-01-31T09:30:00Z"],
            "--manual-alpaca-rvol-capture-current-start",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-end", "2026-01-31T09:35:00Z"],
            "--manual-alpaca-rvol-capture-current-end",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-max-pages", "5"],
            "--manual-alpaca-rvol-capture-current-max-pages",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-session-id", "CURRENT-001"],
            "--manual-alpaca-rvol-capture-current-session-id",
        ),
        (
            ["--manual-alpaca-rvol-capture-bucket", "09:35"],
            "--manual-alpaca-rvol-capture-bucket",
        ),
        (
            ["--manual-alpaca-rvol-capture-cutoff", "2026-01-31T09:35:00Z"],
            "--manual-alpaca-rvol-capture-cutoff",
        ),
        (
            ["--manual-alpaca-rvol-capture-minimum-historical-sessions", "20"],
            "--manual-alpaca-rvol-capture-minimum-historical-sessions",
        ),
        (
            ["--manual-alpaca-rvol-capture-timeframe", "5Min"],
            "--manual-alpaca-rvol-capture-timeframe",
        ),
        (
            ["--manual-alpaca-rvol-capture-page-limit", "500"],
            "--manual-alpaca-rvol-capture-page-limit",
        ),
        (
            ["--manual-alpaca-rvol-capture-sort", "desc"],
            "--manual-alpaca-rvol-capture-sort",
        ),
    ],
)
def test_local_rvol_artifact_manifest_writer_rejects_all_documented_conflicts(
    monkeypatch,
    capsys,
    extra,
    expected,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manifest writer conflict should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_manifest_writer",
        lambda _command: pytest.fail("manifest writer helper should not run"),
    )

    exit_code = main(_local_rvol_artifact_manifest_writer_argv(*extra))
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local RVOL Artifact Manifest Writer" in output
    assert "Result: COMMAND_ERROR" in output
    assert expected in output


def test_session_seed_owns_seed_and_manifest_writer_conflict(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("seed/writer conflict should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_session_seed",
        lambda _command: pytest.fail("seed helper should not run"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_manifest_writer",
        lambda _command: pytest.fail("manifest writer helper should not run"),
    )

    exit_code = main(
        [
            "--local-rvol-session-seed",
            "plan.json",
            "metadata.json",
            "--local-rvol-artifact-manifest-write",
            "manifest.json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local RVOL Session Seed" in output
    assert "--local-rvol-artifact-manifest-write" in output


def test_artifact_audit_owns_audit_and_manifest_writer_conflict(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("audit/writer conflict should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_audit",
        lambda _command: pytest.fail("audit helper should not run"),
    )
    monkeypatch.setattr(
        runner,
        "run_local_rvol_artifact_manifest_writer",
        lambda _command: pytest.fail("manifest writer helper should not run"),
    )

    exit_code = main(
        [
            "--local-rvol-artifact-preflight",
            "audit-manifest.json",
            "--local-rvol-artifact-manifest-write",
            "manifest.json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local RVOL Artifact Preflight" in output
    assert "--local-rvol-artifact-manifest-write" in output


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        (["--loop"], "--loop"),
        (["--interval", "10"], "--interval"),
        (["--interval=10"], "--interval"),
        (["--live-readiness"], "--live-readiness"),
        (["--relative-volume-configured"], "--relative-volume-configured"),
        (["--speak"], "--speak"),
        (["--no-speak"], "--no-speak"),
        (["--local-json-preflight", "metadata.json"], "--local-json-preflight"),
        (["--local-json-preflight-report", "report.txt"], "--local-json-preflight-report"),
        (
            ["--local-json-bundle-preflight", "metadata.json", "bundle.json"],
            "--local-json-bundle-preflight",
        ),
        (
            ["--local-json-bundle-preflight-report", "bundle-report.txt"],
            "--local-json-bundle-preflight-report",
        ),
        (
            ["--manual-alpaca-rvol-capture", "seed.json", "meta.json", "bundle.json"],
            "--manual-alpaca-rvol-capture",
        ),
        (
            ["--manual-alpaca-rvol-capture-report", "report.txt"],
            "--manual-alpaca-rvol-capture-report",
        ),
        (
            ["--manual-alpaca-rvol-capture-confirm-live-data"],
            "--manual-alpaca-rvol-capture-confirm-live-data",
        ),
        (
            ["--manual-alpaca-rvol-capture-symbol", "RVOL"],
            "--manual-alpaca-rvol-capture-symbol",
        ),
        (
            ["--manual-alpaca-rvol-capture-historical-start", "2026-01-02T09:30:00Z"],
            "--manual-alpaca-rvol-capture-historical-start",
        ),
        (
            ["--manual-alpaca-rvol-capture-historical-end", "2026-01-21T10:00:00Z"],
            "--manual-alpaca-rvol-capture-historical-end",
        ),
        (
            ["--manual-alpaca-rvol-capture-historical-max-pages", "5"],
            "--manual-alpaca-rvol-capture-historical-max-pages",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-start", "2026-01-31T09:30:00Z"],
            "--manual-alpaca-rvol-capture-current-start",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-end", "2026-01-31T09:35:00Z"],
            "--manual-alpaca-rvol-capture-current-end",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-max-pages", "5"],
            "--manual-alpaca-rvol-capture-current-max-pages",
        ),
        (
            ["--manual-alpaca-rvol-capture-current-session-id", "CURRENT-001"],
            "--manual-alpaca-rvol-capture-current-session-id",
        ),
        (
            ["--manual-alpaca-rvol-capture-bucket", "09:35"],
            "--manual-alpaca-rvol-capture-bucket",
        ),
        (
            ["--manual-alpaca-rvol-capture-cutoff", "2026-01-31T09:35:00Z"],
            "--manual-alpaca-rvol-capture-cutoff",
        ),
        (
            ["--manual-alpaca-rvol-capture-minimum-historical-sessions", "20"],
            "--manual-alpaca-rvol-capture-minimum-historical-sessions",
        ),
        (
            ["--manual-alpaca-rvol-capture-timeframe", "5Min"],
            "--manual-alpaca-rvol-capture-timeframe",
        ),
        (
            ["--manual-alpaca-rvol-capture-page-limit", "500"],
            "--manual-alpaca-rvol-capture-page-limit",
        ),
        (
            ["--manual-alpaca-rvol-capture-sort", "desc"],
            "--manual-alpaca-rvol-capture-sort",
        ),
    ],
)
def test_local_rvol_session_seed_rejects_all_documented_conflicts(
    monkeypatch,
    capsys,
    extra,
    expected,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("session seed conflict should not load config"),
    )

    exit_code = main(_local_rvol_session_seed_argv(*extra))
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local RVOL Session Seed" in output
    assert "Result: COMMAND_ERROR" in output
    assert expected in output


def test_manual_capture_report_dependency_error_avoids_config_and_helper(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manual dependency error should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_manual_explicit_alpaca_rvol_capture_preflight",
        lambda *_args: pytest.fail("manual helper should not run"),
    )

    exit_code = main(["--manual-alpaca-rvol-capture-report", "capture-report.txt"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Manual Alpaca RVOL Capture Preflight" in output
    assert "Report Path: capture-report.txt" in output
    assert (
        "Error: --manual-alpaca-rvol-capture-report requires "
        "--manual-alpaca-rvol-capture"
    ) in output


def test_manual_capture_option_dependency_error_avoids_config_and_helper(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manual option dependency error should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_manual_explicit_alpaca_rvol_capture_preflight",
        lambda *_args: pytest.fail("manual helper should not run"),
    )

    exit_code = main(["--manual-alpaca-rvol-capture-symbol", "RVOL"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "manual Alpaca capture options require --manual-alpaca-rvol-capture" in output


def test_manual_capture_mode_exclusivity_avoids_config_and_helper(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manual exclusivity error should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_manual_explicit_alpaca_rvol_capture_preflight",
        lambda *_args: pytest.fail("manual helper should not run"),
    )

    exit_code = main(_manual_capture_argv("--local-json-preflight", "local.json"))
    output = capsys.readouterr().out

    assert exit_code == 2
    assert (
        "Error: --manual-alpaca-rvol-capture cannot be combined with "
        "local JSON preflight modes"
    ) in output


def test_manual_capture_conflicts_preserve_raw_order_and_voice_sanitization(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("manual conflict should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_manual_explicit_alpaca_rvol_capture_preflight",
        lambda *_args: pytest.fail("manual helper should not run"),
    )

    exit_code = main(
        [
            "--no-speak",
            *_manual_capture_argv("--loop", "--interval", "10", "--speak"),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Result: COMMAND_ERROR" in output
    assert (
        "Error: --manual-alpaca-rvol-capture cannot be combined with: "
        "--no-speak, --loop, --interval, --speak"
    ) in output


def test_manual_capture_missing_confirmation_avoids_config_and_helper(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "load_config",
        lambda: pytest.fail("missing confirmation should not load config"),
    )
    monkeypatch.setattr(
        runner,
        "run_manual_explicit_alpaca_rvol_capture_preflight",
        lambda *_args: pytest.fail("manual helper should not run"),
    )
    argv = [
        item
        for item in _manual_capture_argv()
        if item != "--manual-alpaca-rvol-capture-confirm-live-data"
    ]

    exit_code = main(argv)
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "LIVE_DATA_CONFIRMATION_REQUIRED" in output


def test_manual_capture_env_gate_error_returns_two_after_config_without_runtime(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    calls = []
    monkeypatch.setattr(runner, "load_config", lambda: calls.append("config") or AppConfig())
    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("manual path should not create providers"),
    )

    exit_code = main(_manual_capture_argv())
    output = capsys.readouterr().out

    assert exit_code == 2
    assert calls == ["config"]
    assert "ENV_LIVE_DATA_NOT_ALLOWED" in output
    assert "Mock Scanner Report" not in output


def test_manual_capture_success_failure_stopped_and_operational_reports(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    config = AppConfig(
        allow_live_data=True,
        alpaca_api_key="key",
        alpaca_api_secret="secret",
    )
    monkeypatch.setattr(runner, "load_config", lambda: config)

    success = SimpleNamespace(
        preflight_result=object(),
        report="phase 17d success report",
        status="PREFLIGHT_SUCCEEDED",
    )
    monkeypatch.setattr(
        runner,
        "run_manual_explicit_alpaca_rvol_capture_preflight",
        lambda command, loaded_config: success,
    )
    monkeypatch.setattr(
        runner,
        "is_manual_explicit_alpaca_rvol_capture_success",
        lambda result: True,
    )

    exit_code = main(_manual_capture_argv())
    output = capsys.readouterr().out
    assert exit_code == 0
    assert output == "phase 17d success report\n"

    failed = SimpleNamespace(
        preflight_result=object(),
        report="phase 17d failure report",
        status="PREFLIGHT_FAILED",
    )
    monkeypatch.setattr(
        runner,
        "run_manual_explicit_alpaca_rvol_capture_preflight",
        lambda command, loaded_config: failed,
    )
    monkeypatch.setattr(
        runner,
        "is_manual_explicit_alpaca_rvol_capture_success",
        lambda result: False,
    )
    exit_code = main(_manual_capture_argv())
    output = capsys.readouterr().out
    assert exit_code == 1
    assert output == "phase 17d failure report\n"

    stopped = SimpleNamespace(preflight_result=None, report=None)
    monkeypatch.setattr(
        runner,
        "run_manual_explicit_alpaca_rvol_capture_preflight",
        lambda command, loaded_config: stopped,
    )
    monkeypatch.setattr(
        runner,
        "render_manual_explicit_alpaca_rvol_capture_stopped_report",
        lambda result, command: "stopped report",
    )
    exit_code = main(_manual_capture_argv())
    output = capsys.readouterr().out
    assert exit_code == 1
    assert output == "stopped report\n"

    monkeypatch.setattr(
        runner,
        "run_manual_explicit_alpaca_rvol_capture_preflight",
        lambda command, loaded_config: (_ for _ in ()).throw(
            FileNotFoundError("missing seed")
        ),
    )
    exit_code = main(_manual_capture_argv())
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Result: ERROR" in output
    assert "Error Type: FileNotFoundError" in output


def _successful_preflight_result(tmp_path):
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    return run_local_json_metadata_preflight_scenario(
        scenario,
        tmp_path / "valid-helper.json",
    ).result


def _partial_preflight_result(tmp_path):
    scenario = get_local_json_metadata_preflight_scenario(
        "partial_manifest_json_complete_multi_page"
    )
    return run_local_json_metadata_preflight_scenario(
        scenario,
        tmp_path / "partial-helper.json",
    ).result


def _bundle_dt_tag(day: int, minute: int = 35) -> dict[str, str]:
    return {"$datetime": f"2026-01-{day:02d}T09:{minute:02d}:00Z"}


def _bundle_raw_bar(day: int, minute: int, volume: int) -> dict[str, object]:
    return {
        "t": f"2026-01-{day:02d}T09:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "h": 1.0,
        "l": 1.0,
        "c": 1.0,
    }


def _bundle_query(**overrides) -> dict[str, object]:
    value = {
        "timeframe": "1Min",
        "start": "2026-01-02T09:30:00Z",
        "end": "2026-01-21T10:00:00Z",
        "limit": 1000,
        "page_token": None,
        "sort": "asc",
    }
    value.update(overrides)
    return value


def _bundle_payload() -> dict[str, object]:
    first_page_bars = [_bundle_raw_bar(2, 31, 25)]
    second_page_bars = [_bundle_raw_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page_bars.append(_bundle_raw_bar(day, 35, 100))
    for day in range(12, 22):
        second_page_bars.append(_bundle_raw_bar(day, 35, 100))
    return {
        "schema_version": 1,
        "collection": {
            "request": {
                "symbols": ["RVOL"],
                "initial_query": _bundle_query(),
                "max_pages": 5,
            },
            "collected_pages": [
                {
                    "index": 0,
                    "query": _bundle_query(page_token="p0"),
                    "page": {
                        "requested_symbols": ["RVOL"],
                        "bars_by_symbol": {"RVOL": first_page_bars},
                        "next_page_token": None,
                    },
                },
                {
                    "index": 1,
                    "query": _bundle_query(page_token="p1"),
                    "page": {
                        "requested_symbols": ["RVOL"],
                        "bars_by_symbol": {"RVOL": second_page_bars},
                        "next_page_token": None,
                    },
                },
            ],
            "status": "COMPLETE",
            "page_collection_complete": True,
            "next_page_token": None,
            "reason": None,
        },
        "manifest_request": {
            "symbol": "RVOL",
            "bucket": "09:35",
            "current_session_id": "CURRENT-001",
        },
        "current_series": {
            "symbol": "RVOL",
            "session_id": "CURRENT-001",
            "bucket": "09:35",
            "cutoff_timestamp": _bundle_dt_tag(31),
            "bars": [{"timestamp": _bundle_dt_tag(31), "volume": 200}],
        },
        "harness_request": {
            "symbol": "RVOL",
            "bucket": "09:35",
            "current_session_id": "CURRENT-001",
            "page_collection_complete": True,
            "minimum_historical_sessions": 20,
        },
    }


def _write_bundle(path: Path, payload: dict[str, object] | None = None) -> None:
    path.write_text(json.dumps(payload or _bundle_payload()), encoding="utf-8")


def test_local_json_preflight_success_returns_zero_without_runtime_work(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    result = _successful_preflight_result(tmp_path)
    calls = []
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda path: calls.append(path) or result,
    )

    exit_code = main(["--local-json-preflight", "metadata.json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == [Path("metadata.json")]
    assert "Market Sentry Local JSON Preflight" in output
    assert "Profile: valid_json_complete_multi_page" in output
    assert "Metadata Load: LOADED" in output
    assert "Relative Volume: 2.0x" in output


def test_local_json_preflight_non_ok_returns_one_with_nested_diagnostics(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    result = _partial_preflight_result(tmp_path)
    monkeypatch.setattr(runner, "run_manual_local_json_preflight", lambda _path: result)

    exit_code = main(["--local-json-preflight", "partial.json"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Coordinator: MANIFEST_PARTIAL" in output
    assert "Manifest: PARTIAL" in output
    assert "Relative Volume: 2.0x" in output


def test_local_json_preflight_file_not_found_renders_error_without_runtime_work(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda _path: (_ for _ in ()).throw(FileNotFoundError()),
    )

    exit_code = main(["--local-json-preflight", "missing.json"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Result: ERROR" in output
    assert "Error Type: FileNotFoundError" in output


def test_local_json_preflight_source_error_renders_class_and_message(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda _path: (_ for _ in ()).throw(
            JsonHistoricalSessionMetadataFileSourceError(
                "UNSUPPORTED_SCHEMA_VERSION"
            )
        ),
    )

    exit_code = main(["--local-json-preflight", "bad.json"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "JsonHistoricalSessionMetadataFileSourceError" in output
    assert "UNSUPPORTED_SCHEMA_VERSION" in output


def test_local_json_preflight_invalid_combination_preserves_conflict_order(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda _path: pytest.fail("helper should not run for command errors"),
    )

    exit_code = main(
        [
            "--loop",
            "--local-json-preflight",
            "metadata.json",
            "--interval",
            "10",
            "--speak",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Result: COMMAND_ERROR" in output
    assert (
        "Error: --local-json-preflight cannot be combined with: "
        "--loop, --interval, --speak"
    ) in output


def test_local_json_preflight_explicit_no_speak_conflicts(monkeypatch, capsys) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda _path: pytest.fail("helper should not run for command errors"),
    )

    exit_code = main(["--local-json-preflight", "metadata.json", "--no-speak"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "--no-speak" in output


def test_local_json_preflight_both_voice_flags_return_command_error_in_raw_order(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda _path: pytest.fail("helper should not run for command errors"),
    )

    exit_code = main(
        [
            "--no-speak",
            "--local-json-preflight",
            "metadata.json",
            "--loop",
            "--speak",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.err == ""
    assert "Result: COMMAND_ERROR" in captured.out
    assert (
        "Error: --local-json-preflight cannot be combined with: "
        "--no-speak, --loop, --speak"
    ) in captured.out


def test_local_json_preflight_default_interval_value_is_allowed(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    result = _successful_preflight_result(tmp_path)
    monkeypatch.setattr(runner, "run_manual_local_json_preflight", lambda _path: result)

    exit_code = main(
        [
            "--local-json-preflight",
            "metadata.json",
            "--interval",
            str(DEFAULT_INTERVAL_SECONDS),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "COMMAND_ERROR" not in output
    assert "Relative Volume: 2.0x" in output


def test_local_json_preflight_interval_equals_syntax_conflicts_when_non_default(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda _path: pytest.fail("helper should not run for command errors"),
    )

    exit_code = main(["--local-json-preflight", "metadata.json", "--interval=10"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "--interval" in output


def test_local_json_preflight_report_without_input_returns_command_error(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    report_path = tmp_path / "report.txt"
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda _path: pytest.fail("preflight should not run"),
    )
    monkeypatch.setattr(
        runner,
        "write_manual_local_json_preflight_report",
        lambda *_args: pytest.fail("export should not run"),
    )

    exit_code = main(["--local-json-preflight-report", str(report_path)])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert output == (
        "Market Sentry Local JSON Preflight\n"
        "Path: N/A\n"
        f"Report Path: {report_path}\n"
        "Result: COMMAND_ERROR\n"
        "Error: --local-json-preflight-report requires --local-json-preflight\n"
    )
    assert not report_path.exists()


def test_local_json_preflight_same_input_output_path_returns_command_error(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    path = tmp_path / "metadata.json"
    path.write_text("original", encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda _path: pytest.fail("preflight should not run"),
    )
    monkeypatch.setattr(
        runner,
        "write_manual_local_json_preflight_report",
        lambda *_args: pytest.fail("export should not run"),
    )

    exit_code = main(
        [
            "--local-json-preflight",
            str(path),
            "--local-json-preflight-report",
            str(path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert output == (
        "Market Sentry Local JSON Preflight\n"
        f"Path: {path}\n"
        f"Report Path: {path}\n"
        "Result: COMMAND_ERROR\n"
        "Error: --local-json-preflight-report must differ from --local-json-preflight\n"
    )
    assert path.read_text(encoding="utf-8") == "original"


def test_local_json_preflight_conflict_with_report_writes_nothing(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    report_path = tmp_path / "report.txt"
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda _path: pytest.fail("preflight should not run"),
    )
    monkeypatch.setattr(
        runner,
        "write_manual_local_json_preflight_report",
        lambda *_args: pytest.fail("export should not run"),
    )

    exit_code = main(
        [
            "--no-speak",
            "--local-json-preflight",
            "metadata.json",
            "--local-json-preflight-report",
            str(report_path),
            "--loop",
            "--speak",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert (
        "Error: --local-json-preflight cannot be combined with: "
        "--no-speak, --loop, --speak"
    ) in output
    assert not report_path.exists()


def test_local_json_preflight_full_success_exports_exact_stdout_report(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    result = _successful_preflight_result(tmp_path)
    report_path = tmp_path / "report.txt"
    writes = []
    monkeypatch.setattr(runner, "run_manual_local_json_preflight", lambda _path: result)
    monkeypatch.setattr(
        runner,
        "write_manual_local_json_preflight_report",
        lambda path, report: writes.append((path, report)),
    )

    exit_code = main(
        [
            "--local-json-preflight",
            "metadata.json",
            "--local-json-preflight-report",
            str(report_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert len(writes) == 1
    assert writes[0][0] == report_path
    assert output == writes[0][1] + "\n"
    assert "Relative Volume: 2.0x" in output


def test_local_json_preflight_non_ok_exports_exact_nested_report(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    result = _partial_preflight_result(tmp_path)
    report_path = tmp_path / "partial-report.txt"
    writes = []
    monkeypatch.setattr(runner, "run_manual_local_json_preflight", lambda _path: result)
    monkeypatch.setattr(
        runner,
        "write_manual_local_json_preflight_report",
        lambda path, report: writes.append((path, report)),
    )

    exit_code = main(
        [
            "--local-json-preflight",
            "partial.json",
            "--local-json-preflight-report",
            str(report_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert len(writes) == 1
    assert writes[0][0] == report_path
    assert output == writes[0][1] + "\n"
    assert "Coordinator: MANIFEST_PARTIAL" in output


def test_local_json_preflight_source_error_exports_exact_error_report(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    report_path = tmp_path / "error-report.txt"
    writes = []
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda _path: (_ for _ in ()).throw(FileNotFoundError()),
    )
    monkeypatch.setattr(
        runner,
        "write_manual_local_json_preflight_report",
        lambda path, report: writes.append((path, report)),
    )

    exit_code = main(
        [
            "--local-json-preflight",
            "missing.json",
            "--local-json-preflight-report",
            str(report_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert len(writes) == 1
    assert writes[0][0] == report_path
    assert output == writes[0][1] + "\n"
    assert "Result: ERROR" in output
    assert "FileNotFoundError" in output


def test_local_json_preflight_export_oserror_prints_only_export_error(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    result = _successful_preflight_result(tmp_path)
    report_path = tmp_path / "missing-parent" / "report.txt"
    monkeypatch.setattr(runner, "run_manual_local_json_preflight", lambda _path: result)
    monkeypatch.setattr(
        runner,
        "write_manual_local_json_preflight_report",
        lambda _path, _report: (_ for _ in ()).throw(
            OSError("disk unavailable")
        ),
    )

    exit_code = main(
        [
            "--local-json-preflight",
            "metadata.json",
            "--local-json-preflight-report",
            str(report_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Result: EXPORT_ERROR" in output
    assert "Error Type: OSError" in output
    assert "disk unavailable" in output
    assert "Metadata Load:" not in output
    assert "Relative Volume: 2.0x" not in output


def test_local_json_preflight_actual_valid_json_exits_zero_without_provider(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("local preflight should not create providers"),
    )
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    path = tmp_path / "valid.json"
    path.write_bytes(scenario.fixture_bytes)

    exit_code = main(["--local-json-preflight", str(path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Relative Volume: 2.0x" in output
    assert "Provider configuration error" not in output


def test_local_json_preflight_actual_unsupported_schema_exits_one(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("local preflight should not create providers"),
    )
    path = tmp_path / "bad-schema.json"
    path.write_text(json.dumps({"schema_version": 2, "records": []}), encoding="utf-8")

    exit_code = main(["--local-json-preflight", str(path)])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Result: ERROR" in output
    assert "JsonHistoricalSessionMetadataFileSourceError" in output
    assert "UNSUPPORTED_SCHEMA_VERSION" in output


def test_local_json_preflight_actual_missing_file_exits_one(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("local preflight should not create providers"),
    )
    path = tmp_path / "missing.json"

    exit_code = main(["--local-json-preflight", str(path)])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Result: ERROR" in output
    assert "FileNotFoundError" in output


def test_local_json_preflight_actual_valid_json_exports_exact_stdout(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("local preflight should not create providers"),
    )
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    input_path = tmp_path / "valid.json"
    output_path = tmp_path / "report.txt"
    input_path.write_bytes(scenario.fixture_bytes)

    exit_code = main(
        [
            "--local-json-preflight",
            str(input_path),
            "--local-json-preflight-report",
            str(output_path),
        ]
    )
    stdout = capsys.readouterr().out

    assert exit_code == 0
    assert "Relative Volume: 2.0x" in stdout
    assert output_path.read_text(encoding="utf-8") == stdout.removesuffix("\n")


def test_local_json_preflight_actual_unsupported_schema_exports_error_report(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("local preflight should not create providers"),
    )
    input_path = tmp_path / "bad-schema.json"
    output_path = tmp_path / "bad-schema-report.txt"
    input_path.write_text(
        json.dumps({"schema_version": 2, "records": []}),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--local-json-preflight",
            str(input_path),
            "--local-json-preflight-report",
            str(output_path),
        ]
    )
    stdout = capsys.readouterr().out

    assert exit_code == 1
    assert "Result: ERROR" in stdout
    assert "UNSUPPORTED_SCHEMA_VERSION" in stdout
    assert output_path.read_text(encoding="utf-8") == stdout.removesuffix("\n")


def test_local_json_preflight_actual_missing_input_exports_error_report(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("local preflight should not create providers"),
    )
    input_path = tmp_path / "missing.json"
    output_path = tmp_path / "missing-report.txt"

    exit_code = main(
        [
            "--local-json-preflight",
            str(input_path),
            "--local-json-preflight-report",
            str(output_path),
        ]
    )
    stdout = capsys.readouterr().out

    assert exit_code == 1
    assert "Result: ERROR" in stdout
    assert "FileNotFoundError" in stdout
    assert output_path.read_text(encoding="utf-8") == stdout.removesuffix("\n")


def test_local_json_preflight_actual_missing_output_parent_exports_error_only(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("local preflight should not create providers"),
    )
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    input_path = tmp_path / "valid.json"
    original_input = scenario.fixture_bytes
    output_path = tmp_path / "missing-parent" / "report.txt"
    input_path.write_bytes(original_input)

    exit_code = main(
        [
            "--local-json-preflight",
            str(input_path),
            "--local-json-preflight-report",
            str(output_path),
        ]
    )
    stdout = capsys.readouterr().out

    assert exit_code == 1
    assert "Result: EXPORT_ERROR" in stdout
    assert "Metadata Load:" not in stdout
    assert not output_path.exists()
    assert input_path.read_bytes() == original_input


def test_local_json_bundle_report_without_command_returns_dependency_error(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    report_path = tmp_path / "bundle-report.txt"
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: pytest.fail("bundle helper should not run"),
    )

    exit_code = main(["--local-json-bundle-preflight-report", str(report_path)])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert output == (
        "Market Sentry Local JSON Bundle Preflight\n"
        "Metadata Path: N/A\n"
        "Bundle Path: N/A\n"
        f"Report Path: {report_path}\n"
        "Result: COMMAND_ERROR\n"
        "Error: --local-json-bundle-preflight-report requires "
        "--local-json-bundle-preflight\n"
    )
    assert not report_path.exists()


def test_local_json_old_report_flag_with_bundle_command_uses_old_dependency_error(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    old_report = tmp_path / "old-report.txt"
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: pytest.fail("bundle helper should not run"),
    )

    exit_code = main(
        [
            "--local-json-bundle-preflight",
            "metadata.json",
            "bundle.json",
            "--local-json-preflight-report",
            str(old_report),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local JSON Preflight" in output
    assert "--local-json-preflight-report requires --local-json-preflight" in output
    assert not old_report.exists()


def test_local_json_bundle_report_flag_with_old_command_uses_bundle_dependency_error(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    bundle_report = tmp_path / "bundle-report.txt"
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda *_args: pytest.fail("old helper should not run"),
    )

    exit_code = main(
        [
            "--local-json-preflight",
            "metadata.json",
            "--local-json-bundle-preflight-report",
            str(bundle_report),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Local JSON Bundle Preflight" in output
    assert "--local-json-bundle-preflight-report requires" in output
    assert not bundle_report.exists()


def test_local_json_preflight_modes_cannot_be_combined(monkeypatch, capsys) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_preflight",
        lambda *_args: pytest.fail("old helper should not run"),
    )
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: pytest.fail("bundle helper should not run"),
    )

    exit_code = main(
        [
            "--local-json-preflight",
            "metadata.json",
            "--local-json-bundle-preflight",
            "metadata.json",
            "bundle.json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert output == (
        "Market Sentry Local JSON Preflight\n"
        "Path: N/A\n"
        "Result: COMMAND_ERROR\n"
        "Error: --local-json-preflight and --local-json-bundle-preflight "
        "cannot be combined\n"
    )


def test_local_json_bundle_conflicts_preserve_raw_order_with_voice_flags(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: pytest.fail("bundle helper should not run"),
    )

    exit_code = main(
        [
            "--no-speak",
            "--local-json-bundle-preflight",
            "metadata.json",
            "bundle.json",
            "--loop",
            "--speak",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.err == ""
    assert "Market Sentry Local JSON Bundle Preflight" in captured.out
    assert (
        "Error: --local-json-bundle-preflight cannot be combined with: "
        "--no-speak, --loop, --speak"
    ) in captured.out


def test_local_json_bundle_default_interval_allowed(monkeypatch, capsys) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    result = object()
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_bundle_preflight",
        lambda metadata, bundle: result,
    )
    monkeypatch.setattr(
        runner,
        "render_manual_local_json_bundle_preflight_report",
        lambda metadata, bundle, value: "bundle report",
    )
    monkeypatch.setattr(
        runner,
        "is_manual_local_json_bundle_preflight_success",
        lambda value: True,
    )

    exit_code = main(
        [
            "--local-json-bundle-preflight",
            "metadata.json",
            "bundle.json",
            "--interval",
            str(DEFAULT_INTERVAL_SECONDS),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output == "bundle report\n"


def test_local_json_bundle_non_default_interval_conflicts(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: pytest.fail("bundle helper should not run"),
    )

    exit_code = main(
        ["--local-json-bundle-preflight", "metadata.json", "bundle.json", "--interval=10"]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "--interval" in output


def test_local_json_bundle_report_cannot_equal_metadata_or_bundle_path(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: pytest.fail("bundle helper should not run"),
    )

    exit_code = main(
        [
            "--local-json-bundle-preflight",
            "metadata.json",
            "bundle.json",
            "--local-json-bundle-preflight-report",
            "metadata.json",
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 2
    assert "must differ from metadata path" in output

    exit_code = main(
        [
            "--local-json-bundle-preflight",
            "metadata.json",
            "bundle.json",
            "--local-json-bundle-preflight-report",
            "bundle.json",
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 2
    assert "must differ from bundle path" in output


def test_local_json_bundle_monkeypatched_success_and_export(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    result = object()
    report_path = tmp_path / "bundle-report.txt"
    writes = []
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_bundle_preflight",
        lambda metadata, bundle: result,
    )
    monkeypatch.setattr(
        runner,
        "render_manual_local_json_bundle_preflight_report",
        lambda metadata, bundle, value: "bundle report",
    )
    monkeypatch.setattr(
        runner,
        "is_manual_local_json_bundle_preflight_success",
        lambda value: True,
    )
    monkeypatch.setattr(
        runner,
        "write_manual_local_json_bundle_preflight_report",
        lambda path, report: writes.append((path, report)),
    )

    exit_code = main(
        [
            "--local-json-bundle-preflight",
            "metadata.json",
            "bundle.json",
            "--local-json-bundle-preflight-report",
            str(report_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output == "bundle report\n"
    assert writes == [(report_path, "bundle report")]


def test_local_json_bundle_expected_error_and_export_error_paths(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    _fail_if_runtime_work_runs(monkeypatch)
    report_path = tmp_path / "missing-parent" / "bundle-report.txt"
    monkeypatch.setattr(
        runner,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: (_ for _ in ()).throw(
            JsonHistoricalRvolBundleError("UNSUPPORTED_SCHEMA_VERSION")
        ),
    )

    exit_code = main(["--local-json-bundle-preflight", "metadata.json", "bundle.json"])
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Result: ERROR" in output
    assert "JsonHistoricalRvolBundleError" in output

    monkeypatch.setattr(
        runner,
        "write_manual_local_json_bundle_preflight_report",
        lambda *_args: (_ for _ in ()).throw(OSError("disk unavailable")),
    )
    exit_code = main(
        [
            "--local-json-bundle-preflight",
            "metadata.json",
            "bundle.json",
            "--local-json-bundle-preflight-report",
            str(report_path),
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Result: EXPORT_ERROR" in output
    assert "disk unavailable" in output
    assert "Result: ERROR" not in output


def test_local_json_bundle_actual_valid_command_and_export(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("bundle preflight should not create providers"),
    )
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    metadata_path = tmp_path / "metadata.json"
    bundle_path = tmp_path / "bundle.json"
    report_path = tmp_path / "bundle-report.txt"
    metadata_path.write_bytes(scenario.fixture_bytes)
    _write_bundle(bundle_path)

    exit_code = main(
        [
            "--local-json-bundle-preflight",
            str(metadata_path),
            str(bundle_path),
            "--local-json-bundle-preflight-report",
            str(report_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Market Sentry Local JSON Bundle Preflight" in output
    assert "Input Mode: EXPLICIT_LOCAL_BUNDLE" in output
    assert "Relative Volume: 2.0x" in output
    assert "Profile:" not in output
    assert report_path.read_text(encoding="utf-8") == output.removesuffix("\n")


def test_local_json_bundle_actual_invalid_inputs_and_downstream_failure(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("bundle preflight should not create providers"),
    )
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_bytes(scenario.fixture_bytes)

    bad_bundle_path = tmp_path / "bad-bundle.json"
    bad_bundle_path.write_text(
        json.dumps({"schema_version": 2}),
        encoding="utf-8",
    )
    exit_code = main(
        ["--local-json-bundle-preflight", str(metadata_path), str(bad_bundle_path)]
    )
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "JsonHistoricalRvolBundleError" in output
    assert "UNSUPPORTED_SCHEMA_VERSION" in output

    bad_metadata_path = tmp_path / "bad-metadata.json"
    bundle_path = tmp_path / "bundle.json"
    bad_metadata_path.write_text(
        json.dumps({"schema_version": 2, "records": []}),
        encoding="utf-8",
    )
    _write_bundle(bundle_path)
    exit_code = main(
        ["--local-json-bundle-preflight", str(bad_metadata_path), str(bundle_path)]
    )
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "JsonHistoricalSessionMetadataFileSourceError" in output
    assert "UNSUPPORTED_SCHEMA_VERSION" in output

    invalid_volume_payload = _bundle_payload()
    invalid_volume_payload["current_series"]["bars"][0]["volume"] = False
    _write_bundle(bundle_path, invalid_volume_payload)
    exit_code = main(
        ["--local-json-bundle-preflight", str(metadata_path), str(bundle_path)]
    )
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Final: CURRENT_CUMULATIVE_VOLUME_FAILED" in output
    assert "Final Reason: CURRENT_CUMULATIVE_VOLUME_FAILED:INVALID_INTRADAY_VOLUME" in output


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
    assert "MISSING_RVOL_ARTIFACT_MANIFEST_PATH" in output
    assert "Market Sentry" not in output
    assert "Mock Scanner Report" not in output
    assert "Fixture Scanner Report" not in output
    assert "Composed Fixture Scanner Report" not in output
    assert "Qualified Results" not in output
    assert "Traceback" not in output
    assert speaker.calls == 0


def test_runtime_live_composed_missing_manifest_file_fails_cleanly(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "live_composed")
    monkeypatch.setenv("MARKET_SENTRY_ALLOW_LIVE_DATA", "true")
    monkeypatch.setenv("MARKET_SENTRY_WATCHLIST", "AAPL")
    monkeypatch.setenv("ALPACA_API_KEY", "visible-key-should-not-print")
    monkeypatch.setenv("ALPACA_API_SECRET", "visible-secret-should-not-print")
    monkeypatch.setenv("FMP_API_KEY", "visible-fmp-should-not-print")
    monkeypatch.setenv("MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH", "missing.json")

    exit_code = main([])

    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Provider configuration error:" in output
    assert "missing.json" in output
    assert "visible-key-should-not-print" not in output
    assert "visible-secret-should-not-print" not in output
    assert "visible-fmp-should-not-print" not in output
    assert "Market Sentry" not in output
    assert "Qualified Results" not in output
    assert "Traceback" not in output


def test_runtime_live_composed_loop_rejected_before_factory(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "live_composed")
    monkeypatch.setattr(
        runner,
        "create_market_data_provider",
        lambda _config: pytest.fail("factory should not run for live loop"),
    )

    exit_code = main(["--loop", "--interval", "30"])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "Market Sentry Live Composed Scanner" in output
    assert "--loop is not available for live_composed in Phase 18A" in output
    assert "RVOL comes from explicit local artifacts" in output


def test_runtime_live_composed_one_shot_uses_live_report_label(
    monkeypatch,
    capsys,
) -> None:
    import market_sentry.main as runner

    provider = MockMarketDataProvider()
    calls = []
    monkeypatch.setenv("MARKET_SENTRY_PROVIDER", "live_composed")
    monkeypatch.setattr(runner, "create_market_data_provider", lambda _config: provider)

    def fake_run_scan(**kwargs):
        calls.append(kwargs)
        print(kwargs["report_label"])

    monkeypatch.setattr(runner, "_run_scan", fake_run_scan)

    exit_code = main([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls[0]["provider"] is provider
    assert calls[0]["speak"] is False
    assert "Live Composed One-Shot Scanner Report" in output
    assert "live Alpaca snapshots + live FMP float + explicit local RVOL artifacts" in output


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
