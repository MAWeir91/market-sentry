import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path

import pytest

from market_sentry.config import AppConfig
from market_sentry.data.http import FakeHttpTransport, HttpResponse
from market_sentry.data.explicit_alpaca_rvol_capture_preflight import (
    ExplicitAlpacaRvolCapturePreflightStatus,
)
from market_sentry.manual_explicit_alpaca_rvol_capture_preflight_cli import (
    ManualExplicitAlpacaRvolCaptureCommandError,
    ManualExplicitAlpacaRvolCaptureCommandRequest,
    is_manual_explicit_alpaca_rvol_capture_success,
    render_manual_explicit_alpaca_rvol_capture_command_error,
    render_manual_explicit_alpaca_rvol_capture_error,
    render_manual_explicit_alpaca_rvol_capture_stopped_report,
    run_manual_explicit_alpaca_rvol_capture_preflight,
    validate_manual_explicit_alpaca_rvol_capture_command,
)
from market_sentry import manual_explicit_alpaca_rvol_capture_preflight_cli as module


UTC = timezone.utc


def dt(day: int, hour: int = 9, minute: int = 35) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def raw_record(session_id: str, *, day: int, is_complete=True) -> dict[str, object]:
    return {
        "symbol": "RVOL",
        "session_id": session_id,
        "bucket": "09:35",
        "session_start_timestamp": {"$datetime": dt(day, 9, 30).isoformat().replace("+00:00", "Z")},
        "session_end_timestamp": {"$datetime": dt(day, 10, 0).isoformat().replace("+00:00", "Z")},
        "cutoff_timestamp": {"$datetime": dt(day, 9, 35).isoformat().replace("+00:00", "Z")},
        "is_complete": is_complete,
    }


def valid_records(count: int = 20) -> list[dict[str, object]]:
    return [
        raw_record(f"HIST-{index:02d}", day=index + 1)
        for index in range(1, count + 1)
    ]


def write_seed(path: Path, records=None) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": valid_records() if records is None else records,
            }
        ),
        encoding="utf-8",
    )


def raw_bar(day: int, minute: int, volume: int) -> dict[str, object]:
    return {
        "t": f"2026-01-{day:02d}T09:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "h": 1.0,
        "l": 1.0,
        "c": 1.0,
    }


def response(symbol: str, bars, *, next_page_token=None) -> HttpResponse:
    return HttpResponse(
        status_code=200,
        body=json.dumps(
            {
                "bars": {symbol: bars},
                "next_page_token": next_page_token,
            }
        ),
    )


def valid_historical_pages() -> list[HttpResponse]:
    first_page = [raw_bar(2, 31, 25), raw_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page.append(raw_bar(day, 35, 100))
    second_page = [raw_bar(day, 35, 100) for day in range(12, 22)]
    return [
        response("RVOL", first_page, next_page_token="hist-2"),
        response("RVOL", second_page),
    ]


def current_page(*, next_page_token=None) -> HttpResponse:
    return response("RVOL", [raw_bar(31, 35, 200)], next_page_token=next_page_token)


def command(tmp_path, **overrides) -> ManualExplicitAlpacaRvolCaptureCommandRequest:
    values = {
        "metadata_input_path": tmp_path / "seed.json",
        "metadata_output_path": tmp_path / "metadata.json",
        "bundle_output_path": tmp_path / "bundle.json",
        "report_output_path": tmp_path / "report.txt",
        "confirm_live_data": True,
        "symbol": "RVOL",
        "historical_start": "2026-01-02T09:30:00Z",
        "historical_end": "2026-01-21T10:00:00Z",
        "historical_max_pages": 5,
        "current_start": "2026-01-31T09:30:00Z",
        "current_end": "2026-01-31T09:35:00Z",
        "current_max_pages": 5,
        "current_session_id": "CURRENT-001",
        "bucket": "09:35",
        "cutoff": "2026-01-31T09:35:00Z",
        "minimum_historical_sessions": 20,
        "timeframe": "1Min",
        "page_limit": 1000,
        "sort": "asc",
    }
    values.update(overrides)
    return ManualExplicitAlpacaRvolCaptureCommandRequest(**values)


def live_config(**overrides) -> AppConfig:
    values = {
        "allow_live_data": True,
        "alpaca_api_key": "test-key",
        "alpaca_api_secret": "test-secret",
        "alpaca_data_feed": "iex",
    }
    values.update(overrides)
    return AppConfig(**values)


def test_command_model_is_frozen_and_retains_paths(tmp_path) -> None:
    request = command(tmp_path)

    assert request.metadata_input_path == tmp_path / "seed.json"
    assert request.metadata_output_path == tmp_path / "metadata.json"
    assert request.bundle_output_path == tmp_path / "bundle.json"
    assert request.report_output_path == tmp_path / "report.txt"
    with pytest.raises(FrozenInstanceError):
        request.symbol = "ALT"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"metadata_input_path": "seed.json"}, "metadata_input_path must be a pathlib.Path."),
        ({"metadata_output_path": "metadata.json"}, "metadata_output_path must be a pathlib.Path."),
        ({"bundle_output_path": "bundle.json"}, "bundle_output_path must be a pathlib.Path."),
        ({"report_output_path": "report.txt"}, "report_output_path must be a pathlib.Path or None."),
    ],
)
def test_path_type_errors_before_source_transport_or_capture(
    monkeypatch,
    tmp_path,
    overrides,
    message,
) -> None:
    monkeypatch.setattr(
        module,
        "JsonHistoricalSessionMetadataFileSource",
        lambda *_args: pytest.fail("source should not load"),
    )
    monkeypatch.setattr(
        module,
        "StdlibHttpTransport",
        lambda: pytest.fail("transport should not construct"),
    )
    monkeypatch.setattr(
        module,
        "capture_and_preflight_explicit_alpaca_rvol_bundle",
        lambda *_args: pytest.fail("Phase 17D should not run"),
    )

    with pytest.raises(TypeError) as exc_info:
        run_manual_explicit_alpaca_rvol_capture_preflight(
            command(tmp_path, **overrides),
            live_config(),
        )

    assert str(exc_info.value) == message


