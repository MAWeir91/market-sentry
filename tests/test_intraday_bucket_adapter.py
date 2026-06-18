from datetime import date, datetime, timezone
from math import inf, nan
from pathlib import Path

from market_sentry.data.intraday_bucket_adapter import (
    CumulativeVolumeAtBucketResult,
    IntradayBucketStatus,
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
    TimeOfDayRelativeVolumeInputBuildResult,
    build_time_of_day_relative_volume_input,
    calculate_cumulative_volume_at_bucket,
    calculate_cumulative_volume_at_bucket_results,
)
from market_sentry.data.time_of_day_rvol import (
    HistoricalCumulativeVolumeObservation,
    TimeOfDayRelativeVolumeInput,
)


def dt(hour: int, minute: int, *, tzinfo=None) -> datetime:
    return datetime(2026, 1, 2, hour, minute, tzinfo=tzinfo)


def make_bars(*, tzinfo=None) -> list[IntradayVolumeBar]:
    return [
        IntradayVolumeBar(dt(9, 31, tzinfo=tzinfo), 100),
        IntradayVolumeBar(dt(9, 32, tzinfo=tzinfo), 200),
        IntradayVolumeBar(dt(9, 33, tzinfo=tzinfo), 300),
    ]


def make_series(
    symbol: str = "TOD",
    session_id: str = "session-current",
    bucket: str = "09:32",
    cutoff_timestamp: datetime | None = None,
    bars: list[IntradayVolumeBar] | None = None,
) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        cutoff_timestamp=cutoff_timestamp or dt(9, 32),
        bars=bars if bars is not None else make_bars(),
    )


def test_valid_cumulative_sum_through_cutoff() -> None:
    result = calculate_cumulative_volume_at_bucket(make_series())

    assert result == CumulativeVolumeAtBucketResult(
        symbol="TOD",
        session_id="session-current",
        bucket="09:32",
        cutoff_timestamp=dt(9, 32),
        cumulative_volume=300.0,
        status="OK",
        reason=None,
        included_bar_count=2,
        total_bar_count=3,
    )


def test_excludes_bars_after_cutoff() -> None:
    result = calculate_cumulative_volume_at_bucket(
        make_series(cutoff_timestamp=dt(9, 31))
    )

    assert result.status == "OK"
    assert result.cumulative_volume == 100.0
    assert result.included_bar_count == 1
    assert result.total_bar_count == 3


def test_symbol_bucket_and_session_id_normalization() -> None:
    result = calculate_cumulative_volume_at_bucket(
        make_series(symbol="  abc  ", session_id=" session-a ", bucket="  09:32  ")
    )

    assert result.symbol == "ABC"
    assert result.session_id == "session-a"
    assert result.bucket == "09:32"
    assert result.status == "OK"


def test_empty_symbol_empty_bucket_and_invalid_session_id() -> None:
    empty_symbol = calculate_cumulative_volume_at_bucket(make_series(symbol=" "))
    empty_bucket = calculate_cumulative_volume_at_bucket(make_series(bucket=" "))
    invalid_session = calculate_cumulative_volume_at_bucket(make_series(session_id=" "))

    assert empty_symbol.status == "EMPTY_SYMBOL"
    assert empty_symbol.cumulative_volume is None
    assert empty_bucket.status == "EMPTY_BUCKET"
    assert empty_bucket.cumulative_volume is None
    assert invalid_session.status == "INVALID_SESSION_ID"
    assert invalid_session.cumulative_volume is None


