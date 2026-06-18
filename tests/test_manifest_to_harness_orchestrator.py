import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from market_sentry.data import manifest_to_harness_orchestrator
from market_sentry.data.alpaca_historical_bars_fetcher import AlpacaHistoricalBarsPage
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolResult,
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_baseline_composition import (
    HistoricalBaselineCompositionRequest,
    HistoricalBaselineCompositionResult,
    HistoricalBaselineCompositionStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRecordResult,
    HistoricalSessionManifestRecordStatus,
    HistoricalSessionManifestRequest,
    HistoricalSessionManifestResult,
    HistoricalSessionManifestStatus,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
    HistoricalToTodRvolRunResult,
    HistoricalToTodRvolRunStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessResult,
    ManifestToHarnessStatus,
    run_manifest_to_historical_tod_rvol,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeResult


UTC = timezone.utc


def ts(day: int = 2, hour: int = 9, minute: int = 35) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def manifest_request(**overrides) -> HistoricalSessionManifestRequest:
    values = {
        "symbol": "RVOL",
        "bucket": "09:35",
        "current_session_id": "CURRENT-001",
    }
    values.update(overrides)
    return HistoricalSessionManifestRequest(**values)


def harness_request(**overrides) -> HistoricalToTodRvolRunRequest:
    values = {
        "symbol": "RVOL",
        "bucket": "09:35",
        "current_session_id": "CURRENT-001",
        "page_collection_complete": True,
    }
    values.update(overrides)
    return HistoricalToTodRvolRunRequest(**values)


def raw_record(session_id: str = "HIST-01", *, day: int = 2) -> dict[str, object]:
    return {
        "symbol": "RVOL",
        "session_id": session_id,
        "bucket": "09:35",
        "session_start_timestamp": ts(day, 9, 30),
        "session_end_timestamp": ts(day, 10, 0),
        "cutoff_timestamp": ts(day, 9, 35),
        "is_complete": True,
    }


def valid_raw_records(count: int = 20) -> list[dict[str, object]]:
    return [raw_record(f"HIST-{index:02d}", day=index + 1) for index in range(1, count + 1)]


def page_for(count: int = 20, *, volume: int | float = 100) -> AlpacaHistoricalBarsPage:
    bars = tuple(
        {"t": f"2026-01-{index + 1:02d}T09:35:00Z", "v": volume}
        for index in range(1, count + 1)
    )
    return AlpacaHistoricalBarsPage(
        requested_symbols=("RVOL",),
        bars_by_symbol={"RVOL": bars},
        next_page_token=None,
    )


def current_series(*, volume: int | float = 200) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol="RVOL",
        session_id="CURRENT-001",
        bucket="09:35",
        cutoff_timestamp=ts(31, 9, 35),
        bars=(IntradayVolumeBar(ts(31, 9, 35), volume),),
    )


def baseline_result() -> HistoricalBaselineCompositionResult:
    return HistoricalBaselineCompositionResult(
        symbol="RVOL",
        bucket="09:35",
        current_session_id="CURRENT-001",
        minimum_historical_sessions=20,
        observations=(),
        session_results=(),
        eligible_session_count=0,
        status=HistoricalBaselineCompositionStatus.OK,
        reason=None,
    )


def final_result(status: str = CurrentSessionTimeOfDayRvolStatus.OK) -> CurrentSessionTimeOfDayRvolResult:
    tod_result = (
        TimeOfDayRelativeVolumeResult(
            symbol="RVOL",
            bucket="09:35",
            relative_volume=2.0,
            historical_average_cumulative_volume=100.0,
            status="OK",
            reason=None,
            observation_count=20,
        )
        if status == CurrentSessionTimeOfDayRvolStatus.OK
        else None
    )
    return CurrentSessionTimeOfDayRvolResult(
        baseline_result=baseline_result(),
        current_result=None,
        calculation_input=None,
        time_of_day_result=tod_result,
        status=status,
        reason=None if status == CurrentSessionTimeOfDayRvolStatus.OK else status,
    )


def manifest_result(
    status: str = HistoricalSessionManifestStatus.OK,
    *,
    metadata_records=(),
) -> HistoricalSessionManifestResult:
    return HistoricalSessionManifestResult(
        request=manifest_request(),
        record_results=(),
        metadata_records=metadata_records,
        valid_record_count=len(metadata_records),
        status=status,
        reason=None if status == HistoricalSessionManifestStatus.OK else status,
    )


