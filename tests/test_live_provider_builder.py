import ast
import inspect

import pytest

from market_sentry.config import (
    AppConfig,
    LiveProviderGateFailure,
    LiveProviderGateResult,
)
from market_sentry.data import factory, live_provider_builder
from market_sentry.data.alpaca import AlpacaMarketDataSettings, AlpacaSnapshot
from market_sentry.data.composer import CandidateSkipReason
from market_sentry.data.composed_fixture_provider import OfflineComposedFixtureProvider
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.fmp import FMPFloatData, FMPReferenceSettings
from market_sentry.data.live_composed_provider import LiveComposedMarketDataProvider
from market_sentry.data.live_provider_builder import (
    LiveProviderBuildError,
    build_live_composed_provider,
)
from market_sentry.data.mock_provider import MockMarketDataProvider


class FakeTransport:
    def __init__(self) -> None:
        self.send_calls = 0

    def send(self, _request):
        self.send_calls += 1
        raise AssertionError("Network send should not be called in Phase 12D tests.")


class FakeAlpacaFetcher:
    def __init__(
        self,
        *,
        settings: AlpacaMarketDataSettings,
        transport: FakeTransport,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.calls: list[list[str] | tuple[str, ...]] = []

    def fetch_snapshots(self, symbols: list[str] | tuple[str, ...]) -> dict[str, AlpacaSnapshot]:
        self.calls.append(symbols)
        return {
            "XTRM": AlpacaSnapshot(
                symbol="XTRM",
                price=11.4,
                daily_volume=6_400_000,
                high_of_day=11.55,
                previous_close=5.7,
            ),
            "MISSRV": AlpacaSnapshot(
                symbol="MISSRV",
                price=4.2,
                daily_volume=900_000,
                high_of_day=4.4,
                previous_close=3.0,
            ),
        }


class FakeFMPFetcher:
    def __init__(
        self,
        *,
        settings: FMPReferenceSettings,
        transport: FakeTransport,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.calls: list[str | None] = []

    def fetch_float(self, symbol: str | None) -> FMPFloatData | None:
        self.calls.append(symbol)
        if symbol == "XTRM":
            return FMPFloatData(
                symbol="XTRM",
                float_shares=1_300_000,
                outstanding_shares=6_000_000,
                date="2026-06-17",
            )
        if symbol == "MISSRV":
            return FMPFloatData(symbol="MISSRV", float_shares=2_000_000)
        return None


def live_config(**overrides: object) -> AppConfig:
    values = {
        "provider": "live_composed",
        "allow_live_data": True,
        "watchlist": ("XTRM",),
        "alpaca_api_key": "placeholder-key",
        "alpaca_api_secret": "placeholder-secret",
        "fmp_api_key": "placeholder-fmp-key",
    }
    values.update(overrides)
    return AppConfig(**values)


class FactoryRecorder:
    def __init__(self) -> None:
        self.transport = FakeTransport()
        self.alpaca_fetchers: list[FakeAlpacaFetcher] = []
        self.fmp_fetchers: list[FakeFMPFetcher] = []

    def transport_factory(self) -> FakeTransport:
        return self.transport

    def alpaca_fetcher_factory(
        self,
        *,
        settings: AlpacaMarketDataSettings,
        transport: FakeTransport,
    ) -> FakeAlpacaFetcher:
        fetcher = FakeAlpacaFetcher(settings=settings, transport=transport)
        self.alpaca_fetchers.append(fetcher)
        return fetcher

    def fmp_fetcher_factory(
        self,
        *,
        settings: FMPReferenceSettings,
        transport: FakeTransport,
    ) -> FakeFMPFetcher:
        fetcher = FakeFMPFetcher(settings=settings, transport=transport)
        self.fmp_fetchers.append(fetcher)
        return fetcher


def build_provider(
    *,
    config: AppConfig | None = None,
    relative_volume_by_symbol: dict[str, float | int | str] | None = None,
    gate_result: LiveProviderGateResult | None = None,
) -> tuple[LiveComposedMarketDataProvider, FactoryRecorder]:
    recorder = FactoryRecorder()
    provider = build_live_composed_provider(
        config or live_config(),
        relative_volume_by_symbol=(
            {"XTRM": 12.5}
            if relative_volume_by_symbol is None
            else relative_volume_by_symbol
        ),
        transport_factory=recorder.transport_factory,
        alpaca_fetcher_factory=recorder.alpaca_fetcher_factory,
        fmp_fetcher_factory=recorder.fmp_fetcher_factory,
        gate_result=gate_result,
    )
    return provider, recorder


def test_builder_constructs_live_composed_provider_using_injected_fake_factories() -> None:
    provider, recorder = build_provider()

    assert isinstance(provider, LiveComposedMarketDataProvider)
    assert provider.snapshot_source is recorder.alpaca_fetchers[0]
    assert provider.float_source is recorder.fmp_fetchers[0]
    assert recorder.alpaca_fetchers[0].transport is recorder.transport
    assert recorder.fmp_fetchers[0].transport is recorder.transport
    assert recorder.transport.send_calls == 0


def test_builder_requires_passing_phase_12a_live_gate() -> None:
    failing_gate = LiveProviderGateResult(
        allowed=False,
        failure_reasons=(LiveProviderGateFailure.LIVE_DATA_NOT_ALLOWED,),
    )
    recorder = FactoryRecorder()

    with pytest.raises(LiveProviderBuildError) as exc_info:
        build_live_composed_provider(
            live_config(),
            relative_volume_by_symbol={"XTRM": 12.5},
            transport_factory=recorder.transport_factory,
            alpaca_fetcher_factory=recorder.alpaca_fetcher_factory,
            fmp_fetcher_factory=recorder.fmp_fetcher_factory,
            gate_result=failing_gate,
        )

    assert "Live provider gate failed: LIVE_DATA_NOT_ALLOWED." == str(exc_info.value)
    assert recorder.alpaca_fetchers == []
    assert recorder.fmp_fetchers == []


def test_builder_runs_gate_when_gate_result_is_not_supplied() -> None:
    recorder = FactoryRecorder()

    with pytest.raises(LiveProviderBuildError) as exc_info:
        build_live_composed_provider(
            live_config(allow_live_data=False),
            relative_volume_by_symbol={"XTRM": 12.5},
            transport_factory=recorder.transport_factory,
            alpaca_fetcher_factory=recorder.alpaca_fetcher_factory,
            fmp_fetcher_factory=recorder.fmp_fetcher_factory,
        )

    assert "LIVE_DATA_NOT_ALLOWED" in str(exc_info.value)
    assert recorder.transport.send_calls == 0


def test_builder_fails_when_required_live_config_fields_are_missing() -> None:
    passing_gate = LiveProviderGateResult(allowed=True, failure_reasons=())
    recorder = FactoryRecorder()

    with pytest.raises(LiveProviderBuildError) as exc_info:
        build_live_composed_provider(
            live_config(
                watchlist=(),
                alpaca_api_key=None,
                alpaca_api_secret=None,
                fmp_api_key=None,
            ),
            relative_volume_by_symbol={"XTRM": 12.5},
            transport_factory=recorder.transport_factory,
            alpaca_fetcher_factory=recorder.alpaca_fetcher_factory,
            fmp_fetcher_factory=recorder.fmp_fetcher_factory,
            gate_result=passing_gate,
        )

    message = str(exc_info.value)

    assert "Missing live provider config fields:" in message
    assert "WATCHLIST" in message
    assert "ALPACA_API_KEY" in message
    assert "ALPACA_API_SECRET" in message
    assert "FMP_API_KEY" in message
    assert recorder.transport.send_calls == 0


def test_builder_uses_watchlist_from_config() -> None:
    provider, recorder = build_provider(config=live_config(watchlist=(" xtrm ", "missrv")))

    provider.get_candidates()

    assert provider.watchlist == (" xtrm ", "missrv")
    assert recorder.alpaca_fetchers[0].calls == [["XTRM", "MISSRV"]]
    assert recorder.fmp_fetchers[0].calls == ["XTRM", "MISSRV"]


def test_builder_uses_explicit_relative_volume_and_does_not_fabricate_it() -> None:
    provider, _ = build_provider(
        config=live_config(watchlist=("XTRM", "MISSRV")),
        relative_volume_by_symbol={"XTRM": 12.5},
    )

    results = {result.symbol: result for result in provider.build_results()}

    assert results["XTRM"].succeeded
    assert results["XTRM"].candidate is not None
    assert results["XTRM"].candidate.relative_volume == 12.5
    assert results["MISSRV"].skipped_reason == CandidateSkipReason.MISSING_RELATIVE_VOLUME


def test_builder_requires_explicit_relative_volume_input() -> None:
    recorder = FactoryRecorder()

    with pytest.raises(LiveProviderBuildError) as exc_info:
        build_live_composed_provider(
            live_config(),
            relative_volume_by_symbol=None,
            transport_factory=recorder.transport_factory,
            alpaca_fetcher_factory=recorder.alpaca_fetcher_factory,
            fmp_fetcher_factory=recorder.fmp_fetcher_factory,
        )

    assert str(exc_info.value) == (
        "Explicit relative_volume_by_symbol is required for live provider wiring."
    )
    assert recorder.transport.send_calls == 0


def test_builder_passes_injected_settings_into_sources() -> None:
    provider, recorder = build_provider(config=live_config(alpaca_data_feed="sip"))

    alpaca_fetcher = recorder.alpaca_fetchers[0]
    fmp_fetcher = recorder.fmp_fetchers[0]

    assert provider.snapshot_source is alpaca_fetcher
    assert provider.float_source is fmp_fetcher
    assert alpaca_fetcher.settings.feed == "sip"
    assert alpaca_fetcher.settings.api_key == "placeholder-key"
    assert alpaca_fetcher.settings.api_secret == "placeholder-secret"
    assert fmp_fetcher.settings.api_key == "placeholder-fmp-key"


def test_builder_requires_injected_factories() -> None:
    with pytest.raises(LiveProviderBuildError, match="transport_factory is required"):
        build_live_composed_provider(
            live_config(),
            relative_volume_by_symbol={"XTRM": 12.5},
            transport_factory=None,
            alpaca_fetcher_factory=FakeAlpacaFetcher,
            fmp_fetcher_factory=FakeFMPFetcher,
        )


def test_builder_errors_are_secret_safe() -> None:
    recorder = FactoryRecorder()
    config = live_config(
        allow_live_data=False,
        alpaca_api_key="visible-key-should-not-print",
        alpaca_api_secret="visible-secret-should-not-print",
        fmp_api_key="visible-fmp-should-not-print",
    )

    with pytest.raises(LiveProviderBuildError) as exc_info:
        build_live_composed_provider(
            config,
            relative_volume_by_symbol={"XTRM": 12.5},
            transport_factory=recorder.transport_factory,
            alpaca_fetcher_factory=recorder.alpaca_fetcher_factory,
            fmp_fetcher_factory=recorder.fmp_fetcher_factory,
        )

    message = str(exc_info.value)

    assert "visible-key-should-not-print" not in message
    assert "visible-secret-should-not-print" not in message
    assert "visible-fmp-should-not-print" not in message
    assert "LIVE_DATA_NOT_ALLOWED" in message


def test_provider_returned_by_builder_can_produce_candidates_using_fake_sources() -> None:
    provider, recorder = build_provider()

    candidates = provider.get_candidates()

    assert [candidate.symbol for candidate in candidates] == ["XTRM"]
    assert candidates[0].price == 11.4
    assert candidates[0].float_shares == 1_300_000
    assert candidates[0].relative_volume == 12.5
    assert recorder.transport.send_calls == 0


def test_provider_returned_by_builder_skips_missing_relative_volume() -> None:
    provider, _ = build_provider(relative_volume_by_symbol={})

    assert provider.get_candidates() == []
    assert provider.latest_build_results[0].skipped_reason == (
        CandidateSkipReason.MISSING_RELATIVE_VOLUME
    )


def test_live_provider_builder_has_no_runtime_network_or_trading_behavior() -> None:
    source = inspect.getsource(live_provider_builder)
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

    assert not {"http", "requests", "socket", "urllib", "httpx", "aiohttp", "os"} & imported_modules
    assert "StdlibHttpTransport" not in source
    assert ".send(" not in source
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "load_config" not in source
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()


def test_runtime_provider_factory_remains_live_composed_placeholder() -> None:
    source = inspect.getsource(factory)

    assert "build_live_composed_provider" not in source
    with pytest.raises(ProviderConfigurationError, match="reserved"):
        create_market_data_provider(live_config())


def test_existing_runtime_providers_remain_unchanged() -> None:
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
