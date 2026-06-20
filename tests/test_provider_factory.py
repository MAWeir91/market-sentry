import ast
import inspect
import json
from pathlib import Path

import pytest

from market_sentry.config import (
    LIVE_COMPOSED_PROVIDER,
    AppConfig,
    LiveProviderGateFailure,
    LiveProviderGateResult,
    load_config,
)
from market_sentry.data import factory
from market_sentry.data.alpaca import AlpacaSnapshot
from market_sentry.data.composed_fixture_provider import OfflineComposedFixtureProvider
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.fmp import FMPFloatData
from market_sentry.data.http import FakeHttpTransport, HttpResponse
from market_sentry.data.live_composed_provider import LiveComposedMarketDataProvider
from market_sentry.data.local_rvol_artifact_manifest import (
    LocalRvolArtifact,
    LocalRvolArtifactManifest,
    LocalRvolArtifactManifestError,
)
from market_sentry.data.local_rvol_artifact_provider import LocalRvolArtifactProviderError
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
        "rvol_artifact_manifest_path": Path("rvol-artifacts.json"),
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


def test_live_composed_builds_one_shot_provider_after_local_artifact_preflight(
    monkeypatch,
) -> None:
    calls = []
    manifest = LocalRvolArtifactManifest(
        path=Path("rvol-artifacts.json"),
        artifacts=(
            LocalRvolArtifact(
                symbol="AAPL",
                metadata_path=Path("AAPL.metadata.json"),
                bundle_path=Path("AAPL.bundle.json"),
            ),
        ),
    )

    class FakeArtifactProvider:
        def __init__(self, loaded_manifest):
            calls.append(("provider", loaded_manifest))

        def get_relative_volumes(self, symbols):
            calls.append(("rvol", tuple(symbols)))
            return {"AAPL": 2.0}

    def fake_builder(config, **kwargs):
        calls.append(("builder", config, kwargs))
        return "provider"

    monkeypatch.setattr(
        factory,
        "load_local_rvol_artifact_manifest",
        lambda path: calls.append(("manifest", path)) or manifest,
    )
    monkeypatch.setattr(factory, "LocalRvolArtifactProvider", FakeArtifactProvider)
    monkeypatch.setattr(factory, "build_live_composed_provider", fake_builder)

    provider = create_market_data_provider(live_composed_config())

    assert provider == "provider"
    assert [call[0] for call in calls] == ["manifest", "provider", "rvol", "builder"]
    assert calls[0][1] == Path("rvol-artifacts.json")
    assert calls[1][1] is manifest
    assert calls[2][1] == ("AAPL",)
    assert calls[3][2]["relative_volume_by_symbol"] == {"AAPL": 2.0}
    assert calls[3][2]["transport_factory"] is factory.StdlibHttpTransport
    assert calls[3][2]["alpaca_fetcher_factory"] is factory.AlpacaSnapshotFetcher
    assert calls[3][2]["fmp_fetcher_factory"] is factory.FMPFloatFetcher


def test_live_composed_runs_phase_12a_config_gate(monkeypatch) -> None:
    seen_providers: list[str] = []

    def fake_gate(config: AppConfig) -> LiveProviderGateResult:
        seen_providers.append(config.provider)
        return LiveProviderGateResult(
            allowed=False,
            failure_reasons=(LiveProviderGateFailure.LIVE_DATA_NOT_ALLOWED,),
        )

    monkeypatch.setattr(factory, "validate_live_provider_gate", fake_gate)

    with pytest.raises(ProviderConfigurationError, match="LIVE_DATA_NOT_ALLOWED"):
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


def test_live_composed_missing_manifest_path_produces_clean_failure() -> None:
    assert_live_composed_error_contains(
        live_composed_config(rvol_artifact_manifest_path=None),
        LiveProviderGateFailure.MISSING_RVOL_ARTIFACT_MANIFEST_PATH,
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


def test_live_composed_local_artifact_errors_are_secret_safe(monkeypatch) -> None:
    monkeypatch.setattr(
        factory,
        "load_local_rvol_artifact_manifest",
        lambda _path: (_ for _ in ()).throw(
            LocalRvolArtifactManifestError("DUPLICATE_SYMBOL:AAPL")
        ),
    )

    with pytest.raises(ProviderConfigurationError) as exc_info:
        create_market_data_provider(
            live_composed_config(alpaca_api_key="visible-key-should-not-print")
        )

    message = str(exc_info.value)
    assert message == (
        "live_composed local RVOL artifacts invalid: DUPLICATE_SYMBOL:AAPL."
    )
    assert "visible-key-should-not-print" not in message


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


def test_provider_factory_imports_only_existing_live_transport_classes() -> None:
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

    assert not {"requests", "socket", "urllib", "httpx", "aiohttp"} & imported_modules


def test_live_composed_path_constructs_no_http_request_during_factory(monkeypatch) -> None:
    transport = FakeHttpTransport([])
    calls = []
    manifest = LocalRvolArtifactManifest(path=Path("manifest.json"), artifacts=())

    monkeypatch.setattr(factory, "load_local_rvol_artifact_manifest", lambda _path: manifest)
    monkeypatch.setattr(
        factory.LocalRvolArtifactProvider,
        "get_relative_volumes",
        lambda self, symbols: {"AAPL": 2.0},
    )
    monkeypatch.setattr(factory, "StdlibHttpTransport", lambda: calls.append("transport") or transport)

    provider = create_market_data_provider(live_composed_config())

    assert isinstance(provider, LiveComposedMarketDataProvider)
    assert calls == ["transport"]
    assert transport.requests == []


def test_live_composed_source_boundary() -> None:
    source = inspect.getsource(factory)

    assert ".send(" not in source


def test_live_composed_fake_transport_candidate_flow(monkeypatch) -> None:
    transport = FakeHttpTransport(
        [
            HttpResponse(
                status_code=200,
                body=json.dumps(
                    {
                        "snapshots": {
                            "AAPL": {
                                "latestTrade": {"p": 4.8},
                                "dailyBar": {"v": 1_400_000, "h": 4.95},
                                "prevDailyBar": {"c": 3.6},
                            }
                        }
                    }
                ),
            ),
            HttpResponse(
                status_code=200,
                body=json.dumps(
                    [
                        {
                            "symbol": "AAPL",
                            "floatShares": 4_600_000,
                            "outstandingShares": 8_000_000,
                            "date": "2026-06-20",
                        }
                    ]
                ),
            ),
        ]
    )
    manifest = LocalRvolArtifactManifest(path=Path("manifest.json"), artifacts=())
    monkeypatch.setattr(factory, "load_local_rvol_artifact_manifest", lambda _path: manifest)
    monkeypatch.setattr(
        factory.LocalRvolArtifactProvider,
        "get_relative_volumes",
        lambda self, symbols: {"AAPL": 3.8},
    )
    monkeypatch.setattr(factory, "StdlibHttpTransport", lambda: transport)

    provider = create_market_data_provider(live_composed_config())
    assert transport.requests == []

    candidates = provider.get_candidates()

    assert len(transport.requests) == 2
    assert transport.requests[0].url.endswith("/v2/stocks/snapshots")
    assert transport.requests[1].url.endswith("/stable/shares-float")
    assert [candidate.symbol for candidate in candidates] == ["AAPL"]
    assert candidates[0].relative_volume == 3.8
