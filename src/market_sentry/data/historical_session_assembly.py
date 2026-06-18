"""Offline historical-session assembly for raw historical bars.

This module applies explicit caller metadata to one raw bars page and delegates
eligible session-scoped bars to the Phase 14B adapter.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from market_sentry.data.alpaca_historical_bars_adapter import (
    AlpacaHistoricalBarsIntradaySeriesRequest,
    AlpacaHistoricalBarsIntradaySeriesResult,
    build_intraday_series_from_historical_bars,
)
from market_sentry.data.alpaca_historical_bars_fetcher import AlpacaHistoricalBarsPage
from market_sentry.data.intraday_bucket_adapter import IntradayVolumeSeriesInput


class HistoricalSessionAssemblyStatus:
    """Stable status/reason codes for historical-session assembly."""

    OK = "OK"
    EMPTY_SYMBOL = "EMPTY_SYMBOL"
    INVALID_SESSION_ID = "INVALID_SESSION_ID"
    EMPTY_BUCKET = "EMPTY_BUCKET"
    INVALID_SESSION_START_TIMESTAMP = "INVALID_SESSION_START_TIMESTAMP"
    INVALID_SESSION_END_TIMESTAMP = "INVALID_SESSION_END_TIMESTAMP"
    INVALID_CUTOFF_TIMESTAMP = "INVALID_CUTOFF_TIMESTAMP"
    NAIVE_SESSION_TIMESTAMP = "NAIVE_SESSION_TIMESTAMP"
    MISMATCHED_SESSION_TIMEZONE = "MISMATCHED_SESSION_TIMEZONE"
    INVALID_SESSION_WINDOW = "INVALID_SESSION_WINDOW"
    INVALID_CUTOFF_OUTSIDE_SESSION = "INVALID_CUTOFF_OUTSIDE_SESSION"
    INVALID_IS_COMPLETE = "INVALID_IS_COMPLETE"
    INVALID_CURRENT_SESSION_ID = "INVALID_CURRENT_SESSION_ID"
    CURRENT_SESSION_IN_HISTORY = "CURRENT_SESSION_IN_HISTORY"
    DUPLICATE_HISTORICAL_SESSION_ID = "DUPLICATE_HISTORICAL_SESSION_ID"
    INCOMPLETE_PAGE_COLLECTION = "INCOMPLETE_PAGE_COLLECTION"
    INCOMPLETE_SESSION = "INCOMPLETE_SESSION"
    INVALID_RAW_BAR = "INVALID_RAW_BAR"
    MISSING_RAW_TIMESTAMP = "MISSING_RAW_TIMESTAMP"
    INVALID_RAW_TIMESTAMP = "INVALID_RAW_TIMESTAMP"
    NAIVE_RAW_TIMESTAMP = "NAIVE_RAW_TIMESTAMP"
    MISMATCHED_RAW_TIMESTAMP_TIMEZONE = "MISMATCHED_RAW_TIMESTAMP_TIMEZONE"
    CUT_OFF_NOT_REACHED = "CUT_OFF_NOT_REACHED"
    ADAPTER_FAILED = "ADAPTER_FAILED"


@dataclass(frozen=True)
class HistoricalIntradaySessionMetadata:
    """Caller-supplied metadata for one potential historical session."""

    symbol: str
    session_id: str
    bucket: str
    session_start_timestamp: datetime
    session_end_timestamp: datetime
    cutoff_timestamp: datetime
    is_complete: bool


@dataclass(frozen=True)
class HistoricalSessionAssemblyResult:
    """Inspectable result for assembling one historical session."""

    symbol: str
    session_id: str
    bucket: str
    session_start_timestamp: datetime | None
    session_end_timestamp: datetime | None
    cutoff_timestamp: datetime | None
    intraday_series: IntradayVolumeSeriesInput | None
    status: str
    reason: str | None = None
    source_raw_bar_count: int = 0
    in_window_raw_bar_count: int = 0
    adapter_result: AlpacaHistoricalBarsIntradaySeriesResult | None = None


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


def _valid_datetime(value: Any) -> bool:
    return isinstance(value, datetime)


def _identity(record: HistoricalIntradaySessionMetadata) -> tuple[str, str, str]:
    return (
        _normalize_symbol(getattr(record, "symbol", "")),
        _normalize_label(getattr(record, "session_id", "")),
        _normalize_label(getattr(record, "bucket", "")),
    )


def _fail(
    record: HistoricalIntradaySessionMetadata,
    status: str,
    *,
    session_start_timestamp: datetime | None = None,
    session_end_timestamp: datetime | None = None,
    cutoff_timestamp: datetime | None = None,
    source_raw_bar_count: int = 0,
    in_window_raw_bar_count: int = 0,
    adapter_result: AlpacaHistoricalBarsIntradaySeriesResult | None = None,
    reason: str | None = None,
) -> HistoricalSessionAssemblyResult:
    symbol, session_id, bucket = _identity(record)
    return HistoricalSessionAssemblyResult(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        session_start_timestamp=session_start_timestamp,
        session_end_timestamp=session_end_timestamp,
        cutoff_timestamp=cutoff_timestamp,
        intraday_series=None,
        status=status,
        reason=reason or status,
        source_raw_bar_count=source_raw_bar_count,
        in_window_raw_bar_count=in_window_raw_bar_count,
        adapter_result=adapter_result,
    )


def _batch_failure(
    metadata_records: Sequence[HistoricalIntradaySessionMetadata],
    status: str,
) -> list[HistoricalSessionAssemblyResult]:
    return [_fail(record, status) for record in metadata_records]


def _duplicate_keys(
    metadata_records: Sequence[HistoricalIntradaySessionMetadata],
) -> set[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for record in metadata_records:
        symbol, session_id, _bucket = _identity(record)
        if symbol and session_id:
            keys.append((symbol, session_id))
    counts = Counter(keys)
    return {key for key, count in counts.items() if count > 1}


def _parse_raw_timestamp(value: Any, cutoff_timestamp: datetime) -> tuple[datetime | None, str | None]:
    if not isinstance(value, str):
        return None, HistoricalSessionAssemblyStatus.INVALID_RAW_TIMESTAMP
    if not value or value != value.strip():
        return None, HistoricalSessionAssemblyStatus.INVALID_RAW_TIMESTAMP
    if "T" not in value:
        return None, HistoricalSessionAssemblyStatus.INVALID_RAW_TIMESTAMP

    parse_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        timestamp = datetime.fromisoformat(parse_value)
    except ValueError:
        return None, HistoricalSessionAssemblyStatus.INVALID_RAW_TIMESTAMP

    if not _is_aware(timestamp):
        return None, HistoricalSessionAssemblyStatus.NAIVE_RAW_TIMESTAMP
    if timestamp.tzinfo != cutoff_timestamp.tzinfo:
        return None, HistoricalSessionAssemblyStatus.MISMATCHED_RAW_TIMESTAMP_TIMEZONE
    return timestamp, None


def _validate_record(
    record: HistoricalIntradaySessionMetadata,
    *,
    current_session_id: str,
    duplicate_keys: set[tuple[str, str]],
) -> HistoricalSessionAssemblyResult | None:
    symbol, session_id, bucket = _identity(record)
    if not symbol:
        return _fail(record, HistoricalSessionAssemblyStatus.EMPTY_SYMBOL)
    if not session_id:
        return _fail(record, HistoricalSessionAssemblyStatus.INVALID_SESSION_ID)
    if not bucket:
        return _fail(record, HistoricalSessionAssemblyStatus.EMPTY_BUCKET)

    start = getattr(record, "session_start_timestamp", None)
    end = getattr(record, "session_end_timestamp", None)
    cutoff = getattr(record, "cutoff_timestamp", None)
    if not _valid_datetime(start):
        return _fail(record, HistoricalSessionAssemblyStatus.INVALID_SESSION_START_TIMESTAMP)
    if not _valid_datetime(end):
        return _fail(record, HistoricalSessionAssemblyStatus.INVALID_SESSION_END_TIMESTAMP)
    if not _valid_datetime(cutoff):
        return _fail(record, HistoricalSessionAssemblyStatus.INVALID_CUTOFF_TIMESTAMP)
    if not _is_aware(start) or not _is_aware(end) or not _is_aware(cutoff):
        return _fail(
            record,
            HistoricalSessionAssemblyStatus.NAIVE_SESSION_TIMESTAMP,
            session_start_timestamp=start,
            session_end_timestamp=end,
            cutoff_timestamp=cutoff,
        )
    if start.tzinfo != end.tzinfo or start.tzinfo != cutoff.tzinfo:
        return _fail(
            record,
            HistoricalSessionAssemblyStatus.MISMATCHED_SESSION_TIMEZONE,
            session_start_timestamp=start,
            session_end_timestamp=end,
            cutoff_timestamp=cutoff,
        )
    if not start < end:
        return _fail(
            record,
            HistoricalSessionAssemblyStatus.INVALID_SESSION_WINDOW,
            session_start_timestamp=start,
            session_end_timestamp=end,
            cutoff_timestamp=cutoff,
        )
    if not start <= cutoff < end:
        return _fail(
            record,
            HistoricalSessionAssemblyStatus.INVALID_CUTOFF_OUTSIDE_SESSION,
            session_start_timestamp=start,
            session_end_timestamp=end,
            cutoff_timestamp=cutoff,
        )

    is_complete = getattr(record, "is_complete", None)
    if not isinstance(is_complete, bool):
        return _fail(
            record,
            HistoricalSessionAssemblyStatus.INVALID_IS_COMPLETE,
            session_start_timestamp=start,
            session_end_timestamp=end,
            cutoff_timestamp=cutoff,
        )
    if is_complete is False:
        return _fail(
            record,
            HistoricalSessionAssemblyStatus.INCOMPLETE_SESSION,
            session_start_timestamp=start,
            session_end_timestamp=end,
            cutoff_timestamp=cutoff,
        )

    if (symbol, session_id) in duplicate_keys:
        return _fail(
            record,
            HistoricalSessionAssemblyStatus.DUPLICATE_HISTORICAL_SESSION_ID,
            session_start_timestamp=start,
            session_end_timestamp=end,
            cutoff_timestamp=cutoff,
        )
    if session_id == current_session_id:
        return _fail(
            record,
            HistoricalSessionAssemblyStatus.CURRENT_SESSION_IN_HISTORY,
            session_start_timestamp=start,
            session_end_timestamp=end,
            cutoff_timestamp=cutoff,
        )
    return None


def _assemble_record(
    page: AlpacaHistoricalBarsPage,
    record: HistoricalIntradaySessionMetadata,
) -> HistoricalSessionAssemblyResult:
    symbol, session_id, bucket = _identity(record)
    start = record.session_start_timestamp
    end = record.session_end_timestamp
    cutoff = record.cutoff_timestamp

    raw_bars = tuple(page.bars_by_symbol.get(symbol, ()))
    source_raw_bar_count = len(raw_bars)
    selected_bars: list[Mapping[str, object]] = []
    selected_timestamps: list[datetime] = []

    for raw_bar in raw_bars:
        if not isinstance(raw_bar, Mapping):
            return _fail(
                record,
                HistoricalSessionAssemblyStatus.INVALID_RAW_BAR,
                session_start_timestamp=start,
                session_end_timestamp=end,
                cutoff_timestamp=cutoff,
                source_raw_bar_count=source_raw_bar_count,
            )
        if "t" not in raw_bar:
            return _fail(
                record,
                HistoricalSessionAssemblyStatus.MISSING_RAW_TIMESTAMP,
                session_start_timestamp=start,
                session_end_timestamp=end,
                cutoff_timestamp=cutoff,
                source_raw_bar_count=source_raw_bar_count,
            )
        timestamp, timestamp_error = _parse_raw_timestamp(raw_bar["t"], cutoff)
        if timestamp_error is not None or timestamp is None:
            return _fail(
                record,
                timestamp_error or HistoricalSessionAssemblyStatus.INVALID_RAW_TIMESTAMP,
                session_start_timestamp=start,
                session_end_timestamp=end,
                cutoff_timestamp=cutoff,
                source_raw_bar_count=source_raw_bar_count,
            )
        if start <= timestamp < end:
            selected_bars.append(raw_bar)
            selected_timestamps.append(timestamp)

    in_window_raw_bar_count = len(selected_bars)
    if not any(timestamp >= cutoff for timestamp in selected_timestamps):
        return _fail(
            record,
            HistoricalSessionAssemblyStatus.CUT_OFF_NOT_REACHED,
            session_start_timestamp=start,
            session_end_timestamp=end,
            cutoff_timestamp=cutoff,
            source_raw_bar_count=source_raw_bar_count,
            in_window_raw_bar_count=in_window_raw_bar_count,
        )

    session_page = AlpacaHistoricalBarsPage(
        requested_symbols=(symbol,),
        bars_by_symbol={symbol: tuple(selected_bars)},
        next_page_token=None,
    )
    adapter_request = AlpacaHistoricalBarsIntradaySeriesRequest(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        cutoff_timestamp=cutoff,
    )
    adapter_result = build_intraday_series_from_historical_bars(
        session_page,
        adapter_request,
    )
    if adapter_result.status != HistoricalSessionAssemblyStatus.OK:
        return HistoricalSessionAssemblyResult(
            symbol=symbol,
            session_id=session_id,
            bucket=bucket,
            session_start_timestamp=start,
            session_end_timestamp=end,
            cutoff_timestamp=cutoff,
            intraday_series=None,
            status=HistoricalSessionAssemblyStatus.ADAPTER_FAILED,
            reason=f"{HistoricalSessionAssemblyStatus.ADAPTER_FAILED}:{adapter_result.status}",
            source_raw_bar_count=source_raw_bar_count,
            in_window_raw_bar_count=in_window_raw_bar_count,
            adapter_result=adapter_result,
        )

    return HistoricalSessionAssemblyResult(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        session_start_timestamp=start,
        session_end_timestamp=end,
        cutoff_timestamp=cutoff,
        intraday_series=adapter_result.intraday_series,
        status=HistoricalSessionAssemblyStatus.OK,
        reason=None,
        source_raw_bar_count=source_raw_bar_count,
        in_window_raw_bar_count=in_window_raw_bar_count,
        adapter_result=adapter_result,
    )


def assemble_historical_sessions_from_page(
    page: AlpacaHistoricalBarsPage,
    metadata_records: Sequence[HistoricalIntradaySessionMetadata],
    *,
    current_session_id: str,
    page_collection_complete: bool,
) -> list[HistoricalSessionAssemblyResult]:
    """Assemble eligible historical sessions from one raw bars page."""

    records = list(metadata_records)
    if not isinstance(page_collection_complete, bool):
        return _batch_failure(records, HistoricalSessionAssemblyStatus.INCOMPLETE_PAGE_COLLECTION)
    if page_collection_complete is False or page.next_page_token is not None:
        return _batch_failure(records, HistoricalSessionAssemblyStatus.INCOMPLETE_PAGE_COLLECTION)

    current_session = _normalize_label(current_session_id)
    if not current_session:
        return _batch_failure(records, HistoricalSessionAssemblyStatus.INVALID_CURRENT_SESSION_ID)

    duplicate_keys = _duplicate_keys(records)
    results: list[HistoricalSessionAssemblyResult] = []
    for record in records:
        validation_result = _validate_record(
            record,
            current_session_id=current_session,
            duplicate_keys=duplicate_keys,
        )
        if validation_result is not None:
            results.append(validation_result)
            continue
        results.append(_assemble_record(page, record))
    return results
