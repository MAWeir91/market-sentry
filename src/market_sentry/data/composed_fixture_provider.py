"""Offline composed provider harness for future live-data composition.

This provider is static and offline. It exercises the live candidate builder
with normalized Alpaca-style movement data, normalized FMP-style float data, and
explicit relative-volume fixtures. It does not create transports or call APIs.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from market_sentry.data.alpaca import AlpacaSnapshot
from market_sentry.data.fmp import FMPFloatData
from market_sentry.data.live_candidate_builder import (
    LiveCandidateBuildResult,
    LiveCandidateBuilder,
)
from market_sentry.scanner.models import StockCandidate


DEFAULT_COMPOSED_SYMBOLS = ("CMPX", "NORV", "BADFLT", "NOMOVE")

DEFAULT_STATIC_SNAPSHOTS = {
    "CMPX": AlpacaSnapshot(
        symbol="CMPX",
        price=8.40,
        daily_volume=3_200_000,
        high_of_day=8.75,
        previous_close=4.20,
    ),
    "NORV": AlpacaSnapshot(
        symbol="NORV",
        price=2.75,
        daily_volume=850_000,
        high_of_day=2.90,
        previous_close=2.20,
    ),
    "BADFLT": AlpacaSnapshot(
        symbol="BADFLT",
        price=5.50,
        daily_volume=1_500_000,
        high_of_day=5.80,
        previous_close=4.00,
    ),
}

DEFAULT_STATIC_FLOATS = {
    "CMPX": FMPFloatData(
        symbol="CMPX",
        float_shares=1_100_000,
        outstanding_shares=7_500_000,
        date="2026-06-17",
    ),
    "NORV": FMPFloatData(
        symbol="NORV",
        float_shares=2_400_000,
        outstanding_shares=11_000_000,
        date="2026-06-17",
    ),
    "BADFLT": FMPFloatData(
        symbol="BADFLT",
        float_shares=0,
        outstanding_shares=5_500_000,
        date="2026-06-17",
    ),
    "NOMOVE": FMPFloatData(
        symbol="NOMOVE",
        float_shares=900_000,
        outstanding_shares=4_200_000,
        date="2026-06-17",
    ),
}

DEFAULT_STATIC_RELATIVE_VOLUME = {
    "CMPX": 7.4,
    "BADFLT": 4.6,
    "NOMOVE": 3.2,
}


@dataclass(frozen=True)
class _StaticAlpacaSnapshotSource:
    snapshots: dict[str, AlpacaSnapshot]

    def fetch_snapshots(self, symbols: list[str] | tuple[str, ...]) -> dict[str, AlpacaSnapshot]:
        """Return static normalized snapshots for requested symbols."""

        return {
            symbol: self.snapshots[symbol]
            for symbol in symbols
            if symbol in self.snapshots
        }


@dataclass(frozen=True)
class _StaticFMPFloatSource:
    floats: dict[str, FMPFloatData]

    def fetch_float(self, symbol: str | None) -> FMPFloatData | None:
        """Return static normalized float data for one symbol."""

        if symbol is None:
            return None
        return self.floats.get(symbol.strip().upper())


@dataclass(frozen=True)
class OfflineComposedFixtureProvider:
    """MarketDataProvider harness backed by static composed fixture data."""

    symbols: tuple[str, ...] = DEFAULT_COMPOSED_SYMBOLS
    snapshots: dict[str, AlpacaSnapshot] = field(
        default_factory=lambda: deepcopy(DEFAULT_STATIC_SNAPSHOTS)
    )
    floats: dict[str, FMPFloatData] = field(
        default_factory=lambda: deepcopy(DEFAULT_STATIC_FLOATS)
    )
    relative_volume_by_symbol: dict[str, float | int | str] = field(
        default_factory=lambda: deepcopy(DEFAULT_STATIC_RELATIVE_VOLUME)
    )

    def _builder(self) -> LiveCandidateBuilder:
        return LiveCandidateBuilder(
            snapshot_source=_StaticAlpacaSnapshotSource(self.snapshots),
            float_source=_StaticFMPFloatSource(self.floats),
        )

    def build_results(self) -> list[LiveCandidateBuildResult]:
        """Return successful and skipped composed build results."""

        return self._builder().build_candidates(
            self.symbols,
            self.relative_volume_by_symbol,
        )

    def get_candidates(self) -> list[StockCandidate]:
        """Return only successfully composed scanner-ready candidates."""

        return [
            result.candidate
            for result in self.build_results()
            if result.candidate is not None
        ]
