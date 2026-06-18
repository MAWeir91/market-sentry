from math import inf, nan
from pathlib import Path

from market_sentry.data.relative_volume_calculator import (
    RelativeVolumeCalculationInput,
    RelativeVolumeResult,
    RelativeVolumeStatus,
    calculate_relative_volume,
    calculate_relative_volume_results,
    calculate_relative_volumes,
)


def test_calculates_valid_relative_volume() -> None:
    result = calculate_relative_volume("RVOL", 1_500_000, 500_000)

    assert result == RelativeVolumeResult(
        symbol="RVOL",
        relative_volume=3.0,
        status=RelativeVolumeStatus.OK,
        reason=None,
    )


def test_normalizes_symbol() -> None:
    result = calculate_relative_volume("  rvol  ", 2_000, 1_000)

    assert result.symbol == "RVOL"
    assert result.relative_volume == 2.0
    assert result.status == "OK"


def test_empty_symbol_fails_with_stable_status() -> None:
    result = calculate_relative_volume("   ", 2_000, 1_000)

    assert result.symbol == ""
    assert result.relative_volume is None
    assert result.status == "EMPTY_SYMBOL"
    assert result.reason == "EMPTY_SYMBOL"


def test_missing_current_volume_fails() -> None:
    result = calculate_relative_volume("MISS", None, 1_000)

    assert result.relative_volume is None
    assert result.status == "INVALID_CURRENT_VOLUME"
    assert result.reason == "INVALID_CURRENT_VOLUME"


def test_non_numeric_current_volume_fails() -> None:
    result = calculate_relative_volume("BAD", "not-volume", 1_000)

    assert result.relative_volume is None
    assert result.status == "INVALID_CURRENT_VOLUME"


def test_missing_historical_average_volume_fails() -> None:
    result = calculate_relative_volume("MISS", 1_000, None)

    assert result.relative_volume is None
    assert result.status == "INVALID_HISTORICAL_AVERAGE_VOLUME"
    assert result.reason == "INVALID_HISTORICAL_AVERAGE_VOLUME"


def test_non_numeric_historical_average_volume_fails() -> None:
    result = calculate_relative_volume("BAD", 1_000, "not-average")

    assert result.relative_volume is None
    assert result.status == "INVALID_HISTORICAL_AVERAGE_VOLUME"


def test_zero_and_negative_current_volume_fail() -> None:
    zero_result = calculate_relative_volume("ZERO", 0, 1_000)
    negative_result = calculate_relative_volume("NEG", -1, 1_000)

    assert zero_result.status == "NON_POSITIVE_CURRENT_VOLUME"
    assert zero_result.relative_volume is None
    assert negative_result.status == "NON_POSITIVE_CURRENT_VOLUME"
    assert negative_result.relative_volume is None


def test_zero_and_negative_historical_average_volume_fail() -> None:
    zero_result = calculate_relative_volume("ZERO", 1_000, 0)
    negative_result = calculate_relative_volume("NEG", 1_000, -1)

    assert zero_result.status == "NON_POSITIVE_HISTORICAL_AVERAGE_VOLUME"
    assert zero_result.relative_volume is None
    assert negative_result.status == "NON_POSITIVE_HISTORICAL_AVERAGE_VOLUME"
    assert negative_result.relative_volume is None


def test_nan_and_infinity_current_volume_fail() -> None:
    nan_result = calculate_relative_volume("NAN", nan, 1_000)
    inf_result = calculate_relative_volume("INF", inf, 1_000)

    assert nan_result.status == "NON_FINITE_CURRENT_VOLUME"
    assert nan_result.relative_volume is None
    assert inf_result.status == "NON_FINITE_CURRENT_VOLUME"
    assert inf_result.relative_volume is None


def test_nan_and_infinity_historical_average_volume_fail() -> None:
    nan_result = calculate_relative_volume("NAN", 1_000, nan)
    inf_result = calculate_relative_volume("INF", 1_000, inf)

    assert nan_result.status == "NON_FINITE_HISTORICAL_AVERAGE_VOLUME"
    assert nan_result.relative_volume is None
    assert inf_result.status == "NON_FINITE_HISTORICAL_AVERAGE_VOLUME"
    assert inf_result.relative_volume is None


