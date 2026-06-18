import ast
import inspect
from collections.abc import Sequence
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from market_sentry.data import historical_session_manifest
from market_sentry.data.alpaca_historical_bars_fetcher import AlpacaHistoricalBarsPage
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRecordStatus,
    HistoricalSessionManifestRequest,
    HistoricalSessionManifestResult,
    HistoricalSessionManifestStatus,
    adapt_historical_session_manifest,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
    HistoricalToTodRvolRunStatus,
    run_historical_to_time_of_day_rvol,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)


UTC = timezone.utc
EASTERN = timezone(timedelta(hours=-5))


def ts(day: int = 2, hour: int = 9, minute: int = 35, *, tz=UTC) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=tz)


def request(**overrides) -> HistoricalSessionManifestRequest:
    values = {
        "symbol": " rvol ",
        "bucket": " 09:35 ",
        "current_session_id": " CURRENT-001 ",
    }
    values.update(overrides)
    return HistoricalSessionManifestRequest(**values)


def raw_record(
    session_id: str = " HIST-01 ",
    *,
    symbol: object = " rvol ",
    bucket: object = " 09:35 ",
    start: object | None = None,
    end: object | None = None,
    cutoff: object | None = None,
    is_complete: object = True,
    extra: bool = False,
    day: int = 2,
) -> dict[str, object]:
    record = {
        "symbol": symbol,
        "session_id": session_id,
        "bucket": bucket,
        "session_start_timestamp": ts(day, 9, 30) if start is None else start,
        "session_end_timestamp": ts(day, 10, 0) if end is None else end,
        "cutoff_timestamp": ts(day, 9, 35) if cutoff is None else cutoff,
        "is_complete": is_complete,
    }
    if extra:
        record["ignored"] = "still inspectable"
    return record


def valid_records(count: int = 20) -> list[dict[str, object]]:
    return [
        raw_record(f" HIST-{index:02d} ", day=index + 1)
        for index in range(1, count + 1)
    ]


def assert_record_failure(result, status: str, *, reason: str | None = None) -> None:
    assert result.status == status
    assert result.reason == (reason if reason is not None else status)
    assert result.metadata is None


def test_valid_twenty_record_manifest_emits_ordered_normalized_metadata() -> None:
    records = valid_records(20)
    first_start = records[0]["session_start_timestamp"]

    result = adapt_historical_session_manifest(records, request())

    assert result.status == HistoricalSessionManifestStatus.OK
    assert result.reason is None
    assert result.valid_record_count == 20
    assert len(result.record_results) == 20
    assert len(result.metadata_records) == 20
    assert [item.status for item in result.record_results] == [
        HistoricalSessionManifestRecordStatus.OK
    ] * 20
    assert result.metadata_records[0].symbol == "RVOL"
    assert result.metadata_records[0].session_id == "HIST-01"
    assert result.metadata_records[0].bucket == "09:35"
    assert result.metadata_records[0].session_start_timestamp is first_start
    assert result.metadata_records[0].is_complete is True


def test_partial_manifest_retains_valid_metadata_and_invalid_diagnostics() -> None:
    records = [
        raw_record("HIST-01", day=2),
        raw_record("BAD", symbol="OTHER", day=3),
        raw_record("HIST-02", day=4),
    ]

    result = adapt_historical_session_manifest(records, request())

    assert result.status == HistoricalSessionManifestStatus.PARTIAL
    assert result.reason == HistoricalSessionManifestStatus.PARTIAL
    assert [item.status for item in result.record_results] == [
        HistoricalSessionManifestRecordStatus.OK,
        HistoricalSessionManifestRecordStatus.MISMATCHED_MANIFEST_SYMBOL,
        HistoricalSessionManifestRecordStatus.OK,
    ]
    assert [item.session_id for item in result.metadata_records] == [
        "HIST-01",
        "HIST-02",
    ]


def test_empty_manifest_returns_no_valid_metadata() -> None:
    result = adapt_historical_session_manifest([], request())

    assert result.status == HistoricalSessionManifestStatus.NO_VALID_METADATA
    assert result.reason == HistoricalSessionManifestStatus.NO_VALID_METADATA
    assert result.record_results == ()
    assert result.metadata_records == ()
    assert result.valid_record_count == 0


class ExplodingRecords(Sequence):
    def __getitem__(self, index):
        raise AssertionError("raw records should not be inspected")

    def __len__(self):
        raise AssertionError("raw records should not be inspected")


