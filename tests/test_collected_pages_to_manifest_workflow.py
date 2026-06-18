import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from market_sentry.data import collected_pages_to_manifest_workflow
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionResult,
    CollectedHistoricalPagesCompositionStatus,
)
from market_sentry.data.collected_pages_to_manifest_workflow import (
    CollectedPagesToManifestWorkflowStatus,
    run_collected_pages_to_manifest_workflow,
)
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolResult,
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_baseline_composition import (
    HistoricalBaselineCompositionRequest,
    HistoricalBaselineCompositionResult,
    HistoricalBaselineCompositionStatus,
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
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
    HistoricalToTodRvolRunResult,
    HistoricalToTodRvolRunStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayBucketStatus,
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessResult,
    ManifestToHarnessStatus,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeResult


UTC = timezone.utc


def ts(day: int = 2, hour: int = 9, minute: int = 35) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def query(**overrides) -> AlpacaHistoricalBarsQuery:
    values = {
        "timeframe": "1Min",
        "start": "2026-01-02T09:30:00Z",
        "end": "2026-01-21T10:00:00Z",
    }
    values.update(overrides)
    return AlpacaHistoricalBarsQuery(**values)


def page_for(bars, *, next_page_token=None) -> AlpacaHistoricalBarsPage:
    return AlpacaHistoricalBarsPage(
        requested_symbols=("RVOL",),
        bars_by_symbol={"RVOL": tuple(bars)},
        next_page_token=next_page_token,
    )


def collection_request() -> HistoricalBarsPageCollectionRequest:
    return HistoricalBarsPageCollectionRequest(
        symbols=("RVOL",),
        initial_query=query(),
        max_pages=5,
    )


def collected_page(index: int, page: AlpacaHistoricalBarsPage) -> HistoricalBarsCollectedPage:
    return HistoricalBarsCollectedPage(index=index, query=query(page_token=f"p{index}"), page=page)


def collection_for(
    pages,
    *,
    status=HistoricalBarsPageCollectionStatus.COMPLETE,
    complete=True,
    next_page_token=None,
) -> HistoricalBarsPageCollectionResult:
    return HistoricalBarsPageCollectionResult(
        request=collection_request(),
        collected_pages=tuple(
            collected_page(index, page) for index, page in enumerate(pages)
        ),
        status=status,
        page_collection_complete=complete,
        next_page_token=next_page_token,
    )


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
    return [
        raw_record(f"HIST-{index:02d}", day=index + 1)
        for index in range(1, count + 1)
    ]


def historical_bar(day: int, minute: int, volume) -> dict[str, object]:
    return {
        "t": f"2026-01-{day:02d}T09:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "h": 1.0,
        "l": 1.0,
        "c": 1.0,
    }


def split_complete_collection() -> HistoricalBarsPageCollectionResult:
    first_page_bars = [historical_bar(2, 31, 25)]
    second_page_bars = [historical_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page_bars.append(historical_bar(day, 35, 100))
    for day in range(12, 22):
        second_page_bars.append(historical_bar(day, 35, 100))

    return collection_for(
        [
            page_for(first_page_bars),
            page_for(second_page_bars),
        ]
    )


def incomplete_collection() -> HistoricalBarsPageCollectionResult:
    return collection_for(
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


def harness_artifact(status: str = HistoricalToTodRvolRunStatus.OK) -> HistoricalToTodRvolRunResult:
    return HistoricalToTodRvolRunResult(
        request=harness_request(),
        baseline_request=HistoricalBaselineCompositionRequest(
            symbol="RVOL",
            bucket="09:35",
            current_session_id="CURRENT-001",
        ),
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


def workflow_artifact(status: str = ManifestToHarnessStatus.OK) -> ManifestToHarnessResult:
    manifest_status = HistoricalSessionManifestStatus.OK
    harness_status = HistoricalToTodRvolRunStatus.OK
    reason = None
    if status == ManifestToHarnessStatus.MANIFEST_PARTIAL:
        manifest_status = HistoricalSessionManifestStatus.PARTIAL
        reason = ManifestToHarnessStatus.MANIFEST_PARTIAL
    elif status == ManifestToHarnessStatus.MANIFEST_FAILED:
        manifest_status = HistoricalSessionManifestStatus.NO_VALID_METADATA
        reason = "MANIFEST_FAILED:NO_VALID_METADATA"
    elif status == ManifestToHarnessStatus.HARNESS_FAILED:
        harness_status = HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
        reason = "HARNESS_FAILED:FINAL_COMPOSITION_FAILED"

    from market_sentry.data.historical_session_manifest import HistoricalSessionManifestResult

    return ManifestToHarnessResult(
        manifest_result=HistoricalSessionManifestResult(
            request=manifest_request(),
            record_results=(),
            metadata_records=(),
            valid_record_count=0,
            status=manifest_status,
            reason=None if manifest_status == HistoricalSessionManifestStatus.OK else manifest_status,
        ),
        harness_result=harness_artifact(harness_status),
        status=status,
        reason=reason,
    )


def composition_artifact(
    collection: HistoricalBarsPageCollectionResult,
    *,
    status=CollectedHistoricalPagesCompositionStatus.COMPOSED,
    page=None,
) -> CollectedHistoricalPagesCompositionResult:
    return CollectedHistoricalPagesCompositionResult(
        source_collection=collection,
        composed_page=page,
        status=status,
        reason=None if status == CollectedHistoricalPagesCompositionStatus.COMPOSED else status,
    )


def test_call_order_identity_forwarding_and_artifact_retention(monkeypatch) -> None:
    calls = []
    collection = split_complete_collection()
    raw_records = valid_raw_records(20)
    manifest_req = manifest_request()
    series = current_series()
    harness_req = harness_request()
    composed_page = page_for((historical_bar(2, 35, 100),))
    composition = composition_artifact(collection, page=composed_page)
    workflow = workflow_artifact()

    def fake_compose(collection_arg):
        calls.append("compose")
        assert collection_arg is collection
        return composition

    def fake_workflow(raw_arg, manifest_arg, page_arg, series_arg, harness_arg):
        calls.append("workflow")
        assert raw_arg is raw_records
        assert manifest_arg is manifest_req
        assert page_arg is composed_page
        assert series_arg is series
        assert harness_arg is harness_req
        return workflow

    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "compose_collected_historical_pages",
        fake_compose,
    )
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "run_manifest_to_historical_tod_rvol",
        fake_workflow,
    )

    result = run_collected_pages_to_manifest_workflow(
        collection,
        raw_records,
        manifest_req,
        series,
        harness_req,
    )

    assert calls == ["compose", "workflow"]
    assert result.source_collection is collection
    assert result.composition_result is composition
    assert result.workflow_result is workflow
    assert result.status == CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    assert result.reason is None


@pytest.mark.parametrize(
    "workflow_status",
    [
        ManifestToHarnessStatus.OK,
        ManifestToHarnessStatus.MANIFEST_PARTIAL,
        ManifestToHarnessStatus.MANIFEST_FAILED,
        ManifestToHarnessStatus.HARNESS_FAILED,
    ],
)
def test_composed_status_always_maps_to_workflow_ran(monkeypatch, workflow_status) -> None:
    collection = split_complete_collection()
    composition = composition_artifact(
        collection,
        page=page_for((historical_bar(2, 35, 100),)),
    )
    workflow = workflow_artifact(workflow_status)
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "compose_collected_historical_pages",
        lambda collection_arg: composition,
    )
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "run_manifest_to_historical_tod_rvol",
        lambda *args: workflow,
    )

    result = run_collected_pages_to_manifest_workflow(
        collection,
        valid_raw_records(20),
        manifest_request(),
        current_series(),
        harness_request(),
    )

    assert result.status == CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    assert result.reason is None
    assert result.workflow_result is workflow
    assert result.workflow_result.status == workflow_status


