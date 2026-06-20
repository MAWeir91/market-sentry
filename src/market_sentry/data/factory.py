"""Provider factory skeleton for future real data providers."""

from __future__ import annotations

from dataclasses import replace

from market_sentry.config import (
    LIVE_COMPOSED_PROVIDER,
    AppConfig,
    validate_live_provider_gate,
)
from market_sentry.data.alpaca_fetcher import AlpacaSnapshotFetcher
from market_sentry.data.composed_fixture_provider import OfflineComposedFixtureProvider
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.fmp_fetcher import FMPFloatFetcher
from market_sentry.data.http_stdlib import StdlibHttpTransport
from market_sentry.data.live_provider_builder import build_live_composed_provider
from market_sentry.data.local_rvol_artifact_manifest import (
    LocalRvolArtifactManifestError,
    load_local_rvol_artifact_manifest,
)
from market_sentry.data.local_rvol_artifact_provider import (
    LocalRvolArtifactProvider,
    LocalRvolArtifactProviderError,
)
from market_sentry.data.mock_provider import MockMarketDataProvider
from market_sentry.data.provider import MarketDataProvider


class ProviderConfigurationError(ValueError):
    """Raised when provider configuration is unsupported or invalid."""


def _create_live_composed_provider(config: AppConfig) -> MarketDataProvider:
    normalized_config = replace(config, provider=LIVE_COMPOSED_PROVIDER)
    gate_result = validate_live_provider_gate(normalized_config)

    if not gate_result.allowed:
        reasons = ", ".join(reason.value for reason in gate_result.failure_reasons)
        raise ProviderConfigurationError(
            f"{LIVE_COMPOSED_PROVIDER} is not enabled. "
            f"Missing requirements: {reasons}."
        )

    try:
        manifest = load_local_rvol_artifact_manifest(
            normalized_config.rvol_artifact_manifest_path
        )
        relative_volumes = LocalRvolArtifactProvider(manifest).get_relative_volumes(
            normalized_config.watchlist
        )
    except (LocalRvolArtifactManifestError, LocalRvolArtifactProviderError) as exc:
        raise ProviderConfigurationError(
            f"{LIVE_COMPOSED_PROVIDER} local RVOL artifacts invalid: {exc}."
        ) from exc

    return build_live_composed_provider(
        normalized_config,
        relative_volume_by_symbol=relative_volumes,
        transport_factory=StdlibHttpTransport,
        alpaca_fetcher_factory=AlpacaSnapshotFetcher,
        fmp_fetcher_factory=FMPFloatFetcher,
        gate_result=gate_result,
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
        return _create_live_composed_provider(config)

    raise ProviderConfigurationError(
        f"Unknown market data provider: {provider}"
    )
