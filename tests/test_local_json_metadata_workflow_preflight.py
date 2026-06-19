import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import inspect
import json

import pytest

from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.collected_pages_to_manifest_workflow import (
    CollectedPagesToManifestWorkflowStatus,
)
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsCollectedPage,
    HistoricalBarsPageCollectionRequest,
    HistoricalBarsPageCollectionResult,
    HistoricalBarsPageCollectionStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRecordStatus,
    HistoricalSessionManifestRequest,
    HistoricalSessionManifestStatus,
)
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSourceLoadStatus,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.json_historical_session_metadata_source import (
    UNSUPPORTED_SCHEMA_VERSION,
    JsonHistoricalSessionMetadataFileSource,
    JsonHistoricalSessionMetadataFileSourceError,
)
from market_sentry.data.local_json_metadata_workflow_preflight import (
    LocalJsonMetadataWorkflowPreflightResult,
    run_local_json_metadata_workflow_preflight,
)
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessStatus,
)
from market_sentry.data.metadata_loaded_historical_workflow import (
    MetadataLoadedHistoricalWorkflowStatus,
)
from market_sentry.data import local_json_metadata_workflow_preflight as preflight_module


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
        "session_start_timestamp": {"$datetime": f"2026-01-{day:02d}T09:30:00Z"},
        "session_end_timestamp": {"$datetime": f"2026-01-{day:02d}T10:00:00Z"},
        "cutoff_timestamp": {"$datetime": f"2026-01-{day:02d}T09:35:00Z"},
        "is_complete": True,
    }


def valid_raw_records(count: int = 20) -> list[dict[str, object]]:
    return [
        raw_record(f"HIST-{index:02d}", day=index + 1)
        for index in range(1, count + 1)
    ]


def write_envelope(path, records, **extra) -> None:
    payload = {"schema_version": 1, "records": records}
    payload.update(extra)
    path.write_text(json.dumps(payload), encoding="utf-8")


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


def non_composable_collection() -> HistoricalBarsPageCollectionResult:
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


class FakeSource:
    def __init__(self, *, path) -> None:
        self.path = path


def test_constructs_source_forwards_inputs_and_retains_artifacts(monkeypatch, tmp_path) -> None:
    calls = []
    constructed_sources = []
    path = tmp_path / "metadata.json"
    collection = object()
    request = object()
    series = object()
    harness = object()
    workflow_result = object()

    def fake_source_constructor(*, path):
        calls.append("construct")
        source = FakeSource(path=path)
        constructed_sources.append(source)
        return source

    def fake_workflow(source_arg, collection_arg, request_arg, series_arg, harness_arg):
        calls.append("workflow")
        assert source_arg is constructed_sources[0]
        assert collection_arg is collection
        assert request_arg is request
        assert series_arg is series
        assert harness_arg is harness
        return workflow_result

    monkeypatch.setattr(
        preflight_module,
        "JsonHistoricalSessionMetadataFileSource",
        fake_source_constructor,
    )
    monkeypatch.setattr(
        preflight_module,
        "run_metadata_loaded_historical_workflow",
        fake_workflow,
    )

    result = preflight_module.run_local_json_metadata_workflow_preflight(
        path,
        collection,
        request,
        series,
        harness,
    )

    assert calls == ["construct", "workflow"]
    assert len(constructed_sources) == 1
    assert constructed_sources[0].path is path
    assert result.path is path
    assert result.metadata_source is constructed_sources[0]
    assert result.workflow_result is workflow_result
    with pytest.raises(FrozenInstanceError):
        result.path = tmp_path / "other.json"  # type: ignore[misc]


