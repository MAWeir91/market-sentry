import ast
import inspect
from dataclasses import FrozenInstanceError

import pytest

from market_sentry.data import metadata_loaded_historical_workflow_scenario_catalog
from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionStatus,
)
from market_sentry.data.collected_pages_to_manifest_workflow import (
    CollectedPagesToManifestWorkflowStatus,
)
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_session_manifest import HistoricalSessionManifestStatus
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSourceLoadStatus,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunStatus,
)
from market_sentry.data.manifest_to_harness_orchestrator import ManifestToHarnessStatus
from market_sentry.data.metadata_loaded_historical_workflow_scenario_catalog import (
    MetadataLoadedHistoricalWorkflowScenario,
    get_metadata_loaded_historical_workflow_scenario,
    get_metadata_loaded_historical_workflow_scenarios,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeStatus


EXPECTED_NAMES = [
    "valid_multi_page_metadata_loaded",
    "partial_manifest_multi_page_metadata_loaded",
    "incomplete_metadata_record",
    "missing_historical_metadata_record",
    "invalid_metadata_mapping_no_bridge",
    "invalid_metadata_generator_no_bridge",
    "page_cap_collection_not_composable",
    "repeated_token_collection_not_composable",
    "empty_complete_collection_not_composable",
    "mismatched_page_symbols_not_composable",
    "invalid_manifest_request_workflow_failure",
    "invalid_current_volume_workflow_failure",
]


def by_name():
    return {scenario.name: scenario for scenario in get_metadata_loaded_historical_workflow_scenarios()}


def test_exact_scenario_names_and_order() -> None:
    scenarios = get_metadata_loaded_historical_workflow_scenarios()

    assert [scenario.name for scenario in scenarios] == EXPECTED_NAMES


def test_exact_name_lookup_returns_matching_fresh_scenario() -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "valid_multi_page_metadata_loaded"
    )

    assert scenario.name == "valid_multi_page_metadata_loaded"
    assert scenario is not by_name()["valid_multi_page_metadata_loaded"]


@pytest.mark.parametrize("name", ["missing", "VALID_MULTI_PAGE_METADATA_LOADED"])
def test_unknown_or_case_changed_name_raises_key_error_with_name(name) -> None:
    with pytest.raises(KeyError) as exc_info:
        get_metadata_loaded_historical_workflow_scenario(name)

    assert exc_info.value.args == (name,)


def test_scenario_model_is_frozen() -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(
        "valid_multi_page_metadata_loaded"
    )

    with pytest.raises(FrozenInstanceError):
        scenario.name = "changed"  # type: ignore[misc]


def test_catalog_calls_return_fresh_scenarios_and_inputs() -> None:
    first = by_name()
    second = by_name()

    for name in EXPECTED_NAMES:
        first_scenario = first[name]
        second_scenario = second[name]
        assert first_scenario is not second_scenario
        assert first_scenario.metadata_source is not second_scenario.metadata_source
        assert first_scenario.collection is not second_scenario.collection
        assert first_scenario.manifest_request is not second_scenario.manifest_request
        assert first_scenario.current_series is not second_scenario.current_series
        assert first_scenario.harness_request is not second_scenario.harness_request


def test_raw_source_records_and_raw_bars_are_fresh_across_catalog_calls() -> None:
    first = get_metadata_loaded_historical_workflow_scenario(
        "valid_multi_page_metadata_loaded"
    )
    second = get_metadata_loaded_historical_workflow_scenario(
        "valid_multi_page_metadata_loaded"
    )

    first_records = first.metadata_source.raw_manifest_records
    second_records = second.metadata_source.raw_manifest_records
    assert first_records is not second_records
    assert first_records[0] is not second_records[0]

    first_bar = first.collection.collected_pages[0].page.bars_by_symbol["RVOL"][0]
    second_bar = second.collection.collected_pages[0].page.bars_by_symbol["RVOL"][0]
    assert first_bar is not second_bar
    assert first_bar == second_bar


