import ast
import inspect
from dataclasses import FrozenInstanceError

import pytest

from market_sentry.data import metadata_loaded_historical_workflow_scenario_harness
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_baseline_composition import (
    HistoricalBaselineCompositionStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRecordStatus,
)
from market_sentry.data.intraday_bucket_adapter import IntradayBucketStatus
from market_sentry.data.metadata_loaded_historical_workflow import (
    MetadataLoadedHistoricalWorkflowResult,
    MetadataLoadedHistoricalWorkflowStatus,
)
from market_sentry.data.metadata_loaded_historical_workflow_scenario_catalog import (
    get_metadata_loaded_historical_workflow_scenario,
    get_metadata_loaded_historical_workflow_scenarios,
)
from market_sentry.data.metadata_loaded_historical_workflow_scenario_harness import (
    MetadataLoadedHistoricalWorkflowScenarioRun,
    run_metadata_loaded_historical_workflow_scenario,
)


def fake_result_for(scenario) -> MetadataLoadedHistoricalWorkflowResult:
    return MetadataLoadedHistoricalWorkflowResult(
        metadata_source=scenario.metadata_source,
        source_collection=scenario.collection,
        metadata_load_result=object(),  # type: ignore[arg-type]
        workflow_bridge_result=None,
        status=MetadataLoadedHistoricalWorkflowStatus.METADATA_NOT_LOADED,
        reason="METADATA_NOT_LOADED:TEST",
    )


def test_harness_calls_phase_15e_once_and_forwards_inputs_by_identity(monkeypatch) -> None:
    calls = []
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "valid_multi_page_metadata_loaded"
    )
    expected_result = fake_result_for(scenario)

    def fake_runner(source, collection, request, current, harness):
        calls.append((source, collection, request, current, harness))
        assert source is scenario.metadata_source
        assert collection is scenario.collection
        assert request is scenario.manifest_request
        assert current is scenario.current_series
        assert harness is scenario.harness_request
        return expected_result

    monkeypatch.setattr(
        metadata_loaded_historical_workflow_scenario_harness,
        "run_metadata_loaded_historical_workflow",
        fake_runner,
    )

    run = run_metadata_loaded_historical_workflow_scenario(scenario)

    assert calls == [
        (
            scenario.metadata_source,
            scenario.collection,
            scenario.manifest_request,
            scenario.current_series,
            scenario.harness_request,
        )
    ]
    assert run.scenario is scenario
    assert run.result is expected_result


def test_run_wrapper_is_frozen_and_separate_calls_create_fresh_wrappers(monkeypatch) -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "valid_multi_page_metadata_loaded"
    )
    monkeypatch.setattr(
        metadata_loaded_historical_workflow_scenario_harness,
        "run_metadata_loaded_historical_workflow",
        lambda *args: fake_result_for(scenario),
    )

    first = run_metadata_loaded_historical_workflow_scenario(scenario)
    second = run_metadata_loaded_historical_workflow_scenario(scenario)

    assert isinstance(first, MetadataLoadedHistoricalWorkflowScenarioRun)
    assert first is not second
    assert first.scenario is second.scenario
    assert first.result is not second.result
    with pytest.raises(FrozenInstanceError):
        first.result = second.result  # type: ignore[misc]


def test_phase_15e_exception_propagates_unchanged(monkeypatch) -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "valid_multi_page_metadata_loaded"
    )
    error = RuntimeError("phase 15e failed")
    monkeypatch.setattr(
        metadata_loaded_historical_workflow_scenario_harness,
        "run_metadata_loaded_historical_workflow",
        lambda *args: (_ for _ in ()).throw(error),
    )

    with pytest.raises(RuntimeError) as exc_info:
        run_metadata_loaded_historical_workflow_scenario(scenario)

    assert exc_info.value is error


def _assert_expected_nested_statuses(scenario, run) -> None:
    result = run.result
    assert result.metadata_load_result.status == scenario.expected_metadata_load_status
    assert result.status == scenario.expected_workflow_status
    assert result.reason == scenario.expected_workflow_reason

    bridge = result.workflow_bridge_result
    if scenario.expected_bridge_status is None:
        assert bridge is None
        return

    assert bridge is not None
    assert bridge.status == scenario.expected_bridge_status
    assert bridge.reason == scenario.expected_bridge_reason
    assert bridge.composition_result.status == scenario.expected_composition_status

    workflow = bridge.workflow_result
    if scenario.expected_coordinator_status is None:
        assert workflow is None
        return

    assert workflow is not None
    assert workflow.status == scenario.expected_coordinator_status
    assert workflow.manifest_result.status == scenario.expected_manifest_status
    assert workflow.harness_result.status == scenario.expected_harness_status
    assert workflow.harness_result.final_result.status == scenario.expected_final_status

    tod_result = workflow.harness_result.final_result.time_of_day_result
    if scenario.expected_time_of_day_status is None:
        assert tod_result is None
    else:
        assert tod_result is not None
        assert tod_result.status == scenario.expected_time_of_day_status
        assert tod_result.relative_volume == scenario.expected_relative_volume


def test_all_catalog_scenarios_run_end_to_end_with_expected_statuses() -> None:
    for scenario in get_metadata_loaded_historical_workflow_scenarios():
        run = run_metadata_loaded_historical_workflow_scenario(scenario)

        assert run.scenario is scenario
        _assert_expected_nested_statuses(scenario, run)


