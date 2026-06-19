import ast
from datetime import datetime, timedelta, timezone
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
    adapt_historical_session_manifest,
)
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSource,
    HistoricalSessionMetadataSourceLoadStatus,
    load_historical_session_metadata_source,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.json_historical_session_metadata_source import (
    INVALID_ENVELOPE_ROOT,
    INVALID_RECORDS_CONTAINER,
    MISSING_RECORDS_FIELD,
    MISSING_SCHEMA_VERSION,
    UNSUPPORTED_SCHEMA_VERSION,
    JsonHistoricalSessionMetadataFileSource,
    JsonHistoricalSessionMetadataFileSourceError,
)
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessStatus,
)
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


def write_envelope(path, records, **extra):
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


def test_path_identity_protocol_and_frozen_source(tmp_path) -> None:
    path = tmp_path / "records.json"
    write_envelope(path, [])

    source = JsonHistoricalSessionMetadataFileSource(path)

    assert source.path is path
    assert isinstance(source, HistoricalSessionMetadataSource)
    with pytest.raises(Exception):
        source.path = tmp_path / "other.json"  # type: ignore[misc]


@pytest.mark.parametrize("bad_path", ["records.json", None, 123])
def test_non_path_constructor_values_raise_type_error(bad_path) -> None:
    with pytest.raises(TypeError):
        JsonHistoricalSessionMetadataFileSource(bad_path)


def test_load_does_not_inspect_request_fields(tmp_path) -> None:
    path = tmp_path / "records.json"
    write_envelope(path, [{"anything": 1}])
    source = JsonHistoricalSessionMetadataFileSource(path)
    request = object.__new__(HistoricalSessionManifestRequest)

    records = source.load_raw_manifest_records(request)

    assert records == [{"anything": 1}]


def test_valid_envelope_returns_ordered_records_and_ignores_extra_root_keys(tmp_path) -> None:
    path = tmp_path / "records.json"
    write_envelope(
        path,
        [
            {"name": "first", "source_reason": "manually curated"},
            {"name": "second", "extra": True},
        ],
        source_name="ignored root value",
    )
    source = JsonHistoricalSessionMetadataFileSource(path)

    records = source.load_raw_manifest_records(manifest_request())

    assert isinstance(records, list)
    assert records == [
        {"name": "first", "source_reason": "manually curated"},
        {"name": "second", "extra": True},
    ]


def test_empty_records_list_is_valid(tmp_path) -> None:
    path = tmp_path / "records.json"
    write_envelope(path, [])

    records = JsonHistoricalSessionMetadataFileSource(path).load_raw_manifest_records(
        manifest_request()
    )

    assert records == []


def test_separate_loads_return_fresh_parsed_lists_and_nested_values(tmp_path) -> None:
    path = tmp_path / "records.json"
    write_envelope(path, [{"nested": {"value": 1}}])
    source = JsonHistoricalSessionMetadataFileSource(path)

    first = source.load_raw_manifest_records(manifest_request())
    second = source.load_raw_manifest_records(manifest_request())

    assert first == second
    assert first is not second
    assert first[0] is not second[0]
    assert first[0]["nested"] is not second[0]["nested"]


def test_generic_datetime_tags_decode_without_timezone_normalization(tmp_path) -> None:
    path = tmp_path / "records.json"
    write_envelope(
        path,
        [
            {
                "z": {"$datetime": "2026-01-02T09:30:00Z"},
                "utc": {"$datetime": "2026-01-02T09:30:00+00:00"},
                "offset": {"$datetime": "2026-01-02T09:30:00-05:00"},
                "naive": {"$datetime": "2026-01-02T09:30:00"},
                "bad": {"$datetime": "not-a-datetime"},
                "non_string": {"$datetime": 123},
                "extra_key": {
                    "$datetime": "2026-01-02T09:30:00Z",
                    "note": "extra",
                },
                "source_generated_at": {"$datetime": "2026-01-02T11:00:00Z"},
            }
        ],
    )

    record = JsonHistoricalSessionMetadataFileSource(path).load_raw_manifest_records(
        manifest_request()
    )[0]

    assert record["z"] == datetime(2026, 1, 2, 9, 30, tzinfo=UTC)
    assert record["utc"] == datetime(2026, 1, 2, 9, 30, tzinfo=UTC)
    assert record["offset"].utcoffset() == timedelta(hours=-5)
    assert record["naive"] == datetime(2026, 1, 2, 9, 30)
    assert record["naive"].tzinfo is None
    assert record["bad"] == {"$datetime": "not-a-datetime"}
    assert record["non_string"] == {"$datetime": 123}
    assert record["extra_key"] == {
        "$datetime": "2026-01-02T09:30:00Z",
        "note": "extra",
    }
    assert record["source_generated_at"] == datetime(2026, 1, 2, 11, 0, tzinfo=UTC)


def test_missing_file_error_propagates_unchanged(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        JsonHistoricalSessionMetadataFileSource(
            tmp_path / "missing.json"
        ).load_raw_manifest_records(manifest_request())


def test_invalid_utf8_error_propagates_unchanged(tmp_path) -> None:
    path = tmp_path / "records.json"
    path.write_bytes(b"\xff\xfe\xfa")

    with pytest.raises(UnicodeDecodeError):
        JsonHistoricalSessionMetadataFileSource(path).load_raw_manifest_records(
            manifest_request()
        )


def test_malformed_json_error_propagates_unchanged(tmp_path) -> None:
    path = tmp_path / "records.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        JsonHistoricalSessionMetadataFileSource(path).load_raw_manifest_records(
            manifest_request()
        )