def test_expected_fields_match_each_scenario_definition() -> None:
    scenarios = by_name()

    expected = {
        "valid_multi_page_metadata_loaded": (
            HistoricalSessionMetadataSourceLoadStatus.LOADED,
            "WORKFLOW_BRIDGE_RAN",
            None,
            CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN,
            None,
            CollectedHistoricalPagesCompositionStatus.COMPOSED,
            ManifestToHarnessStatus.OK,
            HistoricalSessionManifestStatus.OK,
            HistoricalToTodRvolRunStatus.OK,
            CurrentSessionTimeOfDayRvolStatus.OK,
            TimeOfDayRelativeVolumeStatus.OK,
            2.0,
        ),
        "partial_manifest_multi_page_metadata_loaded": (
            HistoricalSessionMetadataSourceLoadStatus.LOADED,
            "WORKFLOW_BRIDGE_RAN",
            None,
            CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN,
            None,
            CollectedHistoricalPagesCompositionStatus.COMPOSED,
            ManifestToHarnessStatus.MANIFEST_PARTIAL,
            HistoricalSessionManifestStatus.PARTIAL,
            HistoricalToTodRvolRunStatus.OK,
            CurrentSessionTimeOfDayRvolStatus.OK,
            TimeOfDayRelativeVolumeStatus.OK,
            2.0,
        ),
        "incomplete_metadata_record": (
            HistoricalSessionMetadataSourceLoadStatus.LOADED,
            "WORKFLOW_BRIDGE_RAN",
            None,
            CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN,
            None,
            CollectedHistoricalPagesCompositionStatus.COMPOSED,
            ManifestToHarnessStatus.MANIFEST_PARTIAL_AND_HARNESS_FAILED,
            HistoricalSessionManifestStatus.PARTIAL,
            HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
            None,
            None,
        ),
        "missing_historical_metadata_record": (
            HistoricalSessionMetadataSourceLoadStatus.LOADED,
            "WORKFLOW_BRIDGE_RAN",
            None,
            CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN,
            None,
            CollectedHistoricalPagesCompositionStatus.COMPOSED,
            ManifestToHarnessStatus.HARNESS_FAILED,
            HistoricalSessionManifestStatus.OK,
            HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
            None,
            None,
        ),
        "invalid_metadata_mapping_no_bridge": (
            HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE,
            "METADATA_NOT_LOADED",
            "METADATA_NOT_LOADED:INVALID_RECORD_SEQUENCE",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        "invalid_metadata_generator_no_bridge": (
            HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE,
            "METADATA_NOT_LOADED",
            "METADATA_NOT_LOADED:INVALID_RECORD_SEQUENCE",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        "page_cap_collection_not_composable": (
            HistoricalSessionMetadataSourceLoadStatus.LOADED,
            "WORKFLOW_BRIDGE_RAN",
            None,
            CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE,
            "COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION",
            CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        "repeated_token_collection_not_composable": (
            HistoricalSessionMetadataSourceLoadStatus.LOADED,
            "WORKFLOW_BRIDGE_RAN",
            None,
            CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE,
            "COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION",
            CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        "empty_complete_collection_not_composable": (
            HistoricalSessionMetadataSourceLoadStatus.LOADED,
            "WORKFLOW_BRIDGE_RAN",
            None,
            CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE,
            "COLLECTION_NOT_COMPOSABLE:EMPTY_COMPLETE_COLLECTION",
            CollectedHistoricalPagesCompositionStatus.EMPTY_COMPLETE_COLLECTION,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        "mismatched_page_symbols_not_composable": (
            HistoricalSessionMetadataSourceLoadStatus.LOADED,
            "WORKFLOW_BRIDGE_RAN",
            None,
            CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE,
            "COLLECTION_NOT_COMPOSABLE:MISMATCHED_PAGE_REQUESTED_SYMBOLS",
            CollectedHistoricalPagesCompositionStatus.MISMATCHED_PAGE_REQUESTED_SYMBOLS,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        "invalid_manifest_request_workflow_failure": (
            HistoricalSessionMetadataSourceLoadStatus.LOADED,
            "WORKFLOW_BRIDGE_RAN",
            None,
            CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN,
            None,
            CollectedHistoricalPagesCompositionStatus.COMPOSED,
            ManifestToHarnessStatus.MANIFEST_FAILED,
            HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL,
            HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
            None,
            None,
        ),
        "invalid_current_volume_workflow_failure": (
            HistoricalSessionMetadataSourceLoadStatus.LOADED,
            "WORKFLOW_BRIDGE_RAN",
            None,
            CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN,
            None,
            CollectedHistoricalPagesCompositionStatus.COMPOSED,
            ManifestToHarnessStatus.HARNESS_FAILED,
            HistoricalSessionManifestStatus.OK,
            HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
            CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED,
            None,
            None,
        ),
    }

    for name, expected_values in expected.items():
        scenario = scenarios[name]
        assert (
            scenario.expected_metadata_load_status,
            scenario.expected_workflow_status,
            scenario.expected_workflow_reason,
            scenario.expected_bridge_status,
            scenario.expected_bridge_reason,
            scenario.expected_composition_status,
            scenario.expected_coordinator_status,
            scenario.expected_manifest_status,
            scenario.expected_harness_status,
            scenario.expected_final_status,
            scenario.expected_time_of_day_status,
            scenario.expected_relative_volume,
        ) == expected_values


def test_catalog_source_boundary_does_not_execute_workflow_code() -> None:
    source = inspect.getsource(metadata_loaded_historical_workflow_scenario_catalog)
    tree = ast.parse(source)
    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    forbidden_calls = {
        "load_historical_session_metadata_source",
        "run_metadata_loaded_historical_workflow",
        "run_collected_pages_to_manifest_workflow",
        "compose_collected_historical_pages",
        "run_manifest_to_historical_tod_rvol",
        "adapt_historical_session_manifest",
    }
    assert not forbidden_calls & called_names

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
    forbidden_import_fragments = [
        "http",
        "transport",
        "factory",
        "config",
        "readiness",
        "scanner",
        "alerts",
        "voice",
        "candidate",
        "broker",
    ]
    for module in imported_modules:
        lowered = module.lower()
        for fragment in forbidden_import_fragments:
            assert fragment not in lowered


def test_scenario_instances_are_dataclass_model() -> None:
    scenario = get_metadata_loaded_historical_workflow_scenario(EXPECTED_NAMES[0])

    assert isinstance(scenario, MetadataLoadedHistoricalWorkflowScenario)
