from collections.abc import Callable
from dataclasses import dataclass, replace
import json
from pathlib import Path

from market_sentry.config import AppConfig, LIVE_COMPOSED_PROVIDER
from market_sentry.data.factory import ProviderConfigurationError
from market_sentry.data.http import HttpTransportError
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsFetchError,
)
from market_sentry.data.local_rvol_artifact_manifest import LocalRvolArtifact
from market_sentry.data.local_rvol_artifact_manifest_writer import (
    LocalRvolArtifactManifestWriteError,
)
from market_sentry.data.one_shot_live_composed_workflow_plan import (
    OneShotLiveComposedWorkflowArtifact,
    OneShotLiveComposedWorkflowPlan,
    OneShotLiveComposedWorkflowPlanError,
    load_one_shot_live_composed_workflow_plan,
)
from market_sentry.local_rvol_artifact_manifest_audit_cli import (
    LOCAL_RVOL_ARTIFACT_AUDIT_EXPECTED_ERRORS,
    LocalRvolArtifactAuditCommandRequest,
    LocalRvolArtifactAuditResult,
    is_local_rvol_artifact_audit_success,
    render_local_rvol_artifact_audit_report,
    run_local_rvol_artifact_audit,
)
from market_sentry.local_rvol_artifact_manifest_writer_cli import (
    LocalRvolArtifactManifestWriterCommandRequest,
    LocalRvolArtifactManifestWriterCommandResult,
    run_local_rvol_artifact_manifest_writer,
)
from market_sentry.manual_explicit_alpaca_rvol_capture_preflight_cli import (
    MANUAL_EXPLICIT_ALPACA_CAPTURE_EXPECTED_ERRORS,
    ManualExplicitAlpacaRvolCaptureCommandError,
    ManualExplicitAlpacaRvolCaptureCommandRequest,
    is_manual_explicit_alpaca_rvol_capture_success,
    render_manual_explicit_alpaca_rvol_capture_stopped_report,
    run_manual_explicit_alpaca_rvol_capture_preflight,
)


ONE_SHOT_LIVE_COMPOSED_WORKFLOW_NOTE = (
    "Note: This command is one-shot and plan-driven. It requires explicit live "
    "data confirmation, writes only declared RVOL artifacts and manifest output, "
    "then runs one live-composed diagnostic scan. It does not loop, play voice "
    "alerts, place trades, or submit orders."
)

ONE_SHOT_LIVE_COMPOSED_WORKFLOW_EXPECTED_ERRORS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    LocalRvolArtifactManifestWriteError,
    ProviderConfigurationError,
    AlpacaHistoricalBarsFetchError,
    HttpTransportError,
    ManualExplicitAlpacaRvolCaptureCommandError,
    *LOCAL_RVOL_ARTIFACT_AUDIT_EXPECTED_ERRORS,
    *MANUAL_EXPLICIT_ALPACA_CAPTURE_EXPECTED_ERRORS,
)


class OneShotLiveComposedWorkflowCommandError(ValueError):
    """Raised for invalid one-shot live-composed workflow command inputs."""


@dataclass(frozen=True)
class OneShotLiveComposedWorkflowCommandRequest:
    plan_path: Path | None
    confirm_live_data: bool


@dataclass(frozen=True)
class OneShotLiveComposedWorkflowResult:
    plan: OneShotLiveComposedWorkflowPlan
    capture_results: tuple[object, ...]
    manifest_result: LocalRvolArtifactManifestWriterCommandResult | None
    audit_result: LocalRvolArtifactAuditResult | None
    scan_report: str | None
    status: str
    reason: str | None = None


def _command_error(message: str) -> OneShotLiveComposedWorkflowCommandError:
    return OneShotLiveComposedWorkflowCommandError(message)


def _display_path(path: Path | None) -> str:
    if path is None:
        return "N/A"
    return str(path)


def validate_one_shot_live_composed_workflow_command(
    command: OneShotLiveComposedWorkflowCommandRequest,
) -> None:
    if not isinstance(command, OneShotLiveComposedWorkflowCommandRequest):
        raise TypeError(
            "command must be a OneShotLiveComposedWorkflowCommandRequest."
        )
    if command.plan_path is None:
        if command.confirm_live_data:
            raise _command_error(
                "--one-shot-live-composed-confirm-live-data requires "
                "--one-shot-live-composed-workflow"
            )
        raise _command_error("MISSING_WORKFLOW_PLAN_PATH")
    if not isinstance(command.plan_path, Path):
        raise TypeError("plan_path must be a pathlib.Path.")
    if command.confirm_live_data is not True:
        raise _command_error("LIVE_DATA_CONFIRMATION_REQUIRED")


