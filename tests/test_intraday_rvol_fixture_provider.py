from datetime import datetime
from pathlib import Path

from market_sentry.data.alpaca import AlpacaSnapshot
from market_sentry.data.fmp import FMPFloatData
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.intraday_rvol_fixture_provider import (
    OfflineIntradayRelativeVolumeFixtureProvider,
)
from market_sentry.data.intraday_rvol_harness import (
    IntradayRelativeVolumeHarnessInput,
    IntradayRelativeVolumeHarnessResult,
    IntradayRelativeVolumeHarnessStatus,
    calculate_intraday_time_of_day_relative_volume,
)
from market_sentry.data.live_candidate_builder import LiveCandidateBuilder
from market_sentry.data.relative_volume import RelativeVolumeProvider


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 2, 9, minute)


def make_series(
    symbol: str = "RVOL",
    session_id: str = "current",
    *,
    start_volume: int = 100,
    bucket: str = "09:32",
    bars: list[IntradayVolumeBar] | None = None,
) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
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


def test_provider_structurally_works_as_relative_volume_provider() -> None:
    provider: RelativeVolumeProvider = OfflineIntradayRelativeVolumeFixtureProvider(
        [make_harness_input()]
    )

    assert provider.get_relative_volumes(["rvol"]) == {"RVOL": 2.0}


def test_valid_phase_13g_fixture_input_produces_requested_rvol_mapping() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider([make_harness_input()])

    assert provider.get_relative_volumes(["RVOL"]) == {"RVOL": 2.0}


def test_returned_rvol_exactly_matches_phase_13g_output() -> None:
    fixture_input = make_harness_input()
    phase_13g_result = calculate_intraday_time_of_day_relative_volume(fixture_input)
    provider = OfflineIntradayRelativeVolumeFixtureProvider([fixture_input])

    assert provider.get_relative_volumes(["RVOL"]) == {
        "RVOL": phase_13g_result.relative_volume
    }


def test_requested_symbol_trim_uppercase_and_empty_requested_symbols() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider([make_harness_input()])

    assert provider.get_relative_volumes(["  rvol  ", "", "   "]) == {"RVOL": 2.0}


def test_unrequested_valid_fixture_symbols_are_excluded() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider(
        [make_harness_input("AAA"), make_harness_input("BBB")]
    )

    assert provider.get_relative_volumes(["aaa"]) == {"AAA": 2.0}


def test_missing_requested_symbols_are_omitted_not_defaulted() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider([make_harness_input("AAA")])

    assert provider.get_relative_volumes(["MISSING"]) == {}


def test_empty_fixture_collection_returns_empty_results_and_mapping() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider([])

    assert provider.build_results() == ()
    assert provider.latest_results == ()
    assert provider.get_relative_volumes(["ANY"]) == {}


def test_failed_fixture_omitted_but_inspectable_via_latest_results() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider(
        [make_harness_input(history_count=1)]
    )

    assert provider.get_relative_volumes(["RVOL"]) == {}
    assert len(provider.latest_results) == 1
    assert provider.latest_results[0].status == "FAILED_TIME_OF_DAY_RVOL"
    assert provider.latest_results[0].time_of_day_result is not None
    assert provider.latest_results[0].time_of_day_result.status == (
        "INSUFFICIENT_HISTORICAL_OBSERVATIONS"
    )


def test_failed_fixture_for_one_symbol_does_not_block_valid_requested_symbol() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider(
        [
            make_harness_input("BAD", history_count=1),
            make_harness_input("GOOD", current_start_volume=300),
        ]
    )

    assert provider.get_relative_volumes(["BAD", "GOOD"]) == {"GOOD": 3.0}


def test_all_invalid_fixture_inputs_return_empty_mapping_and_preserve_diagnostics() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider(
        [
            make_harness_input("BAD1", history_count=1),
            IntradayRelativeVolumeHarnessInput(
                current_series=make_series("BAD2", bars=[]),
                historical_series=[make_series("BAD2", "hist-1")],
            ),
        ]
    )

    assert provider.get_relative_volumes(["BAD1", "BAD2"]) == {}
    assert [result.status for result in provider.latest_results] == [
        "FAILED_TIME_OF_DAY_RVOL",
        "FAILED_INPUT_BUILD",
    ]


