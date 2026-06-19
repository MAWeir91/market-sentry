from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsCollectedPage,
    HistoricalBarsPageCollectionRequest,
    HistoricalBarsPageCollectionResult,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)


class JsonHistoricalRvolBundleError(ValueError):
    """Raised for invalid local historical RVOL bundle envelopes or structures."""


@dataclass(frozen=True)
class LocalHistoricalRvolBundle:
    """Explicit local non-metadata inputs for one existing preflight run."""

    path: Path
    collection: HistoricalBarsPageCollectionResult
    manifest_request: HistoricalSessionManifestRequest
    current_series: IntradayVolumeSeriesInput
    harness_request: HistoricalToTodRvolRunRequest


def _bundle_error(message: str) -> JsonHistoricalRvolBundleError:
    return JsonHistoricalRvolBundleError(message)


def _required(mapping: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in mapping:
        raise _bundle_error(f"MISSING_REQUIRED_FIELD:{path}")
    return mapping[key]


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _bundle_error(f"INVALID_MAPPING:{path}")
    return value


def _sequence(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise _bundle_error(f"INVALID_SEQUENCE:{path}")
    return value


def _integer(value: Any, path: str) -> int:
    if type(value) is not int:
        raise _bundle_error(f"INVALID_INTEGER:{path}")
    return value


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise _bundle_error(f"INVALID_BOOLEAN:{path}")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise _bundle_error(f"INVALID_STRING_OR_NULL:{path}")
    return value


def _string_or_null(value: Any, path: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise _bundle_error(f"INVALID_STRING_OR_NULL:{path}")


def _decode_datetime_tag(value: str) -> datetime | None:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _decode_generic_tags(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_generic_tags(item) for item in value]
    if isinstance(value, dict):
        if tuple(value.keys()) == ("$datetime",):
            tag_value = value["$datetime"]
            if isinstance(tag_value, str):
                decoded = _decode_datetime_tag(tag_value)
                if decoded is not None:
                    return decoded
            return value
        return {
            key: _decode_generic_tags(item)
            for key, item in value.items()
        }
    return value


def _query(payload: Mapping[str, Any], path: str) -> AlpacaHistoricalBarsQuery:
    for key in ("timeframe", "start", "end", "limit", "page_token", "sort"):
        _required(payload, key, f"{path}.{key}")
    return AlpacaHistoricalBarsQuery(
        timeframe=_string(payload["timeframe"], f"{path}.timeframe"),
        start=_string(payload["start"], f"{path}.start"),
        end=_string(payload["end"], f"{path}.end"),
        limit=_integer(payload["limit"], f"{path}.limit"),
        page_token=_string_or_null(payload["page_token"], f"{path}.page_token"),
        sort=_string(payload["sort"], f"{path}.sort"),
    )


def _collection_request(
    payload: Mapping[str, Any],
) -> HistoricalBarsPageCollectionRequest:
    path = "collection.request"
    symbols = _sequence(_required(payload, "symbols", f"{path}.symbols"), f"{path}.symbols")
    initial_query = _mapping(
        _required(payload, "initial_query", f"{path}.initial_query"),
        f"{path}.initial_query",
    )
    max_pages = _integer(_required(payload, "max_pages", f"{path}.max_pages"), f"{path}.max_pages")
    return HistoricalBarsPageCollectionRequest(
        symbols=tuple(symbols),
        initial_query=_query(initial_query, f"{path}.initial_query"),
        max_pages=max_pages,
    )


def _historical_page(payload: Mapping[str, Any], path: str) -> AlpacaHistoricalBarsPage:
    requested_symbols = _sequence(
        _required(payload, "requested_symbols", f"{path}.requested_symbols"),
        f"{path}.requested_symbols",
    )
    bars_by_symbol_payload = _mapping(
        _required(payload, "bars_by_symbol", f"{path}.bars_by_symbol"),
        f"{path}.bars_by_symbol",
    )
    bars_by_symbol = {}
    for symbol, raw_bars in bars_by_symbol_payload.items():
        bars_path = f"{path}.bars_by_symbol"
        bars = _sequence(raw_bars, bars_path)
        normalized_bars = []
        for index, raw_bar in enumerate(bars):
            normalized_bars.append(_mapping(raw_bar, f"{bars_path}[{index}]"))
        bars_by_symbol[symbol] = tuple(normalized_bars)
    next_page_token = _string_or_null(
        _required(payload, "next_page_token", f"{path}.next_page_token"),
        f"{path}.next_page_token",
    )
    return AlpacaHistoricalBarsPage(
        requested_symbols=tuple(requested_symbols),
        bars_by_symbol=bars_by_symbol,
        next_page_token=next_page_token,
    )


def _collected_page(
    payload: Mapping[str, Any],
    index: int,
) -> HistoricalBarsCollectedPage:
    path = f"collection.collected_pages[{index}]"
    query_payload = _mapping(
        _required(payload, "query", f"{path}.query"),
        f"{path}.query",
    )
    page_payload = _mapping(
        _required(payload, "page", f"{path}.page"),
        f"{path}.page",
    )
    return HistoricalBarsCollectedPage(
        index=_integer(_required(payload, "index", f"{path}.index"), f"{path}.index"),
        query=_query(query_payload, f"{path}.query"),
        page=_historical_page(page_payload, f"{path}.page"),
    )


def _collection(payload: Mapping[str, Any]) -> HistoricalBarsPageCollectionResult:
    request_payload = _mapping(
        _required(payload, "request", "collection.request"),
        "collection.request",
    )
    collected_pages_payload = _sequence(
        _required(payload, "collected_pages", "collection.collected_pages"),
        "collection.collected_pages",
    )
    collected_pages = []
    for index, collected_page_payload in enumerate(collected_pages_payload):
        collected_pages.append(
            _collected_page(
                _mapping(
                    collected_page_payload,
                    f"collection.collected_pages[{index}]",
                ),
                index,
            )
        )
    return HistoricalBarsPageCollectionResult(
        request=_collection_request(request_payload),
        collected_pages=tuple(collected_pages),
        status=_string(_required(payload, "status", "collection.status"), "collection.status"),
        page_collection_complete=_boolean(
            _required(
                payload,
                "page_collection_complete",
                "collection.page_collection_complete",
            ),
            "collection.page_collection_complete",
        ),
        next_page_token=_string_or_null(
            _required(payload, "next_page_token", "collection.next_page_token"),
            "collection.next_page_token",
        ),
        reason=_string_or_null(
            _required(payload, "reason", "collection.reason"),
            "collection.reason",
        ),
    )


def _manifest_request(payload: Mapping[str, Any]) -> HistoricalSessionManifestRequest:
    return HistoricalSessionManifestRequest(
        symbol=_required(payload, "symbol", "manifest_request.symbol"),
        bucket=_required(payload, "bucket", "manifest_request.bucket"),
        current_session_id=_required(
            payload,
            "current_session_id",
            "manifest_request.current_session_id",
        ),
    )


def _current_series(payload: Mapping[str, Any]) -> IntradayVolumeSeriesInput:
    bars_payload = _sequence(
        _required(payload, "bars", "current_series.bars"),
        "current_series.bars",
    )
    bars = []
    for index, bar_payload in enumerate(bars_payload):
        bar_path = f"current_series.bars[{index}]"
        bar = _mapping(bar_payload, bar_path)
        bars.append(
            IntradayVolumeBar(
                timestamp=_required(bar, "timestamp", f"{bar_path}.timestamp"),
                volume=_required(bar, "volume", f"{bar_path}.volume"),
            )
        )
    return IntradayVolumeSeriesInput(
        symbol=_required(payload, "symbol", "current_series.symbol"),
        session_id=_required(payload, "session_id", "current_series.session_id"),
        bucket=_required(payload, "bucket", "current_series.bucket"),
        cutoff_timestamp=_required(
            payload,
            "cutoff_timestamp",
            "current_series.cutoff_timestamp",
        ),
        bars=tuple(bars),
    )


def _harness_request(payload: Mapping[str, Any]) -> HistoricalToTodRvolRunRequest:
    return HistoricalToTodRvolRunRequest(
        symbol=_required(payload, "symbol", "harness_request.symbol"),
        bucket=_required(payload, "bucket", "harness_request.bucket"),
        current_session_id=_required(
            payload,
            "current_session_id",
            "harness_request.current_session_id",
        ),
        page_collection_complete=_required(
            payload,
            "page_collection_complete",
            "harness_request.page_collection_complete",
        ),
        minimum_historical_sessions=_required(
            payload,
            "minimum_historical_sessions",
            "harness_request.minimum_historical_sessions",
        ),
    )


def _load_envelope(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise _bundle_error("INVALID_ENVELOPE_ROOT")
    if "schema_version" not in payload:
        raise _bundle_error("MISSING_SCHEMA_VERSION")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise _bundle_error("UNSUPPORTED_SCHEMA_VERSION")
    return _decode_generic_tags(dict(payload))


def load_local_historical_rvol_bundle(
    path: Path,
) -> LocalHistoricalRvolBundle:
    """Load one explicit local RVOL bundle into existing typed workflow inputs."""

    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path.")

    payload = _load_envelope(path)
    collection_payload = _mapping(
        _required(payload, "collection", "collection"),
        "collection",
    )
    manifest_request_payload = _mapping(
        _required(payload, "manifest_request", "manifest_request"),
        "manifest_request",
    )
    current_series_payload = _mapping(
        _required(payload, "current_series", "current_series"),
        "current_series",
    )
    harness_request_payload = _mapping(
        _required(payload, "harness_request", "harness_request"),
        "harness_request",
    )
    return LocalHistoricalRvolBundle(
        path=path,
        collection=_collection(collection_payload),
        manifest_request=_manifest_request(manifest_request_payload),
        current_series=_current_series(current_series_payload),
        harness_request=_harness_request(harness_request_payload),
    )
