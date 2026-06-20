import ast
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import inspect
import json
import math
from pathlib import Path
from types import MappingProxyType

import pytest

from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRecordStatus,
    HistoricalSessionManifestRequest,
    adapt_historical_session_manifest,
)
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSourceLoadStatus,
    load_historical_session_metadata_source,
)
from market_sentry.data.intraday_bucket_adapter import IntradayBucketStatus
from market_sentry.data.json_historical_session_metadata_source import (
    JsonHistoricalSessionMetadataFileSource,
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
from market_sentry.data import json_historical_session_metadata_writer as writer_module
from market_sentry.data.json_historical_session_metadata_writer import (
    JsonHistoricalSessionMetadataWriteError,
    render_local_historical_session_metadata,
    write_local_historical_session_metadata,
)


UTC = timezone.utc


def dt(day: int, hour: int = 9, minute: int = 35) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=UTC)


def manifest_request() -> HistoricalSessionManifestRequest:
    return HistoricalSessionManifestRequest(
        symbol="RVOL",
        bucket="09:35",
        current_session_id="CURRENT-001",
    )


def raw_record(session_id: str, *, day: int, is_complete=True) -> dict[str, object]:
    return {
        "symbol": "RVOL",
        "session_id": session_id,
        "bucket": "09:35",
        "session_start_timestamp": dt(day, 9, 30),
        "session_end_timestamp": dt(day, 10, 0),
        "cutoff_timestamp": dt(day, 9, 35),
        "is_complete": is_complete,
    }


def valid_records(count: int = 20) -> list[dict[str, object]]:
    return [
        raw_record(f"HIST-{index:02d}", day=index + 1)
        for index in range(1, count + 1)
    ]


def test_valid_sequence_acceptance_and_preserved_order() -> None:
    records = [
        {"name": "first"},
        "opaque",
        7,
        {"name": "last"},
    ]

    payload = json.loads(render_local_historical_session_metadata(records))

    assert payload["records"] == records
    assert [item for item in payload["records"]] == records


@pytest.mark.parametrize(
    "records",
    [
        "records",
        b"records",
        bytearray(b"records"),
        memoryview(b"records"),
        object(),
        {"not": "a sequence"},
        (item for item in (1, 2)),
    ],
)
def test_invalid_records_sequence_error(records) -> None:
    with pytest.raises(JsonHistoricalSessionMetadataWriteError) as exc_info:
        render_local_historical_session_metadata(records)

    assert str(exc_info.value) == "INVALID_RECORDS_SEQUENCE"


def test_canonical_deterministic_rendering_and_utf8_preservation() -> None:
    records = [
        {"session": "café", "value": 1},
        {"session": "second", "nested": [True, None]},
    ]
    rendered = render_local_historical_session_metadata(records)
    repeated = render_local_historical_session_metadata(tuple(records))

    assert rendered == repeated
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")
    assert "café" in rendered
    assert "\\u00e9" not in rendered
    payload = json.loads(rendered)
    assert payload == {
        "records": records,
        "schema_version": 1,
    }
    assert rendered == json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def test_writer_writes_exact_rendered_utf8_text_once(monkeypatch, tmp_path) -> None:
    path = tmp_path / "metadata.json"
    records = [{"name": "café"}]
    calls = []
    original_write_text = Path.write_text

    def tracked_write_text(self, data, *, encoding=None, errors=None, newline=None):
        calls.append((self, data, encoding))
        return original_write_text(
            self,
            data,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )

    monkeypatch.setattr(Path, "write_text", tracked_write_text)

    result = write_local_historical_session_metadata(path, records)

    assert result is None
    assert calls == [
        (path, render_local_historical_session_metadata(records), "utf-8")
    ]
    assert path.read_text(encoding="utf-8") == (
        render_local_historical_session_metadata(records)
    )


def test_non_path_output_raises_exact_type_error() -> None:
    with pytest.raises(TypeError) as exc_info:
        write_local_historical_session_metadata("metadata.json", [])  # type: ignore[arg-type]

    assert str(exc_info.value) == "path must be a pathlib.Path."


