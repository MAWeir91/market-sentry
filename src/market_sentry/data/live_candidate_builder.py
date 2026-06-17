"""Composed live-data candidate builder skeleton.

This module combines already-normalized Alpaca movement data, FMP float data,
and explicit relative-volume inputs through the existing candidate composer. It
is not registered as a runtime provider and does not instantiate transports.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from market_sentry.data.alpaca import AlpacaSnapshot
from market_sentry.data.composer import CandidateSkipReason, compose_stock_candidates
from market_sentry.data.fmp import FMPFloatData
from market_sentry.scanner.models import StockCandidate


class AlpacaSnapshotSource(Protocol):
    """Compatible source for normalized Alpaca snapshot data."""

    def fetch_snapshots(self, symbols: list[str] | tuple[str, ...]) -> dict[str, AlpacaSnapshot]:
        """Return normalized snapshots keyed by symbol."""
        ...


class FMPFloatSource(Protocol):
    """Compatible source for normalized FMP float data."""

    def fetch_float(self, symbol: str | None) -> FMPFloatData | None:
        """Return normalized float data for one symbol."""
        ...


@dataclass(frozen=True)
class LiveCandidateBuildResult:
    """Result of building one scanner-ready candidate."""

    symbol: str
    candidate: StockCandidate | None
    skipped_reason: CandidateSkipReason | None

    @property
    def succeeded(self) -> bool:
        return self.candidate is not None


def normalize_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    """Trim and uppercase symbols, dropping empty entries."""

    return tuple(
        symbol
        for symbol in (item.strip().upper() for item in symbols)
        if symbol
    )


class LiveCandidateBuilder:
    """Build candidates from injected movement and reference-data sources."""

    def __init__(
        self,
        *,
        snapshot_source: AlpacaSnapshotSource,
        float_source: FMPFloatSource,
    ) -> None:
        self.snapshot_source = snapshot_source
        self.float_source = float_source

    def build_candidates(
        self,
        symbols: Sequence[str],
        relative_volume_by_symbol: Mapping[str, float | int | str],
    ) -> list[LiveCandidateBuildResult]:
        """Build scanner-ready candidates or inspectable skip results."""

        normalized_symbols = normalize_symbols(symbols)
        if not normalized_symbols:
            return []

        snapshots_by_symbol = self.snapshot_source.fetch_snapshots(list(normalized_symbols))
        float_data_by_symbol = {
            symbol: float_data
            for symbol in normalized_symbols
            if (float_data := self.float_source.fetch_float(symbol)) is not None
        }

        composition_results = compose_stock_candidates(
            normalized_symbols,
            snapshots_by_symbol=snapshots_by_symbol,
            float_data_by_symbol=float_data_by_symbol,
            relative_volume_by_symbol=relative_volume_by_symbol,
        )

        return [
            LiveCandidateBuildResult(
                symbol=result.symbol,
                candidate=result.candidate,
                skipped_reason=result.skipped_reason,
            )
            for result in composition_results
        ]

    def get_candidates(
        self,
        symbols: Sequence[str],
        relative_volume_by_symbol: Mapping[str, float | int | str],
    ) -> list[StockCandidate]:
        """Return only successfully built scanner-ready candidates."""

        return [
            result.candidate
            for result in self.build_candidates(symbols, relative_volume_by_symbol)
            if result.candidate is not None
        ]
