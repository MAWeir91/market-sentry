import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from market_sentry.data import historical_session_metadata_source
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.collected_pages_to_manifest_workflow import (
    CollectedPagesToManifestWorkflowStatus,
    run_collected_pages_to_manifest_workflow,
)
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsCollectedPage,
    HistoricalBarsPageCollectionRequest,
    HistoricalBarsPageCollectionResult,
    HistoricalBarsPageCollectionStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
    HistoricalSessionManifestStatus,
    adapt_historical_session_manifest,
)
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSource,
    HistoricalSessionMetadataSourceLoadStatus,
    StaticHistoricalSessionMetadataSource,
    load_historical_session_metadata_source,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.manifest_to_harness_orchestrator import ManifestToHarnessStatus


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


def page_for(bars) -> AlpacaHistoricalBarsPage:
    return AlpacaHistoricalBarsPage(
        requested_symbols=("RVOL",),
        bars_by_symbol={"RVOL": tuple(bars)},
        next_page_token=None,
    )


def complete_collection() -> HistoricalBarsPageCollectionResult:
    first_page_bars = [historical_bar(2, 31, 25)]
    second_page_bars = [historical_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page_bars.append(historical_bar(day, 35, 100))
    for day in range(12, 22):
        second_page_bars.append(historical_bar(day, 35, 100))

    pages = (page_for(first_page_bars), page_for(second_page_bars))
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
        status=HistoricalBarsPageCollectionStatus.COMPLETE,
        page_collection_complete=True,
        next_page_token=None,
    )


def current_series(*, volume=200) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol="RVOL",
        session_id="CURRENT-001",
        bucket="09:35",
        cutoff_timestamp=ts(31, 9, 35),
        bars=(IntradayVolumeBar(ts(31, 9, 35), volume),),
    )


class RecordingSource:
    def __init__(self, raw_manifest_records) -> None:
        self.raw_manifest_records = raw_manifest_records
        self.calls = []

    def load_raw_manifest_records(self, request):
        self.calls.append(request)
        return self.raw_manifest_records


class RaisingSource:
    def __init__(self, error: BaseException) -> None:
        self.error = error
        self.calls = []

    def load_raw_manifest_records(self, request):
        self.calls.append(request)
        raise self.error


def test_static_source_returns_exact_tuple_by_identity() -> None:
    records = valid_raw_records(1)
    source = StaticHistoricalSessionMetadataSource(records)
    request = manifest_request()

    loaded = source.load_raw_manifest_records(request)

    assert isinstance(source, HistoricalSessionMetadataSource)
    assert loaded is records


def test_static_source_returns_exact_list_by_identity() -> None:
    records = list(valid_raw_records(1))
    source = StaticHistoricalSessionMetadataSource(records)

    loaded = source.load_raw_manifest_records(manifest_request())

    assert loaded is records


def test_static_source_does_not_inspect_request_fields() -> None:
    records = valid_raw_records(1)
    source = StaticHistoricalSessionMetadataSource(records)
    request = object.__new__(HistoricalSessionManifestRequest)

    assert source.load_raw_manifest_records(request) is records


def test_static_source_is_frozen_and_malformed_records_pass_through_unchanged() -> None:
    malformed = {"unexpected": object(), "is_complete": False, "source_reason": "halt"}
    records = (malformed, {"mixed": ["not", "validated"]})
    source = StaticHistoricalSessionMetadataSource(records)

    assert source.load_raw_manifest_records(manifest_request()) is records
    assert source.raw_manifest_records[0] is malformed
    with pytest.raises(FrozenInstanceError):
        source.raw_manifest_records = ()  # type: ignore[misc]


@pytest.mark.parametrize("records", [valid_raw_records(1), list(valid_raw_records(1))])
def test_loader_retains_valid_sequence_by_identity(records) -> None:
    source = RecordingSource(records)
    request = manifest_request()

    result = load_historical_session_metadata_source(source, request)

    assert source.calls == [request]
    assert result.source is source
    assert result.request is request
    assert result.raw_manifest_records is records
    assert result.status == HistoricalSessionMetadataSourceLoadStatus.LOADED
    assert result.reason is None


@pytest.mark.parametrize("records", [(), []])
def test_empty_tuple_or_list_returns_loaded(records) -> None:
    source = RecordingSource(records)

    result = load_historical_session_metadata_source(source, manifest_request())

    assert result.raw_manifest_records is records
    assert result.status == HistoricalSessionMetadataSourceLoadStatus.LOADED


