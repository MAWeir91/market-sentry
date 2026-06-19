import ast
from dataclasses import FrozenInstanceError
import inspect

import pytest

from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRecordStatus,
    HistoricalSessionManifestStatus,
)
from market_sentry.data.intraday_bucket_adapter import IntradayBucketStatus
from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    LocalJsonMetadataPreflightScenario,
    get_local_json_metadata_preflight_scenario,
    get_local_json_metadata_preflight_scenarios,
)
from market_sentry.data.local_json_metadata_preflight_scenario_harness import (
    run_local_json_metadata_preflight_scenario,
)
from market_sentry.data import local_json_metadata_preflight_scenario_harness as harness


class RecordingPath:
    def __init__(self, calls) -> None:
        self.calls = calls

    def write_bytes(self, value):
        self.calls.append(("write", self, value))
        return len(value)


def make_scenario(*, fixture_bytes=b"payload") -> LocalJsonMetadataPreflightScenario:
    return LocalJsonMetadataPreflightScenario(
        name="unit",
        fixture_bytes=fixture_bytes,
        collection=object(),
        manifest_request=object(),
        current_series=object(),
        harness_request=object(),
        expected_exception_type=None,
        expected_exception_message=None,
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


def test_harness_writes_fixture_then_calls_preflight_and_retains_identity(monkeypatch):
    calls = []
    scenario = make_scenario(fixture_bytes=b"fixture")
    path = RecordingPath(calls)
    preflight_result = object()

    def fake_preflight(path_arg, collection_arg, request_arg, series_arg, harness_arg):
        calls.append(("preflight", path_arg, collection_arg, request_arg, series_arg, harness_arg))
        assert path_arg is path
        assert collection_arg is scenario.collection
        assert request_arg is scenario.manifest_request
        assert series_arg is scenario.current_series
        assert harness_arg is scenario.harness_request
        return preflight_result

    monkeypatch.setattr(
        harness,
        "run_local_json_metadata_workflow_preflight",
        fake_preflight,
    )

    run = harness.run_local_json_metadata_preflight_scenario(scenario, path)

    assert calls == [
        ("write", path, b"fixture"),
        (
            "preflight",
            path,
            scenario.collection,
            scenario.manifest_request,
            scenario.current_series,
            scenario.harness_request,
        ),
    ]
    assert run.scenario is scenario
    assert run.path is path
    assert run.result is preflight_result
    with pytest.raises(FrozenInstanceError):
        run.result = object()  # type: ignore[misc]


def test_harness_skips_write_when_fixture_bytes_are_none(monkeypatch):
    calls = []
    scenario = make_scenario(fixture_bytes=None)
    path = RecordingPath(calls)
    preflight_result = object()

    def fake_preflight(*args):
        calls.append(("preflight",) + args)
        return preflight_result

    monkeypatch.setattr(
        harness,
        "run_local_json_metadata_workflow_preflight",
        fake_preflight,
    )

    run = harness.run_local_json_metadata_preflight_scenario(scenario, path)

    assert calls == [
        (
            "preflight",
            path,
            scenario.collection,
            scenario.manifest_request,
            scenario.current_series,
            scenario.harness_request,
        )
    ]
    assert run.result is preflight_result


def test_harness_returns_fresh_wrappers_on_separate_successful_calls(monkeypatch):
    scenario = make_scenario()
    first_path = RecordingPath([])
    second_path = RecordingPath([])
    results = [object(), object()]

    def fake_preflight(*args):
        return results.pop(0)

    monkeypatch.setattr(
        harness,
        "run_local_json_metadata_workflow_preflight",
        fake_preflight,
    )

    first = harness.run_local_json_metadata_preflight_scenario(scenario, first_path)
    second = harness.run_local_json_metadata_preflight_scenario(scenario, second_path)

    assert first is not second
    assert first.scenario is scenario
    assert second.scenario is scenario
    assert first.path is first_path
    assert second.path is second_path
    assert first.result is not second.result


def test_harness_preflight_exception_propagates_unchanged(monkeypatch):
    scenario = make_scenario()
    path = RecordingPath([])
    error = ValueError("preflight failed")

    def fake_preflight(*args):
        raise error

    monkeypatch.setattr(
        harness,
        "run_local_json_metadata_workflow_preflight",
        fake_preflight,
    )

    with pytest.raises(ValueError) as exc_info:
        harness.run_local_json_metadata_preflight_scenario(scenario, path)

    assert exc_info.value is error


def assert_expected_result(scenario, run) -> None:
    workflow_result = run.result.workflow_result
    assert workflow_result.metadata_load_result.status == (
        scenario.expected_metadata_load_status
    )
    assert workflow_result.status == scenario.expected_outer_status
    assert workflow_result.reason == scenario.expected_outer_reason

    bridge = workflow_result.workflow_bridge_result
    assert bridge is not None
    assert bridge.status == scenario.expected_bridge_status
    assert bridge.reason == scenario.expected_bridge_reason
    assert bridge.composition_result.status == scenario.expected_composition_status

    if scenario.expected_coordinator_status is None:
        assert bridge.workflow_result is None
        return

    coordinator = bridge.workflow_result
    assert coordinator is not None
    assert coordinator.status == scenario.expected_coordinator_status
    assert coordinator.manifest_result.status == scenario.expected_manifest_status
    assert coordinator.harness_result.status == scenario.expected_harness_status
    assert coordinator.harness_result.final_result.status == (
        scenario.expected_final_status
    )
    time_of_day_result = coordinator.harness_result.final_result.time_of_day_result
    if scenario.expected_time_of_day_status is None:
        assert time_of_day_result is None
    else:
        assert time_of_day_result is not None
        assert time_of_day_result.status == scenario.expected_time_of_day_status
        assert time_of_day_result.relative_volume == scenario.expected_relative_volume


def test_all_catalog_scenarios_run_through_real_harness_and_phase_15h(tmp_path) -> None:
    for scenario in get_local_json_metadata_preflight_scenarios():
        path = tmp_path / f"{scenario.name}.json"

        if scenario.expected_exception_type is not None:
            run = None
            with pytest.raises(scenario.expected_exception_type) as exc_info:
                run = run_local_json_metadata_preflight_scenario(scenario, path)
            assert run is None
            if scenario.expected_exception_message is not None:
                assert str(exc_info.value) == scenario.expected_exception_message
            if scenario.name == "missing_json_file_error":
                assert not path.exists()
            continue

        run = run_local_json_metadata_preflight_scenario(scenario, path)
        assert run.scenario is scenario
        assert run.path is path
        assert run.result.path is path
        assert run.result.metadata_source.path is path
        assert_expected_result(scenario, run)


def test_valid_scenario_targeted_split_session_and_rvol(tmp_path) -> None:
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )

    run = run_local_json_metadata_preflight_scenario(
        scenario,
        tmp_path / "valid.json",
    )
    coordinator = run.result.workflow_result.workflow_bridge_result.workflow_result

    assert coordinator.harness_result.assembly_results[0].in_window_raw_bar_count == 2
    assert (
        coordinator.harness_result.final_result.time_of_day_result.relative_volume
        == 2.0
    )


