from pathlib import Path

import pytest

from market_sentry.config import AppConfig
from market_sentry.data.composed_fixture_provider import OfflineComposedFixtureProvider
from market_sentry.data.factory import ProviderConfigurationError, create_market_data_provider
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.mock_provider import MockMarketDataProvider


ROOT = Path(__file__).resolve().parents[1]


def read_project_file(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_env_example_documents_live_readiness_variables_without_real_values() -> None:
    content = read_project_file(".env.example")

    assert "# MARKET_SENTRY_PROVIDER=live_composed" in content
    assert "# MARKET_SENTRY_ALLOW_LIVE_DATA=false" in content
    assert "# MARKET_SENTRY_WATCHLIST=AAPL,MSFT" in content
    assert "# ALPACA_API_KEY=" in content
    assert "# ALPACA_API_SECRET=" in content
    assert "# ALPACA_DATA_FEED=iex" in content
    assert "# FMP_API_KEY=" in content
    assert "placeholder-key" not in content
    assert "placeholder-secret" not in content
    assert "placeholder-fmp-key" not in content


def test_env_example_documents_provider_options_and_boundaries() -> None:
    content = read_project_file(".env.example")

    assert "# MARKET_SENTRY_PROVIDER=mock" in content
    assert "# MARKET_SENTRY_PROVIDER=fixture" in content
    assert "# MARKET_SENTRY_PROVIDER=composed_fixture" in content
    assert "Default provider is mock." in content
    assert "fixture and composed_fixture are offline." in content
    assert "alpaca remains a placeholder." in content
    assert "live_composed remains reserved, gated, and inactive" in content
    assert "Setting live env vars does not activate live scanning yet." in content
    assert "python -m market_sentry --live-readiness" in content
    assert "python -m market_sentry --live-readiness --relative-volume-configured" in content


def test_readme_documents_live_readiness_preflight_usage() -> None:
    content = read_project_file("README.md")

    assert "python -m market_sentry --live-readiness" in content
    assert "python -m market_sentry --live-readiness --relative-volume-configured" in content
    assert "$env:MARKET_SENTRY_PROVIDER=\"live_composed\"" in content
    assert "$env:MARKET_SENTRY_ALLOW_LIVE_DATA=\"true\"" in content
    assert "$env:MARKET_SENTRY_WATCHLIST=\"AAPL\"" in content
    assert "$env:MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH=" in content
    assert "$env:ALPACA_API_KEY=\"placeholder-key\"" in content
    assert "$env:ALPACA_API_SECRET=\"placeholder-secret\"" in content
    assert "$env:FMP_API_KEY=\"placeholder-fmp-key\"" in content


def test_readme_documents_preflight_safety_boundaries() -> None:
    content = read_project_file("README.md")

    assert "`--live-readiness` performs local checks only." in content
    assert "does not call Alpaca, FMP, or any network API" in content
    assert "does not activate `live_composed`" in content
    assert "does not render the scanner report" in content
    assert "`--relative-volume-configured` is only an explicit local signal" in content
    assert "RVOL is not calculated, fetched, inferred, or fabricated." in content
    assert "`live_composed` is available only for one-shot scanner runs" in content
    assert "Alpaca remains a placeholder" in content
    assert "trading/order functionality is out of scope" in content


def test_runtime_provider_factory_remains_unchanged() -> None:
    assert isinstance(create_market_data_provider(AppConfig()), MockMarketDataProvider)
    assert isinstance(
        create_market_data_provider(AppConfig(provider="fixture")),
        FixtureComposedMarketDataProvider,
    )
    assert isinstance(
        create_market_data_provider(AppConfig(provider="composed_fixture")),
        OfflineComposedFixtureProvider,
    )

    with pytest.raises(ProviderConfigurationError, match="future placeholder"):
        create_market_data_provider(AppConfig(provider="alpaca"))

    with pytest.raises(ProviderConfigurationError, match="MISSING_RVOL_ARTIFACT"):
        create_market_data_provider(
            AppConfig(
                provider="live_composed",
                allow_live_data=True,
                watchlist=("AAPL",),
                alpaca_api_key="placeholder-key",
                alpaca_api_secret="placeholder-secret",
                fmp_api_key="placeholder-fmp-key",
            )
        )
