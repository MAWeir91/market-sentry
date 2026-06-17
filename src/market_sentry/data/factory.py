"""Provider factory skeleton for future real data providers."""

from __future__ import annotations

from dataclasses import replace

from market_sentry.config import (
    LIVE_COMPOSED_PROVIDER,
    AppConfig,
    validate_live_provider_gate,
)
from market_sentry.data.composed_fixture_provider import OfflineComposedFixtureProvider
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.mock_provider import MockMarketDataProvider
from market_sentry.data.provider import MarketDataProvider


class ProviderConfigurationError(ValueError):
    """Raised when provider configuration is unsupported or invalid."""


def _raise_live_composed_placeholder(config: AppConfig) -> None:
    normalized_config = replace(config, provider=LIVE_COMPOSED_PROVIDER)
    gate_result = validate_live_provider_gate(normalized_config)

    if not gate_result.allowed:
        reasons = ", ".join(reason.value for reason in gate_result.failure_reasons)
        raise ProviderConfigurationError(
            f"{LIVE_COMPOSED_PROVIDER} is not enabled. "
            f"Missing requirements: {reasons}."
        )

    raise ProviderConfigurationError(
        f"{LIVE_COMPOSED_PROVIDER} is reserved for a future live provider "
        "and is not active yet."
    )


def create_market_data_provider(config: AppConfig) -> MarketDataProvider:
    """Create the configured market data provider without network access."""

    provider = config.provider.strip().lower()

    if provider == "mock":
        return MockMarketDataProvider()

    if provider == "fixture":
        return FixtureComposedMarketDataProvider()

    if provider == "composed_fixture":
        return OfflineComposedFixtureProvider()

    if provider == "alpaca":
        raise ProviderConfigurationError(
            "Alpaca provider is a future placeholder. Live API implementation "
            "is not present yet."
        )

    if provider == LIVE_COMPOSED_PROVIDER:
        _raise_live_composed_placeholder(config)

    raise ProviderConfigurationError(
        f"Unknown market data provider: {provider}"
    )
