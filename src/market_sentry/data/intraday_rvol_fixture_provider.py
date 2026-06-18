"""Offline intraday RVOL fixture provider.

This module exposes successful Phase 13G fixture-harness RVOL results through
the existing relative-volume provider contract. It does not register a runtime
provider or calculate lower-level intraday RVOL values itself.
"""

from __future__ import annotations

from collections.abc import Sequence

from market_sentry.data.intraday_rvol_harness import (
    IntradayRelativeVolumeHarnessInput,
    IntradayRelativeVolumeHarnessResult,
    IntradayRelativeVolumeHarnessStatus,
    calculate_intraday_time_of_day_relative_volume_results,
)
from market_sentry.data.relative_volume import RelativeVolumeProvider, normalize_symbols


class OfflineIntradayRelativeVolumeFixtureProvider(RelativeVolumeProvider):
    """Fixture-only RelativeVolumeProvider backed by Phase 13G."""

    def __init__(
        self,
        fixture_inputs: Sequence[IntradayRelativeVolumeHarnessInput],
    ) -> None:
        self._fixture_inputs = tuple(fixture_inputs)
        self._latest_results: tuple[IntradayRelativeVolumeHarnessResult, ...] = ()

    def build_results(self) -> tuple[IntradayRelativeVolumeHarnessResult, ...]:
        """Build ordered inspectable harness results from stored fixtures."""

        self._latest_results = tuple(
            calculate_intraday_time_of_day_relative_volume_results(
                self._fixture_inputs
            )
        )
        return self._latest_results

    @property
    def latest_results(self) -> tuple[IntradayRelativeVolumeHarnessResult, ...]:
        """Return the most recently built immutable harness results."""

        return self._latest_results

    def get_relative_volumes(self, symbols: Sequence[str]) -> dict[str, float]:
        """Return successful requested RVOL values keyed by normalized symbol."""

        results = self.build_results()
        requested_symbols = set(normalize_symbols(symbols))
        if not requested_symbols:
            return {}

        relative_volumes: dict[str, float] = {}
        for result in results:
            if (
                result.status == IntradayRelativeVolumeHarnessStatus.OK
                and result.relative_volume is not None
                and result.symbol in requested_symbols
            ):
                relative_volumes[result.symbol] = result.relative_volume
        return relative_volumes
