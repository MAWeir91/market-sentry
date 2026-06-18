from math import inf, nan
from pathlib import Path

from market_sentry.data.time_of_day_rvol import (
    DEFAULT_MINIMUM_HISTORICAL_SESSIONS,
    HistoricalCumulativeVolumeObservation,
    TimeOfDayRelativeVolumeInput,
    TimeOfDayRelativeVolumeResult,
    TimeOfDayRelativeVolumeStatus,
    calculate_time_of_day_relative_volume,
    calculate_time_of_day_relative_volume_results,
    calculate_time_of_day_relative_volumes,
)


def make_observations(
    count: int,
    *,
    bucket: str = "10:00",
    start_volume: int = 1_000,
) -> list[HistoricalCumulativeVolumeObservation]:
    return [
        HistoricalCumulativeVolumeObservation(
            session_id=f"session-{index}",
            bucket=bucket,
            cumulative_volume=start_volume + index,
        )
        for index in range(count)
    ]


def test_valid_time_of_day_rvol_from_explicit_fixture_observations() -> None:
    observations = [
        HistoricalCumulativeVolumeObservation("s1", "10:00", 1_000),
        HistoricalCumulativeVolumeObservation("s2", "10:00", 2_000),
        HistoricalCumulativeVolumeObservation("s3", "10:00", 3_000),
    ]

    result = calculate_time_of_day_relative_volume(
        "tod",
        "10:00",
        4_000,
        observations,
        minimum_historical_sessions=3,
    )

    assert result == TimeOfDayRelativeVolumeResult(
        symbol="TOD",
        bucket="10:00",
        relative_volume=2.0,
        historical_average_cumulative_volume=2_000.0,
        status="OK",
        reason=None,
        observation_count=3,
    )


def test_arithmetic_historical_cumulative_baseline() -> None:
    observations = [
        HistoricalCumulativeVolumeObservation("s1", "11:00", 2_000),
        HistoricalCumulativeVolumeObservation("s2", "11:00", 4_000),
        HistoricalCumulativeVolumeObservation("s3", "11:00", 9_000),
    ]

    result = calculate_time_of_day_relative_volume(
        "BASE",
        "11:00",
        10_000,
        observations,
        minimum_historical_sessions=3,
    )

    assert result.historical_average_cumulative_volume == 5_000.0
    assert result.relative_volume == 2.0


def test_symbol_normalization_and_bucket_trimming() -> None:
    result = calculate_time_of_day_relative_volume(
        "  sym  ",
        " 10:00 ET ",
        2_000,
        make_observations(2, bucket="10:00 ET"),
        minimum_historical_sessions=2,
    )

    assert result.symbol == "SYM"
    assert result.bucket == "10:00 ET"
    assert result.status == "OK"


def test_blank_symbol_and_blank_bucket_failures() -> None:
    symbol_result = calculate_time_of_day_relative_volume(
        " ",
        "10:00",
        2_000,
        make_observations(1),
        minimum_historical_sessions=1,
    )
    bucket_result = calculate_time_of_day_relative_volume(
        "BKT",
        " ",
        2_000,
        make_observations(1),
        minimum_historical_sessions=1,
    )

    assert symbol_result.status == "EMPTY_SYMBOL"
    assert symbol_result.relative_volume is None
    assert bucket_result.status == "EMPTY_BUCKET"
    assert bucket_result.relative_volume is None


def test_default_twenty_session_lookback_is_valid() -> None:
    result = calculate_time_of_day_relative_volume(
        "DEF",
        "10:00",
        30_000,
        make_observations(20),
    )

    assert DEFAULT_MINIMUM_HISTORICAL_SESSIONS == 20
    assert result.status == "OK"
    assert result.observation_count == 20


def test_configurable_smaller_fixture_lookback_is_valid() -> None:
    result = calculate_time_of_day_relative_volume(
        "SMALL",
        "10:00",
        3_000,
        make_observations(2),
        minimum_historical_sessions=2,
    )

    assert result.status == "OK"
    assert result.relative_volume is not None