def harness_result(status: str = HistoricalToTodRvolRunStatus.OK) -> HistoricalToTodRvolRunResult:
    baseline_request = HistoricalBaselineCompositionRequest(
        symbol="RVOL",
        bucket="09:35",
        current_session_id="CURRENT-001",
    )
    return HistoricalToTodRvolRunResult(
        request=harness_request(),
        baseline_request=baseline_request,
        assembly_results=(),
        baseline_result=baseline_result(),
        final_result=final_result(
            CurrentSessionTimeOfDayRvolStatus.OK
            if status == HistoricalToTodRvolRunStatus.OK
            else CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED
        ),
        status=status,
        reason=None if status == HistoricalToTodRvolRunStatus.OK else status,
    )


def test_call_order_identity_forwarding_and_artifact_retention(monkeypatch) -> None:
    calls = []
    raw_records = valid_raw_records(1)
    manifest_req = manifest_request(symbol="RVOL")
    page = page_for(1)
    series = current_series()
    harness_req = harness_request(symbol="OTHER")
    emitted_metadata = ("metadata-tuple",)
    manifest_artifact = manifest_result(metadata_records=emitted_metadata)
    harness_artifact = harness_result()

    def fake_manifest(raw_records_arg, manifest_request_arg):
        calls.append("manifest")
        assert raw_records_arg is raw_records
        assert manifest_request_arg is manifest_req
        return manifest_artifact

    def fake_harness(page_arg, metadata_records_arg, current_series_arg, harness_request_arg):
        calls.append("harness")
        assert page_arg is page
        assert metadata_records_arg is emitted_metadata
        assert current_series_arg is series
        assert harness_request_arg is harness_req
        return harness_artifact

    monkeypatch.setattr(
        manifest_to_harness_orchestrator,
        "adapt_historical_session_manifest",
        fake_manifest,
    )
    monkeypatch.setattr(
        manifest_to_harness_orchestrator,
        "run_historical_to_time_of_day_rvol",
        fake_harness,
    )

    result = run_manifest_to_historical_tod_rvol(
        raw_records,
        manifest_req,
        page,
        series,
        harness_req,
    )

    assert calls == ["manifest", "harness"]
    assert result.manifest_result is manifest_artifact
    assert result.harness_result is harness_artifact
    assert result.status == ManifestToHarnessStatus.OK
    assert result.reason is None


@pytest.mark.parametrize(
    (
        "manifest_status",
        "harness_status",
        "expected_status",
        "expected_reason",
    ),
    [
        (
            HistoricalSessionManifestStatus.OK,
            HistoricalToTodRvolRunStatus.OK,
            ManifestToHarnessStatus.OK,
            None,
        ),
        (
            HistoricalSessionManifestStatus.PARTIAL,
            HistoricalToTodRvolRunStatus.OK,
            ManifestToHarnessStatus.MANIFEST_PARTIAL,
            ManifestToHarnessStatus.MANIFEST_PARTIAL,
        ),
        (
            HistoricalSessionManifestStatus.NO_VALID_METADATA,
            HistoricalToTodRvolRunStatus.OK,
            ManifestToHarnessStatus.MANIFEST_FAILED,
            "MANIFEST_FAILED:NO_VALID_METADATA",
        ),
        (
            HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL,
            HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            ManifestToHarnessStatus.MANIFEST_FAILED,
            "MANIFEST_FAILED:INVALID_TARGET_SYMBOL",
        ),
        (
            HistoricalSessionManifestStatus.OK,
            HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            ManifestToHarnessStatus.HARNESS_FAILED,
            "HARNESS_FAILED:FINAL_COMPOSITION_FAILED",
        ),
        (
            HistoricalSessionManifestStatus.PARTIAL,
            HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            ManifestToHarnessStatus.MANIFEST_PARTIAL_AND_HARNESS_FAILED,
            "MANIFEST_PARTIAL_AND_HARNESS_FAILED:FINAL_COMPOSITION_FAILED",
        ),
        (
            "FUTURE_MANIFEST_STATUS",
            HistoricalToTodRvolRunStatus.OK,
            ManifestToHarnessStatus.MANIFEST_FAILED,
            "MANIFEST_FAILED:FUTURE_MANIFEST_STATUS",
        ),
        (
            HistoricalSessionManifestStatus.OK,
            "FUTURE_HARNESS_STATUS",
            ManifestToHarnessStatus.HARNESS_FAILED,
            "HARNESS_FAILED:FUTURE_HARNESS_STATUS",
        ),
    ],
)
def test_coordinator_status_mapping(
    monkeypatch,
    manifest_status,
    harness_status,
    expected_status,
    expected_reason,
) -> None:
    monkeypatch.setattr(
        manifest_to_harness_orchestrator,
        "adapt_historical_session_manifest",
        lambda *args: manifest_result(status=manifest_status),
    )
    monkeypatch.setattr(
        manifest_to_harness_orchestrator,
        "run_historical_to_time_of_day_rvol",
        lambda *args: harness_result(status=harness_status),
    )

    result = run_manifest_to_historical_tod_rvol(
        [],
        manifest_request(),
        page_for(1),
        current_series(),
        harness_request(),
    )

    assert result.status == expected_status
    assert result.reason == expected_reason