def test_valid_datetime_and_rejection_of_date_or_non_datetime_values() -> None:
    valid = calculate_cumulative_volume_at_bucket(make_series())
    bad_cutoff = calculate_cumulative_volume_at_bucket(
        make_series(cutoff_timestamp=date(2026, 1, 2))  # type: ignore[arg-type]
    )
    bad_bar_timestamp = calculate_cumulative_volume_at_bucket(
        make_series(
            bars=[
                IntradayVolumeBar(date(2026, 1, 2), 100),  # type: ignore[arg-type]
            ]
        )
    )
    string_bar_timestamp = calculate_cumulative_volume_at_bucket(
        make_series(
            bars=[
                IntradayVolumeBar("2026-01-02 09:31", 100),  # type: ignore[arg-type]
            ]
        )
    )

    assert valid.status == "OK"
    assert bad_cutoff.status == "INVALID_CUTOFF_TIMESTAMP"
    assert bad_cutoff.cutoff_timestamp is None
    assert bad_bar_timestamp.status == "INVALID_INTRADAY_TIMESTAMP"
    assert string_bar_timestamp.status == "INVALID_INTRADAY_TIMESTAMP"


def test_matching_naive_and_matching_aware_timestamps_are_valid() -> None:
    naive = calculate_cumulative_volume_at_bucket(make_series())
    aware = calculate_cumulative_volume_at_bucket(
        make_series(
            cutoff_timestamp=dt(9, 32, tzinfo=timezone.utc),
            bars=make_bars(tzinfo=timezone.utc),
        )
    )

    assert naive.status == "OK"
    assert aware.status == "OK"


def test_mismatched_timezone_values_fail() -> None:
    result = calculate_cumulative_volume_at_bucket(
        make_series(
            cutoff_timestamp=dt(9, 32, tzinfo=timezone.utc),
            bars=make_bars(),
        )
    )

    assert result.status == "MISMATCHED_TIMESTAMP_TIMEZONE"
    assert result.cumulative_volume is None


def test_duplicate_and_out_of_order_bar_timestamps_fail() -> None:
    duplicate = calculate_cumulative_volume_at_bucket(
        make_series(
            bars=[
                IntradayVolumeBar(dt(9, 31), 100),
                IntradayVolumeBar(dt(9, 31), 200),
            ]
        )
    )
    out_of_order = calculate_cumulative_volume_at_bucket(
        make_series(
            bars=[
                IntradayVolumeBar(dt(9, 32), 100),
                IntradayVolumeBar(dt(9, 31), 200),
            ]
        )
    )

    assert duplicate.status == "DUPLICATE_INTRADAY_TIMESTAMP"
    assert out_of_order.status == "OUT_OF_ORDER_INTRADAY_TIMESTAMP"


def test_no_bars_and_no_bars_at_or_before_cutoff_fail() -> None:
    no_bars = calculate_cumulative_volume_at_bucket(make_series(bars=[]))
    no_included = calculate_cumulative_volume_at_bucket(
        make_series(
            cutoff_timestamp=dt(9, 30),
            bars=make_bars(),
        )
    )

    assert no_bars.status == "NO_INTRADAY_BARS"
    assert no_bars.total_bar_count == 0
    assert no_included.status == "NO_BARS_AT_OR_BEFORE_CUTOFF"
    assert no_included.total_bar_count == 3


def test_invalid_zero_negative_nan_infinity_and_boolean_bar_volume_fail() -> None:
    cases = [
        (None, "INVALID_INTRADAY_VOLUME"),
        ("bad", "INVALID_INTRADAY_VOLUME"),
        (True, "INVALID_INTRADAY_VOLUME"),
        (0, "NON_POSITIVE_INTRADAY_VOLUME"),
        (-1, "NON_POSITIVE_INTRADAY_VOLUME"),
        (nan, "NON_FINITE_INTRADAY_VOLUME"),
        (inf, "NON_FINITE_INTRADAY_VOLUME"),
    ]

    for volume, expected_status in cases:
        result = calculate_cumulative_volume_at_bucket(
            make_series(
                bars=[
                    IntradayVolumeBar(dt(9, 31), volume),  # type: ignore[arg-type]
                ]
            )
        )
        assert result.status == expected_status
        assert result.cumulative_volume is None


