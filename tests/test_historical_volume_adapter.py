from datetime import date, datetime, timedelta
from math import inf, nan
from pathlib import Path

from market_sentry.data.historical_volume_adapter import (
    DEFAULT_MINIMUM_HISTORICAL_DAYS,
    HistoricalAverageVolumeResult,
    HistoricalDailyVolumeBar,
    HistoricalVolumeSeriesInput,
    HistoricalVolumeStatus,
    RelativeVolumeInputBuildResult,
    build_relative_volume_calculation_inputs,
    calculate_historical_average_volume,
    calculate_historical_average_volume_results,
    calculate_historical_average_volumes,
)
from market_sentry.data.relative_volume_calculator import (
    RelativeVolumeCalculationInput,
)


def make_bars(count: int, *, start_volume: int = 1_000) -> list[HistoricalDailyVolumeBar]:
    start_date = date(2026, 1, 1)
    return [
        HistoricalDailyVolumeBar(
            session_date=start_date + timedelta(days=offset),
            volume=start_volume + offset,
        )
        for offset in range(count)
    ]


def test_calculates_valid_arithmetic_average_from_explicit_bars() -> None:
    bars = [
        HistoricalDailyVolumeBar(date(2026, 1, 1), 1_000),
        HistoricalDailyVolumeBar(date(2026, 1, 2), 2_000),
        HistoricalDailyVolumeBar(date(2026, 1, 3), 3_000),
    ]

    result = calculate_historical_average_volume(
        "avg",
        bars,
        minimum_historical_days=3,
    )

    assert result == HistoricalAverageVolumeResult(
        symbol="AVG",
        historical_average_volume=2_000.0,
        status="OK",
        reason=None,
        bar_count=3,
    )


def test_bars_arriving_in_different_date_orders_produce_same_average() -> None:
    ascending = make_bars(5)
    descending = list(reversed(ascending))

    ascending_result = calculate_historical_average_volume(
        "ord",
        ascending,
        minimum_historical_days=5,
    )
    descending_result = calculate_historical_average_volume(
        "ord",
        descending,
        minimum_historical_days=5,
    )

    assert ascending_result.historical_average_volume == (
        descending_result.historical_average_volume
    )
    assert descending_result.status == "OK"


def test_normalizes_symbol() -> None:
    result = calculate_historical_average_volume(
        "  hist  ",
        make_bars(3),
        minimum_historical_days=3,
    )

    assert result.symbol == "HIST"
    assert result.status == "OK"


def test_empty_symbol_fails() -> None:
    result = calculate_historical_average_volume(
        "   ",
        make_bars(3),
        minimum_historical_days=3,
    )

    assert result.symbol == ""
    assert result.historical_average_volume is None
    assert result.status == "EMPTY_SYMBOL"
    assert result.reason == "EMPTY_SYMBOL"


def test_no_bars_fail() -> None:
    result = calculate_historical_average_volume(
        "NONE",
        [],
        minimum_historical_days=1,
    )

    assert result.historical_average_volume is None
    assert result.status == "NO_HISTORICAL_BARS"
    assert result.bar_count == 0


def test_invalid_minimum_lookback_fails() -> None:
    invalid_values = [True, "20", 0, -1]

    for invalid_value in invalid_values:
        result = calculate_historical_average_volume(
            "MIN",
            make_bars(3),
            minimum_historical_days=invalid_value,  # type: ignore[arg-type]
        )
        assert result.status == "INVALID_MINIMUM_HISTORICAL_DAYS"
        assert result.historical_average_volume is None


def test_insufficient_lookback_fails() -> None:
    result = calculate_historical_average_volume(
        "SHORT",
        make_bars(2),
        minimum_historical_days=3,
    )

    assert result.status == "INSUFFICIENT_HISTORICAL_BARS"
    assert result.historical_average_volume is None
    assert result.bar_count == 2