def test_no_output_read_back(monkeypatch, tmp_path) -> None:
    path = tmp_path / "metadata.json"

    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *_args, **_kwargs: pytest.fail("read_text should not run"),
    )
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda *_args, **_kwargs: pytest.fail("read_bytes should not run"),
    )

    write_local_historical_session_metadata(path, [])

    assert path.exists()


def test_no_parent_creation_and_filesystem_errors_propagate(tmp_path, monkeypatch) -> None:
    missing_parent = tmp_path / "missing-parent" / "metadata.json"

    with pytest.raises(FileNotFoundError):
        write_local_historical_session_metadata(missing_parent, [])

    assert not (tmp_path / "missing-parent").exists()

    path = tmp_path / "metadata.json"
    error = IsADirectoryError("directory")

    def fake_write_text(self, data, *, encoding=None):
        raise error

    monkeypatch.setattr(Path, "write_text", fake_write_text)
    with pytest.raises(IsADirectoryError) as exc_info:
        write_local_historical_session_metadata(path, [])

    assert exc_info.value is error


def test_fresh_writes_use_fresh_current_input_without_cache(tmp_path) -> None:
    path = tmp_path / "metadata.json"

    write_local_historical_session_metadata(path, [{"value": 1}])
    first = path.read_text(encoding="utf-8")
    write_local_historical_session_metadata(path, [{"value": 2}])
    second = path.read_text(encoding="utf-8")

    assert first != second
    assert '"value": 1' in first
    assert '"value": 2' in second


def test_recursive_datetime_encoding() -> None:
    fixed = timezone(timedelta(hours=-5))
    records = [
        {
            "naive": datetime(2026, 1, 2, 9, 30),
            "utc": datetime(2026, 1, 2, 9, 30, tzinfo=UTC),
            "fixed": datetime(2026, 1, 2, 9, 30, tzinfo=fixed),
            "nested": [
                {"timestamp": datetime(2026, 1, 2, 9, 35, tzinfo=UTC)}
            ],
        }
    ]

    payload = json.loads(render_local_historical_session_metadata(records))
    record = payload["records"][0]

    assert record["naive"] == {"$datetime": "2026-01-02T09:30:00"}
    assert record["utc"] == {"$datetime": "2026-01-02T09:30:00Z"}
    assert record["fixed"] == {"$datetime": "2026-01-02T09:30:00-05:00"}
    assert record["nested"][0]["timestamp"] == {
        "$datetime": "2026-01-02T09:35:00Z"
    }


def assert_writer_error(records, expected: str) -> None:
    with pytest.raises(JsonHistoricalSessionMetadataWriteError) as exc_info:
        render_local_historical_session_metadata(records)
    assert str(exc_info.value) == expected


def test_non_string_mapping_key_error() -> None:
    assert_writer_error([{1: "bad"}], "INVALID_MAPPING_KEY:records[0]")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_float_error(value) -> None:
    assert_writer_error(
        [{"value": value}],
        "NON_FINITE_FLOAT:records[0].value",
    )


@pytest.mark.parametrize(
    "value",
    [
        b"bytes",
        bytearray(b"bytes"),
        {1, 2},
        frozenset({1}),
        date(2026, 1, 1),
        Decimal("1.2"),
        object(),
        lambda: None,
        (item for item in (1, 2)),
    ],
)
def test_unsupported_value_error(value) -> None:
    assert_writer_error(
        [{"value": value}],
        "UNSUPPORTED_VALUE:records[0].value",
    )


def test_representation_error_before_write_leaves_existing_output_unchanged(
    tmp_path,
) -> None:
    path = tmp_path / "metadata.json"
    path.write_bytes(b"keep me")

    with pytest.raises(JsonHistoricalSessionMetadataWriteError):
        write_local_historical_session_metadata(path, [{"value": b"bad"}])

    assert path.read_bytes() == b"keep me"