@pytest.mark.parametrize(
    ("bad_request", "status"),
    [
        (request(symbol=" "), HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL),
        (request(symbol=None), HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL),
        (request(bucket=" "), HistoricalSessionManifestStatus.INVALID_TARGET_BUCKET),
        (request(bucket=123), HistoricalSessionManifestStatus.INVALID_TARGET_BUCKET),
        (
            request(current_session_id=" "),
            HistoricalSessionManifestStatus.INVALID_CURRENT_SESSION_ID,
        ),
        (
            request(current_session_id=False),
            HistoricalSessionManifestStatus.INVALID_CURRENT_SESSION_ID,
        ),
    ],
)
def test_invalid_request_returns_before_raw_record_inspection(bad_request, status) -> None:
    result = adapt_historical_session_manifest(ExplodingRecords(), bad_request)

    assert result.status == status
    assert result.reason == status
    assert result.record_results == ()
    assert result.metadata_records == ()
    assert result.valid_record_count == 0


def test_non_mapping_raw_record_is_invalid_with_no_source_record() -> None:
    result = adapt_historical_session_manifest(["not-a-mapping"], request())

    assert result.status == HistoricalSessionManifestStatus.NO_VALID_METADATA
    assert_record_failure(
        result.record_results[0],
        HistoricalSessionManifestRecordStatus.INVALID_RECORD,
    )
    assert result.record_results[0].source_record is None


@pytest.mark.parametrize(
    ("missing_field", "reason"),
    [
        ("symbol", "MISSING_REQUIRED_FIELD:symbol"),
        ("session_id", "MISSING_REQUIRED_FIELD:session_id"),
        ("bucket", "MISSING_REQUIRED_FIELD:bucket"),
        (
            "session_start_timestamp",
            "MISSING_REQUIRED_FIELD:session_start_timestamp",
        ),
        ("session_end_timestamp", "MISSING_REQUIRED_FIELD:session_end_timestamp"),
        ("cutoff_timestamp", "MISSING_REQUIRED_FIELD:cutoff_timestamp"),
        ("is_complete", "MISSING_REQUIRED_FIELD:is_complete"),
    ],
)
def test_missing_required_fields_use_fixed_order(missing_field, reason) -> None:
    record = raw_record(extra=True)
    del record[missing_field]

    result = adapt_historical_session_manifest([record], request())

    assert_record_failure(
        result.record_results[0],
        HistoricalSessionManifestRecordStatus.MISSING_REQUIRED_FIELD,
        reason=reason,
    )
    assert result.record_results[0].source_record is not None
    assert result.record_results[0].source_record["ignored"] == "still inspectable"


def test_first_missing_field_order_wins_when_multiple_fields_are_missing() -> None:
    record = raw_record()
    del record["bucket"]
    del record["symbol"]

    result = adapt_historical_session_manifest([record], request())

    assert result.record_results[0].reason == "MISSING_REQUIRED_FIELD:symbol"


@pytest.mark.parametrize(
    ("record", "status"),
    [
        (raw_record(symbol=" "), HistoricalSessionManifestRecordStatus.EMPTY_SYMBOL),
        (raw_record(symbol=123), HistoricalSessionManifestRecordStatus.EMPTY_SYMBOL),
        (
            raw_record(symbol="OTHER"),
            HistoricalSessionManifestRecordStatus.MISMATCHED_MANIFEST_SYMBOL,
        ),
        (raw_record(session_id=" "), HistoricalSessionManifestRecordStatus.EMPTY_SESSION_ID),
        (raw_record(session_id=False), HistoricalSessionManifestRecordStatus.EMPTY_SESSION_ID),
        (
            raw_record(session_id=" CURRENT-001 "),
            HistoricalSessionManifestRecordStatus.CURRENT_SESSION_IN_HISTORY,
        ),
        (raw_record(bucket=" "), HistoricalSessionManifestRecordStatus.EMPTY_BUCKET),
        (raw_record(bucket=None), HistoricalSessionManifestRecordStatus.EMPTY_BUCKET),
        (
            raw_record(bucket="09:36"),
            HistoricalSessionManifestRecordStatus.MISMATCHED_MANIFEST_BUCKET,
        ),
    ],
)
def test_symbol_session_and_bucket_validation(record, status) -> None:
    result = adapt_historical_session_manifest([record], request())

    assert_record_failure(result.record_results[0], status)


def test_session_id_current_comparison_is_case_sensitive() -> None:
    result = adapt_historical_session_manifest(
        [raw_record(session_id=" current-001 ")],
        request(),
    )

    assert result.status == HistoricalSessionManifestStatus.OK
    assert result.metadata_records[0].session_id == "current-001"


