import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone, timedelta
import inspect
import json

import pytest

from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSourceLoadStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayBucketStatus,
    calculate_cumulative_volume_at_bucket,
)
from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    get_local_json_metadata_preflight_scenario,
)
from market_sentry.data.local_json_metadata_workflow_preflight import (
    run_local_json_metadata_workflow_preflight,
)
from market_sentry.data.metadata_loaded_historical_workflow import (
    MetadataLoadedHistoricalWorkflowStatus,
)
from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionStatus,
)
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessStatus,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeStatus
from market_sentry.data import json_historical_rvol_bundle as bundle_module
from market_sentry.data.json_historical_rvol_bundle import (
    JsonHistoricalRvolBundleError,
    load_local_historical_rvol_bundle,
)


def dt_tag(day: int, minute: int = 35) -> dict[str, str]:
    return {"$datetime": f"2026-01-{day:02d}T09:{minute:02d}:00Z"}


def raw_bar(day: int, minute: int, volume, **extra) -> dict[str, object]:
    value = {
        "t": f"2026-01-{day:02d}T09:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "h": 1.0,
        "l": 1.0,
        "c": 1.0,
    }
    value.update(extra)
    return value


def query(**overrides) -> dict[str, object]:
    value = {
        "timeframe": "1Min",
        "start": "2026-01-02T09:30:00Z",
        "end": "2026-01-21T10:00:00Z",
        "limit": 1000,
        "page_token": None,
        "sort": "asc",
    }
    value.update(overrides)
    return value


