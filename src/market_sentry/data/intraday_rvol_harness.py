"""Offline end-to-end intraday RVOL harness.

This module composes the existing intraday bucket adapter with the existing
time-of-day RVOL calculator. It does not fetch data, build providers, or
recompute cumulative volume, historical baselines, or final RVOL itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeSeriesInput,
    TimeOfDayRelativeVolumeInputBuildResult,
    build_time_of_day_relative_volume_input,
)
from market_sentry.data.time_of_day_rvol import (
    TimeOfDayRelativeVolumeInput,
    TimeOfDayRelativeVolumeResult,
    TimeOfDayRelativeVolumeStatus,
    calculate_time_of_day_relative_volume,
)


class IntradayRelativeVolumeHarnessStatus:
    """Stable status/reason codes for harness-level results."""

    OK = "OK"
    FAILED_INPUT_BUILD = "FAILED_INPUT_BUILD"
    FAILED_TIME_OF_DAY_RVOL = "FAILED_TIME_OF_DAY_RVOL"


@dataclass(frozen=True)
class IntradayRelativeVolumeHarnessInput:
    """Explicit fixture inputs for one end-to-end intraday RVOL run."""

    current_series: IntradayVolumeSeriesInput
    historical_series: Sequence[IntradayVolumeSeriesInput]


@dataclass(frozen=True)
class IntradayRelativeVolumeHarnessResult:
    """Inspectable result preserving lower-level artifacts."""

    symbol: str
    bucket: str
    relative_volume: float | None
    status: str
    reason: str | None = None
    time_of_day_input: TimeOfDayRelativeVolumeInput | None = None
    input_build_result: TimeOfDayRelativeVolumeInputBuildResult | None = None
    time_of_day_result: TimeOfDayRelativeVolumeResult | None = None


def calculate_intraday_time_of_day_relative_volume(
    input: IntradayRelativeVolumeHarnessInput,
) -> IntradayRelativeVolumeHarnessResult:
    """Run the Phase 13F builder, then Phase 13E TOD RVOL calculator."""

    input_build_result = build_time_of_day_relative_volume_input(
        input.current_series,
        input.historical_series,
    )
    if input_build_result.calculation_input is None:
        return IntradayRelativeVolumeHarnessResult(
            symbol=input_build_result.symbol,
            bucket=input_build_result.bucket,
            relative_volume=None,
            status=IntradayRelativeVolumeHarnessStatus.FAILED_INPUT_BUILD,
            reason=input_build_result.reason or input_build_result.status,
            time_of_day_input=None,
            input_build_result=input_build_result,
            time_of_day_result=None,
        )

    time_of_day_input = input_build_result.calculation_input
    time_of_day_result = calculate_time_of_day_relative_volume(
        time_of_day_input.symbol,
        time_of_day_input.bucket,
        time_of_day_input.current_cumulative_volume,
        time_of_day_input.historical_observations,
    )
    if (
        time_of_day_result.status != TimeOfDayRelativeVolumeStatus.OK
        or time_of_day_result.relative_volume is None
    ):
        return IntradayRelativeVolumeHarnessResult(
            symbol=time_of_day_result.symbol,
            bucket=time_of_day_result.bucket,
            relative_volume=None,
            status=IntradayRelativeVolumeHarnessStatus.FAILED_TIME_OF_DAY_RVOL,
            reason=time_of_day_result.reason or time_of_day_result.status,
            time_of_day_input=time_of_day_input,
            input_build_result=input_build_result,
            time_of_day_result=time_of_day_result,
        )

    return IntradayRelativeVolumeHarnessResult(
        symbol=time_of_day_result.symbol,
        bucket=time_of_day_result.bucket,
        relative_volume=time_of_day_result.relative_volume,
        status=IntradayRelativeVolumeHarnessStatus.OK,
        reason=None,
        time_of_day_input=time_of_day_input,
        input_build_result=input_build_result,
        time_of_day_result=time_of_day_result,
    )


def calculate_intraday_time_of_day_relative_volume_results(
    inputs: Sequence[IntradayRelativeVolumeHarnessInput],
) -> list[IntradayRelativeVolumeHarnessResult]:
    """Return ordered inspectable harness results."""

    return [calculate_intraday_time_of_day_relative_volume(item) for item in inputs]


def calculate_intraday_time_of_day_relative_volumes(
    inputs: Sequence[IntradayRelativeVolumeHarnessInput],
) -> dict[str, float]:
    """Return successful intraday TOD RVOL values keyed by normalized symbol."""

    relative_volumes: dict[str, float] = {}
    for result in calculate_intraday_time_of_day_relative_volume_results(inputs):
        if (
            result.status == IntradayRelativeVolumeHarnessStatus.OK
            and result.relative_volume is not None
        ):
            relative_volumes[result.symbol] = result.relative_volume
    return relative_volumes
