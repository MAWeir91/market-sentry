from datetime import datetime
from pathlib import Path
from types import MappingProxyType

import pytest

from market_sentry.data.alpaca import AlpacaSnapshot
from market_sentry.data.fmp import FMPFloatData
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.intraday_rvol_candidate_composition_harness import (
    OfflineIntradayRvolCandidateCompositionHarness,
    OfflineIntradayRvolCandidateCompositionRun,
)
from market_sentry.data.intraday_rvol_fixture_provider import (
    OfflineIntradayRelativeVolumeFixtureProvider,
)
from market_sentry.data.intraday_rvol_harness import (
    IntradayRelativeVolumeHarnessInput,
)
from market_sentry.data.live_candidate_builder import (
    LiveCandidateBuildResult,
    LiveCandidateBuilder,
)
from market_sentry.data.composer import CandidateSkipReason


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 2, 9, minute)


def make_series(
    symbol: str = "RVOL",
    session_id: str = "current",
    *,
    start_volume: int = 100,
    bars: list[IntradayVolumeBar] | None = None,
) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol=symbol,
        session_id=session_id,
        bucket="09:32",
        cutoff_timestamp=dt(32),
        bars=bars
        if bars is not None
        else [
            IntradayVolumeBar(dt(31), start_volume),
            IntradayVolumeBar(dt(32), start_volume * 2),
            IntradayVolumeBar(dt(33), start_volume * 3),
        ],
    )


def make_harness_input(
    symbol: str = "RVOL",
    *,
    current_start_volume: int = 200,
    history_start_volume: int = 100,
    history_count: int = 20,
) -> IntradayRelativeVolumeHarnessInput:
    return IntradayRelativeVolumeHarnessInput(
        current_series=make_series(symbol, "current", start_volume=current_start_volume),
        historical_series=[
            make_series(symbol, f"hist-{index}", start_volume=history_start_volume)
            for index in range(history_count)
        ],
    )


class FakeSnapshotSource:
    def __init__(self, snapshots: dict[str, AlpacaSnapshot]) -> None:
        self.snapshots = snapshots

    def fetch_snapshots(self, symbols):
        return {
            symbol: self.snapshots[symbol]
            for symbol in symbols
            if symbol in self.snapshots
        }


class FakeFloatSource:
    def __init__(self, floats: dict[str, FMPFloatData]) -> None:
        self.floats = floats

    def fetch_float(self, symbol):
        return self.floats.get(symbol)


def make_snapshot(symbol: str) -> AlpacaSnapshot:
    return AlpacaSnapshot(
        symbol=symbol,
        price=4.0,
        daily_volume=1_200_000,
        high_of_day=4.25,
        previous_close=2.0,
    )


def make_builder(
    *,
    snapshots: dict[str, AlpacaSnapshot] | None = None,
    floats: dict[str, FMPFloatData] | None = None,
) -> LiveCandidateBuilder:
    snapshots = snapshots or {"RVOL": make_snapshot("RVOL")}
    floats = floats or {"RVOL": FMPFloatData(symbol="RVOL", float_shares=1_500_000)}
    return LiveCandidateBuilder(
        snapshot_source=FakeSnapshotSource(snapshots),
        float_source=FakeFloatSource(floats),
    )


def make_provider(
    inputs: list[IntradayRelativeVolumeHarnessInput] | None = None,
) -> OfflineIntradayRelativeVolumeFixtureProvider:
    return OfflineIntradayRelativeVolumeFixtureProvider(
        inputs if inputs is not None else [make_harness_input()]
    )


def make_composition_harness(
    *,
    provider: OfflineIntradayRelativeVolumeFixtureProvider | None = None,
    builder: LiveCandidateBuilder | None = None,
) -> OfflineIntradayRvolCandidateCompositionHarness:
    return OfflineIntradayRvolCandidateCompositionHarness(
        candidate_builder=builder or make_builder(),
        relative_volume_provider=provider or make_provider(),
    )