def test_invalid_minimum_lookback_fails() -> None:
    invalid_values = [True, "20", 0, -1]

    for invalid_value in invalid_values:
        result = calculate_time_of_day_relative_volume(
            "MIN",
            "10:00",
            3_000,
            make_observations(2),
            minimum_historical_sessions=invalid_value,  # type: ignore[arg-type]
        )
        assert result.status == "INVALID_MINIMUM_HISTORICAL_SESSIONS"
        assert result.relative_volume is None


def test_no_observations_and_insufficient_observations_fail() -> None:
    no_observations = calculate_time_of_day_relative_volume(
        "NONE",
        "10:00",
        3_000,
        [],
        minimum_historical_sessions=1,
    )
    insufficient = calculate_time_of_day_relative_volume(
        "SHORT",
        "10:00",
        3_000,
        make_observations(1),
        minimum_historical_sessions=2,
    )

    assert no_observations.status == "NO_HISTORICAL_OBSERVATIONS"
    assert no_observations.observation_count == 0
    assert insufficient.status == "INSUFFICIENT_HISTORICAL_OBSERVATIONS"
    assert insufficient.observation_count == 1


def test_mismatched_observation_bucket_fails() -> None:
    observations = [
        HistoricalCumulativeVolumeObservation("s1", "10:00", 1_000),
        HistoricalCumulativeVolumeObservation("s2", "10:15", 2_000),
    ]

    result = calculate_time_of_day_relative_volume(
        "BKT",
        "10:00",
        3_000,
        observations,
        minimum_historical_sessions=2,
    )

    assert result.status == "MISMATCHED_HISTORICAL_BUCKET"
    assert result.relative_volume is None


def test_invalid_blank_and_duplicate_session_ids_fail() -> None:
    invalid_session = calculate_time_of_day_relative_volume(
        "SID",
        "10:00",
        3_000,
        [HistoricalCumulativeVolumeObservation(123, "10:00", 1_000)],  # type: ignore[arg-type]
        minimum_historical_sessions=1,
    )
    blank_session = calculate_time_of_day_relative_volume(
        "SID",
        "10:00",
        3_000,
        [HistoricalCumulativeVolumeObservation("   ", "10:00", 1_000)],
        minimum_historical_sessions=1,
    )
    duplicate_session = calculate_time_of_day_relative_volume(
        "SID",
        "10:00",
        3_000,
        [
            HistoricalCumulativeVolumeObservation(" session-1 ", "10:00", 1_000),
            HistoricalCumulativeVolumeObservation("session-1", "10:00", 2_000),
        ],
        minimum_historical_sessions=2,
    )

    assert invalid_session.status == "INVALID_HISTORICAL_SESSION_ID"
    assert blank_session.status == "INVALID_HISTORICAL_SESSION_ID"
    assert duplicate_session.status == "DUPLICATE_HISTORICAL_SESSION_ID"


def test_session_ids_are_trimmed_but_case_preserved_for_duplicates() -> None:
    result = calculate_time_of_day_relative_volume(
        "SID",
        "10:00",
        3_000,
        [
            HistoricalCumulativeVolumeObservation("session-1", "10:00", 1_000),
            HistoricalCumulativeVolumeObservation("SESSION-1", "10:00", 2_000),
        ],
        minimum_historical_sessions=2,
    )

    assert result.status == "OK"


def test_invalid_historical_cumulative_volume_fails() -> None:
    missing = calculate_time_of_day_relative_volume(
        "MISS",
        "10:00",
        3_000,
        [HistoricalCumulativeVolumeObservation("s1", "10:00", None)],  # type: ignore[arg-type]
        minimum_historical_sessions=1,
    )
    non_numeric = calculate_time_of_day_relative_volume(
        "BAD",
        "10:00",
        3_000,
        [HistoricalCumulativeVolumeObservation("s1", "10:00", "nope")],  # type: ignore[arg-type]
        minimum_historical_sessions=1,
    )

    assert missing.status == "INVALID_HISTORICAL_CUMULATIVE_VOLUME"
    assert missing.relative_volume is None
    assert non_numeric.status == "INVALID_HISTORICAL_CUMULATIVE_VOLUME"
    assert non_numeric.relative_volume is None


