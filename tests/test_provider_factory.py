import ast
import inspect

import pytest

from market_sentry.config import AppConfig
from market_sentry.data import factory
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.mock_provider import MockMarketDataProvider


def test_provider_factory_returns_mock_provider_for_mock() -> None:
    provider = create_market_data_provider(AppConfig(provider="mock"))

    assert isinstance(provider, MockMarketDataProvider)


def test_provider_factory_normalizes_provider_name() -> None:
    provider = create_market_data_provider(AppConfig(provider=" MOCK "))

    assert isinstance(provider, MockMarketDataProvider)


def test_provider_factory_raises_clear_error_for_alpaca_placeholder() -> None:
    with pytest.raises(ProviderConfigurationError, match="future placeholder"):
        create_market_data_provider(AppConfig(provider="alpaca"))


def test_provider_factory_raises_clear_error_for_unknown_provider() -> None:
    with pytest.raises(ProviderConfigurationError, match="Unknown market data provider"):
        create_market_data_provider(AppConfig(provider="other"))


def test_provider_factory_requires_no_credentials_for_mock() -> None:
    provider = create_market_data_provider(AppConfig(provider="mock"))

    assert isinstance(provider, MockMarketDataProvider)


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
