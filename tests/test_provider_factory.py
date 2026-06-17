import ast
import inspect

import pytest

from market_sentry.config import AppConfig
from market_sentry.config import load_config
from market_sentry.data import factory
from market_sentry.data.composed_fixture_provider import OfflineComposedFixtureProvider
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.mock_provider import MockMarketDataProvider


def test_provider_factory_returns_mock_provider_for_mock() -> None:
    provider = create_market_data_provider(AppConfig(provider="mock"))

    assert isinstance(provider, MockMarketDataProvider)


def test_provider_factory_returns_fixture_provider_for_fixture() -> None:
    provider = create_market_data_provider(AppConfig(provider="fixture"))

    assert isinstance(provider, FixtureComposedMarketDataProvider)


def test_provider_factory_returns_composed_fixture_provider_for_composed_fixture() -> None:
    provider = create_market_data_provider(AppConfig(provider="composed_fixture"))

    assert isinstance(provider, OfflineComposedFixtureProvider)


def test_provider_factory_normalizes_provider_name() -> None:
    mock_provider = create_market_data_provider(AppConfig(provider=" MOCK "))
    fixture_provider = create_market_data_provider(AppConfig(provider=" FIXTURE "))
    composed_fixture_provider = create_market_data_provider(
        AppConfig(provider=" COMPOSED_FIXTURE ")
    )

    assert isinstance(mock_provider, MockMarketDataProvider)
    assert isinstance(fixture_provider, FixtureComposedMarketDataProvider)
    assert isinstance(composed_fixture_provider, OfflineComposedFixtureProvider)


def test_provider_factory_raises_clear_error_for_alpaca_placeholder() -> None:
    with pytest.raises(ProviderConfigurationError, match="future placeholder"):
        create_market_data_provider(AppConfig(provider="alpaca"))


def test_provider_factory_raises_clear_error_for_unknown_provider() -> None:
    with pytest.raises(ProviderConfigurationError, match="Unknown market data provider"):
        create_market_data_provider(AppConfig(provider="other"))


def test_provider_factory_requires_no_credentials_for_mock() -> None:
    provider = create_market_data_provider(AppConfig(provider="mock"))

    assert isinstance(provider, MockMarketDataProvider)


def test_provider_factory_requires_no_credentials_for_fixture() -> None:
    provider = create_market_data_provider(
        AppConfig(
            provider="fixture",
            alpaca_api_key=None,
            alpaca_api_secret=None,
            fmp_api_key=None,
        )
    )

    assert isinstance(provider, FixtureComposedMarketDataProvider)
    assert provider.get_candidates()


def test_provider_factory_requires_no_credentials_for_composed_fixture() -> None:
    provider = create_market_data_provider(
        AppConfig(
            provider="composed_fixture",
            alpaca_api_key=None,
            alpaca_api_secret=None,
            fmp_api_key=None,
        )
    )

    assert isinstance(provider, OfflineComposedFixtureProvider)
    assert provider.get_candidates()


def test_environment_provider_fixture_loads_without_credentials() -> None:
    config = load_config({"MARKET_SENTRY_PROVIDER": "fixture"})
    provider = create_market_data_provider(config)

    assert isinstance(provider, FixtureComposedMarketDataProvider)


def test_environment_provider_composed_fixture_loads_without_credentials() -> None:
    config = load_config({"MARKET_SENTRY_PROVIDER": "composed_fixture"})
    provider = create_market_data_provider(config)

    assert isinstance(provider, OfflineComposedFixtureProvider)


def test_provider_factory_has_no_network_dependencies() -> None:
    source = inspect.getsource(factory)
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