def test_default_twenty_bar_lookback_is_valid() -> None:
    result = calculate_historical_average_volume("DEF", make_bars(20))

    assert DEFAULT_MINIMUM_HISTORICAL_DAYS == 20
    assert result.status == "OK"
    assert result.bar_count == 20


def test_configurable_smaller_fixture_lookback_is_valid() -> None:
    result = calculate_historical_average_volume(
        "SMALL",
        make_bars(2),
        minimum_historical_days=2,
    )

    assert result.status == "OK"
    assert result.historical_average_volume is not None


def test_valid_date_is_accepted_and_datetime_is_rejected() -> None:
    valid_result = calculate_historical_average_volume(
        "DATE",
        [HistoricalDailyVolumeBar(date(2026, 1, 1), 1_000)],
        minimum_historical_days=1,
    )
    invalid_result = calculate_historical_average_volume(
        "DATE",
        [HistoricalDailyVolumeBar(datetime(2026, 1, 1), 1_000)],  # type: ignore[arg-type]
        minimum_historical_days=1,
    )

    assert valid_result.status == "OK"
    assert invalid_result.status == "INVALID_SESSION_DATE"
    assert invalid_result.historical_average_volume is None


def test_invalid_session_date_rejection() -> None:
    result = calculate_historical_average_volume(
        "BADDATE",
        [HistoricalDailyVolumeBar("2026-01-01", 1_000)],  # type: ignore[arg-type]
        minimum_historical_days=1,
    )

    assert result.status == "INVALID_SESSION_DATE"
    assert result.historical_average_volume is None


def test_duplicate_session_date_rejection() -> None:
    duplicate_date = date(2026, 1, 1)
    result = calculate_historical_average_volume(
        "DUP",
        [
            HistoricalDailyVolumeBar(duplicate_date, 1_000),
            HistoricalDailyVolumeBar(duplicate_date, 2_000),
        ],
        minimum_historical_days=2,
    )

    assert result.status == "DUPLICATE_SESSION_DATE"
    assert result.historical_average_volume is None


def test_missing_and_non_numeric_historical_volume_fail() -> None:
    missing_result = calculate_historical_average_volume(
        "MISS",
        [HistoricalDailyVolumeBar(date(2026, 1, 1), None)],  # type: ignore[arg-type]
        minimum_historical_days=1,
    )
    non_numeric_result = calculate_historical_average_volume(
        "BAD",
        [HistoricalDailyVolumeBar(date(2026, 1, 1), "not-volume")],  # type: ignore[arg-type]
        minimum_historical_days=1,
    )

    assert missing_result.status == "INVALID_HISTORICAL_VOLUME"
    assert missing_result.historical_average_volume is None
    assert non_numeric_result.status == "INVALID_HISTORICAL_VOLUME"
    assert non_numeric_result.historical_average_volume is None


def test_zero_and_negative_historical_volume_fail() -> None:
    zero_result = calculate_historical_average_volume(
        "ZERO",
        [HistoricalDailyVolumeBar(date(2026, 1, 1), 0)],
        minimum_historical_days=1,
    )
    negative_result = calculate_historical_average_volume(
        "NEG",
        [HistoricalDailyVolumeBar(date(2026, 1, 1), -1)],
        minimum_historical_days=1,
    )

    assert zero_result.status == "NON_POSITIVE_HISTORICAL_VOLUME"
    assert zero_result.historical_average_volume is None
    assert negative_result.status == "NON_POSITIVE_HISTORICAL_VOLUME"
    assert negative_result.historical_average_volume is None


def test_nan_and_infinity_rejection() -> None:
    nan_result = calculate_historical_average_volume(
        "NAN",
        [HistoricalDailyVolumeBar(date(2026, 1, 1), nan)],
        minimum_historical_days=1,
    )
    inf_result = calculate_historical_average_volume(
        "INF",
        [HistoricalDailyVolumeBar(date(2026, 1, 1), inf)],
        minimum_historical_days=1,
    )

    assert nan_result.status == "NON_FINITE_HISTORICAL_VOLUME"
    assert nan_result.historical_average_volume is None
    assert inf_result.status == "NON_FINITE_HISTORICAL_VOLUME"
    assert inf_result.historical_average_volume is None