def _require_live_config(config: AppConfig) -> None:
    if config.allow_live_data is not True:
        raise _command_error("ENV_LIVE_DATA_NOT_ALLOWED")
    if not config.alpaca_api_key:
        raise _command_error("MISSING_ALPACA_API_KEY")
    if not config.alpaca_api_secret:
        raise _command_error("MISSING_ALPACA_API_SECRET")
    if not config.fmp_api_key:
        raise _command_error("MISSING_FMP_API_KEY")


def _capture_command(
    artifact: OneShotLiveComposedWorkflowArtifact,
) -> ManualExplicitAlpacaRvolCaptureCommandRequest:
    return ManualExplicitAlpacaRvolCaptureCommandRequest(
        metadata_input_path=artifact.metadata_input_path,
        metadata_output_path=artifact.metadata_output_path,
        bundle_output_path=artifact.bundle_output_path,
        report_output_path=None,
        confirm_live_data=True,
        symbol=artifact.symbol,
        historical_start=artifact.historical_start,
        historical_end=artifact.historical_end,
        historical_max_pages=artifact.historical_max_pages,
        current_start=artifact.current_start,
        current_end=artifact.current_end,
        current_max_pages=artifact.current_max_pages,
        current_session_id=artifact.current_session_id,
        bucket=artifact.bucket,
        cutoff=artifact.cutoff,
        minimum_historical_sessions=artifact.minimum_historical_sessions,
        timeframe=artifact.timeframe,
        page_limit=artifact.page_limit,
        sort=artifact.sort,
    )


def _manifest_command(
    plan: OneShotLiveComposedWorkflowPlan,
) -> LocalRvolArtifactManifestWriterCommandRequest:
    return LocalRvolArtifactManifestWriterCommandRequest(
        output_path=plan.manifest_output_path,
        artifact_declarations=tuple(
            (
                artifact.symbol,
                str(artifact.metadata_output_path),
                str(artifact.bundle_output_path),
            )
            for artifact in plan.artifacts
        ),
    )


def _derived_live_config(
    config: AppConfig,
    plan: OneShotLiveComposedWorkflowPlan,
) -> AppConfig:
    return replace(
        config,
        provider=LIVE_COMPOSED_PROVIDER,
        watchlist=tuple(artifact.symbol for artifact in plan.artifacts),
        rvol_artifact_manifest_path=plan.manifest_output_path,
    )


def run_one_shot_live_composed_workflow(
    command: OneShotLiveComposedWorkflowCommandRequest,
    *,
    load_config_fn: Callable[[], AppConfig],
    provider_factory: Callable[[AppConfig], object],
    scan_reporter: Callable[[object], str],
    transport: object | None = None,
    plan_loader: Callable[
        [Path],
        OneShotLiveComposedWorkflowPlan,
    ] = load_one_shot_live_composed_workflow_plan,
    capture_runner: Callable[..., object] = run_manual_explicit_alpaca_rvol_capture_preflight,
    manifest_writer: Callable[
        [LocalRvolArtifactManifestWriterCommandRequest],
        LocalRvolArtifactManifestWriterCommandResult,
    ] = run_local_rvol_artifact_manifest_writer,
    audit_runner: Callable[
        [LocalRvolArtifactAuditCommandRequest],
        LocalRvolArtifactAuditResult,
    ] = run_local_rvol_artifact_audit,
) -> OneShotLiveComposedWorkflowResult:
    validate_one_shot_live_composed_workflow_command(command)
    plan = plan_loader(command.plan_path)
    config = load_config_fn()
    _require_live_config(config)

    captures: list[object] = []
    for artifact in plan.artifacts:
        capture = capture_runner(
            _capture_command(artifact),
            config,
            transport=transport,
        )
        captures.append(capture)
        if not is_manual_explicit_alpaca_rvol_capture_success(capture):
            return OneShotLiveComposedWorkflowResult(
                plan=plan,
                capture_results=tuple(captures),
                manifest_result=None,
                audit_result=None,
                scan_report=None,
                status="FAILED",
                reason="CAPTURE_FAILED",
            )

    manifest_result = manifest_writer(_manifest_command(plan))
    audit_result = audit_runner(
        LocalRvolArtifactAuditCommandRequest(plan.manifest_output_path)
    )
    if not is_local_rvol_artifact_audit_success(audit_result):
        return OneShotLiveComposedWorkflowResult(
            plan=plan,
            capture_results=tuple(captures),
            manifest_result=manifest_result,
            audit_result=audit_result,
            scan_report=None,
            status="FAILED",
            reason="ARTIFACT_AUDIT_FAILED",
        )

    provider = provider_factory(_derived_live_config(config, plan))
    scan_report = scan_reporter(provider)
    return OneShotLiveComposedWorkflowResult(
        plan=plan,
        capture_results=tuple(captures),
        manifest_result=manifest_result,
        audit_result=audit_result,
        scan_report=scan_report,
        status="OK",
        reason=None,
    )


