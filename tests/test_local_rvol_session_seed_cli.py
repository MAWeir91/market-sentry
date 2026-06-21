import ast
from dataclasses import FrozenInstanceError
import inspect
import json
from pathlib import Path

import pytest

from market_sentry import local_rvol_session_seed_cli as module
from market_sentry.local_rvol_session_seed_cli import (
    LOCAL_RVOL_SESSION_SEED_NOTE,
    LocalRvolSessionSeedCommandError,
    LocalRvolSessionSeedCommandRequest,
    render_local_rvol_session_seed_command_error,
    render_local_rvol_session_seed_error,
    render_local_rvol_session_seed_success_report,
    run_local_rvol_session_seed,
    validate_local_rvol_session_seed_command,
)


def session() -> dict[str, object]:
    return {
        "session_id": "2026-06-17",
        "session_start_timestamp": "2026-06-17T13:30:00Z",
        "session_end_timestamp": "2026-06-17T20:00:00Z",
        "cutoff_timestamp": "2026-06-17T14:00:00Z",
        "is_complete": True,
    }


def payload(**overrides) -> dict[str, object]:
    value = {
        "schema_version": 1,
        "symbol": "rvol",
        "bucket": "regular",
        "current_session_id": "2026-06-18",
        "sessions": [session()],
    }
    value.update(overrides)
    return value


def write_plan(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def command(tmp_path, **overrides) -> LocalRvolSessionSeedCommandRequest:
    values = {
        "plan_path": tmp_path / "plan.json",
        "metadata_output_path": tmp_path / "metadata.json",
    }
    values.update(overrides)
    return LocalRvolSessionSeedCommandRequest(**values)


def test_command_model_is_frozen_and_retains_paths(tmp_path) -> None:
    request = command(tmp_path)

    assert request.plan_path == tmp_path / "plan.json"
    assert request.metadata_output_path == tmp_path / "metadata.json"
    with pytest.raises(FrozenInstanceError):
        request.plan_path = tmp_path / "other.json"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"plan_path": "plan.json"}, "plan_path must be a pathlib.Path."),
        (
            {"metadata_output_path": "metadata.json"},
            "metadata_output_path must be a pathlib.Path.",
        ),
    ],
)
def test_path_type_errors(tmp_path, overrides, message) -> None:
    with pytest.raises(TypeError) as exc_info:
        validate_local_rvol_session_seed_command(command(tmp_path, **overrides))

    assert str(exc_info.value) == message


def test_distinct_path_requirement(tmp_path) -> None:
    request = command(tmp_path, metadata_output_path=tmp_path / "plan.json")

    with pytest.raises(LocalRvolSessionSeedCommandError) as exc_info:
        validate_local_rvol_session_seed_command(request)

    assert str(exc_info.value) == "PLAN_PATH_EQUALS_METADATA_OUTPUT"


def test_success_report_and_result(tmp_path) -> None:
    request = command(tmp_path)
    write_plan(request.plan_path, payload())

    result = run_local_rvol_session_seed(request)
    report = render_local_rvol_session_seed_success_report(request, result)

    assert request.metadata_output_path.exists()
    assert "Market Sentry Local RVOL Session Seed" in report
    assert f"Plan Path: {request.plan_path}" in report
    assert f"Metadata Path: {request.metadata_output_path}" in report
    assert "Input Mode: EXPLICIT_SESSION_PLAN" in report
    assert "Symbol: RVOL" in report
    assert "Bucket: regular" in report
    assert "Current Session ID: 2026-06-18" in report
    assert "Historical Sessions: 1" in report
    assert "Result: WRITTEN" in report
    assert LOCAL_RVOL_SESSION_SEED_NOTE in report


def test_command_error_report_is_secret_safe(tmp_path) -> None:
    request = command(tmp_path)

    rendered = render_local_rvol_session_seed_command_error(
        request,
        LocalRvolSessionSeedCommandError("PLAN_PATH_EQUALS_METADATA_OUTPUT"),
    )

    assert rendered.splitlines() == [
        "Market Sentry Local RVOL Session Seed",
        f"Plan Path: {request.plan_path}",
        f"Metadata Path: {request.metadata_output_path}",
        "Result: COMMAND_ERROR",
        "Error: PLAN_PATH_EQUALS_METADATA_OUTPUT",
        LOCAL_RVOL_SESSION_SEED_NOTE,
    ]
    assert "Traceback" not in rendered


def test_invalid_plan_creates_no_metadata_output(tmp_path) -> None:
    request = command(tmp_path)
    write_plan(request.plan_path, payload(sessions=[]))

    with pytest.raises(ValueError):
        run_local_rvol_session_seed(request)

    assert not request.metadata_output_path.exists()


def test_output_write_failure_surfaces_as_operation_error(tmp_path) -> None:
    request = command(
        tmp_path,
        metadata_output_path=tmp_path / "missing-parent" / "metadata.json",
    )
    write_plan(request.plan_path, payload())

    with pytest.raises(FileNotFoundError) as exc_info:
        run_local_rvol_session_seed(request)

    rendered = render_local_rvol_session_seed_error(request, exc_info.value)
    assert "Result: ERROR" in rendered
    assert "Error Type: FileNotFoundError" in rendered
    assert "Traceback" not in rendered
    assert not request.metadata_output_path.parent.exists()


def test_helper_source_boundary() -> None:
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert imported_modules == {
        "__future__",
        "dataclasses",
        "pathlib",
        "market_sentry.data.local_rvol_session_seed_plan",
    }

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("load_local_rvol_session_seed_plan") == 1
    assert call_names.count("write_local_rvol_session_seed") == 1
    forbidden_calls = {
        "load_config",
        "create_market_data_provider",
        "StdlibHttpTransport",
        "AlpacaHistoricalBarsFetcher",
        "load_local_historical_rvol_bundle",
        "run_local_json_metadata_workflow_preflight",
        "capture_and_preflight_explicit_alpaca_rvol_bundle",
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "mkdir",
        "getenv",
        "send",
    }
    assert not forbidden_calls & set(call_names)

    lowered = source.lower()
    for forbidden in (
        "config",
        "transport",
        "http",
        "alpaca",
        "fmp",
        "capture",
        "bundle",
        "preflight",
        "scanner",
        "alert",
        "voice",
        "trading",
        "order",
    ):
        assert forbidden not in lowered
