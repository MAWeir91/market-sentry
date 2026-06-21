from dataclasses import dataclass
from pathlib import Path

from market_sentry.data.local_rvol_artifact_manifest import (
    LocalRvolArtifact,
    LocalRvolArtifactManifest,
    LocalRvolArtifactManifestError,
    load_local_rvol_artifact_manifest,
)
from market_sentry.local_json_bundle_preflight_cli import (
    MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS,
    ManualLocalJsonBundlePreflightResult,
    is_manual_local_json_bundle_preflight_success,
    run_manual_local_json_bundle_preflight,
)


LOCAL_RVOL_ARTIFACT_AUDIT_NOTE = (
    "Note: This command reads only one explicit local RVOL artifact manifest "
    "and the metadata/bundle paths it declares. It does not load config, "
    "call APIs, activate providers, scan candidates, or play voice alerts."
)

LOCAL_RVOL_ARTIFACT_AUDIT_EXPECTED_ERRORS = (
    OSError,
    UnicodeDecodeError,
    LocalRvolArtifactManifestError,
    *MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS,
)


@dataclass(frozen=True)
class LocalRvolArtifactAuditCommandRequest:
    manifest_path: Path


@dataclass(frozen=True)
class LocalRvolArtifactAuditEntry:
    index: int
    artifact: LocalRvolArtifact
    status: str
    preflight_result: ManualLocalJsonBundlePreflightResult | None
    relative_volume: float | None
    error_type: str | None
    error_message: str | None


@dataclass(frozen=True)
class LocalRvolArtifactAuditResult:
    manifest: LocalRvolArtifactManifest
    entries: tuple[LocalRvolArtifactAuditEntry, ...]


class LocalRvolArtifactAuditCommandError(ValueError):
    """Raised for invalid local RVOL artifact audit command inputs."""


def validate_local_rvol_artifact_audit_command(
    command: LocalRvolArtifactAuditCommandRequest,
) -> None:
    if not isinstance(command.manifest_path, Path):
        raise TypeError("manifest_path must be a pathlib.Path.")


def _error_entry(
    *,
    index: int,
    artifact: LocalRvolArtifact,
    error: BaseException,
) -> LocalRvolArtifactAuditEntry:
    return LocalRvolArtifactAuditEntry(
        index=index,
        artifact=artifact,
        status="ERROR",
        preflight_result=None,
        relative_volume=None,
        error_type=error.__class__.__name__,
        error_message=str(error) or error.__class__.__name__,
    )


def run_local_rvol_artifact_audit(
    command: LocalRvolArtifactAuditCommandRequest,
) -> LocalRvolArtifactAuditResult:
    validate_local_rvol_artifact_audit_command(command)
    manifest = load_local_rvol_artifact_manifest(command.manifest_path)
    entries: list[LocalRvolArtifactAuditEntry] = []

    for index, artifact in enumerate(manifest.artifacts):
        try:
            preflight_result = run_manual_local_json_bundle_preflight(
                artifact.metadata_path,
                artifact.bundle_path,
            )
        except MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS as exc:
            entries.append(_error_entry(index=index, artifact=artifact, error=exc))
            continue

        if is_manual_local_json_bundle_preflight_success(preflight_result):
            entries.append(
                LocalRvolArtifactAuditEntry(
                    index=index,
                    artifact=artifact,
                    status="OK",
                    preflight_result=preflight_result,
                    relative_volume=float(
                        preflight_result.preflight_result.workflow_result
                        .workflow_bridge_result.workflow_result.harness_result
                        .final_result.time_of_day_result.relative_volume
                    ),
                    error_type=None,
                    error_message=None,
                )
            )
            continue

        entries.append(
            LocalRvolArtifactAuditEntry(
                index=index,
                artifact=artifact,
                status="FAILED",
                preflight_result=preflight_result,
                relative_volume=None,
                error_type=None,
                error_message=None,
            )
        )

    return LocalRvolArtifactAuditResult(manifest=manifest, entries=tuple(entries))


def is_local_rvol_artifact_audit_success(
    result: LocalRvolArtifactAuditResult,
) -> bool:
    return all(entry.status == "OK" for entry in result.entries)


def _value_or_na(value: object) -> str:
    if value is None:
        return "N/A"
    return str(value)


def _relative_volume_or_na(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}x"


def render_local_rvol_artifact_audit_report(
    command: LocalRvolArtifactAuditCommandRequest,
    result: LocalRvolArtifactAuditResult,
) -> str:
    lines = [
        "Market Sentry Local RVOL Artifact Preflight",
        f"Manifest Path: {command.manifest_path}",
        "Input Mode: EXPLICIT_LOCAL_RVOL_ARTIFACT_MANIFEST",
        f"Artifacts: {len(result.entries)}",
    ]

    for number, entry in enumerate(result.entries, start=1):
        lines.extend(
            [
                f"Artifact {number} Symbol: {entry.artifact.symbol}",
                f"Artifact {number} Metadata Path: {entry.artifact.metadata_path}",
                f"Artifact {number} Bundle Path: {entry.artifact.bundle_path}",
                f"Artifact {number} Result: {entry.status}",
                (
                    f"Artifact {number} Relative Volume: "
                    f"{_relative_volume_or_na(entry.relative_volume)}"
                ),
                f"Artifact {number} Error Type: {_value_or_na(entry.error_type)}",
                f"Artifact {number} Error: {_value_or_na(entry.error_message)}",
            ]
        )

    result_status = "OK" if is_local_rvol_artifact_audit_success(result) else "FAILED"
    lines.extend(
        [
            f"Result: {result_status}",
            LOCAL_RVOL_ARTIFACT_AUDIT_NOTE,
        ]
    )
    return "\n".join(lines)


def render_local_rvol_artifact_audit_command_error(
    command: LocalRvolArtifactAuditCommandRequest,
    error: BaseException,
) -> str:
    return "\n".join(
        [
            "Market Sentry Local RVOL Artifact Preflight",
            f"Manifest Path: {command.manifest_path}",
            "Result: COMMAND_ERROR",
            f"Error: {str(error) or error.__class__.__name__}",
            LOCAL_RVOL_ARTIFACT_AUDIT_NOTE,
        ]
    )


def render_local_rvol_artifact_audit_error(
    command: LocalRvolArtifactAuditCommandRequest,
    error: BaseException,
) -> str:
    return "\n".join(
        [
            "Market Sentry Local RVOL Artifact Preflight",
            f"Manifest Path: {command.manifest_path}",
            "Result: ERROR",
            f"Error Type: {error.__class__.__name__}",
            f"Error: {str(error) or error.__class__.__name__}",
            LOCAL_RVOL_ARTIFACT_AUDIT_NOTE,
        ]
    )
