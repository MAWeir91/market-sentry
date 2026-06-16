import ast
import inspect

from market_sentry.data import composer
from market_sentry.data.alpaca import AlpacaSnapshot
from market_sentry.data.composer import (
    CandidateCompositionResult,
    CandidateSkipReason,
    compose_stock_candidate,
    compose_stock_candidates,
)
from market_sentry.data.fmp import FMPFloatData
from market_sentry.scanner.engine import ScannerEngine
from market_sentry.scanner.models import StockCandidate


def snapshot(**overrides: object) -> AlpacaSnapshot:
    values = {
        "symbol": "XTRM",
        "price": 11.4,
        "daily_volume": 6_400_000,
        "high_of_day": 11.55,
        "previous_close": 5.7,
    }
    values.update(overrides)
    return AlpacaSnapshot(**values)


def float_data(**overrides: object) -> FMPFloatData:
    values = {
        "symbol": "XTRM",
        "float_shares": 1_300_000,
        "outstanding_shares": 6_000_000,
        "date": "2026-06-16",
    }
    values.update(overrides)
    return FMPFloatData(**values)


def compose_valid(**overrides: object) -> CandidateCompositionResult:
    values = {
        "symbol": "XTRM",
        "snapshot": snapshot(),
        "float_data": float_data(),
        "relative_volume": 12.5,
        "bars": [{"c": 9.6}, {"c": 10.2}, {"c": 11.02}],
    }
    values.update(overrides)
    return compose_stock_candidate(**values)


def test_valid_stock_candidate_composition_from_fixtures() -> None:
    result = compose_valid()

    assert result.succeeded
    assert result.symbol == "XTRM"
    assert result.skipped_reason is None
    assert result.candidate == StockCandidate(
        symbol="XTRM",
        price=11.4,
        float_shares=1_300_000,
        daily_gain_percent=100.0,
        relative_volume=12.5,
        daily_volume=6_400_000,
        high_of_day=11.55,
        change_15m_pct=14.79,
    )


def test_symbol_normalization_during_composition() -> None:
    result = compose_valid(
        symbol=" xtrm ",
        snapshot=snapshot(symbol=" xtrm "),
        float_data=float_data(symbol=" xtrm "),
    )

    assert result.succeeded
    assert result.symbol == "XTRM"
    assert result.candidate is not None
    assert result.candidate.symbol == "XTRM"


def test_high_of_day_and_15m_change_are_carried_into_candidate() -> None:
    result = compose_valid(
        snapshot=snapshot(high_of_day=11.55),
        bars=[{"c": 10.0}, {"c": 10.5}, {"c": 11.0}],
    )

    assert result.candidate is not None
    assert result.candidate.high_of_day == 11.55
    assert result.candidate.change_15m_pct == 10.0


def test_daily_gain_daily_volume_and_float_are_derived_from_fixtures() -> None:
    result = compose_valid(
        snapshot=snapshot(price=7.5, previous_close=5.0, daily_volume=1_250_000),
        float_data=float_data(float_shares=750_000),
    )

    assert result.candidate is not None
    assert result.candidate.daily_gain_percent == 50.0
    assert result.candidate.daily_volume == 1_250_000
    assert result.candidate.float_shares == 750_000


def test_relative_volume_must_be_explicit() -> None:
    result = compose_valid(relative_volume=None)

    assert not result.succeeded
    assert result.candidate is None
    assert result.skipped_reason == CandidateSkipReason.MISSING_RELATIVE_VOLUME


def test_invalid_relative_volume_is_skipped_safely() -> None:
    for value in (0, -1, "bad"):
        result = compose_valid(relative_volume=value)

        assert not result.succeeded
        assert result.skipped_reason == CandidateSkipReason.INVALID_RELATIVE_VOLUME


def test_missing_fmp_float_data_is_skipped_safely() -> None:
    result = compose_valid(float_data=None)

    assert not result.succeeded
    assert result.skipped_reason == CandidateSkipReason.MISSING_FMP_FLOAT_DATA


def test_missing_alpaca_snapshot_data_is_skipped_safely() -> None:
    result = compose_valid(snapshot=None)

    assert not result.succeeded
    assert result.skipped_reason == CandidateSkipReason.MISSING_ALPACA_SNAPSHOT