def test_opaque_records_and_mapping_proxy_preserved() -> None:
    records = [
        1,
        "raw",
        MappingProxyType({"nested": MappingProxyType({"ok": True})}),
        {"invalid_datetime": {"$datetime": "not-a-date"}},
    ]

    payload = json.loads(render_local_historical_session_metadata(records))

    assert payload["records"] == [
        1,
        "raw",
        {"nested": {"ok": True}},
        {"invalid_datetime": {"$datetime": "not-a-date"}},
    ]


def test_writer_output_loads_through_phase_15g_equivalent_records(tmp_path) -> None:
    records = [
        {
            "when": datetime(2026, 1, 2, 9, 30, tzinfo=UTC),
            "bad_tag": {"$datetime": "not-a-date"},
            "extra": ["kept"],
        },
        {"when": datetime(2026, 1, 3, 9, 30)},
    ]
    path = tmp_path / "metadata.json"

    write_local_historical_session_metadata(path, records)
    loaded = JsonHistoricalSessionMetadataFileSource(path).load_raw_manifest_records(
        manifest_request()
    )

    assert loaded == [
        {
            "when": datetime(2026, 1, 2, 9, 30, tzinfo=UTC),
            "bad_tag": {"$datetime": "not-a-date"},
            "extra": ["kept"],
        },
        {"when": datetime(2026, 1, 3, 9, 30)},
    ]


def test_valid_written_metadata_reaches_phase_15h_rvol_two(tmp_path) -> None:
    path = tmp_path / "metadata.json"
    write_local_historical_session_metadata(path, valid_records())
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )

    result = run_local_json_metadata_workflow_preflight(
        path,
        scenario.collection,
        scenario.manifest_request,
        scenario.current_series,
        scenario.harness_request,
    )

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


def test_incomplete_record_writes_loads_and_remains_downstream_diagnostic(
    tmp_path,
) -> None:
    records = valid_records()
    records[0] = raw_record("HIST-01", day=2, is_complete=False)
    path = tmp_path / "metadata.json"

    write_local_historical_session_metadata(path, records)
    source = JsonHistoricalSessionMetadataFileSource(path)
    load_result = load_historical_session_metadata_source(
        source,
        manifest_request(),
    )
    manifest_result = adapt_historical_session_manifest(
        load_result.raw_manifest_records,
        manifest_request(),
    )

    assert load_result.status == HistoricalSessionMetadataSourceLoadStatus.LOADED
    assert manifest_result.record_results[0].status == (
        HistoricalSessionManifestRecordStatus.INCOMPLETE_SESSION
    )


def test_source_boundary() -> None:
    source = inspect.getsource(writer_module)
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
        "collections.abc",
        "datetime",
        "json",
        "math",
        "pathlib",
        "typing",
    }

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("write_text") == 1
    forbidden_calls = {
        "JsonHistoricalSessionMetadataFileSource",
        "run_local_json_metadata_workflow_preflight",
        "load_historical_session_metadata_source",
        "load_local_historical_rvol_bundle",
        "write_local_historical_rvol_bundle",
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "mkdir",
        "touch",
        "open",
        "read_text",
        "read_bytes",
        "exists",
        "stat",
        "rename",
        "replace",
        "unlink",
        "getenv",
        "send",
    }
    assert not forbidden_calls & set(call_names)

    forbidden_modules = [
        "json_historical_session_metadata_source",
        "json_historical_rvol_bundle",
        "local_json_metadata_workflow_preflight",
        "workflow",
        "main",
        "preflight",
        "scenario",
        "catalog",
        "harness",
        "config",
        "provider",
        "readiness",
        "factory",
        "fmp",
        "alpaca",
        "http",
        "transport",
        "scanner",
        "alert",
        "voice",
        "live",
        "trading",
        "order",
        "tests",
    ]
    for module_name in imported_modules:
        for forbidden in forbidden_modules:
            assert forbidden not in module_name.lower()

    lowered = source.lower()
    for forbidden in forbidden_modules:
        assert forbidden not in lowered
