"""Offline Alpaca market-data request and parsing skeleton.

Alpaca can provide market data such as price, volume, high of day, previous
close, and intraday bars. It is not the planned source of float/reference data,
so this module does not produce scanner-ready StockCandidate objects by itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALPACA_MARKET_DATA_BASE_URL = "https://data.alpaca.markets"
SNAPSHOTS_PATH = "/v2/stocks/snapshots"
BARS_PATH = "/v2/stocks/bars"
DEFAULT_FEED = "iex"


@dataclass(frozen=True)
class AlpacaMarketDataSettings:
    """Settings for shaping future Alpaca market-data requests."""

    api_key: str | None = field(default=None, repr=False)
    api_secret: str | None = field(default=None, repr=False)
    feed: str = DEFAULT_FEED
    base_url: str = ALPACA_MARKET_DATA_BASE_URL


@dataclass(frozen=True)
class AlpacaRequest:
    """Deterministic request shape for future HTTP execution."""

    path: str
    params: dict[str, str | int]
    headers: dict[str, str] = field(repr=False)


@dataclass(frozen=True)
class AlpacaSnapshot:
    """Normalized market-data snapshot from an Alpaca-style fixture."""

    symbol: str
    price: float | None
    daily_volume: int | None
    high_of_day: float | None
    previous_close: float | None


def _normalize_symbols(symbols: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        symbol
        for symbol in (item.strip().upper() for item in symbols)
        if symbol
    )


def _symbols_param(symbols: list[str] | tuple[str, ...]) -> str:
    return ",".join(_normalize_symbols(symbols))


def build_auth_headers(settings: AlpacaMarketDataSettings) -> dict[str, str]:
    """Build Alpaca auth headers without logging or validating secrets."""

    headers: dict[str, str] = {}
    if settings.api_key:
        headers["APCA-API-KEY-ID"] = settings.api_key
    if settings.api_secret:
        headers["APCA-API-SECRET-KEY"] = settings.api_secret
    return headers


def build_snapshot_request(
    symbols: list[str] | tuple[str, ...],
    settings: AlpacaMarketDataSettings,
) -> AlpacaRequest:
    """Build a multi-symbol snapshot request shape without sending it."""

    return AlpacaRequest(
        path=SNAPSHOTS_PATH,
        params={
            "symbols": _symbols_param(symbols),
            "feed": settings.feed or DEFAULT_FEED,
        },
        headers=build_auth_headers(settings),
    )


def build_bars_request(
    symbols: list[str] | tuple[str, ...],
    settings: AlpacaMarketDataSettings,
    *,
    timeframe: str = "1Min",
    limit: int = 15,
) -> AlpacaRequest:
    """Build an intraday bars request shape without sending it."""

    return AlpacaRequest(
        path=BARS_PATH,
        params={
            "symbols": _symbols_param(symbols),
            "feed": settings.feed or DEFAULT_FEED,
            "timeframe": timeframe,
            "limit": limit,
        },
        headers=build_auth_headers(settings),
    )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        converted = int(value)
    except (TypeError, ValueError):
        return None
    return converted


def _nested(mapping: dict[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def parse_snapshot_response(
    payload: dict[str, Any],
    symbol: str,
) -> AlpacaSnapshot | None:
    """Parse one symbol from an Alpaca-style snapshot fixture."""

    normalized_symbol = symbol.strip().upper()
    snapshots = payload.get("snapshots", payload)
    if not isinstance(snapshots, dict):
        return None

    raw_snapshot = snapshots.get(normalized_symbol)
    if not isinstance(raw_snapshot, dict):
        return None

    latest_trade_price = _to_float(_nested(raw_snapshot, "latestTrade", "p"))
    daily_bar_close = _to_float(_nested(raw_snapshot, "dailyBar", "c"))
    price = latest_trade_price if latest_trade_price is not None else daily_bar_close

    return AlpacaSnapshot(
        symbol=normalized_symbol,
        price=price,
        daily_volume=_to_int(_nested(raw_snapshot, "dailyBar", "v")),
        high_of_day=_to_float(_nested(raw_snapshot, "dailyBar", "h")),
        previous_close=_to_float(_nested(raw_snapshot, "prevDailyBar", "c")),
    )


def calculate_daily_gain_from_snapshot(snapshot: AlpacaSnapshot) -> float | None:
    """Return whole-number percent daily gain from snapshot data."""

    if snapshot.price is None or snapshot.previous_close is None:
        return None
    if snapshot.previous_close <= 0:
        return None
    return round(((snapshot.price - snapshot.previous_close) / snapshot.previous_close) * 100.0, 2)


def calculate_15m_change_from_bars(bars: list[dict[str, Any]]) -> float | None:
    """Return whole-number percent change from first and last bar close."""

    if len(bars) < 2:
        return None

    first_close = _to_float(bars[0].get("c"))
    last_close = _to_float(bars[-1].get("c"))
    if first_close is None or last_close is None:
        return None
    if first_close <= 0:
        return None

    return round(((last_close - first_close) / first_close) * 100.0, 2)