def base_bundle_payload(**overrides) -> dict[str, object]:
    first_page_bars = [raw_bar(2, 31, 25, custom="kept", invalid_text="bad")]
    second_page_bars = [raw_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page_bars.append(raw_bar(day, 35, 100))
    for day in range(12, 22):
        second_page_bars.append(raw_bar(day, 35, 100))

    value = {
        "schema_version": 1,
        "collection": {
            "request": {
                "symbols": ["RVOL"],
                "initial_query": query(),
                "max_pages": 5,
            },
            "collected_pages": [
                {
                    "index": 0,
                    "query": query(page_token="p0"),
                    "page": {
                        "requested_symbols": ["RVOL"],
                        "bars_by_symbol": {"RVOL": first_page_bars},
                        "next_page_token": None,
                    },
                },
                {
                    "index": 1,
                    "query": query(page_token="p1"),
                    "page": {
                        "requested_symbols": ["RVOL"],
                        "bars_by_symbol": {"RVOL": second_page_bars},
                        "next_page_token": None,
                    },
                },
            ],
            "status": "COMPLETE",
            "page_collection_complete": True,
            "next_page_token": None,
            "reason": None,
        },
        "manifest_request": {
            "symbol": "RVOL",
            "bucket": "09:35",
            "current_session_id": "CURRENT-001",
        },
        "current_series": {
            "symbol": "RVOL",
            "session_id": "CURRENT-001",
            "bucket": "09:35",
            "cutoff_timestamp": dt_tag(31),
            "bars": [
                {
                    "timestamp": dt_tag(31),
                    "volume": 200,
                }
            ],
        },
        "harness_request": {
            "symbol": "RVOL",
            "bucket": "09:35",
            "current_session_id": "CURRENT-001",
            "page_collection_complete": True,
            "minimum_historical_sessions": 20,
        },
    }
    value.update(overrides)
    return value


def write_bundle(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def load_payload(tmp_path, payload=None):
    path = tmp_path / "historical-rvol-bundle.json"
    write_bundle(path, base_bundle_payload() if payload is None else payload)
    return load_local_historical_rvol_bundle(path)


def nested_set(payload, keys, value) -> None:
    target = payload
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value


def nested_delete(payload, keys) -> None:
    target = payload
    for key in keys[:-1]:
        target = target[key]
    del target[keys[-1]]


def assert_bundle_error(tmp_path, payload, expected: str) -> None:
    path = tmp_path / "bad.json"
    write_bundle(path, payload)
    with pytest.raises(JsonHistoricalRvolBundleError) as exc_info:
        load_local_historical_rvol_bundle(path)
    assert str(exc_info.value) == expected


def test_path_must_be_path() -> None:
    with pytest.raises(TypeError) as exc_info:
        load_local_historical_rvol_bundle("bundle.json")  # type: ignore[arg-type]

    assert str(exc_info.value) == "path must be a pathlib.Path."


def test_exact_path_identity_and_frozen_bundle(tmp_path) -> None:
    path = tmp_path / "bundle.json"
    write_bundle(path, base_bundle_payload())

    loaded = load_local_historical_rvol_bundle(path)

    assert loaded.path is path
    assert loaded.collection.request.symbols == ("RVOL",)
    with pytest.raises(FrozenInstanceError):
        loaded.path = tmp_path / "other.json"  # type: ignore[misc]


def test_standard_file_utf8_and_json_errors_propagate(tmp_path, monkeypatch) -> None:
    with pytest.raises(FileNotFoundError):
        load_local_historical_rvol_bundle(tmp_path / "missing.json")

    invalid_utf8 = tmp_path / "invalid-utf8.json"
    invalid_utf8.write_bytes(b"\xff\xfe")
    with pytest.raises(UnicodeDecodeError):
        load_local_historical_rvol_bundle(invalid_utf8)

    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"schema_version": 1,', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_local_historical_rvol_bundle(malformed)

    path = tmp_path / "standard-error.json"
    path.write_text("{}", encoding="utf-8")
    directory_error = IsADirectoryError("directory")

    def fake_read_text(self, *, encoding=None):
        raise directory_error

    monkeypatch.setattr(type(path), "read_text", fake_read_text)
    with pytest.raises(IsADirectoryError) as directory_exc_info:
        load_local_historical_rvol_bundle(path)
    assert directory_exc_info.value is directory_error

    permission_error = PermissionError("nope")
    monkeypatch.setattr(
        type(path),
        "read_text",
        lambda self, *, encoding=None: (_ for _ in ()).throw(permission_error),
    )
    with pytest.raises(PermissionError) as exc_info:
        load_local_historical_rvol_bundle(path)
    assert exc_info.value is permission_error


def test_file_is_read_every_call_and_successful_loads_are_fresh(tmp_path) -> None:
    path = tmp_path / "bundle.json"
    payload = base_bundle_payload()
    write_bundle(path, payload)

    first = load_local_historical_rvol_bundle(path)
    nested_set(payload, ["manifest_request", "symbol"], "ALT")
    write_bundle(path, payload)
    second = load_local_historical_rvol_bundle(path)

    assert first is not second
    assert first.collection is not second.collection
    assert first.collection.request is not second.collection.request
    assert first.collection.collected_pages[0] is not second.collection.collected_pages[0]
    assert first.manifest_request is not second.manifest_request
    assert first.current_series is not second.current_series
    assert first.current_series.bars[0] is not second.current_series.bars[0]
    assert first.harness_request is not second.harness_request
    assert first.manifest_request.symbol == "RVOL"
    assert second.manifest_request.symbol == "ALT"


def test_envelope_errors(tmp_path) -> None:
    assert_bundle_error(tmp_path, [], "INVALID_ENVELOPE_ROOT")

    payload = base_bundle_payload()
    del payload["schema_version"]
    assert_bundle_error(tmp_path, payload, "MISSING_SCHEMA_VERSION")

    for value in (False, 1.0, "1", 2):
        payload = base_bundle_payload(schema_version=value)
        assert_bundle_error(tmp_path, payload, "UNSUPPORTED_SCHEMA_VERSION")


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("collection", "MISSING_REQUIRED_FIELD:collection"),
        ("manifest_request", "MISSING_REQUIRED_FIELD:manifest_request"),
        ("current_series", "MISSING_REQUIRED_FIELD:current_series"),
        ("harness_request", "MISSING_REQUIRED_FIELD:harness_request"),
    ],
)
def test_missing_root_required_fields(tmp_path, field, message) -> None:
    payload = base_bundle_payload()
    del payload[field]

    assert_bundle_error(tmp_path, payload, message)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("collection", "INVALID_MAPPING:collection"),
        ("manifest_request", "INVALID_MAPPING:manifest_request"),
        ("current_series", "INVALID_MAPPING:current_series"),
        ("harness_request", "INVALID_MAPPING:harness_request"),
    ],
)
def test_non_mapping_sections(tmp_path, field, message) -> None:
    payload = base_bundle_payload()
    payload[field] = []

    assert_bundle_error(tmp_path, payload, message)


