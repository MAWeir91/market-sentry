"""Offline manifest-to-harness coordinator."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
    HistoricalSessionManifestResult,
    HistoricalSessionManifestStatus,
    adapt_historical_session_manifest,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
    HistoricalToTodRvolRunResult,
    HistoricalToTodRvolRunStatus,
    run_historical_to_time_of_day_rvol,
)
from market_sentry.data.intraday_bucket_adapter import IntradayVolumeSeriesInput


class ManifestToHarnessStatus:
    """Stable coordinator-level status/reason codes."""

    OK = "OK"
    MANIFEST_PARTIAL = "MANIFEST_PARTIAL"
    MANIFEST_FAILED = "MANIFEST_FAILED"
    HARNESS_FAILED = "HARNESS_FAILED"
    MANIFEST_PARTIAL_AND_HARNESS_FAILED = "MANIFEST_PARTIAL_AND_HARNESS_FAILED"


@dataclass(frozen=True)
class ManifestToHarnessResult:
    """Combined immutable artifacts from Phase 14I and Phase 14G."""

    manifest_result: HistoricalSessionManifestResult
    harness_result: HistoricalToTodRvolRunResult
    status: str
    reason: str | None = None


def _classify_status(
    manifest_result: HistoricalSessionManifestResult,
    harness_result: HistoricalToTodRvolRunResult,
) -> tuple[str, str | None]:
    if manifest_result.status == HistoricalSessionManifestStatus.OK:
        if harness_result.status == HistoricalToTodRvolRunStatus.OK:
            return ManifestToHarnessStatus.OK, None
        return (
            ManifestToHarnessStatus.HARNESS_FAILED,
            f"{ManifestToHarnessStatus.HARNESS_FAILED}:{harness_result.status}",
        )

    if manifest_result.status == HistoricalSessionManifestStatus.PARTIAL:
        if harness_result.status == HistoricalToTodRvolRunStatus.OK:
            return (
                ManifestToHarnessStatus.MANIFEST_PARTIAL,
                ManifestToHarnessStatus.MANIFEST_PARTIAL,
            )
        return (
            ManifestToHarnessStatus.MANIFEST_PARTIAL_AND_HARNESS_FAILED,
            (
                f"{ManifestToHarnessStatus.MANIFEST_PARTIAL_AND_HARNESS_FAILED}:"
                f"{harness_result.status}"
            ),
        )

    return (
        ManifestToHarnessStatus.MANIFEST_FAILED,
        f"{ManifestToHarnessStatus.MANIFEST_FAILED}:{manifest_result.status}",
    )


def run_manifest_to_historical_tod_rvol(
    raw_manifest_records: Sequence[object],
    manifest_request: HistoricalSessionManifestRequest,
    page: AlpacaHistoricalBarsPage,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> ManifestToHarnessResult:
    """Run manifest adaptation, then run the harness with emitted metadata."""

    manifest_result = adapt_historical_session_manifest(
        raw_manifest_records,
        manifest_request,
    )
    harness_result = run_historical_to_time_of_day_rvol(
        page,
        manifest_result.metadata_records,
        current_series,
        harness_request,
    )
    status, reason = _classify_status(manifest_result, harness_result)

    return ManifestToHarnessResult(
        manifest_result=manifest_result,
        harness_result=harness_result,
        status=status,
        reason=reason,
    )
