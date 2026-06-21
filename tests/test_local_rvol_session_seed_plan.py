import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path

import pytest

from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRecordStatus,
    HistoricalSessionManifestStatus,
)
from market_sentry.data.json_historical_session_metadata_source import (
    JsonHistoricalSessionMetadataFileSource,
)
from market_sentry.data.local_rvol_session_seed_plan import (
    LocalRvolSessionSeedBuildResult,
    LocalRvolSessionSeedPlan,
    LocalRvolSessionSeedPlanError,
    build_local_rvol_session_seed,
    load_local_rvol_session_seed_plan,
    write_local_rvol_session_seed,
)
from market_sentry.data import local_rvol_session_seed_plan as module


def session(
    session_id: str = "2026-06-17",
    *,
    start: str = "2026-06-17T13:30:00Z",
    end: str = "2026-06-17T20:00:00Z",
    cutoff: str = "2026-06-17T14:00:00Z",
    is_complete=True,
) -> dict[str, object]:
    return {
        "session_id": session_id,
        "session_start_timestamp": start,
        "session_end_timestamp": end,
        "cutoff_timestamp": cutoff,
        "is_complete": is_complete,
    }


def payload(**overrides) -> dict[str, object]:
    value = {
        "schema_version": 1,
        "symbol": " rvol ",
        "bucket": "09:35",
        "current_session_id": "2026-06-18",
        "sessions": [
            session(),
            session(
                "2026-06-16",
                start="2026-06-16T13:30:00Z",
                end="2026-06-16T20:00:00Z",
                cutoff="2026-06-16T14:00:00Z",
            ),
        ],
    }
    value.update(overrides)
    return value