def test_separate_calls_create_independent_sources_results_and_wrappers(
    monkeypatch,
    tmp_path,
) -> None:
    path = tmp_path / "metadata.json"
    collection = object()
    request = object()
    series = object()
    harness = object()
    constructed_sources = []
    workflow_results = []

    def fake_source_constructor(*, path):
        source = FakeSource(path=path)
        constructed_sources.append(source)
        return source

    def fake_workflow(*args):
        result = object()
        workflow_results.append(result)
        return result

    monkeypatch.setattr(
        preflight_module,
        "JsonHistoricalSessionMetadataFileSource",
        fake_source_constructor,
    )
    monkeypatch.setattr(
        preflight_module,
        "run_metadata_loaded_historical_workflow",
        fake_workflow,
    )

    first = preflight_module.run_local_json_metadata_workflow_preflight(
        path,
        collection,
        request,
        series,
        harness,
    )
    second = preflight_module.run_local_json_metadata_workflow_preflight(
        path,
        collection,
        request,
        series,
        harness,
    )

    assert first is not second
    assert len(constructed_sources) == 2
    assert constructed_sources[0] is not constructed_sources[1]
    assert first.metadata_source is constructed_sources[0]
    assert second.metadata_source is constructed_sources[1]
    assert len(workflow_results) == 2
    assert workflow_results[0] is not workflow_results[1]
    assert first.workflow_result is workflow_results[0]
    assert second.workflow_result is workflow_results[1]


def test_source_constructor_type_error_propagates_without_workflow(monkeypatch, tmp_path) -> None:
    error = TypeError("bad path")
    workflow_calls = []

    def fake_source_constructor(*, path):
        raise error

    monkeypatch.setattr(
        preflight_module,
        "JsonHistoricalSessionMetadataFileSource",
        fake_source_constructor,
    )
    monkeypatch.setattr(
        preflight_module,
        "run_metadata_loaded_historical_workflow",
        lambda *args: workflow_calls.append(args),
    )

    with pytest.raises(TypeError) as exc_info:
        preflight_module.run_local_json_metadata_workflow_preflight(
            tmp_path / "metadata.json",
            object(),
            object(),
            object(),
            object(),
        )

    assert exc_info.value is error
    assert workflow_calls == []


@pytest.mark.parametrize("error", [ValueError("workflow failed"), RuntimeError("custom")])
def test_phase_15e_exceptions_propagate_after_source_construction(
    monkeypatch,
    tmp_path,
    error,
) -> None:
    constructed_sources = []

    def fake_source_constructor(*, path):
        source = FakeSource(path=path)
        constructed_sources.append(source)
        return source

    def fake_workflow(*args):
        raise error

    monkeypatch.setattr(
        preflight_module,
        "JsonHistoricalSessionMetadataFileSource",
        fake_source_constructor,
    )
    monkeypatch.setattr(
        preflight_module,
        "run_metadata_loaded_historical_workflow",
        fake_workflow,
    )

    with pytest.raises(type(error)) as exc_info:
        preflight_module.run_local_json_metadata_workflow_preflight(
            tmp_path / "metadata.json",
            object(),
            object(),
            object(),
            object(),
        )

    assert exc_info.value is error
    assert len(constructed_sources) == 1


