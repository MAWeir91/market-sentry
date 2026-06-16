"""Base scanner filters for mock candidates."""

from __future__ import annotations

from market_sentry.scanner.models import (
    DEFAULT_CRITERIA,
    EvaluationReason,
    FilterEvaluation,
    ScannerCriteria,
    StockCandidate,
)


def evaluate_filters(
    candidate: StockCandidate,
    criteria: ScannerCriteria = DEFAULT_CRITERIA,
) -> FilterEvaluation:
    """Evaluate base scanner criteria and return explicit reasons."""

    reasons: list[EvaluationReason] = []

    if candidate.price < criteria.min_price:
        reasons.append(
            EvaluationReason(
                code="PRICE_BELOW_MIN",
                message=(
                    f"Price {candidate.price:.2f} is below the minimum "
                    f"{criteria.min_price:.2f}."
                ),
                passed=False,
            )
        )
    elif candidate.price > criteria.max_price:
        reasons.append(
            EvaluationReason(
                code="PRICE_ABOVE_MAX",
                message=(
                    f"Price {candidate.price:.2f} is above the maximum "
                    f"{criteria.max_price:.2f}."
                ),
                passed=False,
            )
        )
    else:
        reasons.append(
            EvaluationReason(
                code="PRICE_IN_RANGE",
                message=(
                    f"Price {candidate.price:.2f} is within "
                    f"{criteria.min_price:.2f}-{criteria.max_price:.2f}."
                ),
                passed=True,
            )
        )

    if candidate.float_shares < criteria.min_float_shares:
        reasons.append(
            EvaluationReason(
                code="FLOAT_BELOW_MIN",
                message=(
                    f"Float {candidate.float_shares:,} is below the minimum "
                    f"{criteria.min_float_shares:,}."
                ),
                passed=False,
            )
        )
    elif candidate.float_shares > criteria.max_float_shares:
        reasons.append(
            EvaluationReason(
                code="FLOAT_ABOVE_MAX",
                message=(
                    f"Float {candidate.float_shares:,} is above the maximum "
                    f"{criteria.max_float_shares:,}."
                ),
                passed=False,
            )
        )
    else:
        reasons.append(
            EvaluationReason(
                code="FLOAT_IN_RANGE",
                message=(
                    f"Float {candidate.float_shares:,} is within "
                    f"{criteria.min_float_shares:,}-{criteria.max_float_shares:,}."
                ),
                passed=True,
            )
        )

    if candidate.daily_gain_percent >= criteria.min_daily_gain_percent:
        reasons.append(
            EvaluationReason(
                code="GAIN_MEETS_MIN",
                message=(
                    f"Daily gain {candidate.daily_gain_percent:.1f}% meets the "
                    f"{criteria.min_daily_gain_percent:.1f}% minimum."
                ),
                passed=True,
            )
        )
    else:
        reasons.append(
            EvaluationReason(
                code="GAIN_BELOW_MIN",
                message=(
                    f"Daily gain {candidate.daily_gain_percent:.1f}% is below "
                    f"the {criteria.min_daily_gain_percent:.1f}% minimum."
                ),
                passed=False,
            )
        )

    if candidate.relative_volume >= criteria.min_relative_volume:
        reasons.append(
            EvaluationReason(
                code="RELATIVE_VOLUME_MEETS_MIN",
                message=(
                    f"Relative volume {candidate.relative_volume:.1f}x meets "
                    f"the {criteria.min_relative_volume:.1f}x minimum."
                ),
                passed=True,
            )
        )
    else:
        reasons.append(
            EvaluationReason(
                code="RELATIVE_VOLUME_BELOW_MIN",
                message=(
                    f"Relative volume {candidate.relative_volume:.1f}x is below "
                    f"the {criteria.min_relative_volume:.1f}x minimum."
                ),
                passed=False,
            )
        )

    if candidate.daily_volume >= criteria.min_daily_volume:
        reasons.append(
            EvaluationReason(
                code="DAILY_VOLUME_MEETS_MIN",
                message=(
                    f"Daily volume {candidate.daily_volume:,} meets the "
                    f"{criteria.min_daily_volume:,} minimum."
                ),
                passed=True,
            )
        )
    else:
        reasons.append(
            EvaluationReason(
                code="DAILY_VOLUME_BELOW_MIN",
                message=(
                    f"Daily volume {candidate.daily_volume:,} is below the "
                    f"{criteria.min_daily_volume:,} minimum."
                ),
                passed=False,
            )
        )

    return FilterEvaluation(
        qualified=all(reason.passed for reason in reasons),
        reasons=tuple(reasons),
    )
