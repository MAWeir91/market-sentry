import ast
import inspect

import pytest

from market_sentry.config import AppConfig
from market_sentry.data import factory, live_composed_provider
from market_sentry.data.alpaca import AlpacaSnapshot
from market_sentry.data.composer import CandidateSkipReason
from market_sentry.data.composed_fixture_provider import OfflineComposedFixtureProvider
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.fmp import FMPFloatData
from market_sentry.data.live_candidate_builder import LiveCandidateBuildResult
from market_sentry.data.live_composed_provider import LiveComposedMarketDataProvider
from market_sentry.data.mock_provider import MockMarketDataProvider
from market_sentry.scanner.models import StockCandidate


class FakeSnapshotSource:
    def __init__(self, snapshots: dict[str, AlpacaSnapshot]) -> None:
        self.snapshots = snapshots
        self.calls: list[list[str] | tuple[str, ...]] = []

    def fetch_snapshots(self, symbols: list[str] | tuple[str, ...]) -> dict[str, AlpacaSnapshot]:
        self.calls.append(symbols)
        return {
            symbol: self.snapshots[symbol]
            for symbol in symbols
            if symbol in self.snapshots
        }


class FakeFloatSource:
    def __init__(self, floats: dict[str, FMPFloatData | None]) -> None:
        self.floats = floats
        self.calls: list[str | None] = []

    def fetch_float(self, symbol: str | None) -> FMPFloatData | None:
        self.calls.append(symbol)
        return self.floats.get(symbol or "")


class RecordingBuilder:
    def __init__(self, results: list[LiveCandidateBuildResult]) -> None:
        self.results = results
        self.calls: list[tuple[list[str], dict[str, float | int | str]]] = []

    def build_candidates(
        self,
        symbols,
        relative_volume_by_symbol,
    ) -> list[LiveCandidateBuildResult]:
        self.calls.append((list(symbols), dict(relative_volume_by_symbol)))
        return self.results


def snapshot(**overrides: object) -> AlpacaSnapshot:
    values = {
        "symbol": "XTRM",
        "price": 11.4,
        "daily_volume": 6_400_000,
        "high_of_day": 11.55,
        "previous_close": 5.7,
    }
    values.update(overrides)
    return AlpacaSnapshot(**values)


def float_data(**overrides: object) -> FMPFloatData:
    values = {
        "symbol": "XTRM",
        "float_shares": 1_300_000,
        "outstanding_shares": 6_000_000,
        "date": "2026-06-17",
    }
    values.update(overrides)
    return FMPFloatData(**values)


def provider(
    *,
    watchlist: list[str] | tuple[str, ...] = ("XTRM",),
    snapshots: dict[str, AlpacaSnapshot] | None = None,
    floats: dict[str, FMPFloatData | None] | None = None,
    relative_volume_by_symbol: dict[str, float | int | str] | None = None,
    builder=None,
) -> tuple[LiveComposedMarketDataProvider, FakeSnapshotSource, FakeFloatSource]:
    snapshot_source = FakeSnapshotSource(
        {"XTRM": snapshot()} if snapshots is None else snapshots
    )
    float_source = FakeFloatSource(
        {"XTRM": float_data()} if floats is None else floats
    )
    return (
        LiveComposedMarketDataProvider(
            watchlist=watchlist,
            snapshot_source=snapshot_source,
            float_source=float_source,
            relative_volume_by_symbol=(
                {"XTRM": 12.5}
                if relative_volume_by_symbol is None
                else relative_volume_by_symbol
            ),
            builder=builder,
        ),
        snapshot_source,
        float_source,
    )


def result_by_symbol(results: list[LiveCandidateBuildResult]):
    return {result.symbol: result for result in results}


def test_provider_can_be_instantiated_with_fake_injected_components() -> None:
    live_provider, snapshot_source, float_source = provider()

    assert live_provider.watchlist == ("XTRM",)
    assert live_provider.snapshot_source is snapshot_source
    assert live_provider.float_source is float_source