def test_invalid_price_is_skipped_safely() -> None:
    result = compose_valid(snapshot=snapshot(price=0))

    assert not result.succeeded
    assert result.skipped_reason == CandidateSkipReason.INVALID_PRICE


def test_invalid_float_is_skipped_safely() -> None:
    result = compose_valid(float_data=float_data(float_shares=0))

    assert not result.succeeded
    assert result.skipped_reason == CandidateSkipReason.INVALID_FLOAT


def test_invalid_daily_volume_is_skipped_safely() -> None:
    result = compose_valid(snapshot=snapshot(daily_volume=0))

    assert not result.succeeded
    assert result.skipped_reason == CandidateSkipReason.INVALID_DAILY_VOLUME


def test_mismatched_symbols_are_skipped_safely() -> None:
    result = compose_valid(float_data=float_data(symbol="DIFF"))

    assert not result.succeeded
    assert result.skipped_reason == CandidateSkipReason.MISMATCHED_SYMBOLS


def test_missing_or_invalid_previous_close_skips_without_fabricated_gain() -> None:
    missing_previous = compose_valid(snapshot=snapshot(previous_close=None))
    invalid_previous = compose_valid(snapshot=snapshot(previous_close=0))

    assert missing_previous.skipped_reason == CandidateSkipReason.MISSING_DAILY_GAIN
    assert invalid_previous.skipped_reason == CandidateSkipReason.MISSING_DAILY_GAIN


def test_missing_or_invalid_bars_do_not_block_composition() -> None:
    missing_bars = compose_valid(bars=None)
    invalid_bars = compose_valid(bars=[{"c": "bad"}, {"c": 11.0}])

    assert missing_bars.candidate is not None
    assert missing_bars.candidate.change_15m_pct is None
    assert invalid_bars.candidate is not None
    assert invalid_bars.candidate.change_15m_pct is None


def test_multiple_symbols_can_be_composed_with_invalid_symbols_skipped() -> None:
    results = compose_stock_candidates(
        ["xtrm", "MISS", "NORV", "BADFLOAT"],
        snapshots_by_symbol={
            "XTRM": snapshot(),
            "NORV": snapshot(symbol="NORV"),
            "BADFLOAT": snapshot(symbol="BADFLOAT"),
        },
        float_data_by_symbol={
            "XTRM": float_data(),
            "NORV": FMPFloatData(symbol="NORV", float_shares=2_000_000),
            "BADFLOAT": FMPFloatData(symbol="BADFLOAT", float_shares=-1),
        },
        relative_volume_by_symbol={
            "XTRM": 12.5,
            "BADFLOAT": 5.0,
        },
    )

    assert [result.symbol for result in results] == ["XTRM", "MISS", "NORV", "BADFLOAT"]
    assert results[0].succeeded
    assert results[1].skipped_reason == CandidateSkipReason.MISSING_ALPACA_SNAPSHOT
    assert results[2].skipped_reason == CandidateSkipReason.MISSING_RELATIVE_VOLUME
    assert results[3].skipped_reason == CandidateSkipReason.INVALID_FLOAT


def test_composed_candidates_can_be_scanned_by_scanner_engine() -> None:
    result = compose_valid()
    assert result.candidate is not None

    scan_results = ScannerEngine().scan([result.candidate])

    assert len(scan_results) == 1
    assert scan_results[0].symbol == "XTRM"
    assert scan_results[0].qualified
    assert scan_results[0].tier is not None


def test_phase_7_optional_metrics_contribute_to_scoring_when_present() -> None:
    with_metrics = compose_valid().candidate
    without_metrics = compose_valid(
        snapshot=snapshot(high_of_day=None),
        bars=None,
    ).candidate

    assert with_metrics is not None
    assert without_metrics is not None

    scored = ScannerEngine().scan([with_metrics, without_metrics])
    scores_by_symbol = {result.candidate.change_15m_pct: result.score for result in scored}

    assert scores_by_symbol[14.79] > scores_by_symbol[None]


def test_composer_has_no_network_or_trading_behavior() -> None:
    source = inspect.getsource(composer)
    tree = ast.parse(source)
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert not {"http", "requests", "socket", "urllib", "httpx", "aiohttp"} & imported_modules
    assert "websocket" not in source.lower()
    assert "api_key" not in source.lower()
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()
