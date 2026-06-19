from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    LocalJsonMetadataPreflightScenario,
)
from market_sentry.data.local_json_metadata_workflow_preflight import (
    LocalJsonMetadataWorkflowPreflightResult,
    run_local_json_metadata_workflow_preflight,
)


@dataclass(frozen=True)
class LocalJsonMetadataPreflightScenarioRun:
    scenario: LocalJsonMetadataPreflightScenario
    path: Path
    result: LocalJsonMetadataWorkflowPreflightResult


def run_local_json_metadata_preflight_scenario(
    scenario: LocalJsonMetadataPreflightScenario,
    path: Path,
) -> LocalJsonMetadataPreflightScenarioRun:
    if scenario.fixture_bytes is not None:
        path.write_bytes(scenario.fixture_bytes)

    result = run_local_json_metadata_workflow_preflight(
        path,
        scenario.collection,
        scenario.manifest_request,
        scenario.current_series,
        scenario.harness_request,
    )

    return LocalJsonMetadataPreflightScenarioRun(
        scenario=scenario,
        path=path,
        result=result,
    )
