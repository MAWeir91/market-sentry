"""Offline historical-volume baselines for future RVOL calculation.

This module accepts explicitly supplied completed daily-volume bars and turns
them into historical average-volume baselines. It does not fetch bars, call
APIs, discover symbols, activate providers, or calculate final RVOL.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Any

from market_sentry.data.relative_volume_calculator import (
    RelativeVolumeCalculationInput,
)


DEFAULT_MINIMUM_HISTORICAL_DAYS = 20


class HistoricalVolumeStatus:
    """Stable status/reason codes for historical-volume adapter results."""

    OK = "OK"
    EMPTY_SYMBOL = "EMPTY_SYMBOL"
    NO_HISTORICAL_BARS = "NO_HISTORICAL_BARS"
    INSUFFICIENT_HISTORICAL_BARS = "INSUFFICIENT_HISTORICAL_BARS"
    INVALID_MINIMUM_HISTORICAL_DAYS = "INVALID_MINIMUM_HISTORICAL_DAYS"
    INVALID_SESSION_DATE = "INVALID_SESSION_DATE"
    DUPLICATE_SESSION_DATE = "DUPLICATE_SESSION_DATE"
    INVALID_HISTORICAL_VOLUME = "INVALID_HISTORICAL_VOLUME"
    NON_FINITE_HISTORICAL_VOLUME = "NON_FINITE_HISTORICAL_VOLUME"
    NON_POSITIVE_HISTORICAL_VOLUME = "NON_POSITIVE_HISTORICAL_VOLUME"
    INVALID_HISTORICAL_AVERAGE_VOLUME = "INVALID_HISTORICAL_AVERAGE_VOLUME"
    MISSING_CURRENT_VOLUME = "MISSING_CURRENT_VOLUME"


@dataclass(frozen=True)
class HistoricalDailyVolumeBar:
    """One explicitly supplied completed daily-volume bar."""

    session_date: date
    volume: float | int


@dataclass(frozen=True)
class HistoricalVolumeSeriesInput:
    """Historical daily-volume bars for one symbol."""

    symbol: str
    bars: Sequence[HistoricalDailyVolumeBar]


@dataclass(frozen=True)
class HistoricalAverageVolumeResult:
    """Inspectable historical average-volume baseline result."""

    symbol: str
    historical_average_volume: float | None
    status: str
    reason: str | None = None
    bar_count: int = 0


@dataclass(frozen=True)
class RelativeVolumeInputBuildResult:
    """Result for building Phase 13C RVOL calculation input."""

    symbol: str
    calculation_input: RelativeVolumeCalculationInput | None
    historical_result: HistoricalAverageVolumeResult
    reason: str | None = None


def _normalize_symbol(symbol: Any) -> str:
    if symbol is None:
        return ""
    return str(symbol).strip().upper()


def _fail(
    symbol: str,
    status: str,
    *,
    bar_count: int = 0,
) -> HistoricalAverageVolumeResult:
    return HistoricalAverageVolumeResult(
        symbol=symbol,
        historical_average_volume=None,
        status=status,
        reason=status,
        bar_count=bar_count,
    )


def _is_valid_minimum_historical_days(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_valid_session_date(value: Any) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _coerce_volume(value: Any) -> tuple[float | None, str | None]:
    if value is None or isinstance(value, bool):
        return None, HistoricalVolumeStatus.INVALID_HISTORICAL_VOLUME
    try:
        volume = float(value)
    except (TypeError, ValueError):
        return None, HistoricalVolumeStatus.INVALID_HISTORICAL_VOLUME
    if not isfinite(volume):
        return None, HistoricalVolumeStatus.NON_FINITE_HISTORICAL_VOLUME
    if volume <= 0:
        return None, HistoricalVolumeStatus.NON_POSITIVE_HISTORICAL_VOLUME
    return volume, None


def calculate_historical_average_volume(
    symbol: str,
    bars: Sequence[HistoricalDailyVolumeBar],
    *,
    minimum_historical_days: int = DEFAULT_MINIMUM_HISTORICAL_DAYS,
) -> HistoricalAverageVolumeResult:
    """Calculate an average from supplied completed daily-volume bars."""

    normalized_symbol = _normalize_symbol(symbol)
    bar_list = list(bars)
    bar_count = len(bar_list)

    if not normalized_symbol:
        return _fail(
            "",
            HistoricalVolumeStatus.EMPTY_SYMBOL,
            bar_count=bar_count,
        )
    if not _is_valid_minimum_historical_days(minimum_historical_days):
        return _fail(
            normalized_symbol,
            HistoricalVolumeStatus.INVALID_MINIMUM_HISTORICAL_DAYS,
            bar_count=bar_count,
        )
    if bar_count == 0:
        return _fail(
            normalized_symbol,
            HistoricalVolumeStatus.NO_HISTORICAL_BARS,
            bar_count=0,
        )
    if bar_count < minimum_historical_days:
        return _fail(
            normalized_symbol,
            HistoricalVolumeStatus.INSUFFICIENT_HISTORICAL_BARS,
            bar_count=bar_count,
        )

    seen_dates: set[date] = set()
    validated_bars: list[tuple[date, float]] = []
    for bar in bar_list:
        session_date = getattr(bar, "session_date", None)
        volume_value = getattr(bar, "volume", None)

        if not _is_valid_session_date(session_date):
            return _fail(
                normalized_symbol,
                HistoricalVolumeStatus.INVALID_SESSION_DATE,
                bar_count=bar_count,
            )
        if session_date in seen_dates:
            return _fail(
                normalized_symbol,
                HistoricalVolumeStatus.DUPLICATE_SESSION_DATE,
                bar_count=bar_count,
            )
        seen_dates.add(session_date)

        volume, volume_error = _coerce_volume(volume_value)
        if volume_error is not None:
            return _fail(normalized_symbol, volume_error, bar_count=bar_count)
        validated_bars.append((session_date, volume))

    sorted_bars = sorted(validated_bars, key=lambda item: item[0])
    historical_average = sum(volume for _, volume in sorted_bars) / bar_count
    if not isfinite(historical_average) or historical_average <= 0:
        return _fail(
            normalized_symbol,
            HistoricalVolumeStatus.INVALID_HISTORICAL_AVERAGE_VOLUME,
            bar_count=bar_count,
        )

    return HistoricalAverageVolumeResult(
        symbol=normalized_symbol,
        historical_average_volume=historical_average,
        status=HistoricalVolumeStatus.OK,
        reason=None,
        bar_count=bar_count,
    )


def calculate_historical_average_volume_results(
    inputs: Sequence[HistoricalVolumeSeriesInput],
    *,
    minimum_historical_days: int = DEFAULT_MINIMUM_HISTORICAL_DAYS,
) -> list[HistoricalAverageVolumeResult]:
    """Return inspectable baseline results while preserving input order."""

    return [
        calculate_historical_average_volume(
            item.symbol,
            item.bars,
            minimum_historical_days=minimum_historical_days,
        )
        for item in inputs
    ]


def calculate_historical_average_volumes(
    inputs: Sequence[HistoricalVolumeSeriesInput],
    *,
    minimum_historical_days: int = DEFAULT_MINIMUM_HISTORICAL_DAYS,
) -> dict[str, float]:
    """Return usable historical averages keyed by normalized symbol.

    Duplicate normalized symbols are deterministic: the last successful series
    wins. Invalid duplicate entries are omitted and do not erase prior success.
    """

    averages: dict[str, float] = {}
    for result in calculate_historical_average_volume_results(
        inputs,
        minimum_historical_days=minimum_historical_days,
    ):
        if (
            result.status == HistoricalVolumeStatus.OK
            and result.historical_average_volume is not None
        ):
            averages[result.symbol] = result.historical_average_volume
    return averages


def _normalize_current_volume_mapping(
    current_volume_by_symbol: Mapping[str, float | int],
) -> dict[str, float | int]:
    normalized: dict[str, float | int] = {}
    for symbol, current_volume in current_volume_by_symbol.items():
        if normalized_symbol := _normalize_symbol(symbol):
            normalized[normalized_symbol] = current_volume
    return normalized


def build_relative_volume_calculation_inputs(
    current_volume_by_symbol: Mapping[str, float | int],
    historical_inputs: Sequence[HistoricalVolumeSeriesInput],
    *,
    minimum_historical_days: int = DEFAULT_MINIMUM_HISTORICAL_DAYS,
) -> list[RelativeVolumeInputBuildResult]:
    """Build Phase 13C inputs without calculating final RVOL."""

    normalized_current_volume = _normalize_current_volume_mapping(
        current_volume_by_symbol
    )
    historical_results = calculate_historical_average_volume_results(
        historical_inputs,
        minimum_historical_days=minimum_historical_days,
    )

    build_results: list[RelativeVolumeInputBuildResult] = []
    for historical_result in historical_results:
        if (
            historical_result.status != HistoricalVolumeStatus.OK
            or historical_result.historical_average_volume is None
        ):
            build_results.append(
                RelativeVolumeInputBuildResult(
                    symbol=historical_result.symbol,
                    calculation_input=None,
                    historical_result=historical_result,
                    reason=historical_result.status,
                )
            )
            continue

        if historical_result.symbol not in normalized_current_volume:
            build_results.append(
                RelativeVolumeInputBuildResult(
                    symbol=historical_result.symbol,
                    calculation_input=None,
                    historical_result=historical_result,
                    reason=HistoricalVolumeStatus.MISSING_CURRENT_VOLUME,
                )
            )
            continue

        build_results.append(
            RelativeVolumeInputBuildResult(
                symbol=historical_result.symbol,
                calculation_input=RelativeVolumeCalculationInput(
                    symbol=historical_result.symbol,
                    current_volume=normalized_current_volume[historical_result.symbol],
                    historical_average_volume=(
                        historical_result.historical_average_volume
                    ),
                ),
                historical_result=historical_result,
                reason=None,
            )
        )
    return build_results