def test_bad_bar_after_cutoff_invalidates_entire_series() -> None:
    result = calculate_cumulative_volume_at_bucket(
        make_series(
            cutoff_timestamp=dt(9, 31),
            bars=[
                IntradayVolumeBar(dt(9, 31), 100),
                IntradayVolumeBar(dt(9, 32), 0),
            ],
        )
    )

    assert result.status == "NON_POSITIVE_INTRADAY_VOLUME"
    assert result.cumulative_volume is None


def test_batch_result_order() -> None:
    inputs = [
        make_series(symbol="aaa"),
        make_series(symbol=" "),
        make_series(symbol="bbb"),
    ]

    results = calculate_cumulative_volume_at_bucket_results(inputs)

    assert [result.symbol for result in results] == ["AAA", "", "BBB"]
    assert [result.status for result in results] == ["OK", "EMPTY_SYMBOL", "OK"]


def test_builder_builds_phase_13e_input() -> None:
    current = make_series("build", "current", "09:32")
    history = [
        make_series("BUILD", "hist-1", "09:32"),
        make_series(" build ", "hist-2", "09:32"),
    ]

    result = build_time_of_day_relative_volume_input(current, history)

    assert result == TimeOfDayRelativeVolumeInputBuildResult(
        symbol="BUILD",
        bucket="09:32",
        calculation_input=TimeOfDayRelativeVolumeInput(
            symbol="BUILD",
            bucket="09:32",
            current_cumulative_volume=300.0,
            historical_observations=(
                HistoricalCumulativeVolumeObservation("hist-1", "09:32", 300.0),
                HistoricalCumulativeVolumeObservation("hist-2", "09:32", 300.0),
            ),
        ),
        current_result=calculate_cumulative_volume_at_bucket(current),
        historical_results=tuple(
            calculate_cumulative_volume_at_bucket(series) for series in history
        ),
        status="OK",
        reason=None,
    )


def test_builder_rejects_no_history() -> None:
    result = build_time_of_day_relative_volume_input(make_series(), [])

    assert result.status == "NO_HISTORICAL_SERIES"
    assert result.calculation_input is None
    assert result.historical_results == ()


def test_builder_rejects_failed_current_series() -> None:
    result = build_time_of_day_relative_volume_input(make_series(symbol=" "), [make_series()])

    assert result.status == "FAILED_CURRENT_SERIES"
    assert result.calculation_input is None
    assert result.current_result.status == "EMPTY_SYMBOL"


def test_builder_rejects_failed_historical_series() -> None:
    result = build_time_of_day_relative_volume_input(
        make_series(),
        [make_series(bars=[])],
    )

    assert result.status == "FAILED_HISTORICAL_SERIES"
    assert result.calculation_input is None
    assert result.historical_results[0].status == "NO_INTRADAY_BARS"


def test_builder_rejects_mismatched_symbol_and_bucket() -> None:
    symbol_result = build_time_of_day_relative_volume_input(
        make_series("AAA", "current", "09:32"),
        [make_series("BBB", "hist-1", "09:32")],
    )
    bucket_result = build_time_of_day_relative_volume_input(
        make_series("AAA", "current", "09:32"),
        [make_series("AAA", "hist-1", "09:33", cutoff_timestamp=dt(9, 33))],
    )

    assert symbol_result.status == "MISMATCHED_HISTORICAL_SYMBOL"
    assert symbol_result.calculation_input is None
    assert bucket_result.status == "MISMATCHED_HISTORICAL_BUCKET"
    assert bucket_result.calculation_input is None


def test_builder_rejects_current_session_in_history_and_duplicate_history_ids() -> None:
    current_in_history = build_time_of_day_relative_volume_input(
        make_series("AAA", "current", "09:32"),
        [make_series("AAA", " current ", "09:32")],
    )
    duplicate_history = build_time_of_day_relative_volume_input(
        make_series("AAA", "current", "09:32"),
        [
            make_series("AAA", "hist-1", "09:32"),
            make_series("AAA", " hist-1 ", "09:32"),
        ],
    )

    assert current_in_history.status == "CURRENT_SESSION_IN_HISTORY"
    assert current_in_history.calculation_input is None
    assert duplicate_history.status == "DUPLICATE_HISTORICAL_SESSION_ID"
    assert duplicate_history.calculation_input is None