def test_valid_scenario_has_split_first_session_and_final_rvol() -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "valid_multi_page_metadata_loaded"
    )
    run = run_metadata_loaded_historical_workflow_scenario(scenario)
    workflow = run.result.workflow_bridge_result.workflow_result

    assert workflow.harness_result.assembly_results[0].in_window_raw_bar_count == 2
    assert workflow.harness_result.final_result.time_of_day_result.relative_volume == 2.0


def test_partial_manifest_scenario_preserves_missing_field_record_and_rvol() -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "partial_manifest_multi_page_metadata_loaded"
    )
    run = run_metadata_loaded_historical_workflow_scenario(scenario)
    workflow = run.result.workflow_bridge_result.workflow_result

    assert workflow.manifest_result.record_results[-1].status == (
        HistoricalSessionManifestRecordStatus.MISSING_REQUIRED_FIELD
    )
    assert workflow.manifest_result.valid_record_count == 20
    assert len(workflow.manifest_result.metadata_records) == 20
    assert workflow.harness_result.final_result.time_of_day_result.relative_volume == 2.0


def test_incomplete_metadata_record_scenario_preserves_record_diagnostic() -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "incomplete_metadata_record"
    )
    run = run_metadata_loaded_historical_workflow_scenario(scenario)
    workflow = run.result.workflow_bridge_result.workflow_result

    assert workflow.manifest_result.record_results[4].status == (
        HistoricalSessionManifestRecordStatus.INCOMPLETE_SESSION
    )
    assert workflow.manifest_result.valid_record_count == 19
    assert len(workflow.manifest_result.metadata_records) == 19


def test_missing_metadata_record_scenario_has_no_calendar_inference() -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "missing_historical_metadata_record"
    )
    run = run_metadata_loaded_historical_workflow_scenario(scenario)
    workflow = run.result.workflow_bridge_result.workflow_result

    assert workflow.manifest_result.valid_record_count == 19
    assert len(workflow.manifest_result.metadata_records) == 19
    assert workflow.harness_result.baseline_result.status == (
        HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
    )


@pytest.mark.parametrize(
    "name",
    [
        "invalid_metadata_mapping_no_bridge",
        "invalid_metadata_generator_no_bridge",
    ],
)
def test_invalid_metadata_source_scenarios_have_no_bridge_result(name) -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(name)
    run = run_metadata_loaded_historical_workflow_scenario(scenario)

    assert run.result.workflow_bridge_result is None


@pytest.mark.parametrize(
    "name",
    [
        "page_cap_collection_not_composable",
        "repeated_token_collection_not_composable",
    ],
)
def test_page_cap_and_repeated_token_scenarios_do_not_reach_phase_14j(name) -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(name)
    run = run_metadata_loaded_historical_workflow_scenario(scenario)
    bridge = run.result.workflow_bridge_result

    assert bridge.workflow_result is None
    assert bridge.composition_result.status == "INCOMPLETE_COLLECTION"


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        (
            "empty_complete_collection_not_composable",
            "COLLECTION_NOT_COMPOSABLE:EMPTY_COMPLETE_COLLECTION",
        ),
        (
            "mismatched_page_symbols_not_composable",
            "COLLECTION_NOT_COMPOSABLE:MISMATCHED_PAGE_REQUESTED_SYMBOLS",
        ),
    ],
)
def test_empty_and_mismatched_collection_diagnostics_are_retained(name, reason) -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(name)
    run = run_metadata_loaded_historical_workflow_scenario(scenario)
    bridge = run.result.workflow_bridge_result

    assert bridge.workflow_result is None
    assert bridge.reason == reason


def test_invalid_manifest_request_failure_remains_nested_under_loaded_source() -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "invalid_manifest_request_workflow_failure"
    )
    run = run_metadata_loaded_historical_workflow_scenario(scenario)
    workflow = run.result.workflow_bridge_result.workflow_result

    assert run.result.metadata_load_result.status == "LOADED"
    assert workflow.status == "MANIFEST_FAILED"
    assert workflow.manifest_result.status == "INVALID_TARGET_SYMBOL"


def test_invalid_current_volume_scenario_retains_current_bucket_failure() -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "invalid_current_volume_workflow_failure"
    )
    run = run_metadata_loaded_historical_workflow_scenario(scenario)
    workflow = run.result.workflow_bridge_result.workflow_result
    current_result = workflow.harness_result.final_result.current_result

    assert workflow.harness_result.final_result.status == (
        CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
    )
    assert current_result.status == IntradayBucketStatus.INVALID_INTRADAY_VOLUME


def test_harness_source_boundary_is_thin() -> None:
    source = inspect.getsource(metadata_loaded_historical_workflow_scenario_harness)
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
        "market_sentry.data.metadata_loaded_historical_workflow",
        "market_sentry.data.metadata_loaded_historical_workflow_scenario_catalog",
    }

    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    assert called_names == {
        "dataclass",
        "run_metadata_loaded_historical_workflow",
        "MetadataLoadedHistoricalWorkflowScenarioRun",
    }

    attribute_names = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "metadata_source" in attribute_names
    assert "collection" in attribute_names
    assert "manifest_request" in attribute_names
    assert "current_series" in attribute_names
    assert "harness_request" in attribute_names
    assert "status" not in attribute_names
    assert "bars_by_symbol" not in attribute_names
    assert "requested_symbols" not in attribute_names
