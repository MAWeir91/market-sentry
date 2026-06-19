import ast
import inspect
from pathlib import Path

import pytest

from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    get_local_json_metadata_preflight_scenario,
)
from market_sentry.data.local_json_metadata_preflight_scenario_harness import (
    run_local_json_metadata_preflight_scenario,
)
from market_sentry.local_json_preflight_cli import (
    LOCAL_JSON_PREFLIGHT_NOTE,
    PROFILE_NAME,
    is_manual_local_json_preflight_success,
    render_manual_local_json_preflight_error,
    render_manual_local_json_preflight_report,
    run_manual_local_json_preflight,
)
from market_sentry import local_json_preflight_cli as helper


class ProbeScenario:
    def __init__(self, name: str) -> None:
        self.name = name
        self.fixture_reads = 0
        self.collection = object()
        self.manifest_request = object()
        self.current_series = object()
        self.harness_request = object()

    @property
    def fixture_bytes(self):
        self.fixture_reads += 1
        raise AssertionError("fixture_bytes should not be read")


def scenario_result(tmp_path, name):
    scenario = get_local_json_metadata_preflight_scenario(name)
    return run_local_json_metadata_preflight_scenario(
        scenario,
        tmp_path / f"{name}.json",
    ).result


def test_helper_looks_up_valid_profile_and_calls_phase_15h_once(monkeypatch, tmp_path):
    path = tmp_path / "metadata.json"
    scenario = ProbeScenario(PROFILE_NAME)
    workflow_result = object()
    lookups = []
    calls = []

    def fake_lookup(name):
        lookups.append(name)
        return scenario

    def fake_preflight(path_arg, collection_arg, request_arg, series_arg, harness_arg):
        calls.append((path_arg, collection_arg, request_arg, series_arg, harness_arg))
        return workflow_result

    monkeypatch.setattr(helper, "get_local_json_metadata_preflight_scenario", fake_lookup)
    monkeypatch.setattr(helper, "run_local_json_metadata_workflow_preflight", fake_preflight)

    result = run_manual_local_json_preflight(path)

    assert result is workflow_result
    assert lookups == [PROFILE_NAME]
    assert calls == [
        (
            path,
            scenario.collection,
            scenario.manifest_request,
            scenario.current_series,
            scenario.harness_request,
        )
    ]
    assert scenario.fixture_reads == 0


def test_helper_gets_fresh_profile_for_each_call(monkeypatch, tmp_path):
    path = tmp_path / "metadata.json"
    scenarios = [ProbeScenario(PROFILE_NAME), ProbeScenario(PROFILE_NAME)]
    results = [object(), object()]
    calls = []

    def fake_lookup(name):
        assert name == PROFILE_NAME
        return scenarios.pop(0)

    def fake_preflight(path_arg, collection_arg, request_arg, series_arg, harness_arg):
        calls.append((path_arg, collection_arg, request_arg, series_arg, harness_arg))
        return results.pop(0)

    monkeypatch.setattr(helper, "get_local_json_metadata_preflight_scenario", fake_lookup)
    monkeypatch.setattr(helper, "run_local_json_metadata_workflow_preflight", fake_preflight)

    first = run_manual_local_json_preflight(path)
    second = run_manual_local_json_preflight(path)

    assert first is not second
    assert len(calls) == 2
    assert calls[0][1] is not calls[1][1]


def test_helper_exceptions_propagate_unchanged(monkeypatch, tmp_path):
    error = ValueError("boom")

    def fake_lookup(_name):
        raise error

    monkeypatch.setattr(helper, "get_local_json_metadata_preflight_scenario", fake_lookup)

    with pytest.raises(ValueError) as exc_info:
        run_manual_local_json_preflight(tmp_path / "metadata.json")

    assert exc_info.value is error


def test_success_report_renders_required_order_note_and_rvol(tmp_path):
    path = tmp_path / "valid.json"
    result = scenario_result(tmp_path, "valid_json_complete_multi_page")

    report = render_manual_local_json_preflight_report(path, result)

    expected_lines = [
        "Market Sentry Local JSON Preflight",
        f"Path: {path}",
        "Profile: valid_json_complete_multi_page",
        "Metadata Load: LOADED",
        "Metadata Load Reason: N/A",
        "Workflow: WORKFLOW_BRIDGE_RAN",
        "Workflow Reason: N/A",
        "Bridge: WORKFLOW_RAN",
        "Bridge Reason: N/A",
        "Composition: COMPOSED",
        "Coordinator: OK",
        "Coordinator Reason: N/A",
        "Manifest: OK",
        "Manifest Reason: N/A",
        "Harness: OK",
        "Harness Reason: N/A",
        "Final: OK",
        "Final Reason: N/A",
        "Time-of-Day RVOL: OK",
        "Time-of-Day RVOL Reason: N/A",
        "Relative Volume: 2.0x",
        LOCAL_JSON_PREFLIGHT_NOTE,
    ]
    assert report.splitlines() == expected_lines
    assert "placeholder" not in report.lower()
    assert "provider" in report
    assert "api_key" not in report.lower()