def test_missing_capture_arguments_use_stable_order(tmp_path) -> None:
    request = command(
        tmp_path,
        symbol="",
        historical_start=None,
        current_max_pages=None,
        cutoff="",
    )

    with pytest.raises(ManualExplicitAlpacaRvolCaptureCommandError) as exc_info:
        validate_manual_explicit_alpaca_rvol_capture_command(request)

    assert str(exc_info.value) == (
        "MISSING_CAPTURE_ARGUMENTS:"
        "--manual-alpaca-rvol-capture-symbol,"
        "--manual-alpaca-rvol-capture-historical-start,"
        "--manual-alpaca-rvol-capture-current-max-pages,"
        "--manual-alpaca-rvol-capture-cutoff"
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            lambda tmp_path: {
                "metadata_output_path": tmp_path / "seed.json",
            },
            "METADATA_INPUT_EQUALS_METADATA_OUTPUT",
        ),
        (
            lambda tmp_path: {
                "bundle_output_path": tmp_path / "seed.json",
            },
            "METADATA_INPUT_EQUALS_BUNDLE_OUTPUT",
        ),
        (
            lambda tmp_path: {
                "report_output_path": tmp_path / "seed.json",
            },
            "METADATA_INPUT_EQUALS_REPORT_OUTPUT",
        ),
    ],
)
def test_metadata_input_collision_precedence(tmp_path, overrides, message) -> None:
    request = command(tmp_path, **overrides(tmp_path))

    with pytest.raises(ManualExplicitAlpacaRvolCaptureCommandError) as exc_info:
        validate_manual_explicit_alpaca_rvol_capture_command(request)

    assert str(exc_info.value) == message


@pytest.mark.parametrize(
    ("request_overrides", "config_overrides", "message"),
    [
        ({"confirm_live_data": False}, {}, "LIVE_DATA_CONFIRMATION_REQUIRED"),
        ({}, {"allow_live_data": False}, "ENV_LIVE_DATA_NOT_ALLOWED"),
        ({}, {"alpaca_api_key": None}, "MISSING_ALPACA_API_KEY"),
        ({}, {"alpaca_api_secret": None}, "MISSING_ALPACA_API_SECRET"),
    ],
)
def test_gates_and_credentials_before_source_transport_or_capture(
    monkeypatch,
    tmp_path,
    request_overrides,
    config_overrides,
    message,
) -> None:
    monkeypatch.setattr(
        module,
        "JsonHistoricalSessionMetadataFileSource",
        lambda *_args: pytest.fail("source should not load"),
    )
    monkeypatch.setattr(
        module,
        "StdlibHttpTransport",
        lambda: pytest.fail("transport should not construct"),
    )
    monkeypatch.setattr(
        module,
        "capture_and_preflight_explicit_alpaca_rvol_bundle",
        lambda *_args: pytest.fail("Phase 17D should not run"),
    )

    with pytest.raises(ManualExplicitAlpacaRvolCaptureCommandError) as exc_info:
        run_manual_explicit_alpaca_rvol_capture_preflight(
            command(tmp_path, **request_overrides),
            live_config(**config_overrides),
        )

    assert str(exc_info.value) == message