def test_partial_manifest_targeted_extra_record_and_rvol(tmp_path) -> None:
    scenario = get_local_json_metadata_preflight_scenario(
        "partial_manifest_json_complete_multi_page"
    )

    run = run_local_json_metadata_preflight_scenario(
        scenario,
        tmp_path / "partial.json",
    )
    manifest = (
        run.result.workflow_result.workflow_bridge_result.workflow_result.manifest_result
    )
    final_result = (
        run.result.workflow_result.workflow_bridge_result.workflow_result.harness_result.final_result
    )

    assert manifest.record_results[-1].status == (
        HistoricalSessionManifestRecordStatus.MISSING_REQUIRED_FIELD
    )
    assert manifest.valid_record_count == 20
    assert len(manifest.metadata_records) == 20
    assert final_result.time_of_day_result.relative_volume == 2.0


def test_invalid_cutoff_targeted_manifest_and_baseline_failure(tmp_path) -> None:
    scenario = get_local_json_metadata_preflight_scenario(
        "invalid_cutoff_datetime_json"
    )

    run = run_local_json_metadata_preflight_scenario(
        scenario,
        tmp_path / "invalid-cutoff.json",
    )
    coordinator = run.result.workflow_result.workflow_bridge_result.workflow_result
    manifest = coordinator.manifest_result
    final_result = coordinator.harness_result.final_result

    assert manifest.record_results[0].status == (
        HistoricalSessionManifestRecordStatus.INVALID_CUTOFF_TIMESTAMP
    )
    assert manifest.valid_record_count == 19
    assert len(manifest.metadata_records) == 19
    assert final_result.status == scenario.expected_final_status
    assert final_result.time_of_day_result is None


