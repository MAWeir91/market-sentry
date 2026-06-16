"""FMP float/reference fetcher behind the generic HTTP transport.

This module is provider plumbing only. It uses an injected transport and is not
registered as a runtime market-data provider.
"""

from __future__ import annotations

import json
from typing import Any

from market_sentry.data.fmp import (
    FMPFloatData,
    FMPReferenceSettings,
    FMPRequest,
    build_shares_float_request,
    parse_shares_float_response,
)
from market_sentry.data.http import HttpRequest, HttpResponse, HttpTransport


class FMPFloatFetchError(ValueError):
    """Raised when an FMP float response cannot be parsed."""


def _shares_float_url(settings: FMPReferenceSettings, request: FMPRequest) -> str:
    return f"{settings.base_url.rstrip('/')}{request.path}"


def build_shares_float_http_request(
    symbol: str | None,
    settings: FMPReferenceSettings,
    *,
    timeout_seconds: float = 10.0,
) -> HttpRequest:
    """Build a generic HTTP request for FMP shares-float without sending it."""

    fmp_request = build_shares_float_request(symbol, settings)
    return HttpRequest(
        method="GET",
        url=_shares_float_url(settings, fmp_request),
        params=fmp_request.params,
        timeout_seconds=timeout_seconds,
    )


def _requested_symbol(request: HttpRequest) -> str:
    return request.params.get("symbol", "").strip().upper()


def parse_float_http_response(
    response: HttpResponse,
    symbol: str,
) -> FMPFloatData | None:
    """Parse a fake HTTP response body into normalized FMP float data."""

    try:
        payload: Any = json.loads(response.body)
    except json.JSONDecodeError as exc:
        raise FMPFloatFetchError("FMP float response body is not valid JSON.") from exc

    if not isinstance(payload, (dict, list)):
        raise FMPFloatFetchError("FMP float response body must be a JSON object or array.")

    return parse_shares_float_response(payload, symbol)


class FMPFloatFetcher:
    """Fetch normalized FMP float data through an injected transport."""

    def __init__(
        self,
        *,
        settings: FMPReferenceSettings,
        transport: HttpTransport,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def build_request(self, symbol: str | None) -> HttpRequest:
        """Build the request used by fetch_float without sending it."""

        return build_shares_float_http_request(
            symbol,
            self.settings,
            timeout_seconds=self.timeout_seconds,
        )

    def fetch_float(self, symbol: str | None) -> FMPFloatData | None:
        """Fetch and parse normalized FMP float data for one symbol."""

        request = self.build_request(symbol)
        normalized_symbol = _requested_symbol(request)
        if not normalized_symbol:
            return None

        response = self.transport.send(request)
        return parse_float_http_response(response, normalized_symbol)
