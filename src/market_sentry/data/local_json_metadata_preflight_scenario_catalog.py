from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json

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
    HistoricalSessionMetadataSourceLoadStatus,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
    HistoricalToTodRvolRunStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.json_historical_session_metadata_source import (
    JsonHistoricalSessionMetadataFileSourceError,
)
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessStatus,
)
from market_sentry.data.metadata_loaded_historical_workflow import (
    MetadataLoadedHistoricalWorkflowStatus,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeStatus


@dataclass(frozen=True)
class LocalJsonMetadataPreflightScenario:
    name: str
    fixture_bytes: bytes | None

    collection: HistoricalBarsPageCollectionResult
    manifest_request: HistoricalSessionManifestRequest
    current_series: IntradayVolumeSeriesInput
    harness_request: HistoricalToTodRvolRunRequest

    expected_exception_type: type[BaseException] | None
    expected_exception_message: str | None

    expected_metadata_load_status: str | None
    expected_outer_status: str | None
    expected_outer_reason: str | None

    expected_bridge_status: str | None
    expected_bridge_reason: str | None
    expected_composition_status: str | None

    expected_coordinator_status: str | None
    expected_manifest_status: str | None
    expected_harness_status: str | None
    expected_final_status: str | None
    expected_time_of_day_status: str | None
    expected_relative_volume: float | None


def _ts(day: int, hour: int = 9, minute: int = 35) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=timezone.utc)


def _dt_tag(day: int, hour: int, minute: int) -> dict[str, str]:
    return {"$datetime": f"2026-01-{day:02d}T{hour:02d}:{minute:02d}:00Z"}


def _raw_record(session_id: str, *, day: int) -> dict[str, object]:
    return {
        "symbol": "RVOL",
        "session_id": session_id,
        "bucket": "09:35",
        "session_start_timestamp": _dt_tag(day, 9, 30),
        "session_end_timestamp": _dt_tag(day, 10, 0),
        "cutoff_timestamp": _dt_tag(day, 9, 35),
        "is_complete": True,
    }


def _valid_raw_records() -> list[dict[str, object]]:
    return [
        _raw_record(f"HIST-{index:02d}", day=index + 1)
        for index in range(1, 21)
    ]


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _envelope_bytes(records: list[object]) -> bytes:
    return _json_bytes({"schema_version": 1, "records": records})


def _valid_fixture_bytes() -> bytes:
    return _envelope_bytes(_valid_raw_records())


def _partial_manifest_fixture_bytes() -> bytes:
    records = _valid_raw_records()
    extra_record = _raw_record("HIST-21", day=22)
    del extra_record["bucket"]
    records.append(extra_record)
    return _envelope_bytes(records)


def _invalid_cutoff_fixture_bytes() -> bytes:
    records = _valid_raw_records()
    records[0] = dict(records[0])
    records[0]["cutoff_timestamp"] = {"$datetime": "not-a-datetime"}
    return _envelope_bytes(records)


def _query(**overrides) -> AlpacaHistoricalBarsQuery:
    values = {
        "timeframe": "1Min",
        "start": "2026-01-02T09:30:00Z",
        "end": "2026-01-21T10:00:00Z",
    }
    values.update(overrides)
    return AlpacaHistoricalBarsQuery(**values)


def _historical_bar(day: int, minute: int, volume: int) -> dict[str, object]:
    return {
        "t": f"2026-01-{day:02d}T09:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "h": 1.0,
        "l": 1.0,
        "c": 1.0,
    }


def _page_for(
    bars: list[dict[str, object]],
    *,
    next_page_token: str | None = None,
) -> AlpacaHistoricalBarsPage:
    return AlpacaHistoricalBarsPage(
        requested_symbols=("RVOL",),
        bars_by_symbol={"RVOL": tuple(bars)},
        next_page_token=next_page_token,
    )


def _collection_from_pages(
    pages: list[AlpacaHistoricalBarsPage],
    *,
    status: str = HistoricalBarsPageCollectionStatus.COMPLETE,
    complete: bool = True,
    next_page_token: str | None = None,
) -> HistoricalBarsPageCollectionResult:
    return HistoricalBarsPageCollectionResult(
        request=HistoricalBarsPageCollectionRequest(
            symbols=("RVOL",),
            initial_query=_query(),
            max_pages=5,
        ),
        collected_pages=tuple(
            HistoricalBarsCollectedPage(
                index=index,
                query=_query(page_token=f"p{index}"),
                page=page,
            )
            for index, page in enumerate(pages)
        ),
        status=status,
        page_collection_complete=complete,
        next_page_token=next_page_token,
    )