@pytest.mark.parametrize(
    "manifest_status",
    [
        HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL,
        HistoricalSessionManifestStatus.NO_VALID_METADATA,
        HistoricalSessionManifestStatus.PARTIAL,
    ],
)
def test_harness_runs_for_invalid_no_valid_and_partial_manifest_results(
    monkeypatch,
    manifest_status,
) -> None:
    harness_calls = []
    manifest_artifact = manifest_result(status=manifest_status)
    monkeypatch.setattr(
        manifest_to_harness_orchestrator,
        "adapt_historical_session_manifest",
        lambda *args: manifest_artifact,
    )
    monkeypatch.setattr(
        manifest_to_harness_orchestrator,
        "run_historical_to_time_of_day_rvol",
        lambda *args: harness_calls.append(args) or harness_result(),
    )

    result = run_manifest_to_historical_tod_rvol(
        [],
        manifest_request(symbol=""),
        page_for(1),
        current_series(),
        harness_request(),
    )

    assert len(harness_calls) == 1
    assert harness_calls[0][1] is manifest_artifact.metadata_records
    assert result.harness_result.status == HistoricalToTodRvolRunStatus.OK


def test_mismatched_manifest_and_harness_requests_are_forwarded_without_repair(
    monkeypatch,
) -> None:
    manifest_req = manifest_request(symbol="RVOL", bucket="09:35")
    harness_req = harness_request(symbol="OTHER", bucket="09:40")
    seen = {}
    manifest_artifact = manifest_result()

    def fake_manifest(raw, request):
        seen["manifest_request"] = request
        return manifest_artifact

    def fake_harness(page, metadata, current, request):
        seen["harness_request"] = request
        return harness_result()

    monkeypatch.setattr(
        manifest_to_harness_orchestrator,
        "adapt_historical_session_manifest",
        fake_manifest,
    )
    monkeypatch.setattr(
        manifest_to_harness_orchestrator,
        "run_historical_to_time_of_day_rvol",
        fake_harness,
    )

    run_manifest_to_historical_tod_rvol(
        valid_raw_records(1),
        manifest_req,
        page_for(1),
        current_series(),
        harness_req,
    )

    assert seen["manifest_request"] is manifest_req
    assert seen["harness_request"] is harness_req
    assert harness_req.symbol == "OTHER"
    assert harness_req.bucket == "09:40"


def test_coordinator_result_is_frozen_and_repeated_calls_create_new_objects(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        manifest_to_harness_orchestrator,
        "adapt_historical_session_manifest",
        lambda *args: manifest_result(),
    )
    monkeypatch.setattr(
        manifest_to_harness_orchestrator,
        "run_historical_to_time_of_day_rvol",
        lambda *args: harness_result(),
    )

    first = run_manifest_to_historical_tod_rvol(
        [],
        manifest_request(),
        page_for(1),
        current_series(),
        harness_request(),
    )
    second = run_manifest_to_historical_tod_rvol(
        [],
        manifest_request(),
        page_for(1),
        current_series(),
        harness_request(),
    )

    assert isinstance(first, ManifestToHarnessResult)
    assert first is not second
    with pytest.raises(FrozenInstanceError):
        first.status = "changed"  # type: ignore[misc]


