import ast
import inspect

import pytest

from market_sentry.config import (
    LIVE_COMPOSED_PROVIDER,
    AppConfig,
    LiveProviderGateFailure,
    LiveProviderGateResult,
    load_config,
)
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


def live_composed_config(**overrides: object) -> AppConfig:
    values = {
        "provider": LIVE_COMPOSED_PROVIDER,
        "allow_live_data": True,
        "watchlist": ("AAPL",),
        "alpaca_api_key": "placeholder-key",
        "alpaca_api_secret": "placeholder-secret",
        "fmp_api_key": "placeholder-fmp-key",
    }
    values.update(overrides)
    return AppConfig(**values)


def assert_live_composed_error_contains(
    config: AppConfig,
    expected_reason: LiveProviderGateFailure,
) -> None:
    with pytest.raises(ProviderConfigurationError) as exc_info:
        create_market_data_provider(config)

    message = str(exc_info.value)

    assert f"{LIVE_COMPOSED_PROVIDER} is not enabled." in message
    assert "Missing requirements:" in message
    assert expected_reason.value in message


def test_live_composed_is_recognized_as_reserved_provider_name() -> None:
    with pytest.raises(ProviderConfigurationError) as exc_info:
        create_market_data_provider(live_composed_config())

    assert (
        str(exc_info.value)
        == "live_composed is reserved for a future live provider and is not active yet."
    )


def test_live_composed_runs_phase_12a_config_gate(monkeypatch) -> None:
    seen_providers: list[str] = []

    def fake_gate(config: AppConfig) -> LiveProviderGateResult:
        seen_providers.append(config.provider)
        return LiveProviderGateResult(allowed=True, failure_reasons=())

    monkeypatch.setattr(factory, "validate_live_provider_gate", fake_gate)

    with pytest.raises(ProviderConfigurationError, match="reserved"):
        create_market_data_provider(AppConfig(provider=" LIVE_COMPOSED "))

    assert seen_providers == [LIVE_COMPOSED_PROVIDER]


def test_live_composed_missing_allow_live_flag_produces_clean_failure() -> None:
    assert_live_composed_error_contains(
        live_composed_config(allow_live_data=False),
        LiveProviderGateFailure.LIVE_DATA_NOT_ALLOWED,
    )


def test_live_composed_missing_watchlist_produces_clean_failure() -> None:
    assert_live_composed_error_contains(
        live_composed_config(watchlist=()),
        LiveProviderGateFailure.MISSING_WATCHLIST,
    )


def test_live_composed_missing_alpaca_key_produces_clean_failure() -> None:
    assert_live_composed_error_contains(
        live_composed_config(alpaca_api_key=None),
        LiveProviderGateFailure.MISSING_ALPACA_API_KEY,
    )


def test_live_composed_missing_alpaca_secret_produces_clean_failure() -> None:
    assert_live_composed_error_contains(
        live_composed_config(alpaca_api_secret=None),
        LiveProviderGateFailure.MISSING_ALPACA_API_SECRET,
    )


def test_live_composed_missing_fmp_key_produces_clean_failure() -> None:
    assert_live_composed_error_contains(
        live_composed_config(fmp_api_key=None),
        LiveProviderGateFailure.MISSING_FMP_API_KEY,
    )


def test_live_composed_failure_message_does_not_expose_secret_values() -> None:
    config = live_composed_config(
        allow_live_data=False,
        alpaca_api_key="visible-key-should-not-print",
        alpaca_api_secret="visible-secret-should-not-print",
        fmp_api_key="visible-fmp-should-not-print",
    )

    with pytest.raises(ProviderConfigurationError) as exc_info:
        create_market_data_provider(config)

    message = str(exc_info.value)

    assert "visible-key-should-not-print" not in message
    assert "visible-secret-should-not-print" not in message
    assert "visible-fmp-should-not-print" not in message
    assert LiveProviderGateFailure.LIVE_DATA_NOT_ALLOWED.value in message


def test_live_composed_gate_passing_config_still_fails_as_reserved_inactive() -> None:
    with pytest.raises(ProviderConfigurationError) as exc_info:
        create_market_data_provider(live_composed_config())

    assert (
        str(exc_info.value)
        == "live_composed is reserved for a future live provider and is not active yet."
    )


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


def test_live_composed_path_does_not_instantiate_live_runtime_components() -> None:
    source = inspect.getsource(factory)

    assert "StdlibHttpTransport" not in source
    assert "AlpacaSnapshotFetcher" not in source
    assert "FMPFloatFetcher" not in source
    assert ".send(" not in source