def _complete_collection() -> HistoricalBarsPageCollectionResult:
    first_page_bars = [_historical_bar(2, 31, 25)]
    second_page_bars = [_historical_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page_bars.append(_historical_bar(day, 35, 100))
    for day in range(12, 22):
        second_page_bars.append(_historical_bar(day, 35, 100))
    return _collection_from_pages(
        [_page_for(first_page_bars), _page_for(second_page_bars)]
    )


def _incomplete_collection(
    *,
    status: str,
    next_page_token: str,
) -> HistoricalBarsPageCollectionResult:
    return _collection_from_pages(
        [_page_for([_historical_bar(2, 35, 100)], next_page_token=next_page_token)],
        status=status,
        complete=False,
        next_page_token=next_page_token,
    )


def _manifest_request(**overrides) -> HistoricalSessionManifestRequest:
    values = {
        "symbol": "RVOL",
        "bucket": "09:35",
        "current_session_id": "CURRENT-001",
    }
    values.update(overrides)
    return HistoricalSessionManifestRequest(**values)


def _current_series(*, volume: object = 200) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol="RVOL",
        session_id="CURRENT-001",
        bucket="09:35",
        cutoff_timestamp=_ts(31, 9, 35),
        bars=(IntradayVolumeBar(_ts(31, 9, 35), volume),),
    )


def _harness_request() -> HistoricalToTodRvolRunRequest:
    return HistoricalToTodRvolRunRequest(
        symbol="RVOL",
        bucket="09:35",
        current_session_id="CURRENT-001",
        page_collection_complete=True,
    )


def _result_scenario(
    *,
    name: str,
    fixture_bytes: bytes,
    collection: HistoricalBarsPageCollectionResult | None = None,
    manifest_request: HistoricalSessionManifestRequest | None = None,
    current_series: IntradayVolumeSeriesInput | None = None,
    coordinator_status: str | None,
    manifest_status: str | None,
    harness_status: str | None,
    final_status: str | None,
    time_of_day_status: str | None,
    relative_volume: float | None,
    bridge_status: str = CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN,
    bridge_reason: str | None = None,
    composition_status: str = CollectedHistoricalPagesCompositionStatus.COMPOSED,
) -> LocalJsonMetadataPreflightScenario:
    return LocalJsonMetadataPreflightScenario(
        name=name,
        fixture_bytes=fixture_bytes,
        collection=collection or _complete_collection(),
        manifest_request=manifest_request or _manifest_request(),
        current_series=current_series or _current_series(),
        harness_request=_harness_request(),
        expected_exception_type=None,
        expected_exception_message=None,
        expected_metadata_load_status=HistoricalSessionMetadataSourceLoadStatus.LOADED,
        expected_outer_status=(
            MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
        ),
        expected_outer_reason=None,
        expected_bridge_status=bridge_status,
        expected_bridge_reason=bridge_reason,
        expected_composition_status=composition_status,
        expected_coordinator_status=coordinator_status,
        expected_manifest_status=manifest_status,
        expected_harness_status=harness_status,
        expected_final_status=final_status,
        expected_time_of_day_status=time_of_day_status,
        expected_relative_volume=relative_volume,
    )


