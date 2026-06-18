from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionResult,
    CollectedHistoricalPagesCompositionStatus,
    compose_collected_historical_pages,
)
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsPageCollectionResult,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
)
from market_sentry.data.intraday_bucket_adapter import IntradayVolumeSeriesInput
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessResult,
    run_manifest_to_historical_tod_rvol,
)


class CollectedPagesToManifestWorkflowStatus:
    WORKFLOW_RAN = "WORKFLOW_RAN"
    COLLECTION_NOT_COMPOSABLE = "COLLECTION_NOT_COMPOSABLE"


@dataclass(frozen=True)
class CollectedPagesToManifestWorkflowResult:
    source_collection: HistoricalBarsPageCollectionResult
    composition_result: CollectedHistoricalPagesCompositionResult
    workflow_result: ManifestToHarnessResult | None
    status: str
    reason: str | None = None


def run_collected_pages_to_manifest_workflow(
    collection: HistoricalBarsPageCollectionResult,
    raw_manifest_records: Sequence[object],
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> CollectedPagesToManifestWorkflowResult:
    composition_result = compose_collected_historical_pages(collection)

    if (
        composition_result.status
        != CollectedHistoricalPagesCompositionStatus.COMPOSED
    ):
        return CollectedPagesToManifestWorkflowResult(
            source_collection=collection,
            composition_result=composition_result,
            workflow_result=None,
            status=CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE,
            reason=(
                f"{CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE}:"
                f"{composition_result.status}"
            ),
        )

    if composition_result.composed_page is None:
        raise RuntimeError("COMPOSED result must include a composed page.")

    workflow_result = run_manifest_to_historical_tod_rvol(
        raw_manifest_records,
        manifest_request,
        composition_result.composed_page,
        current_series,
        harness_request,
    )
    return CollectedPagesToManifestWorkflowResult(
        source_collection=collection,
        composition_result=composition_result,
        workflow_result=workflow_result,
        status=CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN,
        reason=None,
    )