def test_duplicate_last_successful_normalized_fixture_wins() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider(
        [
            make_harness_input("dup", current_start_volume=200),
            make_harness_input("DUP", current_start_volume=500),
        ]
    )

    assert provider.get_relative_volumes(["DUP"]) == {"DUP": 5.0}


def test_failed_duplicate_does_not_erase_earlier_success() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider(
        [
            make_harness_input("DUP", current_start_volume=200),
            make_harness_input("DUP", history_count=1),
        ]
    )

    assert provider.get_relative_volumes(["DUP"]) == {"DUP": 2.0}


def test_failed_first_duplicate_followed_by_success_returns_later_success() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider(
        [
            make_harness_input("DUP", history_count=1),
            make_harness_input("DUP", current_start_volume=400),
        ]
    )

    assert provider.get_relative_volumes(["DUP"]) == {"DUP": 4.0}


def test_build_results_preserves_order_and_returns_immutable_tuple() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider(
        [make_harness_input("AAA"), make_harness_input("BBB")]
    )

    results = provider.build_results()

    assert isinstance(results, tuple)
    assert [result.symbol for result in results] == ["AAA", "BBB"]
    assert not hasattr(results, "append")


def test_latest_results_starts_empty_and_updates_after_builds() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider([make_harness_input()])

    assert provider.latest_results == ()
    results = provider.build_results()
    assert provider.latest_results == results
    assert isinstance(provider.latest_results, tuple)


def test_get_relative_volumes_refreshes_latest_results_even_for_empty_request() -> None:
    provider = OfflineIntradayRelativeVolumeFixtureProvider([make_harness_input()])

    assert provider.get_relative_volumes([]) == {}
    assert len(provider.latest_results) == 1
    assert provider.latest_results[0].symbol == "RVOL"


def test_provider_uses_phase_13g_ordered_results(monkeypatch) -> None:
    calls = []
    fake_result = IntradayRelativeVolumeHarnessResult(
        symbol="FAKE",
        bucket="09:32",
        relative_volume=9.5,
        status=IntradayRelativeVolumeHarnessStatus.OK,
    )

    def fake_ordered_results(inputs):
        calls.append(tuple(inputs))
        return [fake_result]

    monkeypatch.setattr(
        "market_sentry.data.intraday_rvol_fixture_provider."
        "calculate_intraday_time_of_day_relative_volume_results",
        fake_ordered_results,
    )
    fixture_input = make_harness_input("FAKE")
    provider = OfflineIntradayRelativeVolumeFixtureProvider([fixture_input])

    assert provider.get_relative_volumes(["FAKE"]) == {"FAKE": 9.5}
    assert calls == [(fixture_input,)]


def test_offline_candidate_builder_accepts_provider_rvol_mapping() -> None:
    class FakeSnapshotSource:
        def fetch_snapshots(self, symbols):
            return {
                "RVOL": AlpacaSnapshot(
                    symbol="RVOL",
                    price=4.0,
                    daily_volume=1_200_000,
                    high_of_day=4.25,
                    previous_close=2.0,
                )
            }

    class FakeFloatSource:
        def fetch_float(self, symbol):
            if symbol == "RVOL":
                return FMPFloatData(symbol="RVOL", float_shares=1_500_000)
            return None

    provider = OfflineIntradayRelativeVolumeFixtureProvider([make_harness_input()])
    relative_volumes = provider.get_relative_volumes(["RVOL"])
    builder = LiveCandidateBuilder(
        snapshot_source=FakeSnapshotSource(),
        float_source=FakeFloatSource(),
    )

    candidates = builder.get_candidates(["RVOL"], relative_volumes)

    assert len(candidates) == 1
    assert candidates[0].symbol == "RVOL"
    assert candidates[0].relative_volume == 2.0


def test_module_has_no_network_credential_factory_transport_or_trading_hooks() -> None:
    source = Path(
        "src/market_sentry/data/intraday_rvol_fixture_provider.py"
    ).read_text(encoding="utf-8")

    forbidden_terms = [
        "urllib",
        "requests",
        "socket",
        "api_key",
        "secret",
        "credential",
        "MARKET_SENTRY_PROVIDER",
        "factory",
        "transport",
        "fetcher",
        "place_order",
        "execute_order",
        "broker",
    ]

    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
