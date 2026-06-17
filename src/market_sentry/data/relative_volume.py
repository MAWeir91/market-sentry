"""Relative-volume provider boundary for future live-provider phases.

Relative volume remains explicit. This module does not calculate, infer, or
fetch RVOL values from external services.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any, Protocol


class RelativeVolumeProvider(Protocol):
    """Provider contract for explicit relative-volume values."""

    def get_relative_volumes(self, symbols: Sequence[str]) -> dict[str, float]:
        """Return usable relative-volume values keyed by normalized symbol."""
        ...


def normalize_symbol(symbol: str | None) -> str:
    """Normalize a symbol for relative-volume lookups."""

    if symbol is None:
        return ""
    return symbol.strip().upper()


def normalize_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    """Normalize symbols while dropping empty entries and preserving order."""

    return tuple(
        normalized
        for symbol in symbols
        if (normalized := normalize_symbol(symbol))
    )


def normalize_relative_volume(value: Any) -> float | None:
    """Return a positive finite RVOL value, or None when unusable."""

    if value is None or isinstance(value, bool):
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if converted <= 0 or not isfinite(converted):
        return None
    return converted


class StaticRelativeVolumeProvider:
    """Offline provider that returns only explicitly configured RVOL values."""

    def __init__(self, relative_volume_by_symbol: Mapping[str, Any]) -> None:
        self._relative_volume_by_symbol = {
            normalized_symbol: normalized_rvol
            for symbol, value in relative_volume_by_symbol.items()
            if (normalized_symbol := normalize_symbol(symbol))
            and (normalized_rvol := normalize_relative_volume(value)) is not None
        }

    def get_relative_volumes(self, symbols: Sequence[str]) -> dict[str, float]:
        """Return explicit RVOL values for requested symbols only."""

        requested_symbols = normalize_symbols(symbols)
        return {
            symbol: self._relative_volume_by_symbol[symbol]
            for symbol in requested_symbols
            if symbol in self._relative_volume_by_symbol
        }