def test_zero_negative_nan_infinity_and_boolean_historical_volume_fail() -> None:
    cases = [
        (0, "NON_POSITIVE_HISTORICAL_CUMULATIVE_VOLUME"),
        (-1, "NON_POSITIVE_HISTORICAL_CUMULATIVE_VOLUME"),
        (nan, "NON_FINITE_HISTORICAL_CUMULATIVE_VOLUME"),
        (inf, "NON_FINITE_HISTORICAL_CUMULATIVE_VOLUME"),
        (True, "INVALID_HISTORICAL_CUMULATIVE_VOLUME"),
    ]

    for value, expected_status in cases:
        result = calculate_time_of_day_relative_volume(
            "HIST",
            "10:00",
            3_000,
            [HistoricalCumulativeVolumeObservation("s1", "10:00", value)],
            minimum_historical_sessions=1,
        )
        assert result.status == expected_status
        assert result.relative_volume is None


def test_invalid_historical_observation_invalidates_full_input() -> None:
    result = calculate_time_of_day_relative_volume(
        "STRICT",
        "10:00",
        3_000,
        [
            HistoricalCumulativeVolumeObservation("s1", "10:00", 1_000),
            HistoricalCumulativeVolumeObservation("s2", "10:00", 0),
            HistoricalCumulativeVolumeObservation("s3", "10:00", 3_000),
        ],
        minimum_historical_sessions=3,
    )

    assert result.status == "NON_POSITIVE_HISTORICAL_CUMULATIVE_VOLUME"
    assert result.relative_volume is None
    assert result.historical_average_cumulative_volume is None


def test_invalid_current_cumulative_volume_fails() -> None:
    cases = [
        (None, "INVALID_CURRENT_CUMULATIVE_VOLUME"),
        ("bad", "INVALID_CURRENT_CUMULATIVE_VOLUME"),
        (True, "INVALID_CURRENT_CUMULATIVE_VOLUME"),
        (nan, "NON_FINITE_CURRENT_CUMULATIVE_VOLUME"),
        (inf, "NON_FINITE_CURRENT_CUMULATIVE_VOLUME"),
        (0, "NON_POSITIVE_CURRENT_CUMULATIVE_VOLUME"),
        (-1, "NON_POSITIVE_CURRENT_CUMULATIVE_VOLUME"),
    ]

    for value, expected_status in cases:
        result = calculate_time_of_day_relative_volume(
            "CURR",
            "10:00",
            value,  # type: ignore[arg-type]
            make_observations(1),
            minimum_historical_sessions=1,
        )
        assert result.status == expected_status
        assert result.relative_volume is None


def test_non_finite_historical_average_and_final_output_handling() -> None:
    average_result = calculate_time_of_day_relative_volume(
        "AVG",
        "10:00",
        1_000,
        [
            HistoricalCumulativeVolumeObservation("s1", "10:00", 1e308),
            HistoricalCumulativeVolumeObservation("s2", "10:00", 1e308),
        ],
        minimum_historical_sessions=2,
    )
    rvol_result = calculate_time_of_day_relative_volume(
        "RVOL",
        "10:00",
        1e308,
        [HistoricalCumulativeVolumeObservation("s1", "10:00", 1e-308)],
        minimum_historical_sessions=1,
    )

    assert average_result.status == "INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME"
    assert average_result.relative_volume is None
    assert rvol_result.status == "NON_FINITE_TIME_OF_DAY_RVOL"
    assert rvol_result.relative_volume is None
    assert rvol_result.historical_average_cumulative_volume == 1e-308


