import ast
import inspect

import pytest

from market_sentry.config import AppConfig
from market_sentry.data import http
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.http import (
    FakeHttpTransport,
    HttpRequest,
    HttpResponse,
    HttpStatusError,
    HttpTimeoutError,
    HttpTransportError,
    redact_sensitive_values,
)
from market_sentry.data.mock_provider import MockMarketDataProvider


SECRET_VALUES = {
    "APCA-API-KEY-ID": "alpaca-key-secret",
    "APCA-API-SECRET-KEY": "alpaca-secret-secret",
    "apikey": "fmp-api-key-secret",
    "api_key": "generic-api-key-secret",
    "apiSecret": "generic-api-secret",
    "authorization": "Bearer secret-token",
}


def secret_request() -> HttpRequest:
    return HttpRequest(
        method="GET",
        url="https://example.test/data",
        params={
            "symbol": "XTRM",
            "apikey": SECRET_VALUES["apikey"],
            "api_key": SECRET_VALUES["api_key"],
            "apiSecret": SECRET_VALUES["apiSecret"],
        },
        headers={
            "APCA-API-KEY-ID": SECRET_VALUES["APCA-API-KEY-ID"],
            "APCA-API-SECRET-KEY": SECRET_VALUES["APCA-API-SECRET-KEY"],
            "authorization": SECRET_VALUES["authorization"],
        },
        timeout_seconds=3.0,
    )


def assert_no_secret_values(text: str) -> None:
    for value in SECRET_VALUES.values():
        assert value not in text


def test_http_request_repr_does_not_expose_headers_or_params() -> None:
    request = secret_request()

    request_repr = repr(request)

    assert "headers" not in request_repr
    assert "params" not in request_repr
    assert_no_secret_values(request_repr)


def test_headers_and_params_remain_accessible() -> None:
    request = secret_request()

    assert request.headers["APCA-API-KEY-ID"] == SECRET_VALUES["APCA-API-KEY-ID"]
    assert request.headers["authorization"] == SECRET_VALUES["authorization"]
    assert request.params["apikey"] == SECRET_VALUES["apikey"]
    assert request.params["api_key"] == SECRET_VALUES["api_key"]


def test_redact_sensitive_values_redacts_known_sensitive_names() -> None:
    redacted = redact_sensitive_values(
        {
            "APCA-API-KEY-ID": SECRET_VALUES["APCA-API-KEY-ID"],
            "APCA-API-SECRET-KEY": SECRET_VALUES["APCA-API-SECRET-KEY"],
            "apikey": SECRET_VALUES["apikey"],
            "api_key": SECRET_VALUES["api_key"],
            "apiSecret": SECRET_VALUES["apiSecret"],
            "authorization": SECRET_VALUES["authorization"],
            "symbol": "XTRM",
        }
    )

    assert redacted == {
        "APCA-API-KEY-ID": "[REDACTED]",
        "APCA-API-SECRET-KEY": "[REDACTED]",
        "apikey": "[REDACTED]",
        "api_key": "[REDACTED]",
        "apiSecret": "[REDACTED]",
        "authorization": "[REDACTED]",
        "symbol": "XTRM",
    }


def test_fake_transport_returns_fixture_response_and_records_request() -> None:
    response = HttpResponse(
        status_code=200,
        body='{"symbol":"XTRM"}',
        headers={"content-type": "application/json"},
    )
    transport = FakeHttpTransport([response])
    request = secret_request()

    result = transport.send(request)

    assert result == response
    assert transport.requests == [request]


def test_fake_transport_can_simulate_status_errors_without_secrets() -> None:
    transport = FakeHttpTransport([HttpResponse(status_code=500, body="server error")])

    with pytest.raises(HttpStatusError) as exc_info:
        transport.send(secret_request())

    message = str(exc_info.value)
    assert "500" in message
    assert_no_secret_values(message)


def test_fake_transport_can_return_non_2xx_when_status_raising_is_disabled() -> None:
    response = HttpResponse(status_code=404, body="missing")
    transport = FakeHttpTransport([response], raise_for_status=False)

    assert transport.send(secret_request()) == response


def test_fake_transport_can_simulate_timeout_errors_without_secrets() -> None:
    transport = FakeHttpTransport([HttpTimeoutError("HTTP request timed out.")])

    with pytest.raises(HttpTimeoutError) as exc_info:
        transport.send(secret_request())

    assert "timed out" in str(exc_info.value)
    assert_no_secret_values(str(exc_info.value))


def test_fake_transport_can_simulate_generic_transport_errors_without_secrets() -> None:
    transport = FakeHttpTransport([HttpTransportError("HTTP transport unavailable.")])

    with pytest.raises(HttpTransportError) as exc_info:
        transport.send(secret_request())

    assert "unavailable" in str(exc_info.value)
    assert_no_secret_values(str(exc_info.value))


def test_fake_transport_missing_fixture_error_is_secret_safe() -> None:
    transport = FakeHttpTransport([])

    with pytest.raises(HttpTransportError) as exc_info:
        transport.send(secret_request())

    assert "No fake HTTP response configured." in str(exc_info.value)
    assert_no_secret_values(str(exc_info.value))


def test_http_transport_skeleton_has_no_external_http_dependencies() -> None:
    source = inspect.getsource(http)
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
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()


def test_provider_factory_behavior_remains_unchanged() -> None:
    assert isinstance(create_market_data_provider(AppConfig(provider="mock")), MockMarketDataProvider)
    assert isinstance(
        create_market_data_provider(AppConfig(provider="fixture")),
        FixtureComposedMarketDataProvider,
    )

    with pytest.raises(ProviderConfigurationError, match="future placeholder"):
        create_market_data_provider(AppConfig(provider="alpaca"))
