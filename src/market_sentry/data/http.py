"""Generic HTTP transport skeleton for future provider phases.

This module is intentionally not wired into runtime providers yet. It provides
secret-safe request/response models and a fake transport for offline tests.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol


SENSITIVE_FIELD_NAMES = {
    "apca-api-key-id",
    "apca-api-secret-key",
    "apikey",
    "api_key",
    "apisecret",
    "authorization",
}


@dataclass(frozen=True)
class HttpRequest:
    """Provider-neutral HTTP request shape.

    Headers and params are hidden from repr because future provider requests may
    contain API keys or authorization values.
    """

    method: str
    url: str
    params: Mapping[str, str] = field(default_factory=dict, repr=False)
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class HttpResponse:
    """Provider-neutral HTTP response shape."""

    status_code: int
    body: str
    headers: Mapping[str, str] = field(default_factory=dict)


class HttpTransportError(Exception):
    """Base error for future HTTP transport failures."""


class HttpStatusError(HttpTransportError):
    """Raised when a fake or future transport receives a non-2xx response."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP request failed with status {status_code}.")


class HttpTimeoutError(HttpTransportError):
    """Raised when a fake or future transport times out."""


class HttpTransport(Protocol):
    """Protocol for injectable HTTP transports."""

    def send(self, request: HttpRequest) -> HttpResponse:
        """Send a request and return a response."""
        ...


def redact_sensitive_values(values: Mapping[str, str]) -> dict[str, str]:
    """Return a copy of mapping values with known secret keys redacted."""

    redacted: dict[str, str] = {}
    for key, value in values.items():
        if key.lower() in SENSITIVE_FIELD_NAMES:
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


class FakeHttpTransport:
    """Offline fake transport for deterministic tests.

    Items can be HttpResponse instances or HttpTransportError instances. Non-2xx
    responses raise HttpStatusError when raise_for_status is enabled.
    """

    def __init__(
        self,
        items: Iterable[HttpResponse | HttpTransportError],
        *,
        raise_for_status: bool = True,
    ) -> None:
        self._items = list(items)
        self.raise_for_status = raise_for_status
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)

        if not self._items:
            raise HttpTransportError("No fake HTTP response configured.")

        item = self._items.pop(0)
        if isinstance(item, HttpTransportError):
            raise item

        if self.raise_for_status and not 200 <= item.status_code <= 299:
            raise HttpStatusError(item.status_code)

        return item
