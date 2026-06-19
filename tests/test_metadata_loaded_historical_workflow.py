import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from market_sentry.data import metadata_loaded_historical_workflow
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.collected_pages_to_manifest_workflow import (
    CollectedPagesToManifestWorkflowResult,
    CollectedPagesToManifestWorkflowStatus,
)
from market_sentry.data.current_session_tod_rvol import CurrentSessionTimeOfDayRvolStatus
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsCollectedPage,
    HistoricalBarsPageCollectionRequest,
    HistoricalBarsPageCollectionResult,
    HistoricalBarsPageCollectionStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
)
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSourceLoadResult,
    HistoricalSessionMetadataSourceLoadStatus,
    StaticHistoricalSessionMetadataSource,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
    HistoricalToTodRvolRunStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayBucketStatus,
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.manifest_to_harness_orchestrator import ManifestToHarnessStatus
from market_sentry.data.metadata_loaded_historical_workflow import (
    MetadataLoadedHistoricalWorkflowStatus,
    run_metadata_loaded_historical_workflow,
)


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


def valid_raw_records(count: int = 20) -> tuple[dict[str, object], ...]:
    return tuple(
        raw_record(f"HIST-{index:02d}", day=index + 1)
        for index in range(1, count + 1)
    )


def query(**overrides) -> AlpacaHistoricalBarsQuery:
    values = {
        "timeframe": "1Min",
        "start": "2026-01-02T09:30:00Z",
        "end": "2026-01-21T10:00:00Z",
    }
    values.update(overrides)
    return AlpacaHistoricalBarsQuery(**values)


def historical_bar(day: int, minute: int, volume) -> dict[str, object]:
    return {
        "t": f"2026-01-{day:02d}T09:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "h": 1.0,
        "l": 1.0,
        "c": 1.0,
    }


def page_for(bars, *, next_page_token=None) -> AlpacaHistoricalBarsPage:
    return AlpacaHistoricalBarsPage(
        requested_symbols=("RVOL",),
        bars_by_symbol={"RVOL": tuple(bars)},
        next_page_token=next_page_token,
    )


def collection_from_pages(
    pages,
    *,
    status=HistoricalBarsPageCollectionStatus.COMPLETE,
    complete=True,
    next_page_token=None,
) -> HistoricalBarsPageCollectionResult:
    return HistoricalBarsPageCollectionResult(
        request=HistoricalBarsPageCollectionRequest(
            symbols=("RVOL",),
            initial_query=query(),
            max_pages=5,
        ),
        collected_pages=tuple(
            HistoricalBarsCollectedPage(
                index=index,
                query=query(page_token=f"p{index}"),
                page=page,
            )
            for index, page in enumerate(pages)
        ),
        status=status,
        page_collection_complete=complete,
        next_page_token=next_page_token,
    )


def complete_collection() -> HistoricalBarsPageCollectionResult:
    first_page_bars = [historical_bar(2, 31, 25)]
    second_page_bars = [historical_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page_bars.append(historical_bar(day, 35, 100))
    for day in range(12, 22):
        second_page_bars.append(historical_bar(day, 35, 100))
    return collection_from_pages([page_for(first_page_bars), page_for(second_page_bars)])


def incomplete_collection() -> HistoricalBarsPageCollectionResult:
    return collection_from_pages(
        [page_for((historical_bar(2, 35, 100),), next_page_token="NEXT")],
        status=HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED,
        complete=False,
        next_page_token="NEXT",
    )


def current_series(*, volume=200) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol="RVOL",
        session_id="CURRENT-001",
        bucket="09:35",
        cutoff_timestamp=ts(31, 9, 35),
        bars=(IntradayVolumeBar(ts(31, 9, 35), volume),),
    )


def load_result_for(source, request, records, *, status=HistoricalSessionMetadataSourceLoadStatus.LOADED):
    return HistoricalSessionMetadataSourceLoadResult(
        source=source,
        request=request,
        raw_manifest_records=records,
        status=status,
        reason=None if status == HistoricalSessionMetadataSourceLoadStatus.LOADED else status,
    )


def bridge_result(status=CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN):
    return CollectedPagesToManifestWorkflowResult(
        source_collection=complete_collection(),
        composition_result=None,  # type: ignore[arg-type]
        workflow_result=None,
        status=status,
        reason=None if status == CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN else status,
    )


class LocalInvalidSource:
    def __init__(self, value) -> None:
        self.value = value

    def load_raw_manifest_records(self, request):
        return self.value