def test_duplicate_historical_ids_reject_every_duplicate_but_preserve_case_distinct_ids() -> None:
    records = [
        raw_record(" dup ", day=2),
        raw_record("dup", day=3),
        raw_record("Dup", day=4),
    ]

    result = adapt_historical_session_manifest(records, request())

    assert result.status == HistoricalSessionManifestStatus.PARTIAL
    assert [item.status for item in result.record_results] == [
        HistoricalSessionManifestRecordStatus.DUPLICATE_HISTORICAL_SESSION_ID,
        HistoricalSessionManifestRecordStatus.DUPLICATE_HISTORICAL_SESSION_ID,
        HistoricalSessionManifestRecordStatus.OK,
    ]
    assert [item.session_id for item in result.metadata_records] == ["Dup"]


@pytest.mark.parametrize(
    ("field_name", "value", "status"),
    [
        (
            "session_start_timestamp",
            date(2026, 1, 2),
            HistoricalSessionManifestRecordStatus.INVALID_SESSION_START_TIMESTAMP,
        ),
        (
            "session_start_timestamp",
            True,
            HistoricalSessionManifestRecordStatus.INVALID_SESSION_START_TIMESTAMP,
        ),
        (
            "session_end_timestamp",
            "2026-01-02T10:00:00Z",
            HistoricalSessionManifestRecordStatus.INVALID_SESSION_END_TIMESTAMP,
        ),
        (
            "cutoff_timestamp",
            9.35,
            HistoricalSessionManifestRecordStatus.INVALID_CUTOFF_TIMESTAMP,
        ),
    ],
)
def test_timestamp_bad_types_get_field_specific_status(field_name, value, status) -> None:
    record = raw_record()
    record[field_name] = value

    result = adapt_historical_session_manifest([record], request())

    assert_record_failure(result.record_results[0], status)


@pytest.mark.parametrize(
    ("record", "status"),
    [
        (
            raw_record(start=datetime(2026, 1, 2, 9, 30)),
            HistoricalSessionManifestRecordStatus.NAIVE_SESSION_TIMESTAMP,
        ),
        (
            raw_record(end=ts(2, 10, 0, tz=EASTERN)),
            HistoricalSessionManifestRecordStatus.MISMATCHED_SESSION_TIMEZONE,
        ),
        (
            raw_record(start=ts(2, 10, 0), end=ts(2, 10, 0)),
            HistoricalSessionManifestRecordStatus.INVALID_SESSION_WINDOW,
        ),
        (
            raw_record(cutoff=ts(2, 9, 29)),
            HistoricalSessionManifestRecordStatus.INVALID_CUTOFF_OUTSIDE_SESSION,
        ),
        (
            raw_record(cutoff=ts(2, 10, 0)),
            HistoricalSessionManifestRecordStatus.INVALID_CUTOFF_OUTSIDE_SESSION,
        ),
    ],
)
def test_timestamp_awareness_window_and_cutoff_validation(record, status) -> None:
    result = adapt_historical_session_manifest([record], request())

    assert_record_failure(result.record_results[0], status)


def test_cutoff_equal_to_start_is_valid() -> None:
    result = adapt_historical_session_manifest(
        [raw_record(cutoff=ts(2, 9, 30))],
        request(),
    )

    assert result.status == HistoricalSessionManifestStatus.OK
    assert result.metadata_records[0].cutoff_timestamp == ts(2, 9, 30)


@pytest.mark.parametrize(
    ("is_complete", "status"),
    [
        ("true", HistoricalSessionManifestRecordStatus.INVALID_IS_COMPLETE),
        (1, HistoricalSessionManifestRecordStatus.INVALID_IS_COMPLETE),
        (None, HistoricalSessionManifestRecordStatus.INVALID_IS_COMPLETE),
        (False, HistoricalSessionManifestRecordStatus.INCOMPLETE_SESSION),
    ],
)
def test_completion_flag_validation(is_complete, status) -> None:
    result = adapt_historical_session_manifest(
        [raw_record(is_complete=is_complete)],
        request(),
    )

    assert_record_failure(result.record_results[0], status)


def test_source_record_is_protected_copy_and_caller_mapping_is_unchanged() -> None:
    record = raw_record(extra=True)

    result = adapt_historical_session_manifest([record], request())

    source_record = result.record_results[0].source_record
    assert isinstance(source_record, MappingProxyType)
    assert source_record is not record
    assert source_record["ignored"] == "still inspectable"
    with pytest.raises(TypeError):
        source_record["ignored"] = "changed"  # type: ignore[index]
    assert record["ignored"] == "still inspectable"