def test_provider_returns_only_successful_stock_candidates() -> None:
    live_provider, _, _ = provider(
        watchlist=("XTRM", "MISSRV", "NOFLOAT"),
        snapshots={
            "XTRM": snapshot(),
            "MISSRV": snapshot(symbol="MISSRV"),
            "NOFLOAT": snapshot(symbol="NOFLOAT"),
        },
        floats={
            "XTRM": float_data(),
            "MISSRV": FMPFloatData(symbol="MISSRV", float_shares=2_000_000),
        },
        relative_volume_by_symbol={"XTRM": 12.5},
    )

    candidates = live_provider.get_candidates()

    assert all(isinstance(candidate, StockCandidate) for candidate in candidates)
    assert [candidate.symbol for candidate in candidates] == ["XTRM"]
    assert len(live_provider.latest_build_results) == 3


def test_provider_uses_injected_builder_path() -> None:
    candidate = StockCandidate(
        symbol="XTRM",
        price=11.4,
        float_shares=1_300_000,
        daily_gain_percent=100.0,
        relative_volume=12.5,
        daily_volume=6_400_000,
    )
    recording_builder = RecordingBuilder(
        [LiveCandidateBuildResult("XTRM", candidate, None)]
    )
    live_provider, _, _ = provider(
        watchlist=(" xtrm ",),
        relative_volume_by_symbol={"xtrm": 12.5},
        builder=recording_builder,
    )

    assert live_provider.get_candidates() == [candidate]
    assert recording_builder.calls == [([" xtrm "], {"xtrm": 12.5})]
    assert live_provider.latest_build_results == tuple(recording_builder.results)


def test_provider_requires_explicit_relative_volume() -> None:
    live_provider, _, _ = provider(relative_volume_by_symbol={})

    results = live_provider.build_results()

    assert results[0].skipped_reason == CandidateSkipReason.MISSING_RELATIVE_VOLUME
    assert live_provider.get_candidates() == []


def test_missing_alpaca_movement_data_is_skipped() -> None:
    live_provider, _, _ = provider(
        snapshots={},
        floats={"XTRM": float_data()},
        relative_volume_by_symbol={"XTRM": 12.5},
    )

    results = live_provider.build_results()

    assert results[0].skipped_reason == CandidateSkipReason.MISSING_ALPACA_SNAPSHOT
    assert live_provider.get_candidates() == []


def test_missing_fmp_float_data_is_skipped() -> None:
    live_provider, _, _ = provider(
        snapshots={"XTRM": snapshot()},
        floats={},
        relative_volume_by_symbol={"XTRM": 12.5},
    )

    results = live_provider.build_results()

    assert results[0].skipped_reason == CandidateSkipReason.MISSING_FMP_FLOAT_DATA
    assert live_provider.get_candidates() == []


def test_watchlist_symbols_are_handled_safely() -> None:
    live_provider, snapshot_source, float_source = provider(
        watchlist=[" xtrm ", "", " nofloat "],
        snapshots={"XTRM": snapshot(), "NOFLOAT": snapshot(symbol="NOFLOAT")},
        floats={"XTRM": float_data()},
        relative_volume_by_symbol={"xtrm": 12.5, "nofloat": 4.0},
    )

    results = result_by_symbol(live_provider.build_results())

    assert snapshot_source.calls == [["XTRM", "NOFLOAT"]]
    assert float_source.calls == ["XTRM", "NOFLOAT"]
    assert results["XTRM"].succeeded
    assert results["NOFLOAT"].skipped_reason == CandidateSkipReason.MISSING_FMP_FLOAT_DATA


def test_inspectable_build_results_are_exposed_after_candidate_request() -> None:
    live_provider, _, _ = provider()

    assert live_provider.latest_build_results == ()

    candidates = live_provider.get_candidates()

    assert [candidate.symbol for candidate in candidates] == ["XTRM"]
    assert len(live_provider.latest_build_results) == 1
    assert live_provider.latest_build_results[0].succeeded


def test_live_composed_provider_has_no_network_or_trading_behavior() -> None:
    source = inspect.getsource(live_composed_provider)
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
    assert "StdlibHttpTransport" not in source
    assert "AlpacaSnapshotFetcher" not in source
    assert "FMPFloatFetcher" not in source
    assert ".send(" not in source
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "load_config" not in source
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()


def test_provider_factory_requires_rvol_manifest_before_live_composed_activation() -> None:
    source = inspect.getsource(factory)

    assert ".send(" not in source
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
