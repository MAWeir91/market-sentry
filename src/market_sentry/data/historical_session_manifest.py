"""Offline historical-session manifest adapter."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from market_sentry.data.historical_session_assembly import (
    HistoricalIntradaySessionMetadata,
)


REQUIRED_FIELDS = (
    "symbol",
    "session_id",
    "bucket",
    "session_start_timestamp",
    "session_end_timestamp",
    "cutoff_timestamp",
    "is_complete",
)


class HistoricalSessionManifestStatus:
    """Stable manifest-level status/reason codes."""

    OK = "OK"
    PARTIAL = "PARTIAL"
    NO_VALID_METADATA = "NO_VALID_METADATA"
    INVALID_TARGET_SYMBOL = "INVALID_TARGET_SYMBOL"
    INVALID_TARGET_BUCKET = "INVALID_TARGET_BUCKET"
    INVALID_CURRENT_SESSION_ID = "INVALID_CURRENT_SESSION_ID"


class HistoricalSessionManifestRecordStatus:
    """Stable per-record status/reason codes."""

    OK = "OK"
    INVALID_RECORD = "INVALID_RECORD"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    EMPTY_SYMBOL = "EMPTY_SYMBOL"
    MISMATCHED_MANIFEST_SYMBOL = "MISMATCHED_MANIFEST_SYMBOL"
    EMPTY_SESSION_ID = "EMPTY_SESSION_ID"
    CURRENT_SESSION_IN_HISTORY = "CURRENT_SESSION_IN_HISTORY"
    EMPTY_BUCKET = "EMPTY_BUCKET"
    MISMATCHED_MANIFEST_BUCKET = "MISMATCHED_MANIFEST_BUCKET"
    INVALID_SESSION_START_TIMESTAMP = "INVALID_SESSION_START_TIMESTAMP"
    INVALID_SESSION_END_TIMESTAMP = "INVALID_SESSION_END_TIMESTAMP"
    INVALID_CUTOFF_TIMESTAMP = "INVALID_CUTOFF_TIMESTAMP"
    NAIVE_SESSION_TIMESTAMP = "NAIVE_SESSION_TIMESTAMP"
    MISMATCHED_SESSION_TIMEZONE = "MISMATCHED_SESSION_TIMEZONE"
    INVALID_SESSION_WINDOW = "INVALID_SESSION_WINDOW"
    INVALID_CUTOFF_OUTSIDE_SESSION = "INVALID_CUTOFF_OUTSIDE_SESSION"
    INVALID_IS_COMPLETE = "INVALID_IS_COMPLETE"
    INCOMPLETE_SESSION = "INCOMPLETE_SESSION"
    DUPLICATE_HISTORICAL_SESSION_ID = "DUPLICATE_HISTORICAL_SESSION_ID"


@dataclass(frozen=True)
class HistoricalSessionManifestRequest:
    """Target identity for one caller-supplied historical metadata manifest."""

    symbol: str
    bucket: str
    current_session_id: str


@dataclass(frozen=True)
class HistoricalSessionManifestRecordResult:
    """Inspectable outcome for one raw manifest record."""

    index: int
    source_record: Mapping[str, object] | None
    metadata: HistoricalIntradaySessionMetadata | None
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class HistoricalSessionManifestResult:
    """Validated metadata records and diagnostics for one manifest."""

    request: HistoricalSessionManifestRequest
    record_results: tuple[HistoricalSessionManifestRecordResult, ...]
    metadata_records: tuple[HistoricalIntradaySessionMetadata, ...]
    valid_record_count: int
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class _ValidatedRecord:
    index: int
    source_record: Mapping[str, object]
    metadata: HistoricalIntradaySessionMetadata
    duplicate_key: tuple[str, str]


def _protected_source(record: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(record))


def _normalize_symbol(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().upper()


def _normalize_label(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _is_aware_datetime(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _request_error(
    request: HistoricalSessionManifestRequest,
    status: str,
) -> HistoricalSessionManifestResult:
    return HistoricalSessionManifestResult(
        request=request,
        record_results=(),
        metadata_records=(),
        valid_record_count=0,
        status=status,
        reason=status,
    )


def _record_failure(
    *,
    index: int,
    source_record: Mapping[str, object] | None,
    status: str,
    reason: str | None = None,
) -> HistoricalSessionManifestRecordResult:
    return HistoricalSessionManifestRecordResult(
        index=index,
        source_record=source_record,
        metadata=None,
        status=status,
        reason=reason if reason is not None else status,
    )


def _validate_request(
    request: HistoricalSessionManifestRequest,
) -> tuple[str, str, str, str | None]:
    symbol = _normalize_symbol(request.symbol)
    bucket = _normalize_label(request.bucket)
    current_session_id = _normalize_label(request.current_session_id)

    if not symbol:
        return symbol, bucket, current_session_id, (
            HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL
        )
    if not bucket:
        return symbol, bucket, current_session_id, (
            HistoricalSessionManifestStatus.INVALID_TARGET_BUCKET
        )
    if not current_session_id:
        return symbol, bucket, current_session_id, (
            HistoricalSessionManifestStatus.INVALID_CURRENT_SESSION_ID
        )
    return symbol, bucket, current_session_id, None


def _invalid_timestamp_status(field_name: str) -> str:
    if field_name == "session_start_timestamp":
        return HistoricalSessionManifestRecordStatus.INVALID_SESSION_START_TIMESTAMP
    if field_name == "session_end_timestamp":
        return HistoricalSessionManifestRecordStatus.INVALID_SESSION_END_TIMESTAMP
    return HistoricalSessionManifestRecordStatus.INVALID_CUTOFF_TIMESTAMP


def _validate_mapping_record(
    *,
    index: int,
    raw_record: Mapping[str, object],
    target_symbol: str,
    target_bucket: str,
    current_session_id: str,
) -> HistoricalSessionManifestRecordResult | _ValidatedRecord:
    source_record = _protected_source(raw_record)

    for field_name in REQUIRED_FIELDS:
        if field_name not in raw_record:
            return _record_failure(
                index=index,
                source_record=source_record,
                status=HistoricalSessionManifestRecordStatus.MISSING_REQUIRED_FIELD,
                reason=(
                    f"{HistoricalSessionManifestRecordStatus.MISSING_REQUIRED_FIELD}:"
                    f"{field_name}"
                ),
            )

    symbol = _normalize_symbol(raw_record["symbol"])
    if not symbol:
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.EMPTY_SYMBOL,
        )
    if symbol != target_symbol:
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.MISMATCHED_MANIFEST_SYMBOL,
        )

    session_id = _normalize_label(raw_record["session_id"])
    if not session_id:
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.EMPTY_SESSION_ID,
        )
    if session_id == current_session_id:
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.CURRENT_SESSION_IN_HISTORY,
        )

    bucket = _normalize_label(raw_record["bucket"])
    if not bucket:
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.EMPTY_BUCKET,
        )
    if bucket != target_bucket:
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.MISMATCHED_MANIFEST_BUCKET,
        )

    timestamps: list[datetime] = []
    for field_name in (
        "session_start_timestamp",
        "session_end_timestamp",
        "cutoff_timestamp",
    ):
        value = raw_record[field_name]
        if not isinstance(value, datetime):
            return _record_failure(
                index=index,
                source_record=source_record,
                status=_invalid_timestamp_status(field_name),
            )
        timestamps.append(value)

    start, end, cutoff = timestamps
    if not all(_is_aware_datetime(value) for value in timestamps):
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.NAIVE_SESSION_TIMESTAMP,
        )
    if start.tzinfo != end.tzinfo or start.tzinfo != cutoff.tzinfo:
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.MISMATCHED_SESSION_TIMEZONE,
        )
    if not start < end:
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.INVALID_SESSION_WINDOW,
        )
    if not start <= cutoff < end:
        return _record_failure(
            index=index,
            source_record=source_record,
            status=(
                HistoricalSessionManifestRecordStatus.INVALID_CUTOFF_OUTSIDE_SESSION
            ),
        )

    is_complete = raw_record["is_complete"]
    if not isinstance(is_complete, bool):
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.INVALID_IS_COMPLETE,
        )
    if is_complete is False:
        return _record_failure(
            index=index,
            source_record=source_record,
            status=HistoricalSessionManifestRecordStatus.INCOMPLETE_SESSION,
        )

    metadata = HistoricalIntradaySessionMetadata(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        session_start_timestamp=start,
        session_end_timestamp=end,
        cutoff_timestamp=cutoff,
        is_complete=True,
    )
    return _ValidatedRecord(
        index=index,
        source_record=source_record,
        metadata=metadata,
        duplicate_key=(symbol, session_id),
    )


def adapt_historical_session_manifest(
    raw_records: Sequence[object],
    request: HistoricalSessionManifestRequest,
) -> HistoricalSessionManifestResult:
    """Adapt explicit raw manifest records into ordered session metadata."""

    target_symbol, target_bucket, current_session_id, request_error = (
        _validate_request(request)
    )
    if request_error is not None:
        return _request_error(request, request_error)

    intermediate: list[HistoricalSessionManifestRecordResult | _ValidatedRecord] = []
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, Mapping):
            intermediate.append(
                _record_failure(
                    index=index,
                    source_record=None,
                    status=HistoricalSessionManifestRecordStatus.INVALID_RECORD,
                )
            )
            continue
        intermediate.append(
            _validate_mapping_record(
                index=index,
                raw_record=raw_record,
                target_symbol=target_symbol,
                target_bucket=target_bucket,
                current_session_id=current_session_id,
            )
        )

    duplicate_counts = Counter(
        item.duplicate_key for item in intermediate if isinstance(item, _ValidatedRecord)
    )
    record_results: list[HistoricalSessionManifestRecordResult] = []
    metadata_records: list[HistoricalIntradaySessionMetadata] = []
    for item in intermediate:
        if isinstance(item, HistoricalSessionManifestRecordResult):
            record_results.append(item)
            continue
        if duplicate_counts[item.duplicate_key] > 1:
            record_results.append(
                _record_failure(
                    index=item.index,
                    source_record=item.source_record,
                    status=(
                        HistoricalSessionManifestRecordStatus.DUPLICATE_HISTORICAL_SESSION_ID
                    ),
                )
            )
            continue
        record_results.append(
            HistoricalSessionManifestRecordResult(
                index=item.index,
                source_record=item.source_record,
                metadata=item.metadata,
                status=HistoricalSessionManifestRecordStatus.OK,
                reason=None,
            )
        )
        metadata_records.append(item.metadata)

    record_results_tuple = tuple(record_results)
    metadata_records_tuple = tuple(metadata_records)
    valid_record_count = len(metadata_records_tuple)
    if valid_record_count == 0:
        status = HistoricalSessionManifestStatus.NO_VALID_METADATA
        reason = status
    elif valid_record_count == len(record_results_tuple):
        status = HistoricalSessionManifestStatus.OK
        reason = None
    else:
        status = HistoricalSessionManifestStatus.PARTIAL
        reason = status

    return HistoricalSessionManifestResult(
        request=request,
        record_results=record_results_tuple,
        metadata_records=metadata_records_tuple,
        valid_record_count=valid_record_count,
        status=status,
        reason=reason,
    )