def test_does_not_inspect_provider_watchlist_or_fmp_fields(tmp_path) -> None:
    request = command(tmp_path)
    write_seed(request.metadata_input_path)
    transport = FakeHttpTransport(valid_historical_pages() + [current_page()])
    config = live_config(
        provider="ignored",
        watchlist=(),
        fmp_api_key=None,
    )

    result = run_manual_explicit_alpaca_rvol_capture_preflight(
        request,
        config,
        transport=transport,
    )

    assert result.status == ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_SUCCEEDED
    assert "Relative Volume: 2.0x" in result.report


def test_invalid_cutoff_before_source_transport_or_capture(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        module,
        "JsonHistoricalSessionMetadataFileSource",
        lambda *_args: pytest.fail("source should not load"),
    )
    monkeypatch.setattr(
        module,
        "StdlibHttpTransport",
        lambda: pytest.fail("transport should not construct"),
    )

    with pytest.raises(ManualExplicitAlpacaRvolCaptureCommandError) as exc_info:
        run_manual_explicit_alpaca_rvol_capture_preflight(
            command(tmp_path, cutoff="not-a-date"),
            live_config(),
        )

    assert str(exc_info.value) == "INVALID_CUTOFF_TIMESTAMP"


def test_query_validation_errors_propagate_before_source(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        module,
        "JsonHistoricalSessionMetadataFileSource",
        lambda *_args: pytest.fail("source should not load"),
    )

    with pytest.raises(Exception) as exc_info:
        run_manual_explicit_alpaca_rvol_capture_preflight(
            command(tmp_path, page_limit=0),
            live_config(),
        )

    assert "limit must be between 1 and 10000" in str(exc_info.value)


def test_metadata_seed_load_happens_before_transport_creation(monkeypatch, tmp_path):
    calls = []
    request = command(tmp_path)
    records = [{"loaded": True}]

    class FakeSource:
        def __init__(self, path):
            calls.append(("source_constructed", path))

        def load_raw_manifest_records(self, manifest_request):
            calls.append(("source_loaded", manifest_request))
            return records

    class FakeTransport:
        def __init__(self):
            calls.append(("transport",))

    def fake_phase_17d(fetcher, phase_request):
        calls.append(("phase_17d", fetcher, phase_request))
        return "result"

    monkeypatch.setattr(module, "JsonHistoricalSessionMetadataFileSource", FakeSource)
    monkeypatch.setattr(module, "StdlibHttpTransport", FakeTransport)
    monkeypatch.setattr(
        module,
        "capture_and_preflight_explicit_alpaca_rvol_bundle",
        fake_phase_17d,
    )

    result = run_manual_explicit_alpaca_rvol_capture_preflight(request, live_config())

    assert result == "result"
    assert [call[0] for call in calls] == [
        "source_constructed",
        "source_loaded",
        "transport",
        "phase_17d",
    ]
    assert calls[0][1] is request.metadata_input_path
    manifest_request = calls[1][1]
    assert manifest_request.symbol == "RVOL"
    assert manifest_request.bucket == "09:35"
    assert manifest_request.current_session_id == "CURRENT-001"
    fetcher = calls[3][1]
    phase_request = calls[3][2]
    assert fetcher.settings.api_key == "test-key"
    assert fetcher.settings.api_secret == "test-secret"
    assert fetcher.settings.feed == "iex"
    assert isinstance(fetcher.transport, FakeTransport)
    assert phase_request.metadata_records is records
    assert phase_request.metadata_output_path is request.metadata_output_path
    assert phase_request.report_output_path is request.report_output_path
    assert phase_request.capture_request.symbol == "RVOL"
    assert phase_request.capture_request.historical_initial_query.start == (
        "2026-01-02T09:30:00Z"
    )
    assert phase_request.capture_request.current_initial_query.end == (
        "2026-01-31T09:35:00Z"
    )
    assert phase_request.capture_request.cutoff_timestamp == dt(31)
    assert phase_request.capture_request.allow_live_data is True


def test_provided_transport_is_used_exactly(tmp_path, monkeypatch) -> None:
    calls = []
    request = command(tmp_path)
    write_seed(request.metadata_input_path)
    transport = object()

    def fake_phase_17d(fetcher, phase_request):
        calls.append((fetcher, phase_request))
        return "result"

    monkeypatch.setattr(
        module,
        "StdlibHttpTransport",
        lambda: pytest.fail("default transport should not construct"),
    )
    monkeypatch.setattr(
        module,
        "capture_and_preflight_explicit_alpaca_rvol_bundle",
        fake_phase_17d,
    )

    result = run_manual_explicit_alpaca_rvol_capture_preflight(
        request,
        live_config(),
        transport=transport,
    )

    assert result == "result"
    assert calls[0][0].transport is transport


