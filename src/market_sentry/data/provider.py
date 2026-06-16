"""Provider contract for scanner-ready market candidates."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from market_sentry.scanner.models import StockCandidate


@runtime_checkable
class MarketDataProvider(Protocol):
    """Contract for local or future scanner candidate providers."""

    def get_candidates(self) -> list[StockCandidate]:
        """Return scanner-ready stock candidates."""
        ...
