from __future__ import annotations

import json
from pathlib import Path

from market_sentry.data.json_historical_session_metadata_source import (
    JsonHistoricalSessionMetadataFileSourceError,
)
from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    get_local_json_metadata_preflight_scenario,
)
from market_sentry.data.local_json_metadata_workflow_preflight import (
    LocalJsonMetadataWorkflowPreflightResult,
    run_local_json_metadata_workflow_preflight,
)


PROFILE_NAME = "valid_json_complete_multi_page"
LOCAL_JSON_PREFLIGHT_NOTE = (
    "Note: This command reads only the explicit local JSON path. It does not "
    "activate providers, scan candidates, call APIs, or play voice alerts."
)


def run_manual_local_json_preflight(
    path: Path,
) -> LocalJsonMetadataWorkflowPreflightResult:
    scenario = get_local_json_metadata_preflight_scenario(PROFILE_NAME)

    return run_local_json_metadata_workflow_preflight(
        path,
        scenario.collection,
        scenario.manifest_request,
        scenario.current_series,
        scenario.harness_request,
    )


def _value_or_na(value: object) -> str:
    if value is None:
        return "N/A"
    return str(value)


def _relative_volume_or_na(value: object) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.1f}x"


def render_manual_local_json_preflight_report(
    path: Path,
    result: LocalJsonMetadataWorkflowPreflightResult,
) -> str:
    workflow_result = result.workflow_result
    metadata_load = workflow_result.metadata_load_result
    bridge = workflow_result.workflow_bridge_result
    composition = bridge.composition_result if bridge is not None else None
    coordinator = bridge.workflow_result if bridge is not None else None
    manifest = coordinator.manifest_result if coordinator is not None else None
    harness = coordinator.harness_result if coordinator is not None else None
    final = harness.final_result if harness is not None else None
    tod = final.time_of_day_result if final is not None else None

    lines = [
        "Market Sentry Local JSON Preflight",
        f"Path: {path}",
        f"Profile: {PROFILE_NAME}",
        f"Metadata Load: {_value_or_na(metadata_load.status)}",
        f"Metadata Load Reason: {_value_or_na(metadata_load.reason)}",
        f"Workflow: {_value_or_na(workflow_result.status)}",
        f"Workflow Reason: {_value_or_na(workflow_result.reason)}",
        f"Bridge: {_value_or_na(bridge.status if bridge is not None else None)}",
        f"Bridge Reason: {_value_or_na(bridge.reason if bridge is not None else None)}",
        (
            "Composition: "
            f"{_value_or_na(composition.status if composition is not None else None)}"
        ),
        (
            "Coordinator: "
            f"{_value_or_na(coordinator.status if coordinator is not None else None)}"
        ),
        (
            "Coordinator Reason: "
            f"{_value_or_na(coordinator.reason if coordinator is not None else None)}"
        ),
        f"Manifest: {_value_or_na(manifest.status if manifest is not None else None)}",
        (
            "Manifest Reason: "
            f"{_value_or_na(manifest.reason if manifest is not None else None)}"
        ),
        f"Harness: {_value_or_na(harness.status if harness is not None else None)}",
        (
            "Harness Reason: "
            f"{_value_or_na(harness.reason if harness is not None else None)}"
        ),
        f"Final: {_value_or_na(final.status if final is not None else None)}",
        (
            "Final Reason: "
            f"{_value_or_na(final.reason if final is not None else None)}"
        ),
        f"Time-of-Day RVOL: {_value_or_na(tod.status if tod is not None else None)}",
        (
            "Time-of-Day RVOL Reason: "
            f"{_value_or_na(tod.reason if tod is not None else None)}"
        ),
        (
            "Relative Volume: "
            f"{_relative_volume_or_na(tod.relative_volume if tod is not None else None)}"
        ),
        LOCAL_JSON_PREFLIGHT_NOTE,
    ]
    return "\n".join(lines)


def render_manual_local_json_preflight_error(path: Path, error: BaseException) -> str:
    error_message = str(error) or error.__class__.__name__
    return "\n".join(
        [
            "Market Sentry Local JSON Preflight",
            f"Path: {path}",
            "Result: ERROR",
            f"Error Type: {error.__class__.__name__}",
            f"Error: {error_message}",
            LOCAL_JSON_PREFLIGHT_NOTE,
        ]
    )


def is_manual_local_json_preflight_success(
    result: LocalJsonMetadataWorkflowPreflightResult,
) -> bool:
    workflow_result = result.workflow_result
    metadata_load = workflow_result.metadata_load_result
    if metadata_load.status != "LOADED":
        return False
    if workflow_result.status != "WORKFLOW_BRIDGE_RAN":
        return False

    bridge = workflow_result.workflow_bridge_result
    if bridge is None or bridge.status != "WORKFLOW_RAN":
        return False
    if bridge.composition_result.status != "COMPOSED":
        return False

    coordinator = bridge.workflow_result
    if coordinator is None or coordinator.status != "OK":
        return False
    if coordinator.manifest_result.status != "OK":
        return False

    harness = coordinator.harness_result
    if harness.status != "OK":
        return False

    final = harness.final_result
    if final.status != "OK":
        return False

    tod = final.time_of_day_result
    return (
        tod is not None
        and tod.status == "OK"
        and tod.relative_volume is not None
    )


__all__ = [
    "JsonHistoricalSessionMetadataFileSourceError",
    "json",
    "run_manual_local_json_preflight",
    "render_manual_local_json_preflight_report",
    "render_manual_local_json_preflight_error",
    "is_manual_local_json_preflight_success",
]