@pytest.mark.parametrize(
    ("keys", "message"),
    [
        (["collection", "request"], "MISSING_REQUIRED_FIELD:collection.request"),
        (
            ["collection", "request", "symbols"],
            "MISSING_REQUIRED_FIELD:collection.request.symbols",
        ),
        (
            ["collection", "request", "initial_query"],
            "MISSING_REQUIRED_FIELD:collection.request.initial_query",
        ),
        (
            ["collection", "request", "max_pages"],
            "MISSING_REQUIRED_FIELD:collection.request.max_pages",
        ),
        (
            ["collection", "collected_pages"],
            "MISSING_REQUIRED_FIELD:collection.collected_pages",
        ),
        (["collection", "status"], "MISSING_REQUIRED_FIELD:collection.status"),
        (
            ["collection", "next_page_token"],
            "MISSING_REQUIRED_FIELD:collection.next_page_token",
        ),
        (["collection", "reason"], "MISSING_REQUIRED_FIELD:collection.reason"),
        (
            ["collection", "collected_pages", 0, "index"],
            "MISSING_REQUIRED_FIELD:collection.collected_pages[0].index",
        ),
        (
            ["collection", "collected_pages", 0, "query"],
            "MISSING_REQUIRED_FIELD:collection.collected_pages[0].query",
        ),
        (
            ["collection", "collected_pages", 0, "page"],
            "MISSING_REQUIRED_FIELD:collection.collected_pages[0].page",
        ),
        (
            ["collection", "collected_pages", 0, "page", "bars_by_symbol"],
            "MISSING_REQUIRED_FIELD:collection.collected_pages[0].page.bars_by_symbol",
        ),
        (
            ["current_series", "bars"],
            "MISSING_REQUIRED_FIELD:current_series.bars",
        ),
        (
            ["current_series", "bars", 0, "timestamp"],
            "MISSING_REQUIRED_FIELD:current_series.bars[0].timestamp",
        ),
        (
            ["current_series", "bars", 0, "volume"],
            "MISSING_REQUIRED_FIELD:current_series.bars[0].volume",
        ),
    ],
)
def test_missing_nested_required_fields(tmp_path, keys, message) -> None:
    payload = base_bundle_payload()
    nested_delete(payload, keys)

    assert_bundle_error(tmp_path, payload, message)


@pytest.mark.parametrize(
    ("keys", "value", "message"),
    [
        (
            ["collection", "request", "symbols"],
            "RVOL",
            "INVALID_SEQUENCE:collection.request.symbols",
        ),
        (
            ["collection", "collected_pages"],
            {},
            "INVALID_SEQUENCE:collection.collected_pages",
        ),
        (
            ["collection", "collected_pages", 0, "page", "requested_symbols"],
            "RVOL",
            "INVALID_SEQUENCE:collection.collected_pages[0].page.requested_symbols",
        ),
        (
            ["collection", "collected_pages", 0, "page", "bars_by_symbol", "RVOL"],
            {},
            "INVALID_SEQUENCE:collection.collected_pages[0].page.bars_by_symbol",
        ),
        (
            ["current_series", "bars"],
            {},
            "INVALID_SEQUENCE:current_series.bars",
        ),
    ],
)
def test_invalid_sequences(tmp_path, keys, value, message) -> None:
    payload = base_bundle_payload()
    nested_set(payload, keys, value)

    assert_bundle_error(tmp_path, payload, message)


@pytest.mark.parametrize(
    ("keys", "value", "message"),
    [
        (
            ["collection", "request", "initial_query"],
            [],
            "INVALID_MAPPING:collection.request.initial_query",
        ),
        (
            ["collection", "collected_pages", 0],
            [],
            "INVALID_MAPPING:collection.collected_pages[0]",
        ),
        (
            ["collection", "collected_pages", 0, "page", "bars_by_symbol"],
            [],
            "INVALID_MAPPING:collection.collected_pages[0].page.bars_by_symbol",
        ),
        (
            ["collection", "collected_pages", 0, "page", "bars_by_symbol", "RVOL", 0],
            [],
            "INVALID_MAPPING:collection.collected_pages[0].page.bars_by_symbol[0]",
        ),
        (
            ["current_series", "bars", 0],
            [],
            "INVALID_MAPPING:current_series.bars[0]",
        ),
    ],
)
def test_invalid_mappings(tmp_path, keys, value, message) -> None:
    payload = base_bundle_payload()
    nested_set(payload, keys, value)

    assert_bundle_error(tmp_path, payload, message)


@pytest.mark.parametrize(
    ("keys", "value", "message"),
    [
        (
            ["collection", "request", "initial_query", "page_token"],
            12,
            "INVALID_STRING_OR_NULL:collection.request.initial_query.page_token",
        ),
        (
            ["collection", "next_page_token"],
            12,
            "INVALID_STRING_OR_NULL:collection.next_page_token",
        ),
        (
            ["collection", "reason"],
            12,
            "INVALID_STRING_OR_NULL:collection.reason",
        ),
        (
            ["collection", "request", "initial_query", "timeframe"],
            12,
            "INVALID_STRING_OR_NULL:collection.request.initial_query.timeframe",
        ),
    ],
)
def test_invalid_string_or_null_values(tmp_path, keys, value, message) -> None:
    payload = base_bundle_payload()
    nested_set(payload, keys, value)

    assert_bundle_error(tmp_path, payload, message)


