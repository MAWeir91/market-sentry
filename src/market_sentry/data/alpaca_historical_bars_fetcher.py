"""Alpaca historical intraday-bars fetcher behind injected HTTP transport.

This module is request/response plumbing only. It returns one raw response page
and is not registered as a runtime market-data provider.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from market_sentry.data.alpaca import (
    AlpacaMarketDataSettings,
    BARS_PATH,
    DEFAULT_FEED,
    build_auth_headers,
)
from market_sentry.data.http import HttpRequest, HttpResponse, HttpTransport


class AlpacaHistoricalBarsFetchError(ValueError):
    """Raised for invalid Alpaca historical-bars request or response shape."""


def _normalize_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        symbol
        for symbol in (str(item).strip().upper() for item in symbols)
        if symbol
    )


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise AlpacaHistoricalBarsFetchError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise AlpacaHistoricalBarsFetchError(f"{field_name} must be non-empty.")
    return normalized


@dataclass(frozen=True)
class AlpacaHistoricalBarsQuery:
    """Explicit query controls for one historical-bars response page."""

    timeframe: str
    start: str
    end: str
    limit: int = 1000
    page_token: str | None = None
    sort: str = "asc"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "timeframe",
            _non_empty_string(self.timeframe, "timeframe"),
        )
        object.__setattr__(self, "start", _non_empty_string(self.start, "start"))
        object.__setattr__(self, "end", _non_empty_string(self.end, "end"))

        if isinstance(self.limit, bool) or not isinstance(self.limit, int):
            raise AlpacaHistoricalBarsFetchError("limit must be an integer.")
        if not 1 <= self.limit <= 10_000:
            raise AlpacaHistoricalBarsFetchError("limit must be between 1 and 10000.")

        if self.sort not in {"asc", "desc"}:
            raise AlpacaHistoricalBarsFetchError("sort must be exactly 'asc' or 'desc'.")

        if self.page_token is not None:
            object.__setattr__(
                self,
                "page_token",
                _non_empty_string(self.page_token, "page_token"),
            )


@dataclass(frozen=True)
class AlpacaHistoricalBarsPage:
    """Raw one-page historical-bar response for requested symbols only."""

    requested_symbols: tuple[str, ...]
    bars_by_symbol: Mapping[str, tuple[Mapping[str, object], ...]]
    next_page_token: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_symbols", tuple(self.requested_symbols))
        protected_bars: dict[str, tuple[Mapping[str, object], ...]] = {}
        for symbol, bars in self.bars_by_symbol.items():
            protected_bars[symbol] = tuple(
                MappingProxyType(dict(bar)) for bar in bars
            )
        object.__setattr__(
            self,
            "bars_by_symbol",
            MappingProxyType(protected_bars),
        )


def build_historical_bars_http_request(
    symbols: Sequence[str],
    settings: AlpacaMarketDataSettings,
    query: AlpacaHistoricalBarsQuery,
    *,
    timeout_seconds: float = 10.0,
) -> HttpRequest:
    """Build a generic HTTP request for one Alpaca historical-bars page."""

    normalized_symbols = _normalize_symbols(symbols)
    params = {
        "symbols": ",".join(normalized_symbols),
        "feed": settings.feed or DEFAULT_FEED,
        "timeframe": query.timeframe,
        "start": query.start,
        "end": query.end,
        "limit": str(query.limit),
        "sort": query.sort,
    }
    if query.page_token is not None:
        params["page_token"] = query.page_token

    return HttpRequest(
        method="GET",
        url=f"{settings.base_url.rstrip('/')}{BARS_PATH}",
        params=params,
        headers=build_auth_headers(settings),
        timeout_seconds=timeout_seconds,
    )


def _load_payload(response: HttpResponse) -> dict[str, Any]:
    try:
        payload: Any = json.loads(response.body)
    except json.JSONDecodeError as exc:
        raise AlpacaHistoricalBarsFetchError(
            "Alpaca historical-bars response body is not valid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise AlpacaHistoricalBarsFetchError(
            "Alpaca historical-bars response body must be a JSON object."
        )
    return payload


def _next_page_token(payload: Mapping[str, Any]) -> str | None:
    token = payload.get("next_page_token")
    if token is None:
        return None
    if not isinstance(token, str):
        raise AlpacaHistoricalBarsFetchError(
            "next_page_token must be null or a non-empty string."
        )
    if not token.strip():
        raise AlpacaHistoricalBarsFetchError(
            "next_page_token must be null or a non-empty string."
        )
    return token


def parse_historical_bars_http_response(
    response: HttpResponse,
    requested_symbols: Sequence[str],
) -> AlpacaHistoricalBarsPage:
    """Parse one raw historical-bars response page without interpreting bars."""

    normalized_symbols = _normalize_symbols(requested_symbols)
    payload = _load_payload(response)
    bars_payload = payload.get("bars", {})
    if not isinstance(bars_payload, dict):
        raise AlpacaHistoricalBarsFetchError("bars must be a JSON object when present.")

    normalized_payload_bars = {
        str(symbol).strip().upper(): bars
        for symbol, bars in bars_payload.items()
        if str(symbol).strip()
    }

    bars_by_symbol: dict[str, tuple[Mapping[str, object], ...]] = {}
    for symbol in normalized_symbols:
        raw_bars = normalized_payload_bars.get(symbol, [])
        if not isinstance(raw_bars, list):
            raise AlpacaHistoricalBarsFetchError(
                f"bars for requested symbol {symbol} must be a JSON array."
            )

        protected_symbol_bars: list[Mapping[str, object]] = []
        for raw_bar in raw_bars:
            if not isinstance(raw_bar, dict):
                raise AlpacaHistoricalBarsFetchError(
                    f"bars for requested symbol {symbol} must contain JSON objects."
                )
            protected_symbol_bars.append(MappingProxyType(dict(raw_bar)))
        bars_by_symbol[symbol] = tuple(protected_symbol_bars)

    return AlpacaHistoricalBarsPage(
        requested_symbols=normalized_symbols,
        bars_by_symbol=bars_by_symbol,
        next_page_token=_next_page_token(payload),
    )


class AlpacaHistoricalBarsFetcher:
    """Fetch one raw Alpaca historical-bars page through injected transport."""

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

    def build_request(
        self,
        symbols: Sequence[str],
        query: AlpacaHistoricalBarsQuery,
    ) -> HttpRequest:
        """Build the request used by fetch_bars without sending it."""

        return build_historical_bars_http_request(
            symbols,
            self.settings,
            query,
            timeout_seconds=self.timeout_seconds,
        )

    def fetch_bars(
        self,
        symbols: Sequence[str],
        query: AlpacaHistoricalBarsQuery,
    ) -> AlpacaHistoricalBarsPage:
        """Fetch and parse one raw historical-bars response page."""

        normalized_symbols = _normalize_symbols(symbols)
        if not normalized_symbols:
            return AlpacaHistoricalBarsPage(
                requested_symbols=(),
                bars_by_symbol=MappingProxyType({}),
                next_page_token=None,
            )

        request = self.build_request(normalized_symbols, query)
        response = self.transport.send(request)
        return parse_historical_bars_http_response(response, normalized_symbols)