def test_builder_does_not_calculate_final_rvol() -> None:
    result = build_time_of_day_relative_volume_input(
        make_series("RVOL", "current", "09:32"),
        [make_series("RVOL", "hist-1", "09:32")],
    )

    assert result.calculation_input is not None
    assert not hasattr(result.calculation_input, "relative_volume")


def test_status_values_are_stable_strings() -> None:
    assert IntradayBucketStatus.OK == "OK"
    assert IntradayBucketStatus.EMPTY_SYMBOL == "EMPTY_SYMBOL"
    assert IntradayBucketStatus.EMPTY_BUCKET == "EMPTY_BUCKET"
    assert IntradayBucketStatus.INVALID_SESSION_ID == "INVALID_SESSION_ID"
    assert IntradayBucketStatus.INVALID_CUTOFF_TIMESTAMP == "INVALID_CUTOFF_TIMESTAMP"
    assert IntradayBucketStatus.NO_INTRADAY_BARS == "NO_INTRADAY_BARS"
    assert IntradayBucketStatus.INVALID_INTRADAY_TIMESTAMP == "INVALID_INTRADAY_TIMESTAMP"
    assert (
        IntradayBucketStatus.MISMATCHED_TIMESTAMP_TIMEZONE
        == "MISMATCHED_TIMESTAMP_TIMEZONE"
    )
    assert (
        IntradayBucketStatus.DUPLICATE_INTRADAY_TIMESTAMP
        == "DUPLICATE_INTRADAY_TIMESTAMP"
    )
    assert (
        IntradayBucketStatus.OUT_OF_ORDER_INTRADAY_TIMESTAMP
        == "OUT_OF_ORDER_INTRADAY_TIMESTAMP"
    )
    assert IntradayBucketStatus.INVALID_INTRADAY_VOLUME == "INVALID_INTRADAY_VOLUME"
    assert (
        IntradayBucketStatus.NON_FINITE_INTRADAY_VOLUME
        == "NON_FINITE_INTRADAY_VOLUME"
    )
    assert (
        IntradayBucketStatus.NON_POSITIVE_INTRADAY_VOLUME
        == "NON_POSITIVE_INTRADAY_VOLUME"
    )
    assert (
        IntradayBucketStatus.NO_BARS_AT_OR_BEFORE_CUTOFF
        == "NO_BARS_AT_OR_BEFORE_CUTOFF"
    )
    assert IntradayBucketStatus.NO_HISTORICAL_SERIES == "NO_HISTORICAL_SERIES"
    assert (
        IntradayBucketStatus.MISMATCHED_HISTORICAL_SYMBOL
        == "MISMATCHED_HISTORICAL_SYMBOL"
    )
    assert (
        IntradayBucketStatus.MISMATCHED_HISTORICAL_BUCKET
        == "MISMATCHED_HISTORICAL_BUCKET"
    )
    assert (
        IntradayBucketStatus.CURRENT_SESSION_IN_HISTORY
        == "CURRENT_SESSION_IN_HISTORY"
    )
    assert (
        IntradayBucketStatus.DUPLICATE_HISTORICAL_SESSION_ID
        == "DUPLICATE_HISTORICAL_SESSION_ID"
    )
    assert IntradayBucketStatus.FAILED_CURRENT_SERIES == "FAILED_CURRENT_SERIES"
    assert IntradayBucketStatus.FAILED_HISTORICAL_SERIES == "FAILED_HISTORICAL_SERIES"


def test_module_has_no_network_credential_provider_or_trading_hooks() -> None:
    source = Path("src/market_sentry/data/intraday_bucket_adapter.py").read_text(
        encoding="utf-8"
    )

    forbidden_terms = [
        "urllib",
        "requests",
        "socket",
        "api_key",
        "secret",
        "credential",
        "MARKET_SENTRY_PROVIDER",
        "factory",
        "place_order",
        "execute_order",
        "broker",
    ]

    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
