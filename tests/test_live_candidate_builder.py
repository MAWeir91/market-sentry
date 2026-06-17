import ast
import inspect

import pytest

from market_sentry.config import AppConfig
from market_sentry.data import live_candidate_builder
from market_sentry.data.alpaca import AlpacaSnapshot
from market_sentry.data.composer import CandidateSkipReason
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.fmp import FMPFloatData
from market_sentry.data.live_candidate_builder import (
    LiveCandidateBuilder,
    normalize_symbols,
)
from market_sentry.data.mock_provider import MockMarketDataProvider
from market_sentry.scanner.engine import ScannerEngine


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
        "date": "2026-06-16",
    }
    values.update(overrides)
    return FMPFloatData(**values)


def builder(
    snapshots: dict[str, AlpacaSnapshot] | None = None,
    floats: dict[str, FMPFloatData | None] | None = None,
) -> tuple[LiveCandidateBuilder, FakeSnapshotSource, FakeFloatSource]:
    snapshot_source = FakeSnapshotSource(
        {"XTRM": snapshot()} if snapshots is None else snapshots
    )
    float_source = FakeFloatSource(
        {"XTRM": float_data()} if floats is None else floats
    )
    return (
        LiveCandidateBuilder(
            snapshot_source=snapshot_source,
            float_source=float_source,
        ),
        snapshot_source,
        float_source,
    )


def result_by_symbol(results):
    return {result.symbol: result for result in results}


def test_builder_normalizes_symbols() -> None:
    assert normalize_symbols([" xtrm ", "", "crvo", "  "]) == ("XTRM", "CRVO")


def test_builder_ignores_empty_symbols_safely() -> None:
    live_builder, snapshot_source, float_source = builder()

    assert live_builder.build_candidates([" ", ""], {"XTRM": 12.5}) == []
    assert snapshot_source.calls == []
    assert float_source.calls == []


def test_builder_combines_fake_sources_and_explicit_relative_volume() -> None:
    live_builder, snapshot_source, float_source = builder()

    results = live_builder.build_candidates([" xtrm "], {"xtrm": 12.5})

    assert snapshot_source.calls == [["XTRM"]]
    assert float_source.calls == ["XTRM"]
    assert len(results) == 1
    result = results[0]
    assert result.succeeded
    assert result.skipped_reason is None
    assert result.candidate is not None
    assert result.candidate.symbol == "XTRM"
    assert result.candidate.price == 11.4
    assert result.candidate.float_shares == 1_300_000
    assert result.candidate.daily_gain_percent == 100.0
    assert result.candidate.relative_volume == 12.5
    assert result.candidate.daily_volume == 6_400_000


def test_builder_reuses_existing_composition_behavior() -> None:
    live_builder, _, _ = builder()

    result = live_builder.build_candidates(["XTRM"], {"XTRM": 12.5})[0]

    assert result.candidate is not None
    scan_result = ScannerEngine().scan([result.candidate])[0]
    assert scan_result.qualified
    assert scan_result.tier is not None


def test_missing_relative_volume_causes_safe_skip() -> None:
    live_builder, _, _ = builder()

    result = live_builder.build_candidates(["XTRM"], {})[0]

    assert not result.succeeded
    assert result.candidate is None
    assert result.skipped_reason == CandidateSkipReason.MISSING_RELATIVE_VOLUME


def test_missing_alpaca_movement_data_causes_safe_skip() -> None:
    live_builder, _, _ = builder(snapshots={}, floats={"XTRM": float_data()})

    result = live_builder.build_candidates(["XTRM"], {"XTRM": 12.5})[0]

    assert not result.succeeded
    assert result.skipped_reason == CandidateSkipReason.MISSING_ALPACA_SNAPSHOT


def test_missing_fmp_float_data_causes_safe_skip() -> None:
    live_builder, _, _ = builder(snapshots={"XTRM": snapshot()}, floats={})

    result = live_builder.build_candidates(["XTRM"], {"XTRM": 12.5})[0]

    assert not result.succeeded
    assert result.skipped_reason == CandidateSkipReason.MISSING_FMP_FLOAT_DATA


