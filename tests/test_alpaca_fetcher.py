import ast
import inspect
import json

import pytest

from market_sentry.config import AppConfig
from market_sentry.data import alpaca_fetcher
from market_sentry.data.alpaca import AlpacaMarketDataSettings, AlpacaSnapshot
from market_sentry.data.alpaca_fetcher import (
    AlpacaSnapshotFetchError,
    AlpacaSnapshotFetcher,
    build_snapshot_http_request,
    parse_snapshot_http_response,
)
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.http import (
    FakeHttpTransport,
    HttpResponse,
    HttpStatusError,
    HttpTimeoutError,
    HttpTransportError,
)
from market_sentry.data.mock_provider import MockMarketDataProvider


API_KEY = "test-alpaca-key"
API_SECRET = "test-alpaca-secret"


def snapshot_payload() -> dict:
    return {
        "snapshots": {
            "XTRM": {
                "latestTrade": {"p": 11.4},
                "dailyBar": {"v": 6_400_000, "h": 11.55, "c": 11.35},
                "prevDailyBar": {"c": 5.7},
            },
            "MISSFIELDS": {},
        }
    }


def snapshot_response() -> HttpResponse:
    return HttpResponse(
        status_code=200,
        body=json.dumps(snapshot_payload()),
        headers={"content-type": "application/json"},
    )


def fetcher_with_transport(
    transport: FakeHttpTransport,
    *,
    settings: AlpacaMarketDataSettings | None = None,
) -> AlpacaSnapshotFetcher:
    return AlpacaSnapshotFetcher(
        settings=settings
        or AlpacaMarketDataSettings(api_key=API_KEY, api_secret=API_SECRET),
        transport=transport,
        timeout_seconds=7.5,
    )


def assert_no_secrets(text: str) -> None:
    assert API_KEY not in text
    assert API_SECRET not in text


def test_fetcher_builds_http_request_using_injected_fake_transport() -> None:
    transport = FakeHttpTransport([snapshot_response()])
    fetcher = fetcher_with_transport(transport)

    snapshots = fetcher.fetch_snapshots([" xtrm ", "", "missing"])

    assert snapshots["XTRM"] == AlpacaSnapshot(
        symbol="XTRM",
        price=11.4,
        daily_volume=6_400_000,
        high_of_day=11.55,
        previous_close=5.7,
    )
    assert "MISSING" not in snapshots
    assert len(transport.requests) == 1


def test_snapshot_request_url_params_feed_headers_and_timeout_are_sent() -> None:
    transport = FakeHttpTransport([snapshot_response()])
    fetcher = fetcher_with_transport(transport)

    fetcher.fetch_snapshots([" xtrm ", "crvo", "", "atai"])

    request = transport.requests[0]
    assert request.method == "GET"
    assert request.url == "https://data.alpaca.markets/v2/stocks/snapshots"
    assert request.params == {
        "symbols": "XTRM,CRVO,ATAI",
        "feed": "iex",
    }
    assert request.headers == {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET,
    }
    assert request.timeout_seconds == 7.5


def test_snapshot_request_uses_configured_feed() -> None:
    request = build_snapshot_http_request(
        ["xtrm"],
        AlpacaMarketDataSettings(feed="sip"),
    )

    assert request.params["feed"] == "sip"


def test_snapshot_request_repr_does_not_expose_key_or_secret() -> None:
    request = build_snapshot_http_request(
        ["xtrm"],
        AlpacaMarketDataSettings(api_key=API_KEY, api_secret=API_SECRET),
    )

    assert request.headers["APCA-API-KEY-ID"] == API_KEY
    assert request.headers["APCA-API-SECRET-KEY"] == API_SECRET
    assert_no_secrets(repr(request))


def test_fetcher_parses_missing_nested_fields_without_fabricating_data() -> None:
    transport = FakeHttpTransport([snapshot_response()])
    fetcher = fetcher_with_transport(transport)

    snapshots = fetcher.fetch_snapshots(["MISSFIELDS"])

    assert snapshots["MISSFIELDS"] == AlpacaSnapshot(
        symbol="MISSFIELDS",
        price=None,
        daily_volume=None,
        high_of_day=None,
        previous_close=None,
    )


def test_fetcher_handles_empty_symbol_list_safely_without_sending_request() -> None:
    transport = FakeHttpTransport([snapshot_response()])
    fetcher = fetcher_with_transport(transport)

    assert fetcher.fetch_snapshots([" ", ""]) == {}
    assert transport.requests == []


def test_parse_snapshot_http_response_rejects_invalid_json_safely() -> None:
    response = HttpResponse(status_code=200, body="{not-json")

    with pytest.raises(AlpacaSnapshotFetchError) as exc_info:
        parse_snapshot_http_response(response, ["XTRM"])

    assert "not valid JSON" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_parse_snapshot_http_response_rejects_non_object_json_safely() -> None:
    response = HttpResponse(status_code=200, body="[]")

    with pytest.raises(AlpacaSnapshotFetchError) as exc_info:
        parse_snapshot_http_response(response, ["XTRM"])

    assert "JSON object" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_fetcher_propagates_timeout_errors_safely() -> None:
    transport = FakeHttpTransport([HttpTimeoutError("HTTP request timed out.")])
    fetcher = fetcher_with_transport(transport)

    with pytest.raises(HttpTimeoutError) as exc_info:
        fetcher.fetch_snapshots(["XTRM"])

    assert "timed out" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_fetcher_propagates_status_errors_safely() -> None:
    transport = FakeHttpTransport([HttpResponse(status_code=429, body="rate limited")])
    fetcher = fetcher_with_transport(transport)

    with pytest.raises(HttpStatusError) as exc_info:
        fetcher.fetch_snapshots(["XTRM"])

    assert "429" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_fetcher_propagates_generic_transport_errors_safely() -> None:
    transport = FakeHttpTransport([HttpTransportError("HTTP transport unavailable.")])
    fetcher = fetcher_with_transport(transport)

    with pytest.raises(HttpTransportError) as exc_info:
        fetcher.fetch_snapshots(["XTRM"])

    assert "unavailable" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_fetcher_has_no_external_http_or_trading_behavior() -> None:
    source = inspect.getsource(alpaca_fetcher)
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
    assert "StockCandidate" not in source
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()


def test_runtime_provider_factory_remains_unchanged() -> None:
    assert isinstance(create_market_data_provider(AppConfig(provider="mock")), MockMarketDataProvider)
    assert isinstance(
        create_market_data_provider(AppConfig(provider="fixture")),
        FixtureComposedMarketDataProvider,
    )

    with pytest.raises(ProviderConfigurationError, match="future placeholder"):
        create_market_data_provider(AppConfig(provider="alpaca"))
