"""Typed scanner models for Phase 1 mock evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ScannerTier(IntEnum):
    """Scanner alert tiers ordered by momentum strength."""

    EARLY_HEAT = 1
    ACTIVE_MOMENTUM = 2
    MAJOR_RUNNER = 3
    EXTREME_RUNNER = 4

    @property
    def label(self) -> str:
        labels = {
            ScannerTier.EARLY_HEAT: "Tier 1: Early Heat",
            ScannerTier.ACTIVE_MOMENTUM: "Tier 2: Active Momentum",
            ScannerTier.MAJOR_RUNNER: "Tier 3: Major Runner",
            ScannerTier.EXTREME_RUNNER: "Tier 4: Extreme Runner",
        }
        return labels[self]


@dataclass(frozen=True)
class StockCandidate:
    """A local mock stock candidate.

    Percent values use whole-number percentages, such as 10.0 for 10%.
    Relative volume uses a multiplier, such as 2.0.
    """

    symbol: str
    price: float
    float_shares: int
    daily_gain_percent: float
    relative_volume: float
    daily_volume: int


@dataclass(frozen=True)
class ScannerCriteria:
    """Base scanner criteria used to decide whether a candidate qualifies."""

    min_price: float = 0.25
    max_price: float = 20.00
    min_float_shares: int = 500_000
    max_float_shares: int = 10_000_000
    min_daily_gain_percent: float = 10.0
    min_relative_volume: float = 2.0
    min_daily_volume: int = 500_000


@dataclass(frozen=True)
class EvaluationReason:
    """A pass/fail reason from evaluating one scanner criterion."""

    code: str
    message: str
    passed: bool


@dataclass(frozen=True)
class FilterEvaluation:
    """Base criteria evaluation for a stock candidate."""

    qualified: bool
    reasons: tuple[EvaluationReason, ...]


@dataclass(frozen=True)
class ScannerResult:
    """Final scanner result for a candidate.

    This is an evaluation artifact only. It contains no trading or order fields.
    """

    symbol: str
    qualified: bool
    tier: ScannerTier | None
    score: float
    reasons: tuple[EvaluationReason, ...]
    candidate: StockCandidate


DEFAULT_CRITERIA = ScannerCriteria()
