from collections.abc import Mapping
from datetime import datetime
import json
import math
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


class JsonHistoricalRvolBundleWriteError(ValueError):
    """Raised when bundle inputs cannot be represented as canonical JSON."""


def _datetime_tag(value: datetime) -> dict[str, str]:
    rendered = value.isoformat()
    if rendered.endswith("+00:00"):
        rendered = f"{rendered[:-6]}Z"
    return {"$datetime": rendered}


def _encode_json_value(value: Any, path: str) -> Any:
    if value is None or isinstance(value, bool | str | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise JsonHistoricalRvolBundleWriteError(f"NON_FINITE_FLOAT:{path}")
        return value
    if isinstance(value, datetime):
        return _datetime_tag(value)
    if isinstance(value, list | tuple):
        return [
            _encode_json_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        encoded: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise JsonHistoricalRvolBundleWriteError(
                    f"INVALID_MAPPING_KEY:{path}"
                )
            encoded[key] = _encode_json_value(item, f"{path}.{key}")
        return encoded
    raise JsonHistoricalRvolBundleWriteError(f"UNSUPPORTED_VALUE:{path}")


def _query(query: AlpacaHistoricalBarsQuery) -> dict[str, Any]:
    return {
        "timeframe": query.timeframe,
        "start": query.start,
        "end": query.end,
        "limit": query.limit,
        "page_token": query.page_token,
        "sort": query.sort,
    }


def _collection_request(
    request: HistoricalBarsPageCollectionRequest,
) -> dict[str, Any]:
    return {
        "symbols": list(request.symbols),
        "initial_query": _query(request.initial_query),
        "max_pages": request.max_pages,
    }


def _page(page: AlpacaHistoricalBarsPage) -> dict[str, Any]:
    return {
        "requested_symbols": list(page.requested_symbols),
        "bars_by_symbol": page.bars_by_symbol,
        "next_page_token": page.next_page_token,
    }


def _collected_page(page: HistoricalBarsCollectedPage) -> dict[str, Any]:
    return {
        "index": page.index,
        "query": _query(page.query),
        "page": _page(page.page),
    }


def _collection(collection: HistoricalBarsPageCollectionResult) -> dict[str, Any]:
    return {
        "request": _collection_request(collection.request),
        "collected_pages": [
            _collected_page(page) for page in collection.collected_pages
        ],
        "status": collection.status,
        "page_collection_complete": collection.page_collection_complete,
        "next_page_token": collection.next_page_token,
        "reason": collection.reason,
    }


def _manifest_request(
    request: HistoricalSessionManifestRequest,
) -> dict[str, Any]:
    return {
        "symbol": request.symbol,
        "bucket": request.bucket,
        "current_session_id": request.current_session_id,
    }


def _intraday_bar(bar: IntradayVolumeBar) -> dict[str, Any]:
    return {
        "timestamp": bar.timestamp,
        "volume": bar.volume,
    }


def _current_series(series: IntradayVolumeSeriesInput) -> dict[str, Any]:
    return {
        "symbol": series.symbol,
        "session_id": series.session_id,
        "bucket": series.bucket,
        "cutoff_timestamp": series.cutoff_timestamp,
        "bars": [_intraday_bar(bar) for bar in series.bars],
    }


def _harness_request(
    request: HistoricalToTodRvolRunRequest,
) -> dict[str, Any]:
    return {
        "symbol": request.symbol,
        "bucket": request.bucket,
        "current_session_id": request.current_session_id,
        "page_collection_complete": request.page_collection_complete,
        "minimum_historical_sessions": request.minimum_historical_sessions,
    }


def render_local_historical_rvol_bundle(
    collection: HistoricalBarsPageCollectionResult,
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> str:
    """Return canonical schema-version-one local RVOL bundle JSON text."""

    envelope = {
        "schema_version": 1,
        "collection": _collection(collection),
        "manifest_request": _manifest_request(manifest_request),
        "current_series": _current_series(current_series),
        "harness_request": _harness_request(harness_request),
    }
    encoded = _encode_json_value(envelope, "")
    return (
        json.dumps(
            encoded,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def write_local_historical_rvol_bundle(
    path: Path,
    collection: HistoricalBarsPageCollectionResult,
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> None:
    """Render and write one canonical local historical RVOL bundle."""

    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path.")
    rendered = render_local_historical_rvol_bundle(
        collection,
        manifest_request,
        current_series,
        harness_request,
    )
    path.write_text(rendered, encoding="utf-8")
