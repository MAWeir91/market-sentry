import ast
import inspect
import json
from types import MappingProxyType

import pytest

from market_sentry.data import alpaca_historical_bars_fetcher
from market_sentry.data.alpaca import AlpacaMarketDataSettings
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsFetchError,
    AlpacaHistoricalBarsFetcher,
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
    build_historical_bars_http_request,
    parse_historical_bars_http_response,
)
from market_sentry.data.http import (
    FakeHttpTransport,
    HttpResponse,
    HttpStatusError,
    HttpTimeoutError,
    HttpTransportError,
)


API_KEY = "test-alpaca-key"
API_SECRET = "test-alpaca-secret"


def query(**overrides) -> AlpacaHistoricalBarsQuery:
    values = {
        "timeframe": "1Min",
        "start": "2026-01-02T14:30:00Z",
        "end": "2026-01-02T15:00:00Z",
    }
    values.update(overrides)
    return AlpacaHistoricalBarsQuery(**values)


def bars_payload(*, next_page_token=None) -> dict:
    return {
        "bars": {
            "XTRM": [
                {
                    "t": "2026-01-02T14:31:00Z",
                    "o": 10.0,
                    "h": 10.4,
                    "l": 9.9,
                    "c": 10.2,
                    "v": "12345",
                    "n": 77,
                    "vw": 10.12,
                },
                {
                    "t": "2026-01-02T14:32:00Z",
                    "o": 10.2,
                    "h": 10.8,
                    "l": 10.1,
                    "c": 10.7,
                    "v": 23456,
                    "n": 88,
                    "vw": 10.55,
                },
            ],
            "CRVO": [
                {
                    "t": "2026-01-02T14:31:00Z",
                    "o": 4.0,
                    "h": 4.2,
                    "l": 3.9,
                    "c": 4.1,
                    "v": 9000,
                }
            ],
            "EXTRA": [{"t": "ignored", "v": 1}],
        },
        "next_page_token": next_page_token,
    }


def response(payload: dict) -> HttpResponse:
    return HttpResponse(status_code=200, body=json.dumps(payload))


def fetcher_with_transport(transport: FakeHttpTransport) -> AlpacaHistoricalBarsFetcher:
    return AlpacaHistoricalBarsFetcher(
        settings=AlpacaMarketDataSettings(api_key=API_KEY, api_secret=API_SECRET),
        transport=transport,
        timeout_seconds=7.5,
    )


def assert_no_secrets(text: str) -> None:
    assert API_KEY not in text
    assert API_SECRET not in text


def test_query_accepts_valid_values_and_trims_shape_strings() -> None:
    item = AlpacaHistoricalBarsQuery(
        timeframe=" 1Min ",
        start=" 2026-01-02T14:30:00Z ",
        end=" 2026-01-02T15:00:00Z ",
        limit=500,
        page_token=" token-1 ",
        sort="desc",
    )

    assert item.timeframe == "1Min"
    assert item.start == "2026-01-02T14:30:00Z"
    assert item.end == "2026-01-02T15:00:00Z"
    assert item.limit == 500
    assert item.page_token == "token-1"
    assert item.sort == "desc"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timeframe", ""),
        ("timeframe", "   "),
        ("timeframe", 123),
        ("start", ""),
        ("start", "   "),
        ("start", None),
        ("end", ""),
        ("end", "   "),
        ("end", object()),
    ],
)
def test_query_rejects_invalid_timeframe_start_and_end(field, value) -> None:
    with pytest.raises(AlpacaHistoricalBarsFetchError):
        query(**{field: value})


@pytest.mark.parametrize("limit", [True, False, 0, -1, 10_001, 1.5, "100"])
def test_query_rejects_invalid_limits(limit) -> None:
    with pytest.raises(AlpacaHistoricalBarsFetchError):
        query(limit=limit)


