from __future__ import annotations

from dataclasses import dataclass

from market_sentry.data.collected_pages_to_manifest_workflow import (
    CollectedPagesToManifestWorkflowResult,
    run_collected_pages_to_manifest_workflow,
)
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsPageCollectionResult,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
)
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSource,
    HistoricalSessionMetadataSourceLoadResult,
    HistoricalSessionMetadataSourceLoadStatus,
    load_historical_session_metadata_source,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
)
from market_sentry.data.intraday_bucket_adapter import IntradayVolumeSeriesInput


class MetadataLoadedHistoricalWorkflowStatus:
    WORKFLOW_BRIDGE_RAN = "WORKFLOW_BRIDGE_RAN"
    METADATA_NOT_LOADED = "METADATA_NOT_LOADED"


@dataclass(frozen=True)
class MetadataLoadedHistoricalWorkflowResult:
    metadata_source: HistoricalSessionMetadataSource
    source_collection: HistoricalBarsPageCollectionResult
    metadata_load_result: HistoricalSessionMetadataSourceLoadResult
    workflow_bridge_result: CollectedPagesToManifestWorkflowResult | None
    status: str
    reason: str | None = None


def run_metadata_loaded_historical_workflow(
    metadata_source: HistoricalSessionMetadataSource,
    collection: HistoricalBarsPageCollectionResult,
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> MetadataLoadedHistoricalWorkflowResult:
    metadata_load_result = load_historical_session_metadata_source(
        metadata_source,
        manifest_request,
    )

    if metadata_load_result.status != HistoricalSessionMetadataSourceLoadStatus.LOADED:
        return MetadataLoadedHistoricalWorkflowResult(
            metadata_source=metadata_source,
            source_collection=collection,
            metadata_load_result=metadata_load_result,
            workflow_bridge_result=None,
            status=MetadataLoadedHistoricalWorkflowStatus.METADATA_NOT_LOADED,
            reason=(
                f"{MetadataLoadedHistoricalWorkflowStatus.METADATA_NOT_LOADED}:"
                f"{metadata_load_result.status}"
            ),
        )

    if metadata_load_result.raw_manifest_records is None:
        raise RuntimeError("LOADED metadata result must include raw manifest records.")

    workflow_bridge_result = run_collected_pages_to_manifest_workflow(
        collection,
        metadata_load_result.raw_manifest_records,
        manifest_request,
        current_series,
        harness_request,
    )
    return MetadataLoadedHistoricalWorkflowResult(
        metadata_source=metadata_source,
        source_collection=collection,
        metadata_load_result=metadata_load_result,
        workflow_bridge_result=workflow_bridge_result,
        status=MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN,
        reason=None,
    )
