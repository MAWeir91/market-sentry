"""Offline historical baseline composition from assembled sessions.

This module consumes Phase 14D session assembly results and produces ordered
historical cumulative-volume observations for a later TOD RVOL calculation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from market_sentry.data.historical_session_assembly import (
    HistoricalSessionAssemblyResult,
    HistoricalSessionAssemblyStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    CumulativeVolumeAtBucketResult,
    IntradayBucketStatus,
    calculate_cumulative_volume_at_bucket,
)
from market_sentry.data.time_of_day_rvol import (
    DEFAULT_MINIMUM_HISTORICAL_SESSIONS,
    HistoricalCumulativeVolumeObservation,
)


class HistoricalBaselineCompositionStatus:
    """Stable status/reason codes for a baseline composition run."""

    OK = "OK"
    INVALID_TARGET_SYMBOL = "INVALID_TARGET_SYMBOL"
    INVALID_TARGET_BUCKET = "INVALID_TARGET_BUCKET"
    INVALID_CURRENT_SESSION_ID = "INVALID_CURRENT_SESSION_ID"
    INVALID_MINIMUM_HISTORICAL_SESSIONS = "INVALID_MINIMUM_HISTORICAL_SESSIONS"
    INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS = (
        "INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS"
    )


class HistoricalBaselineSessionStatus:
    """Stable status/reason codes for one supplied assembled session."""

    OK = "OK"
    ASSEMBLY_FAILED = "ASSEMBLY_FAILED"
    MISSING_INTRADAY_SERIES = "MISSING_INTRADAY_SERIES"
    MISMATCHED_HISTORICAL_SYMBOL = "MISMATCHED_HISTORICAL_SYMBOL"
    MISMATCHED_HISTORICAL_BUCKET = "MISMATCHED_HISTORICAL_BUCKET"
    CURRENT_SESSION_IN_HISTORY = "CURRENT_SESSION_IN_HISTORY"
    DUPLICATE_HISTORICAL_SESSION_ID = "DUPLICATE_HISTORICAL_SESSION_ID"
    CUMULATIVE_VOLUME_FAILED = "CUMULATIVE_VOLUME_FAILED"


@dataclass(frozen=True)
class HistoricalBaselineCompositionRequest:
    """Target identity and required observation count for one baseline run."""

    symbol: str
    bucket: str
    current_session_id: str
    minimum_historical_sessions: int = DEFAULT_MINIMUM_HISTORICAL_SESSIONS


@dataclass(frozen=True)
class HistoricalBaselineSessionResult:
    """Inspectable outcome for one supplied assembly result."""

    assembly_result: HistoricalSessionAssemblyResult
    cumulative_result: CumulativeVolumeAtBucketResult | None
    observation: HistoricalCumulativeVolumeObservation | None
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class HistoricalBaselineCompositionResult:
    """Ordered historical-baseline artifact without final RVOL calculation."""

    symbol: str
    bucket: str
    current_session_id: str
    minimum_historical_sessions: int | None
    observations: tuple[HistoricalCumulativeVolumeObservation, ...]
    session_results: tuple[HistoricalBaselineSessionResult, ...]
    eligible_session_count: int
    status: str
    reason: str | None = None


def _normalize_symbol(symbol: Any) -> str:
    if symbol is None:
        return ""
    return str(symbol).strip().upper()


def _normalize_label(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _invalid_result(
    *,
    symbol: str,
    bucket: str,
    current_session_id: str,
    minimum_historical_sessions: int | None,
    status: str,
) -> HistoricalBaselineCompositionResult:
    return HistoricalBaselineCompositionResult(
        symbol=symbol,
        bucket=bucket,
        current_session_id=current_session_id,
        minimum_historical_sessions=minimum_historical_sessions,
        observations=(),
        session_results=(),
        eligible_session_count=0,
        status=status,
        reason=status,
    )


def _validate_request(
    request: HistoricalBaselineCompositionRequest,
) -> tuple[str, str, str, int | None, str | None]:
    symbol = _normalize_symbol(request.symbol)
    bucket = _normalize_label(request.bucket)
    current_session_id = _normalize_label(request.current_session_id)
    minimum = request.minimum_historical_sessions

    if not symbol:
        return symbol, bucket, current_session_id, minimum, (
            HistoricalBaselineCompositionStatus.INVALID_TARGET_SYMBOL
        )
    if not bucket:
        return symbol, bucket, current_session_id, minimum, (
            HistoricalBaselineCompositionStatus.INVALID_TARGET_BUCKET
        )
    if not current_session_id:
        return symbol, bucket, current_session_id, minimum, (
            HistoricalBaselineCompositionStatus.INVALID_CURRENT_SESSION_ID
        )
    if (
        isinstance(minimum, bool)
        or not isinstance(minimum, int)
        or minimum < DEFAULT_MINIMUM_HISTORICAL_SESSIONS
    ):
        return symbol, bucket, current_session_id, None, (
            HistoricalBaselineCompositionStatus.INVALID_MINIMUM_HISTORICAL_SESSIONS
        )
    return symbol, bucket, current_session_id, minimum, None


def _series_identity(result: HistoricalSessionAssemblyResult) -> tuple[str, str, str]:
    series = result.intraday_series
    if series is None:
        return "", "", ""
    return (
        _normalize_symbol(series.symbol),
        _normalize_label(series.session_id),
        _normalize_label(series.bucket),
    )


def _eligible_duplicate_keys(
    assembly_results: Sequence[HistoricalSessionAssemblyResult],
    *,
    symbol: str,
    bucket: str,
    current_session_id: str,
) -> set[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for result in assembly_results:
        if result.status != HistoricalSessionAssemblyStatus.OK:
            continue
        series_symbol, session_id, series_bucket = _series_identity(result)
        if not result.intraday_series:
            continue
        if series_symbol != symbol or series_bucket != bucket:
            continue
        if session_id == current_session_id:
            continue
        keys.append((series_symbol, session_id))

    counts = Counter(keys)
    return {key for key, count in counts.items() if count > 1}


def _session_result(
    assembly_result: HistoricalSessionAssemblyResult,
    *,
    status: str,
    reason: str | None = None,
    cumulative_result: CumulativeVolumeAtBucketResult | None = None,
    observation: HistoricalCumulativeVolumeObservation | None = None,
) -> HistoricalBaselineSessionResult:
    return HistoricalBaselineSessionResult(
        assembly_result=assembly_result,
        cumulative_result=cumulative_result,
        observation=observation,
        status=status,
        reason=reason if reason is not None else status,
    )


def _compose_session(
    assembly_result: HistoricalSessionAssemblyResult,
    *,
    symbol: str,
    bucket: str,
    current_session_id: str,
    duplicate_keys: set[tuple[str, str]],
) -> HistoricalBaselineSessionResult:
    if assembly_result.status != HistoricalSessionAssemblyStatus.OK:
        return _session_result(
            assembly_result,
            status=HistoricalBaselineSessionStatus.ASSEMBLY_FAILED,
            reason=f"{HistoricalBaselineSessionStatus.ASSEMBLY_FAILED}:{assembly_result.status}",
        )

    series = assembly_result.intraday_series
    if series is None:
        return _session_result(
            assembly_result,
            status=HistoricalBaselineSessionStatus.MISSING_INTRADAY_SERIES,
        )

    series_symbol, session_id, series_bucket = _series_identity(assembly_result)
    if series_symbol != symbol:
        return _session_result(
            assembly_result,
            status=HistoricalBaselineSessionStatus.MISMATCHED_HISTORICAL_SYMBOL,
        )
    if series_bucket != bucket:
        return _session_result(
            assembly_result,
            status=HistoricalBaselineSessionStatus.MISMATCHED_HISTORICAL_BUCKET,
        )
    if session_id == current_session_id:
        return _session_result(
            assembly_result,
            status=HistoricalBaselineSessionStatus.CURRENT_SESSION_IN_HISTORY,
        )
    if (series_symbol, session_id) in duplicate_keys:
        return _session_result(
            assembly_result,
            status=HistoricalBaselineSessionStatus.DUPLICATE_HISTORICAL_SESSION_ID,
        )

    cumulative_result = calculate_cumulative_volume_at_bucket(series)
    if cumulative_result.status != IntradayBucketStatus.OK:
        return _session_result(
            assembly_result,
            status=HistoricalBaselineSessionStatus.CUMULATIVE_VOLUME_FAILED,
            reason=(
                f"{HistoricalBaselineSessionStatus.CUMULATIVE_VOLUME_FAILED}:"
                f"{cumulative_result.status}"
            ),
            cumulative_result=cumulative_result,
        )

    observation = HistoricalCumulativeVolumeObservation(
        session_id=cumulative_result.session_id,
        bucket=cumulative_result.bucket,
        cumulative_volume=cumulative_result.cumulative_volume,
    )
    return HistoricalBaselineSessionResult(
        assembly_result=assembly_result,
        cumulative_result=cumulative_result,
        observation=observation,
        status=HistoricalBaselineSessionStatus.OK,
        reason=None,
    )


def compose_historical_baseline(
    assembly_results: Sequence[HistoricalSessionAssemblyResult],
    request: HistoricalBaselineCompositionRequest,
) -> HistoricalBaselineCompositionResult:
    """Compose ordered historical baseline observations from assembled sessions."""

    symbol, bucket, current_session_id, minimum, request_error = _validate_request(request)
    if request_error is not None:
        return _invalid_result(
            symbol=symbol,
            bucket=bucket,
            current_session_id=current_session_id,
            minimum_historical_sessions=minimum,
            status=request_error,
        )

    assembly_results_tuple = tuple(assembly_results)
    duplicate_keys = _eligible_duplicate_keys(
        assembly_results_tuple,
        symbol=symbol,
        bucket=bucket,
        current_session_id=current_session_id,
    )

    session_results = tuple(
        _compose_session(
            assembly_result,
            symbol=symbol,
            bucket=bucket,
            current_session_id=current_session_id,
            duplicate_keys=duplicate_keys,
        )
        for assembly_result in assembly_results_tuple
    )
    observations = tuple(
        result.observation
        for result in session_results
        if result.observation is not None
    )
    eligible_session_count = len(observations)
    assert minimum is not None
    status = (
        HistoricalBaselineCompositionStatus.OK
        if eligible_session_count >= minimum
        else HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
    )

    return HistoricalBaselineCompositionResult(
        symbol=symbol,
        bucket=bucket,
        current_session_id=current_session_id,
        minimum_historical_sessions=minimum,
        observations=observations,
        session_results=session_results,
        eligible_session_count=eligible_session_count,
        status=status,
        reason=None if status == HistoricalBaselineCompositionStatus.OK else status,
    )
