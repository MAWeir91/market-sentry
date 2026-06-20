import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from market_sentry.data import explicit_alpaca_rvol_capture_preflight as module
from market_sentry.data.alpaca import AlpacaMarketDataSettings
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsFetcher,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.explicit_alpaca_rvol_bundle_capture import (
    ExplicitAlpacaRvolBundleCaptureRequest,
    ExplicitAlpacaRvolBundleCaptureResult,
    ExplicitAlpacaRvolBundleCaptureStatus,
)
from market_sentry.data.explicit_alpaca_rvol_capture_preflight import (
    ExplicitAlpacaRvolCapturePreflightRequest,
    ExplicitAlpacaRvolCapturePreflightStatus,
    capture_and_preflight_explicit_alpaca_rvol_bundle,
    is_explicit_alpaca_rvol_capture_preflight_success,
    render_explicit_alpaca_rvol_capture_preflight_report,
)
from market_sentry.data.http import FakeHttpTransport, HttpResponse
from market_sentry.data.json_historical_session_metadata_writer import (
    JsonHistoricalSessionMetadataWriteError,
)


UTC = timezone.utc


def query(**overrides) -> AlpacaHistoricalBarsQuery:
    values = {
        "timeframe": "1Min",
        "start": "2026-01-02T09:30:00Z",
        "end": "2026-01-21T10:00:00Z",
        "limit": 1000,
        "page_token": None,
        "sort": "asc",
    }
    values.update(overrides)
    return AlpacaHistoricalBarsQuery(**values)


def capture_request(
    output_path,
    *,
    allow_live_data=True,
    historical_max_pages=5,
    current_max_pages=5,
) -> ExplicitAlpacaRvolBundleCaptureRequest:
    return ExplicitAlpacaRvolBundleCaptureRequest(
        symbol="RVOL",
        historical_initial_query=query(),
        historical_max_pages=historical_max_pages,
        current_initial_query=query(
            start="2026-01-31T09:30:00Z",
            end="2026-01-31T09:35:00Z",
        ),
        current_max_pages=current_max_pages,
        current_session_id="CURRENT-001",
        bucket="09:35",
        cutoff_timestamp=datetime(2026, 1, 31, 9, 35, tzinfo=UTC),
        minimum_historical_sessions=20,
        output_path=output_path,
        allow_live_data=allow_live_data,
    )


def preflight_request(
    tmp_path,
    *,
    allow_live_data=True,
    bundle_path=None,
    metadata_path=None,
    report_path=None,
    records=None,
) -> ExplicitAlpacaRvolCapturePreflightRequest:
    bundle_path = tmp_path / "bundle.json" if bundle_path is None else bundle_path
    metadata_path = (
        tmp_path / "metadata.json" if metadata_path is None else metadata_path
    )
    return ExplicitAlpacaRvolCapturePreflightRequest(
        capture_request=capture_request(
            bundle_path,
            allow_live_data=allow_live_data,
        ),
        metadata_records=valid_records() if records is None else records,
        metadata_output_path=metadata_path,
        report_output_path=report_path,
    )


def dt(day: int, hour: int = 9, minute: int = 35) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def metadata_record(session_id: str, *, day: int, is_complete=True) -> dict[str, object]:
    return {
        "symbol": "RVOL",
        "session_id": session_id,
        "bucket": "09:35",
        "session_start_timestamp": dt(day, 9, 30),
        "session_end_timestamp": dt(day, 10, 0),
        "cutoff_timestamp": dt(day, 9, 35),
        "is_complete": is_complete,
    }


def valid_records(count: int = 20) -> list[dict[str, object]]:
    return [
        metadata_record(f"HIST-{index:02d}", day=index + 1)
        for index in range(1, count + 1)
    ]


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


def current_page(*, bars=None, next_page_token=None) -> HttpResponse:
    return response(
        "RVOL",
        [raw_bar(31, 35, 200)] if bars is None else bars,
        next_page_token=next_page_token,
    )


