from dataclasses import dataclass
import json
from pathlib import Path

from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsFetchError,
)
from market_sentry.data.json_historical_rvol_bundle import (
    JsonHistoricalRvolBundleError,
    LocalHistoricalRvolBundle,
    load_local_historical_rvol_bundle,
)
from market_sentry.data.json_historical_session_metadata_source import (
    JsonHistoricalSessionMetadataFileSourceError,
)
from market_sentry.data.local_json_metadata_workflow_preflight import (
    LocalJsonMetadataWorkflowPreflightResult,
    run_local_json_metadata_workflow_preflight,
)


LOCAL_JSON_BUNDLE_PREFLIGHT_NOTE = (
    "Note: This command reads only the explicit local metadata JSON path and "
    "local historical RVOL bundle path. It does not activate providers, scan "
    "candidates, call APIs, or play voice alerts."
)

MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    JsonHistoricalSessionMetadataFileSourceError,
    JsonHistoricalRvolBundleError,
    AlpacaHistoricalBarsFetchError,
)


@dataclass(frozen=True)
class ManualLocalJsonBundlePreflightResult:
    """One explicit local bundle load plus one metadata workflow preflight."""

    metadata_path: Path
    bundle_path: Path
    bundle: LocalHistoricalRvolBundle
    preflight_result: LocalJsonMetadataWorkflowPreflightResult


def run_manual_local_json_bundle_preflight(
    metadata_path: Path,
    bundle_path: Path,
) -> ManualLocalJsonBundlePreflightResult:
    bundle = load_local_historical_rvol_bundle(bundle_path)
    preflight_result = run_local_json_metadata_workflow_preflight(
        metadata_path,
        bundle.collection,
        bundle.manifest_request,
        bundle.current_series,
        bundle.harness_request,
    )
    return ManualLocalJsonBundlePreflightResult(
        metadata_path=metadata_path,
        bundle_path=bundle_path,
        bundle=bundle,
        preflight_result=preflight_result,
    )


def _value_or_na(value: object) -> str:
    if value is None:
        return "N/A"
    return str(value)


def _relative_volume_or_na(value: object) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.1f}x"


def render_manual_local_json_bundle_preflight_report(
    metadata_path: Path,
    bundle_path: Path,
    result: ManualLocalJsonBundlePreflightResult,
) -> str:
    workflow_result = result.preflight_result.workflow_result
    metadata_load = workflow_result.metadata_load_result
    bridge = workflow_result.workflow_bridge_result
    composition = bridge.composition_result if bridge is not None else None
    coordinator = bridge.workflow_result if bridge is not None else None
    manifest = coordinator.manifest_result if coordinator is not None else None
    harness = coordinator.harness_result if coordinator is not None else None
    final = harness.final_result if harness is not None else None
    tod = final.time_of_day_result if final is not None else None

    return "\n".join(
        [
            "Market Sentry Local JSON Bundle Preflight",
            f"Metadata Path: {metadata_path}",
            f"Bundle Path: {bundle_path}",
            "Input Mode: EXPLICIT_LOCAL_BUNDLE",
            f"Metadata Load: {_value_or_na(metadata_load.status)}",
            f"Metadata Load Reason: {_value_or_na(metadata_load.reason)}",
            f"Workflow: {_value_or_na(workflow_result.status)}",
            f"Workflow Reason: {_value_or_na(workflow_result.reason)}",
            f"Bridge: {_value_or_na(bridge.status if bridge is not None else None)}",
            (
                "Bridge Reason: "
                f"{_value_or_na(bridge.reason if bridge is not None else None)}"
            ),
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
            f"Final Reason: {_value_or_na(final.reason if final is not None else None)}",
            f"Time-of-Day RVOL: {_value_or_na(tod.status if tod is not None else None)}",
            (
                "Time-of-Day RVOL Reason: "
                f"{_value_or_na(tod.reason if tod is not None else None)}"
            ),
            (
                "Relative Volume: "
                f"{_relative_volume_or_na(tod.relative_volume if tod is not None else None)}"
            ),
            LOCAL_JSON_BUNDLE_PREFLIGHT_NOTE,
        ]
    )


def render_manual_local_json_bundle_preflight_error(
    metadata_path: Path,
    bundle_path: Path,
    error: BaseException,
) -> str:
    error_message = str(error) or error.__class__.__name__
    return "\n".join(
        [
            "Market Sentry Local JSON Bundle Preflight",
            f"Metadata Path: {metadata_path}",
            f"Bundle Path: {bundle_path}",
            "Result: ERROR",
            f"Error Type: {error.__class__.__name__}",
            f"Error: {error_message}",
            LOCAL_JSON_BUNDLE_PREFLIGHT_NOTE,
        ]
    )


def is_manual_local_json_bundle_preflight_success(
    result: ManualLocalJsonBundlePreflightResult,
) -> bool:
    workflow_result = result.preflight_result.workflow_result
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