@pytest.mark.parametrize("sort", ["", "ASC", "ascending", " desc ", None])
def test_query_rejects_invalid_sort(sort) -> None:
    with pytest.raises(AlpacaHistoricalBarsFetchError):
        query(sort=sort)


@pytest.mark.parametrize("page_token", ["", "   ", 123, False])
def test_query_rejects_invalid_page_token(page_token) -> None:
    with pytest.raises(AlpacaHistoricalBarsFetchError):
        query(page_token=page_token)


def test_request_construction_uses_get_url_params_feed_headers_and_timeout() -> None:
    request = build_historical_bars_http_request(
        [" xtrm ", "", "crvo"],
        AlpacaMarketDataSettings(api_key=API_KEY, api_secret=API_SECRET, feed="sip"),
        query(limit=250, page_token="next-token", sort="desc"),
        timeout_seconds=7.5,
    )

    assert request.method == "GET"
    assert request.url == "https://data.alpaca.markets/v2/stocks/bars"
    assert request.params == {
        "symbols": "XTRM,CRVO",
        "feed": "sip",
        "timeframe": "1Min",
        "start": "2026-01-02T14:30:00Z",
        "end": "2026-01-02T15:00:00Z",
        "limit": "250",
        "sort": "desc",
        "page_token": "next-token",
    }
    assert request.headers == {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": API_SECRET,
    }
    assert request.timeout_seconds == 7.5
    assert_no_secrets(repr(request))


def test_request_uses_feed_fallback_and_omits_absent_page_token() -> None:
    request = build_historical_bars_http_request(
        ["xtrm"],
        AlpacaMarketDataSettings(feed=""),
        query(),
    )

    assert request.params["feed"] == "iex"
    assert "page_token" not in request.params


def test_parser_returns_valid_single_symbol_page_with_immutable_bars() -> None:
    page = parse_historical_bars_http_response(response(bars_payload()), ["xtrm"])

    assert isinstance(page, AlpacaHistoricalBarsPage)
    assert page.requested_symbols == ("XTRM",)
    assert isinstance(page.bars_by_symbol, MappingProxyType)
    assert len(page.bars_by_symbol["XTRM"]) == 2
    assert isinstance(page.bars_by_symbol["XTRM"][0], MappingProxyType)
    assert page.bars_by_symbol["XTRM"][0]["t"] == "2026-01-02T14:31:00Z"
    assert page.bars_by_symbol["XTRM"][0]["v"] == "12345"
    assert page.next_page_token is None

    with pytest.raises(TypeError):
        page.bars_by_symbol["NEW"] = ()  # type: ignore[index]
    with pytest.raises(TypeError):
        page.bars_by_symbol["XTRM"][0]["v"] = 999  # type: ignore[index]


def test_parser_returns_multi_symbol_page_preserves_order_and_ignores_extra() -> None:
    page = parse_historical_bars_http_response(
        response(bars_payload(next_page_token="token-2")),
        ["crvo", "xtrm"],
    )

    assert page.requested_symbols == ("CRVO", "XTRM")
    assert tuple(page.bars_by_symbol) == ("CRVO", "XTRM")
    assert [bar["t"] for bar in page.bars_by_symbol["XTRM"]] == [
        "2026-01-02T14:31:00Z",
        "2026-01-02T14:32:00Z",
    ]
    assert "EXTRA" not in page.bars_by_symbol
    assert page.next_page_token == "token-2"


def test_parser_preserves_original_nonblank_page_token() -> None:
    raw_token = " token-with-spaces "

    page = parse_historical_bars_http_response(
        HttpResponse(
            status_code=200,
            headers={},
            body='{"bars": {}, "next_page_token": " token-with-spaces "}',
        ),
        ["ABC"],
    )

    assert page.next_page_token == raw_token


def test_parser_represents_absent_requested_symbol_as_empty_tuple() -> None:
    page = parse_historical_bars_http_response(response(bars_payload()), ["missing"])

    assert page.requested_symbols == ("MISSING",)
    assert page.bars_by_symbol["MISSING"] == ()