def test_valid_requested_fixture_symbol_produces_stock_candidate() -> None:
    harness = make_composition_harness()

    run = harness.build_run(["RVOL"])

    assert len(run.candidates) == 1
    assert run.candidates[0].symbol == "RVOL"
    assert run.candidates[0].relative_volume == 2.0
    assert run.skipped_results == ()


def test_candidate_rvol_equals_phase_13h_rvol() -> None:
    provider = make_provider()
    harness = make_composition_harness(provider=provider)

    run = harness.build_run(["RVOL"])

    assert run.relative_volumes["RVOL"] == 2.0
    assert run.candidates[0].relative_volume == run.relative_volumes["RVOL"]


def test_failed_or_missing_phase_13h_rvol_becomes_builder_missing_rvol_skip() -> None:
    builder = make_builder(
        snapshots={"BAD": make_snapshot("BAD")},
        floats={"BAD": FMPFloatData(symbol="BAD", float_shares=1_500_000)},
    )
    provider = make_provider([make_harness_input("BAD", history_count=1)])
    harness = make_composition_harness(provider=provider, builder=builder)

    run = harness.build_run(["BAD"])

    assert run.candidates == ()
    assert len(run.skipped_results) == 1
    assert run.skipped_results[0].symbol == "BAD"
    assert run.skipped_results[0].skipped_reason == (
        CandidateSkipReason.MISSING_RELATIVE_VOLUME
    )


def test_one_rvol_failure_does_not_block_another_valid_requested_symbol() -> None:
    builder = make_builder(
        snapshots={"BAD": make_snapshot("BAD"), "GOOD": make_snapshot("GOOD")},
        floats={
            "BAD": FMPFloatData(symbol="BAD", float_shares=1_500_000),
            "GOOD": FMPFloatData(symbol="GOOD", float_shares=1_500_000),
        },
    )
    provider = make_provider(
        [make_harness_input("BAD", history_count=1), make_harness_input("GOOD")]
    )
    harness = make_composition_harness(provider=provider, builder=builder)

    run = harness.build_run(["BAD", "GOOD"])

    assert [candidate.symbol for candidate in run.candidates] == ["GOOD"]
    assert run.skipped_results[0].symbol == "BAD"
    assert run.skipped_results[0].skipped_reason == (
        CandidateSkipReason.MISSING_RELATIVE_VOLUME
    )


def test_missing_snapshot_and_invalid_float_remain_inspectable() -> None:
    builder = make_builder(
        snapshots={"BADFLOAT": make_snapshot("BADFLOAT")},
        floats={
            "NOSNAP": FMPFloatData(symbol="NOSNAP", float_shares=1_500_000),
            "BADFLOAT": FMPFloatData(symbol="BADFLOAT", float_shares=0),
        },
    )
    provider = make_provider(
        [make_harness_input("NOSNAP"), make_harness_input("BADFLOAT")]
    )
    harness = make_composition_harness(provider=provider, builder=builder)

    run = harness.build_run(["NOSNAP", "BADFLOAT"])

    assert [result.symbol for result in run.skipped_results] == [
        "NOSNAP",
        "BADFLOAT",
    ]
    assert run.skipped_results[0].skipped_reason == (
        CandidateSkipReason.MISSING_ALPACA_SNAPSHOT
    )
    assert run.skipped_results[1].skipped_reason == CandidateSkipReason.INVALID_FLOAT


def test_rvol_results_preserve_failed_phase_13h_fixture_diagnostics() -> None:
    provider = make_provider([make_harness_input("BAD", history_count=1)])
    harness = make_composition_harness(
        provider=provider,
        builder=make_builder(
            snapshots={"BAD": make_snapshot("BAD")},
            floats={"BAD": FMPFloatData(symbol="BAD", float_shares=1_500_000)},
        ),
    )

    run = harness.build_run(["BAD"])

    assert len(run.rvol_results) == 1
    assert run.rvol_results[0].status == "FAILED_TIME_OF_DAY_RVOL"
    assert run.rvol_results[0].time_of_day_result is not None
    assert run.rvol_results[0].time_of_day_result.status == (
        "INSUFFICIENT_HISTORICAL_OBSERVATIONS"
    )


