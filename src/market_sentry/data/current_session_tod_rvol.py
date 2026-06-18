"""Offline current-session time-of-day RVOL composition."""

from __future__ import annotations

from dataclasses import dataclass

from market_sentry.data.historical_baseline_composition import (
    HistoricalBaselineCompositionResult,
    HistoricalBaselineCompositionStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    CumulativeVolumeAtBucketResult,
    IntradayBucketStatus,
    IntradayVolumeSeriesInput,
    calculate_cumulative_volume_at_bucket,
)
from market_sentry.data.time_of_day_rvol import (
    TimeOfDayRelativeVolumeInput,
    TimeOfDayRelativeVolumeResult,
    TimeOfDayRelativeVolumeStatus,
    calculate_time_of_day_relative_volume,
)


class CurrentSessionTimeOfDayRvolStatus:
    """Stable status/reason codes for one current-session composition run."""

    OK = "OK"
    BASELINE_FAILED = "BASELINE_FAILED"
    CURRENT_CUMULATIVE_VOLUME_FAILED = "CURRENT_CUMULATIVE_VOLUME_FAILED"
    MISMATCHED_CURRENT_SYMBOL = "MISMATCHED_CURRENT_SYMBOL"
    MISMATCHED_CURRENT_BUCKET = "MISMATCHED_CURRENT_BUCKET"
    MISMATCHED_CURRENT_SESSION_ID = "MISMATCHED_CURRENT_SESSION_ID"
    TIME_OF_DAY_RVOL_FAILED = "TIME_OF_DAY_RVOL_FAILED"


@dataclass(frozen=True)
class CurrentSessionTimeOfDayRvolResult:
    """Final offline TOD RVOL composition result."""

    baseline_result: HistoricalBaselineCompositionResult
    current_result: CumulativeVolumeAtBucketResult | None
    calculation_input: TimeOfDayRelativeVolumeInput | None
    time_of_day_result: TimeOfDayRelativeVolumeResult | None
    status: str
    reason: str | None = None


def _result(
    *,
    baseline_result: HistoricalBaselineCompositionResult,
    current_result: CumulativeVolumeAtBucketResult | None,
    calculation_input: TimeOfDayRelativeVolumeInput | None,
    time_of_day_result: TimeOfDayRelativeVolumeResult | None,
    status: str,
    reason: str | None = None,
) -> CurrentSessionTimeOfDayRvolResult:
    return CurrentSessionTimeOfDayRvolResult(
        baseline_result=baseline_result,
        current_result=current_result,
        calculation_input=calculation_input,
        time_of_day_result=time_of_day_result,
        status=status,
        reason=reason,
    )


def _prefixed_reason(prefix: str, status: str) -> str:
    return f"{prefix}:{status}"


def compose_current_session_time_of_day_rvol(
    current_series: IntradayVolumeSeriesInput,
    baseline_result: HistoricalBaselineCompositionResult,
) -> CurrentSessionTimeOfDayRvolResult:
    """Compose one current cumulative-volume result with one baseline artifact."""

    if baseline_result.status != HistoricalBaselineCompositionStatus.OK:
        return _result(
            baseline_result=baseline_result,
            current_result=None,
            calculation_input=None,
            time_of_day_result=None,
            status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
            reason=_prefixed_reason(
                CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
                baseline_result.status,
            ),
        )

    current_result = calculate_cumulative_volume_at_bucket(current_series)
    if current_result.status != IntradayBucketStatus.OK:
        return _result(
            baseline_result=baseline_result,
            current_result=current_result,
            calculation_input=None,
            time_of_day_result=None,
            status=CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED,
            reason=_prefixed_reason(
                CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED,
                current_result.status,
            ),
        )

    if current_result.symbol != baseline_result.symbol:
        return _result(
            baseline_result=baseline_result,
            current_result=current_result,
            calculation_input=None,
            time_of_day_result=None,
            status=CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SYMBOL,
            reason=CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SYMBOL,
        )
    if current_result.bucket != baseline_result.bucket:
        return _result(
            baseline_result=baseline_result,
            current_result=current_result,
            calculation_input=None,
            time_of_day_result=None,
            status=CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_BUCKET,
            reason=CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_BUCKET,
        )
    if current_result.session_id != baseline_result.current_session_id:
        return _result(
            baseline_result=baseline_result,
            current_result=current_result,
            calculation_input=None,
            time_of_day_result=None,
            status=CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SESSION_ID,
            reason=CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SESSION_ID,
        )

    calculation_input = TimeOfDayRelativeVolumeInput(
        symbol=current_result.symbol,
        bucket=current_result.bucket,
        current_cumulative_volume=current_result.cumulative_volume,
        historical_observations=baseline_result.observations,
    )
    time_of_day_result = calculate_time_of_day_relative_volume(
        calculation_input.symbol,
        calculation_input.bucket,
        calculation_input.current_cumulative_volume,
        calculation_input.historical_observations,
        minimum_historical_sessions=baseline_result.minimum_historical_sessions,
    )
    if time_of_day_result.status != TimeOfDayRelativeVolumeStatus.OK:
        return _result(
            baseline_result=baseline_result,
            current_result=current_result,
            calculation_input=calculation_input,
            time_of_day_result=time_of_day_result,
            status=CurrentSessionTimeOfDayRvolStatus.TIME_OF_DAY_RVOL_FAILED,
            reason=_prefixed_reason(
                CurrentSessionTimeOfDayRvolStatus.TIME_OF_DAY_RVOL_FAILED,
                time_of_day_result.status,
            ),
        )

    return _result(
        baseline_result=baseline_result,
        current_result=current_result,
        calculation_input=calculation_input,
        time_of_day_result=time_of_day_result,
        status=CurrentSessionTimeOfDayRvolStatus.OK,
        reason=None,
    )