def test_call_order_identity_forwarding_and_artifact_retention(monkeypatch) -> None:
    calls = []
    records = valid_raw_records(1)
    source = StaticHistoricalSessionMetadataSource(records)
    collection = complete_collection()
    manifest_req = manifest_request()
    series = current_series()
    harness_req = harness_request()
    load_artifact = load_result_for(source, manifest_req, records)
    bridge_artifact = bridge_result()

    def fake_loader(source_arg, request_arg):
        calls.append("load")
        assert source_arg is source
        assert request_arg is manifest_req
        return load_artifact

    def fake_bridge(collection_arg, records_arg, request_arg, series_arg, harness_arg):
        calls.append("bridge")
        assert collection_arg is collection
        assert records_arg is records
        assert request_arg is manifest_req
        assert series_arg is series
        assert harness_arg is harness_req
        return bridge_artifact

    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "load_historical_session_metadata_source",
        fake_loader,
    )
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "run_collected_pages_to_manifest_workflow",
        fake_bridge,
    )

    result = run_metadata_loaded_historical_workflow(
        source,
        collection,
        manifest_req,
        series,
        harness_req,
    )

    assert calls == ["load", "bridge"]
    assert result.metadata_source is source
    assert result.source_collection is collection
    assert result.metadata_load_result is load_artifact
    assert result.workflow_bridge_result is bridge_artifact
    assert result.status == MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    assert result.reason is None


@pytest.mark.parametrize(
    "bridge_status",
    [
        CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN,
        CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE,
    ],
)
def test_loaded_status_always_maps_to_workflow_bridge_ran(monkeypatch, bridge_status) -> None:
    records = valid_raw_records(1)
    source = StaticHistoricalSessionMetadataSource(records)
    request = manifest_request()
    load_artifact = load_result_for(source, request, records)
    bridge_artifact = bridge_result(bridge_status)
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "load_historical_session_metadata_source",
        lambda source_arg, request_arg: load_artifact,
    )
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "run_collected_pages_to_manifest_workflow",
        lambda *args: bridge_artifact,
    )

    result = run_metadata_loaded_historical_workflow(
        source,
        complete_collection(),
        request,
        current_series(),
        harness_request(),
    )

    assert result.status == MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    assert result.reason is None
    assert result.workflow_bridge_result is bridge_artifact
    assert result.workflow_bridge_result.status == bridge_status


@pytest.mark.parametrize(
    "load_status",
    [
        HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE,
        "FUTURE_NON_LOADED_STATUS",
    ],
)
def test_non_loaded_status_skips_bridge(monkeypatch, load_status) -> None:
    bridge_calls = []
    source = StaticHistoricalSessionMetadataSource(())
    request = manifest_request()
    load_artifact = load_result_for(source, request, None, status=load_status)
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "load_historical_session_metadata_source",
        lambda source_arg, request_arg: load_artifact,
    )
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "run_collected_pages_to_manifest_workflow",
        lambda *args: bridge_calls.append(args) or bridge_result(),
    )

    result = run_metadata_loaded_historical_workflow(
        source,
        complete_collection(),
        request,
        current_series(),
        harness_request(),
    )

    assert bridge_calls == []
    assert result.metadata_source is source
    assert result.metadata_load_result is load_artifact
    assert result.workflow_bridge_result is None
    assert result.status == MetadataLoadedHistoricalWorkflowStatus.METADATA_NOT_LOADED
    assert result.reason == f"METADATA_NOT_LOADED:{load_status}"


def test_loader_runs_once_for_non_loaded_invocation(monkeypatch) -> None:
    loader_calls = []
    source = StaticHistoricalSessionMetadataSource(())
    request = manifest_request()
    load_artifact = load_result_for(
        source,
        request,
        None,
        status=HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE,
    )
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "load_historical_session_metadata_source",
        lambda source_arg, request_arg: loader_calls.append((source_arg, request_arg))
        or load_artifact,
    )
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "run_collected_pages_to_manifest_workflow",
        lambda *args: pytest.fail("bridge should not run"),
    )

    run_metadata_loaded_historical_workflow(
        source,
        complete_collection(),
        request,
        current_series(),
        harness_request(),
    )

    assert loader_calls == [(source, request)]


