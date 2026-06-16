from market_sentry.scanner.models import StockCandidate
from market_sentry.scanner.scoring import calculate_score


def candidate(**overrides: object) -> StockCandidate:
    values = {
        "symbol": "SCOR",
        "price": 4.00,
        "float_shares": 5_000_000,
        "daily_gain_percent": 20.0,
        "relative_volume": 3.0,
        "daily_volume": 1_000_000,
    }
    values.update(overrides)
    return StockCandidate(**values)


def test_scoring_is_deterministic() -> None:
    sample = candidate()

    assert calculate_score(sample) == calculate_score(sample)


def test_stronger_candidate_scores_higher_than_weaker_candidate() -> None:
    weaker = candidate(
        daily_gain_percent=12.0,
        relative_volume=2.1,
        daily_volume=550_000,
        float_shares=8_000_000,
    )
    stronger = candidate(
        daily_gain_percent=95.0,
        relative_volume=9.0,
        daily_volume=4_500_000,
        float_shares=1_000_000,
    )

    assert calculate_score(stronger) > calculate_score(weaker)


def test_score_stays_within_documented_zero_to_100_range() -> None:
    samples = [
        candidate(daily_gain_percent=-5.0, relative_volume=-1.0, daily_volume=-1),
        candidate(),
        candidate(
            daily_gain_percent=250.0,
            relative_volume=30.0,
            daily_volume=20_000_000,
            float_shares=500_000,
            high_of_day=4.0,
            change_15m_pct=50.0,
        ),
    ]

    for sample in samples:
        score = calculate_score(sample)
        assert 0.0 <= score <= 100.0


def test_rotation_improves_score_when_all_else_is_equal() -> None:
    lower_rotation = candidate(float_shares=5_000_000, daily_volume=1_000_000)
    higher_rotation = candidate(float_shares=1_000_000, daily_volume=1_000_000)

    assert calculate_score(higher_rotation) > calculate_score(lower_rotation)


def test_15_minute_strength_improves_score_when_all_else_is_equal() -> None:
    no_recent_strength = candidate(change_15m_pct=None)
    recent_strength = candidate(change_15m_pct=12.0)

    assert calculate_score(recent_strength) > calculate_score(no_recent_strength)


def test_near_hod_candidate_scores_higher_than_far_from_hod_candidate() -> None:
    near_high = candidate(price=9.90, high_of_day=10.00)
    far_from_high = candidate(price=8.00, high_of_day=10.00)

    assert calculate_score(near_high) > calculate_score(far_from_high)


def test_missing_optional_metrics_do_not_crash_scoring() -> None:
    score = calculate_score(candidate(high_of_day=None, change_15m_pct=None))

    assert 0.0 <= score <= 100.0
