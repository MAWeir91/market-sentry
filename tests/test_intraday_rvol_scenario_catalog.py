from pathlib import Path
from types import MappingProxyType

import pytest

from market_sentry.data.composer import CandidateSkipReason
from market_sentry.data.intraday_bucket_adapter import IntradayBucketStatus
from market_sentry.data.intraday_rvol_candidate_composition_harness import (
    OfflineIntradayRvolCandidateCompositionHarness,
)
from market_sentry.data.intraday_rvol_fixture_provider import (
    OfflineIntradayRelativeVolumeFixtureProvider,
)
from market_sentry.data.intraday_rvol_scenario_catalog import (
    OfflineIntradayRvolScenarioFixture,
    get_offline_intraday_rvol_scenario,
    get_offline_intraday_rvol_scenarios,
    offline_intraday_rvol_scenario_names,
)
from market_sentry.data.live_candidate_builder import LiveCandidateBuilder


EXPECTED_SCENARIO_NAMES = (
    "valid_runner",
    "missing_rvol_invalid_history",
    "missing_snapshot",
    "invalid_float",
    "duplicate_symbols",
    "all_skipped",
)


class FakeSnapshotSource:
    def __init__(self, scenario: OfflineIntradayRvolScenarioFixture) -> None:
        self._snapshots = scenario.snapshots_by_symbol

    def fetch_snapshots(self, symbols):
        return {
            symbol: self._snapshots[symbol]
            for symbol in symbols
            if symbol in self._snapshots
        }


class FakeFloatSource:
    def __init__(self, scenario: OfflineIntradayRvolScenarioFixture) -> None:
        self._floats = scenario.float_data_by_symbol

    def fetch_float(self, symbol):
        return self._floats.get(symbol)


def build_catalog_run(name: str):
    scenario = get_offline_intraday_rvol_scenario(name)
    provider = OfflineIntradayRelativeVolumeFixtureProvider(
        scenario.rvol_fixture_inputs
    )
    builder = LiveCandidateBuilder(
        snapshot_source=FakeSnapshotSource(scenario),
        float_source=FakeFloatSource(scenario),
    )
    harness = OfflineIntradayRvolCandidateCompositionHarness(
        candidate_builder=builder,
        relative_volume_provider=provider,
    )
    return scenario, harness.build_run(scenario.requested_symbols)


def skipped_by_symbol(run) -> dict[str, CandidateSkipReason | None]:
    return {
        result.symbol: result.skipped_reason
        for result in run.candidate_build_results
        if result.candidate is None
    }


def test_catalog_exposes_required_scenarios_in_stable_order() -> None:
    scenarios = get_offline_intraday_rvol_scenarios()

    assert tuple(scenario.name for scenario in scenarios) == EXPECTED_SCENARIO_NAMES
    assert offline_intraday_rvol_scenario_names() == EXPECTED_SCENARIO_NAMES


def test_scenario_names_are_unique() -> None:
    names = tuple(scenario.name for scenario in get_offline_intraday_rvol_scenarios())

    assert len(names) == len(set(names))


def test_known_lookup_returns_matching_scenario_and_unknown_fails_clearly() -> None:
    scenario = get_offline_intraday_rvol_scenario("valid_runner")

    assert scenario.name == "valid_runner"
    with pytest.raises(KeyError, match="Unknown offline intraday RVOL scenario"):
        get_offline_intraday_rvol_scenario("VALID_RUNNER")


def test_scenario_tuple_and_mappings_are_immutable_or_protected() -> None:
    scenarios = get_offline_intraday_rvol_scenarios()
    scenario = scenarios[0]

    assert isinstance(scenarios, tuple)
    assert isinstance(scenario.requested_symbols, tuple)
    assert isinstance(scenario.rvol_fixture_inputs, tuple)
    assert isinstance(scenario.snapshots_by_symbol, MappingProxyType)
    assert isinstance(scenario.float_data_by_symbol, MappingProxyType)

    with pytest.raises(TypeError):
        scenario.snapshots_by_symbol["NEW"] = scenario.snapshots_by_symbol["RUNR"]  # type: ignore[index]
    with pytest.raises(TypeError):
        scenario.float_data_by_symbol["NEW"] = scenario.float_data_by_symbol["RUNR"]  # type: ignore[index]


def test_separate_catalog_calls_do_not_share_caller_mutable_state() -> None:
    first = get_offline_intraday_rvol_scenario("valid_runner")
    second = get_offline_intraday_rvol_scenario("valid_runner")

    assert first is not second
    assert first.snapshots_by_symbol is not second.snapshots_by_symbol
    assert first.float_data_by_symbol is not second.float_data_by_symbol