def test_empty_records_targeted_source_load_and_manifest_failure(tmp_path) -> None:
    scenario = get_local_json_metadata_preflight_scenario("empty_records_json")

    run = run_local_json_metadata_preflight_scenario(
        scenario,
        tmp_path / "empty.json",
    )
    workflow_result = run.result.workflow_result
    manifest = workflow_result.workflow_bridge_result.workflow_result.manifest_result

    assert workflow_result.metadata_load_result.status == (
        scenario.expected_metadata_load_status
    )
    assert manifest.status == HistoricalSessionManifestStatus.NO_VALID_METADATA


@pytest.mark.parametrize(
    "name",
    [
        "page_cap_json_collection_not_composable",
        "repeated_token_json_collection_not_composable",
    ],
)
def test_non_composable_targets_retain_incomplete_collection(name, tmp_path) -> None:
    scenario = get_local_json_metadata_preflight_scenario(name)

    run = run_local_json_metadata_preflight_scenario(
        scenario,
        tmp_path / f"{name}.json",
    )
    bridge = run.result.workflow_result.workflow_bridge_result

    assert bridge.workflow_result is None
    assert bridge.composition_result.status == (
        CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION
    )
    assert bridge.reason == "COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION"


def test_invalid_manifest_request_targeted_nested_failure(tmp_path) -> None:
    scenario = get_local_json_metadata_preflight_scenario(
        "invalid_manifest_request_json"
    )

    run = run_local_json_metadata_preflight_scenario(
        scenario,
        tmp_path / "bad-request.json",
    )
    workflow_result = run.result.workflow_result
    manifest = workflow_result.workflow_bridge_result.workflow_result.manifest_result

    assert workflow_result.metadata_load_result.status == (
        scenario.expected_metadata_load_status
    )
    assert manifest.status == HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL


def test_invalid_current_volume_targeted_nested_intraday_failure(tmp_path) -> None:
    scenario = get_local_json_metadata_preflight_scenario(
        "invalid_current_volume_json"
    )

    run = run_local_json_metadata_preflight_scenario(
        scenario,
        tmp_path / "bad-current.json",
    )
    current_result = (
        run.result.workflow_result.workflow_bridge_result.workflow_result.harness_result.final_result.current_result
    )

    assert current_result is not None
    assert current_result.status == IntradayBucketStatus.INVALID_INTRADAY_VOLUME


def test_source_error_scenarios_do_not_return_wrappers(tmp_path) -> None:
    names = [
        "unsupported_schema_json_error",
        "malformed_json_error",
        "invalid_utf8_json_error",
        "missing_json_file_error",
    ]
    for name in names:
        scenario = get_local_json_metadata_preflight_scenario(name)
        path = tmp_path / f"{name}.json"
        run = None

        with pytest.raises(scenario.expected_exception_type):
            run = run_local_json_metadata_preflight_scenario(scenario, path)

        assert run is None


def test_harness_source_boundary() -> None:
    source = inspect.getsource(harness)
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
        "dataclasses",
        "pathlib",
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
        "dataclass",
        "Path",
        "LocalJsonMetadataPreflightScenario",
        "LocalJsonMetadataWorkflowPreflightResult",
        "run_local_json_metadata_workflow_preflight",
    }

    call_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)

    assert call_names == {
        "dataclass",
        "write_bytes",
        "run_local_json_metadata_workflow_preflight",
        "LocalJsonMetadataPreflightScenarioRun",
    }

    forbidden_terms = [
        "json.loads",
        "JsonHistoricalSessionMetadataFileSource",
        "load_historical_session_metadata_source",
        "run_metadata_loaded_historical_workflow",
        "run_collected_pages_to_manifest_workflow",
        "compose_collected_historical_pages",
        "run_manifest_to_historical_tod_rvol",
        "adapt_historical_session_manifest",
        "status",
        "reason",
        "metadata_records",
        "bars_by_symbol",
        "scanner",
        "alerts",
        "voice",
        "candidate",
        "trading",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