def test_candidates_and_skipped_results_preserve_builder_order() -> None:
    builder = make_builder(
        snapshots={"AAA": make_snapshot("AAA"), "BBB": make_snapshot("BBB")},
        floats={
            "AAA": FMPFloatData(symbol="AAA", float_shares=1_500_000),
            "BBB": FMPFloatData(symbol="BBB", float_shares=0),
        },
    )
    provider = make_provider([make_harness_input("AAA"), make_harness_input("BBB")])
    harness = make_composition_harness(provider=provider, builder=builder)

    run = harness.build_run(["AAA", "BBB", "CCC"])

    assert [candidate.symbol for candidate in run.candidates] == ["AAA"]
    assert [result.symbol for result in run.skipped_results] == ["BBB", "CCC"]


def test_get_candidates_matches_successful_candidates_from_build_run() -> None:
    harness = make_composition_harness()

    run = harness.build_run(["RVOL"])
    candidates = harness.get_candidates(["RVOL"])

    assert candidates == list(run.candidates)
    assert harness.latest_run is not run
    assert harness.latest_run is not None
    assert candidates == list(harness.latest_run.candidates)


def test_requested_symbols_use_trim_uppercase_normalization() -> None:
    harness = make_composition_harness()

    run = harness.build_run(["  rvol  ", "", "   "])

    assert run.requested_symbols == ("RVOL",)
    assert [candidate.symbol for candidate in run.candidates] == ["RVOL"]


def test_blank_requested_symbols_create_no_candidates_or_fabricated_values() -> None:
    harness = make_composition_harness()

    run = harness.build_run(["", "   "])

    assert run.requested_symbols == ()
    assert run.relative_volumes == {}
    assert run.candidates == ()
    assert run.skipped_results == ()
    assert run.candidate_build_results == ()


def test_empty_request_calls_phase_13h_once_with_empty_tuple() -> None:
    class SpyProvider:
        latest_results = ("refreshed",)

        def __init__(self) -> None:
            self.calls = []

        def get_relative_volumes(self, symbols):
            self.calls.append(tuple(symbols))
            return {}

    class SpyBuilder:
        def __init__(self) -> None:
            self.calls = []

        def build_candidates(self, symbols, relative_volume_by_symbol):
            self.calls.append((tuple(symbols), dict(relative_volume_by_symbol)))
            return []

    provider = SpyProvider()
    builder = SpyBuilder()
    harness = OfflineIntradayRvolCandidateCompositionHarness(
        candidate_builder=builder,  # type: ignore[arg-type]
        relative_volume_provider=provider,  # type: ignore[arg-type]
    )

    run = harness.build_run([])

    assert provider.calls == [()]
    assert builder.calls == [((), {})]
    assert run.rvol_results == ("refreshed",)
    assert run.candidates == ()


def test_unrequested_valid_fixture_data_produces_no_candidate() -> None:
    builder = make_builder(
        snapshots={"REQ": make_snapshot("REQ"), "OTHER": make_snapshot("OTHER")},
        floats={
            "REQ": FMPFloatData(symbol="REQ", float_shares=1_500_000),
            "OTHER": FMPFloatData(symbol="OTHER", float_shares=1_500_000),
        },
    )
    provider = make_provider([make_harness_input("OTHER")])
    harness = make_composition_harness(provider=provider, builder=builder)

    run = harness.build_run(["REQ"])

    assert run.relative_volumes == {}
    assert run.candidates == ()
    assert run.skipped_results[0].symbol == "REQ"
    assert run.skipped_results[0].skipped_reason == (
        CandidateSkipReason.MISSING_RELATIVE_VOLUME
    )


