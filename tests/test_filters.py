from market_sentry.scanner.filters import evaluate_filters
from market_sentry.scanner.models import StockCandidate


def candidate(**overrides: object) -> StockCandidate:
    values = {
        "symbol": "PASS",
        "price": 2.50,
        "float_shares": 2_000_000,
        "daily_gain_percent": 12.0,
        "relative_volume": 2.5,
        "daily_volume": 600_000,
    }
    values.update(overrides)
    return StockCandidate(**values)


def reason_codes(result) -> set[str]:
    return {reason.code for reason in result.reasons}


def test_candidate_passes_all_default_criteria() -> None:
    result = evaluate_filters(candidate())

    assert result.qualified is True
    assert all(reason.passed for reason in result.reasons)
    assert reason_codes(result) == {
        "PRICE_IN_RANGE",
        "FLOAT_IN_RANGE",
        "GAIN_MEETS_MIN",
        "RELATIVE_VOLUME_MEETS_MIN",
        "DAILY_VOLUME_MEETS_MIN",
    }


def test_price_below_minimum_fails_with_reason() -> None:
    result = evaluate_filters(candidate(price=0.24))

    assert result.qualified is False
    assert "PRICE_BELOW_MIN" in reason_codes(result)


def test_price_above_maximum_fails_with_reason() -> None:
    result = evaluate_filters(candidate(price=20.01))

    assert result.qualified is False
    assert "PRICE_ABOVE_MAX" in reason_codes(result)


def test_float_below_minimum_fails_with_reason() -> None:
    result = evaluate_filters(candidate(float_shares=499_999))

    assert result.qualified is False
    assert "FLOAT_BELOW_MIN" in reason_codes(result)


def test_float_above_maximum_fails_with_reason() -> None:
    result = evaluate_filters(candidate(float_shares=10_000_001))

    assert result.qualified is False
    assert "FLOAT_ABOVE_MAX" in reason_codes(result)


def test_gain_below_minimum_fails_with_reason() -> None:
    result = evaluate_filters(candidate(daily_gain_percent=9.9))

    assert result.qualified is False
    assert "GAIN_BELOW_MIN" in reason_codes(result)


def test_relative_volume_below_minimum_fails_with_reason() -> None:
    result = evaluate_filters(candidate(relative_volume=1.9))

    assert result.qualified is False
    assert "RELATIVE_VOLUME_BELOW_MIN" in reason_codes(result)


def test_daily_volume_below_minimum_fails_with_reason() -> None:
    result = evaluate_filters(candidate(daily_volume=499_999))

    assert result.qualified is False
    assert "DAILY_VOLUME_BELOW_MIN" in reason_codes(result)


def test_boundary_values_pass() -> None:
    result = evaluate_filters(
        candidate(
            price=0.25,
            float_shares=500_000,
            daily_gain_percent=10.0,
            relative_volume=2.0,
            daily_volume=500_000,
        )
    )

    assert result.qualified is True

    high_boundary = evaluate_filters(
        candidate(
            price=20.00,
            float_shares=10_000_000,
        )
    )

    assert high_boundary.qualified is True
