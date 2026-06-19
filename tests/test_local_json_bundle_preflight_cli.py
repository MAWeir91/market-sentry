import ast
from dataclasses import FrozenInstanceError
import inspect
import json

import pytest

from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.intraday_bucket_adapter import IntradayBucketStatus
from market_sentry.data.json_historical_rvol_bundle import LocalHistoricalRvolBundle
from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    get_local_json_metadata_preflight_scenario,
)
from market_sentry import local_json_bundle_preflight_cli as helper
from market_sentry.local_json_bundle_preflight_cli import (
    LOCAL_JSON_BUNDLE_PREFLIGHT_NOTE,
    ManualLocalJsonBundlePreflightResult,
    is_manual_local_json_bundle_preflight_success,
    render_manual_local_json_bundle_preflight_error,
    render_manual_local_json_bundle_preflight_report,
    run_manual_local_json_bundle_preflight,
)


def dt_tag(day: int, minute: int = 35) -> dict[str, str]:
    return {"$datetime": f"2026-01-{day:02d}T09:{minute:02d}:00Z"}


def raw_bar(day: int, minute: int, volume: int) -> dict[str, object]:
    return {
        "t": f"2026-01-{day:02d}T09:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "h": 1.0,
        "l": 1.0,
        "c": 1.0,
    }


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


def base_bundle_payload() -> dict[str, object]:
    first_page_bars = [raw_bar(2, 31, 25)]
    second_page_bars = [raw_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page_bars.append(raw_bar(day, 35, 100))
    for day in range(12, 22):
        second_page_bars.append(raw_bar(day, 35, 100))
    return {
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
            "bars": [{"timestamp": dt_tag(31), "volume": 200}],
        },
        "harness_request": {
            "symbol": "RVOL",
            "bucket": "09:35",
            "current_session_id": "CURRENT-001",
            "page_collection_complete": True,
            "minimum_historical_sessions": 20,
        },
    }


