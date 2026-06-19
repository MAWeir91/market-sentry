from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionStatus,
)
from market_sentry.data.collected_pages_to_manifest_workflow import (
    CollectedPagesToManifestWorkflowStatus,
)
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
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
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSource,
    HistoricalSessionMetadataSourceLoadStatus,
    StaticHistoricalSessionMetadataSource,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
    HistoricalToTodRvolRunStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessStatus,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeStatus


SYMBOL = "RVOL"
BUCKET = "09:35"
CURRENT_SESSION_ID = "CURRENT-001"


@dataclass(frozen=True)
class MetadataLoadedHistoricalWorkflowScenario:
    name: str
    metadata_source: HistoricalSessionMetadataSource
    collection: HistoricalBarsPageCollectionResult
    manifest_request: HistoricalSessionManifestRequest
    current_series: IntradayVolumeSeriesInput
    harness_request: HistoricalToTodRvolRunRequest
    expected_metadata_load_status: str
    expected_workflow_status: str
    expected_workflow_reason: str | None
    expected_bridge_status: str | None
    expected_bridge_reason: str | None
    expected_composition_status: str | None
    expected_coordinator_status: str | None
    expected_manifest_status: str | None
    expected_harness_status: str | None
    expected_final_status: str | None
    expected_time_of_day_status: str | None
    expected_relative_volume: float | None


@dataclass(frozen=True)
class MappingMetadataSource:
    records_by_name: dict[str, object]

    def load_raw_manifest_records(self, request: HistoricalSessionManifestRequest):
        return self.records_by_name


@dataclass(frozen=True)
class GeneratorMetadataSource:
    records: tuple[object, ...]

    def load_raw_manifest_records(self, request: HistoricalSessionManifestRequest):
        return (record for record in self.records)


def _ts(day: int, hour: int = 9, minute: int = 35) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=timezone.utc)


def _query() -> AlpacaHistoricalBarsQuery:
    return AlpacaHistoricalBarsQuery(
        timeframe="1Min",
        start="2026-01-02T09:30:00Z",
        end="2026-01-21T10:00:00Z",
    )


def _raw_record(session_id: str, *, day: int, is_complete: bool = True) -> dict[str, object]:
    return {
        "symbol": SYMBOL,
        "session_id": session_id,
        "bucket": BUCKET,
        "session_start_timestamp": _ts(day, 9, 30),
        "session_end_timestamp": _ts(day, 10, 0),
        "cutoff_timestamp": _ts(day, 9, 35),
        "is_complete": is_complete,
    }


def _valid_raw_records(count: int = 20) -> tuple[dict[str, object], ...]:
    return tuple(
        _raw_record(f"HIST-{index:02d}", day=index + 1)
        for index in range(1, count + 1)
    )


def _historical_bar(day: int, minute: int, volume: int) -> dict[str, object]:
    return {
        "t": f"2026-01-{day:02d}T09:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "h": 1.0,
        "l": 1.0,
        "c": 1.0,
    }


def _page(
    requested_symbols: tuple[str, ...],
    bars_by_symbol: dict[str, tuple[dict[str, object], ...]],
    *,
    next_page_token: str | None = None,
) -> AlpacaHistoricalBarsPage:
    return AlpacaHistoricalBarsPage(
        requested_symbols=requested_symbols,
        bars_by_symbol=bars_by_symbol,
        next_page_token=next_page_token,
    )


