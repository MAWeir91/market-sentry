import ast
import inspect

from market_sentry.data import composed_fixture_provider
from market_sentry.data.composed_fixture_provider import OfflineComposedFixtureProvider
from market_sentry.data.composer import CandidateSkipReason
from market_sentry.data.provider import MarketDataProvider
from market_sentry.scanner.engine import ScannerEngine
from market_sentry.scanner.models import StockCandidate


def results_by_symbol(provider: OfflineComposedFixtureProvider):
    return {result.symbol: result for result in provider.build_results()}


def test_composed_fixture_provider_implements_market_data_provider_contract() -> None:
    provider = OfflineComposedFixtureProvider()

    assert isinstance(provider, MarketDataProvider)


def test_composed_fixture_provider_returns_only_valid_stock_candidates() -> None:
    provider = OfflineComposedFixtureProvider()
    candidates = provider.get_candidates()

    assert candidates
    assert all(isinstance(candidate, StockCandidate) for candidate in candidates)
    assert [candidate.symbol for candidate in candidates] == ["CMPX"]


def test_composed_fixture_provider_uses_live_candidate_builder_path() -> None:
    source = inspect.getsource(composed_fixture_provider)

    assert "LiveCandidateBuilder" in source
    assert "compose_stock_candidate" not in source
    assert "compose_stock_candidates" not in source


def test_valid_composed_candidate_scans_under_existing_rules() -> None:
    provider = OfflineComposedFixtureProvider()

    scan_result = ScannerEngine().scan(provider.get_candidates())[0]

    assert scan_result.symbol == "CMPX"
    assert scan_result.qualified
    assert scan_result.tier is not None


def test_static_alpaca_source_supplies_movement_data() -> None:
    candidate = OfflineComposedFixtureProvider().get_candidates()[0]

    assert candidate.symbol == "CMPX"
    assert candidate.price == 8.40
    assert candidate.daily_volume == 3_200_000
    assert candidate.daily_gain_percent == 100.0
    assert candidate.high_of_day == 8.75


def test_static_fmp_source_supplies_float_data() -> None:
    candidate = OfflineComposedFixtureProvider().get_candidates()[0]

    assert candidate.float_shares == 1_100_000


def test_relative_volume_is_explicit_and_not_fabricated() -> None:
    provider = OfflineComposedFixtureProvider()
    results = results_by_symbol(provider)

    assert provider.relative_volume_by_symbol["CMPX"] == 7.4
    assert results["CMPX"].candidate is not None
    assert results["CMPX"].candidate.relative_volume == 7.4
    assert results["NORV"].skipped_reason == CandidateSkipReason.MISSING_RELATIVE_VOLUME


def test_missing_or_invalid_fmp_float_symbol_is_skipped() -> None:
    results = results_by_symbol(OfflineComposedFixtureProvider())

    assert results["BADFLT"].skipped_reason == CandidateSkipReason.INVALID_FLOAT
    assert results["BADFLT"].candidate is None


def test_missing_alpaca_movement_symbol_is_skipped() -> None:
    results = results_by_symbol(OfflineComposedFixtureProvider())

    assert results["NOMOVE"].skipped_reason == CandidateSkipReason.MISSING_ALPACA_SNAPSHOT
    assert results["NOMOVE"].candidate is None


def test_build_results_are_inspectable() -> None:
    results = results_by_symbol(OfflineComposedFixtureProvider())

    assert set(results) == {"CMPX", "NORV", "BADFLT", "NOMOVE"}
    assert results["CMPX"].succeeded
    assert not results["NORV"].succeeded
    assert not results["BADFLT"].succeeded
    assert not results["NOMOVE"].succeeded


def test_composed_fixture_provider_has_no_network_credentials_or_trading_behavior() -> None:
    source = inspect.getsource(composed_fixture_provider)
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
    assert "HttpTransport" not in source
    assert "api_key" not in source.lower()
    assert "websocket" not in source.lower()
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()