def test_loaded_without_records_raises_runtime_error_without_bridge(monkeypatch) -> None:
    bridge_calls = []
    source = StaticHistoricalSessionMetadataSource(())
    request = manifest_request()
    load_artifact = load_result_for(source, request, None)
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "load_historical_session_metadata_source",
        lambda source_arg, request_arg: load_artifact,
    )
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "run_collected_pages_to_manifest_workflow",
        lambda *args: bridge_calls.append(args) or bridge_result(),
    )

    with pytest.raises(RuntimeError):
        run_metadata_loaded_historical_workflow(
            source,
            complete_collection(),
            request,
            current_series(),
            harness_request(),
        )

    assert bridge_calls == []


@pytest.mark.parametrize("error", [ValueError("load failed"), RuntimeError("custom")])
def test_loader_exception_propagates_unchanged_without_bridge(monkeypatch, error) -> None:
    bridge_calls = []
    source = StaticHistoricalSessionMetadataSource(())
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "load_historical_session_metadata_source",
        lambda *args: (_ for _ in ()).throw(error),
    )
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "run_collected_pages_to_manifest_workflow",
        lambda *args: bridge_calls.append(args) or bridge_result(),
    )

    with pytest.raises(type(error)) as exc_info:
        run_metadata_loaded_historical_workflow(
            source,
            complete_collection(),
            manifest_request(),
            current_series(),
            harness_request(),
        )

    assert exc_info.value is error
    assert bridge_calls == []


def test_result_is_frozen_and_repeated_calls_have_no_shared_state(monkeypatch) -> None:
    source = StaticHistoricalSessionMetadataSource(valid_raw_records(1))
    request = manifest_request()
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "load_historical_session_metadata_source",
        lambda source_arg, request_arg: load_result_for(
            source_arg,
            request_arg,
            source_arg.raw_manifest_records,
        ),
    )
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "run_collected_pages_to_manifest_workflow",
        lambda *args: bridge_result(),
    )

    first = run_metadata_loaded_historical_workflow(
        source,
        complete_collection(),
        request,
        current_series(),
        harness_request(),
    )
    second = run_metadata_loaded_historical_workflow(
        source,
        complete_collection(),
        request,
        current_series(),
        harness_request(),
    )

    assert first is not second
    assert first.metadata_load_result is not second.metadata_load_result
    assert first.workflow_bridge_result is not second.workflow_bridge_result
    with pytest.raises(FrozenInstanceError):
        first.status = "changed"  # type: ignore[misc]