def render_one_shot_live_composed_workflow_report(
    command: OneShotLiveComposedWorkflowCommandRequest,
    result: OneShotLiveComposedWorkflowResult,
) -> str:
    lines = [
        "Market Sentry Explicit One-Shot Live-Composed Workflow",
        f"Plan Path: {_display_path(command.plan_path)}",
        f"Manifest Path: {result.plan.manifest_output_path}",
        f"Artifacts: {len(result.plan.artifacts)}",
        "",
    ]
    for number, capture in enumerate(result.capture_results, start=1):
        artifact = result.plan.artifacts[number - 1]
        lines.extend(
            [
                f"Capture {number} Symbol: {artifact.symbol}",
                f"Capture {number} Status: {getattr(capture, 'status', 'N/A')}",
            ]
        )
        if not is_manual_explicit_alpaca_rvol_capture_success(capture):
            lines.append(
                f"Capture {number} Reason: {getattr(capture, 'reason', 'N/A') or 'N/A'}"
            )
            lines.append(render_manual_explicit_alpaca_rvol_capture_stopped_report(capture))
    lines.append(
        "Manifest Write: "
        + ("OK" if result.manifest_result is not None else "NOT_RUN")
    )
    lines.append(
        "Artifact Audit: " + ("OK" if result.audit_result is not None else "NOT_RUN")
    )
    if result.audit_result is not None:
        lines.append(render_local_rvol_artifact_audit_report(
            LocalRvolArtifactAuditCommandRequest(result.plan.manifest_output_path),
            result.audit_result,
        ))
    lines.append("Live Scan: " + ("OK" if result.scan_report is not None else "NOT_RUN"))
    if result.scan_report is not None:
        lines.extend(["", result.scan_report])
    lines.extend(
        [
            f"Result: {result.status}",
            f"Reason: {result.reason or 'N/A'}",
            ONE_SHOT_LIVE_COMPOSED_WORKFLOW_NOTE,
        ]
    )
    return "\n".join(lines)


def render_one_shot_live_composed_workflow_command_error(
    command: OneShotLiveComposedWorkflowCommandRequest,
    error: BaseException,
) -> str:
    return "\n".join(
        [
            "Market Sentry Explicit One-Shot Live-Composed Workflow",
            f"Plan Path: {_display_path(command.plan_path)}",
            "Manifest Path: N/A",
            "Result: COMMAND_ERROR",
            f"Error: {str(error) or error.__class__.__name__}",
            ONE_SHOT_LIVE_COMPOSED_WORKFLOW_NOTE,
        ]
    )


def render_one_shot_live_composed_workflow_error(
    command: OneShotLiveComposedWorkflowCommandRequest,
    error: BaseException,
) -> str:
    return "\n".join(
        [
            "Market Sentry Explicit One-Shot Live-Composed Workflow",
            f"Plan Path: {_display_path(command.plan_path)}",
            "Manifest Path: N/A",
            "Result: ERROR",
            f"Error Type: {error.__class__.__name__}",
            f"Error: {str(error) or error.__class__.__name__}",
            ONE_SHOT_LIVE_COMPOSED_WORKFLOW_NOTE,
        ]
    )


def local_rvol_artifacts_from_plan(
    plan: OneShotLiveComposedWorkflowPlan,
) -> tuple[LocalRvolArtifact, ...]:
    return tuple(
        LocalRvolArtifact(
            symbol=artifact.symbol,
            metadata_path=artifact.metadata_output_path,
            bundle_path=artifact.bundle_output_path,
        )
        for artifact in plan.artifacts
    )