def _error_scenario(
    *,
    name: str,
    fixture_bytes: bytes | None,
    exception_type: type[BaseException],
    exception_message: str | None = None,
) -> LocalJsonMetadataPreflightScenario:
    return LocalJsonMetadataPreflightScenario(
        name=name,
        fixture_bytes=fixture_bytes,
        collection=_complete_collection(),
        manifest_request=_manifest_request(),
        current_series=_current_series(),
        harness_request=_harness_request(),
        expected_exception_type=exception_type,
        expected_exception_message=exception_message,
        expected_metadata_load_status=None,
        expected_outer_status=None,
        expected_outer_reason=None,
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


def get_local_json_metadata_preflight_scenarios(
) -> tuple[LocalJsonMetadataPreflightScenario, ...]:
    not_composable_reason = (
        f"{CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE}:"
        f"{CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION}"
    )
    baseline_failed = CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED
    final_failed = HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
    return (
        _result_scenario(
            name="valid_json_complete_multi_page",
            fixture_bytes=_valid_fixture_bytes(),
            coordinator_status=ManifestToHarnessStatus.OK,
            manifest_status=HistoricalSessionManifestStatus.OK,
            harness_status=HistoricalToTodRvolRunStatus.OK,
            final_status=CurrentSessionTimeOfDayRvolStatus.OK,
            time_of_day_status=TimeOfDayRelativeVolumeStatus.OK,
            relative_volume=2.0,
        ),
        _result_scenario(
            name="partial_manifest_json_complete_multi_page",
            fixture_bytes=_partial_manifest_fixture_bytes(),
            coordinator_status=ManifestToHarnessStatus.MANIFEST_PARTIAL,
            manifest_status=HistoricalSessionManifestStatus.PARTIAL,
            harness_status=HistoricalToTodRvolRunStatus.OK,
            final_status=CurrentSessionTimeOfDayRvolStatus.OK,
            time_of_day_status=TimeOfDayRelativeVolumeStatus.OK,
            relative_volume=2.0,
        ),
        _result_scenario(
            name="invalid_cutoff_datetime_json",
            fixture_bytes=_invalid_cutoff_fixture_bytes(),
            coordinator_status=(
                ManifestToHarnessStatus.MANIFEST_PARTIAL_AND_HARNESS_FAILED
            ),
            manifest_status=HistoricalSessionManifestStatus.PARTIAL,
            harness_status=final_failed,
            final_status=baseline_failed,
            time_of_day_status=None,
            relative_volume=None,
        ),
        _result_scenario(
            name="empty_records_json",
            fixture_bytes=_envelope_bytes([]),
            coordinator_status=ManifestToHarnessStatus.MANIFEST_FAILED,
            manifest_status=HistoricalSessionManifestStatus.NO_VALID_METADATA,
            harness_status=final_failed,
            final_status=baseline_failed,
            time_of_day_status=None,
            relative_volume=None,
        ),
        _result_scenario(
            name="page_cap_json_collection_not_composable",
            fixture_bytes=_valid_fixture_bytes(),
            collection=_incomplete_collection(
                status=HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED,
                next_page_token="NEXT",
            ),
            coordinator_status=None,
            manifest_status=None,
            harness_status=None,
            final_status=None,
            time_of_day_status=None,
            relative_volume=None,
            bridge_status=(
                CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE
            ),
            bridge_reason=not_composable_reason,
            composition_status=(
                CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION
            ),
        ),
        _result_scenario(
            name="repeated_token_json_collection_not_composable",
            fixture_bytes=_valid_fixture_bytes(),
            collection=_incomplete_collection(
                status=HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN,
                next_page_token="LOOP",
            ),
            coordinator_status=None,
            manifest_status=None,
            harness_status=None,
            final_status=None,
            time_of_day_status=None,
            relative_volume=None,
            bridge_status=(
                CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE
            ),
            bridge_reason=not_composable_reason,
            composition_status=(
                CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION
            ),
        ),
        _result_scenario(
            name="invalid_manifest_request_json",
            fixture_bytes=_valid_fixture_bytes(),
            manifest_request=_manifest_request(symbol=" "),
            coordinator_status=ManifestToHarnessStatus.MANIFEST_FAILED,
            manifest_status=HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL,
            harness_status=final_failed,
            final_status=baseline_failed,
            time_of_day_status=None,
            relative_volume=None,
        ),
        _result_scenario(
            name="invalid_current_volume_json",
            fixture_bytes=_valid_fixture_bytes(),
            current_series=_current_series(volume=False),
            coordinator_status=ManifestToHarnessStatus.HARNESS_FAILED,
            manifest_status=HistoricalSessionManifestStatus.OK,
            harness_status=final_failed,
            final_status=(
                CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
            ),
            time_of_day_status=None,
            relative_volume=None,
        ),
        _error_scenario(
            name="unsupported_schema_json_error",
            fixture_bytes=_json_bytes({"schema_version": 2, "records": []}),
            exception_type=JsonHistoricalSessionMetadataFileSourceError,
            exception_message="UNSUPPORTED_SCHEMA_VERSION",
        ),
        _error_scenario(
            name="malformed_json_error",
            fixture_bytes=b'{"schema_version": 1, "records": [',
            exception_type=json.JSONDecodeError,
        ),
        _error_scenario(
            name="invalid_utf8_json_error",
            fixture_bytes=b"\xff\xfe\xfa",
            exception_type=UnicodeDecodeError,
        ),
        _error_scenario(
            name="missing_json_file_error",
            fixture_bytes=None,
            exception_type=FileNotFoundError,
        ),
    )


def get_local_json_metadata_preflight_scenario(
    name: str,
) -> LocalJsonMetadataPreflightScenario:
    for scenario in get_local_json_metadata_preflight_scenarios():
        if scenario.name == name:
            return scenario
    raise KeyError(name)