def _valid_pages() -> tuple[AlpacaHistoricalBarsPage, AlpacaHistoricalBarsPage]:
    first_page_bars = [_historical_bar(2, 31, 25)]
    second_page_bars = [_historical_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page_bars.append(_historical_bar(day, 35, 100))
    for day in range(12, 22):
        second_page_bars.append(_historical_bar(day, 35, 100))

    return (
        _page((SYMBOL,), {SYMBOL: tuple(first_page_bars)}),
        _page((SYMBOL,), {SYMBOL: tuple(second_page_bars)}),
    )


def _collection(
    pages: tuple[AlpacaHistoricalBarsPage, ...],
    *,
    status: str = HistoricalBarsPageCollectionStatus.COMPLETE,
    complete: bool = True,
    next_page_token: str | None = None,
) -> HistoricalBarsPageCollectionResult:
    return HistoricalBarsPageCollectionResult(
        request=HistoricalBarsPageCollectionRequest(
            symbols=(SYMBOL,),
            initial_query=_query(),
            max_pages=5,
        ),
        collected_pages=tuple(
            HistoricalBarsCollectedPage(
                index=index,
                query=_query(),
                page=page,
            )
            for index, page in enumerate(pages)
        ),
        status=status,
        page_collection_complete=complete,
        next_page_token=next_page_token,
    )


def _valid_collection() -> HistoricalBarsPageCollectionResult:
    return _collection(_valid_pages())


def _page_cap_collection() -> HistoricalBarsPageCollectionResult:
    return _collection(
        (_page((SYMBOL,), {SYMBOL: (_historical_bar(2, 35, 100),)}, next_page_token="NEXT"),),
        status=HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED,
        complete=False,
        next_page_token="NEXT",
    )


def _repeated_token_collection() -> HistoricalBarsPageCollectionResult:
    return _collection(
        (_page((SYMBOL,), {SYMBOL: (_historical_bar(2, 35, 100),)}, next_page_token="LOOP"),),
        status=HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN,
        complete=False,
        next_page_token="LOOP",
    )


def _empty_complete_collection() -> HistoricalBarsPageCollectionResult:
    return _collection(())


def _mismatched_page_collection() -> HistoricalBarsPageCollectionResult:
    return _collection(
        (
            _page((SYMBOL,), {SYMBOL: (_historical_bar(2, 35, 100),)}),
            _page(("OTHER", SYMBOL), {"OTHER": (), SYMBOL: (_historical_bar(3, 35, 100),)}),
        )
    )


def _manifest_request(*, symbol: str = SYMBOL) -> HistoricalSessionManifestRequest:
    return HistoricalSessionManifestRequest(
        symbol=symbol,
        bucket=BUCKET,
        current_session_id=CURRENT_SESSION_ID,
    )


def _harness_request() -> HistoricalToTodRvolRunRequest:
    return HistoricalToTodRvolRunRequest(
        symbol=SYMBOL,
        bucket=BUCKET,
        current_session_id=CURRENT_SESSION_ID,
        page_collection_complete=True,
    )


def _current_series(*, volume: int | bool = 200) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol=SYMBOL,
        session_id=CURRENT_SESSION_ID,
        bucket=BUCKET,
        cutoff_timestamp=_ts(31, 9, 35),
        bars=(IntradayVolumeBar(_ts(31, 9, 35), volume),),
    )


def _source(records: tuple[object, ...]) -> StaticHistoricalSessionMetadataSource:
    return StaticHistoricalSessionMetadataSource(records)


def _scenario(
    *,
    name: str,
    metadata_source: HistoricalSessionMetadataSource,
    collection: HistoricalBarsPageCollectionResult,
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    expected_metadata_load_status: str,
    expected_workflow_status: str,
    expected_workflow_reason: str | None,
    expected_bridge_status: str | None,
    expected_bridge_reason: str | None,
    expected_composition_status: str | None,
    expected_coordinator_status: str | None,
    expected_manifest_status: str | None,
    expected_harness_status: str | None,
    expected_final_status: str | None,
    expected_time_of_day_status: str | None,
    expected_relative_volume: float | None,
) -> MetadataLoadedHistoricalWorkflowScenario:
    return MetadataLoadedHistoricalWorkflowScenario(
        name=name,
        metadata_source=metadata_source,
        collection=collection,
        manifest_request=manifest_request,
        current_series=current_series,
        harness_request=_harness_request(),
        expected_metadata_load_status=expected_metadata_load_status,
        expected_workflow_status=expected_workflow_status,
        expected_workflow_reason=expected_workflow_reason,
        expected_bridge_status=expected_bridge_status,
        expected_bridge_reason=expected_bridge_reason,
        expected_composition_status=expected_composition_status,
        expected_coordinator_status=expected_coordinator_status,
        expected_manifest_status=expected_manifest_status,
        expected_harness_status=expected_harness_status,
        expected_final_status=expected_final_status,
        expected_time_of_day_status=expected_time_of_day_status,
        expected_relative_volume=expected_relative_volume,
    )


