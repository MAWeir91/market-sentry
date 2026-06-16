from market_sentry.scanner.engine import evaluate_candidate
from market_sentry.scanner.models import ScannerTier, StockCandidate
from market_sentry.scanner.tiers import assign_tier


def candidate(**overrides: object) -> StockCandidate:
    values = {
        "symbol": "TIER",
        "price": 3.50,
        "float_shares": 2_000_000,
        "daily_gain_percent": 10.0,
        "relative_volume": 2.0,
        "daily_volume": 500_000,
    }
    values.update(overrides)
    return StockCandidate(**values)


def test_tier_1_threshold_candidate_is_tier_1() -> None:
    assert assign_tier(candidate()) == ScannerTier.EARLY_HEAT


def test_tier_2_threshold_candidate_is_tier_2() -> None:
    assert (
        assign_tier(
            candidate(
                daily_gain_percent=25.0,
                relative_volume=3.0,
                daily_volume=1_000_000,
            )
        )
        == ScannerTier.ACTIVE_MOMENTUM
    )


def test_tier_3_threshold_candidate_is_tier_3() -> None:
    assert (
        assign_tier(
            candidate(
                daily_gain_percent=50.0,
                relative_volume=5.0,
                daily_volume=2_000_000,
            )
        )
        == ScannerTier.MAJOR_RUNNER
    )


def test_tier_4_threshold_candidate_is_tier_4() -> None:
    assert (
        assign_tier(
            candidate(
                daily_gain_percent=100.0,
                relative_volume=10.0,
                daily_volume=5_000_000,
            )
        )
        == ScannerTier.EXTREME_RUNNER
    )


def test_non_qualifying_candidate_receives_no_tier_in_final_result() -> None:
    result = evaluate_candidate(
        candidate(
            price=0.24,
            daily_gain_percent=100.0,
            relative_volume=10.0,
            daily_volume=5_000_000,
        )
    )

    assert result.qualified is False
    assert result.tier is None
