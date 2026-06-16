"""Deterministic 0-100 scoring for mock scanner candidates."""

from __future__ import annotations

from market_sentry.scanner.models import DEFAULT_CRITERIA, StockCandidate


def _capped_ratio(value: float, cap: float) -> float:
    if value <= 0:
        return 0.0
    return min(value / cap, 1.0)


def _optional_capped_ratio(value: float | None, cap: float) -> float:
    if value is None:
        return 0.0
    return _capped_ratio(value, cap)


def _near_high_ratio(distance_from_high_pct: float | None) -> float:
    if distance_from_high_pct is None:
        return 0.0
    if distance_from_high_pct <= 0:
        return 1.0
    return max(0.0, 1.0 - (distance_from_high_pct / 10.0))


def calculate_score(candidate: StockCandidate) -> float:
    """Return a transparent 0-100 score for a candidate.

    Phase 7 scoring keeps a deterministic 0-100 range:
    - daily gain contributes up to 25 points, capped at 100%
    - relative volume contributes up to 20 points, capped at 10x
    - daily volume contributes up to 15 points, capped at 5M shares
    - float quality contributes up to 10 points for low floats inside range
    - rotation contributes up to 15 points, capped at 5x float traded
    - 15-minute change contributes up to 10 points, capped at 20%
    - near high of day contributes up to 5 points, full credit at HOD
    """

    gain_points = _capped_ratio(candidate.daily_gain_percent, 100.0) * 25.0
    relative_volume_points = _capped_ratio(candidate.relative_volume, 10.0) * 20.0
    volume_points = _capped_ratio(candidate.daily_volume, 5_000_000.0) * 15.0

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

    rotation_points = _optional_capped_ratio(candidate.rotation, 5.0) * 15.0
    change_15m_points = _optional_capped_ratio(candidate.change_15m_pct, 20.0) * 10.0
    near_high_points = _near_high_ratio(candidate.distance_from_high_pct) * 5.0

    score = (
        gain_points
        + relative_volume_points
        + volume_points
        + float_points
        + rotation_points
        + change_15m_points
        + near_high_points
    )
    return round(max(0.0, min(score, 100.0)), 2)
