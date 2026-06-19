from __future__ import annotations

from dataclasses import dataclass

from market_sentry.data.metadata_loaded_historical_workflow import (
    MetadataLoadedHistoricalWorkflowResult,
    run_metadata_loaded_historical_workflow,
)
from market_sentry.data.metadata_loaded_historical_workflow_scenario_catalog import (
    MetadataLoadedHistoricalWorkflowScenario,
)


@dataclass(frozen=True)
class MetadataLoadedHistoricalWorkflowScenarioRun:
    scenario: MetadataLoadedHistoricalWorkflowScenario
    result: MetadataLoadedHistoricalWorkflowResult


def run_metadata_loaded_historical_workflow_scenario(
    scenario: MetadataLoadedHistoricalWorkflowScenario,
) -> MetadataLoadedHistoricalWorkflowScenarioRun:
    result = run_metadata_loaded_historical_workflow(
        scenario.metadata_source,
        scenario.collection,
        scenario.manifest_request,
        scenario.current_series,
        scenario.harness_request,
    )
    return MetadataLoadedHistoricalWorkflowScenarioRun(
        scenario=scenario,
        result=result,
    )
