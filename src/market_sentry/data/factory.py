"""Provider factory skeleton for future real data providers."""

from __future__ import annotations

from market_sentry.config import AppConfig
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.mock_provider import MockMarketDataProvider
from market_sentry.data.provider import MarketDataProvider


class ProviderConfigurationError(ValueError):
    """Raised when provider configuration is unsupported or invalid."""


def create_market_data_provider(config: AppConfig) -> MarketDataProvider:
    """Create the configured market data provider without network access."""

    provider = config.provider.strip().lower()

    if provider == "mock":
        return MockMarketDataProvider()

    if provider == "fixture":
        return FixtureComposedMarketDataProvider()

    if provider == "alpaca":
        raise ProviderConfigurationError(
            "Alpaca provider is a future placeholder. Live API implementation "
            "is not present yet."
        )

    raise ProviderConfigurationError(
        f"Unknown market data provider: {provider}"
    )