def test_real_valid_integration_returns_ok_and_final_rvol() -> None:
    result = run_manifest_to_historical_tod_rvol(
        valid_raw_records(20),
        manifest_request(),
        page_for(20, volume=100),
        current_series(volume=200),
        harness_request(),
    )

    assert result.manifest_result.status == HistoricalSessionManifestStatus.OK
    assert result.harness_result.status == HistoricalToTodRvolRunStatus.OK
    assert result.status == ManifestToHarnessStatus.OK
    assert result.harness_result.final_result.time_of_day_result is not None
    assert result.harness_result.final_result.time_of_day_result.relative_volume == 2.0


def test_real_partial_manifest_can_still_have_successful_harness() -> None:
    records = valid_raw_records(20)
    invalid = raw_record("BAD", day=30)
    del invalid["bucket"]
    records.append(invalid)

    result = run_manifest_to_historical_tod_rvol(
        records,
        manifest_request(),
        page_for(20, volume=100),
        current_series(volume=200),
        harness_request(),
    )

    assert result.manifest_result.status == HistoricalSessionManifestStatus.PARTIAL
    assert result.manifest_result.valid_record_count == 20
    assert result.harness_result.status == HistoricalToTodRvolRunStatus.OK
    assert result.status == ManifestToHarnessStatus.MANIFEST_PARTIAL
    assert result.reason == ManifestToHarnessStatus.MANIFEST_PARTIAL
    assert result.harness_result.final_result.time_of_day_result is not None
    assert result.harness_result.final_result.time_of_day_result.relative_volume == 2.0


def test_real_invalid_manifest_request_still_invokes_harness_and_preserves_failure() -> None:
    result = run_manifest_to_historical_tod_rvol(
        valid_raw_records(20),
        manifest_request(symbol=" "),
        page_for(20, volume=100),
        current_series(volume=200),
        harness_request(),
    )

    assert result.manifest_result.status == (
        HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL
    )
    assert result.manifest_result.metadata_records == ()
    assert result.harness_result.status == (
        HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
    )
    assert result.status == ManifestToHarnessStatus.MANIFEST_FAILED
    assert result.reason == "MANIFEST_FAILED:INVALID_TARGET_SYMBOL"


def test_status_values_are_stable_strings() -> None:
    assert ManifestToHarnessStatus.OK == "OK"
    assert ManifestToHarnessStatus.MANIFEST_PARTIAL == "MANIFEST_PARTIAL"
    assert ManifestToHarnessStatus.MANIFEST_FAILED == "MANIFEST_FAILED"
    assert ManifestToHarnessStatus.HARNESS_FAILED == "HARNESS_FAILED"
    assert (
        ManifestToHarnessStatus.MANIFEST_PARTIAL_AND_HARNESS_FAILED
        == "MANIFEST_PARTIAL_AND_HARNESS_FAILED"
    )


def test_source_boundary_uses_only_approved_interfaces() -> None:
    source = inspect.getsource(manifest_to_harness_orchestrator)
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
        "__future__",
        "collections.abc",
        "dataclasses",
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.historical_tod_rvol_harness",
        "market_sentry.data.intraday_bucket_adapter",
    }

    forbidden_terms = [
        "assemble_historical_sessions_from_page",
        "compose_historical_baseline",
        "compose_current_session_time_of_day_rvol",
        "calculate_time_of_day_relative_volume",
        "calculate_cumulative_volume_at_bucket",
        "alpaca_historical_bars_adapter",
        "HttpTransport",
        "market_sentry.data.http",
        "market_sentry.data.http_stdlib",
        "market_sentry.data.factory",
        "market_sentry.config",
        "market_sentry.live_readiness",
        "market_sentry.scanner",
        "market_sentry.alerts",
        "voice",
        "StockCandidate",
        "LiveCandidateBuilder",
        "LiveComposedMarketDataProvider",
        "place_order",
        "execute_order",
        "broker",
        "copy(",
        "list(",
        "tuple(manifest_result.metadata_records",
        "sorted(",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
