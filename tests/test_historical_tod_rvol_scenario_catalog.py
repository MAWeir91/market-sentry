import ast
import inspect
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from market_sentry.data import historical_tod_rvol_scenario_catalog
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_session_assembly import (
    HistoricalSessionAssemblyStatus,
)
from market_sentry.data.historical_tod_rvol_harness import (
    run_historical_to_time_of_day_rvol,
)
from market_sentry.data.historical_tod_rvol_scenario_catalog import (
    HistoricalTodRvolScenario,
    get_historical_tod_rvol_scenario,
    get_historical_tod_rvol_scenarios,
)
from market_sentry.data.intraday_bucket_adapter import IntradayBucketStatus
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeStatus


EXPECTED_NAMES = (
    "valid_20_session_baseline",
    "insufficient_history",
    "incomplete_page_collection",
    "historical_session_cutoff_not_reached",
    "historical_invalid_volume",
    "current_invalid_volume",
    "current_identity_mismatch",
    "final_phase_13e_validation_failure",
)


def run_scenario(scenario: HistoricalTodRvolScenario):
    return run_historical_to_time_of_day_rvol(
        scenario.page,
        scenario.historical_metadata_records,
        scenario.current_series,
        scenario.request,
    )


def test_scenarios_are_returned_in_exact_order_with_unique_names() -> None:
    scenarios = get_historical_tod_rvol_scenarios()

    assert tuple(scenario.name for scenario in scenarios) == EXPECTED_NAMES
    assert len({scenario.name for scenario in scenarios}) == len(EXPECTED_NAMES)


def test_lookup_is_exact_case_sensitive_and_unknown_name_raises_requested_key() -> None:
    scenario = get_historical_tod_rvol_scenario("valid_20_session_baseline")

    assert scenario.name == "valid_20_session_baseline"
    with pytest.raises(KeyError) as mixed_case:
        get_historical_tod_rvol_scenario("Valid_20_session_baseline")
    with pytest.raises(KeyError) as padded:
        get_historical_tod_rvol_scenario(" valid_20_session_baseline ")
    with pytest.raises(KeyError) as unknown:
        get_historical_tod_rvol_scenario("missing")

    assert mixed_case.value.args == ("Valid_20_session_baseline",)
    assert padded.value.args == (" valid_20_session_baseline ",)
    assert unknown.value.args == ("missing",)


def test_scenario_fields_and_expected_values_are_present() -> None:
    scenario = get_historical_tod_rvol_scenario("valid_20_session_baseline")

    assert scenario.page is not None
    assert scenario.historical_metadata_records
    assert scenario.current_series is not None
    assert scenario.request is not None
    assert scenario.expected_harness_status == "OK"
    assert scenario.expected_baseline_status == "OK"
    assert scenario.expected_final_status == "OK"
    assert scenario.expected_time_of_day_status == "OK"
    assert scenario.expected_assembly_statuses == ("OK",) * 20
    assert scenario.expected_relative_volume == 2.0


def test_fixture_structures_are_frozen_tuple_based_and_mapping_protected() -> None:
    scenario = get_historical_tod_rvol_scenario("valid_20_session_baseline")

    assert isinstance(scenario.page.requested_symbols, tuple)
    assert isinstance(scenario.page.bars_by_symbol, MappingProxyType)
    assert isinstance(scenario.page.bars_by_symbol["RVOL"], tuple)
    assert isinstance(scenario.page.bars_by_symbol["RVOL"][0], MappingProxyType)
    assert isinstance(scenario.historical_metadata_records, tuple)
    assert isinstance(scenario.current_series.bars, tuple)

    with pytest.raises(FrozenInstanceError):
        scenario.name = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        scenario.page.bars_by_symbol["RVOL"] = ()  # type: ignore[index]
    with pytest.raises(TypeError):
        scenario.page.bars_by_symbol["RVOL"][0]["v"] = 999  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        scenario.request.symbol = "OTHER"  # type: ignore[misc]


def test_catalog_calls_return_fresh_independent_fixture_objects() -> None:
    first = get_historical_tod_rvol_scenarios()
    second = get_historical_tod_rvol_scenarios()

    assert first is not second
    assert first[0] is not second[0]
    assert first[0].page is not second[0].page
    assert first[0].historical_metadata_records is not second[0].historical_metadata_records
    assert first[0].historical_metadata_records[0] is not second[0].historical_metadata_records[0]
    assert first[0].current_series is not second[0].current_series
    assert first[0].current_series.bars is not second[0].current_series.bars
    assert first[0].page.bars_by_symbol["RVOL"][0] is not (
        second[0].page.bars_by_symbol["RVOL"][0]
    )