def test_invalid_float_data_causes_safe_skip() -> None:
    live_builder, _, _ = builder(floats={"XTRM": float_data(float_shares=0)})

    result = live_builder.build_candidates(["XTRM"], {"XTRM": 12.5})[0]

    assert not result.succeeded
    assert result.skipped_reason == CandidateSkipReason.INVALID_FLOAT


@pytest.mark.parametrize(
    ("bad_snapshot", "expected_reason"),
    [
        (snapshot(price=0), CandidateSkipReason.INVALID_PRICE),
        (snapshot(daily_volume=0), CandidateSkipReason.INVALID_DAILY_VOLUME),
        (snapshot(previous_close=None), CandidateSkipReason.MISSING_DAILY_GAIN),
        (snapshot(previous_close=0), CandidateSkipReason.MISSING_DAILY_GAIN),
    ],
)
def test_invalid_or_missing_movement_fields_cause_safe_skip(
    bad_snapshot: AlpacaSnapshot,
    expected_reason: CandidateSkipReason,
) -> None:
    live_builder, _, _ = builder(snapshots={"XTRM": bad_snapshot})

    result = live_builder.build_candidates(["XTRM"], {"XTRM": 12.5})[0]

    assert not result.succeeded
    assert result.skipped_reason == expected_reason


def test_optional_hod_data_is_carried_through_when_present() -> None:
    live_builder, _, _ = builder(snapshots={"XTRM": snapshot(high_of_day=12.0)})

    result = live_builder.build_candidates(["XTRM"], {"XTRM": 12.5})[0]

    assert result.candidate is not None
    assert result.candidate.high_of_day == 12.0


def test_optional_15_minute_data_is_not_fabricated_when_absent() -> None:
    live_builder, _, _ = builder()

    result = live_builder.build_candidates(["XTRM"], {"XTRM": 12.5})[0]

    assert result.candidate is not None
    assert result.candidate.change_15m_pct is None


def test_skip_build_results_are_inspectable_for_multiple_symbols() -> None:
    live_builder, _, _ = builder(
        snapshots={
            "XTRM": snapshot(),
            "MISSRV": snapshot(symbol="MISSRV"),
            "NOFLOAT": snapshot(symbol="NOFLOAT"),
        },
        floats={
            "XTRM": float_data(),
            "MISSRV": FMPFloatData(symbol="MISSRV", float_shares=2_000_000),
        },
    )

    results = result_by_symbol(
        live_builder.build_candidates(
            ["xtrm", "missrv", "nofloat"],
            {"XTRM": 12.5},
        )
    )

    assert results["XTRM"].succeeded
    assert results["MISSRV"].skipped_reason == CandidateSkipReason.MISSING_RELATIVE_VOLUME
    assert results["NOFLOAT"].skipped_reason == CandidateSkipReason.MISSING_FMP_FLOAT_DATA


def test_get_candidates_returns_only_successfully_built_candidates() -> None:
    live_builder, _, _ = builder(
        snapshots={"XTRM": snapshot(), "NOFLOAT": snapshot(symbol="NOFLOAT")},
        floats={"XTRM": float_data()},
    )

    candidates = live_builder.get_candidates(["XTRM", "NOFLOAT"], {"XTRM": 12.5})

    assert [candidate.symbol for candidate in candidates] == ["XTRM"]


def test_live_candidate_builder_has_no_network_or_trading_behavior() -> None:
    source = inspect.getsource(live_candidate_builder)
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
    assert "websocket" not in source.lower()
    assert "api_key" not in source.lower()
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()


def test_provider_factory_remains_unchanged() -> None:
    assert isinstance(create_market_data_provider(AppConfig(provider="mock")), MockMarketDataProvider)
    assert isinstance(
        create_market_data_provider(AppConfig(provider="fixture")),
        FixtureComposedMarketDataProvider,
    )

    with pytest.raises(ProviderConfigurationError, match="future placeholder"):
        create_market_data_provider(AppConfig(provider="alpaca"))
