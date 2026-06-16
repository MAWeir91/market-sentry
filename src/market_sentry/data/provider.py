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


class FloatDataProvider(Protocol):
    """Future contract for float/reference data providers."""

    def get_float_shares(self, symbol: str) -> int | None:
        """Return reference float shares for a symbol when available."""
        ...


class CatalystProvider(Protocol):
    """Future contract for catalyst context providers."""

    def get_catalysts(self, symbol: str) -> tuple[str, ...]:
        """Return catalyst notes for a symbol when available."""
        ...


class HaltProvider(Protocol):
    """Future contract for halt/resume context providers."""

    def get_halt_status(self, symbol: str) -> str | None:
        """Return halt/resume status for a symbol when available."""
        ...
