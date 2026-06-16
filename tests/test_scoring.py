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
        ),
    ]

    for sample in samples:
        score = calculate_score(sample)
        assert 0.0 <= score <= 100.0
