"""Dependency-injected skeleton for a future live composed provider.

This provider is not registered for runtime use. It composes injected movement
and float/reference sources with explicit relative-volume data through the
existing live candidate builder.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from market_sentry.data.live_candidate_builder import (
    AlpacaSnapshotSource,
    FMPFloatSource,
    LiveCandidateBuilder,
    LiveCandidateBuildResult,
)
from market_sentry.scanner.models import StockCandidate


@dataclass
class LiveComposedMarketDataProvider:
    """Future provider skeleton backed entirely by injected dependencies."""

    watchlist: Sequence[str]
    snapshot_source: AlpacaSnapshotSource
    float_source: FMPFloatSource
    relative_volume_by_symbol: Mapping[str, float | int | str]
    builder: LiveCandidateBuilder | None = None
    latest_build_results: tuple[LiveCandidateBuildResult, ...] = field(
        default=(),
        init=False,
    )

    def __post_init__(self) -> None:
        if self.builder is None:
            self.builder = LiveCandidateBuilder(
                snapshot_source=self.snapshot_source,
                float_source=self.float_source,
            )

    def build_results(self) -> list[LiveCandidateBuildResult]:
        """Return successful and skipped build results for inspection."""

        if self.builder is None:
            return []

        results = self.builder.build_candidates(
            self.watchlist,
            self.relative_volume_by_symbol,
        )
        self.latest_build_results = tuple(results)
        return results

    def get_candidates(self) -> list[StockCandidate]:
        """Return only successfully built scanner-ready candidates."""

        return [
            result.candidate
            for result in self.build_results()
            if result.candidate is not None
        ]
