"""Offline CLI helper for building explicit local RVOL metadata seeds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from market_sentry.data.local_rvol_session_seed_plan import (
    LocalRvolSessionSeedBuildResult,
    LocalRvolSessionSeedPlanError,
    load_local_rvol_session_seed_plan,
    write_local_rvol_session_seed,
)


LOCAL_RVOL_SESSION_SEED_NOTE = (
    "Note: This operation is offline-only. It uses caller-supplied sessions "
    "and timestamps, writes only the explicit metadata path, and does not "
    "infer calendars or call APIs."
)

LOCAL_RVOL_SESSION_SEED_EXPECTED_ERRORS = (
    OSError,
    UnicodeDecodeError,
    LocalRvolSessionSeedPlanError,
)


@dataclass(frozen=True)
class LocalRvolSessionSeedCommandRequest:
    plan_path: Path
    metadata_output_path: Path


class LocalRvolSessionSeedCommandError(ValueError):
    """Raised for invalid local RVOL session-seed command inputs."""


def _command_error(message: str) -> LocalRvolSessionSeedCommandError:
    return LocalRvolSessionSeedCommandError(message)


def _display_path(path: Path) -> str:
    return str(path)


def validate_local_rvol_session_seed_command(
    command: LocalRvolSessionSeedCommandRequest,
) -> None:
    if not isinstance(command.plan_path, Path):
        raise TypeError("plan_path must be a pathlib.Path.")
    if not isinstance(command.metadata_output_path, Path):
        raise TypeError("metadata_output_path must be a pathlib.Path.")
    if command.plan_path == command.metadata_output_path:
        raise _command_error("PLAN_PATH_EQUALS_METADATA_OUTPUT")


def run_local_rvol_session_seed(
    command: LocalRvolSessionSeedCommandRequest,
) -> LocalRvolSessionSeedBuildResult:
    validate_local_rvol_session_seed_command(command)
    plan = load_local_rvol_session_seed_plan(command.plan_path)
    return write_local_rvol_session_seed(command.metadata_output_path, plan)


def render_local_rvol_session_seed_report(
    result: LocalRvolSessionSeedBuildResult,
) -> str:
    request = result.manifest_result.request
    return "\n".join(
        [
            "Market Sentry Local RVOL Session Seed",
            f"Plan Path: {_display_path(result.plan.path)}",
            "Metadata Path: N/A",
            "Input Mode: EXPLICIT_SESSION_PLAN",
            f"Symbol: {request.symbol.strip().upper()}",
            f"Bucket: {request.bucket.strip()}",
            f"Current Session ID: {request.current_session_id.strip()}",
            f"Historical Sessions: {len(result.metadata_records)}",
            "Result: WRITTEN",
            LOCAL_RVOL_SESSION_SEED_NOTE,
        ]
    )


def render_local_rvol_session_seed_success_report(
    command: LocalRvolSessionSeedCommandRequest,
    result: LocalRvolSessionSeedBuildResult,
) -> str:
    request = result.manifest_result.request
    return "\n".join(
        [
            "Market Sentry Local RVOL Session Seed",
            f"Plan Path: {_display_path(command.plan_path)}",
            f"Metadata Path: {_display_path(command.metadata_output_path)}",
            "Input Mode: EXPLICIT_SESSION_PLAN",
            f"Symbol: {request.symbol.strip().upper()}",
            f"Bucket: {request.bucket.strip()}",
            f"Current Session ID: {request.current_session_id.strip()}",
            f"Historical Sessions: {len(result.metadata_records)}",
            "Result: WRITTEN",
            LOCAL_RVOL_SESSION_SEED_NOTE,
        ]
    )


def render_local_rvol_session_seed_command_error(
    command: LocalRvolSessionSeedCommandRequest,
    error: BaseException,
) -> str:
    return "\n".join(
        [
            "Market Sentry Local RVOL Session Seed",
            f"Plan Path: {_display_path(command.plan_path)}",
            f"Metadata Path: {_display_path(command.metadata_output_path)}",
            "Result: COMMAND_ERROR",
            f"Error: {str(error) or error.__class__.__name__}",
            LOCAL_RVOL_SESSION_SEED_NOTE,
        ]
    )


def render_local_rvol_session_seed_error(
    command: LocalRvolSessionSeedCommandRequest,
    error: BaseException,
) -> str:
    return "\n".join(
        [
            "Market Sentry Local RVOL Session Seed",
            f"Plan Path: {_display_path(command.plan_path)}",
            f"Metadata Path: {_display_path(command.metadata_output_path)}",
            "Result: ERROR",
            f"Error Type: {error.__class__.__name__}",
            f"Error: {str(error) or error.__class__.__name__}",
            LOCAL_RVOL_SESSION_SEED_NOTE,
        ]
    )
