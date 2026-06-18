import ast
import inspect
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from market_sentry.data import manifest_to_harness_scenario_catalog
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_session_assembly import (
    HistoricalSessionAssemblyStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRecordStatus,
    HistoricalSessionManifestStatus,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunStatus,
)
from market_sentry.data.intraday_bucket_adapter import IntradayBucketStatus
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessStatus,
    run_manifest_to_historical_tod_rvol,
)
from market_sentry.data.manifest_to_harness_scenario_catalog import (
    ManifestToHarnessWorkflowScenario,
    get_manifest_to_harness_workflow_scenario,
    get_manifest_to_harness_workflow_scenarios,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeStatus


EXPECTED_NAMES = (
    "valid_manifest_valid_rvol",
    "partial_manifest_valid_rvol",
    "invalid_manifest_empty_harness_input",
    "duplicate_manifest_records",
    "incomplete_historical_page",
    "historical_cutoff_not_reached",
    "current_invalid_volume",
    "current_identity_mismatch",
    "final_phase_13e_validation_failure",
)


def run_scenario(scenario: ManifestToHarnessWorkflowScenario):
    return run_manifest_to_historical_tod_rvol(
        scenario.raw_manifest_records,
        scenario.manifest_request,
        scenario.page,
        scenario.current_series,
        scenario.harness_request,
    )


def test_scenarios_are_returned_in_exact_order_with_unique_names() -> None:
    scenarios = get_manifest_to_harness_workflow_scenarios()

    assert tuple(scenario.name for scenario in scenarios) == EXPECTED_NAMES
    assert len({scenario.name for scenario in scenarios}) == len(EXPECTED_NAMES)


def test_lookup_is_exact_case_sensitive_and_unknown_key_is_preserved() -> None:
    scenario = get_manifest_to_harness_workflow_scenario("valid_manifest_valid_rvol")

    assert scenario.name == "valid_manifest_valid_rvol"
    with pytest.raises(KeyError) as mixed_case:
        get_manifest_to_harness_workflow_scenario("Valid_manifest_valid_rvol")
    with pytest.raises(KeyError) as padded:
        get_manifest_to_harness_workflow_scenario(" valid_manifest_valid_rvol ")
    with pytest.raises(KeyError) as unknown:
        get_manifest_to_harness_workflow_scenario("missing")

    assert mixed_case.value.args == ("Valid_manifest_valid_rvol",)
    assert padded.value.args == (" valid_manifest_valid_rvol ",)
    assert unknown.value.args == ("missing",)


def test_fixture_structures_are_frozen_tuple_based_and_protected() -> None:
    scenario = get_manifest_to_harness_workflow_scenario("valid_manifest_valid_rvol")

    assert isinstance(scenario.raw_manifest_records, tuple)
    assert isinstance(scenario.raw_manifest_records[0], MappingProxyType)
    assert isinstance(scenario.page.requested_symbols, tuple)
    assert isinstance(scenario.page.bars_by_symbol, MappingProxyType)
    assert isinstance(scenario.page.bars_by_symbol["RVOL"], tuple)
    assert isinstance(scenario.page.bars_by_symbol["RVOL"][0], MappingProxyType)
    assert isinstance(scenario.current_series.bars, tuple)

    with pytest.raises(FrozenInstanceError):
        scenario.name = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        scenario.raw_manifest_records[0]["symbol"] = "OTHER"  # type: ignore[index]
    with pytest.raises(TypeError):
        scenario.page.bars_by_symbol["RVOL"][0]["v"] = 999  # type: ignore[index]


def test_separate_catalog_calls_rebuild_independent_objects() -> None:
    first = get_manifest_to_harness_workflow_scenarios()
    second = get_manifest_to_harness_workflow_scenarios()

    assert first is not second
    assert first[0] is not second[0]
    assert first[0].manifest_request is not second[0].manifest_request
    assert first[0].raw_manifest_records is not second[0].raw_manifest_records
    assert first[0].raw_manifest_records[0] is not second[0].raw_manifest_records[0]
    assert first[0].page is not second[0].page
    assert first[0].page.bars_by_symbol["RVOL"][0] is not (
        second[0].page.bars_by_symbol["RVOL"][0]
    )
    assert first[0].current_series is not second[0].current_series
    assert first[0].harness_request is not second[0].harness_request


@pytest.mark.parametrize("scenario", get_manifest_to_harness_workflow_scenarios())
def test_every_scenario_runs_through_actual_phase_14j_coordinator(
    scenario: ManifestToHarnessWorkflowScenario,
) -> None:
    result = run_scenario(scenario)

    assert result.status == scenario.expected_coordinator_status
    assert result.reason == scenario.expected_coordinator_reason
    assert result.manifest_result.status == scenario.expected_manifest_status
    assert tuple(item.status for item in result.manifest_result.record_results) == (
        scenario.expected_manifest_record_statuses
    )
    assert result.harness_result.status == scenario.expected_harness_status
    assert tuple(item.status for item in result.harness_result.assembly_results) == (
        scenario.expected_assembly_statuses
    )
    assert result.harness_result.baseline_result.status == (
        scenario.expected_baseline_status
    )
    assert result.harness_result.final_result.status == scenario.expected_final_status

    time_of_day_result = result.harness_result.final_result.time_of_day_result
    if scenario.expected_time_of_day_status is None:
        assert time_of_day_result is None
    else:
        assert time_of_day_result is not None
        assert time_of_day_result.status == scenario.expected_time_of_day_status

    if scenario.expected_relative_volume is None:
        if time_of_day_result is not None:
            assert time_of_day_result.relative_volume is None
    else:
        assert time_of_day_result is not None
        assert time_of_day_result.relative_volume == scenario.expected_relative_volume


def test_valid_scenario_artifacts() -> None:
    result = run_scenario(get_manifest_to_harness_workflow_scenario("valid_manifest_valid_rvol"))

    assert result.status == ManifestToHarnessStatus.OK
    assert len(result.manifest_result.metadata_records) == 20
    assert len(result.harness_result.baseline_result.observations) == 20
    assert result.harness_result.final_result.time_of_day_result is not None
    assert result.harness_result.final_result.time_of_day_result.relative_volume == 2.0


def test_partial_scenario_preserves_invalid_diagnostic_and_harness_success() -> None:
    result = run_scenario(get_manifest_to_harness_workflow_scenario("partial_manifest_valid_rvol"))

    assert result.manifest_result.status == HistoricalSessionManifestStatus.PARTIAL
    assert result.manifest_result.record_results[-1].status == (
        HistoricalSessionManifestRecordStatus.MISSING_REQUIRED_FIELD
    )
    assert len(result.manifest_result.metadata_records) == 20
    assert result.harness_result.status == HistoricalToTodRvolRunStatus.OK
    assert result.status == ManifestToHarnessStatus.MANIFEST_PARTIAL


def test_invalid_request_scenario_still_preserves_harness_artifact() -> None:
    result = run_scenario(
        get_manifest_to_harness_workflow_scenario(
            "invalid_manifest_empty_harness_input"
        )
    )

    assert result.manifest_result.record_results == ()
    assert result.manifest_result.metadata_records == ()
    assert result.harness_result.status == (
        HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
    )
    assert result.status == ManifestToHarnessStatus.MANIFEST_FAILED


def test_duplicate_scenario_rejects_both_duplicates_and_emits_twenty_records() -> None:
    result = run_scenario(get_manifest_to_harness_workflow_scenario("duplicate_manifest_records"))

    assert result.manifest_result.record_results[-2].status == (
        HistoricalSessionManifestRecordStatus.DUPLICATE_HISTORICAL_SESSION_ID
    )
    assert result.manifest_result.record_results[-1].status == (
        HistoricalSessionManifestRecordStatus.DUPLICATE_HISTORICAL_SESSION_ID
    )
    assert len(result.manifest_result.metadata_records) == 20
    assert all(
        item.session_id != "DUP-ONLY"
        for item in result.manifest_result.metadata_records
    )
    assert result.harness_result.status == HistoricalToTodRvolRunStatus.OK
    assert result.status == ManifestToHarnessStatus.MANIFEST_PARTIAL


def test_incomplete_page_scenario_rejects_every_assembly_record() -> None:
    result = run_scenario(get_manifest_to_harness_workflow_scenario("incomplete_historical_page"))

    assert {item.status for item in result.harness_result.assembly_results} == {
        HistoricalSessionAssemblyStatus.INCOMPLETE_PAGE_COLLECTION
    }


def test_historical_cutoff_scenario_has_only_intended_cutoff_failure() -> None:
    result = run_scenario(
        get_manifest_to_harness_workflow_scenario("historical_cutoff_not_reached")
    )

    statuses = [item.status for item in result.harness_result.assembly_results]
    assert statuses.count(HistoricalSessionAssemblyStatus.CUT_OFF_NOT_REACHED) == 1
    assert statuses[-1] == HistoricalSessionAssemblyStatus.CUT_OFF_NOT_REACHED


def test_current_invalid_volume_scenario_has_no_final_tod_result() -> None:
    result = run_scenario(get_manifest_to_harness_workflow_scenario("current_invalid_volume"))

    assert result.harness_result.final_result.status == (
        CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
    )
    assert result.harness_result.final_result.current_result is not None
    assert result.harness_result.final_result.current_result.status == (
        IntradayBucketStatus.INVALID_INTRADAY_VOLUME
    )
    assert result.harness_result.final_result.time_of_day_result is None


def test_identity_mismatch_scenario_retains_successful_current_artifact() -> None:
    result = run_scenario(get_manifest_to_harness_workflow_scenario("current_identity_mismatch"))

    assert result.harness_result.final_result.status == (
        CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SYMBOL
    )
    assert result.harness_result.final_result.current_result is not None
    assert result.harness_result.final_result.current_result.status == (
        IntradayBucketStatus.OK
    )
    assert result.harness_result.final_result.current_result.symbol == "OTHER"
    assert result.harness_result.final_result.time_of_day_result is None


def test_final_phase_13e_failure_retains_nested_tod_artifact() -> None:
    result = run_scenario(
        get_manifest_to_harness_workflow_scenario(
            "final_phase_13e_validation_failure"
        )
    )

    assert result.harness_result.final_result.status == (
        CurrentSessionTimeOfDayRvolStatus.TIME_OF_DAY_RVOL_FAILED
    )
    assert result.harness_result.final_result.time_of_day_result is not None
    assert result.harness_result.final_result.time_of_day_result.status == (
        TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME
    )
    assert result.harness_result.final_result.time_of_day_result.relative_volume is None


def test_source_boundary_imports_only_approved_models_and_statuses() -> None:
    source = inspect.getsource(manifest_to_harness_scenario_catalog)
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
        "datetime",
        "types",
        "typing",
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.current_session_tod_rvol",
        "market_sentry.data.historical_baseline_composition",
        "market_sentry.data.historical_session_assembly",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.historical_tod_rvol_harness",
        "market_sentry.data.intraday_bucket_adapter",
        "market_sentry.data.manifest_to_harness_orchestrator",
        "market_sentry.data.time_of_day_rvol",
    }

    forbidden_call_names = {
        "adapt_historical_session_manifest",
        "run_manifest_to_historical_tod_rvol",
        "run_historical_to_time_of_day_rvol",
        "assemble_historical_sessions_from_page",
        "compose_historical_baseline",
        "compose_current_session_time_of_day_rvol",
        "calculate_cumulative_volume_at_bucket",
        "calculate_time_of_day_relative_volume",
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not forbidden_call_names & called_names

    forbidden_terms = [
        "alpaca_historical_bars_adapter",
        "HttpTransport",
        "StdlibHttpTransport",
        "market_sentry.data.http",
        "market_sentry.data.http_stdlib",
        "market_sentry.data.factory",
        "market_sentry.config",
        "market_sentry.live_readiness",
        "market_sentry.data.provider",
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