@pytest.mark.parametrize(
    ("keys", "value", "message"),
    [
        (
            ["collection", "request", "max_pages"],
            False,
            "INVALID_INTEGER:collection.request.max_pages",
        ),
        (
            ["collection", "request", "max_pages"],
            1.5,
            "INVALID_INTEGER:collection.request.max_pages",
        ),
        (
            ["collection", "request", "initial_query", "limit"],
            False,
            "INVALID_INTEGER:collection.request.initial_query.limit",
        ),
        (
            ["collection", "request", "initial_query", "limit"],
            1.5,
            "INVALID_INTEGER:collection.request.initial_query.limit",
        ),
        (
            ["collection", "collected_pages", 0, "index"],
            False,
            "INVALID_INTEGER:collection.collected_pages[0].index",
        ),
        (
            ["collection", "collected_pages", 0, "index"],
            1.5,
            "INVALID_INTEGER:collection.collected_pages[0].index",
        ),
    ],
)
def test_invalid_integers(tmp_path, keys, value, message) -> None:
    payload = base_bundle_payload()
    nested_set(payload, keys, value)

    assert_bundle_error(tmp_path, payload, message)


@pytest.mark.parametrize("value", [True, False])
def test_collection_page_collection_complete_accepts_real_booleans(
    tmp_path,
    value,
) -> None:
    payload = base_bundle_payload()
    nested_set(payload, ["collection", "page_collection_complete"], value)

    loaded = load_payload(tmp_path, payload)

    assert loaded.collection.page_collection_complete is value


@pytest.mark.parametrize("value", ["true", 1, None, []])
def test_collection_page_collection_complete_rejects_non_booleans(
    tmp_path,
    value,
) -> None:
    payload = base_bundle_payload()
    nested_set(payload, ["collection", "page_collection_complete"], value)

    assert_bundle_error(
        tmp_path,
        payload,
        "INVALID_BOOLEAN:collection.page_collection_complete",
    )


def test_existing_query_constructor_errors_propagate(tmp_path) -> None:
    payload = base_bundle_payload()
    nested_set(payload, ["collection", "request", "initial_query", "sort"], "oldest")
    path = tmp_path / "bad-query.json"
    write_bundle(path, payload)

    with pytest.raises(ValueError) as exc_info:
        load_local_historical_rvol_bundle(path)

    assert str(exc_info.value) == "sort must be exactly 'asc' or 'desc'."


def test_datetime_tags_decode_without_normalization(tmp_path) -> None:
    payload = base_bundle_payload()
    payload["current_series"]["cutoff_timestamp"] = {
        "$datetime": "2026-01-31T09:35:00Z"
    }
    payload["current_series"]["bars"] = [
        {"timestamp": {"$datetime": "2026-01-31T09:34:00-05:00"}, "volume": 50},
        {"timestamp": {"$datetime": "2026-01-31T09:35:00"}, "volume": 50},
    ]

    loaded = load_payload(tmp_path, payload)

    assert loaded.current_series.cutoff_timestamp == datetime(
        2026, 1, 31, 9, 35, tzinfo=timezone.utc
    )
    assert loaded.current_series.bars[0].timestamp.utcoffset() == timedelta(hours=-5)
    assert loaded.current_series.bars[1].timestamp == datetime(2026, 1, 31, 9, 35)
    assert loaded.current_series.bars[1].timestamp.tzinfo is None


def test_invalid_datetime_tags_remain_mappings_and_recurse(tmp_path) -> None:
    payload = base_bundle_payload()
    payload["current_series"]["cutoff_timestamp"] = {
        "$datetime": "2026-01-31T09:35:00Z"
    }
    payload["current_series"]["bars"] = [
        {"timestamp": {"$datetime": "not-a-date"}, "volume": 10},
        {"timestamp": {"$datetime": 7}, "volume": 20},
        {"timestamp": {"$datetime": "2026-01-31T09:35:00Z", "extra": True}, "volume": 30},
    ]

    loaded = load_payload(tmp_path, payload)

    assert loaded.current_series.bars[0].timestamp == {"$datetime": "not-a-date"}
    assert loaded.current_series.bars[1].timestamp == {"$datetime": 7}
    assert loaded.current_series.bars[2].timestamp == {
        "$datetime": "2026-01-31T09:35:00Z",
        "extra": True,
    }


