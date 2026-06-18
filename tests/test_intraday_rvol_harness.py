from datetime import datetime
from pathlib import Path

import pytest

from market_sentry.data import intraday_rvol_harness
from market_sentry.data.intraday_bucket_adapter import (
    IntradayBucketStatus,
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
    TimeOfDayRelativeVolumeInputBuildResult,
)
from market_sentry.data.intraday_rvol_harness import (
    IntradayRelativeVolumeHarnessInput,
    IntradayRelativeVolumeHarnessResult,
    IntradayRelativeVolumeHarnessStatus,
    calculate_intraday_time_of_day_relative_volume,
    calculate_intraday_time_of_day_relative_volume_results,
    calculate_intraday_time_of_day_relative_volumes,
)
from market_sentry.data.time_of_day_rvol import (
    TimeOfDayRelativeVolumeInput,
    TimeOfDayRelativeVolumeStatus,
    calculate_time_of_day_relative_volume,
)


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 2, 9, minute)


def make_series(
    symbol: str = "RVOL",
    session_id: str = "current",
    bucket: str = "09:32",
    *,
    start_volume: int = 100,
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


def make_history(
    count: int = 20,
    *,
    symbol: str = "RVOL",
    bucket: str = "09:32",
    start_volume: int = 100,
) -> list[IntradayVolumeSeriesInput]:
    return [
        make_series(
            symbol=symbol,
            session_id=f"hist-{index}",
            bucket=bucket,
            start_volume=start_volume,
        )
        for index in range(count)
    ]


def make_harness_input(
    *,
    symbol: str = "RVOL",
    current_start_volume: int = 200,
    history_start_volume: int = 100,
    history_count: int = 20,
) -> IntradayRelativeVolumeHarnessInput:
    return IntradayRelativeVolumeHarnessInput(
        current_series=make_series(symbol=symbol, start_volume=current_start_volume),
        historical_series=make_history(
            history_count,
            symbol=symbol,
            start_volume=history_start_volume,
        ),
    )


def test_valid_end_to_end_result_from_explicit_fixture_series() -> None:
    result = calculate_intraday_time_of_day_relative_volume(make_harness_input())

    assert result.status == "OK"
    assert result.reason is None
    assert result.symbol == "RVOL"
    assert result.bucket == "09:32"
    assert result.relative_volume == 2.0
    assert result.input_build_result is not None
    assert result.input_build_result.status == IntradayBucketStatus.OK
    assert result.time_of_day_input is not None
    assert result.time_of_day_result is not None
    assert result.time_of_day_result.status == TimeOfDayRelativeVolumeStatus.OK


def test_harness_rvol_equals_phase_13e_result_from_constructed_input() -> None:
    result = calculate_intraday_time_of_day_relative_volume(make_harness_input())
    assert result.time_of_day_input is not None

    expected = calculate_time_of_day_relative_volume(
        result.time_of_day_input.symbol,
        result.time_of_day_input.bucket,
        result.time_of_day_input.current_cumulative_volume,
        result.time_of_day_input.historical_observations,
    )

    assert result.relative_volume == expected.relative_volume
    assert result.time_of_day_result == expected


def test_current_series_build_failure_produces_failed_input_build() -> None:
    result = calculate_intraday_time_of_day_relative_volume(
        IntradayRelativeVolumeHarnessInput(
            current_series=make_series(symbol=" "),
            historical_series=make_history(),
        )
    )

    assert result.status == "FAILED_INPUT_BUILD"
    assert result.reason == "FAILED_CURRENT_SERIES"
    assert result.relative_volume is None
    assert result.input_build_result is not None
    assert result.input_build_result.status == "FAILED_CURRENT_SERIES"
    assert result.input_build_result.current_result.status == "EMPTY_SYMBOL"
    assert result.time_of_day_result is None


def test_current_series_build_failure_does_not_call_phase_13e(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Phase 13E should not be called")

    monkeypatch.setattr(
        intraday_rvol_harness,
        "calculate_time_of_day_relative_volume",
        fail_if_called,
    )

    result = calculate_intraday_time_of_day_relative_volume(
        IntradayRelativeVolumeHarnessInput(
            current_series=make_series(symbol=" "),
            historical_series=make_history(),
        )
    )

    assert result.status == "FAILED_INPUT_BUILD"


def test_historical_series_failure_produces_failed_input_build() -> None:
    result = calculate_intraday_time_of_day_relative_volume(
        IntradayRelativeVolumeHarnessInput(
            current_series=make_series(),
            historical_series=[make_series(session_id="hist-1", bars=[])],
        )
    )

    assert result.status == "FAILED_INPUT_BUILD"
    assert result.reason == "FAILED_HISTORICAL_SERIES"
    assert result.input_build_result is not None
    assert result.input_build_result.historical_results[0].status == "NO_INTRADAY_BARS"
    assert result.time_of_day_result is None


def test_lower_level_input_build_diagnostic_context_remains_inspectable() -> None:
    result = calculate_intraday_time_of_day_relative_volume(
        IntradayRelativeVolumeHarnessInput(
            current_series=make_series("AAA"),
            historical_series=[make_series("BBB", "hist-1")],
        )
    )

    assert result.status == "FAILED_INPUT_BUILD"
    assert result.reason == "MISMATCHED_HISTORICAL_SYMBOL"
    assert result.input_build_result is not None
    assert result.input_build_result.reason == "MISMATCHED_HISTORICAL_SYMBOL"
    assert result.input_build_result.current_result.symbol == "AAA"
    assert result.input_build_result.historical_results[0].symbol == "BBB"


def test_phase_13e_failure_after_successful_build_is_preserved() -> None:
    result = calculate_intraday_time_of_day_relative_volume(
        make_harness_input(history_count=1)
    )

    assert result.status == "FAILED_TIME_OF_DAY_RVOL"
    assert result.reason == "INSUFFICIENT_HISTORICAL_OBSERVATIONS"
    assert result.relative_volume is None
    assert result.input_build_result is not None
    assert result.input_build_result.status == "OK"
    assert result.time_of_day_input is not None
    assert result.time_of_day_result is not None
    assert result.time_of_day_result.status == "INSUFFICIENT_HISTORICAL_OBSERVATIONS"


def test_lower_level_phase_13e_diagnostic_context_remains_inspectable(monkeypatch) -> None:
    def fake_calculator(symbol, bucket, current_cumulative_volume, historical_observations):
        return calculate_time_of_day_relative_volume(
            symbol,
            bucket,
            current_cumulative_volume,
            historical_observations,
            minimum_historical_sessions=21,
        )

    monkeypatch.setattr(
        intraday_rvol_harness,
        "calculate_time_of_day_relative_volume",
        fake_calculator,
    )

    result = calculate_intraday_time_of_day_relative_volume(make_harness_input())

    assert result.status == "FAILED_TIME_OF_DAY_RVOL"
    assert result.time_of_day_result is not None
    assert result.time_of_day_result.observation_count == 20
    assert result.time_of_day_result.status == "INSUFFICIENT_HISTORICAL_OBSERVATIONS"


def test_results_include_builder_and_phase_13e_artifacts() -> None:
    result = calculate_intraday_time_of_day_relative_volume(make_harness_input())

    assert result.input_build_result is not None
    assert result.time_of_day_input == result.input_build_result.calculation_input
    assert result.time_of_day_result is not None


def test_batch_result_order_is_preserved() -> None:
    inputs = [
        make_harness_input(symbol="aaa"),
        IntradayRelativeVolumeHarnessInput(
            current_series=make_series(symbol=" "),
            historical_series=make_history(),
        ),
        make_harness_input(symbol="bbb"),
    ]

    results = calculate_intraday_time_of_day_relative_volume_results(inputs)

    assert [result.symbol for result in results] == ["AAA", "", "BBB"]
    assert [result.status for result in results] == [
        "OK",
        "FAILED_INPUT_BUILD",
        "OK",
    ]


def test_batch_usable_mapping_includes_successes_only() -> None:
    inputs = [
        make_harness_input(symbol="good"),
        IntradayRelativeVolumeHarnessInput(
            current_series=make_series(symbol=" "),
            historical_series=make_history(),
        ),
        make_harness_input(symbol="also_good", current_start_volume=300),
    ]

    assert calculate_intraday_time_of_day_relative_volumes(inputs) == {
        "GOOD": 2.0,
        "ALSO_GOOD": 3.0,
    }


def test_duplicate_normalized_symbol_last_success_wins_invalid_does_not_erase() -> None:
    inputs = [
        make_harness_input(symbol="dup", current_start_volume=200),
        IntradayRelativeVolumeHarnessInput(
            current_series=make_series(symbol="DUP", start_volume=0),
            historical_series=make_history(symbol="DUP"),
        ),
        make_harness_input(symbol=" dup ", current_start_volume=500),
    ]

    assert calculate_intraday_time_of_day_relative_volumes(inputs) == {"DUP": 5.0}


def test_all_invalid_batch_returns_empty_mapping() -> None:
    inputs = [
        IntradayRelativeVolumeHarnessInput(
            current_series=make_series(symbol=" "),
            historical_series=make_history(),
        ),
        make_harness_input(history_count=1),
    ]

    assert calculate_intraday_time_of_day_relative_volumes(inputs) == {}


def test_harness_does_not_calculate_or_alter_lower_level_values(monkeypatch) -> None:
    build_result = TimeOfDayRelativeVolumeInputBuildResult(
        symbol="FAKE",
        bucket="09:32",
        calculation_input=TimeOfDayRelativeVolumeInput(
            symbol="FAKE",
            bucket="09:32",
            current_cumulative_volume=123,
            historical_observations=(),
        ),
        current_result=make_harness_input().current_series and None,  # type: ignore[arg-type]
        historical_results=(),
        status="OK",
        reason=None,
    )

    class FakeTodResult:
        symbol = "FAKE"
        bucket = "09:32"
        relative_volume = 7.5
        status = "OK"
        reason = None

    monkeypatch.setattr(
        intraday_rvol_harness,
        "build_time_of_day_relative_volume_input",
        lambda current, history: build_result,
    )
    monkeypatch.setattr(
        intraday_rvol_harness,
        "calculate_time_of_day_relative_volume",
        lambda *args: FakeTodResult(),
    )

    result = calculate_intraday_time_of_day_relative_volume(make_harness_input())

    assert result.relative_volume == 7.5


def test_status_values_are_stable_strings() -> None:
    assert IntradayRelativeVolumeHarnessStatus.OK == "OK"
    assert (
        IntradayRelativeVolumeHarnessStatus.FAILED_INPUT_BUILD
        == "FAILED_INPUT_BUILD"
    )
    assert (
        IntradayRelativeVolumeHarnessStatus.FAILED_TIME_OF_DAY_RVOL
        == "FAILED_TIME_OF_DAY_RVOL"
    )


def test_harness_module_has_no_network_credential_provider_or_trading_hooks() -> None:
    source = Path("src/market_sentry/data/intraday_rvol_harness.py").read_text(
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
        "transport",
        "fetcher",
        "place_order",
        "execute_order",
        "broker",
    ]

    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
