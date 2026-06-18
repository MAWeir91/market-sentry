"""Offline candidate-composition harness for intraday RVOL fixtures.

This module connects the offline intraday RVOL fixture provider to the existing
candidate builder. It does not fetch data, register providers, or calculate
RVOL or candidate fields itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from market_sentry.data.intraday_rvol_fixture_provider import (
    OfflineIntradayRelativeVolumeFixtureProvider,
)
from market_sentry.data.live_candidate_builder import (
    LiveCandidateBuildResult,
    LiveCandidateBuilder,
)
from market_sentry.data.relative_volume import normalize_symbols
from market_sentry.scanner.models import StockCandidate


@dataclass(frozen=True)
class OfflineIntradayRvolCandidateCompositionRun:
    """Immutable snapshot of one offline intraday RVOL composition run."""

    requested_symbols: tuple[str, ...]
    relative_volumes: Mapping[str, float]
    rvol_results: tuple[Any, ...]
    candidate_build_results: tuple[LiveCandidateBuildResult, ...]

    @property
    def candidates(self) -> tuple[StockCandidate, ...]:
        """Return successful candidates in builder-result order."""

        return tuple(
            result.candidate
            for result in self.candidate_build_results
            if result.candidate is not None
        )

    @property
    def skipped_results(self) -> tuple[LiveCandidateBuildResult, ...]:
        """Return skipped builder results in builder-result order."""

        return tuple(
            result
            for result in self.candidate_build_results
            if result.candidate is None
        )


class OfflineIntradayRvolCandidateCompositionHarness:
    """Offline-only composition harness for explicit intraday RVOL fixtures."""

    def __init__(
        self,
        candidate_builder: LiveCandidateBuilder,
        relative_volume_provider: OfflineIntradayRelativeVolumeFixtureProvider,
    ) -> None:
        self.candidate_builder = candidate_builder
        self.relative_volume_provider = relative_volume_provider
        self._latest_run: OfflineIntradayRvolCandidateCompositionRun | None = None

    @property
    def latest_run(self) -> OfflineIntradayRvolCandidateCompositionRun | None:
        """Return the latest completed immutable run, if any."""

        return self._latest_run

    def build_run(
        self,
        symbols: Sequence[str],
    ) -> OfflineIntradayRvolCandidateCompositionRun:
        """Build an inspectable candidate-composition run."""

        requested_symbols = normalize_symbols(symbols)
        relative_volumes = self.relative_volume_provider.get_relative_volumes(
            requested_symbols
        )
        rvol_results = tuple(self.relative_volume_provider.latest_results)
        candidate_build_results = tuple(
            self.candidate_builder.build_candidates(
                requested_symbols,
                relative_volumes,
            )
        )

        run = OfflineIntradayRvolCandidateCompositionRun(
            requested_symbols=requested_symbols,
            relative_volumes=MappingProxyType(dict(relative_volumes)),
            rvol_results=rvol_results,
            candidate_build_results=candidate_build_results,
        )
        self._latest_run = run
        return run

    def get_candidates(self, symbols: Sequence[str]) -> list[StockCandidate]:
        """Return successful candidates from a freshly built run."""

        return list(self.build_run(symbols).candidates)