def test_directory_path_error_propagates_unchanged(tmp_path) -> None:
    with pytest.raises((IsADirectoryError, PermissionError)):
        JsonHistoricalSessionMetadataFileSource(tmp_path).load_raw_manifest_records(
            manifest_request()
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], INVALID_ENVELOPE_ROOT),
        (123, INVALID_ENVELOPE_ROOT),
        ({"records": []}, MISSING_SCHEMA_VERSION),
        ({"schema_version": False, "records": []}, UNSUPPORTED_SCHEMA_VERSION),
        ({"schema_version": 1.0, "records": []}, UNSUPPORTED_SCHEMA_VERSION),
        ({"schema_version": "1", "records": []}, UNSUPPORTED_SCHEMA_VERSION),
        ({"schema_version": 2, "records": []}, UNSUPPORTED_SCHEMA_VERSION),
        ({"schema_version": 1}, MISSING_RECORDS_FIELD),
        ({"schema_version": 1, "records": None}, INVALID_RECORDS_CONTAINER),
        ({"schema_version": 1, "records": {}}, INVALID_RECORDS_CONTAINER),
        ({"schema_version": 1, "records": "bad"}, INVALID_RECORDS_CONTAINER),
    ],
)
def test_stable_envelope_errors(tmp_path, payload, message) -> None:
    path = tmp_path / "records.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(JsonHistoricalSessionMetadataFileSourceError) as exc_info:
        JsonHistoricalSessionMetadataFileSource(path).load_raw_manifest_records(
            manifest_request()
        )

    assert str(exc_info.value) == message


def test_source_does_not_validate_record_elements(tmp_path) -> None:
    path = tmp_path / "records.json"
    records_payload = [
        1,
        "raw",
        {"incomplete": True},
        {"arbitrary": {"extra": ["fields"]}},
    ]
    write_envelope(path, records_payload)

    records = JsonHistoricalSessionMetadataFileSource(path).load_raw_manifest_records(
        manifest_request()
    )

    assert records == records_payload


def test_valid_json_file_feeds_phase_15d_and_phase_14i(tmp_path) -> None:
    path = tmp_path / "records.json"
    write_envelope(path, valid_raw_records(20))
    class RecordingJsonSource(JsonHistoricalSessionMetadataFileSource):
        def load_raw_manifest_records(self, request):
            records = super().load_raw_manifest_records(request)
            object.__setattr__(self, "last_loaded_records", records)
            return records

    source = RecordingJsonSource(path)
    request = manifest_request()

    load_result = load_historical_session_metadata_source(source, request)
    manifest_result = adapt_historical_session_manifest(
        load_result.raw_manifest_records,
        request,
    )

    assert load_result.status == HistoricalSessionMetadataSourceLoadStatus.LOADED
    assert load_result.raw_manifest_records is not None
    assert load_result.raw_manifest_records is source.last_loaded_records
    assert manifest_result.status == HistoricalSessionManifestStatus.OK
    assert manifest_result.valid_record_count == 20
    assert len(manifest_result.metadata_records) == 20


def test_valid_json_file_feeds_phase_15e_workflow(tmp_path) -> None:
    path = tmp_path / "records.json"
    write_envelope(path, valid_raw_records(20))
    source = JsonHistoricalSessionMetadataFileSource(path)

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
    tod_result = (
        result.workflow_bridge_result.workflow_result.harness_result.final_result.time_of_day_result
    )
    assert tod_result is not None
    assert tod_result.relative_volume == 2.0


def test_non_decoded_datetime_tag_failure_stays_downstream(tmp_path) -> None:
    path = tmp_path / "records.json"
    records = valid_raw_records(20)
    records[0] = dict(records[0])
    records[0]["cutoff_timestamp"] = {"$datetime": "not-a-datetime"}
    write_envelope(path, records)
    source = JsonHistoricalSessionMetadataFileSource(path)
    request = manifest_request()

    load_result = load_historical_session_metadata_source(source, request)
    manifest_result = adapt_historical_session_manifest(
        load_result.raw_manifest_records,
        request,
    )

    assert load_result.status == HistoricalSessionMetadataSourceLoadStatus.LOADED
    assert manifest_result.status == HistoricalSessionManifestStatus.PARTIAL
    assert manifest_result.record_results[0].status == (
        HistoricalSessionManifestRecordStatus.INVALID_CUTOFF_TIMESTAMP
    )


def test_source_boundary() -> None:
    source = inspect.getsource(
        __import__(
            "market_sentry.data.json_historical_session_metadata_source",
            fromlist=["unused"],
        )
    )
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
        "datetime",
        "json",
        "pathlib",
        "typing",
        "market_sentry.data.historical_session_manifest",
    }

    forbidden_terms = [
        "adapt_historical_session_manifest",
        "load_historical_session_metadata_source",
        "StaticHistoricalSessionMetadataSource",
        "run_metadata_loaded_historical_workflow",
        "run_collected_pages_to_manifest_workflow",
        "compose_collected_historical_pages",
        "run_manifest_to_historical_tod_rvol",
        "fetcher",
        "transport",
        "provider",
        "factory",
        "config",
        "readiness",
        "scanner",
        "alerts",
        "voice",
        "candidate",
        "broker",
        "symbol",
        "session_id",
        "bucket",
        "session_start_timestamp",
        "session_end_timestamp",
        "cutoff_timestamp",
        "is_complete",
        "resolve(",
        "absolute(",
        "expanduser(",
        "expandvars(",
        "glob(",
        "rglob(",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered

    assert "$datetime" in source
