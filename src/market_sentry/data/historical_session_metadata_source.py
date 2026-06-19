from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
)


class HistoricalSessionMetadataSourceLoadStatus:
    LOADED = "LOADED"
    INVALID_RECORD_SEQUENCE = "INVALID_RECORD_SEQUENCE"


@runtime_checkable
class HistoricalSessionMetadataSource(Protocol):
    def load_raw_manifest_records(
        self,
        request: HistoricalSessionManifestRequest,
    ) -> Sequence[object]:
        ...


@dataclass(frozen=True)
class StaticHistoricalSessionMetadataSource:
    raw_manifest_records: Sequence[object]

    def load_raw_manifest_records(
        self,
        request: HistoricalSessionManifestRequest,
    ) -> Sequence[object]:
        return self.raw_manifest_records


@dataclass(frozen=True)
class HistoricalSessionMetadataSourceLoadResult:
    source: HistoricalSessionMetadataSource
    request: HistoricalSessionManifestRequest
    raw_manifest_records: Sequence[object] | None
    status: str
    reason: str | None = None


def _is_valid_record_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray, memoryview),
    )


def load_historical_session_metadata_source(
    source: HistoricalSessionMetadataSource,
    request: HistoricalSessionManifestRequest,
) -> HistoricalSessionMetadataSourceLoadResult:
    raw_manifest_records = source.load_raw_manifest_records(request)

    if not _is_valid_record_sequence(raw_manifest_records):
        return HistoricalSessionMetadataSourceLoadResult(
            source=source,
            request=request,
            raw_manifest_records=None,
            status=HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE,
            reason=HistoricalSessionMetadataSourceLoadStatus.INVALID_RECORD_SEQUENCE,
        )

    return HistoricalSessionMetadataSourceLoadResult(
        source=source,
        request=request,
        raw_manifest_records=raw_manifest_records,
        status=HistoricalSessionMetadataSourceLoadStatus.LOADED,
        reason=None,
    )