def test_actual_fake_transport_success_failure_and_stopped_paths(tmp_path) -> None:
    request = command(tmp_path)
    write_seed(request.metadata_input_path)

    success = run_manual_explicit_alpaca_rvol_capture_preflight(
        request,
        live_config(),
        transport=FakeHttpTransport(valid_historical_pages() + [current_page()]),
    )
    assert success.status == ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_SUCCEEDED
    assert is_manual_explicit_alpaca_rvol_capture_success(success) is True
    assert request.metadata_output_path.exists()
    assert request.bundle_output_path.exists()
    assert request.report_output_path.read_text(encoding="utf-8") == success.report
    assert "Relative Volume: 2.0x" in success.report

    failed_request = command(
        tmp_path,
        metadata_output_path=tmp_path / "failed-metadata.json",
        bundle_output_path=tmp_path / "failed-bundle.json",
        report_output_path=tmp_path / "failed-report.txt",
        historical_max_pages=1,
    )
    write_seed(failed_request.metadata_input_path)
    failed = run_manual_explicit_alpaca_rvol_capture_preflight(
        failed_request,
        live_config(),
        transport=FakeHttpTransport(
            [response("RVOL", [raw_bar(2, 35, 100)], next_page_token="NEXT")]
            + [current_page()]
        ),
    )
    assert failed.status == ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_FAILED
    assert "Composition: INCOMPLETE_COLLECTION" in failed.report

    stopped_request = command(
        tmp_path,
        metadata_output_path=tmp_path / "stopped-metadata.json",
        bundle_output_path=tmp_path / "stopped-bundle.json",
        report_output_path=tmp_path / "stopped-report.txt",
        current_max_pages=1,
    )
    write_seed(stopped_request.metadata_input_path)
    stopped = run_manual_explicit_alpaca_rvol_capture_preflight(
        stopped_request,
        live_config(),
        transport=FakeHttpTransport(
            valid_historical_pages() + [current_page(next_page_token="NEXT")]
        ),
    )
    assert stopped.status == ExplicitAlpacaRvolCapturePreflightStatus.CAPTURE_NOT_WRITTEN
    assert stopped.report is None
    assert not stopped_request.metadata_output_path.exists()
    assert not stopped_request.report_output_path.exists()
    stopped_report = render_manual_explicit_alpaca_rvol_capture_stopped_report(
        stopped,
        stopped_request,
    )
    assert "Result: CAPTURE_NOT_WRITTEN" in stopped_report


def test_reports_are_stable(tmp_path) -> None:
    request = command(tmp_path)
    command_report = render_manual_explicit_alpaca_rvol_capture_command_error(
        request,
        ManualExplicitAlpacaRvolCaptureCommandError("LIVE_DATA_CONFIRMATION_REQUIRED"),
    )
    operational_report = render_manual_explicit_alpaca_rvol_capture_error(
        request,
        FileNotFoundError("missing"),
    )

    assert "Result: COMMAND_ERROR" in command_report
    assert "LIVE_DATA_CONFIRMATION_REQUIRED" in command_report
    assert "Result: ERROR" in operational_report
    assert "Error Type: FileNotFoundError" in operational_report
    assert "scan candidates" in command_report
    assert "scan candidates" in operational_report


def test_source_boundary() -> None:
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert imported_modules == {
        "dataclasses",
        "datetime",
        "json",
        "pathlib",
        "market_sentry.config",
        "market_sentry.data.alpaca",
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.explicit_alpaca_rvol_bundle_capture",
        "market_sentry.data.explicit_alpaca_rvol_capture_preflight",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.http",
        "market_sentry.data.http_stdlib",
        "market_sentry.data.json_historical_session_metadata_source",
        "market_sentry.data.json_historical_session_metadata_writer",
    }

    forbidden_import_fragments = [
        "main",
        "argparse",
        "provider",
        "factory",
        "readiness",
        "fmp",
        "json_historical_rvol_bundle",
        "local_json_bundle_preflight",
        "local_json_preflight",
        "scanner",
        "alert",
        "voice",
        "trading",
        "order",
        "tests",
    ]
    for module_name in imported_modules:
        for forbidden in forbidden_import_fragments:
            assert forbidden not in module_name.lower()

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("StdlibHttpTransport") == 1
    assert call_names.count("capture_and_preflight_explicit_alpaca_rvol_bundle") == 1
    forbidden_calls = {
        "load_config",
        "create_market_data_provider",
        "evaluate_live_readiness",
        "load_local_historical_rvol_bundle",
        "write_local_historical_session_metadata",
        "write_local_historical_rvol_bundle",
        "run_local_json_metadata_workflow_preflight",
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "mkdir",
        "getenv",
    }
    assert not forbidden_calls & set(call_names)
