"""Offline relative-volume calculation helpers.

This module calculates RVOL only from explicitly supplied inputs. It does not
fetch historical bars, call APIs, discover symbols, or activate live providers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any


class RelativeVolumeStatus:
    """Stable status/reason codes for RVOL calculation results."""

    OK = "OK"
    EMPTY_SYMBOL = "EMPTY_SYMBOL"
    INVALID_CURRENT_VOLUME = "INVALID_CURRENT_VOLUME"
    INVALID_HISTORICAL_AVERAGE_VOLUME = "INVALID_HISTORICAL_AVERAGE_VOLUME"
    NON_POSITIVE_CURRENT_VOLUME = "NON_POSITIVE_CURRENT_VOLUME"
    NON_POSITIVE_HISTORICAL_AVERAGE_VOLUME = (
        "NON_POSITIVE_HISTORICAL_AVERAGE_VOLUME"
    )
    NON_FINITE_CURRENT_VOLUME = "NON_FINITE_CURRENT_VOLUME"
    NON_FINITE_HISTORICAL_AVERAGE_VOLUME = (
        "NON_FINITE_HISTORICAL_AVERAGE_VOLUME"
    )
    NON_FINITE_RELATIVE_VOLUME = "NON_FINITE_RELATIVE_VOLUME"


@dataclass(frozen=True)
class RelativeVolumeCalculationInput:
    """Explicit inputs for one offline RVOL calculation."""

    symbol: str
    current_volume: float | int
    historical_average_volume: float | int


@dataclass(frozen=True)
class RelativeVolumeResult:
    """Inspectable result for one offline RVOL calculation."""

    symbol: str
    relative_volume: float | None
    status: str
    reason: str | None = None


def _normalize_symbol(symbol: Any) -> str:
    if symbol is None:
        return ""
    return str(symbol).strip().upper()


def _coerce_number(value: Any, invalid_status: str) -> tuple[float | None, str | None]:
    if value is None or isinstance(value, bool):
        return None, invalid_status
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, invalid_status
    return number, None


def calculate_relative_volume(
    symbol: Any,
    current_volume: Any,
    historical_average_volume: Any,
) -> RelativeVolumeResult:
    """Calculate RVOL from supplied current and historical average volume."""

    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        return RelativeVolumeResult(
            symbol="",
            relative_volume=None,
            status=RelativeVolumeStatus.EMPTY_SYMBOL,
            reason=RelativeVolumeStatus.EMPTY_SYMBOL,
        )

    current, current_error = _coerce_number(
        current_volume,
        RelativeVolumeStatus.INVALID_CURRENT_VOLUME,
    )
    if current_error is not None:
        return RelativeVolumeResult(
            symbol=normalized_symbol,
            relative_volume=None,
            status=current_error,
            reason=current_error,
        )
    if not isfinite(current):
        return RelativeVolumeResult(
            symbol=normalized_symbol,
            relative_volume=None,
            status=RelativeVolumeStatus.NON_FINITE_CURRENT_VOLUME,
            reason=RelativeVolumeStatus.NON_FINITE_CURRENT_VOLUME,
        )
    if current <= 0:
        return RelativeVolumeResult(
            symbol=normalized_symbol,
            relative_volume=None,
            status=RelativeVolumeStatus.NON_POSITIVE_CURRENT_VOLUME,
            reason=RelativeVolumeStatus.NON_POSITIVE_CURRENT_VOLUME,
        )

    historical_average, historical_error = _coerce_number(
        historical_average_volume,
        RelativeVolumeStatus.INVALID_HISTORICAL_AVERAGE_VOLUME,
    )
    if historical_error is not None:
        return RelativeVolumeResult(
            symbol=normalized_symbol,
            relative_volume=None,
            status=historical_error,
            reason=historical_error,
        )
    if not isfinite(historical_average):
        return RelativeVolumeResult(
            symbol=normalized_symbol,
            relative_volume=None,
            status=RelativeVolumeStatus.NON_FINITE_HISTORICAL_AVERAGE_VOLUME,
            reason=RelativeVolumeStatus.NON_FINITE_HISTORICAL_AVERAGE_VOLUME,
        )
    if historical_average <= 0:
        return RelativeVolumeResult(
            symbol=normalized_symbol,
            relative_volume=None,
            status=RelativeVolumeStatus.NON_POSITIVE_HISTORICAL_AVERAGE_VOLUME,
            reason=RelativeVolumeStatus.NON_POSITIVE_HISTORICAL_AVERAGE_VOLUME,
        )

    relative_volume = current / historical_average
    if not isfinite(relative_volume) or relative_volume <= 0:
        return RelativeVolumeResult(
            symbol=normalized_symbol,
            relative_volume=None,
            status=RelativeVolumeStatus.NON_FINITE_RELATIVE_VOLUME,
            reason=RelativeVolumeStatus.NON_FINITE_RELATIVE_VOLUME,
        )

    return RelativeVolumeResult(
        symbol=normalized_symbol,
        relative_volume=relative_volume,
        status=RelativeVolumeStatus.OK,
        reason=None,
    )


def calculate_relative_volume_results(
    inputs: Sequence[RelativeVolumeCalculationInput],
) -> list[RelativeVolumeResult]:
    """Return inspectable RVOL results while preserving input order."""

    return [
        calculate_relative_volume(
            item.symbol,
            item.current_volume,
            item.historical_average_volume,
        )
        for item in inputs
    ]


def calculate_relative_volumes(
    inputs: Sequence[RelativeVolumeCalculationInput],
) -> dict[str, float]:
    """Return usable RVOL values keyed by normalized symbol.

    Duplicate normalized symbols are deterministic: the last successful result
    wins. Invalid duplicate entries are omitted and do not erase prior success.
    """

    relative_volumes: dict[str, float] = {}
    for result in calculate_relative_volume_results(inputs):
        if result.status == RelativeVolumeStatus.OK and result.relative_volume is not None:
            relative_volumes[result.symbol] = result.relative_volume
    return relative_volumes