def test_partial_manifest_report_renders_nested_non_ok_status(tmp_path):
    result = scenario_result(tmp_path, "partial_manifest_json_complete_multi_page")

    report = render_manual_local_json_preflight_report(tmp_path / "partial.json", result)

    assert "Coordinator: MANIFEST_PARTIAL" in report
    assert "Coordinator Reason: MANIFEST_PARTIAL" in report
    assert "Manifest: PARTIAL" in report
    assert "Manifest Reason: PARTIAL" in report
    assert "Relative Volume: 2.0x" in report


def test_non_composable_report_renders_na_for_unreachable_artifacts(tmp_path):
    result = scenario_result(tmp_path, "page_cap_json_collection_not_composable")

    report = render_manual_local_json_preflight_report(tmp_path / "cap.json", result)

    assert "Bridge: COLLECTION_NOT_COMPOSABLE" in report
    assert "Bridge Reason: COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION" in report
    assert "Composition: INCOMPLETE_COLLECTION" in report
    assert "Coordinator: N/A" in report
    assert "Manifest: N/A" in report
    assert "Harness: N/A" in report
    assert "Relative Volume: N/A" in report


def test_error_report_is_stable_and_secret_safe(tmp_path):
    path = tmp_path / "missing.json"

    report = render_manual_local_json_preflight_error(path, FileNotFoundError())

    assert report.splitlines() == [
        "Market Sentry Local JSON Preflight",
        f"Path: {path}",
        "Result: ERROR",
        "Error Type: FileNotFoundError",
        "Error: FileNotFoundError",
        LOCAL_JSON_PREFLIGHT_NOTE,
    ]
    assert "traceback" not in report.lower()
    assert "api_key" not in report.lower()


def test_success_predicate_only_accepts_full_ok(tmp_path):
    assert is_manual_local_json_preflight_success(
        scenario_result(tmp_path, "valid_json_complete_multi_page")
    )
    assert not is_manual_local_json_preflight_success(
        scenario_result(tmp_path, "partial_manifest_json_complete_multi_page")
    )
    assert not is_manual_local_json_preflight_success(
        scenario_result(tmp_path, "invalid_cutoff_datetime_json")
    )
    assert not is_manual_local_json_preflight_success(
        scenario_result(tmp_path, "page_cap_json_collection_not_composable")
    )


def test_success_predicate_rejects_missing_tod_or_relative_volume(tmp_path):
    assert not is_manual_local_json_preflight_success(
        scenario_result(tmp_path, "empty_records_json")
    )
    assert not is_manual_local_json_preflight_success(
        scenario_result(tmp_path, "invalid_current_volume_json")
    )


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
        "__future__",
        "json",
        "pathlib",
        "market_sentry.data.json_historical_session_metadata_source",
        "market_sentry.data.local_json_metadata_preflight_scenario_catalog",
        "market_sentry.data.local_json_metadata_workflow_preflight",
    }

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert imported_names == {
        "annotations",
        "Path",
        "JsonHistoricalSessionMetadataFileSourceError",
        "get_local_json_metadata_preflight_scenario",
        "LocalJsonMetadataWorkflowPreflightResult",
        "run_local_json_metadata_workflow_preflight",
    }
    assert "JsonHistoricalSessionMetadataFileSource" not in imported_names

    call_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)

    assert "get_local_json_metadata_preflight_scenario" in call_names
    assert "run_local_json_metadata_workflow_preflight" in call_names
    forbidden_calls = {
        "write_bytes",
        "read_bytes",
        "loads",
        "load_raw_manifest_records",
        "run_metadata_loaded_historical_workflow",
        "run_collected_pages_to_manifest_workflow",
        "adapt_historical_session_manifest",
    }
    assert not forbidden_calls & call_names

    forbidden_terms = [
        "market_sentry.main",
        "config",
        "transport",
        "http",
        "local_json_metadata_preflight_scenario_harness",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