@pytest.mark.parametrize(
    "composition_status",
    [
        CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION,
        CollectedHistoricalPagesCompositionStatus.EMPTY_COMPLETE_COLLECTION,
        CollectedHistoricalPagesCompositionStatus.MISMATCHED_PAGE_REQUESTED_SYMBOLS,
        "FUTURE_NON_COMPOSED_STATUS",
    ],
)
def test_non_composed_status_skips_workflow(monkeypatch, composition_status) -> None:
    workflow_calls = []
    collection = split_complete_collection()
    composition = composition_artifact(collection, status=composition_status, page=None)
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "compose_collected_historical_pages",
        lambda collection_arg: composition,
    )
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "run_manifest_to_historical_tod_rvol",
        lambda *args: workflow_calls.append(args) or workflow_artifact(),
    )

    result = run_collected_pages_to_manifest_workflow(
        collection,
        valid_raw_records(20),
        manifest_request(),
        current_series(),
        harness_request(),
    )

    assert workflow_calls == []
    assert result.source_collection is collection
    assert result.composition_result is composition
    assert result.workflow_result is None
    assert result.status == CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE
    assert result.reason == f"COLLECTION_NOT_COMPOSABLE:{composition_status}"


def test_composition_runs_once_for_non_composed_invocation(monkeypatch) -> None:
    compose_calls = []
    collection = split_complete_collection()
    composition = composition_artifact(
        collection,
        status=CollectedHistoricalPagesCompositionStatus.EMPTY_COMPLETE_COLLECTION,
        page=None,
    )
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "compose_collected_historical_pages",
        lambda collection_arg: compose_calls.append(collection_arg) or composition,
    )
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "run_manifest_to_historical_tod_rvol",
        lambda *args: pytest.fail("workflow should not run"),
    )

    run_collected_pages_to_manifest_workflow(
        collection,
        valid_raw_records(20),
        manifest_request(),
        current_series(),
        harness_request(),
    )

    assert compose_calls == [collection]