def test_phase_13h_duplicate_success_behavior_reaches_candidate_composition() -> None:
    builder = make_builder(
        snapshots={"DUP": make_snapshot("DUP")},
        floats={"DUP": FMPFloatData(symbol="DUP", float_shares=1_500_000)},
    )
    provider = make_provider(
        [
            make_harness_input("DUP", current_start_volume=200),
            make_harness_input("DUP", history_count=1),
            make_harness_input("DUP", current_start_volume=500),
        ]
    )
    harness = make_composition_harness(provider=provider, builder=builder)

    run = harness.build_run(["DUP"])

    assert run.relative_volumes["DUP"] == 5.0
    assert run.candidates[0].relative_volume == 5.0


def test_latest_run_starts_none_and_updates_after_build_run_and_get_candidates() -> None:
    harness = make_composition_harness()

    assert harness.latest_run is None
    first_run = harness.build_run(["RVOL"])
    assert harness.latest_run == first_run
    candidates = harness.get_candidates(["RVOL"])
    assert harness.latest_run is not None
    assert candidates == list(harness.latest_run.candidates)


def test_provider_called_once_per_build_run_and_builder_receives_mapping() -> None:
    class SpyProvider:
        latest_results = ()

        def __init__(self) -> None:
            self.calls = []

        def get_relative_volumes(self, symbols):
            self.calls.append(tuple(symbols))
            return {"AAA": 2.5}

    class SpyBuilder:
        def __init__(self) -> None:
            self.calls = []

        def build_candidates(self, symbols, relative_volume_by_symbol):
            self.calls.append((tuple(symbols), dict(relative_volume_by_symbol)))
            return [
                LiveCandidateBuildResult(
                    symbol="AAA",
                    candidate=None,
                    skipped_reason=CandidateSkipReason.MISSING_ALPACA_SNAPSHOT,
                )
            ]

    provider = SpyProvider()
    builder = SpyBuilder()
    harness = OfflineIntradayRvolCandidateCompositionHarness(
        candidate_builder=builder,  # type: ignore[arg-type]
        relative_volume_provider=provider,  # type: ignore[arg-type]
    )

    run = harness.build_run([" aaa ", "bbb"])

    assert provider.calls == [("AAA", "BBB")]
    assert builder.calls == [(("AAA", "BBB"), {"AAA": 2.5})]
    assert [result.symbol for result in run.candidate_build_results] == ["AAA"]


def test_run_stores_immutable_copies() -> None:
    harness = make_composition_harness()

    run = harness.build_run(["RVOL"])

    assert isinstance(run.requested_symbols, tuple)
    assert isinstance(run.relative_volumes, MappingProxyType)
    assert isinstance(run.rvol_results, tuple)
    assert isinstance(run.candidate_build_results, tuple)
    with pytest.raises(TypeError):
        run.relative_volumes["RVOL"] = 99.0  # type: ignore[index]


def test_harness_does_not_directly_import_phase_13e_13f_or_13g() -> None:
    source = Path(
        "src/market_sentry/data/intraday_rvol_candidate_composition_harness.py"
    ).read_text(encoding="utf-8")

    forbidden_imports = [
        "time_of_day_rvol",
        "intraday_bucket_adapter",
        "intraday_rvol_harness",
        "calculate_time_of_day_relative_volume",
        "build_time_of_day_relative_volume_input",
        "calculate_intraday_time_of_day_relative_volume",
    ]

    for forbidden in forbidden_imports:
        assert forbidden not in source


def test_module_has_no_network_credentials_factory_runtime_or_trading_hooks() -> None:
    source = Path(
        "src/market_sentry/data/intraday_rvol_candidate_composition_harness.py"
    ).read_text(encoding="utf-8")

    forbidden_terms = [
        "urllib",
        "requests",
        "socket",
        "api_key",
        "secret",
        "credential",
        "MARKET_SENTRY_PROVIDER",
        "transport",
        "fetcher",
        "place_order",
        "execute_order",
        "broker",
    ]

    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
