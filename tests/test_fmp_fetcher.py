import ast
import inspect
import json

import pytest

from market_sentry.config import AppConfig
from market_sentry.data import fmp_fetcher
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.fmp import FMPFloatData, FMPReferenceSettings
from market_sentry.data.fmp_fetcher import (
    FMPFloatFetchError,
    FMPFloatFetcher,
    build_shares_float_http_request,
    parse_float_http_response,
)
from market_sentry.data.http import (
    FakeHttpTransport,
    HttpResponse,
    HttpStatusError,
    HttpTimeoutError,
    HttpTransportError,
)
from market_sentry.data.mock_provider import MockMarketDataProvider


API_KEY = "test-fmp-key"


def float_payload() -> list[dict]:
    return [
        {
            "symbol": "XTRM",
            "floatShares": 1_300_000,
            "outstandingShares": 6_000_000,
            "date": "2026-06-16",
        }
    ]


def float_response(payload: object | None = None) -> HttpResponse:
    return HttpResponse(
        status_code=200,
        body=json.dumps(float_payload() if payload is None else payload),
        headers={"content-type": "application/json"},
    )


def fetcher_with_transport(
    transport: FakeHttpTransport,
    *,
    settings: FMPReferenceSettings | None = None,
) -> FMPFloatFetcher:
    return FMPFloatFetcher(
        settings=settings or FMPReferenceSettings(api_key=API_KEY),
        transport=transport,
        timeout_seconds=6.5,
    )


def assert_no_secrets(text: str) -> None:
    assert API_KEY not in text


def test_fetcher_builds_http_request_using_injected_fake_transport() -> None:
    transport = FakeHttpTransport([float_response()])
    fetcher = fetcher_with_transport(transport)

    result = fetcher.fetch_float(" xtrm ")

    assert result == FMPFloatData(
        symbol="XTRM",
        float_shares=1_300_000,
        outstanding_shares=6_000_000,
        date="2026-06-16",
    )
    assert len(transport.requests) == 1


def test_shares_float_request_url_params_api_key_and_timeout_are_sent() -> None:
    transport = FakeHttpTransport([float_response()])
    fetcher = fetcher_with_transport(transport)

    fetcher.fetch_float(" xtrm ")

    request = transport.requests[0]
    assert request.method == "GET"
    assert request.url == "https://financialmodelingprep.com/stable/shares-float"
    assert request.params == {
        "symbol": "XTRM",
        "apikey": API_KEY,
    }
    assert request.timeout_seconds == 6.5


def test_request_repr_does_not_expose_api_key() -> None:
    request = build_shares_float_http_request(
        "xtrm",
        FMPReferenceSettings(api_key=API_KEY),
    )

    assert request.params["apikey"] == API_KEY
    assert_no_secrets(repr(request))
    assert "params" not in repr(request)


def test_fetcher_parses_dict_style_float_fixture() -> None:
    transport = FakeHttpTransport(
        [
            float_response(
                {
                    "symbol": "CRVO",
                    "freeFloat": "2500000",
                    "sharesOutstanding": "9000000",
                    "date": "2026-06-16",
                }
            )
        ]
    )
    fetcher = fetcher_with_transport(transport)

    assert fetcher.fetch_float("crvo") == FMPFloatData(
        symbol="CRVO",
        float_shares=2_500_000,
        outstanding_shares=9_000_000,
        date="2026-06-16",
    )


def test_fetcher_parses_nested_data_float_fixture() -> None:
    transport = FakeHttpTransport(
        [
            float_response(
                {
                    "data": [
                        {
                            "symbol": "ATAI",
                            "float": 7_500_000,
                            "outstandingShares": 30_000_000,
                        }
                    ]
                }
            )
        ]
    )
    fetcher = fetcher_with_transport(transport)

    assert fetcher.fetch_float("atai") == FMPFloatData(
        symbol="ATAI",
        float_shares=7_500_000,
        outstanding_shares=30_000_000,
        date=None,
    )


def test_fetcher_handles_missing_symbol_data_safely() -> None:
    transport = FakeHttpTransport([float_response()])
    fetcher = fetcher_with_transport(transport)

    assert fetcher.fetch_float("MISSING") is None


def test_fetcher_handles_missing_float_data_safely() -> None:
    transport = FakeHttpTransport([float_response({"symbol": "XTRM"})])
    fetcher = fetcher_with_transport(transport)

    assert fetcher.fetch_float("XTRM") is None


def test_fetcher_handles_empty_symbol_safely_without_sending_request() -> None:
    transport = FakeHttpTransport([float_response()])
    fetcher = fetcher_with_transport(transport)

    assert fetcher.fetch_float("  ") is None
    assert transport.requests == []


def test_parse_float_http_response_rejects_invalid_json_safely() -> None:
    response = HttpResponse(status_code=200, body="{not-json")

    with pytest.raises(FMPFloatFetchError) as exc_info:
        parse_float_http_response(response, "XTRM")

    assert "not valid JSON" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_parse_float_http_response_rejects_non_object_or_array_json_safely() -> None:
    response = HttpResponse(status_code=200, body='"not-an-object"')

    with pytest.raises(FMPFloatFetchError) as exc_info:
        parse_float_http_response(response, "XTRM")

    assert "JSON object or array" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_fetcher_propagates_timeout_errors_safely() -> None:
    transport = FakeHttpTransport([HttpTimeoutError("HTTP request timed out.")])
    fetcher = fetcher_with_transport(transport)

    with pytest.raises(HttpTimeoutError) as exc_info:
        fetcher.fetch_float("XTRM")

    assert "timed out" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_fetcher_propagates_status_errors_safely() -> None:
    transport = FakeHttpTransport([HttpResponse(status_code=429, body="rate limited")])
    fetcher = fetcher_with_transport(transport)

    with pytest.raises(HttpStatusError) as exc_info:
        fetcher.fetch_float("XTRM")

    assert "429" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_fetcher_propagates_generic_transport_errors_safely() -> None:
    transport = FakeHttpTransport([HttpTransportError("HTTP transport unavailable.")])
    fetcher = fetcher_with_transport(transport)

    with pytest.raises(HttpTransportError) as exc_info:
        fetcher.fetch_float("XTRM")

    assert "unavailable" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_fmp_fetcher_has_no_external_http_or_trading_behavior() -> None:
    source = inspect.getsource(fmp_fetcher)
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
