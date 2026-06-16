"""Scanner engine for deterministic mock candidate evaluation."""

from __future__ import annotations

from collections.abc import Iterable

from market_sentry.scanner.filters import evaluate_filters
from market_sentry.scanner.models import ScannerResult, ScannerTier, StockCandidate
from market_sentry.scanner.scoring import calculate_score
from market_sentry.scanner.tiers import assign_tier


def evaluate_candidate(candidate: StockCandidate) -> ScannerResult:
    """Evaluate one candidate and return a scanner result."""

    filter_evaluation = evaluate_filters(candidate)
    tier = assign_tier(candidate) if filter_evaluation.qualified else None
    score = calculate_score(candidate)

    return ScannerResult(
        symbol=candidate.symbol,
        qualified=filter_evaluation.qualified,
        tier=tier,
        score=score,
        reasons=filter_evaluation.reasons,
        candidate=candidate,
    )


def _tier_level(tier: ScannerTier | None) -> int:
    return int(tier) if tier is not None else 0


def rank_results(results: Iterable[ScannerResult]) -> list[ScannerResult]:
    """Rank results with qualified candidates first, then tier, then score."""

    return sorted(
        results,
        key=lambda result: (
            result.qualified,
            _tier_level(result.tier),
            result.score,
            result.symbol,
        ),
        reverse=True,
    )


def scan_candidates(candidates: Iterable[StockCandidate]) -> list[ScannerResult]:
    """Evaluate and rank candidates without external data or trading behavior."""

    return rank_results(evaluate_candidate(candidate) for candidate in candidates)


class ScannerEngine:
    """Small wrapper for scanning local candidate collections."""

    def scan(self, candidates: Iterable[StockCandidate]) -> list[ScannerResult]:
        return scan_candidates(candidates)
