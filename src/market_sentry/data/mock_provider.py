"""Static mock candidates for Phase 2 provider development."""

from __future__ import annotations

from market_sentry.data.provider import MarketDataProvider
from market_sentry.scanner.models import StockCandidate


_MOCK_CANDIDATES: tuple[StockCandidate, ...] = (
    StockCandidate(
        symbol="EHT",
        price=2.35,
        float_shares=8_200_000,
        daily_gain_percent=14.5,
        relative_volume=2.4,
        daily_volume=760_000,
    ),
    StockCandidate(
        symbol="AMOM",
        price=4.80,
        float_shares=4_600_000,
        daily_gain_percent=31.0,
        relative_volume=3.8,
        daily_volume=1_400_000,
    ),
    StockCandidate(
        symbol="MRUN",
        price=7.20,
        float_shares=2_900_000,
        daily_gain_percent=68.0,
        relative_volume=6.2,
        daily_volume=2_800_000,
    ),
    StockCandidate(
        symbol="XTRM",
        price=11.40,
        float_shares=1_300_000,
        daily_gain_percent=118.0,
        relative_volume=12.5,
        daily_volume=6_400_000,
    ),
    StockCandidate(
        symbol="LOWP",
        price=0.18,
        float_shares=3_500_000,
        daily_gain_percent=22.0,
        relative_volume=3.1,
        daily_volume=900_000,
    ),
    StockCandidate(
        symbol="SLOW",
        price=3.10,
        float_shares=6_100_000,
        daily_gain_percent=4.5,
        relative_volume=1.2,
        daily_volume=240_000,
    ),
)


class MockMarketDataProvider(MarketDataProvider):
    """Local, static provider for deterministic scanner development."""

    def get_candidates(self) -> list[StockCandidate]:
        """Return scanner-ready mock candidates."""

        return list(_MOCK_CANDIDATES)


def get_mock_candidates() -> list[StockCandidate]:
    """Return local static examples covering qualified and rejected candidates."""

    return MockMarketDataProvider().get_candidates()
