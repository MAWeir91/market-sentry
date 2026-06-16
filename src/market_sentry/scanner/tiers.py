"""Tier assignment for qualified mock scanner candidates."""

from __future__ import annotations

from dataclasses import dataclass

from market_sentry.scanner.models import DEFAULT_CRITERIA, ScannerTier, StockCandidate


@dataclass(frozen=True)
class TierThreshold:
    """Thresholds for one scanner tier."""

    tier: ScannerTier
    min_daily_gain_percent: float
    min_relative_volume: float
    min_daily_volume: int


TIER_THRESHOLDS: tuple[TierThreshold, ...] = (
    TierThreshold(ScannerTier.EARLY_HEAT, 10.0, 2.0, 500_000),
    TierThreshold(ScannerTier.ACTIVE_MOMENTUM, 25.0, 3.0, 1_000_000),
    TierThreshold(ScannerTier.MAJOR_RUNNER, 50.0, 5.0, 2_000_000),
    TierThreshold(ScannerTier.EXTREME_RUNNER, 100.0, 10.0, 5_000_000),
)


def assign_tier(candidate: StockCandidate) -> ScannerTier | None:
    """Return the highest tier matched by a candidate's momentum metrics."""

    if not (
        DEFAULT_CRITERIA.min_float_shares
        <= candidate.float_shares
        <= DEFAULT_CRITERIA.max_float_shares
    ):
        return None

    matched_tier: ScannerTier | None = None
    for threshold in TIER_THRESHOLDS:
        if (
            candidate.daily_gain_percent >= threshold.min_daily_gain_percent
            and candidate.relative_volume >= threshold.min_relative_volume
            and candidate.daily_volume >= threshold.min_daily_volume
        ):
            matched_tier = threshold.tier

    return matched_tier
