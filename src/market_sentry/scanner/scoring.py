"""Deterministic 0-100 scoring for mock scanner candidates."""

from __future__ import annotations

from market_sentry.scanner.models import DEFAULT_CRITERIA, StockCandidate


def _capped_ratio(value: float, cap: float) -> float:
    if value <= 0:
        return 0.0
    return min(value / cap, 1.0)


def calculate_score(candidate: StockCandidate) -> float:
    """Return a transparent 0-100 score for a candidate.

    Scoring is intentionally simple in Phase 1:
    - daily gain contributes up to 40 points, capped at 100%
    - relative volume contributes up to 30 points, capped at 10x
    - daily volume contributes up to 20 points, capped at 5M shares
    - float contributes up to 10 points, favoring lower floats inside range
    """

    gain_points = _capped_ratio(candidate.daily_gain_percent, 100.0) * 40.0
    relative_volume_points = _capped_ratio(candidate.relative_volume, 10.0) * 30.0
    volume_points = _capped_ratio(candidate.daily_volume, 5_000_000.0) * 20.0

    float_points = 0.0
    if (
        DEFAULT_CRITERIA.min_float_shares
        <= candidate.float_shares
        <= DEFAULT_CRITERIA.max_float_shares
    ):
        float_range = (
            DEFAULT_CRITERIA.max_float_shares - DEFAULT_CRITERIA.min_float_shares
        )
        lower_float_bonus = (
            DEFAULT_CRITERIA.max_float_shares - candidate.float_shares
        ) / float_range
        float_points = 5.0 + (lower_float_bonus * 5.0)

    score = gain_points + relative_volume_points + volume_points + float_points
    return round(max(0.0, min(score, 100.0)), 2)
