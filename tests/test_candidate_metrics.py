from market_sentry.scanner.models import StockCandidate


def candidate(**overrides: object) -> StockCandidate:
    values = {
        "symbol": "METR",
        "price": 9.50,
        "float_shares": 2_000_000,
        "daily_gain_percent": 25.0,
        "relative_volume": 3.0,
        "daily_volume": 5_000_000,
    }
    values.update(overrides)
    return StockCandidate(**values)


def test_rotation_is_calculated_correctly() -> None:
    assert candidate().rotation == 2.5


def test_rotation_handles_invalid_float_safely() -> None:
    assert candidate(float_shares=0).rotation is None
    assert candidate(float_shares=-1).rotation is None


def test_distance_from_high_of_day_is_calculated_correctly() -> None:
    assert candidate(high_of_day=10.00).distance_from_high_pct == 5.0


def test_distance_from_high_handles_missing_or_invalid_high_safely() -> None:
    assert candidate(high_of_day=None).distance_from_high_pct is None
    assert candidate(high_of_day=0).distance_from_high_pct is None
    assert candidate(high_of_day=-1).distance_from_high_pct is None


def test_distance_from_high_is_not_negative_when_high_is_below_price() -> None:
    assert candidate(price=10.50, high_of_day=10.00).distance_from_high_pct == 0.0


def test_optional_metrics_do_not_break_candidate_creation() -> None:
    sample = candidate(high_of_day=None, change_15m_pct=None)

    assert sample.high_of_day is None
    assert sample.change_15m_pct is None
    assert sample.rotation == 2.5
