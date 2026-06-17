import ast
import inspect
import socket
from urllib import error, request

import pytest

from market_sentry.config import AppConfig
from market_sentry.data import http_stdlib
from market_sentry.data.factory import (
    ProviderConfigurationError,
    create_market_data_provider,
)
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.composed_fixture_provider import OfflineComposedFixtureProvider
from market_sentry.data.http import (
    HttpRequest,
    HttpStatusError,
    HttpTimeoutError,
    HttpTransportError,
)
from market_sentry.data.http_stdlib import StdlibHttpTransport
from market_sentry.data.mock_provider import MockMarketDataProvider


SECRET_KEY = "secret-api-key"
SECRET_TOKEN = "Bearer secret-token"


class FakeHeaders(dict):
    def get_content_charset(self) -> str:
        return "utf-8"


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        body: bytes = b'{"ok": true}',
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = FakeHeaders(headers or {"content-type": "application/json"})

    def getcode(self) -> int:
        return self.status_code

    def read(self) -> bytes:
        return self.body


def secret_request(**overrides: object) -> HttpRequest:
    values = {
        "method": "GET",
        "url": "https://example.test/snapshots?existing=1",
        "params": {"symbol": "XTRM", "apikey": SECRET_KEY},
        "headers": {"authorization": SECRET_TOKEN, "X-Test": "yes"},
        "timeout_seconds": 4.5,
    }
    values.update(overrides)
    return HttpRequest(**values)


def assert_no_secrets(text: str) -> None:
    assert SECRET_KEY not in text
    assert SECRET_TOKEN not in text


def test_successful_get_request_returns_http_response(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(stdlib_request, timeout):
        captured["request"] = stdlib_request
        captured["timeout"] = timeout
        return FakeResponse(
            status_code=200,
            body="hello".encode("utf-8"),
            headers={"x-provider": "fake"},
        )

    monkeypatch.setattr(request, "urlopen", fake_urlopen)

    response = StdlibHttpTransport().send(secret_request())

    assert response.status_code == 200
    assert response.body == "hello"
    assert response.headers["x-provider"] == "fake"


def test_query_params_are_encoded_into_url(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(stdlib_request, timeout):
        captured["url"] = stdlib_request.full_url
        return FakeResponse()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)

    StdlibHttpTransport().send(
        secret_request(params={"symbol": "A B", "apikey": SECRET_KEY})
    )

    full_url = captured["url"]
    assert "existing=1" in full_url
    assert "symbol=A+B" in full_url
    assert f"apikey={SECRET_KEY}" in full_url


def test_headers_are_passed_to_standard_library_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(stdlib_request, timeout):
        captured["headers"] = dict(stdlib_request.header_items())
        return FakeResponse()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)

    StdlibHttpTransport().send(secret_request())

    header_values = set(captured["headers"].values())
    assert SECRET_TOKEN in header_values
    assert "yes" in header_values


def test_timeout_value_is_passed_through(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(stdlib_request, timeout):
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)

    StdlibHttpTransport().send(secret_request(timeout_seconds=1.25))

    assert captured["timeout"] == 1.25


def test_response_body_is_decoded_as_text(monkeypatch) -> None:
    monkeypatch.setattr(
        request,
        "urlopen",
        lambda stdlib_request, timeout: FakeResponse(body="café".encode("utf-8")),
    )

    response = StdlibHttpTransport().send(secret_request())

    assert response.body == "café"


def test_unsupported_http_method_raises_transport_error() -> None:
    with pytest.raises(HttpTransportError) as exc_info:
        StdlibHttpTransport().send(secret_request(method="POST"))

    assert "Unsupported HTTP method: POST" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_non_2xx_response_status_raises_status_error(monkeypatch) -> None:
    monkeypatch.setattr(
        request,
        "urlopen",
        lambda stdlib_request, timeout: FakeResponse(status_code=500),
    )

    with pytest.raises(HttpStatusError) as exc_info:
        StdlibHttpTransport().send(secret_request())

    assert "500" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_http_error_raises_status_error_without_secrets(monkeypatch) -> None:
    def fake_urlopen(stdlib_request, timeout):
        raise error.HTTPError(
            url=stdlib_request.full_url,
            code=429,
            msg=f"rate limited {SECRET_KEY}",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(request, "urlopen", fake_urlopen)

    with pytest.raises(HttpStatusError) as exc_info:
        StdlibHttpTransport().send(secret_request())

    assert "429" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_timeout_error_raises_timeout_error_without_secrets(monkeypatch) -> None:
    def fake_urlopen(stdlib_request, timeout):
        raise socket.timeout(f"timeout {SECRET_KEY}")

    monkeypatch.setattr(request, "urlopen", fake_urlopen)

    with pytest.raises(HttpTimeoutError) as exc_info:
        StdlibHttpTransport().send(secret_request())

    assert "timed out" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_url_error_raises_transport_error_without_secrets(monkeypatch) -> None:
    def fake_urlopen(stdlib_request, timeout):
        raise error.URLError(f"network failed {SECRET_KEY} {SECRET_TOKEN}")

    monkeypatch.setattr(request, "urlopen", fake_urlopen)

    with pytest.raises(HttpTransportError) as exc_info:
        StdlibHttpTransport().send(secret_request())

    assert "HTTP request failed." in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_url_error_with_timeout_reason_raises_timeout_error(monkeypatch) -> None:
    def fake_urlopen(stdlib_request, timeout):
        raise error.URLError(socket.timeout(f"timeout {SECRET_KEY}"))

    monkeypatch.setattr(request, "urlopen", fake_urlopen)

    with pytest.raises(HttpTimeoutError) as exc_info:
        StdlibHttpTransport().send(secret_request())

    assert "timed out" in str(exc_info.value)
    assert_no_secrets(str(exc_info.value))


def test_stdlib_transport_uses_no_external_http_dependencies() -> None:
    source = inspect.getsource(http_stdlib)
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

    assert not {"requests", "httpx", "aiohttp", "websockets"} & imported_modules
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()


def test_provider_factory_behavior_remains_unchanged() -> None:
    assert isinstance(create_market_data_provider(AppConfig(provider="mock")), MockMarketDataProvider)
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