def test_batch_order_and_successful_mapping_only() -> None:
    inputs = [
        TimeOfDayRelativeVolumeInput("aaa", "10:00", 2_000, make_observations(1)),
        TimeOfDayRelativeVolumeInput("", "10:00", 2_000, make_observations(1)),
        TimeOfDayRelativeVolumeInput("bbb", "10:00", 4_000, make_observations(1)),
    ]

    results = calculate_time_of_day_relative_volume_results(
        inputs,
        minimum_historical_sessions=1,
    )
    mapping = calculate_time_of_day_relative_volumes(
        inputs,
        minimum_historical_sessions=1,
    )

    assert [result.symbol for result in results] == ["AAA", "", "BBB"]
    assert [result.status for result in results] == ["OK", "EMPTY_SYMBOL", "OK"]
    assert mapping == {"AAA": 2.0, "BBB": 4.0}


def test_all_invalid_batch_returns_empty_mapping() -> None:
    inputs = [
        TimeOfDayRelativeVolumeInput("", "10:00", 2_000, make_observations(1)),
        TimeOfDayRelativeVolumeInput("bad", "", 2_000, make_observations(1)),
    ]

    assert (
        calculate_time_of_day_relative_volumes(
            inputs,
            minimum_historical_sessions=1,
        )
        == {}
    )


def test_duplicate_input_symbol_mapping_uses_last_successful_value() -> None:
    inputs = [
        TimeOfDayRelativeVolumeInput("dup", "10:00", 2_000, make_observations(1)),
        TimeOfDayRelativeVolumeInput("DUP", "10:00", 0, make_observations(1)),
        TimeOfDayRelativeVolumeInput(" dup ", "10:00", 5_000, make_observations(1)),
    ]

    assert calculate_time_of_day_relative_volumes(
        inputs,
        minimum_historical_sessions=1,
    ) == {"DUP": 5.0}


def test_status_values_are_stable_strings() -> None:
    assert TimeOfDayRelativeVolumeStatus.OK == "OK"
    assert TimeOfDayRelativeVolumeStatus.EMPTY_SYMBOL == "EMPTY_SYMBOL"
    assert TimeOfDayRelativeVolumeStatus.EMPTY_BUCKET == "EMPTY_BUCKET"
    assert (
        TimeOfDayRelativeVolumeStatus.INVALID_MINIMUM_HISTORICAL_SESSIONS
        == "INVALID_MINIMUM_HISTORICAL_SESSIONS"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.INVALID_CURRENT_CUMULATIVE_VOLUME
        == "INVALID_CURRENT_CUMULATIVE_VOLUME"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.NON_FINITE_CURRENT_CUMULATIVE_VOLUME
        == "NON_FINITE_CURRENT_CUMULATIVE_VOLUME"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.NON_POSITIVE_CURRENT_CUMULATIVE_VOLUME
        == "NON_POSITIVE_CURRENT_CUMULATIVE_VOLUME"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.NO_HISTORICAL_OBSERVATIONS
        == "NO_HISTORICAL_OBSERVATIONS"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.INSUFFICIENT_HISTORICAL_OBSERVATIONS
        == "INSUFFICIENT_HISTORICAL_OBSERVATIONS"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_SESSION_ID
        == "INVALID_HISTORICAL_SESSION_ID"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.DUPLICATE_HISTORICAL_SESSION_ID
        == "DUPLICATE_HISTORICAL_SESSION_ID"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.MISMATCHED_HISTORICAL_BUCKET
        == "MISMATCHED_HISTORICAL_BUCKET"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_CUMULATIVE_VOLUME
        == "INVALID_HISTORICAL_CUMULATIVE_VOLUME"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.NON_FINITE_HISTORICAL_CUMULATIVE_VOLUME
        == "NON_FINITE_HISTORICAL_CUMULATIVE_VOLUME"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.NON_POSITIVE_HISTORICAL_CUMULATIVE_VOLUME
        == "NON_POSITIVE_HISTORICAL_CUMULATIVE_VOLUME"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME
        == "INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME"
    )
    assert (
        TimeOfDayRelativeVolumeStatus.NON_FINITE_TIME_OF_DAY_RVOL
        == "NON_FINITE_TIME_OF_DAY_RVOL"
    )


def test_module_has_no_network_credential_provider_or_trading_hooks() -> None:
    source = Path("src/market_sentry/data/time_of_day_rvol.py").read_text(
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
