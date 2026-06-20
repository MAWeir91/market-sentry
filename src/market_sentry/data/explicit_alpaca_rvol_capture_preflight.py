from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsFetcher,
)
from market_sentry.data.explicit_alpaca_rvol_bundle_capture import (
    ExplicitAlpacaRvolBundleCaptureRequest,
    ExplicitAlpacaRvolBundleCaptureResult,
    ExplicitAlpacaRvolBundleCaptureStatus,
    capture_explicit_alpaca_rvol_bundle,
)
from market_sentry.data.json_historical_session_metadata_writer import (
    render_local_historical_session_metadata,
    write_local_historical_session_metadata,
)
from market_sentry.data.local_json_metadata_workflow_preflight import (
    LocalJsonMetadataWorkflowPreflightResult,
    run_local_json_metadata_workflow_preflight,
)


EXPLICIT_ALPACA_CAPTURE_PREFLIGHT_NOTE = (
    "Note: This operation uses caller-injected Alpaca fetching only after "
    "explicit allow_live_data=True. It writes only the explicit metadata and "
    "bundle paths, then runs offline RVOL preflight. It does not activate "
    "providers, scan candidates, call FMP, or play voice alerts."
)


class ExplicitAlpacaRvolCapturePreflightStatus:
    """Stable statuses for one explicit capture-and-preflight operation."""

    LIVE_DATA_NOT_ALLOWED = "LIVE_DATA_NOT_ALLOWED"
    OUTPUT_PATH_CONFLICT = "OUTPUT_PATH_CONFLICT"
    CAPTURE_NOT_WRITTEN = "CAPTURE_NOT_WRITTEN"
    PREFLIGHT_SUCCEEDED = "PREFLIGHT_SUCCEEDED"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"


@dataclass(frozen=True)
class ExplicitAlpacaRvolCapturePreflightRequest:
    """Caller-selected inputs for one capture, metadata write, and preflight."""

    capture_request: ExplicitAlpacaRvolBundleCaptureRequest
    metadata_records: Sequence[object]
    metadata_output_path: Path
    report_output_path: Path | None = None


@dataclass(frozen=True)
class ExplicitAlpacaRvolCapturePreflightResult:
    """Artifacts from one explicit capture-and-preflight attempt."""

    request: ExplicitAlpacaRvolCapturePreflightRequest
    metadata_path: Path
    bundle_path: Path
    report_path: Path | None
    capture_result: ExplicitAlpacaRvolBundleCaptureResult | None
    metadata_written: bool
    preflight_result: LocalJsonMetadataWorkflowPreflightResult | None
    report: str | None
    report_written: bool
    status: str
    reason: str | None = None


def _result(
    *,
    request: ExplicitAlpacaRvolCapturePreflightRequest,
    capture_result: ExplicitAlpacaRvolBundleCaptureResult | None,
    metadata_written: bool,
    preflight_result: LocalJsonMetadataWorkflowPreflightResult | None,
    report: str | None,
    report_written: bool,
    status: str,
    reason: str | None = None,
) -> ExplicitAlpacaRvolCapturePreflightResult:
    return ExplicitAlpacaRvolCapturePreflightResult(
        request=request,
        metadata_path=request.metadata_output_path,
        bundle_path=request.capture_request.output_path,
        report_path=request.report_output_path,
        capture_result=capture_result,
        metadata_written=metadata_written,
        preflight_result=preflight_result,
        report=report,
        report_written=report_written,
        status=status,
        reason=reason,
    )


def _value_or_na(value: object) -> str:
    if value is None:
        return "N/A"
    return str(value)


def _relative_volume_or_na(value: object) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.1f}x"


def _preflight_reached_complete_rvol(
    preflight_result: LocalJsonMetadataWorkflowPreflightResult,
) -> bool:
    workflow_result = preflight_result.workflow_result
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


def render_explicit_alpaca_rvol_capture_preflight_report(
    result: ExplicitAlpacaRvolCapturePreflightResult,
) -> str:
    """Render one explicit capture-and-preflight report after preflight exists."""

    workflow_result = (
        result.preflight_result.workflow_result
        if result.preflight_result is not None
        else None
    )
    metadata_load = (
        workflow_result.metadata_load_result if workflow_result is not None else None
    )
    bridge = (
        workflow_result.workflow_bridge_result if workflow_result is not None else None
    )
    composition = bridge.composition_result if bridge is not None else None
    coordinator = bridge.workflow_result if bridge is not None else None
    manifest = coordinator.manifest_result if coordinator is not None else None
    harness = coordinator.harness_result if coordinator is not None else None
    final = harness.final_result if harness is not None else None
    tod = final.time_of_day_result if final is not None else None

    return "\n".join(
        [
            "Market Sentry Explicit Alpaca RVOL Capture Preflight",
            f"Metadata Path: {result.metadata_path}",
            f"Bundle Path: {result.bundle_path}",
            "Input Mode: EXPLICIT_ALPACA_CAPTURE",
            "Capture: BUNDLE_WRITTEN",
            (
                "Metadata Load: "
                f"{_value_or_na(metadata_load.status if metadata_load else None)}"
            ),
            (
                "Metadata Load Reason: "
                f"{_value_or_na(metadata_load.reason if metadata_load else None)}"
            ),
            (
                "Workflow: "
                f"{_value_or_na(workflow_result.status if workflow_result else None)}"
            ),
            (
                "Workflow Reason: "
                f"{_value_or_na(workflow_result.reason if workflow_result else None)}"
            ),
            f"Bridge: {_value_or_na(bridge.status if bridge else None)}",
            f"Bridge Reason: {_value_or_na(bridge.reason if bridge else None)}",
            (
                "Composition: "
                f"{_value_or_na(composition.status if composition else None)}"
            ),
            (
                "Coordinator: "
                f"{_value_or_na(coordinator.status if coordinator else None)}"
            ),
            (
                "Coordinator Reason: "
                f"{_value_or_na(coordinator.reason if coordinator else None)}"
            ),
            f"Manifest: {_value_or_na(manifest.status if manifest else None)}",
            f"Manifest Reason: {_value_or_na(manifest.reason if manifest else None)}",
            f"Harness: {_value_or_na(harness.status if harness else None)}",
            f"Harness Reason: {_value_or_na(harness.reason if harness else None)}",
            f"Final: {_value_or_na(final.status if final else None)}",
            f"Final Reason: {_value_or_na(final.reason if final else None)}",
            f"Time-of-Day RVOL: {_value_or_na(tod.status if tod else None)}",
            f"Time-of-Day RVOL Reason: {_value_or_na(tod.reason if tod else None)}",
            (
                "Relative Volume: "
                f"{_relative_volume_or_na(tod.relative_volume if tod else None)}"
            ),
            EXPLICIT_ALPACA_CAPTURE_PREFLIGHT_NOTE,
        ]
    )


