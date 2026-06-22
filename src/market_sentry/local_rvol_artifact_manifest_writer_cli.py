from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from market_sentry.data.local_rvol_artifact_manifest import LocalRvolArtifact
from market_sentry.data.local_rvol_artifact_manifest_writer import (
    LocalRvolArtifactManifestWriteError,
    LocalRvolArtifactManifestWriteRequest,
    write_local_rvol_artifact_manifest,
)


LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_NOTE = (
    "Note: This command writes one explicit local RVOL artifact manifest from "
    "command-supplied paths. It does not read artifacts, load config, call APIs, "
    "activate providers, scan candidates, or play voice alerts."
)

LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_EXPECTED_ERRORS = (
    OSError,
    LocalRvolArtifactManifestWriteError,
)


@dataclass(frozen=True)
class LocalRvolArtifactManifestWriterCommandRequest:
    output_path: Path | None
    artifact_declarations: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class LocalRvolArtifactManifestWriterCommandResult:
    output_path: Path
    artifacts: tuple[LocalRvolArtifact, ...]


class LocalRvolArtifactManifestWriterCommandError(ValueError):
    """Raised for invalid local RVOL artifact manifest writer command inputs."""


def _command_error(message: str) -> LocalRvolArtifactManifestWriterCommandError:
    return LocalRvolArtifactManifestWriterCommandError(message)


def _display_path(path: Path | None) -> str:
    if path is None:
        return "N/A"
    return str(path)


def _validate_declaration(
    declaration: object,
    index: int,
) -> tuple[str, str, str]:
    if not isinstance(declaration, tuple):
        raise _command_error(f"INVALID_ARTIFACT_DECLARATION:{index}")
    if len(declaration) != 3:
        raise _command_error(f"INVALID_ARTIFACT_DECLARATION:{index}")
    symbol, metadata_path_text, bundle_path_text = declaration
    if not all(
        isinstance(item, str)
        for item in (symbol, metadata_path_text, bundle_path_text)
    ):
        raise _command_error(f"INVALID_ARTIFACT_DECLARATION:{index}")
    return symbol, metadata_path_text, bundle_path_text


def validate_local_rvol_artifact_manifest_writer_command(
    command: LocalRvolArtifactManifestWriterCommandRequest,
) -> LocalRvolArtifactManifestWriteRequest:
    if not isinstance(command, LocalRvolArtifactManifestWriterCommandRequest):
        raise TypeError(
            "command must be a LocalRvolArtifactManifestWriterCommandRequest."
        )
    if command.output_path is None:
        if command.artifact_declarations:
            raise _command_error(
                "--local-rvol-artifact requires "
                "--local-rvol-artifact-manifest-write"
            )
        raise _command_error("MISSING_MANIFEST_OUTPUT_PATH")
    if not isinstance(command.output_path, Path):
        raise TypeError("output_path must be a pathlib.Path.")
    if not isinstance(command.artifact_declarations, tuple):
        raise TypeError("artifact_declarations must be a tuple.")

    artifacts: list[LocalRvolArtifact] = []
    for index, declaration in enumerate(command.artifact_declarations):
        symbol, metadata_path_text, bundle_path_text = _validate_declaration(
            declaration,
            index,
        )
        artifacts.append(
            LocalRvolArtifact(
                symbol=symbol,
                metadata_path=Path(metadata_path_text),
                bundle_path=Path(bundle_path_text),
            )
        )

    return LocalRvolArtifactManifestWriteRequest(
        output_path=command.output_path,
        artifacts=tuple(artifacts),
    )


def run_local_rvol_artifact_manifest_writer(
    command: LocalRvolArtifactManifestWriterCommandRequest,
) -> LocalRvolArtifactManifestWriterCommandResult:
    request = validate_local_rvol_artifact_manifest_writer_command(command)
    artifacts = write_local_rvol_artifact_manifest(request)
    return LocalRvolArtifactManifestWriterCommandResult(
        output_path=request.output_path,
        artifacts=artifacts,
    )


def render_local_rvol_artifact_manifest_writer_success_report(
    command: LocalRvolArtifactManifestWriterCommandRequest,
    result: LocalRvolArtifactManifestWriterCommandResult,
) -> str:
    lines = [
        "Market Sentry Local RVOL Artifact Manifest Writer",
        f"Manifest Path: {result.output_path}",
        f"Artifacts: {len(result.artifacts)}",
    ]
    for number, artifact in enumerate(result.artifacts, start=1):
        lines.extend(
            [
                f"Artifact {number} Symbol: {artifact.symbol}",
                f"Artifact {number} Metadata Path: {artifact.metadata_path}",
                f"Artifact {number} Bundle Path: {artifact.bundle_path}",
            ]
        )
    lines.extend(
        [
            "Result: OK",
            LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_NOTE,
        ]
    )
    return "\n".join(lines)


def render_local_rvol_artifact_manifest_writer_command_error(
    command: LocalRvolArtifactManifestWriterCommandRequest,
    error: BaseException,
) -> str:
    return "\n".join(
        [
            "Market Sentry Local RVOL Artifact Manifest Writer",
            f"Manifest Path: {_display_path(command.output_path)}",
            "Result: COMMAND_ERROR",
            f"Error: {str(error) or error.__class__.__name__}",
            LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_NOTE,
        ]
    )


def render_local_rvol_artifact_manifest_writer_error(
    command: LocalRvolArtifactManifestWriterCommandRequest,
    error: BaseException,
) -> str:
    return "\n".join(
        [
            "Market Sentry Local RVOL Artifact Manifest Writer",
            f"Manifest Path: {_display_path(command.output_path)}",
            "Result: ERROR",
            f"Error Type: {error.__class__.__name__}",
            f"Error: {str(error) or error.__class__.__name__}",
            LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_NOTE,
        ]
    )