def test_composed_without_page_raises_runtime_error_without_workflow(monkeypatch) -> None:
    workflow_calls = []
    collection = split_complete_collection()
    composition = composition_artifact(collection, page=None)
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "compose_collected_historical_pages",
        lambda collection_arg: composition,
    )
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "run_manifest_to_historical_tod_rvol",
        lambda *args: workflow_calls.append(args) or workflow_artifact(),
    )

    with pytest.raises(RuntimeError):
        run_collected_pages_to_manifest_workflow(
            collection,
            valid_raw_records(20),
            manifest_request(),
            current_series(),
            harness_request(),
        )

    assert workflow_calls == []


def test_result_is_frozen_and_repeated_calls_have_no_shared_state(monkeypatch) -> None:
    collection = split_complete_collection()
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "compose_collected_historical_pages",
        lambda collection_arg: composition_artifact(
            collection_arg,
            page=page_for((historical_bar(2, 35, 100),)),
        ),
    )
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "run_manifest_to_historical_tod_rvol",
        lambda *args: workflow_artifact(),
    )

    first = run_collected_pages_to_manifest_workflow(
        collection,
        valid_raw_records(20),
        manifest_request(),
        current_series(),
        harness_request(),
    )
    second = run_collected_pages_to_manifest_workflow(
        collection,
        valid_raw_records(20),
        manifest_request(),
        current_series(),
        harness_request(),
    )

    assert first is not second
    assert first.composition_result is not second.composition_result
    assert first.workflow_result is not second.workflow_result
    with pytest.raises(FrozenInstanceError):
        first.status = "changed"  # type: ignore[misc]


