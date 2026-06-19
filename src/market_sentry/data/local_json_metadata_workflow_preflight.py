from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
from market_sentry.data.json_historical_session_metadata_source import (
    JsonHistoricalSessionMetadataFileSource,
)
from market_sentry.data.metadata_loaded_historical_workflow import (
    MetadataLoadedHistoricalWorkflowResult,
    run_metadata_loaded_historical_workflow,
)


@dataclass(frozen=True)
class LocalJsonMetadataWorkflowPreflightResult:
    path: Path
    metadata_source: JsonHistoricalSessionMetadataFileSource
    workflow_result: MetadataLoadedHistoricalWorkflowResult


def run_local_json_metadata_workflow_preflight(
    path: Path,
    collection: HistoricalBarsPageCollectionResult,
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> LocalJsonMetadataWorkflowPreflightResult:
    metadata_source = JsonHistoricalSessionMetadataFileSource(path=path)

    workflow_result = run_metadata_loaded_historical_workflow(
        metadata_source,
        collection,
        manifest_request,
        current_series,
        harness_request,
    )

    return LocalJsonMetadataWorkflowPreflightResult(
        path=path,
        metadata_source=metadata_source,
        workflow_result=workflow_result,
    )
