import ast
import inspect

import pytest

from market_sentry.config import AppConfig
from market_sentry.data import alpaca
from market_sentry.data.alpaca import (
    AlpacaMarketDataSettings,
    AlpacaSnapshot,
    build_auth_headers,
    build_bars_request,
    build_snapshot_request,
    calculate_15m_change_from_bars,
    calculate_daily_gain_from_snapshot,
    parse_snapshot_response,
)
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)


def snapshot_fixture() -> dict:
    return {
        "snapshots": {
            "XTRM": {
                "latestTrade": {"p": 11.4},
                "dailyBar": {"v": 6_400_000, "h": 11.55, "c": 11.35},
                "prevDailyBar": {"c": 5.7},
            }
        }
    }


def test_alpaca_auth_headers_are_built_without_printing_secrets() -> None:
    settings = AlpacaMarketDataSettings(
        api_key="test-key",
        api_secret="test-secret",
    )

    headers = build_auth_headers(settings)

    assert headers == {
        "APCA-API-KEY-ID": "test-key",
        "APCA-API-SECRET-KEY": "test-secret",
    }
    assert "test-key" not in repr(settings)
    assert "test-secret" not in repr(settings)


def test_alpaca_request_repr_does_not_expose_secret_headers() -> None:
    settings = AlpacaMarketDataSettings(
        api_key="test-key",
        api_secret="test-secret",
    )

    request = build_snapshot_request(["XTRM"], settings)

    assert request.headers == {
        "APCA-API-KEY-ID": "test-key",
        "APCA-API-SECRET-KEY": "test-secret",
    }
    assert "test-key" not in repr(request)
    assert "test-secret" not in repr(request)


def test_snapshot_request_path_and_params_are_built_for_watchlist() -> None:
    request = build_snapshot_request(
        [" xtrm ", "CRVO", "", "atai"],
        AlpacaMarketDataSettings(),
    )

    assert request.path == "/v2/stocks/snapshots"
    assert request.params["symbols"] == "XTRM,CRVO,ATAI"
    assert request.params["feed"] == "iex"


def test_bars_request_path_and_params_are_built_for_15m_context() -> None:
    request = build_bars_request(
        ("xtrm", "crvo"),
        AlpacaMarketDataSettings(feed="sip"),
        timeframe="1Min",
        limit=15,
    )

    assert request.path == "/v2/stocks/bars"
    assert request.params == {
        "symbols": "XTRM,CRVO",
        "feed": "sip",
        "timeframe": "1Min",
        "limit": 15,
    }


def test_empty_watchlist_is_handled_safely() -> None:
    request = build_snapshot_request([], AlpacaMarketDataSettings())

    assert request.params["symbols"] == ""
    assert request.params["feed"] == "iex"


def test_snapshot_fixture_parses_market_data_fields() -> None:
    snapshot = parse_snapshot_response(snapshot_fixture(), "xtrm")

    assert snapshot == AlpacaSnapshot(
        symbol="XTRM",
        price=11.4,
        daily_volume=6_400_000,
        high_of_day=11.55,
        previous_close=5.7,
    )


def test_snapshot_parser_handles_missing_symbol_safely() -> None:
    assert parse_snapshot_response(snapshot_fixture(), "MISSING") is None


def test_snapshot_parser_handles_missing_nested_fields_safely() -> None:
    snapshot = parse_snapshot_response({"snapshots": {"XTRM": {}}}, "XTRM")

    assert snapshot == AlpacaSnapshot(
        symbol="XTRM",
        price=None,
        daily_volume=None,
        high_of_day=None,
        previous_close=None,
    )


def test_daily_gain_calculation_uses_whole_number_percent() -> None:
    snapshot = parse_snapshot_response(snapshot_fixture(), "XTRM")
    assert snapshot is not None

    assert calculate_daily_gain_from_snapshot(snapshot) == 100.0


def test_daily_gain_handles_missing_or_zero_previous_close_safely() -> None:
    missing_previous = AlpacaSnapshot(
        symbol="XTRM",
        price=11.4,
        daily_volume=6_400_000,
        high_of_day=11.55,
        previous_close=None,
    )
    zero_previous = AlpacaSnapshot(
        symbol="XTRM",
        price=11.4,
        daily_volume=6_400_000,
        high_of_day=11.55,
        previous_close=0,
    )

    assert calculate_daily_gain_from_snapshot(missing_previous) is None
    assert calculate_daily_gain_from_snapshot(zero_previous) is None


def test_15m_change_calculation_uses_first_and_last_bar_close() -> None:
    bars = [{"c": 10.0}, {"c": 10.4}, {"c": 10.82}]

    assert calculate_15m_change_from_bars(bars) == 8.2


def test_15m_change_handles_insufficient_or_invalid_bars_safely() -> None:
    assert calculate_15m_change_from_bars([]) is None
    assert calculate_15m_change_from_bars([{"c": 10.0}]) is None
    assert calculate_15m_change_from_bars([{"c": 0}, {"c": 10.0}]) is None
    assert calculate_15m_change_from_bars([{"c": "bad"}, {"c": 10.0}]) is None


def test_runtime_provider_factory_still_keeps_alpaca_as_placeholder() -> None:
    with pytest.raises(ProviderConfigurationError, match="future placeholder"):
        create_market_data_provider(AppConfig(provider="alpaca"))


def test_alpaca_skeleton_has_no_network_dependencies() -> None:
    source = inspect.getsource(alpaca)
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
    assert "order" not in source.lower()
    assert "trade execution" not in source.lower()