def test_real_valid_path_runs_workflow_and_returns_final_rvol() -> None:
    result = run_collected_pages_to_manifest_workflow(
        split_complete_collection(),
        valid_raw_records(20),
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert result.composition_result.status == CollectedHistoricalPagesCompositionStatus.COMPOSED
    assert result.status == CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    assert result.reason is None
    assert result.workflow_result is not None
    assert result.workflow_result.status == ManifestToHarnessStatus.OK
    assert result.workflow_result.harness_result.status == HistoricalToTodRvolRunStatus.OK
    assert result.workflow_result.harness_result.final_result.time_of_day_result is not None
    assert result.workflow_result.harness_result.final_result.time_of_day_result.relative_volume == 2.0
    assert result.workflow_result.harness_result.assembly_results[0].in_window_raw_bar_count == 2


def test_real_incomplete_collection_does_not_run_workflow(monkeypatch) -> None:
    workflow_calls = []
    monkeypatch.setattr(
        collected_pages_to_manifest_workflow,
        "run_manifest_to_historical_tod_rvol",
        lambda *args: workflow_calls.append(args) or workflow_artifact(),
    )

    result = run_collected_pages_to_manifest_workflow(
        incomplete_collection(),
        valid_raw_records(20),
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert workflow_calls == []
    assert result.composition_result.status == (
        CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION
    )
    assert result.status == CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE
    assert result.reason == "COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION"
    assert result.workflow_result is None


def test_real_partial_manifest_runs_workflow_and_preserves_partial_status() -> None:
    records = valid_raw_records(20)
    invalid = raw_record("BAD", day=30)
    del invalid["bucket"]
    records.append(invalid)

    result = run_collected_pages_to_manifest_workflow(
        split_complete_collection(),
        records,
        manifest_request(),
        current_series(volume=200),
        harness_request(),
    )

    assert result.composition_result.status == CollectedHistoricalPagesCompositionStatus.COMPOSED
    assert result.status == CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    assert result.workflow_result is not None
    assert result.workflow_result.status == ManifestToHarnessStatus.MANIFEST_PARTIAL
    assert result.workflow_result.manifest_result.status == HistoricalSessionManifestStatus.PARTIAL
    assert result.workflow_result.harness_result.final_result.time_of_day_result is not None
    assert result.workflow_result.harness_result.final_result.time_of_day_result.relative_volume == 2.0


def test_real_workflow_failure_is_retained_under_workflow_ran() -> None:
    result = run_collected_pages_to_manifest_workflow(
        split_complete_collection(),
        valid_raw_records(20),
        manifest_request(),
        current_series(volume=False),
        harness_request(),
    )

    assert result.composition_result.status == CollectedHistoricalPagesCompositionStatus.COMPOSED
    assert result.status == CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    assert result.workflow_result is not None
    assert result.workflow_result.status == ManifestToHarnessStatus.HARNESS_FAILED
    assert result.workflow_result.harness_result.status == (
        HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
    )
    assert result.workflow_result.harness_result.final_result.current_result is not None
    assert result.workflow_result.harness_result.final_result.current_result.status == (
        IntradayBucketStatus.INVALID_INTRADAY_VOLUME
    )


def test_source_boundary_uses_only_approved_interfaces() -> None:
    source = inspect.getsource(collected_pages_to_manifest_workflow)
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
        "market_sentry.data.collected_historical_pages_composer",
        "market_sentry.data.historical_bars_page_collector",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.historical_tod_rvol_harness",
        "market_sentry.data.intraday_bucket_adapter",
        "market_sentry.data.manifest_to_harness_orchestrator",
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
        "CollectedHistoricalPagesCompositionResult",
        "CollectedHistoricalPagesCompositionStatus",
        "compose_collected_historical_pages",
        "HistoricalBarsPageCollectionResult",
        "HistoricalSessionManifestRequest",
        "HistoricalToTodRvolRunRequest",
        "IntradayVolumeSeriesInput",
        "ManifestToHarnessResult",
        "run_manifest_to_historical_tod_rvol",
    }

    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    assert "compose_collected_historical_pages" in called_names
    assert "run_manifest_to_historical_tod_rvol" in called_names
    forbidden_calls = {
        "fetch_bars",
        "adapt_historical_session_manifest",
        "run_historical_to_time_of_day_rvol",
        "assemble_historical_sessions_from_page",
        "compose_historical_baseline",
        "compose_current_session_time_of_day_rvol",
        "AlpacaHistoricalBarsPage",
        "sorted",
    }
    assert not forbidden_calls & called_names

    attribute_names = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "bars_by_symbol" not in attribute_names
    assert "requested_symbols" not in attribute_names
    assert "metadata_records" not in attribute_names