def _loaded_success_scenario(
    *,
    name: str,
    records: tuple[object, ...],
    collection: HistoricalBarsPageCollectionResult,
    manifest_request: HistoricalSessionManifestRequest | None = None,
    current_series: IntradayVolumeSeriesInput | None = None,
    coordinator_status: str,
    manifest_status: str,
    harness_status: str,
    final_status: str,
    tod_status: str | None,
    relative_volume: float | None,
    bridge_status: str = CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN,
    bridge_reason: str | None = None,
    composition_status: str = CollectedHistoricalPagesCompositionStatus.COMPOSED,
) -> MetadataLoadedHistoricalWorkflowScenario:
    return _scenario(
        name=name,
        metadata_source=_source(records),
        collection=collection,
        manifest_request=manifest_request or _manifest_request(),
        current_series=current_series or _current_series(),
        expected_metadata_load_status=HistoricalSessionMetadataSourceLoadStatus.LOADED,
        expected_workflow_status="WORKFLOW_BRIDGE_RAN",
        expected_workflow_reason=None,
        expected_bridge_status=bridge_status,
        expected_bridge_reason=bridge_reason,
        expected_composition_status=composition_status,
        expected_coordinator_status=coordinator_status,
        expected_manifest_status=manifest_status,
        expected_harness_status=harness_status,
        expected_final_status=final_status,
        expected_time_of_day_status=tod_status,
        expected_relative_volume=relative_volume,
    )


def _not_loaded_scenario(
    *,
    name: str,
    metadata_source: HistoricalSessionMetadataSource,
) -> MetadataLoadedHistoricalWorkflowScenario:
    return _scenario(
        name=name,
        metadata_source=metadata_source,
        collection=_valid_collection(),
        manifest_request=_manifest_request(),
        current_series=_current_series(),
        expected_metadata_load_status=(
            HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE
        ),
        expected_workflow_status="METADATA_NOT_LOADED",
        expected_workflow_reason="METADATA_NOT_LOADED:INVALID_RECORD_SEQUENCE",
        expected_bridge_status=None,
        expected_bridge_reason=None,
        expected_composition_status=None,
        expected_coordinator_status=None,
        expected_manifest_status=None,
        expected_harness_status=None,
        expected_final_status=None,
        expected_time_of_day_status=None,
        expected_relative_volume=None,
    )


def _non_composable_scenario(
    *,
    name: str,
    collection: HistoricalBarsPageCollectionResult,
    bridge_reason: str,
    composition_status: str,
) -> MetadataLoadedHistoricalWorkflowScenario:
    return _scenario(
        name=name,
        metadata_source=_source(_valid_raw_records()),
        collection=collection,
        manifest_request=_manifest_request(),
        current_series=_current_series(),
        expected_metadata_load_status=HistoricalSessionMetadataSourceLoadStatus.LOADED,
        expected_workflow_status="WORKFLOW_BRIDGE_RAN",
        expected_workflow_reason=None,
        expected_bridge_status=CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE,
        expected_bridge_reason=bridge_reason,
        expected_composition_status=composition_status,
        expected_coordinator_status=None,
        expected_manifest_status=None,
        expected_harness_status=None,
        expected_final_status=None,
        expected_time_of_day_status=None,
        expected_relative_volume=None,
    )