def write_plan(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_canonical_success_writes_existing_writer_compatible_metadata(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "metadata.json"
    write_plan(plan_path, payload())

    plan = load_local_rvol_session_seed_plan(plan_path)
    result = write_local_rvol_session_seed(output_path, plan)

    assert isinstance(result, LocalRvolSessionSeedBuildResult)
    assert result.plan is plan
    assert result.plan.path is plan_path
    assert result.manifest_result.status == HistoricalSessionManifestStatus.OK
    assert len(result.metadata_records) == 2
    rendered = output_path.read_text(encoding="utf-8")
    assert rendered.endswith("\n")
    assert '"$datetime": "2026-06-17T13:30:00Z"' in rendered
    loaded = JsonHistoricalSessionMetadataFileSource(
        output_path,
    ).load_raw_manifest_records(result.manifest_result.request)
    assert loaded[0]["symbol"] == "RVOL"
    assert loaded[0]["bucket"] == "09:35"
    assert loaded[0]["session_id"] == "2026-06-17"
    assert loaded[0]["session_start_timestamp"] == datetime(
        2026,
        6,
        17,
        13,
        30,
        tzinfo=timezone.utc,
    )


def test_exact_path_retention_and_raw_records_are_immutable(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    write_plan(plan_path, payload())

    plan = load_local_rvol_session_seed_plan(plan_path)

    assert isinstance(plan, LocalRvolSessionSeedPlan)
    assert plan.path is plan_path
    assert isinstance(plan.raw_manifest_records, tuple)
    with pytest.raises(TypeError):
        plan.raw_manifest_records[0]["symbol"] = "MUTATE"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        plan.path = tmp_path / "other.json"  # type: ignore[misc]


def test_plan_loader_does_not_write_output(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "metadata.json"
    write_plan(plan_path, payload())

    load_local_rvol_session_seed_plan(plan_path)

    assert not output_path.exists()


def test_invalid_plan_creates_no_output(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "metadata.json"
    write_plan(plan_path, payload(sessions=[]))

    with pytest.raises(LocalRvolSessionSeedPlanError) as exc_info:
        plan = load_local_rvol_session_seed_plan(plan_path)
        write_local_rvol_session_seed(output_path, plan)

    assert str(exc_info.value) == "EMPTY_SESSIONS"
    assert not output_path.exists()


def test_no_output_parent_creation(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    output_path = tmp_path / "missing-parent" / "metadata.json"
    write_plan(plan_path, payload())
    plan = load_local_rvol_session_seed_plan(plan_path)

    with pytest.raises(FileNotFoundError):
        write_local_rvol_session_seed(output_path, plan)

    assert not output_path.parent.exists()


@pytest.mark.parametrize(
    ("bad_payload", "expected"),
    [
        ([], "INVALID_ENVELOPE_ROOT"),
        ({"schema_version": 1, "symbol": "RVOL", "bucket": "09:35", "current_session_id": "C", "sessions": [], "extra": True}, "UNKNOWN_FIELD:extra"),
        ({"schema_version": 1, "symbol": "RVOL", "bucket": "09:35", "sessions": []}, "MISSING_REQUIRED_FIELD:current_session_id"),
        (payload(schema_version=True), "INVALID_SCHEMA_VERSION"),
        (payload(schema_version=1.0), "INVALID_SCHEMA_VERSION"),
        (payload(symbol=" "), "EMPTY_STRING:symbol"),
        (payload(bucket=7), "INVALID_STRING:bucket"),
        (payload(sessions={}), "INVALID_SEQUENCE:sessions"),
        (payload(sessions=[]), "EMPTY_SESSIONS"),
        (payload(sessions=[{"session_id": "H"}]), "MISSING_REQUIRED_FIELD:sessions[0].session_start_timestamp"),
        (payload(sessions=[dict(session(), extra=True)]), "UNKNOWN_FIELD:sessions[0].extra"),
        (payload(sessions=["bad"]), "INVALID_MAPPING:sessions[0]"),
        (payload(sessions=[dict(session(), session_id="")]), "EMPTY_STRING:sessions[0].session_id"),
        (payload(sessions=[dict(session(), cutoff_timestamp=7)]), "INVALID_STRING:sessions[0].cutoff_timestamp"),
        (payload(sessions=[dict(session(), cutoff_timestamp="not-a-date")]), "INVALID_TIMESTAMP:sessions[0].cutoff_timestamp"),
        (payload(sessions=[dict(session(), cutoff_timestamp="2026-06-17T14:00:00")]), "NAIVE_TIMESTAMP:sessions[0].cutoff_timestamp"),
        (payload(sessions=[dict(session(), is_complete=1)]), "INVALID_BOOLEAN:sessions[0].is_complete"),
    ],
)
def test_stable_plan_errors(tmp_path, bad_payload, expected) -> None:
    plan_path = tmp_path / "plan.json"
    write_plan(plan_path, bad_payload)

    with pytest.raises(LocalRvolSessionSeedPlanError) as exc_info:
        load_local_rvol_session_seed_plan(plan_path)

    assert str(exc_info.value) == expected


@pytest.mark.parametrize(
    ("sessions", "expected"),
    [
        (
            [dict(session(), is_complete=False)],
            "HISTORICAL_SESSION_MANIFEST_INVALID:NO_VALID_METADATA:0:INCOMPLETE_SESSION",
        ),
        (
            [session("2026-06-18")],
            "HISTORICAL_SESSION_MANIFEST_INVALID:NO_VALID_METADATA:0:CURRENT_SESSION_IN_HISTORY",
        ),
        (
            [session("DUP"), session("DUP", start="2026-06-16T13:30:00Z", end="2026-06-16T20:00:00Z", cutoff="2026-06-16T14:00:00Z")],
            "HISTORICAL_SESSION_MANIFEST_INVALID:NO_VALID_METADATA:0:DUPLICATE_HISTORICAL_SESSION_ID",
        ),
        (
            [
                session(
                    start="2026-06-17T20:00:00Z",
                    end="2026-06-17T13:30:00Z",
                )
            ],
            "HISTORICAL_SESSION_MANIFEST_INVALID:NO_VALID_METADATA:0:INVALID_SESSION_WINDOW",
        ),
        (
            [session(cutoff="2026-06-17T20:00:00Z")],
            "HISTORICAL_SESSION_MANIFEST_INVALID:NO_VALID_METADATA:0:INVALID_CUTOFF_OUTSIDE_SESSION",
        ),
    ],
)
def test_manifest_failures_are_wrapped_stably(tmp_path, sessions, expected) -> None:
    plan_path = tmp_path / "plan.json"
    write_plan(plan_path, payload(sessions=sessions))
    plan = load_local_rvol_session_seed_plan(plan_path)

    with pytest.raises(LocalRvolSessionSeedPlanError) as exc_info:
        build_local_rvol_session_seed(plan)

    assert str(exc_info.value) == expected


def test_manifest_failure_exact_status_index_and_reason_for_partial(tmp_path) -> None:
    plan_path = tmp_path / "plan.json"
    write_plan(
        plan_path,
        payload(
            sessions=[
                dict(session(), is_complete=False),
                session(
                    "2026-06-16",
                    start="2026-06-16T13:30:00Z",
                    end="2026-06-16T20:00:00Z",
                    cutoff="2026-06-16T14:00:00Z",
                ),
            ]
        ),
    )
    plan = load_local_rvol_session_seed_plan(plan_path)

    with pytest.raises(LocalRvolSessionSeedPlanError) as exc_info:
        build_local_rvol_session_seed(plan)

    assert str(exc_info.value) == (
        "HISTORICAL_SESSION_MANIFEST_INVALID:PARTIAL:0:INCOMPLETE_SESSION"
    )


def test_public_type_errors_are_stable(tmp_path) -> None:
    with pytest.raises(TypeError) as exc_info:
        load_local_rvol_session_seed_plan("plan.json")  # type: ignore[arg-type]
    assert str(exc_info.value) == "path must be a pathlib.Path."

    with pytest.raises(TypeError) as exc_info:
        build_local_rvol_session_seed(object())  # type: ignore[arg-type]
    assert str(exc_info.value) == "plan must be a LocalRvolSessionSeedPlan."

    plan_path = tmp_path / "plan.json"
    write_plan(plan_path, payload())
    plan = load_local_rvol_session_seed_plan(plan_path)
    with pytest.raises(TypeError) as exc_info:
        write_local_rvol_session_seed("metadata.json", plan)  # type: ignore[arg-type]
    assert str(exc_info.value) == "output_path must be a pathlib.Path."


def test_filesystem_and_json_errors_propagate(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_local_rvol_session_seed_plan(tmp_path / "missing.json")

    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_local_rvol_session_seed_plan(path)


def test_source_boundary() -> None:
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
        "collections.abc",
        "dataclasses",
        "datetime",
        "json",
        "pathlib",
        "types",
        "market_sentry.data.historical_session_assembly",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.json_historical_session_metadata_writer",
    }

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("adapt_historical_session_manifest") == 1
    assert call_names.count("write_local_historical_session_metadata") == 1
    forbidden_calls = {
        "load_config",
        "create_market_data_provider",
        "StdlibHttpTransport",
        "AlpacaHistoricalBarsFetcher",
        "load_local_historical_rvol_bundle",
        "run_local_json_metadata_workflow_preflight",
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "mkdir",
        "read_bytes",
        "exists",
        "getenv",
        "send",
    }
    assert not forbidden_calls & set(call_names)

    lowered = source.lower()
    for forbidden in (
        "scanner",
        "alert",
        "voice",
        "trading",
        "order",
        "transport",
        "fmp",
        "capture",
        "bundle",
        "preflight",
        "factory",
        "readiness",
    ):
        assert forbidden not in lowered
