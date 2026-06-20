from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from market_sentry.data.alpaca_historical_bars_adapter import (
    AlpacaHistoricalBarsAdapterStatus,
    AlpacaHistoricalBarsIntradaySeriesRequest,
    AlpacaHistoricalBarsIntradaySeriesResult,
    build_intraday_series_from_historical_bars,
)
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsFetcher,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionResult,
    CollectedHistoricalPagesCompositionStatus,
    compose_collected_historical_pages,
)
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsPageCollectionRequest,
    HistoricalBarsPageCollectionResult,
    collect_historical_bars_pages,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
)
from market_sentry.data.json_historical_rvol_bundle_writer import (
    write_local_historical_rvol_bundle,
)


class ExplicitAlpacaRvolBundleCaptureStatus:
    """Stable status/reason codes for one explicit capture request."""

    BUNDLE_WRITTEN = "BUNDLE_WRITTEN"
    LIVE_DATA_NOT_ALLOWED = "LIVE_DATA_NOT_ALLOWED"
    CURRENT_COLLECTION_NOT_COMPOSABLE = "CURRENT_COLLECTION_NOT_COMPOSABLE"
    CURRENT_SERIES_ADAPTATION_FAILED = "CURRENT_SERIES_ADAPTATION_FAILED"


@dataclass(frozen=True)
class ExplicitAlpacaRvolBundleCaptureRequest:
    """All caller-selected controls for one manual Alpaca bundle capture."""

    symbol: str
    historical_initial_query: AlpacaHistoricalBarsQuery
    historical_max_pages: int
    current_initial_query: AlpacaHistoricalBarsQuery
    current_max_pages: int
    current_session_id: str
    bucket: str
    cutoff_timestamp: datetime
    minimum_historical_sessions: int
    output_path: Path
    allow_live_data: bool


@dataclass(frozen=True)
class ExplicitAlpacaRvolBundleCaptureResult:
    """Inspectable artifacts from one explicit Alpaca bundle capture."""

    request: ExplicitAlpacaRvolBundleCaptureRequest
    output_path: Path
    historical_collection: HistoricalBarsPageCollectionResult | None
    current_collection: HistoricalBarsPageCollectionResult | None
    current_composition: CollectedHistoricalPagesCompositionResult | None
    current_series_result: AlpacaHistoricalBarsIntradaySeriesResult | None
    manifest_request: HistoricalSessionManifestRequest | None
    harness_request: HistoricalToTodRvolRunRequest | None
    output_written: bool
    status: str
    reason: str | None = None


def _result(
    *,
    request: ExplicitAlpacaRvolBundleCaptureRequest,
    historical_collection: HistoricalBarsPageCollectionResult | None = None,
    current_collection: HistoricalBarsPageCollectionResult | None = None,
    current_composition: CollectedHistoricalPagesCompositionResult | None = None,
    current_series_result: AlpacaHistoricalBarsIntradaySeriesResult | None = None,
    manifest_request: HistoricalSessionManifestRequest | None = None,
    harness_request: HistoricalToTodRvolRunRequest | None = None,
    output_written: bool,
    status: str,
    reason: str | None = None,
) -> ExplicitAlpacaRvolBundleCaptureResult:
    return ExplicitAlpacaRvolBundleCaptureResult(
        request=request,
        output_path=request.output_path,
        historical_collection=historical_collection,
        current_collection=current_collection,
        current_composition=current_composition,
        current_series_result=current_series_result,
        manifest_request=manifest_request,
        harness_request=harness_request,
        output_written=output_written,
        status=status,
        reason=reason,
    )


def capture_explicit_alpaca_rvol_bundle(
    fetcher: AlpacaHistoricalBarsFetcher,
    request: ExplicitAlpacaRvolBundleCaptureRequest,
) -> ExplicitAlpacaRvolBundleCaptureResult:
    """Capture one explicit Alpaca historical/current bar bundle."""

    if not isinstance(request.output_path, Path):
        raise TypeError("output_path must be a pathlib.Path.")

    if request.allow_live_data is not True:
        return _result(
            request=request,
            output_written=False,
            status=ExplicitAlpacaRvolBundleCaptureStatus.LIVE_DATA_NOT_ALLOWED,
            reason=ExplicitAlpacaRvolBundleCaptureStatus.LIVE_DATA_NOT_ALLOWED,
        )

    historical_request = HistoricalBarsPageCollectionRequest(
        symbols=(request.symbol,),
        initial_query=request.historical_initial_query,
        max_pages=request.historical_max_pages,
    )
    historical_collection = collect_historical_bars_pages(
        fetcher,
        historical_request,
    )

    current_request = HistoricalBarsPageCollectionRequest(
        symbols=(request.symbol,),
        initial_query=request.current_initial_query,
        max_pages=request.current_max_pages,
    )
    current_collection = collect_historical_bars_pages(fetcher, current_request)
    current_composition = compose_collected_historical_pages(current_collection)

    if current_composition.status != CollectedHistoricalPagesCompositionStatus.COMPOSED:
        return _result(
            request=request,
            historical_collection=historical_collection,
            current_collection=current_collection,
            current_composition=current_composition,
            output_written=False,
            status=(
                ExplicitAlpacaRvolBundleCaptureStatus.CURRENT_COLLECTION_NOT_COMPOSABLE
            ),
            reason=(
                f"{ExplicitAlpacaRvolBundleCaptureStatus.CURRENT_COLLECTION_NOT_COMPOSABLE}:"
                f"{current_composition.status}"
            ),
        )

    adapter_request = AlpacaHistoricalBarsIntradaySeriesRequest(
        symbol=request.symbol,
        session_id=request.current_session_id,
        bucket=request.bucket,
        cutoff_timestamp=request.cutoff_timestamp,
    )
    current_series_result = build_intraday_series_from_historical_bars(
        current_composition.composed_page,
        adapter_request,
    )

    if current_series_result.status != AlpacaHistoricalBarsAdapterStatus.OK:
        return _result(
            request=request,
            historical_collection=historical_collection,
            current_collection=current_collection,
            current_composition=current_composition,
            current_series_result=current_series_result,
            output_written=False,
            status=(
                ExplicitAlpacaRvolBundleCaptureStatus.CURRENT_SERIES_ADAPTATION_FAILED
            ),
            reason=(
                f"{ExplicitAlpacaRvolBundleCaptureStatus.CURRENT_SERIES_ADAPTATION_FAILED}:"
                f"{current_series_result.status}"
            ),
        )

    manifest_request = HistoricalSessionManifestRequest(
        symbol=request.symbol,
        bucket=request.bucket,
        current_session_id=request.current_session_id,
    )
    harness_request = HistoricalToTodRvolRunRequest(
        symbol=request.symbol,
        bucket=request.bucket,
        current_session_id=request.current_session_id,
        page_collection_complete=historical_collection.page_collection_complete,
        minimum_historical_sessions=request.minimum_historical_sessions,
    )

    write_local_historical_rvol_bundle(
        request.output_path,
        historical_collection,
        manifest_request,
        current_series_result.intraday_series,
        harness_request,
    )

    return _result(
        request=request,
        historical_collection=historical_collection,
        current_collection=current_collection,
        current_composition=current_composition,
        current_series_result=current_series_result,
        manifest_request=manifest_request,
        harness_request=harness_request,
        output_written=True,
        status=ExplicitAlpacaRvolBundleCaptureStatus.BUNDLE_WRITTEN,
        reason=None,
    )