def test_real_fully_valid_path_runs_bridge_and_returns_final_rvol() -> None:
    source = StaticHistoricalSessionMetadataSource(valid_raw_records(20))

    result = run_metadata_loaded_historical_workflow(
        source,
        complete_collection(),
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert result.metadata_load_result.status == HistoricalSessionMetadataSourceLoadStatus.LOADED
    assert result.status == MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    assert result.workflow_bridge_result is not None
    assert result.workflow_bridge_result.status == (
        CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    )
    assert result.workflow_bridge_result.workflow_result is not None
    assert result.workflow_bridge_result.workflow_result.status == ManifestToHarnessStatus.OK
    assert result.workflow_bridge_result.workflow_result.harness_result.final_result.time_of_day_result is not None
    assert (
        result.workflow_bridge_result.workflow_result.harness_result.final_result.time_of_day_result.relative_volume
        == 2.0
    )
    assert (
        result.workflow_bridge_result.workflow_result.harness_result.assembly_results[0].in_window_raw_bar_count
        == 2
    )


def test_real_invalid_source_container_does_not_run_bridge(monkeypatch) -> None:
    bridge_calls = []
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "run_collected_pages_to_manifest_workflow",
        lambda *args: bridge_calls.append(args) or bridge_result(),
    )
    source = LocalInvalidSource({"not": "a valid sequence"})

    result = run_metadata_loaded_historical_workflow(
        source,
        complete_collection(),
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert bridge_calls == []
    assert result.metadata_load_result.status == (
        HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE
    )
    assert result.status == MetadataLoadedHistoricalWorkflowStatus.METADATA_NOT_LOADED
    assert result.workflow_bridge_result is None


def test_real_invalid_generator_source_container_does_not_run_bridge(monkeypatch) -> None:
    bridge_calls = []
    monkeypatch.setattr(
        metadata_loaded_historical_workflow,
        "run_collected_pages_to_manifest_workflow",
        lambda *args: bridge_calls.append(args) or bridge_result(),
    )
    source = LocalInvalidSource((item for item in valid_raw_records(1)))

    result = run_metadata_loaded_historical_workflow(
        source,
        complete_collection(),
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert bridge_calls == []
    assert result.metadata_load_result.status == (
        HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE
    )
    assert result.status == MetadataLoadedHistoricalWorkflowStatus.METADATA_NOT_LOADED
    assert result.workflow_bridge_result is None


def test_real_loaded_source_with_incomplete_collection_preserves_15c_diagnostic() -> None:
    source = StaticHistoricalSessionMetadataSource(valid_raw_records(20))

    result = run_metadata_loaded_historical_workflow(
        source,
        incomplete_collection(),
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert result.metadata_load_result.status == HistoricalSessionMetadataSourceLoadStatus.LOADED
    assert result.status == MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    assert result.workflow_bridge_result is not None
    assert result.workflow_bridge_result.status == (
        CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE
    )
    assert result.workflow_bridge_result.workflow_result is None


def test_real_loaded_source_with_partial_manifest_preserves_lower_status_and_rvol() -> None:
    records = list(valid_raw_records(20))
    invalid = raw_record("BAD", day=30)
    del invalid["bucket"]
    records.append(invalid)
    source = StaticHistoricalSessionMetadataSource(tuple(records))

    result = run_metadata_loaded_historical_workflow(
        source,
        complete_collection(),
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert result.status == MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    assert result.workflow_bridge_result is not None
    assert result.workflow_bridge_result.status == (
        CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    )
    assert result.workflow_bridge_result.workflow_result is not None
    assert result.workflow_bridge_result.workflow_result.status == (
        ManifestToHarnessStatus.MANIFEST_PARTIAL
    )
    assert result.workflow_bridge_result.workflow_result.harness_result.final_result.time_of_day_result is not None
    assert (
        result.workflow_bridge_result.workflow_result.harness_result.final_result.time_of_day_result.relative_volume
        == 2.0
    )


def test_real_loaded_source_with_workflow_failure_retains_current_failure() -> None:
    source = StaticHistoricalSessionMetadataSource(valid_raw_records(20))

    result = run_metadata_loaded_historical_workflow(
        source,
        complete_collection(),
        manifest_request(),
        current_series(volume=False),
        harness_request(),
    )

    assert result.status == MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    assert result.workflow_bridge_result is not None
    assert result.workflow_bridge_result.status == (
        CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    )
    assert result.workflow_bridge_result.workflow_result is not None
    assert result.workflow_bridge_result.workflow_result.status == (
        ManifestToHarnessStatus.HARNESS_FAILED
    )
    harness_result = result.workflow_bridge_result.workflow_result.harness_result
    assert harness_result.status == HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
    assert harness_result.final_result.status == (
        CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
    )
    assert harness_result.final_result.current_result is not None
    assert harness_result.final_result.current_result.status == (
        IntradayBucketStatus.INVALID_INTRADAY_VOLUME
    )


def test_source_boundary_uses_only_approved_interfaces() -> None:
    source = inspect.getsource(metadata_loaded_historical_workflow)
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
        "dataclasses",
        "market_sentry.data.collected_pages_to_manifest_workflow",
        "market_sentry.data.historical_bars_page_collector",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.historical_session_metadata_source",
        "market_sentry.data.historical_tod_rvol_harness",
        "market_sentry.data.intraday_bucket_adapter",
    }

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert imported_names == {
        "annotations",
        "dataclass",
        "CollectedPagesToManifestWorkflowResult",
        "run_collected_pages_to_manifest_workflow",
        "HistoricalBarsPageCollectionResult",
        "HistoricalSessionManifestRequest",
        "HistoricalSessionMetadataSource",
        "HistoricalSessionMetadataSourceLoadResult",
        "HistoricalSessionMetadataSourceLoadStatus",
        "load_historical_session_metadata_source",
        "HistoricalToTodRvolRunRequest",
        "IntradayVolumeSeriesInput",
    }

    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    assert "load_historical_session_metadata_source" in called_names
    assert "run_collected_pages_to_manifest_workflow" in called_names
    forbidden_calls = {
        "load_raw_manifest_records",
        "adapt_historical_session_manifest",
        "compose_collected_historical_pages",
        "run_manifest_to_historical_tod_rvol",
        "fetch_bars",
        "AlpacaHistoricalBarsPage",
        "dict",
        "tuple",
        "list",
        "sorted",
    }
    assert not forbidden_calls & called_names

    attribute_names = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "bars_by_symbol" not in attribute_names
    assert "requested_symbols" not in attribute_names
    assert "symbol" not in attribute_names
    assert "bucket" not in attribute_names
    assert "current_session_id" not in attribute_names
