import ast
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import inspect
import json
import math
from pathlib import Path
from types import MappingProxyType

import pytest

from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
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
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSourceLoadStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayBucketStatus,
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.json_historical_rvol_bundle import (
    load_local_historical_rvol_bundle,
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
from market_sentry.data import json_historical_rvol_bundle_writer as writer_module
from market_sentry.data.json_historical_rvol_bundle_writer import (
    JsonHistoricalRvolBundleWriteError,
    render_local_historical_rvol_bundle,
    write_local_historical_rvol_bundle,
)


def dt(day: int, minute: int = 35, tz=timezone.utc) -> datetime:
    return datetime(2026, 1, day, 9, minute, tzinfo=tz)


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


def query(**overrides) -> AlpacaHistoricalBarsQuery:
    values = {
        "timeframe": "1Min",
        "start": "2026-01-02T09:30:00Z",
        "end": "2026-01-21T10:00:00Z",
        "limit": 1000,
        "page_token": None,
        "sort": "asc",
    }
    values.update(overrides)
    return AlpacaHistoricalBarsQuery(**values)


def make_inputs(*, current_volume=200, current_timestamp=None, raw_extra=None):
    raw_extra = raw_extra or {}
    first_raw_bar = raw_bar(2, 31, 25, custom="café", nested_time=dt(2, 32))
    first_raw_bar.update(raw_extra)
    first_page_bars = [first_raw_bar, raw_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page_bars.append(raw_bar(day, 35, 100))
    second_page_bars = [raw_bar(day, 35, 100) for day in range(12, 22)]

    request = HistoricalBarsPageCollectionRequest(
        symbols=("RVOL",),
        initial_query=query(),
        max_pages=5,
    )
    collection = HistoricalBarsPageCollectionResult(
        request=request,
        collected_pages=(
            HistoricalBarsCollectedPage(
                index=0,
                query=query(page_token="p0"),
                page=AlpacaHistoricalBarsPage(
                    requested_symbols=("RVOL",),
                    bars_by_symbol={"RVOL": tuple(first_page_bars)},
                    next_page_token=None,
                ),
            ),
            HistoricalBarsCollectedPage(
                index=1,
                query=query(page_token="p1"),
                page=AlpacaHistoricalBarsPage(
                    requested_symbols=("RVOL",),
                    bars_by_symbol={"RVOL": tuple(second_page_bars)},
                    next_page_token=None,
                ),
            ),
        ),
        status=HistoricalBarsPageCollectionStatus.COMPLETE,
        page_collection_complete=True,
        next_page_token=None,
        reason=None,
    )
    manifest_request = HistoricalSessionManifestRequest(
        symbol="RVOL",
        bucket="09:35",
        current_session_id="CURRENT-001",
    )
    current_series = IntradayVolumeSeriesInput(
        symbol="RVOL",
        session_id="CURRENT-001",
        bucket="09:35",
        cutoff_timestamp=dt(31),
        bars=(
            IntradayVolumeBar(
                timestamp=dt(31) if current_timestamp is None else current_timestamp,
                volume=current_volume,
            ),
        ),
    )
    harness_request = HistoricalToTodRvolRunRequest(
        symbol="RVOL",
        bucket="09:35",
        current_session_id="CURRENT-001",
        page_collection_complete=True,
        minimum_historical_sessions=20,
    )
    return collection, manifest_request, current_series, harness_request


def render_inputs(*, current_volume=200, current_timestamp=None, raw_extra=None):
    return render_local_historical_rvol_bundle(
        *make_inputs(
            current_volume=current_volume,
            current_timestamp=current_timestamp,
            raw_extra=raw_extra,
        )
    )


def test_non_path_output_raises_exact_type_error() -> None:
    with pytest.raises(TypeError) as exc_info:
        write_local_historical_rvol_bundle("bundle.json", *make_inputs())  # type: ignore[arg-type]

    assert str(exc_info.value) == "path must be a pathlib.Path."


def test_canonical_renderer_returns_valid_deterministic_json() -> None:
    rendered = render_inputs()
    repeated = render_inputs()

    assert rendered == repeated
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")
    assert "café" in rendered
    assert "\\u00e9" not in rendered
    payload = json.loads(rendered)
    assert set(payload) == {
        "schema_version",
        "collection",
        "manifest_request",
        "current_series",
        "harness_request",
    }
    assert payload["schema_version"] == 1
    assert payload["collection"]["request"]["symbols"] == ["RVOL"]
    assert payload["collection"]["page_collection_complete"] is True
    assert payload["manifest_request"] == {
        "symbol": "RVOL",
        "bucket": "09:35",
        "current_session_id": "CURRENT-001",
    }
    assert payload["current_series"]["bars"][0]["volume"] == 200
    assert payload["harness_request"]["minimum_historical_sessions"] == 20
    assert rendered == json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def test_writer_writes_exact_rendered_utf8_text_once(monkeypatch, tmp_path) -> None:
    path = tmp_path / "bundle.json"
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
    result = write_local_historical_rvol_bundle(path, *make_inputs())

    assert result is None
    assert calls == [(path, render_inputs(), "utf-8")]
    assert path.read_text(encoding="utf-8") == render_inputs()


def test_writer_does_not_read_back(monkeypatch, tmp_path) -> None:
    path = tmp_path / "bundle.json"

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

    write_local_historical_rvol_bundle(path, *make_inputs())

    assert path.exists()


def test_writer_does_not_create_parent_directory(tmp_path) -> None:
    path = tmp_path / "missing-parent" / "bundle.json"

    with pytest.raises(FileNotFoundError):
        write_local_historical_rvol_bundle(path, *make_inputs())

    assert not (tmp_path / "missing-parent").exists()


def test_fresh_repeated_writes_do_not_use_cached_source_data(tmp_path) -> None:
    path = tmp_path / "bundle.json"
    first = make_inputs()
    second = make_inputs(current_volume=300)

    write_local_historical_rvol_bundle(path, *first)
    first_text = path.read_text(encoding="utf-8")
    write_local_historical_rvol_bundle(path, *second)
    second_text = path.read_text(encoding="utf-8")

    assert first_text != second_text
    assert '"volume": 200' in first_text
    assert '"volume": 300' in second_text


def test_datetime_values_encode_recursively() -> None:
    fixed = timezone(timedelta(hours=-5))
    rendered = render_inputs(
        current_timestamp=datetime(2026, 1, 31, 9, 34, tzinfo=fixed),
        raw_extra={
            "naive": datetime(2026, 1, 2, 9, 33),
            "utc": datetime(2026, 1, 2, 9, 34, tzinfo=timezone.utc),
            "fixed": datetime(2026, 1, 2, 9, 35, tzinfo=fixed),
        },
    )
    payload = json.loads(rendered)
    raw = payload["collection"]["collected_pages"][0]["page"]["bars_by_symbol"][
        "RVOL"
    ][0]

    assert raw["naive"] == {"$datetime": "2026-01-02T09:33:00"}
    assert raw["utc"] == {"$datetime": "2026-01-02T09:34:00Z"}
    assert raw["fixed"] == {"$datetime": "2026-01-02T09:35:00-05:00"}
    assert payload["current_series"]["bars"][0]["timestamp"] == {
        "$datetime": "2026-01-31T09:34:00-05:00"
    }


def test_raw_values_and_invalid_current_values_survive_writer_and_loader(tmp_path) -> None:
    invalid_timestamp = {"$datetime": "not-a-date"}
    collection, manifest_request, current_series, harness_request = make_inputs(
        current_volume=False,
        current_timestamp=invalid_timestamp,
        raw_extra={
            "v": False,
            "custom_mapping": {"$datetime": "bad"},
            "extra_datetime_mapping": {
                "$datetime": "2026-01-02T09:34:00Z",
                "extra": True,
            },
        },
    )
    path = tmp_path / "bundle.json"

    write_local_historical_rvol_bundle(
        path,
        collection,
        manifest_request,
        current_series,
        harness_request,
    )
    loaded = load_local_historical_rvol_bundle(path)
    loaded_raw = loaded.collection.collected_pages[0].page.bars_by_symbol["RVOL"][0]

    assert loaded_raw["v"] is False
    assert loaded_raw["custom_mapping"] == {"$datetime": "bad"}
    assert loaded_raw["extra_datetime_mapping"] == {
        "$datetime": "2026-01-02T09:34:00Z",
        "extra": True,
    }
    assert loaded.current_series.bars[0].timestamp == invalid_timestamp
    assert loaded.current_series.bars[0].volume is False


def assert_write_error(raw_extra, expected: str) -> None:
    with pytest.raises(JsonHistoricalRvolBundleWriteError) as exc_info:
        render_inputs(raw_extra=raw_extra)
    assert str(exc_info.value) == expected


def test_non_string_mapping_key_error() -> None:
    assert_write_error(
        {1: "bad"},
        "INVALID_MAPPING_KEY:.collection.collected_pages[0].page.bars_by_symbol.RVOL[0]",
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_float_error(value) -> None:
    assert_write_error(
        {"bad": value},
        "NON_FINITE_FLOAT:.collection.collected_pages[0].page.bars_by_symbol.RVOL[0].bad",
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
def test_unsupported_value_errors(value) -> None:
    assert_write_error(
        {"bad": value},
        "UNSUPPORTED_VALUE:.collection.collected_pages[0].page.bars_by_symbol.RVOL[0].bad",
    )


def test_representation_error_before_write_leaves_existing_output_unchanged(
    tmp_path,
) -> None:
    path = tmp_path / "bundle.json"
    path.write_bytes(b"keep me")

    with pytest.raises(JsonHistoricalRvolBundleWriteError):
        write_local_historical_rvol_bundle(path, *make_inputs(raw_extra={"bad": b"x"}))

    assert path.read_bytes() == b"keep me"


def test_filesystem_errors_propagate_unchanged(monkeypatch, tmp_path) -> None:
    path = tmp_path / "bundle.json"
    error = IsADirectoryError("directory")

    def fake_write_text(self, data, *, encoding=None):
        raise error

    monkeypatch.setattr(Path, "write_text", fake_write_text)

    with pytest.raises(IsADirectoryError) as exc_info:
        write_local_historical_rvol_bundle(path, *make_inputs())

    assert exc_info.value is error


def test_writer_output_loads_into_value_equivalent_typed_inputs(tmp_path) -> None:
    expected = make_inputs()
    path = tmp_path / "bundle.json"

    write_local_historical_rvol_bundle(path, *expected)
    loaded = load_local_historical_rvol_bundle(path)

    assert path.read_text(encoding="utf-8") == render_local_historical_rvol_bundle(
        *expected
    )
    assert loaded.collection == expected[0]
    assert loaded.manifest_request == expected[1]
    assert loaded.current_series == expected[2]
    assert loaded.harness_request == expected[3]


def test_writer_output_with_valid_metadata_reaches_phase_15h_rvol_two(
    tmp_path,
) -> None:
    metadata = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_bytes(metadata.fixture_bytes)
    bundle_path = tmp_path / "bundle.json"
    write_local_historical_rvol_bundle(bundle_path, *make_inputs())

    loaded = load_local_historical_rvol_bundle(bundle_path)
    result = run_local_json_metadata_workflow_preflight(
        metadata_path,
        loaded.collection,
        loaded.manifest_request,
        loaded.current_series,
        loaded.harness_request,
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


def test_invalid_current_volume_false_reaches_downstream_diagnostics(
    tmp_path,
) -> None:
    metadata = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_bytes(metadata.fixture_bytes)
    bundle_path = tmp_path / "bundle.json"
    write_local_historical_rvol_bundle(
        bundle_path,
        *make_inputs(current_volume=False),
    )
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


def test_mapping_proxy_values_are_supported() -> None:
    rendered = render_inputs(raw_extra={"proxy": MappingProxyType({"ok": True})})
    payload = json.loads(rendered)

    raw = payload["collection"]["collected_pages"][0]["page"]["bars_by_symbol"][
        "RVOL"
    ][0]
    assert raw["proxy"] == {"ok": True}


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
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.historical_bars_page_collector",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.historical_tod_rvol_harness",
        "market_sentry.data.intraday_bucket_adapter",
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
        "load_local_historical_rvol_bundle",
        "run_local_json_metadata_workflow_preflight",
        "run_metadata_loaded_historical_workflow",
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "mkdir",
        "read_text",
        "read_bytes",
        "getenv",
        "open",
        "urlopen",
        "send",
    }
    assert not forbidden_calls & set(call_names)

    forbidden_terms = [
        "json_historical_rvol_bundle",
        "local_json_metadata_workflow_preflight",
        "workflow",
        "metadata_source",
        "main",
        "local_json_preflight",
        "local_json_bundle_preflight",
        "scenario",
        "catalog",
        "tests",
        "config",
        "provider",
        "factory",
        "readiness",
        "scanner",
        "alerts",
        "voice",
        "http",
        "transport",
        "live",
        "trading",
        "cache",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