def get_metadata_loaded_historical_workflow_scenarios() -> tuple[MetadataLoadedHistoricalWorkflowScenario, ...]:
    partial_records = list(_valid_raw_records())
    invalid_extra = _raw_record("BAD", day=30)
    del invalid_extra["bucket"]
    partial_records.append(invalid_extra)

    incomplete_records = list(_valid_raw_records())
    incomplete_records[4] = dict(incomplete_records[4])
    incomplete_records[4]["is_complete"] = False

    return (
        _loaded_success_scenario(
            name="valid_multi_page_metadata_loaded",
            records=_valid_raw_records(),
            collection=_valid_collection(),
            coordinator_status=ManifestToHarnessStatus.OK,
            manifest_status=HistoricalSessionManifestStatus.OK,
            harness_status=HistoricalToTodRvolRunStatus.OK,
            final_status=CurrentSessionTimeOfDayRvolStatus.OK,
            tod_status=TimeOfDayRelativeVolumeStatus.OK,
            relative_volume=2.0,
        ),
        _loaded_success_scenario(
            name="partial_manifest_multi_page_metadata_loaded",
            records=tuple(partial_records),
            collection=_valid_collection(),
            coordinator_status=ManifestToHarnessStatus.MANIFEST_PARTIAL,
            manifest_status=HistoricalSessionManifestStatus.PARTIAL,
            harness_status=HistoricalToTodRvolRunStatus.OK,
            final_status=CurrentSessionTimeOfDayRvolStatus.OK,
            tod_status=TimeOfDayRelativeVolumeStatus.OK,
            relative_volume=2.0,
        ),
        _loaded_success_scenario(
            name="incomplete_metadata_record",
            records=tuple(incomplete_records),
            collection=_valid_collection(),
            coordinator_status=ManifestToHarnessStatus.MANIFEST_PARTIAL_AND_HARNESS_FAILED,
            manifest_status=HistoricalSessionManifestStatus.PARTIAL,
            harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            final_status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
            tod_status=None,
            relative_volume=None,
        ),
        _loaded_success_scenario(
            name="missing_historical_metadata_record",
            records=_valid_raw_records(19),
            collection=_valid_collection(),
            coordinator_status=ManifestToHarnessStatus.HARNESS_FAILED,
            manifest_status=HistoricalSessionManifestStatus.OK,
            harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            final_status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
            tod_status=None,
            relative_volume=None,
        ),
        _not_loaded_scenario(
            name="invalid_metadata_mapping_no_bridge",
            metadata_source=MappingMetadataSource({"not": "a sequence"}),
        ),
        _not_loaded_scenario(
            name="invalid_metadata_generator_no_bridge",
            metadata_source=GeneratorMetadataSource(_valid_raw_records(1)),
        ),
        _non_composable_scenario(
            name="page_cap_collection_not_composable",
            collection=_page_cap_collection(),
            bridge_reason="COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION",
            composition_status=CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION,
        ),
        _non_composable_scenario(
            name="repeated_token_collection_not_composable",
            collection=_repeated_token_collection(),
            bridge_reason="COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION",
            composition_status=CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION,
        ),
        _non_composable_scenario(
            name="empty_complete_collection_not_composable",
            collection=_empty_complete_collection(),
            bridge_reason="COLLECTION_NOT_COMPOSABLE:EMPTY_COMPLETE_COLLECTION",
            composition_status=CollectedHistoricalPagesCompositionStatus.EMPTY_COMPLETE_COLLECTION,
        ),
        _non_composable_scenario(
            name="mismatched_page_symbols_not_composable",
            collection=_mismatched_page_collection(),
            bridge_reason="COLLECTION_NOT_COMPOSABLE:MISMATCHED_PAGE_REQUESTED_SYMBOLS",
            composition_status=CollectedHistoricalPagesCompositionStatus.MISMATCHED_PAGE_REQUESTED_SYMBOLS,
        ),
        _loaded_success_scenario(
            name="invalid_manifest_request_workflow_failure",
            records=("opaque", object()),
            collection=_valid_collection(),
            manifest_request=_manifest_request(symbol=" "),
            coordinator_status=ManifestToHarnessStatus.MANIFEST_FAILED,
            manifest_status=HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL,
            harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            final_status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
            tod_status=None,
            relative_volume=None,
        ),
        _loaded_success_scenario(
            name="invalid_current_volume_workflow_failure",
            records=_valid_raw_records(),
            collection=_valid_collection(),
            current_series=_current_series(volume=False),
            coordinator_status=ManifestToHarnessStatus.HARNESS_FAILED,
            manifest_status=HistoricalSessionManifestStatus.OK,
            harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            final_status=CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED,
            tod_status=None,
            relative_volume=None,
        ),
    )


def get_metadata_loaded_historical_workflow_scenario(
    name: str,
) -> MetadataLoadedHistoricalWorkflowScenario:
    for scenario in get_metadata_loaded_historical_workflow_scenarios():
        if scenario.name == name:
            return scenario
    raise KeyError(name)