def fetcher_with_responses(items) -> AlpacaHistoricalBarsFetcher:
    return AlpacaHistoricalBarsFetcher(
        settings=AlpacaMarketDataSettings(
            api_key="test-key",
            api_secret="test-secret",
        ),
        transport=FakeHttpTransport(items),
    )


def successful_fetcher() -> AlpacaHistoricalBarsFetcher:
    return fetcher_with_responses(valid_historical_pages() + [current_page()])


def fake_success_preflight(relative_volume=2.0):
    tod = SimpleNamespace(
        status="OK",
        reason=None,
        relative_volume=relative_volume,
    )
    final = SimpleNamespace(status="OK", reason=None, time_of_day_result=tod)
    harness = SimpleNamespace(status="OK", reason=None, final_result=final)
    coordinator = SimpleNamespace(
        status="OK",
        reason=None,
        manifest_result=SimpleNamespace(status="OK", reason=None),
        harness_result=harness,
    )
    bridge = SimpleNamespace(
        status="WORKFLOW_RAN",
        reason=None,
        composition_result=SimpleNamespace(status="COMPOSED", reason=None),
        workflow_result=coordinator,
    )
    workflow = SimpleNamespace(
        metadata_load_result=SimpleNamespace(status="LOADED", reason=None),
        status="WORKFLOW_BRIDGE_RAN",
        reason=None,
        workflow_bridge_result=bridge,
    )
    return SimpleNamespace(workflow_result=workflow)


def fake_failure_preflight() -> SimpleNamespace:
    bridge = SimpleNamespace(
        status="WORKFLOW_NOT_RUN",
        reason="COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION",
        composition_result=SimpleNamespace(
            status="INCOMPLETE_COLLECTION",
            reason="MAX_PAGE_LIMIT_REACHED",
        ),
        workflow_result=None,
    )
    workflow = SimpleNamespace(
        metadata_load_result=SimpleNamespace(status="LOADED", reason=None),
        status="WORKFLOW_BRIDGE_RAN",
        reason=None,
        workflow_bridge_result=bridge,
    )
    return SimpleNamespace(workflow_result=workflow)


def fake_capture_result(
    request: ExplicitAlpacaRvolBundleCaptureRequest,
    *,
    status=ExplicitAlpacaRvolBundleCaptureStatus.BUNDLE_WRITTEN,
) -> ExplicitAlpacaRvolBundleCaptureResult:
    return ExplicitAlpacaRvolBundleCaptureResult(
        request=request,
        output_path=request.output_path,
        historical_collection=object(),
        current_collection=object(),
        current_composition=object(),
        current_series_result=SimpleNamespace(intraday_series=object()),
        manifest_request=object(),
        harness_request=object(),
        output_written=status == ExplicitAlpacaRvolBundleCaptureStatus.BUNDLE_WRITTEN,
        status=status,
        reason=None,
    )


def install_no_work_spies(monkeypatch):
    calls = []

    def track(name):
        def inner(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"{name} should not run")

        return inner

    monkeypatch.setattr(
        module,
        "render_local_historical_session_metadata",
        track("render"),
    )
    monkeypatch.setattr(
        module,
        "capture_explicit_alpaca_rvol_bundle",
        track("capture"),
    )
    monkeypatch.setattr(
        module,
        "write_local_historical_session_metadata",
        track("metadata_write"),
    )
    monkeypatch.setattr(
        module,
        "run_local_json_metadata_workflow_preflight",
        track("preflight"),
    )
    return calls