def test_valid_runner_produces_one_candidate_with_phase_13h_rvol() -> None:
    scenario, run = build_catalog_run("valid_runner")

    assert scenario.requested_symbols == ("RUNR",)
    assert len(scenario.rvol_fixture_inputs[0].historical_series) == 20
    assert [candidate.symbol for candidate in run.candidates] == ["RUNR"]
    assert run.relative_volumes["RUNR"] == run.candidates[0].relative_volume
    assert run.rvol_results[0].relative_volume == run.candidates[0].relative_volume


def test_missing_rvol_invalid_history_preserves_diagnostics_and_builder_skip() -> None:
    _, run = build_catalog_run("missing_rvol_invalid_history")

    assert run.candidates == ()
    assert run.relative_volumes == {}
    assert run.rvol_results[0].status == "FAILED_INPUT_BUILD"
    assert run.rvol_results[0].reason == IntradayBucketStatus.FAILED_HISTORICAL_SERIES
    assert run.rvol_results[0].input_build_result is not None
    assert run.rvol_results[0].input_build_result.historical_results[0].status == (
        IntradayBucketStatus.NON_POSITIVE_INTRADAY_VOLUME
    )
    assert skipped_by_symbol(run) == {
        "BADH": CandidateSkipReason.MISSING_RELATIVE_VOLUME
    }


def test_missing_snapshot_becomes_native_builder_skip() -> None:
    _, run = build_catalog_run("missing_snapshot")

    assert run.candidates == ()
    assert run.relative_volumes["NOSNAP"] == run.rvol_results[0].relative_volume
    assert skipped_by_symbol(run) == {
        "NOSNAP": CandidateSkipReason.MISSING_ALPACA_SNAPSHOT
    }


def test_invalid_float_becomes_native_builder_skip() -> None:
    _, run = build_catalog_run("invalid_float")

    assert run.candidates == ()
    assert run.relative_volumes["BADFLT"] == run.rvol_results[0].relative_volume
    assert skipped_by_symbol(run) == {"BADFLT": CandidateSkipReason.INVALID_FLOAT}


def test_duplicate_symbols_last_successful_phase_13h_rvol_reaches_candidate() -> None:
    _, run = build_catalog_run("duplicate_symbols")

    assert len(run.rvol_results) == 3
    assert [result.status for result in run.rvol_results] == [
        "OK",
        "FAILED_INPUT_BUILD",
        "OK",
    ]
    assert run.relative_volumes["DUPL"] == 5.2
    assert [candidate.symbol for candidate in run.candidates] == ["DUPL"]
    assert run.candidates[0].relative_volume == 5.2


def test_all_skipped_retains_provider_and_builder_diagnostics() -> None:
    _, run = build_catalog_run("all_skipped")

    assert run.candidates == ()
    assert [result.symbol for result in run.rvol_results] == [
        "BADH",
        "NOSNAP",
        "BADFLT",
    ]
    assert [result.status for result in run.rvol_results] == [
        "FAILED_INPUT_BUILD",
        "OK",
        "OK",
    ]
    assert skipped_by_symbol(run) == {
        "BADH": CandidateSkipReason.MISSING_RELATIVE_VOLUME,
        "NOSNAP": CandidateSkipReason.MISSING_ALPACA_SNAPSHOT,
        "BADFLT": CandidateSkipReason.INVALID_FLOAT,
    }


def test_valid_rvol_scenarios_keep_default_lookback_fixture_count() -> None:
    valid_names = (
        "valid_runner",
        "missing_snapshot",
        "invalid_float",
        "duplicate_symbols",
        "all_skipped",
    )

    for name in valid_names:
        scenario = get_offline_intraday_rvol_scenario(name)
        for fixture_input in scenario.rvol_fixture_inputs:
            assert len(fixture_input.historical_series) == 20


def test_catalog_module_uses_only_raw_fixture_models() -> None:
    source = Path(
        "src/market_sentry/data/intraday_rvol_scenario_catalog.py"
    ).read_text(encoding="utf-8")

    forbidden_terms = [
        "OfflineIntradayRelativeVolumeFixtureProvider",
        "OfflineIntradayRvolCandidateCompositionHarness",
        "LiveCandidateBuilder",
        "create_market_data_provider",
        "StdlibHttpTransport",
        "SnapshotFetcher",
        "FloatFetcher",
        "LiveComposedMarketDataProvider",
    ]

    for term in forbidden_terms:
        assert term not in source


def test_catalog_module_has_no_runtime_network_credentials_or_trading_hooks() -> None:
    source = Path(
        "src/market_sentry/data/intraday_rvol_scenario_catalog.py"
    ).read_text(encoding="utf-8")

    forbidden_terms = [
        "urllib",
        "requests",
        "socket",
        "api_key",
        "secret",
        "credential",
        "MARKET_SENTRY_PROVIDER",
        "http://",
        "https://",
        "websocket",
        "place_order",
        "execute_order",
        "buy",
        "sell",
        "enter",
        "exit",
    ]

    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
