"""Offline time-of-day relative-volume calculation helpers.

This module calculates time-of-day RVOL only from caller-supplied cumulative
volume inputs at an exact caller-supplied bucket. It does not fetch data,
discover symbols, build providers, or infer market-session details.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any


DEFAULT_MINIMUM_HISTORICAL_SESSIONS = 20


class TimeOfDayRelativeVolumeStatus:
    """Stable status/reason codes for time-of-day RVOL results."""

    OK = "OK"
    EMPTY_SYMBOL = "EMPTY_SYMBOL"
    EMPTY_BUCKET = "EMPTY_BUCKET"
    INVALID_MINIMUM_HISTORICAL_SESSIONS = (
        "INVALID_MINIMUM_HISTORICAL_SESSIONS"
    )
    INVALID_CURRENT_CUMULATIVE_VOLUME = "INVALID_CURRENT_CUMULATIVE_VOLUME"
    NON_FINITE_CURRENT_CUMULATIVE_VOLUME = (
        "NON_FINITE_CURRENT_CUMULATIVE_VOLUME"
    )
    NON_POSITIVE_CURRENT_CUMULATIVE_VOLUME = (
        "NON_POSITIVE_CURRENT_CUMULATIVE_VOLUME"
    )
    NO_HISTORICAL_OBSERVATIONS = "NO_HISTORICAL_OBSERVATIONS"
    INSUFFICIENT_HISTORICAL_OBSERVATIONS = (
        "INSUFFICIENT_HISTORICAL_OBSERVATIONS"
    )
    INVALID_HISTORICAL_SESSION_ID = "INVALID_HISTORICAL_SESSION_ID"
    DUPLICATE_HISTORICAL_SESSION_ID = "DUPLICATE_HISTORICAL_SESSION_ID"
    MISMATCHED_HISTORICAL_BUCKET = "MISMATCHED_HISTORICAL_BUCKET"
    INVALID_HISTORICAL_CUMULATIVE_VOLUME = (
        "INVALID_HISTORICAL_CUMULATIVE_VOLUME"
    )
    NON_FINITE_HISTORICAL_CUMULATIVE_VOLUME = (
        "NON_FINITE_HISTORICAL_CUMULATIVE_VOLUME"
    )
    NON_POSITIVE_HISTORICAL_CUMULATIVE_VOLUME = (
        "NON_POSITIVE_HISTORICAL_CUMULATIVE_VOLUME"
    )
    INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME = (
        "INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME"
    )
    NON_FINITE_TIME_OF_DAY_RVOL = "NON_FINITE_TIME_OF_DAY_RVOL"


@dataclass(frozen=True)
class HistoricalCumulativeVolumeObservation:
    """One fixture observation at a caller-supplied session bucket."""

    session_id: str
    bucket: str
    cumulative_volume: float | int


@dataclass(frozen=True)
class TimeOfDayRelativeVolumeInput:
    """Explicit inputs for one time-of-day RVOL calculation."""

    symbol: str
    bucket: str
    current_cumulative_volume: float | int
    historical_observations: Sequence[HistoricalCumulativeVolumeObservation]


@dataclass(frozen=True)
class TimeOfDayRelativeVolumeResult:
    """Inspectable result for one time-of-day RVOL calculation."""

    symbol: str
    bucket: str
    relative_volume: float | None
    historical_average_cumulative_volume: float | None
    status: str
    reason: str | None = None
    observation_count: int = 0


def _normalize_symbol(symbol: Any) -> str:
    if symbol is None:
        return ""
    return str(symbol).strip().upper()


def _normalize_bucket(bucket: Any) -> str:
    if bucket is None:
        return ""
    return str(bucket).strip()


def _normalize_session_id(session_id: Any) -> str:
    if not isinstance(session_id, str):
        return ""
    return session_id.strip()


def _fail(
    symbol: str,
    bucket: str,
    status: str,
    *,
    observation_count: int = 0,
) -> TimeOfDayRelativeVolumeResult:
    return TimeOfDayRelativeVolumeResult(
        symbol=symbol,
        bucket=bucket,
        relative_volume=None,
        historical_average_cumulative_volume=None,
        status=status,
        reason=status,
        observation_count=observation_count,
    )


def _is_valid_minimum_historical_sessions(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _coerce_number(value: Any, invalid_status: str) -> tuple[float | None, str | None]:
    if value is None or isinstance(value, bool):
        return None, invalid_status
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, invalid_status
    return number, None


def calculate_time_of_day_relative_volume(
    symbol: str,
    bucket: str,
    current_cumulative_volume: float | int,
    historical_observations: Sequence[HistoricalCumulativeVolumeObservation],
    *,
    minimum_historical_sessions: int = DEFAULT_MINIMUM_HISTORICAL_SESSIONS,
) -> TimeOfDayRelativeVolumeResult:
    """Calculate time-of-day RVOL from explicit fixture inputs."""

    normalized_symbol = _normalize_symbol(symbol)
    normalized_bucket = _normalize_bucket(bucket)
    observations = list(historical_observations)
    observation_count = len(observations)

    if not normalized_symbol:
        return _fail(
            "",
            normalized_bucket,
            TimeOfDayRelativeVolumeStatus.EMPTY_SYMBOL,
            observation_count=observation_count,
        )
    if not normalized_bucket:
        return _fail(
            normalized_symbol,
            "",
            TimeOfDayRelativeVolumeStatus.EMPTY_BUCKET,
            observation_count=observation_count,
        )
    if not _is_valid_minimum_historical_sessions(minimum_historical_sessions):
        return _fail(
            normalized_symbol,
            normalized_bucket,
            TimeOfDayRelativeVolumeStatus.INVALID_MINIMUM_HISTORICAL_SESSIONS,
            observation_count=observation_count,
        )

    current_volume, current_error = _coerce_number(
        current_cumulative_volume,
        TimeOfDayRelativeVolumeStatus.INVALID_CURRENT_CUMULATIVE_VOLUME,
    )
    if current_error is not None:
        return _fail(
            normalized_symbol,
            normalized_bucket,
            current_error,
            observation_count=observation_count,
        )
    if not isfinite(current_volume):
        return _fail(
            normalized_symbol,
            normalized_bucket,
            TimeOfDayRelativeVolumeStatus.NON_FINITE_CURRENT_CUMULATIVE_VOLUME,
            observation_count=observation_count,
        )
    if current_volume <= 0:
        return _fail(
            normalized_symbol,
            normalized_bucket,
            TimeOfDayRelativeVolumeStatus.NON_POSITIVE_CURRENT_CUMULATIVE_VOLUME,
            observation_count=observation_count,
        )

    if observation_count == 0:
        return _fail(
            normalized_symbol,
            normalized_bucket,
            TimeOfDayRelativeVolumeStatus.NO_HISTORICAL_OBSERVATIONS,
            observation_count=0,
        )
    if observation_count < minimum_historical_sessions:
        return _fail(
            normalized_symbol,
            normalized_bucket,
            TimeOfDayRelativeVolumeStatus.INSUFFICIENT_HISTORICAL_OBSERVATIONS,
            observation_count=observation_count,
        )

    seen_session_ids: set[str] = set()
    cumulative_volumes: list[float] = []
    for observation in observations:
        session_id = _normalize_session_id(getattr(observation, "session_id", None))
        if not session_id:
            return _fail(
                normalized_symbol,
                normalized_bucket,
                TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_SESSION_ID,
                observation_count=observation_count,
            )
        if session_id in seen_session_ids:
            return _fail(
                normalized_symbol,
                normalized_bucket,
                TimeOfDayRelativeVolumeStatus.DUPLICATE_HISTORICAL_SESSION_ID,
                observation_count=observation_count,
            )
        seen_session_ids.add(session_id)

        observation_bucket = _normalize_bucket(getattr(observation, "bucket", None))
        if observation_bucket != normalized_bucket:
            return _fail(
                normalized_symbol,
                normalized_bucket,
                TimeOfDayRelativeVolumeStatus.MISMATCHED_HISTORICAL_BUCKET,
                observation_count=observation_count,
            )

        cumulative_volume, volume_error = _coerce_number(
            getattr(observation, "cumulative_volume", None),
            TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_CUMULATIVE_VOLUME,
        )
        if volume_error is not None:
            return _fail(
                normalized_symbol,
                normalized_bucket,
                volume_error,
                observation_count=observation_count,
            )
        if not isfinite(cumulative_volume):
            return _fail(
                normalized_symbol,
                normalized_bucket,
                TimeOfDayRelativeVolumeStatus.NON_FINITE_HISTORICAL_CUMULATIVE_VOLUME,
                observation_count=observation_count,
            )
        if cumulative_volume <= 0:
            return _fail(
                normalized_symbol,
                normalized_bucket,
                TimeOfDayRelativeVolumeStatus.NON_POSITIVE_HISTORICAL_CUMULATIVE_VOLUME,
                observation_count=observation_count,
            )
        cumulative_volumes.append(cumulative_volume)

    historical_average = sum(cumulative_volumes) / observation_count
    if not isfinite(historical_average) or historical_average <= 0:
        return _fail(
            normalized_symbol,
            normalized_bucket,
            TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME,
            observation_count=observation_count,
        )

    relative_volume = current_volume / historical_average
    if not isfinite(relative_volume) or relative_volume <= 0:
        return TimeOfDayRelativeVolumeResult(
            symbol=normalized_symbol,
            bucket=normalized_bucket,
            relative_volume=None,
            historical_average_cumulative_volume=historical_average,
            status=TimeOfDayRelativeVolumeStatus.NON_FINITE_TIME_OF_DAY_RVOL,
            reason=TimeOfDayRelativeVolumeStatus.NON_FINITE_TIME_OF_DAY_RVOL,
            observation_count=observation_count,
        )

    return TimeOfDayRelativeVolumeResult(
        symbol=normalized_symbol,
        bucket=normalized_bucket,
        relative_volume=relative_volume,
        historical_average_cumulative_volume=historical_average,
        status=TimeOfDayRelativeVolumeStatus.OK,
        reason=None,
        observation_count=observation_count,
    )


def calculate_time_of_day_relative_volume_results(
    inputs: Sequence[TimeOfDayRelativeVolumeInput],
    *,
    minimum_historical_sessions: int = DEFAULT_MINIMUM_HISTORICAL_SESSIONS,
) -> list[TimeOfDayRelativeVolumeResult]:
    """Return inspectable results while preserving input order."""

    return [
        calculate_time_of_day_relative_volume(
            item.symbol,
            item.bucket,
            item.current_cumulative_volume,
            item.historical_observations,
            minimum_historical_sessions=minimum_historical_sessions,
        )
        for item in inputs
    ]


def calculate_time_of_day_relative_volumes(
    inputs: Sequence[TimeOfDayRelativeVolumeInput],
    *,
    minimum_historical_sessions: int = DEFAULT_MINIMUM_HISTORICAL_SESSIONS,
) -> dict[str, float]:
    """Return usable time-of-day RVOL values keyed by normalized symbol.

    Duplicate normalized symbols are deterministic: the last successful input
    wins. Invalid duplicate inputs are omitted and do not erase prior success.
    """

    relative_volumes: dict[str, float] = {}
    for result in calculate_time_of_day_relative_volume_results(
        inputs,
        minimum_historical_sessions=minimum_historical_sessions,
    ):
        if (
            result.status == TimeOfDayRelativeVolumeStatus.OK
            and result.relative_volume is not None
        ):
            relative_volumes[result.symbol] = result.relative_volume
    return relative_volumes