def test_frozen_request_and_result_models(tmp_path) -> None:
    request = preflight_request(tmp_path)
    result = module.ExplicitAlpacaRvolCapturePreflightResult(
        request=request,
        metadata_path=request.metadata_output_path,
        bundle_path=request.capture_request.output_path,
        report_path=request.report_output_path,
        capture_result=None,
        metadata_written=False,
        preflight_result=None,
        report=None,
        report_written=False,
        status=ExplicitAlpacaRvolCapturePreflightStatus.LIVE_DATA_NOT_ALLOWED,
        reason=ExplicitAlpacaRvolCapturePreflightStatus.LIVE_DATA_NOT_ALLOWED,
    )

    with pytest.raises(FrozenInstanceError):
        request.metadata_output_path = tmp_path / "other.json"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.status = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("request_factory", "expected_error"),
    [
        (
            lambda tmp_path: preflight_request(tmp_path, bundle_path="bundle.json"),
            "output_path must be a pathlib.Path.",
        ),
        (
            lambda tmp_path: preflight_request(tmp_path, metadata_path="metadata.json"),
            "metadata_output_path must be a pathlib.Path.",
        ),
        (
            lambda tmp_path: preflight_request(tmp_path, report_path="report.txt"),
            "report_output_path must be a pathlib.Path or None.",
        ),
    ],
)
def test_path_type_errors_before_any_work(
    monkeypatch,
    tmp_path,
    request_factory,
    expected_error,
) -> None:
    calls = install_no_work_spies(monkeypatch)

    with pytest.raises(TypeError) as exc_info:
        capture_and_preflight_explicit_alpaca_rvol_bundle(
            object(),
            request_factory(tmp_path),
        )

    assert str(exc_info.value) == expected_error
    assert calls == []


@pytest.mark.parametrize(
    ("metadata", "bundle", "report", "reason"),
    [
        ("same.json", "same.json", "report.json", "METADATA_PATH_EQUALS_BUNDLE_PATH"),
        (
            "metadata.json",
            "bundle.json",
            "metadata.json",
            "REPORT_PATH_EQUALS_METADATA_PATH",
        ),
        (
            "metadata.json",
            "bundle.json",
            "bundle.json",
            "REPORT_PATH_EQUALS_BUNDLE_PATH",
        ),
        (
            "same.json",
            "same.json",
            "same.json",
            "METADATA_PATH_EQUALS_BUNDLE_PATH",
        ),
    ],
)
def test_collision_guards_before_any_work_and_with_precedence(
    monkeypatch,
    tmp_path,
    metadata,
    bundle,
    report,
    reason,
) -> None:
    calls = install_no_work_spies(monkeypatch)
    request = preflight_request(
        tmp_path,
        metadata_path=tmp_path / metadata,
        bundle_path=tmp_path / bundle,
        report_path=tmp_path / report,
    )

    result = capture_and_preflight_explicit_alpaca_rvol_bundle(object(), request)

    assert result.request is request
    assert result.metadata_path is request.metadata_output_path
    assert result.bundle_path is request.capture_request.output_path
    assert result.report_path is request.report_output_path
    assert result.status == ExplicitAlpacaRvolCapturePreflightStatus.OUTPUT_PATH_CONFLICT
    assert result.reason == reason
    assert result.capture_result is None
    assert result.metadata_written is False
    assert result.preflight_result is None
    assert result.report is None
    assert result.report_written is False
    assert calls == []


@pytest.mark.parametrize("gate", [False, 1, "true", None])
def test_live_data_gate_denies_before_render_capture_or_writes(
    monkeypatch,
    tmp_path,
    gate,
) -> None:
    calls = install_no_work_spies(monkeypatch)
    request = preflight_request(tmp_path, allow_live_data=gate)

    result = capture_and_preflight_explicit_alpaca_rvol_bundle(object(), request)

    assert result.status == ExplicitAlpacaRvolCapturePreflightStatus.LIVE_DATA_NOT_ALLOWED
    assert result.reason == ExplicitAlpacaRvolCapturePreflightStatus.LIVE_DATA_NOT_ALLOWED
    assert result.capture_result is None
    assert result.metadata_written is False
    assert result.preflight_result is None
    assert result.report is None
    assert result.report_written is False
    assert calls == []


