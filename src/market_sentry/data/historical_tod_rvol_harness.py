"""Offline historical-to-time-of-day RVOL harness."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
)
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolResult,
    CurrentSessionTimeOfDayRvolStatus,
    compose_current_session_time_of_day_rvol,
)
from market_sentry.data.historical_baseline_composition import (
    HistoricalBaselineCompositionRequest,
    HistoricalBaselineCompositionResult,
    compose_historical_baseline,
)
from market_sentry.data.historical_session_assembly import (
    HistoricalIntradaySessionMetadata,
    HistoricalSessionAssemblyResult,
    assemble_historical_sessions_from_page,
)
from market_sentry.data.intraday_bucket_adapter import IntradayVolumeSeriesInput
from market_sentry.data.time_of_day_rvol import DEFAULT_MINIMUM_HISTORICAL_SESSIONS


class HistoricalToTodRvolRunStatus:
    """Stable status/reason codes for one offline harness run."""

    OK = "OK"
    FINAL_COMPOSITION_FAILED = "FINAL_COMPOSITION_FAILED"


@dataclass(frozen=True)
class HistoricalToTodRvolRunRequest:
    """Explicit controls for one complete offline historical-to-TOD run."""

    symbol: str
    bucket: str
    current_session_id: str
    page_collection_complete: bool
    minimum_historical_sessions: int = DEFAULT_MINIMUM_HISTORICAL_SESSIONS


@dataclass(frozen=True)
class HistoricalToTodRvolRunResult:
    """Inspectable artifacts from one full offline historical-to-TOD run."""

    request: HistoricalToTodRvolRunRequest
    baseline_request: HistoricalBaselineCompositionRequest
    assembly_results: tuple[HistoricalSessionAssemblyResult, ...]
    baseline_result: HistoricalBaselineCompositionResult
    final_result: CurrentSessionTimeOfDayRvolResult
    status: str
    reason: str | None = None


def run_historical_to_time_of_day_rvol(
    page: AlpacaHistoricalBarsPage,
    historical_metadata_records: Sequence[HistoricalIntradaySessionMetadata],
    current_series: IntradayVolumeSeriesInput,
    request: HistoricalToTodRvolRunRequest,
) -> HistoricalToTodRvolRunResult:
    """Run existing offline stages and preserve their artifacts."""

    metadata_records_tuple = tuple(historical_metadata_records)
    assembly_results = assemble_historical_sessions_from_page(
        page,
        metadata_records_tuple,
        current_session_id=request.current_session_id,
        page_collection_complete=request.page_collection_complete,
    )
    assembly_results_tuple = tuple(assembly_results)

    baseline_request = HistoricalBaselineCompositionRequest(
        symbol=request.symbol,
        bucket=request.bucket,
        current_session_id=request.current_session_id,
        minimum_historical_sessions=request.minimum_historical_sessions,
    )
    baseline_result = compose_historical_baseline(
        assembly_results_tuple,
        baseline_request,
    )
    final_result = compose_current_session_time_of_day_rvol(
        current_series,
        baseline_result,
    )

    if final_result.status == CurrentSessionTimeOfDayRvolStatus.OK:
        return HistoricalToTodRvolRunResult(
            request=request,
            baseline_request=baseline_request,
            assembly_results=assembly_results_tuple,
            baseline_result=baseline_result,
            final_result=final_result,
            status=HistoricalToTodRvolRunStatus.OK,
            reason=None,
        )

    return HistoricalToTodRvolRunResult(
        request=request,
        baseline_request=baseline_request,
        assembly_results=assembly_results_tuple,
        baseline_result=baseline_result,
        final_result=final_result,
        status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
        reason=(
            f"{HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED}:"
            f"{final_result.status}"
        ),
    )