def test_boolean_volume_rejection() -> None:
    result = calculate_historical_average_volume(
        "BOOL",
        [HistoricalDailyVolumeBar(date(2026, 1, 1), True)],  # type: ignore[arg-type]
        minimum_historical_days=1,
    )

    assert result.status == "INVALID_HISTORICAL_VOLUME"
    assert result.historical_average_volume is None


def test_invalid_series_does_not_average_remaining_bars() -> None:
    result = calculate_historical_average_volume(
        "STRICT",
        [
            HistoricalDailyVolumeBar(date(2026, 1, 1), 1_000),
            HistoricalDailyVolumeBar(date(2026, 1, 2), 0),
            HistoricalDailyVolumeBar(date(2026, 1, 3), 3_000),
        ],
        minimum_historical_days=3,
    )

    assert result.status == "NON_POSITIVE_HISTORICAL_VOLUME"
    assert result.historical_average_volume is None


def test_batch_result_order_is_preserved() -> None:
    inputs = [
        HistoricalVolumeSeriesInput("aaa", make_bars(2)),
        HistoricalVolumeSeriesInput("", make_bars(2)),
        HistoricalVolumeSeriesInput("bbb", make_bars(2)),
    ]

    results = calculate_historical_average_volume_results(
        inputs,
        minimum_historical_days=2,
    )

    assert [result.symbol for result in results] == ["AAA", "", "BBB"]
    assert [result.status for result in results] == ["OK", "EMPTY_SYMBOL", "OK"]


def test_successful_mapping_only() -> None:
    inputs = [
        HistoricalVolumeSeriesInput("good", make_bars(2, start_volume=1_000)),
        HistoricalVolumeSeriesInput("bad", []),
        HistoricalVolumeSeriesInput("also_good", make_bars(2, start_volume=2_000)),
    ]

    assert calculate_historical_average_volumes(
        inputs,
        minimum_historical_days=2,
    ) == {
        "GOOD": 1_000.5,
        "ALSO_GOOD": 2_000.5,
    }


def test_all_invalid_batch_returns_empty_mapping() -> None:
    inputs = [
        HistoricalVolumeSeriesInput("", make_bars(1)),
        HistoricalVolumeSeriesInput("empty", []),
    ]

    assert calculate_historical_average_volumes(
        inputs,
        minimum_historical_days=1,
    ) == {}


def test_duplicate_series_mapping_uses_last_successful_value() -> None:
    inputs = [
        HistoricalVolumeSeriesInput("dup", make_bars(2, start_volume=1_000)),
        HistoricalVolumeSeriesInput("DUP", []),
        HistoricalVolumeSeriesInput(" dup ", make_bars(2, start_volume=5_000)),
    ]

    assert calculate_historical_average_volumes(
        inputs,
        minimum_historical_days=2,
    ) == {"DUP": 5_000.5}


def test_builder_creates_phase_13c_inputs_when_history_and_current_volume_exist() -> None:
    build_results = build_relative_volume_calculation_inputs(
        {" build ": 7_500},
        [HistoricalVolumeSeriesInput("build", make_bars(2, start_volume=2_000))],
        minimum_historical_days=2,
    )

    assert build_results == [
        RelativeVolumeInputBuildResult(
            symbol="BUILD",
            calculation_input=RelativeVolumeCalculationInput(
                symbol="BUILD",
                current_volume=7_500,
                historical_average_volume=2_000.5,
            ),
            historical_result=HistoricalAverageVolumeResult(
                symbol="BUILD",
                historical_average_volume=2_000.5,
                status="OK",
                reason=None,
                bar_count=2,
            ),
            reason=None,
        )
    ]