@pytest.mark.parametrize(
    "body",
    [
        "{not-json",
        "[]",
    ],
)
def test_parser_rejects_invalid_json_or_payload(body) -> None:
    with pytest.raises(AlpacaHistoricalBarsFetchError):
        parse_historical_bars_http_response(HttpResponse(status_code=200, body=body), ["XTRM"])


@pytest.mark.parametrize(
    "payload",
    [
        {"bars": []},
        {"bars": {"XTRM": {"t": "not-a-list"}}},
        {"bars": {"XTRM": ["not-an-object"]}},
        {"bars": {"XTRM": []}, "next_page_token": ""},
        {"bars": {"XTRM": []}, "next_page_token": "   "},
        {"bars": {"XTRM": []}, "next_page_token": 123},
    ],
)
def test_parser_rejects_invalid_bars_or_page_token(payload) -> None:
    with pytest.raises(AlpacaHistoricalBarsFetchError):
        parse_historical_bars_http_response(response(payload), ["XTRM"])


def test_fetcher_uses_injected_transport_and_sends_once_for_nonempty_symbols() -> None:
    transport = FakeHttpTransport([response(bars_payload(next_page_token="next"))])
    fetcher = fetcher_with_transport(transport)

    page = fetcher.fetch_bars([" xtrm ", "", "crvo"], query())

    assert page.requested_symbols == ("XTRM", "CRVO")
    assert page.next_page_token == "next"
    assert len(transport.requests) == 1
    assert transport.requests[0].params["symbols"] == "XTRM,CRVO"


def test_fetcher_does_not_send_for_empty_normalized_symbols() -> None:
    transport = FakeHttpTransport([response(bars_payload())])
    fetcher = fetcher_with_transport(transport)

    page = fetcher.fetch_bars(["", "   "], query())

    assert page.requested_symbols == ()
    assert page.bars_by_symbol == {}
    assert page.next_page_token is None
    assert transport.requests == []


def test_fetcher_surfaces_token_without_automatic_pagination() -> None:
    transport = FakeHttpTransport(
        [
            response(bars_payload(next_page_token="next")),
            response(bars_payload(next_page_token=None)),
        ]
    )
    fetcher = fetcher_with_transport(transport)

    page = fetcher.fetch_bars(["XTRM"], query())

    assert page.next_page_token == "next"
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "transport_error",
    [
        HttpTimeoutError("HTTP request timed out."),
        HttpTransportError("HTTP transport unavailable."),
    ],
)
def test_fetcher_propagates_transport_errors(transport_error) -> None:
    transport = FakeHttpTransport([transport_error])
    fetcher = fetcher_with_transport(transport)

    with pytest.raises(type(transport_error)) as exc_info:
        fetcher.fetch_bars(["XTRM"], query())

    assert_no_secrets(str(exc_info.value))


def test_fetcher_propagates_status_errors() -> None:
    transport = FakeHttpTransport([HttpResponse(status_code=429, body="rate limited")])
    fetcher = fetcher_with_transport(transport)

    with pytest.raises(HttpStatusError) as exc_info:
        fetcher.fetch_bars(["XTRM"], query())

    assert "429" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_fetcher_module_has_no_live_http_or_runtime_registration_hooks() -> None:
    source = inspect.getsource(alpaca_historical_bars_fetcher)
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
    forbidden_terms = [
        "StdlibHttpTransport",
        "MARKET_SENTRY_PROVIDER",
        "create_market_data_provider",
        "time_of_day_rvol",
        "intraday_bucket_adapter",
        "intraday_rvol_harness",
        "intraday_rvol_fixture_provider",
        "intraday_rvol_candidate_composition_harness",
        "LiveCandidateBuilder",
        "StockCandidate",
        "scanner",
        "alert",
        "place_order",
        "execute_order",
        "buy",
        "sell",
        "enter",
        "exit",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