def is_explicit_alpaca_rvol_capture_preflight_success(
    result: ExplicitAlpacaRvolCapturePreflightResult,
) -> bool:
    """Return True only when final preflight reached complete RVOL success."""

    return result.status == (
        ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_SUCCEEDED
    )


def capture_and_preflight_explicit_alpaca_rvol_bundle(
    fetcher: AlpacaHistoricalBarsFetcher,
    request: ExplicitAlpacaRvolCapturePreflightRequest,
) -> ExplicitAlpacaRvolCapturePreflightResult:
    """Capture an explicit Alpaca bundle, write metadata, then preflight both."""

    if not isinstance(request.capture_request.output_path, Path):
        raise TypeError("output_path must be a pathlib.Path.")
    if not isinstance(request.metadata_output_path, Path):
        raise TypeError("metadata_output_path must be a pathlib.Path.")
    if (
        request.report_output_path is not None
        and not isinstance(request.report_output_path, Path)
    ):
        raise TypeError("report_output_path must be a pathlib.Path or None.")

    if request.metadata_output_path == request.capture_request.output_path:
        return _result(
            request=request,
            capture_result=None,
            metadata_written=False,
            preflight_result=None,
            report=None,
            report_written=False,
            status=ExplicitAlpacaRvolCapturePreflightStatus.OUTPUT_PATH_CONFLICT,
            reason="METADATA_PATH_EQUALS_BUNDLE_PATH",
        )
    if request.report_output_path == request.metadata_output_path:
        return _result(
            request=request,
            capture_result=None,
            metadata_written=False,
            preflight_result=None,
            report=None,
            report_written=False,
            status=ExplicitAlpacaRvolCapturePreflightStatus.OUTPUT_PATH_CONFLICT,
            reason="REPORT_PATH_EQUALS_METADATA_PATH",
        )
    if request.report_output_path == request.capture_request.output_path:
        return _result(
            request=request,
            capture_result=None,
            metadata_written=False,
            preflight_result=None,
            report=None,
            report_written=False,
            status=ExplicitAlpacaRvolCapturePreflightStatus.OUTPUT_PATH_CONFLICT,
            reason="REPORT_PATH_EQUALS_BUNDLE_PATH",
        )

    if request.capture_request.allow_live_data is not True:
        return _result(
            request=request,
            capture_result=None,
            metadata_written=False,
            preflight_result=None,
            report=None,
            report_written=False,
            status=ExplicitAlpacaRvolCapturePreflightStatus.LIVE_DATA_NOT_ALLOWED,
            reason=ExplicitAlpacaRvolCapturePreflightStatus.LIVE_DATA_NOT_ALLOWED,
        )

    render_local_historical_session_metadata(request.metadata_records)
    capture_result = capture_explicit_alpaca_rvol_bundle(
        fetcher,
        request.capture_request,
    )

    if capture_result.status != ExplicitAlpacaRvolBundleCaptureStatus.BUNDLE_WRITTEN:
        return _result(
            request=request,
            capture_result=capture_result,
            metadata_written=False,
            preflight_result=None,
            report=None,
            report_written=False,
            status=ExplicitAlpacaRvolCapturePreflightStatus.CAPTURE_NOT_WRITTEN,
            reason=f"CAPTURE_NOT_WRITTEN:{capture_result.status}",
        )

    write_local_historical_session_metadata(
        request.metadata_output_path,
        request.metadata_records,
    )
    preflight_result = run_local_json_metadata_workflow_preflight(
        request.metadata_output_path,
        capture_result.historical_collection,
        capture_result.manifest_request,
        capture_result.current_series_result.intraday_series,
        capture_result.harness_request,
    )

    status = (
        ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_SUCCEEDED
        if _preflight_reached_complete_rvol(preflight_result)
        else ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_FAILED
    )
    reason = (
        None
        if status == ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_SUCCEEDED
        else ExplicitAlpacaRvolCapturePreflightStatus.PREFLIGHT_FAILED
    )
    result = _result(
        request=request,
        capture_result=capture_result,
        metadata_written=True,
        preflight_result=preflight_result,
        report=None,
        report_written=False,
        status=status,
        reason=reason,
    )
    report = render_explicit_alpaca_rvol_capture_preflight_report(result)
    result = replace(result, report=report)

    if request.report_output_path is not None:
        request.report_output_path.write_text(report, encoding="utf-8")
        result = replace(result, report_written=True)

    return result
