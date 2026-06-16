"""Alpaca snapshot fetcher behind the generic HTTP transport.

This module is provider plumbing only. It uses an injected transport and is not
registered as a runtime market-data provider.
"""

from __future__ import annotations

import json
from typing import Any

from market_sentry.data.alpaca import (
    AlpacaMarketDataSettings,
    AlpacaRequest,
    AlpacaSnapshot,
    build_snapshot_request,
    parse_snapshot_response,
)
from market_sentry.data.http import HttpRequest, HttpResponse, HttpTransport


class AlpacaSnapshotFetchError(ValueError):
    """Raised when an Alpaca snapshot response cannot be parsed."""


def _snapshot_url(settings: AlpacaMarketDataSettings, request: AlpacaRequest) -> str:
    return f"{settings.base_url.rstrip('/')}{request.path}"


def build_snapshot_http_request(
    symbols: list[str] | tuple[str, ...],
    settings: AlpacaMarketDataSettings,
    *,
    timeout_seconds: float = 10.0,
) -> HttpRequest:
    """Build a generic HTTP request for Alpaca snapshots without sending it."""

    alpaca_request = build_snapshot_request(symbols, settings)
    return HttpRequest(
        method="GET",
        url=_snapshot_url(settings, alpaca_request),
        params={key: str(value) for key, value in alpaca_request.params.items()},
        headers=alpaca_request.headers,
        timeout_seconds=timeout_seconds,
    )


def _requested_symbols(request: HttpRequest) -> tuple[str, ...]:
    symbols_value = request.params.get("symbols", "")
    return tuple(symbol for symbol in symbols_value.split(",") if symbol)


def parse_snapshot_http_response(
    response: HttpResponse,
    symbols: list[str] | tuple[str, ...],
) -> dict[str, AlpacaSnapshot]:
    """Parse a fake HTTP response body into normalized Alpaca snapshots."""

    try:
        payload: Any = json.loads(response.body)
    except json.JSONDecodeError as exc:
        raise AlpacaSnapshotFetchError("Alpaca snapshot response body is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise AlpacaSnapshotFetchError("Alpaca snapshot response body must be a JSON object.")

    snapshots: dict[str, AlpacaSnapshot] = {}
    for symbol in symbols:
        parsed = parse_snapshot_response(payload, symbol)
        if parsed is not None:
            snapshots[parsed.symbol] = parsed
    return snapshots


class AlpacaSnapshotFetcher:
    """Fetch normalized Alpaca snapshot data through an injected transport."""

    def __init__(
        self,
        *,
        settings: AlpacaMarketDataSettings,
        transport: HttpTransport,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def build_request(self, symbols: list[str] | tuple[str, ...]) -> HttpRequest:
        """Build the request used by fetch_snapshots without sending it."""

        return build_snapshot_http_request(
            symbols,
            self.settings,
            timeout_seconds=self.timeout_seconds,
        )

    def fetch_snapshots(
        self,
        symbols: list[str] | tuple[str, ...],
    ) -> dict[str, AlpacaSnapshot]:
        """Fetch and parse normalized Alpaca snapshots for requested symbols."""

        request = self.build_request(symbols)
        normalized_symbols = _requested_symbols(request)
        if not normalized_symbols:
            return {}

        response = self.transport.send(request)
        return parse_snapshot_http_response(response, normalized_symbols)