def test_opaque_historical_raw_bars_are_preserved(tmp_path) -> None:
    payload = base_bundle_payload()
    raw = payload["collection"]["collected_pages"][0]["page"]["bars_by_symbol"]["RVOL"][0]
    raw["v"] = False
    raw["custom"] = {"nested": ["value"]}
    raw["text_volume"] = "bad"

    loaded = load_payload(tmp_path, payload)
    loaded_raw = loaded.collection.collected_pages[0].page.bars_by_symbol["RVOL"][0]

    assert loaded_raw["v"] is False
    assert loaded_raw["custom"] == {"nested": ["value"]}
    assert loaded_raw["text_volume"] == "bad"


def test_invalid_current_values_preserved_for_downstream_validation(tmp_path) -> None:
    payload = base_bundle_payload()
    payload["current_series"]["bars"] = [
        {"timestamp": {"$datetime": "bad"}, "volume": False}
    ]

    loaded = load_payload(tmp_path, payload)

    assert loaded.current_series.bars[0].timestamp == {"$datetime": "bad"}
    assert loaded.current_series.bars[0].volume is False
    result = calculate_cumulative_volume_at_bucket(loaded.current_series)
    assert result.status == IntradayBucketStatus.INVALID_INTRADAY_TIMESTAMP


def test_real_valid_bundle_reaches_phase_15h_rvol_two(tmp_path) -> None:
    metadata = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_bytes(metadata.fixture_bytes)
    bundle_path = tmp_path / "bundle.json"
    write_bundle(bundle_path, base_bundle_payload())

    loaded = load_local_historical_rvol_bundle(bundle_path)
    result = run_local_json_metadata_workflow_preflight(
        metadata_path,
        loaded.collection,
        loaded.manifest_request,
        loaded.current_series,
        loaded.harness_request,
    )

    assert result.metadata_source.path is metadata_path
    assert result.workflow_result.metadata_load_result.status == (
        HistoricalSessionMetadataSourceLoadStatus.LOADED
    )
    assert result.workflow_result.status == (
        MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    )
    bridge = result.workflow_result.workflow_bridge_result
    assert bridge.composition_result.status == (
        CollectedHistoricalPagesCompositionStatus.COMPOSED
    )
    coordinator = bridge.workflow_result
    assert coordinator.status == ManifestToHarnessStatus.OK
    final = coordinator.harness_result.final_result
    assert final.status == CurrentSessionTimeOfDayRvolStatus.OK
    assert final.time_of_day_result.status == TimeOfDayRelativeVolumeStatus.OK
    assert final.time_of_day_result.relative_volume == 2.0


def test_invalid_current_volume_reaches_downstream_diagnostics(tmp_path) -> None:
    metadata = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_bytes(metadata.fixture_bytes)
    payload = base_bundle_payload()
    payload["current_series"]["bars"][0]["volume"] = False
    bundle_path = tmp_path / "bundle.json"
    write_bundle(bundle_path, payload)

    loaded = load_local_historical_rvol_bundle(bundle_path)
    result = run_local_json_metadata_workflow_preflight(
        metadata_path,
        loaded.collection,
        loaded.manifest_request,
        loaded.current_series,
        loaded.harness_request,
    )

    final = (
        result.workflow_result.workflow_bridge_result.workflow_result
        .harness_result.final_result
    )
    assert final.status == (
        CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
    )
    assert final.current_result.status == IntradayBucketStatus.INVALID_INTRADAY_VOLUME


def test_source_boundary() -> None:
    source = inspect.getsource(bundle_module)
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
        "json",
        "collections.abc",
        "dataclasses",
        "datetime",
        "pathlib",
        "typing",
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.historical_bars_page_collector",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.historical_tod_rvol_harness",
        "market_sentry.data.intraday_bucket_adapter",
    }

    call_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)

    forbidden_calls = {
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "mkdir",
        "getenv",
        "run_local_json_metadata_workflow_preflight",
        "run_metadata_loaded_historical_workflow",
        "run_collected_pages_to_manifest_workflow",
        "run_manifest_to_historical_tod_rvol",
    }
    assert not forbidden_calls & call_names
    assert "read_text" in call_names
    assert "loads" in call_names

    forbidden_terms = [
        "local_json_metadata_preflight_scenario",
        "local_json_metadata_workflow_preflight",
        "json_historical_session_metadata_source",
        "provider",
        "factory",
        "config",
        "readiness",
        "scanner",
        "alerts",
        "voice",
        "http",
        "transport",
        "trading",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
