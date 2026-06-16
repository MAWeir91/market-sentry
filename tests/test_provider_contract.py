import ast
import inspect

from market_sentry.data import MarketDataProvider, MockMarketDataProvider
from market_sentry.data import mock_provider
from market_sentry.scanner.engine import ScannerEngine
from market_sentry.scanner.models import ScannerResult, StockCandidate


def test_mock_market_data_provider_has_get_candidates() -> None:
    provider = MockMarketDataProvider()

    assert isinstance(provider, MarketDataProvider)
    assert callable(provider.get_candidates)


def test_get_candidates_returns_list() -> None:
    provider = MockMarketDataProvider()

    assert isinstance(provider.get_candidates(), list)


def test_every_provider_item_is_stock_candidate() -> None:
    provider = MockMarketDataProvider()

    assert all(isinstance(candidate, StockCandidate) for candidate in provider.get_candidates())


def test_mock_provider_returns_at_least_one_candidate() -> None:
    provider = MockMarketDataProvider()

    assert len(provider.get_candidates()) > 0


def test_provider_output_is_deterministic_between_calls() -> None:
    provider = MockMarketDataProvider()

    assert provider.get_candidates() == provider.get_candidates()
    assert provider.get_candidates() is not provider.get_candidates()


def test_scanner_engine_can_evaluate_provider_candidates() -> None:
    provider = MockMarketDataProvider()
    engine = ScannerEngine()

    results = engine.scan(provider.get_candidates())

    assert results
    assert all(isinstance(result, ScannerResult) for result in results)
    assert {result.symbol for result in results} == {
        candidate.symbol for candidate in provider.get_candidates()
    }


def test_mock_provider_includes_phase_7_optional_metrics() -> None:
    candidates = MockMarketDataProvider().get_candidates()

    assert any(candidate.rotation is not None for candidate in candidates)
    assert any(
        candidate.rotation is not None and candidate.rotation >= 4.0
        for candidate in candidates
    )
    assert any(
        candidate.distance_from_high_pct is not None
        and candidate.distance_from_high_pct <= 2.0
        for candidate in candidates
    )
    assert any(
        candidate.change_15m_pct is not None and candidate.change_15m_pct >= 8.0
        for candidate in candidates
    )
    assert any(
        candidate.high_of_day is None and candidate.change_15m_pct is None
        for candidate in candidates
    )


def test_mock_provider_has_no_external_service_dependencies() -> None:
    source = inspect.getsource(mock_provider)
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

    assert not {"http", "requests", "socket", "urllib", "os"} & imported_modules
    assert "getenv" not in source
    assert "environ" not in source