def write_bundle(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_helper_loads_bundle_once_then_calls_phase_15h_once(monkeypatch) -> None:
    metadata_path = object()
    bundle_path = object()
    bundle = LocalHistoricalRvolBundle(
        path=bundle_path,
        collection=object(),
        manifest_request=object(),
        current_series=object(),
        harness_request=object(),
    )
    preflight_result = object()
    calls = []

    def fake_load(path):
        calls.append(("load", path))
        return bundle

    def fake_preflight(metadata, collection, manifest, current, harness):
        calls.append(("preflight", metadata, collection, manifest, current, harness))
        return preflight_result

    monkeypatch.setattr(helper, "load_local_historical_rvol_bundle", fake_load)
    monkeypatch.setattr(
        helper,
        "run_local_json_metadata_workflow_preflight",
        fake_preflight,
    )

    result = run_manual_local_json_bundle_preflight(metadata_path, bundle_path)

    assert calls == [
        ("load", bundle_path),
        (
            "preflight",
            metadata_path,
            bundle.collection,
            bundle.manifest_request,
            bundle.current_series,
            bundle.harness_request,
        ),
    ]
    assert result.metadata_path is metadata_path
    assert result.bundle_path is bundle_path
    assert result.bundle is bundle
    assert result.preflight_result is preflight_result
    with pytest.raises(FrozenInstanceError):
        result.bundle = object()  # type: ignore[misc]


def test_bundle_loader_failure_propagates_and_skips_phase_15h(monkeypatch) -> None:
    error = ValueError("bundle failed")

    def fake_load(_path):
        raise error

    monkeypatch.setattr(helper, "load_local_historical_rvol_bundle", fake_load)
    monkeypatch.setattr(
        helper,
        "run_local_json_metadata_workflow_preflight",
        lambda *_args: pytest.fail("Phase 15H should not run"),
    )

    with pytest.raises(ValueError) as exc_info:
        run_manual_local_json_bundle_preflight(object(), object())

    assert exc_info.value is error


def test_phase_15h_failure_propagates(monkeypatch) -> None:
    bundle = LocalHistoricalRvolBundle(
        path=object(),
        collection=object(),
        manifest_request=object(),
        current_series=object(),
        harness_request=object(),
    )
    error = RuntimeError("phase 15h failed")
    monkeypatch.setattr(
        helper,
        "load_local_historical_rvol_bundle",
        lambda _path: bundle,
    )
    monkeypatch.setattr(
        helper,
        "run_local_json_metadata_workflow_preflight",
        lambda *_args: (_ for _ in ()).throw(error),
    )

    with pytest.raises(RuntimeError) as exc_info:
        run_manual_local_json_bundle_preflight(object(), object())

    assert exc_info.value is error


def test_actual_valid_bundle_report_and_success(tmp_path) -> None:
    metadata = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    metadata_path = tmp_path / "metadata.json"
    bundle_path = tmp_path / "bundle.json"
    metadata_path.write_bytes(metadata.fixture_bytes)
    write_bundle(bundle_path, base_bundle_payload())

    result = run_manual_local_json_bundle_preflight(metadata_path, bundle_path)
    report = render_manual_local_json_bundle_preflight_report(
        metadata_path,
        bundle_path,
        result,
    )

    assert is_manual_local_json_bundle_preflight_success(result) is True
    assert "Market Sentry Local JSON Bundle Preflight" in report
    assert f"Metadata Path: {metadata_path}" in report
    assert f"Bundle Path: {bundle_path}" in report
    assert "Input Mode: EXPLICIT_LOCAL_BUNDLE" in report
    assert "Profile:" not in report
    assert "Metadata Load: LOADED" in report
    assert "Composition: COMPOSED" in report
    assert "Coordinator: OK" in report
    assert "Final: OK" in report
    assert "Relative Volume: 2.0x" in report
    assert LOCAL_JSON_BUNDLE_PREFLIGHT_NOTE in report


def test_actual_invalid_current_volume_reaches_downstream_diagnostics(tmp_path) -> None:
    metadata = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    payload = base_bundle_payload()
    payload["current_series"]["bars"][0]["volume"] = False
    metadata_path = tmp_path / "metadata.json"
    bundle_path = tmp_path / "bundle.json"
    metadata_path.write_bytes(metadata.fixture_bytes)
    write_bundle(bundle_path, payload)

    result = run_manual_local_json_bundle_preflight(metadata_path, bundle_path)
    report = render_manual_local_json_bundle_preflight_report(
        metadata_path,
        bundle_path,
        result,
    )

    assert is_manual_local_json_bundle_preflight_success(result) is False
    assert "Final: CURRENT_CUMULATIVE_VOLUME_FAILED" in report
    final = (
        result.preflight_result.workflow_result.workflow_bridge_result.workflow_result
        .harness_result.final_result
    )
    assert final.status == (
        CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
    )
    assert final.current_result.status == IntradayBucketStatus.INVALID_INTRADAY_VOLUME


def test_error_report_formatting_is_stable(tmp_path) -> None:
    metadata_path = tmp_path / "metadata.json"
    bundle_path = tmp_path / "bundle.json"

    rendered = render_manual_local_json_bundle_preflight_error(
        metadata_path,
        bundle_path,
        json.JSONDecodeError("bad", "{}", 0),
    )

    assert rendered.splitlines() == [
        "Market Sentry Local JSON Bundle Preflight",
        f"Metadata Path: {metadata_path}",
        f"Bundle Path: {bundle_path}",
        "Result: ERROR",
        "Error Type: JSONDecodeError",
        "Error: bad: line 1 column 1 (char 0)",
        LOCAL_JSON_BUNDLE_PREFLIGHT_NOTE,
    ]


def test_error_report_empty_message_falls_back_to_class_name(tmp_path) -> None:
    rendered = render_manual_local_json_bundle_preflight_error(
        tmp_path / "metadata.json",
        tmp_path / "bundle.json",
        OSError(),
    )

    assert "Error Type: OSError" in rendered
    assert "Error: OSError" in rendered


def test_success_predicate_rejects_non_ok_result(tmp_path) -> None:
    metadata = get_local_json_metadata_preflight_scenario("empty_records_json")
    metadata_path = tmp_path / "metadata.json"
    bundle_path = tmp_path / "bundle.json"
    metadata_path.write_bytes(metadata.fixture_bytes)
    write_bundle(bundle_path, base_bundle_payload())

    result = run_manual_local_json_bundle_preflight(metadata_path, bundle_path)

    assert is_manual_local_json_bundle_preflight_success(result) is False


def test_helper_source_boundary() -> None:
    source = inspect.getsource(helper)
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
        "dataclasses",
        "json",
        "pathlib",
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.json_historical_rvol_bundle",
        "market_sentry.data.json_historical_session_metadata_source",
        "market_sentry.data.local_json_metadata_workflow_preflight",
    }

    forbidden_terms = [
        "local_json_preflight_cli",
        "local_json_preflight_report_export",
        "local_json_metadata_preflight_scenario",
        "main",
        "argparse",
        "factory",
        "readiness",
        "http",
        "transport",
        "trading",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