@pytest.mark.parametrize("scenario", get_historical_tod_rvol_scenarios())
def test_every_catalog_scenario_runs_through_actual_phase_14g_harness(
    scenario: HistoricalTodRvolScenario,
) -> None:
    result = run_scenario(scenario)

    assert result.status == scenario.expected_harness_status
    assert result.baseline_result.status == scenario.expected_baseline_status
    assert result.final_result.status == scenario.expected_final_status
    assert tuple(item.status for item in result.assembly_results) == (
        scenario.expected_assembly_statuses
    )

    time_of_day_result = result.final_result.time_of_day_result
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


def test_valid_scenario_has_final_rvol_and_twenty_baseline_observations() -> None:
    result = run_scenario(get_historical_tod_rvol_scenario("valid_20_session_baseline"))

    assert result.final_result.status == CurrentSessionTimeOfDayRvolStatus.OK
    assert result.final_result.time_of_day_result is not None
    assert result.final_result.time_of_day_result.relative_volume == 2.0
    assert len(result.baseline_result.observations) == 20


def test_incomplete_page_scenario_rejects_every_assembly_record() -> None:
    result = run_scenario(get_historical_tod_rvol_scenario("incomplete_page_collection"))

    assert {item.status for item in result.assembly_results} == {
        HistoricalSessionAssemblyStatus.INCOMPLETE_PAGE_COLLECTION
    }


def test_historical_cutoff_scenario_has_only_intended_cutoff_failure() -> None:
    result = run_scenario(
        get_historical_tod_rvol_scenario("historical_session_cutoff_not_reached")
    )

    assert [item.status for item in result.assembly_results].count(
        HistoricalSessionAssemblyStatus.CUT_OFF_NOT_REACHED
    ) == 1
    assert result.assembly_results[-1].status == (
        HistoricalSessionAssemblyStatus.CUT_OFF_NOT_REACHED
    )


def test_historical_missing_volume_scenario_preserves_nested_adapter_failure() -> None:
    result = run_scenario(get_historical_tod_rvol_scenario("historical_invalid_volume"))
    failed = result.assembly_results[-1]

    assert failed.status == HistoricalSessionAssemblyStatus.ADAPTER_FAILED
    assert failed.adapter_result is not None
    assert failed.adapter_result.status == "MISSING_RAW_VOLUME"


def test_current_invalid_volume_scenario_has_no_final_tod_result() -> None:
    result = run_scenario(get_historical_tod_rvol_scenario("current_invalid_volume"))

    assert result.final_result.status == (
        CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
    )
    assert result.final_result.current_result is not None
    assert result.final_result.current_result.status == (
        IntradayBucketStatus.INVALID_INTRADAY_VOLUME
    )
    assert result.final_result.time_of_day_result is None


def test_identity_mismatch_scenario_retains_successful_current_artifact() -> None:
    result = run_scenario(get_historical_tod_rvol_scenario("current_identity_mismatch"))

    assert result.final_result.status == (
        CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SYMBOL
    )
    assert result.final_result.current_result is not None
    assert result.final_result.current_result.status == IntradayBucketStatus.OK
    assert result.final_result.current_result.symbol == "OTHER"
    assert result.final_result.time_of_day_result is None


def test_final_phase_13e_failure_retains_nested_tod_artifact() -> None:
    result = run_scenario(
        get_historical_tod_rvol_scenario("final_phase_13e_validation_failure")
    )

    assert result.final_result.status == (
        CurrentSessionTimeOfDayRvolStatus.TIME_OF_DAY_RVOL_FAILED
    )
    assert result.final_result.time_of_day_result is not None
    assert result.final_result.time_of_day_result.status == (
        TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME
    )
    assert result.final_result.time_of_day_result.relative_volume is None


def test_source_boundary_imports_only_approved_models_and_statuses() -> None:
    source = inspect.getsource(historical_tod_rvol_scenario_catalog)
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
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.current_session_tod_rvol",
        "market_sentry.data.historical_baseline_composition",
        "market_sentry.data.historical_session_assembly",
        "market_sentry.data.historical_tod_rvol_harness",
        "market_sentry.data.intraday_bucket_adapter",
        "market_sentry.data.time_of_day_rvol",
    }

    forbidden_call_names = {
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
        "AlpacaHistoricalBarsFetcher",
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