def test_loader_result_is_frozen_and_separate_calls_create_distinct_results() -> None:
    records = valid_raw_records(1)
    source = RecordingSource(records)
    request = manifest_request()

    first = load_historical_session_metadata_source(source, request)
    second = load_historical_session_metadata_source(source, request)

    assert first is not second
    assert first.source is second.source
    assert first.request is second.request
    assert first.raw_manifest_records is second.raw_manifest_records
    assert source.calls == [request, request]
    with pytest.raises(FrozenInstanceError):
        first.status = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "invalid_records",
    [
        None,
        (item for item in (1, 2)),
        {"record": "mapping"},
        123,
        "records",
        b"records",
        bytearray(b"records"),
        memoryview(b"records"),
    ],
)
def test_loader_rejects_invalid_return_containers(invalid_records) -> None:
    source = RecordingSource(invalid_records)
    request = manifest_request()

    result = load_historical_session_metadata_source(source, request)

    assert source.calls == [request]
    assert result.source is source
    assert result.request is request
    assert result.raw_manifest_records is None
    assert result.status == HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE
    assert result.reason == HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE


def test_loader_propagates_value_error_unchanged_after_one_source_call() -> None:
    error = ValueError("source failed")
    source = RaisingSource(error)
    request = manifest_request()

    with pytest.raises(ValueError) as exc_info:
        load_historical_session_metadata_source(source, request)

    assert exc_info.value is error
    assert source.calls == [request]


def test_loader_propagates_custom_exception_unchanged_after_one_source_call() -> None:
    class CustomSourceError(Exception):
        pass

    error = CustomSourceError("custom")
    source = RaisingSource(error)
    request = manifest_request()

    with pytest.raises(CustomSourceError) as exc_info:
        load_historical_session_metadata_source(source, request)

    assert exc_info.value is error
    assert source.calls == [request]


def test_loaded_static_source_records_can_feed_phase_14i_manifest_adapter() -> None:
    records = valid_raw_records(20)
    request = manifest_request()
    source = StaticHistoricalSessionMetadataSource(records)

    load_result = load_historical_session_metadata_source(source, request)
    manifest_result = adapt_historical_session_manifest(
        load_result.raw_manifest_records,
        request,
    )

    assert load_result.status == HistoricalSessionMetadataSourceLoadStatus.LOADED
    assert load_result.raw_manifest_records is records
    assert manifest_result.status == HistoricalSessionManifestStatus.OK
    assert manifest_result.valid_record_count == 20
    assert len(manifest_result.metadata_records) == 20


def test_loaded_static_source_records_can_feed_phase_15c_workflow() -> None:
    records = valid_raw_records(20)
    request = manifest_request()
    source = StaticHistoricalSessionMetadataSource(records)

    load_result = load_historical_session_metadata_source(source, request)
    workflow_result = run_collected_pages_to_manifest_workflow(
        complete_collection(),
        load_result.raw_manifest_records,
        request,
        current_series(volume=200),
        harness_request(),
    )

    assert load_result.status == HistoricalSessionMetadataSourceLoadStatus.LOADED
    assert load_result.raw_manifest_records is records
    assert workflow_result.status == CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    assert workflow_result.workflow_result is not None
    assert workflow_result.workflow_result.status == ManifestToHarnessStatus.OK
    assert workflow_result.workflow_result.harness_result.final_result.time_of_day_result is not None
    assert (
        workflow_result.workflow_result.harness_result.final_result.time_of_day_result.relative_volume
        == 2.0
    )


def test_source_boundary_uses_only_approved_imports_and_behavior() -> None:
    source = inspect.getsource(historical_session_metadata_source)
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
        "typing",
        "market_sentry.data.historical_session_manifest",
    }

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert imported_names == {
        "annotations",
        "Sequence",
        "dataclass",
        "Protocol",
        "runtime_checkable",
        "HistoricalSessionManifestRequest",
    }

    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    assert "load_raw_manifest_records" in called_names
    forbidden_calls = {
        "adapt_historical_session_manifest",
        "run_collected_pages_to_manifest_workflow",
        "run_manifest_to_historical_tod_rvol",
        "fetch_bars",
        "keys",
        "values",
        "items",
        "get",
        "dict",
        "tuple",
        "list",
    }
    assert not forbidden_calls & called_names

    attribute_names = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "symbol" not in attribute_names
    assert "bucket" not in attribute_names
    assert "current_session_id" not in attribute_names