def test_builder_preserves_failed_baseline() -> None:
    build_results = build_relative_volume_calculation_inputs(
        {"FAIL": 1_000},
        [HistoricalVolumeSeriesInput("FAIL", [])],
        minimum_historical_days=1,
    )

    assert build_results[0].symbol == "FAIL"
    assert build_results[0].calculation_input is None
    assert build_results[0].historical_result.status == "NO_HISTORICAL_BARS"
    assert build_results[0].reason == "NO_HISTORICAL_BARS"


def test_builder_preserves_missing_current_volume_failure() -> None:
    build_results = build_relative_volume_calculation_inputs(
        {},
        [HistoricalVolumeSeriesInput("MISS", make_bars(1))],
        minimum_historical_days=1,
    )

    assert build_results[0].symbol == "MISS"
    assert build_results[0].calculation_input is None
    assert build_results[0].historical_result.status == "OK"
    assert build_results[0].reason == "MISSING_CURRENT_VOLUME"


def test_builder_uses_last_normalized_current_volume_mapping_value() -> None:
    build_results = build_relative_volume_calculation_inputs(
        {"dup": 1_000, " DUP ": 2_000},
        [HistoricalVolumeSeriesInput("DUP", make_bars(1))],
        minimum_historical_days=1,
    )

    assert build_results[0].calculation_input is not None
    assert build_results[0].calculation_input.current_volume == 2_000


def test_builder_does_not_calculate_final_rvol() -> None:
    build_results = build_relative_volume_calculation_inputs(
        {"RVOL": 4_000},
        [HistoricalVolumeSeriesInput("RVOL", make_bars(1, start_volume=1_000))],
        minimum_historical_days=1,
    )

    calculation_input = build_results[0].calculation_input
    assert calculation_input is not None
    assert not hasattr(calculation_input, "relative_volume")


def test_status_values_are_stable_strings() -> None:
    assert HistoricalVolumeStatus.OK == "OK"
    assert HistoricalVolumeStatus.EMPTY_SYMBOL == "EMPTY_SYMBOL"
    assert HistoricalVolumeStatus.NO_HISTORICAL_BARS == "NO_HISTORICAL_BARS"
    assert (
        HistoricalVolumeStatus.INSUFFICIENT_HISTORICAL_BARS
        == "INSUFFICIENT_HISTORICAL_BARS"
    )
    assert (
        HistoricalVolumeStatus.INVALID_MINIMUM_HISTORICAL_DAYS
        == "INVALID_MINIMUM_HISTORICAL_DAYS"
    )
    assert HistoricalVolumeStatus.INVALID_SESSION_DATE == "INVALID_SESSION_DATE"
    assert HistoricalVolumeStatus.DUPLICATE_SESSION_DATE == "DUPLICATE_SESSION_DATE"
    assert (
        HistoricalVolumeStatus.INVALID_HISTORICAL_VOLUME
        == "INVALID_HISTORICAL_VOLUME"
    )
    assert (
        HistoricalVolumeStatus.NON_FINITE_HISTORICAL_VOLUME
        == "NON_FINITE_HISTORICAL_VOLUME"
    )
    assert (
        HistoricalVolumeStatus.NON_POSITIVE_HISTORICAL_VOLUME
        == "NON_POSITIVE_HISTORICAL_VOLUME"
    )
    assert (
        HistoricalVolumeStatus.INVALID_HISTORICAL_AVERAGE_VOLUME
        == "INVALID_HISTORICAL_AVERAGE_VOLUME"
    )
    assert HistoricalVolumeStatus.MISSING_CURRENT_VOLUME == "MISSING_CURRENT_VOLUME"


def test_adapter_module_has_no_network_or_credential_behavior() -> None:
    source = Path("src/market_sentry/data/historical_volume_adapter.py").read_text(
        encoding="utf-8"
    )

    forbidden_terms = [
        "http",
        "urllib",
        "requests",
        "socket",
        "api_key",
        "secret",
        "credential",
        "MARKET_SENTRY_PROVIDER",
        "live_composed",
        "factory",
        "place_order",
        "execute_order",
        "broker",
    ]

    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