def test_valid_json_preflight_reaches_final_rvol(tmp_path) -> None:
    path = tmp_path / "metadata.json"
    write_envelope(path, valid_raw_records(20))

    result = run_local_json_metadata_workflow_preflight(
        path,
        complete_collection(),
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert result.path is path
    assert isinstance(result.metadata_source, JsonHistoricalSessionMetadataFileSource)
    assert result.metadata_source.path is path
    assert result.workflow_result.metadata_load_result.status == (
        HistoricalSessionMetadataSourceLoadStatus.LOADED
    )
    assert result.workflow_result.status == (
        MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    )
    assert result.workflow_result.workflow_bridge_result is not None
    assert result.workflow_result.workflow_bridge_result.status == (
        CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    )
    workflow_result = result.workflow_result.workflow_bridge_result.workflow_result
    assert workflow_result is not None
    assert workflow_result.status == ManifestToHarnessStatus.OK
    tod_result = workflow_result.harness_result.final_result.time_of_day_result
    assert tod_result is not None
    assert tod_result.relative_volume == 2.0


def test_missing_explicit_path_file_not_found_propagates(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        run_local_json_metadata_workflow_preflight(
            tmp_path / "missing.json",
            complete_collection(),
            manifest_request(),
            current_series(),
            harness_request(),
        )


def test_invalid_envelope_error_propagates(tmp_path) -> None:
    path = tmp_path / "metadata.json"
    path.write_text(
        json.dumps({"schema_version": 2, "records": []}),
        encoding="utf-8",
    )

    with pytest.raises(JsonHistoricalSessionMetadataFileSourceError) as exc_info:
        run_local_json_metadata_workflow_preflight(
            path,
            complete_collection(),
            manifest_request(),
            current_series(),
            harness_request(),
        )

    assert str(exc_info.value) == UNSUPPORTED_SCHEMA_VERSION


def test_record_level_failure_remains_downstream(tmp_path) -> None:
    path = tmp_path / "metadata.json"
    records = valid_raw_records(20)
    records[0] = dict(records[0])
    records[0]["cutoff_timestamp"] = {"$datetime": "not-a-datetime"}
    write_envelope(path, records)

    result = run_local_json_metadata_workflow_preflight(
        path,
        complete_collection(),
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert result.workflow_result.metadata_load_result.status == (
        HistoricalSessionMetadataSourceLoadStatus.LOADED
    )
    assert result.workflow_result.status == (
        MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    )
    assert result.workflow_result.workflow_bridge_result is not None
    workflow_result = result.workflow_result.workflow_bridge_result.workflow_result
    assert workflow_result is not None
    assert workflow_result.manifest_result.status == HistoricalSessionManifestStatus.PARTIAL
    assert workflow_result.manifest_result.record_results[0].status == (
        HistoricalSessionManifestRecordStatus.INVALID_CUTOFF_TIMESTAMP
    )


def test_non_composable_collection_remains_downstream(tmp_path) -> None:
    path = tmp_path / "metadata.json"
    write_envelope(path, valid_raw_records(20))

    result = run_local_json_metadata_workflow_preflight(
        path,
        non_composable_collection(),
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert result.workflow_result.metadata_load_result.status == (
        HistoricalSessionMetadataSourceLoadStatus.LOADED
    )
    assert result.workflow_result.status == (
        MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    )
    assert result.workflow_result.workflow_bridge_result is not None
    assert result.workflow_result.workflow_bridge_result.status == (
        CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE
    )
    assert result.workflow_result.workflow_bridge_result.workflow_result is None


def test_source_boundary_uses_only_approved_interfaces() -> None:
    source = inspect.getsource(preflight_module)
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
        "pathlib",
        "market_sentry.data.historical_bars_page_collector",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.historical_tod_rvol_harness",
        "market_sentry.data.intraday_bucket_adapter",
        "market_sentry.data.json_historical_session_metadata_source",
        "market_sentry.data.metadata_loaded_historical_workflow",
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
        "Path",
        "HistoricalBarsPageCollectionResult",
        "HistoricalSessionManifestRequest",
        "HistoricalToTodRvolRunRequest",
        "IntradayVolumeSeriesInput",
        "JsonHistoricalSessionMetadataFileSource",
        "MetadataLoadedHistoricalWorkflowResult",
        "run_metadata_loaded_historical_workflow",
    }

    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    assert called_names == {
        "dataclass",
        "JsonHistoricalSessionMetadataFileSource",
        "run_metadata_loaded_historical_workflow",
        "LocalJsonMetadataWorkflowPreflightResult",
    }

    attribute_names = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert attribute_names == set()

    forbidden_terms = [
        "json.loads",
        "JsonHistoricalSessionMetadataFileSourceError",
        "load_historical_session_metadata_source",
        "StaticHistoricalSessionMetadataSource",
        "adapt_historical_session_manifest",
        "compose_collected_historical_pages",
        "run_collected_pages_to_manifest_workflow",
        "run_manifest_to_historical_tod_rvol",
        "relative_volume",
        "provider",
        "runtime",
        "http",
        "transport",
        "config",
        "scanner",
        "alerts",
        "voice",
        "candidate",
        "trading",
        "load_raw_manifest_records",
        "schema_version",
        "records",
        "bars_by_symbol",
        "collected_pages",
        "metadata_records",
        "status",
        "reason",
        "cache",
        "registry",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
