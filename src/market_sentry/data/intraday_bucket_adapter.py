"""Offline intraday bucket adapter for future TOD RVOL inputs.

This module turns caller-supplied intraday per-bar volumes into cumulative
volume values at a caller-supplied cutoff. It does not fetch bars, infer
calendar/session rules, construct providers, or calculate final RVOL.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Any

from market_sentry.data.time_of_day_rvol import (
    HistoricalCumulativeVolumeObservation,
    TimeOfDayRelativeVolumeInput,
)


class IntradayBucketStatus:
    """Stable status/reason codes for intraday bucket adapter results."""

    OK = "OK"
    EMPTY_SYMBOL = "EMPTY_SYMBOL"
    EMPTY_BUCKET = "EMPTY_BUCKET"
    INVALID_SESSION_ID = "INVALID_SESSION_ID"
    INVALID_CUTOFF_TIMESTAMP = "INVALID_CUTOFF_TIMESTAMP"
    NO_INTRADAY_BARS = "NO_INTRADAY_BARS"
    INVALID_INTRADAY_TIMESTAMP = "INVALID_INTRADAY_TIMESTAMP"
    MISMATCHED_TIMESTAMP_TIMEZONE = "MISMATCHED_TIMESTAMP_TIMEZONE"
    DUPLICATE_INTRADAY_TIMESTAMP = "DUPLICATE_INTRADAY_TIMESTAMP"
    OUT_OF_ORDER_INTRADAY_TIMESTAMP = "OUT_OF_ORDER_INTRADAY_TIMESTAMP"
    INVALID_INTRADAY_VOLUME = "INVALID_INTRADAY_VOLUME"
    NON_FINITE_INTRADAY_VOLUME = "NON_FINITE_INTRADAY_VOLUME"
    NON_POSITIVE_INTRADAY_VOLUME = "NON_POSITIVE_INTRADAY_VOLUME"
    NO_BARS_AT_OR_BEFORE_CUTOFF = "NO_BARS_AT_OR_BEFORE_CUTOFF"
    NO_HISTORICAL_SERIES = "NO_HISTORICAL_SERIES"
    MISMATCHED_HISTORICAL_SYMBOL = "MISMATCHED_HISTORICAL_SYMBOL"
    MISMATCHED_HISTORICAL_BUCKET = "MISMATCHED_HISTORICAL_BUCKET"
    CURRENT_SESSION_IN_HISTORY = "CURRENT_SESSION_IN_HISTORY"
    DUPLICATE_HISTORICAL_SESSION_ID = "DUPLICATE_HISTORICAL_SESSION_ID"
    FAILED_CURRENT_SERIES = "FAILED_CURRENT_SERIES"
    FAILED_HISTORICAL_SERIES = "FAILED_HISTORICAL_SERIES"


@dataclass(frozen=True)
class IntradayVolumeBar:
    """One explicitly supplied intraday volume bar."""

    timestamp: datetime
    volume: float | int


@dataclass(frozen=True)
class IntradayVolumeSeriesInput:
    """Intraday bars for one symbol/session/bucket cutoff."""

    symbol: str
    session_id: str
    bucket: str
    cutoff_timestamp: datetime
    bars: Sequence[IntradayVolumeBar]


@dataclass(frozen=True)
class CumulativeVolumeAtBucketResult:
    """Inspectable cumulative-volume result for one intraday series."""

    symbol: str
    session_id: str
    bucket: str
    cutoff_timestamp: datetime | None
    cumulative_volume: float | None
    status: str
    reason: str | None = None
    included_bar_count: int = 0
    total_bar_count: int = 0


@dataclass(frozen=True)
class TimeOfDayRelativeVolumeInputBuildResult:
    """Result for building a Phase 13E time-of-day RVOL input."""

    symbol: str
    bucket: str
    calculation_input: TimeOfDayRelativeVolumeInput | None
    current_result: CumulativeVolumeAtBucketResult
    historical_results: tuple[CumulativeVolumeAtBucketResult, ...]
    status: str
    reason: str | None = None


def _normalize_symbol(symbol: Any) -> str:
    if symbol is None:
        return ""
    return str(symbol).strip().upper()


def _normalize_label(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_datetime(value: Any) -> bool:
    return isinstance(value, datetime)


def _fail(
    symbol: str,
    session_id: str,
    bucket: str,
    cutoff_timestamp: datetime | None,
    status: str,
    *,
    total_bar_count: int = 0,
) -> CumulativeVolumeAtBucketResult:
    return CumulativeVolumeAtBucketResult(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        cutoff_timestamp=cutoff_timestamp,
        cumulative_volume=None,
        status=status,
        reason=status,
        included_bar_count=0,
        total_bar_count=total_bar_count,
    )


def _coerce_volume(value: Any) -> tuple[float | None, str | None]:
    if value is None or isinstance(value, bool):
        return None, IntradayBucketStatus.INVALID_INTRADAY_VOLUME
    try:
        volume = float(value)
    except (TypeError, ValueError):
        return None, IntradayBucketStatus.INVALID_INTRADAY_VOLUME
    if not isfinite(volume):
        return None, IntradayBucketStatus.NON_FINITE_INTRADAY_VOLUME
    if volume <= 0:
        return None, IntradayBucketStatus.NON_POSITIVE_INTRADAY_VOLUME
    return volume, None


def calculate_cumulative_volume_at_bucket(
    series: IntradayVolumeSeriesInput,
) -> CumulativeVolumeAtBucketResult:
    """Sum validated bars through the caller-supplied cutoff timestamp."""

    normalized_symbol = _normalize_symbol(series.symbol)
    normalized_session_id = _normalize_label(series.session_id)
    normalized_bucket = _normalize_label(series.bucket)
    bars = list(series.bars)
    total_bar_count = len(bars)
    cutoff_timestamp = series.cutoff_timestamp
    valid_cutoff = cutoff_timestamp if _is_datetime(cutoff_timestamp) else None

    if not normalized_symbol:
        return _fail(
            "",
            normalized_session_id,
            normalized_bucket,
            valid_cutoff,
            IntradayBucketStatus.EMPTY_SYMBOL,
            total_bar_count=total_bar_count,
        )
    if not normalized_bucket:
        return _fail(
            normalized_symbol,
            normalized_session_id,
            "",
            valid_cutoff,
            IntradayBucketStatus.EMPTY_BUCKET,
            total_bar_count=total_bar_count,
        )
    if not normalized_session_id:
        return _fail(
            normalized_symbol,
            "",
            normalized_bucket,
            valid_cutoff,
            IntradayBucketStatus.INVALID_SESSION_ID,
            total_bar_count=total_bar_count,
        )
    if not _is_datetime(cutoff_timestamp):
        return _fail(
            normalized_symbol,
            normalized_session_id,
            normalized_bucket,
            None,
            IntradayBucketStatus.INVALID_CUTOFF_TIMESTAMP,
            total_bar_count=total_bar_count,
        )
    if total_bar_count == 0:
        return _fail(
            normalized_symbol,
            normalized_session_id,
            normalized_bucket,
            cutoff_timestamp,
            IntradayBucketStatus.NO_INTRADAY_BARS,
            total_bar_count=0,
        )

    previous_timestamp: datetime | None = None
    validated_bars: list[tuple[datetime, float]] = []
    for bar in bars:
        timestamp = getattr(bar, "timestamp", None)
        volume_value = getattr(bar, "volume", None)

        if not _is_datetime(timestamp) or isinstance(timestamp, date) and not isinstance(timestamp, datetime):
            return _fail(
                normalized_symbol,
                normalized_session_id,
                normalized_bucket,
                cutoff_timestamp,
                IntradayBucketStatus.INVALID_INTRADAY_TIMESTAMP,
                total_bar_count=total_bar_count,
            )
        if timestamp.tzinfo != cutoff_timestamp.tzinfo:
            return _fail(
                normalized_symbol,
                normalized_session_id,
                normalized_bucket,
                cutoff_timestamp,
                IntradayBucketStatus.MISMATCHED_TIMESTAMP_TIMEZONE,
                total_bar_count=total_bar_count,
            )
        if previous_timestamp is not None:
            if timestamp == previous_timestamp:
                return _fail(
                    normalized_symbol,
                    normalized_session_id,
                    normalized_bucket,
                    cutoff_timestamp,
                    IntradayBucketStatus.DUPLICATE_INTRADAY_TIMESTAMP,
                    total_bar_count=total_bar_count,
                )
            if timestamp < previous_timestamp:
                return _fail(
                    normalized_symbol,
                    normalized_session_id,
                    normalized_bucket,
                    cutoff_timestamp,
                    IntradayBucketStatus.OUT_OF_ORDER_INTRADAY_TIMESTAMP,
                    total_bar_count=total_bar_count,
                )
        previous_timestamp = timestamp

        volume, volume_error = _coerce_volume(volume_value)
        if volume_error is not None:
            return _fail(
                normalized_symbol,
                normalized_session_id,
                normalized_bucket,
                cutoff_timestamp,
                volume_error,
                total_bar_count=total_bar_count,
            )
        validated_bars.append((timestamp, volume))

    included_volumes = [
        volume for timestamp, volume in validated_bars if timestamp <= cutoff_timestamp
    ]
    if not included_volumes:
        return _fail(
            normalized_symbol,
            normalized_session_id,
            normalized_bucket,
            cutoff_timestamp,
            IntradayBucketStatus.NO_BARS_AT_OR_BEFORE_CUTOFF,
            total_bar_count=total_bar_count,
        )

    cumulative_volume = sum(included_volumes)
    if not isfinite(cumulative_volume) or cumulative_volume <= 0:
        return _fail(
            normalized_symbol,
            normalized_session_id,
            normalized_bucket,
            cutoff_timestamp,
            IntradayBucketStatus.NON_FINITE_INTRADAY_VOLUME,
            total_bar_count=total_bar_count,
        )

    return CumulativeVolumeAtBucketResult(
        symbol=normalized_symbol,
        session_id=normalized_session_id,
        bucket=normalized_bucket,
        cutoff_timestamp=cutoff_timestamp,
        cumulative_volume=cumulative_volume,
        status=IntradayBucketStatus.OK,
        reason=None,
        included_bar_count=len(included_volumes),
        total_bar_count=total_bar_count,
    )


def calculate_cumulative_volume_at_bucket_results(
    series_inputs: Sequence[IntradayVolumeSeriesInput],
) -> list[CumulativeVolumeAtBucketResult]:
    """Return cumulative-volume results while preserving input order."""

    return [calculate_cumulative_volume_at_bucket(series) for series in series_inputs]


def build_time_of_day_relative_volume_input(
    current_series: IntradayVolumeSeriesInput,
    historical_series: Sequence[IntradayVolumeSeriesInput],
) -> TimeOfDayRelativeVolumeInputBuildResult:
    """Build a Phase 13E input without calculating final TOD RVOL."""

    current_result = calculate_cumulative_volume_at_bucket(current_series)
    historical_results = tuple(
        calculate_cumulative_volume_at_bucket(series) for series in historical_series
    )
    symbol = current_result.symbol
    bucket = current_result.bucket

    if current_result.status != IntradayBucketStatus.OK:
        return TimeOfDayRelativeVolumeInputBuildResult(
            symbol=symbol,
            bucket=bucket,
            calculation_input=None,
            current_result=current_result,
            historical_results=historical_results,
            status=IntradayBucketStatus.FAILED_CURRENT_SERIES,
            reason=IntradayBucketStatus.FAILED_CURRENT_SERIES,
        )
    if not historical_results:
        return TimeOfDayRelativeVolumeInputBuildResult(
            symbol=symbol,
            bucket=bucket,
            calculation_input=None,
            current_result=current_result,
            historical_results=historical_results,
            status=IntradayBucketStatus.NO_HISTORICAL_SERIES,
            reason=IntradayBucketStatus.NO_HISTORICAL_SERIES,
        )

    historical_session_ids: set[str] = set()
    observations: list[HistoricalCumulativeVolumeObservation] = []
    for historical_result in historical_results:
        if historical_result.status != IntradayBucketStatus.OK:
            return TimeOfDayRelativeVolumeInputBuildResult(
                symbol=symbol,
                bucket=bucket,
                calculation_input=None,
                current_result=current_result,
                historical_results=historical_results,
                status=IntradayBucketStatus.FAILED_HISTORICAL_SERIES,
                reason=IntradayBucketStatus.FAILED_HISTORICAL_SERIES,
            )
        if historical_result.symbol != symbol:
            return TimeOfDayRelativeVolumeInputBuildResult(
                symbol=symbol,
                bucket=bucket,
                calculation_input=None,
                current_result=current_result,
                historical_results=historical_results,
                status=IntradayBucketStatus.MISMATCHED_HISTORICAL_SYMBOL,
                reason=IntradayBucketStatus.MISMATCHED_HISTORICAL_SYMBOL,
            )
        if historical_result.bucket != bucket:
            return TimeOfDayRelativeVolumeInputBuildResult(
                symbol=symbol,
                bucket=bucket,
                calculation_input=None,
                current_result=current_result,
                historical_results=historical_results,
                status=IntradayBucketStatus.MISMATCHED_HISTORICAL_BUCKET,
                reason=IntradayBucketStatus.MISMATCHED_HISTORICAL_BUCKET,
            )
        if historical_result.session_id == current_result.session_id:
            return TimeOfDayRelativeVolumeInputBuildResult(
                symbol=symbol,
                bucket=bucket,
                calculation_input=None,
                current_result=current_result,
                historical_results=historical_results,
                status=IntradayBucketStatus.CURRENT_SESSION_IN_HISTORY,
                reason=IntradayBucketStatus.CURRENT_SESSION_IN_HISTORY,
            )
        if historical_result.session_id in historical_session_ids:
            return TimeOfDayRelativeVolumeInputBuildResult(
                symbol=symbol,
                bucket=bucket,
                calculation_input=None,
                current_result=current_result,
                historical_results=historical_results,
                status=IntradayBucketStatus.DUPLICATE_HISTORICAL_SESSION_ID,
                reason=IntradayBucketStatus.DUPLICATE_HISTORICAL_SESSION_ID,
            )
        historical_session_ids.add(historical_result.session_id)

        observations.append(
            HistoricalCumulativeVolumeObservation(
                session_id=historical_result.session_id,
                bucket=historical_result.bucket,
                cumulative_volume=historical_result.cumulative_volume,
            )
        )

    return TimeOfDayRelativeVolumeInputBuildResult(
        symbol=symbol,
        bucket=bucket,
        calculation_input=TimeOfDayRelativeVolumeInput(
            symbol=symbol,
            bucket=bucket,
            current_cumulative_volume=current_result.cumulative_volume,
            historical_observations=tuple(observations),
        ),
        current_result=current_result,
        historical_results=historical_results,
        status=IntradayBucketStatus.OK,
        reason=None,
    )