def test_result_models_are_frozen_and_output_collections_are_tuples() -> None:
    result = adapt_historical_session_manifest([raw_record()], request())

    assert isinstance(result, HistoricalSessionManifestResult)
    assert isinstance(result.record_results, tuple)
    assert isinstance(result.metadata_records, tuple)
    with pytest.raises(FrozenInstanceError):
        result.status = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.record_results[0].status = "changed"  # type: ignore[misc]


def test_repeated_calls_create_fresh_result_record_and_source_objects() -> None:
    records = [raw_record()]

    first = adapt_historical_session_manifest(records, request())
    second = adapt_historical_session_manifest(records, request())

    assert first is not second
    assert first.record_results is not second.record_results
    assert first.record_results[0] is not second.record_results[0]
    assert first.record_results[0].source_record is not second.record_results[0].source_record
    assert first.metadata_records[0] is not second.metadata_records[0]


def test_valid_manifest_metadata_can_drive_actual_phase_14g_harness() -> None:
    records = valid_records(20)
    manifest_result = adapt_historical_session_manifest(records, request())
    bars = tuple(
        {
            "t": f"2026-01-{index + 1:02d}T09:35:00Z",
            "v": 100,
        }
        for index in range(1, 21)
    )
    page = AlpacaHistoricalBarsPage(
        requested_symbols=("RVOL",),
        bars_by_symbol={"RVOL": bars},
        next_page_token=None,
    )
    current_series = IntradayVolumeSeriesInput(
        symbol="RVOL",
        session_id="CURRENT-001",
        bucket="09:35",
        cutoff_timestamp=ts(31, 9, 35),
        bars=(IntradayVolumeBar(timestamp=ts(31, 9, 35), volume=200),),
    )
    harness_request = HistoricalToTodRvolRunRequest(
        symbol="RVOL",
        bucket="09:35",
        current_session_id="CURRENT-001",
        page_collection_complete=True,
    )

    harness_result = run_historical_to_time_of_day_rvol(
        page,
        manifest_result.metadata_records,
        current_series,
        harness_request,
    )

    assert manifest_result.status == HistoricalSessionManifestStatus.OK
    assert len(manifest_result.metadata_records) == 20
    assert harness_result.status == HistoricalToTodRvolRunStatus.OK


def test_status_values_are_stable_strings() -> None:
    assert HistoricalSessionManifestStatus.OK == "OK"
    assert HistoricalSessionManifestStatus.PARTIAL == "PARTIAL"
    assert HistoricalSessionManifestStatus.NO_VALID_METADATA == "NO_VALID_METADATA"
    assert (
        HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL
        == "INVALID_TARGET_SYMBOL"
    )
    assert (
        HistoricalSessionManifestStatus.INVALID_TARGET_BUCKET
        == "INVALID_TARGET_BUCKET"
    )
    assert (
        HistoricalSessionManifestStatus.INVALID_CURRENT_SESSION_ID
        == "INVALID_CURRENT_SESSION_ID"
    )
    assert HistoricalSessionManifestRecordStatus.OK == "OK"
    assert HistoricalSessionManifestRecordStatus.INVALID_RECORD == "INVALID_RECORD"
    assert (
        HistoricalSessionManifestRecordStatus.DUPLICATE_HISTORICAL_SESSION_ID
        == "DUPLICATE_HISTORICAL_SESSION_ID"
    )


def test_source_boundary_imports_only_metadata_model_and_has_no_stage_hooks() -> None:
    source = inspect.getsource(historical_session_manifest)
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
        "collections",
        "collections.abc",
        "dataclasses",
        "datetime",
        "types",
        "typing",
        "market_sentry.data.historical_session_assembly",
    }

    forbidden_terms = [
        "assemble_historical_sessions_from_page",
        "historical_baseline_composition",
        "current_session_tod_rvol",
        "historical_tod_rvol_harness",
        "alpaca",
        "intraday_bucket_adapter",
        "time_of_day_rvol",
        "HttpTransport",
        "fetcher",
        "factory",
        "config",
        "readiness",
        "market_sentry.scanner",
        "market_sentry.alerts",
        "voice",
        "StockCandidate",
        "LiveCandidateBuilder",
        "LiveComposedMarketDataProvider",
        "place_order",
        "execute_order",
        "broker",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
