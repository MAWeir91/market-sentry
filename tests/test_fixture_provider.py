import ast
import inspect

from market_sentry.data import fixture_provider
from market_sentry.data.composer import CandidateSkipReason
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.provider import MarketDataProvider
from market_sentry.scanner.engine import ScannerEngine
from market_sentry.scanner.models import StockCandidate


def candidates_by_symbol(
    provider: FixtureComposedMarketDataProvider,
) -> dict[str, StockCandidate]:
    return {candidate.symbol: candidate for candidate in provider.get_candidates()}


def test_fixture_provider_implements_market_data_provider_contract() -> None:
    provider = FixtureComposedMarketDataProvider()

    assert isinstance(provider, MarketDataProvider)


def test_fixture_provider_returns_stock_candidates_only() -> None:
    provider = FixtureComposedMarketDataProvider()
    candidates = provider.get_candidates()

    assert candidates
    assert all(isinstance(candidate, StockCandidate) for candidate in candidates)


def test_fixture_provider_uses_composed_alpaca_and_fmp_fixture_data() -> None:
    candidates = candidates_by_symbol(FixtureComposedMarketDataProvider())

    assert candidates["XTRM"].price == 11.40
    assert candidates["XTRM"].daily_volume == 6_400_000
    assert candidates["XTRM"].daily_gain_percent == 100.0
    assert candidates["XTRM"].float_shares == 1_300_000


def test_fixture_provider_carries_phase_7_optional_metrics() -> None:
    candidates = candidates_by_symbol(FixtureComposedMarketDataProvider())

    assert candidates["XTRM"].high_of_day == 11.55
    assert candidates["XTRM"].change_15m_pct == 14.79
    assert candidates["HODC"].high_of_day == 6.00
    assert candidates["FSTN"].change_15m_pct == 21.33


def test_fixture_provider_uses_explicit_relative_volume_fixture_data() -> None:
    candidates = candidates_by_symbol(FixtureComposedMarketDataProvider())

    assert candidates["XTRM"].relative_volume == 12.5
    assert candidates["ROTA"].relative_volume == 8.1
    assert candidates["FSTN"].relative_volume == 2.8


def test_fixture_provider_does_not_fabricate_missing_relative_volume() -> None:
    provider = FixtureComposedMarketDataProvider()
    skipped = {
        result.symbol: result.skipped_reason
        for result in provider.composition_results()
        if not result.succeeded
    }

    assert skipped["NORV"] == CandidateSkipReason.MISSING_RELATIVE_VOLUME
    assert "NORV" not in candidates_by_symbol(provider)


def test_fixture_provider_skips_invalid_fixture_records_safely() -> None:
    provider = FixtureComposedMarketDataProvider()
    skipped = {
        result.symbol: result.skipped_reason
        for result in provider.composition_results()
        if not result.succeeded
    }

    assert skipped["NOFLT"] == CandidateSkipReason.MISSING_FMP_FLOAT_DATA
    assert "NOFLT" not in candidates_by_symbol(provider)


def test_get_candidates_returns_only_successfully_composed_candidates() -> None:
    provider = FixtureComposedMarketDataProvider()
    results = provider.composition_results()
    candidates = provider.get_candidates()

    assert len(candidates) == sum(result.succeeded for result in results)
    assert {candidate.symbol for candidate in candidates} == {
        "XTRM",
        "ROTA",
        "HODC",
        "FSTN",
    }


def test_fixture_composed_candidates_can_be_scanned() -> None:
    provider = FixtureComposedMarketDataProvider()

    results = ScannerEngine().scan(provider.get_candidates())

    assert results
    assert all(result.candidate.symbol in {"XTRM", "ROTA", "HODC", "FSTN"} for result in results)
    assert any(result.qualified for result in results)


def test_fixture_provider_includes_strong_rotation_candidate() -> None:
    candidates = candidates_by_symbol(FixtureComposedMarketDataProvider())

    assert candidates["ROTA"].rotation == 8.0


def test_fixture_provider_has_no_network_or_trading_behavior() -> None:
    source = inspect.getsource(fixture_provider)
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
