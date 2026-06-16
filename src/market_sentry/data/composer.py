"""Offline candidate composition for future provider fixtures.

This module composes already-normalized Alpaca and FMP fixture data into
scanner-ready StockCandidate objects. It does not perform HTTP requests,
provider activation, credential loading, or runtime scanner changes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from market_sentry.data.alpaca import (
    AlpacaSnapshot,
    calculate_15m_change_from_bars,
    calculate_daily_gain_from_snapshot,
)
from market_sentry.data.fmp import FMPFloatData
from market_sentry.scanner.models import StockCandidate


class CandidateSkipReason(str, Enum):
    """Stable reasons why fixture data could not produce a candidate."""

    MISSING_SYMBOL = "missing_symbol"
    MISSING_ALPACA_SNAPSHOT = "missing_alpaca_snapshot"
    MISSING_FMP_FLOAT_DATA = "missing_fmp_float_data"
    MISMATCHED_SYMBOLS = "mismatched_symbols"
    INVALID_PRICE = "invalid_price"
    INVALID_FLOAT = "invalid_float"
    MISSING_RELATIVE_VOLUME = "missing_relative_volume"
    INVALID_RELATIVE_VOLUME = "invalid_relative_volume"
    INVALID_DAILY_VOLUME = "invalid_daily_volume"
    MISSING_DAILY_GAIN = "missing_daily_gain"


@dataclass(frozen=True)
class CandidateCompositionResult:
    """Result of composing fixture data into a scanner-ready candidate."""

    symbol: str
    candidate: StockCandidate | None = None
    skipped_reason: CandidateSkipReason | None = None

    @property
    def succeeded(self) -> bool:
        return self.candidate is not None


def _normalize_symbol(symbol: str | None) -> str:
    if symbol is None:
        return ""
    return symbol.strip().upper()


def _positive_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if converted <= 0:
        return None
    return converted


def _positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        converted = int(value)
    except (TypeError, ValueError):
        return None
    if converted <= 0:
        return None
    return converted


def _skipped(
    symbol: str,
    reason: CandidateSkipReason,
) -> CandidateCompositionResult:
    return CandidateCompositionResult(symbol=symbol, skipped_reason=reason)


def _symbols_match(
    expected_symbol: str,
    snapshot: AlpacaSnapshot,
    float_data: FMPFloatData,
) -> bool:
    return (
        _normalize_symbol(snapshot.symbol) == expected_symbol
        and _normalize_symbol(float_data.symbol) == expected_symbol
    )


def compose_stock_candidate(
    symbol: str | None,
    snapshot: AlpacaSnapshot | None,
    float_data: FMPFloatData | None,
    relative_volume: float | int | str | None,
    bars: list[dict[str, Any]] | None = None,
) -> CandidateCompositionResult:
    """Compose one scanner-ready candidate from offline fixture data."""

    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        return _skipped(normalized_symbol, CandidateSkipReason.MISSING_SYMBOL)
    if snapshot is None:
        return _skipped(normalized_symbol, CandidateSkipReason.MISSING_ALPACA_SNAPSHOT)
    if float_data is None:
        return _skipped(normalized_symbol, CandidateSkipReason.MISSING_FMP_FLOAT_DATA)
    if not _symbols_match(normalized_symbol, snapshot, float_data):
        return _skipped(normalized_symbol, CandidateSkipReason.MISMATCHED_SYMBOLS)

    price = _positive_float(snapshot.price)
    if price is None:
        return _skipped(normalized_symbol, CandidateSkipReason.INVALID_PRICE)

    float_shares = _positive_int(float_data.float_shares)
    if float_shares is None:
        return _skipped(normalized_symbol, CandidateSkipReason.INVALID_FLOAT)

    if relative_volume is None:
        return _skipped(normalized_symbol, CandidateSkipReason.MISSING_RELATIVE_VOLUME)
    normalized_relative_volume = _positive_float(relative_volume)
    if normalized_relative_volume is None:
        return _skipped(normalized_symbol, CandidateSkipReason.INVALID_RELATIVE_VOLUME)

    daily_volume = _positive_int(snapshot.daily_volume)
    if daily_volume is None:
        return _skipped(normalized_symbol, CandidateSkipReason.INVALID_DAILY_VOLUME)

    daily_gain_pct = calculate_daily_gain_from_snapshot(snapshot)
    if daily_gain_pct is None:
        return _skipped(normalized_symbol, CandidateSkipReason.MISSING_DAILY_GAIN)

    change_15m_pct = calculate_15m_change_from_bars(bars) if bars is not None else None

    candidate = StockCandidate(
        symbol=normalized_symbol,
        price=price,
        float_shares=float_shares,
        daily_gain_percent=daily_gain_pct,
        relative_volume=normalized_relative_volume,
        daily_volume=daily_volume,
        high_of_day=snapshot.high_of_day,
        change_15m_pct=change_15m_pct,
    )
    return CandidateCompositionResult(symbol=normalized_symbol, candidate=candidate)


def compose_stock_candidates(
    symbols: Iterable[str],
    snapshots_by_symbol: Mapping[str, AlpacaSnapshot],
    float_data_by_symbol: Mapping[str, FMPFloatData],
    relative_volume_by_symbol: Mapping[str, float | int | str],
    bars_by_symbol: Mapping[str, list[dict[str, Any]]] | None = None,
) -> list[CandidateCompositionResult]:
    """Compose multiple candidates while keeping skipped symbols visible."""

    normalized_snapshots = {
        _normalize_symbol(symbol): snapshot
        for symbol, snapshot in snapshots_by_symbol.items()
    }
    normalized_float_data = {
        _normalize_symbol(symbol): data
        for symbol, data in float_data_by_symbol.items()
    }
    normalized_relative_volume = {
        _normalize_symbol(symbol): relative_volume
        for symbol, relative_volume in relative_volume_by_symbol.items()
    }
    normalized_bars = {
        _normalize_symbol(symbol): bars
        for symbol, bars in (bars_by_symbol or {}).items()
    }

    results: list[CandidateCompositionResult] = []
    for symbol in symbols:
        normalized_symbol = _normalize_symbol(symbol)
        results.append(
            compose_stock_candidate(
                normalized_symbol,
                normalized_snapshots.get(normalized_symbol),
                normalized_float_data.get(normalized_symbol),
                normalized_relative_volume.get(normalized_symbol),
                normalized_bars.get(normalized_symbol),
            )
        )
    return results
