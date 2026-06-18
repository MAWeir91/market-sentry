"""Offline adapter from raw Alpaca historical bars to intraday series inputs.

This module only adapts caller-supplied raw bars and explicit metadata into
Phase 13F input models. It does not fetch data, calculate RVOL, or build
candidates.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from market_sentry.data.alpaca_historical_bars_fetcher import AlpacaHistoricalBarsPage
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)


class AlpacaHistoricalBarsAdapterStatus:
    """Stable status/reason codes for raw historical-bar adaptation."""

    OK = "OK"
    EMPTY_SYMBOL = "EMPTY_SYMBOL"
    INVALID_SESSION_ID = "INVALID_SESSION_ID"
    EMPTY_BUCKET = "EMPTY_BUCKET"
    INVALID_CUTOFF_TIMESTAMP = "INVALID_CUTOFF_TIMESTAMP"
    NAIVE_CUTOFF_TIMESTAMP = "NAIVE_CUTOFF_TIMESTAMP"
    INVALID_RAW_BAR = "INVALID_RAW_BAR"
    MISSING_RAW_TIMESTAMP = "MISSING_RAW_TIMESTAMP"
    INVALID_RAW_TIMESTAMP = "INVALID_RAW_TIMESTAMP"
    NAIVE_RAW_TIMESTAMP = "NAIVE_RAW_TIMESTAMP"
    MISMATCHED_TIMESTAMP_TIMEZONE = "MISMATCHED_TIMESTAMP_TIMEZONE"
    MISSING_RAW_VOLUME = "MISSING_RAW_VOLUME"


@dataclass(frozen=True)
class AlpacaHistoricalBarsIntradaySeriesRequest:
    """Explicit metadata for adapting one raw historical-bars series."""

    symbol: str
    session_id: str
    bucket: str
    cutoff_timestamp: datetime


@dataclass(frozen=True)
class AlpacaHistoricalBarsIntradaySeriesResult:
    """Inspectable result for one raw-bar to intraday-series adaptation."""

    symbol: str
    session_id: str
    bucket: str
    cutoff_timestamp: datetime | None
    intraday_series: IntradayVolumeSeriesInput | None
    status: str
    reason: str | None = None
    raw_bar_count: int = 0
    converted_bar_count: int = 0


def _normalize_symbol(symbol: Any) -> str:
    if symbol is None:
        return ""
    return str(symbol).strip().upper()


def _normalize_label(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _fail(
    symbol: str,
    session_id: str,
    bucket: str,
    cutoff_timestamp: datetime | None,
    status: str,
    *,
    raw_bar_count: int = 0,
) -> AlpacaHistoricalBarsIntradaySeriesResult:
    return AlpacaHistoricalBarsIntradaySeriesResult(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        cutoff_timestamp=cutoff_timestamp,
        intraday_series=None,
        status=status,
        reason=status,
        raw_bar_count=raw_bar_count,
        converted_bar_count=0,
    )


def _parse_raw_timestamp(value: Any, cutoff_timestamp: datetime) -> tuple[datetime | None, str | None]:
    if not isinstance(value, str):
        return None, AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP
    if not value or value != value.strip():
        return None, AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP
    if "T" not in value:
        return None, AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP

    parse_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        timestamp = datetime.fromisoformat(parse_value)
    except ValueError:
        return None, AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP

    if not _is_aware(timestamp):
        return None, AlpacaHistoricalBarsAdapterStatus.NAIVE_RAW_TIMESTAMP
    if timestamp.tzinfo != cutoff_timestamp.tzinfo:
        return None, AlpacaHistoricalBarsAdapterStatus.MISMATCHED_TIMESTAMP_TIMEZONE
    return timestamp, None


def build_intraday_series_from_historical_bars(
    page: AlpacaHistoricalBarsPage,
    request: AlpacaHistoricalBarsIntradaySeriesRequest,
) -> AlpacaHistoricalBarsIntradaySeriesResult:
    """Adapt raw historical bars into a Phase 13F intraday series input."""

    symbol = _normalize_symbol(request.symbol)
    session_id = _normalize_label(request.session_id)
    bucket = _normalize_label(request.bucket)
    cutoff_timestamp = request.cutoff_timestamp

    if not symbol:
        return _fail(symbol, session_id, bucket, None, AlpacaHistoricalBarsAdapterStatus.EMPTY_SYMBOL)
    if not session_id:
        return _fail(
            symbol,
            session_id,
            bucket,
            None,
            AlpacaHistoricalBarsAdapterStatus.INVALID_SESSION_ID,
        )
    if not bucket:
        return _fail(symbol, session_id, bucket, None, AlpacaHistoricalBarsAdapterStatus.EMPTY_BUCKET)
    if not isinstance(cutoff_timestamp, datetime):
        return _fail(
            symbol,
            session_id,
            bucket,
            None,
            AlpacaHistoricalBarsAdapterStatus.INVALID_CUTOFF_TIMESTAMP,
        )
    if not _is_aware(cutoff_timestamp):
        return _fail(
            symbol,
            session_id,
            bucket,
            cutoff_timestamp,
            AlpacaHistoricalBarsAdapterStatus.NAIVE_CUTOFF_TIMESTAMP,
        )

    raw_bars = tuple(page.bars_by_symbol.get(symbol, ()))
    raw_bar_count = len(raw_bars)
    converted_bars: list[IntradayVolumeBar] = []
    for raw_bar in raw_bars:
        if not isinstance(raw_bar, Mapping):
            return _fail(
                symbol,
                session_id,
                bucket,
                cutoff_timestamp,
                AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_BAR,
                raw_bar_count=raw_bar_count,
            )
        if "t" not in raw_bar:
            return _fail(
                symbol,
                session_id,
                bucket,
                cutoff_timestamp,
                AlpacaHistoricalBarsAdapterStatus.MISSING_RAW_TIMESTAMP,
                raw_bar_count=raw_bar_count,
            )
        if "v" not in raw_bar:
            return _fail(
                symbol,
                session_id,
                bucket,
                cutoff_timestamp,
                AlpacaHistoricalBarsAdapterStatus.MISSING_RAW_VOLUME,
                raw_bar_count=raw_bar_count,
            )

        timestamp, timestamp_error = _parse_raw_timestamp(raw_bar["t"], cutoff_timestamp)
        if timestamp_error is not None or timestamp is None:
            return _fail(
                symbol,
                session_id,
                bucket,
                cutoff_timestamp,
                timestamp_error or AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP,
                raw_bar_count=raw_bar_count,
            )
        converted_bars.append(
            IntradayVolumeBar(
                timestamp=timestamp,
                volume=raw_bar["v"],
            )
        )

    series = IntradayVolumeSeriesInput(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        cutoff_timestamp=cutoff_timestamp,
        bars=tuple(converted_bars),
    )
    return AlpacaHistoricalBarsIntradaySeriesResult(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        cutoff_timestamp=cutoff_timestamp,
        intraday_series=series,
        status=AlpacaHistoricalBarsAdapterStatus.OK,
        reason=None,
        raw_bar_count=raw_bar_count,
        converted_bar_count=raw_bar_count,
    )


def build_intraday_series_from_historical_bars_results(
    page: AlpacaHistoricalBarsPage,
    requests: Sequence[AlpacaHistoricalBarsIntradaySeriesRequest],
) -> list[AlpacaHistoricalBarsIntradaySeriesResult]:
    """Adapt raw bars for each request while preserving request order."""

    return [
        build_intraday_series_from_historical_bars(page, request)
        for request in requests
    ]