def test_metadata_renderability_runs_once_before_capture(monkeypatch, tmp_path) -> None:
    calls = []
    request = preflight_request(tmp_path)
    capture_result = fake_capture_result(request.capture_request)
    preflight = fake_success_preflight()

    def fake_render(records):
        calls.append(("render", records))
        return "metadata"

    def fake_capture(fetcher, capture_request_arg):
        calls.append(("capture", capture_request_arg))
        return capture_result

    def fake_write(path, records):
        calls.append(("write", path, records))

    def fake_preflight(path, collection, manifest, current_series, harness):
        calls.append(("preflight", path, collection, manifest, current_series, harness))
        return preflight

    monkeypatch.setattr(module, "render_local_historical_session_metadata", fake_render)
    monkeypatch.setattr(module, "capture_explicit_alpaca_rvol_bundle", fake_capture)
    monkeypatch.setattr(module, "write_local_historical_session_metadata", fake_write)
    monkeypatch.setattr(module, "run_local_json_metadata_workflow_preflight", fake_preflight)

    result = capture_and_preflight_explicit_alpaca_rvol_bundle(object(), request)

    assert [call[0] for call in calls] == [
        "render",
        "capture",
        "write",
        "preflight",
    ]
    assert calls[0][1] is request.metadata_records
    assert calls[1][1] is request.capture_request
    assert calls[2][1] is request.metadata_output_path
    assert calls[2][2] is request.metadata_records
    assert calls[3][1] is request.metadata_output_path
    assert calls[3][2] is capture_result.historical_collection
    assert calls[3][3] is capture_result.manifest_request
    assert calls[3][4] is capture_result.current_series_result.intraday_series
    assert calls[3][5] is capture_result.harness_request
    assert result.capture_result is capture_result
    assert result.preflight_result is preflight
    assert result.status == ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_SUCCEEDED


def test_metadata_representation_error_propagates_before_capture(monkeypatch, tmp_path):
    error = JsonHistoricalSessionMetadataWriteError("UNSUPPORTED_VALUE:records[0]")
    calls = []
    monkeypatch.setattr(
        module,
        "render_local_historical_session_metadata",
        lambda *_args: (_ for _ in ()).throw(error),
    )
    monkeypatch.setattr(
        module,
        "capture_explicit_alpaca_rvol_bundle",
        lambda *_args: calls.append("capture"),
    )

    with pytest.raises(JsonHistoricalSessionMetadataWriteError) as exc_info:
        capture_and_preflight_explicit_alpaca_rvol_bundle(
            object(),
            preflight_request(tmp_path),
        )

    assert exc_info.value is error
    assert calls == []


