"""Offline fixture-composed market data provider.

This provider uses static Alpaca-style and FMP-style fixtures plus explicit
relative-volume values. It is intended for future-provider testing only and
does not perform network requests, credential loading, or live provider access.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from market_sentry.data.alpaca import AlpacaSnapshot, parse_snapshot_response
from market_sentry.data.composer import (
    CandidateCompositionResult,
    compose_stock_candidates,
)
from market_sentry.data.fmp import FMPFloatData, parse_shares_float_response
from market_sentry.scanner.models import StockCandidate


DEFAULT_FIXTURE_SYMBOLS = ("XTRM", "ROTA", "HODC", "FSTN", "NORV", "NOFLT")

DEFAULT_ALPACA_SNAPSHOT_FIXTURE: dict[str, Any] = {
    "snapshots": {
        "XTRM": {
            "latestTrade": {"p": 11.40},
            "dailyBar": {"v": 6_400_000, "h": 11.55, "c": 11.35},
            "prevDailyBar": {"c": 5.70},
        },
        "ROTA": {
            "latestTrade": {"p": 3.60},
            "dailyBar": {"v": 4_800_000, "h": 3.85, "c": 3.58},
            "prevDailyBar": {"c": 2.40},
        },
        "HODC": {
            "latestTrade": {"p": 5.92},
            "dailyBar": {"v": 1_900_000, "h": 6.00, "c": 5.90},
            "prevDailyBar": {"c": 4.80},
        },
        "FSTN": {
            "latestTrade": {"p": 1.82},
            "dailyBar": {"v": 820_000, "h": 1.95, "c": 1.80},
            "prevDailyBar": {"c": 1.55},
        },
        "NORV": {
            "latestTrade": {"p": 2.50},
            "dailyBar": {"v": 700_000, "h": 2.60, "c": 2.48},
            "prevDailyBar": {"c": 2.10},
        },
        "NOFLT": {
            "latestTrade": {"p": 7.25},
            "dailyBar": {"v": 1_200_000, "h": 7.40, "c": 7.22},
            "prevDailyBar": {"c": 5.80},
        },
    }
}

DEFAULT_ALPACA_BARS_FIXTURE: dict[str, list[dict[str, float]]] = {
    "XTRM": [{"c": 9.60}, {"c": 10.10}, {"c": 11.02}],
    "ROTA": [{"c": 3.10}, {"c": 3.32}, {"c": 3.61}],
    "HODC": [{"c": 5.70}, {"c": 5.82}, {"c": 5.92}],
    "FSTN": [{"c": 1.50}, {"c": 1.64}, {"c": 1.82}],
    "NORV": [{"c": 2.32}, {"c": 2.46}, {"c": 2.50}],
    "NOFLT": [{"c": 6.80}, {"c": 7.00}, {"c": 7.25}],
}

DEFAULT_FMP_FLOAT_FIXTURE: list[dict[str, Any]] = [
    {
        "symbol": "XTRM",
        "floatShares": 1_300_000,
        "outstandingShares": 6_000_000,
        "date": "2026-06-16",
    },
    {
        "symbol": "ROTA",
        "floatShares": 600_000,
        "outstandingShares": 3_500_000,
        "date": "2026-06-16",
    },
    {
        "symbol": "HODC",
        "floatShares": 2_200_000,
        "outstandingShares": 8_900_000,
        "date": "2026-06-16",
    },
    {
        "symbol": "FSTN",
        "floatShares": 8_500_000,
        "outstandingShares": 20_000_000,
        "date": "2026-06-16",
    },
    {
        "symbol": "NORV",
        "floatShares": 3_100_000,
        "outstandingShares": 12_000_000,
        "date": "2026-06-16",
    },
]

DEFAULT_RELATIVE_VOLUME_FIXTURE: dict[str, float] = {
    "XTRM": 12.5,
    "ROTA": 8.1,
    "HODC": 4.3,
    "FSTN": 2.8,
    "NOFLT": 6.0,
}


@dataclass(frozen=True)
class FixtureComposedMarketDataProvider:
    """MarketDataProvider implementation backed by offline fixture data."""

    symbols: tuple[str, ...] = DEFAULT_FIXTURE_SYMBOLS
    snapshot_payload: dict[str, Any] = field(
        default_factory=lambda: deepcopy(DEFAULT_ALPACA_SNAPSHOT_FIXTURE)
    )
    float_payload: list[dict[str, Any]] | dict[str, Any] = field(
        default_factory=lambda: deepcopy(DEFAULT_FMP_FLOAT_FIXTURE)
    )
    relative_volume_by_symbol: dict[str, float | int | str] = field(
        default_factory=lambda: deepcopy(DEFAULT_RELATIVE_VOLUME_FIXTURE)
    )
    bars_by_symbol: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: deepcopy(DEFAULT_ALPACA_BARS_FIXTURE)
    )

    def composition_results(self) -> list[CandidateCompositionResult]:
        """Return successful and skipped fixture composition results."""

        snapshots_by_symbol: dict[str, AlpacaSnapshot] = {}
        float_data_by_symbol: dict[str, FMPFloatData] = {}

        for symbol in self.symbols:
            normalized_symbol = symbol.strip().upper()
            snapshot = parse_snapshot_response(self.snapshot_payload, normalized_symbol)
            if snapshot is not None:
                snapshots_by_symbol[normalized_symbol] = snapshot

            float_data = parse_shares_float_response(self.float_payload, normalized_symbol)
            if float_data is not None:
                float_data_by_symbol[normalized_symbol] = float_data

        return compose_stock_candidates(
            self.symbols,
            snapshots_by_symbol=snapshots_by_symbol,
            float_data_by_symbol=float_data_by_symbol,
            relative_volume_by_symbol=self.relative_volume_by_symbol,
            bars_by_symbol=self.bars_by_symbol,
        )

    def get_candidates(self) -> list[StockCandidate]:
        """Return only successfully composed scanner-ready candidates."""

        return [
            result.candidate
            for result in self.composition_results()
            if result.candidate is not None
        ]