def test_booleans_are_rejected_as_volumes() -> None:
    current_result = calculate_relative_volume("BOOL", True, 1_000)
    average_result = calculate_relative_volume("BOOL", 1_000, False)

    assert current_result.status == "INVALID_CURRENT_VOLUME"
    assert current_result.relative_volume is None
    assert average_result.status == "INVALID_HISTORICAL_AVERAGE_VOLUME"
    assert average_result.relative_volume is None


def test_non_finite_calculated_relative_volume_fails() -> None:
    result = calculate_relative_volume("HUGE", 1e308, 1e-308)

    assert result.relative_volume is None
    assert result.status == "NON_FINITE_RELATIVE_VOLUME"


def test_result_list_preserves_input_order_and_failures() -> None:
    inputs = [
        RelativeVolumeCalculationInput("aaa", 2_000, 1_000),
        RelativeVolumeCalculationInput("", 2_000, 1_000),
        RelativeVolumeCalculationInput("bbb", 6_000, 3_000),
    ]

    results = calculate_relative_volume_results(inputs)

    assert [result.symbol for result in results] == ["AAA", "", "BBB"]
    assert [result.status for result in results] == [
        "OK",
        "EMPTY_SYMBOL",
        "OK",
    ]


def test_batch_mapping_returns_only_successful_values() -> None:
    inputs = [
        RelativeVolumeCalculationInput("good", 4_000, 1_000),
        RelativeVolumeCalculationInput("bad", 0, 1_000),
        RelativeVolumeCalculationInput("also_good", 9_000, 3_000),
    ]

    assert calculate_relative_volumes(inputs) == {
        "GOOD": 4.0,
        "ALSO_GOOD": 3.0,
    }


def test_all_invalid_batch_returns_empty_mapping() -> None:
    inputs = [
        RelativeVolumeCalculationInput("", 4_000, 1_000),
        RelativeVolumeCalculationInput("bad", None, 1_000),  # type: ignore[arg-type]
        RelativeVolumeCalculationInput("also_bad", 1_000, 0),
    ]

    assert calculate_relative_volumes(inputs) == {}
    assert [result.status for result in calculate_relative_volume_results(inputs)] == [
        "EMPTY_SYMBOL",
        "INVALID_CURRENT_VOLUME",
        "NON_POSITIVE_HISTORICAL_AVERAGE_VOLUME",
    ]


def test_duplicate_symbol_mapping_uses_last_successful_value() -> None:
    inputs = [
        RelativeVolumeCalculationInput("dup", 2_000, 1_000),
        RelativeVolumeCalculationInput("DUP", 0, 1_000),
        RelativeVolumeCalculationInput(" dup ", 5_000, 1_000),
    ]

    assert calculate_relative_volumes(inputs) == {"DUP": 5.0}


def test_status_values_are_stable_strings() -> None:
    assert RelativeVolumeStatus.OK == "OK"
    assert RelativeVolumeStatus.EMPTY_SYMBOL == "EMPTY_SYMBOL"
    assert RelativeVolumeStatus.INVALID_CURRENT_VOLUME == "INVALID_CURRENT_VOLUME"
    assert (
        RelativeVolumeStatus.INVALID_HISTORICAL_AVERAGE_VOLUME
        == "INVALID_HISTORICAL_AVERAGE_VOLUME"
    )
    assert (
        RelativeVolumeStatus.NON_POSITIVE_CURRENT_VOLUME
        == "NON_POSITIVE_CURRENT_VOLUME"
    )
    assert (
        RelativeVolumeStatus.NON_POSITIVE_HISTORICAL_AVERAGE_VOLUME
        == "NON_POSITIVE_HISTORICAL_AVERAGE_VOLUME"
    )
    assert (
        RelativeVolumeStatus.NON_FINITE_CURRENT_VOLUME
        == "NON_FINITE_CURRENT_VOLUME"
    )
    assert (
        RelativeVolumeStatus.NON_FINITE_HISTORICAL_AVERAGE_VOLUME
        == "NON_FINITE_HISTORICAL_AVERAGE_VOLUME"
    )
    assert (
        RelativeVolumeStatus.NON_FINITE_RELATIVE_VOLUME
        == "NON_FINITE_RELATIVE_VOLUME"
    )


def test_calculator_module_has_no_network_or_credential_behavior() -> None:
    source = Path(
        "src/market_sentry/data/relative_volume_calculator.py"
    ).read_text(encoding="utf-8")

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
