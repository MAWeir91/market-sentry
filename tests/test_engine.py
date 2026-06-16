from market_sentry.data.mock_provider import get_mock_candidates
from market_sentry.scanner.engine import ScannerEngine, scan_candidates
from market_sentry.scanner.models import ScannerTier, StockCandidate


def candidate(**overrides: object) -> StockCandidate:
    values = {
        "symbol": "BASE",
        "price": 3.00,
        "float_shares": 2_000_000,
        "daily_gain_percent": 12.0,
        "relative_volume": 2.2,
        "daily_volume": 650_000,
    }
    values.update(overrides)
    return StockCandidate(**values)


def test_engine_evaluates_mock_candidates_without_external_apis() -> None:
    engine = ScannerEngine()
    results = engine.scan(get_mock_candidates())

    assert results
    assert {result.symbol for result in results} == {
        candidate.symbol for candidate in get_mock_candidates()
    }


def test_engine_returns_ranked_scanner_results() -> None:
    results = scan_candidates(
        [
            candidate(symbol="T1"),
            candidate(
                symbol="T4",
                daily_gain_percent=120.0,
                relative_volume=12.0,
                daily_volume=6_000_000,
            ),
            candidate(symbol="FAIL", daily_gain_percent=5.0),
        ]
    )

    assert [result.symbol for result in results] == ["T4", "T1", "FAIL"]


def test_engine_includes_pass_and_fail_reasons() -> None:
    results = scan_candidates(
        [
            candidate(symbol="PASS"),
            candidate(symbol="FAIL", relative_volume=1.0),
        ]
    )

    passing = next(result for result in results if result.symbol == "PASS")
    failing = next(result for result in results if result.symbol == "FAIL")

    assert any(reason.passed for reason in passing.reasons)
    assert any(not reason.passed for reason in failing.reasons)
    assert "RELATIVE_VOLUME_BELOW_MIN" in {reason.code for reason in failing.reasons}


def test_qualified_candidates_rank_above_rejected_candidates() -> None:
    results = scan_candidates(
        [
            candidate(
                symbol="REJECTED_HIGH_SCORE",
                price=0.20,
                daily_gain_percent=120.0,
                relative_volume=12.0,
                daily_volume=6_000_000,
            ),
            candidate(symbol="QUALIFIED_LOWER_SCORE"),
        ]
    )

    assert results[0].symbol == "QUALIFIED_LOWER_SCORE"
    assert results[0].qualified is True
    assert results[1].qualified is False


def test_higher_tier_or_higher_score_candidates_rank_first() -> None:
    higher_tier = candidate(
        symbol="HIGHER_TIER",
        daily_gain_percent=50.0,
        relative_volume=5.0,
        daily_volume=2_000_000,
    )
    lower_tier = candidate(symbol="LOWER_TIER")
    same_tier_stronger = candidate(
        symbol="SAME_TIER_STRONGER",
        daily_gain_percent=18.0,
        relative_volume=2.8,
        daily_volume=800_000,
    )
    same_tier_weaker = candidate(symbol="SAME_TIER_WEAKER")

    results = scan_candidates(
        [same_tier_weaker, lower_tier, higher_tier, same_tier_stronger]
    )

    assert results[0].symbol == "HIGHER_TIER"
    assert results[0].tier == ScannerTier.MAJOR_RUNNER
    assert results.index(
        next(result for result in results if result.symbol == "SAME_TIER_STRONGER")
    ) < results.index(
        next(result for result in results if result.symbol == "SAME_TIER_WEAKER")
    )


def test_engine_does_not_expose_trading_or_order_behavior() -> None:
    result = scan_candidates([candidate()])[0]
    public_result_fields = set(result.__dataclass_fields__)
    public_engine_methods = {
        name for name in dir(ScannerEngine) if not name.startswith("_")
    }

    assert "order" not in public_result_fields
    assert "trade" not in public_result_fields
    assert "scan" in public_engine_methods
    assert not any("order" in name or "trade" in name for name in public_engine_methods)