def test_capture_not_written_stops_before_metadata_preflight_or_report(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []
    request = preflight_request(tmp_path, report_path=tmp_path / "report.txt")
    capture_result = fake_capture_result(
        request.capture_request,
        status=ExplicitAlpacaRvolBundleCaptureStatus.CURRENT_COLLECTION_NOT_COMPOSABLE,
    )
    monkeypatch.setattr(
        module,
        "render_local_historical_session_metadata",
        lambda records: calls.append(("render", records)),
    )
    monkeypatch.setattr(
        module,
        "capture_explicit_alpaca_rvol_bundle",
        lambda fetcher, capture_request_arg: calls.append(
            ("capture", capture_request_arg)
        )
        or capture_result,
    )
    monkeypatch.setattr(
        module,
        "write_local_historical_session_metadata",
        lambda *_args: pytest.fail("metadata write should not run"),
    )
    monkeypatch.setattr(
        module,
        "run_local_json_metadata_workflow_preflight",
        lambda *_args: pytest.fail("preflight should not run"),
    )

    result = capture_and_preflight_explicit_alpaca_rvol_bundle(object(), request)

    assert [call[0] for call in calls] == ["render", "capture"]
    assert result.capture_result is capture_result
    assert result.status == ExplicitAlpacaRvolCapturePreflightStatus.CAPTURE_NOT_WRITTEN
    assert result.reason == "CAPTURE_NOT_WRITTEN:CURRENT_COLLECTION_NOT_COMPOSABLE"
    assert result.metadata_written is False
    assert result.preflight_result is None
    assert result.report is None
    assert result.report_written is False
    assert not request.report_output_path.exists()


def test_report_output_is_optional_and_exact(monkeypatch, tmp_path) -> None:
    request = preflight_request(tmp_path, report_path=tmp_path / "report.txt")
    capture_result = fake_capture_result(request.capture_request)
    preflight = fake_success_preflight()
    monkeypatch.setattr(module, "render_local_historical_session_metadata", lambda *_: "")
    monkeypatch.setattr(
        module,
        "capture_explicit_alpaca_rvol_bundle",
        lambda *_args: capture_result,
    )
    monkeypatch.setattr(module, "write_local_historical_session_metadata", lambda *_: None)
    monkeypatch.setattr(
        module,
        "run_local_json_metadata_workflow_preflight",
        lambda *_args: preflight,
    )

    result = capture_and_preflight_explicit_alpaca_rvol_bundle(object(), request)

    assert result.report is not None
    assert result.report_written is True
    assert request.report_output_path.read_text(encoding="utf-8") == result.report
    assert not result.report.endswith("\n")
    assert is_explicit_alpaca_rvol_capture_preflight_success(result) is True

    no_report_request = preflight_request(tmp_path, report_path=None)
    no_report_capture = fake_capture_result(no_report_request.capture_request)
    monkeypatch.setattr(
        module,
        "capture_explicit_alpaca_rvol_bundle",
        lambda *_args: no_report_capture,
    )
    no_report_result = capture_and_preflight_explicit_alpaca_rvol_bundle(
        object(),
        no_report_request,
    )

    assert no_report_result.report is not None
    assert no_report_result.report_written is False


def test_returned_preflight_failure_still_renders_and_writes_report(
    monkeypatch,
    tmp_path,
) -> None:
    request = preflight_request(tmp_path, report_path=tmp_path / "failure-report.txt")
    capture_result = fake_capture_result(request.capture_request)
    monkeypatch.setattr(module, "render_local_historical_session_metadata", lambda *_: "")
    monkeypatch.setattr(
        module,
        "capture_explicit_alpaca_rvol_bundle",
        lambda *_args: capture_result,
    )
    monkeypatch.setattr(module, "write_local_historical_session_metadata", lambda *_: None)
    monkeypatch.setattr(
        module,
        "run_local_json_metadata_workflow_preflight",
        lambda *_args: fake_failure_preflight(),
    )

    result = capture_and_preflight_explicit_alpaca_rvol_bundle(object(), request)

    assert result.status == ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_FAILED
    assert result.reason == ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_FAILED
    assert result.metadata_written is True
    assert result.report_written is True
    assert "Composition: INCOMPLETE_COLLECTION" in result.report
    assert "Relative Volume: N/A" in result.report
    assert request.report_output_path.read_text(encoding="utf-8") == result.report
    assert is_explicit_alpaca_rvol_capture_preflight_success(result) is False


@pytest.mark.parametrize(
    "target",
    [
        "capture_explicit_alpaca_rvol_bundle",
        "write_local_historical_session_metadata",
        "run_local_json_metadata_workflow_preflight",
    ],
)
def test_unexpected_dependency_errors_propagate(monkeypatch, tmp_path, target) -> None:
    request = preflight_request(tmp_path)
    error = RuntimeError(target)
    monkeypatch.setattr(module, "render_local_historical_session_metadata", lambda *_: "")
    if target == "capture_explicit_alpaca_rvol_bundle":
        monkeypatch.setattr(module, target, lambda *_args: (_ for _ in ()).throw(error))
    else:
        capture_result = fake_capture_result(request.capture_request)
        monkeypatch.setattr(
            module,
            "capture_explicit_alpaca_rvol_bundle",
            lambda *_args: capture_result,
        )
        monkeypatch.setattr(
            module,
            target,
            lambda *_args: (_ for _ in ()).throw(error),
        )
        if target == "write_local_historical_session_metadata":
            monkeypatch.setattr(
                module,
                "run_local_json_metadata_workflow_preflight",
                lambda *_args: pytest.fail("preflight should not run"),
            )

    with pytest.raises(RuntimeError) as exc_info:
        capture_and_preflight_explicit_alpaca_rvol_bundle(object(), request)

    assert exc_info.value is error


def test_report_output_error_propagates_without_synthetic_result(
    monkeypatch,
    tmp_path,
) -> None:
    request = preflight_request(tmp_path, report_path=tmp_path / "report.txt")
    error = OSError("cannot write report")
    monkeypatch.setattr(module, "render_local_historical_session_metadata", lambda *_: "")
    monkeypatch.setattr(
        module,
        "capture_explicit_alpaca_rvol_bundle",
        lambda *_args: fake_capture_result(request.capture_request),
    )
    monkeypatch.setattr(module, "write_local_historical_session_metadata", lambda *_: None)
    monkeypatch.setattr(
        module,
        "run_local_json_metadata_workflow_preflight",
        lambda *_args: fake_success_preflight(),
    )
    monkeypatch.setattr(Path, "write_text", lambda *_args, **_kwargs: (_ for _ in ()).throw(error))

    with pytest.raises(OSError) as exc_info:
        capture_and_preflight_explicit_alpaca_rvol_bundle(object(), request)

    assert exc_info.value is error


def test_render_report_line_order_and_na_values(tmp_path) -> None:
    request = preflight_request(tmp_path)
    result = module.ExplicitAlpacaRvolCapturePreflightResult(
        request=request,
        metadata_path=request.metadata_output_path,
        bundle_path=request.capture_request.output_path,
        report_path=None,
        capture_result=fake_capture_result(request.capture_request),
        metadata_written=True,
        preflight_result=SimpleNamespace(
            workflow_result=SimpleNamespace(
                metadata_load_result=SimpleNamespace(status="LOADED", reason=None),
                status="WORKFLOW_BRIDGE_RAN",
                reason=None,
                workflow_bridge_result=None,
            )
        ),
        report=None,
        report_written=False,
        status=ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_FAILED,
        reason=ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_FAILED,
    )

    report = render_explicit_alpaca_rvol_capture_preflight_report(result)

    assert report.splitlines() == [
        "Market Sentry Explicit Alpaca RVOL Capture Preflight",
        f"Metadata Path: {request.metadata_output_path}",
        f"Bundle Path: {request.capture_request.output_path}",
        "Input Mode: EXPLICIT_ALPACA_CAPTURE",
        "Capture: BUNDLE_WRITTEN",
        "Metadata Load: LOADED",
        "Metadata Load Reason: N/A",
        "Workflow: WORKFLOW_BRIDGE_RAN",
        "Workflow Reason: N/A",
        "Bridge: N/A",
        "Bridge Reason: N/A",
        "Composition: N/A",
        "Coordinator: N/A",
        "Coordinator Reason: N/A",
        "Manifest: N/A",
        "Manifest Reason: N/A",
        "Harness: N/A",
        "Harness Reason: N/A",
        "Final: N/A",
        "Final Reason: N/A",
        "Time-of-Day RVOL: N/A",
        "Time-of-Day RVOL Reason: N/A",
        "Relative Volume: N/A",
        module.EXPLICIT_ALPACA_CAPTURE_PREFLIGHT_NOTE,
    ]


def test_actual_fake_alpaca_success_writes_bundle_metadata_report_and_rvol_two(
    tmp_path,
) -> None:
    report_path = tmp_path / "report.txt"
    request = preflight_request(tmp_path, report_path=report_path)

    result = capture_and_preflight_explicit_alpaca_rvol_bundle(
        successful_fetcher(),
        request,
    )

    assert result.status == ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_SUCCEEDED
    assert result.reason is None
    assert request.capture_request.output_path.exists()
    assert request.metadata_output_path.exists()
    assert report_path.read_text(encoding="utf-8") == result.report
    assert "Input Mode: EXPLICIT_ALPACA_CAPTURE" in result.report
    assert "Capture: BUNDLE_WRITTEN" in result.report
    assert "Relative Volume: 2.0x" in result.report
    assert "FMP" in result.report
    assert "voice alerts" in result.report


def test_actual_historical_incomplete_still_writes_and_reports_preflight_failure(
    tmp_path,
) -> None:
    historical_page = response("RVOL", [raw_bar(2, 35, 100)], next_page_token="NEXT")
    fetcher = fetcher_with_responses([historical_page, current_page()])
    request = preflight_request(
        tmp_path,
        report_path=tmp_path / "historical-incomplete-report.txt",
    )
    request = ExplicitAlpacaRvolCapturePreflightRequest(
        capture_request=capture_request(
            request.capture_request.output_path,
            historical_max_pages=1,
        ),
        metadata_records=request.metadata_records,
        metadata_output_path=request.metadata_output_path,
        report_output_path=request.report_output_path,
    )

    result = capture_and_preflight_explicit_alpaca_rvol_bundle(fetcher, request)

    assert result.status == ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_FAILED
    assert result.reason == ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_FAILED
    assert request.capture_request.output_path.exists()
    assert request.metadata_output_path.exists()
    assert "Composition: INCOMPLETE_COLLECTION" in result.report
    assert "Bridge Reason: COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION" in result.report
    assert "Relative Volume: N/A" in result.report


def test_actual_current_capture_failure_does_not_write_metadata_or_report(
    tmp_path,
) -> None:
    fetcher = fetcher_with_responses(
        valid_historical_pages()
        + [current_page(next_page_token="NEXT")]
    )
    request = preflight_request(tmp_path, report_path=tmp_path / "report.txt")
    request = ExplicitAlpacaRvolCapturePreflightRequest(
        capture_request=capture_request(
            request.capture_request.output_path,
            current_max_pages=1,
        ),
        metadata_records=request.metadata_records,
        metadata_output_path=request.metadata_output_path,
        report_output_path=request.report_output_path,
    )

    result = capture_and_preflight_explicit_alpaca_rvol_bundle(fetcher, request)

    assert result.status == ExplicitAlpacaRvolCapturePreflightStatus.CAPTURE_NOT_WRITTEN
    assert result.reason == "CAPTURE_NOT_WRITTEN:CURRENT_COLLECTION_NOT_COMPOSABLE"
    assert result.capture_result.status == (
        ExplicitAlpacaRvolBundleCaptureStatus.CURRENT_COLLECTION_NOT_COMPOSABLE
    )
    assert not request.capture_request.output_path.exists()
    assert not request.metadata_output_path.exists()
    assert not request.report_output_path.exists()
    assert result.preflight_result is None
    assert result.report is None


def test_actual_report_missing_parent_error_keeps_metadata_and_bundle(tmp_path) -> None:
    request = preflight_request(
        tmp_path,
        report_path=tmp_path / "missing-parent" / "report.txt",
    )

    with pytest.raises(FileNotFoundError):
        capture_and_preflight_explicit_alpaca_rvol_bundle(
            successful_fetcher(),
            request,
        )

    assert request.capture_request.output_path.exists()
    assert request.metadata_output_path.exists()
    assert not (tmp_path / "missing-parent").exists()


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
        "collections.abc",
        "dataclasses",
        "pathlib",
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.explicit_alpaca_rvol_bundle_capture",
        "market_sentry.data.json_historical_session_metadata_writer",
        "market_sentry.data.local_json_metadata_workflow_preflight",
    }

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("capture_explicit_alpaca_rvol_bundle") == 1
    assert call_names.count("render_local_historical_session_metadata") == 1
    assert call_names.count("write_local_historical_session_metadata") == 1
    assert call_names.count("run_local_json_metadata_workflow_preflight") == 1
    assert call_names.count("write_text") == 1
    forbidden_calls = {
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "mkdir",
        "read_text",
        "read_bytes",
        "fetch_bars",
        "getenv",
        "load_local_historical_rvol_bundle",
        "JsonHistoricalSessionMetadataFileSource",
    }
    assert not forbidden_calls & set(call_names)

    forbidden_import_fragments = [
        "main",
        "argparse",
        "sys",
        "config",
        "provider",
        "factory",
        "readiness",
        "http",
        "transport",
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
