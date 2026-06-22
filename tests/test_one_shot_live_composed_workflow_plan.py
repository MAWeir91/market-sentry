import ast
from dataclasses import FrozenInstanceError
import inspect
import json
from pathlib import Path

import pytest

from market_sentry.data import one_shot_live_composed_workflow_plan as module
from market_sentry.data.one_shot_live_composed_workflow_plan import (
    OneShotLiveComposedWorkflowArtifact,
    OneShotLiveComposedWorkflowPlanError,
    load_one_shot_live_composed_workflow_plan,
)


def plan_payload(**overrides):
    value = {
        "schema_version": 1,
        "manifest_output_path": "manifest.json",
        "artifacts": [
            {
                "symbol": " aapl ",
                "metadata_input_path": "seed.json",
                "metadata_output_path": "metadata.json",
                "bundle_output_path": "bundle.json",
                "historical_start": "2026-05-18T13:30:00Z",
                "historical_end": "2026-06-18T14:00:00Z",
                "historical_max_pages": 25,
                "current_start": "2026-06-18T13:30:00Z",
                "current_end": "2026-06-18T14:00:00Z",
                "current_max_pages": 2,
                "current_session_id": "2026-06-18",
                "bucket": "regular",
                "cutoff": "2026-06-18T14:00:00Z",
                "minimum_historical_sessions": 20,
                "timeframe": "1Min",
                "page_limit": 1000,
                "sort": "asc",
            }
        ],
    }
    value.update(overrides)
    return value


def write_plan(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_plan_retains_literal_paths_and_normalizes_symbols(tmp_path) -> None:
    path = tmp_path / "workflow.json"
    write_plan(path, plan_payload())

    plan = load_one_shot_live_composed_workflow_plan(path)

    assert plan.path is path
    assert plan.manifest_output_path == Path("manifest.json")
    assert plan.artifacts[0].symbol == "AAPL"
    assert plan.artifacts[0].metadata_input_path == Path("seed.json")
    assert plan.artifacts[0].metadata_output_path == Path("metadata.json")
    assert plan.artifacts[0].bundle_output_path == Path("bundle.json")

    with pytest.raises(FrozenInstanceError):
        plan.artifacts[0].symbol = "MSFT"


def test_loader_reads_plan_once_and_not_declared_artifacts(monkeypatch) -> None:
    calls = []
    payload = json.dumps(plan_payload())

    def fake_read_text(self, *, encoding):
        calls.append((self, encoding))
        assert self == Path("workflow.json")
        return payload

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    plan = load_one_shot_live_composed_workflow_plan(Path("workflow.json"))

    assert plan.path == Path("workflow.json")
    assert calls == [(Path("workflow.json"), "utf-8")]


def test_non_path_plan_path_is_rejected() -> None:
    with pytest.raises(TypeError, match="path must be a pathlib.Path."):
        load_one_shot_live_composed_workflow_plan("workflow.json")


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ([], "INVALID_ENVELOPE_ROOT"),
        ({"artifacts": []}, "MISSING_SCHEMA_VERSION"),
        (
            {"schema_version": True, "artifacts": []},
            "UNSUPPORTED_SCHEMA_VERSION",
        ),
        (
            {"schema_version": 1.0, "artifacts": []},
            "UNSUPPORTED_SCHEMA_VERSION",
        ),
        (
            {"schema_version": 2, "artifacts": []},
            "UNSUPPORTED_SCHEMA_VERSION",
        ),
        (
            {"schema_version": 1, "manifest_output_path": "", "artifacts": []},
            "INVALID_STRING:manifest_output_path",
        ),
        (
            {"schema_version": 1, "manifest_output_path": "manifest.json"},
            "MISSING_REQUIRED_FIELD:artifacts",
        ),
        (
            {
                "schema_version": 1,
                "manifest_output_path": "manifest.json",
                "artifacts": {},
            },
            "INVALID_SEQUENCE:artifacts",
        ),
        (
            {
                "schema_version": 1,
                "manifest_output_path": "manifest.json",
                "artifacts": [],
            },
            "EMPTY_ARTIFACTS",
        ),
    ],
)
def test_envelope_errors_are_stable(tmp_path, payload, expected) -> None:
    path = tmp_path / "workflow.json"
    write_plan(path, payload)

    with pytest.raises(OneShotLiveComposedWorkflowPlanError, match=expected):
        load_one_shot_live_composed_workflow_plan(path)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("symbol", "", "EMPTY_SYMBOL:artifacts\\[0\\].symbol"),
        ("metadata_input_path", "", "INVALID_STRING:artifacts\\[0\\].metadata_input_path"),
        ("historical_start", None, "INVALID_STRING:artifacts\\[0\\].historical_start"),
        ("historical_max_pages", True, "INVALID_INTEGER:artifacts\\[0\\].historical_max_pages"),
        ("current_max_pages", 1.0, "INVALID_INTEGER:artifacts\\[0\\].current_max_pages"),
        ("minimum_historical_sessions", "20", "INVALID_INTEGER:artifacts\\[0\\].minimum_historical_sessions"),
        ("page_limit", False, "INVALID_INTEGER:artifacts\\[0\\].page_limit"),
        ("sort", "newest", "INVALID_SORT:artifacts\\[0\\].sort"),
    ],
)
def test_artifact_field_errors_are_stable(tmp_path, field, value, expected) -> None:
    payload = plan_payload()
    payload["artifacts"][0][field] = value
    path = tmp_path / "workflow.json"
    write_plan(path, payload)

    with pytest.raises(OneShotLiveComposedWorkflowPlanError, match=expected):
        load_one_shot_live_composed_workflow_plan(path)


def test_missing_required_artifact_field_is_stable(tmp_path) -> None:
    payload = plan_payload()
    del payload["artifacts"][0]["bucket"]
    path = tmp_path / "workflow.json"
    write_plan(path, payload)

    with pytest.raises(
        OneShotLiveComposedWorkflowPlanError,
        match="MISSING_REQUIRED_FIELD:artifacts\\[0\\].bucket",
    ):
        load_one_shot_live_composed_workflow_plan(path)


def test_duplicate_normalized_symbols_are_rejected(tmp_path) -> None:
    first = plan_payload()["artifacts"][0]
    second = dict(first)
    second.update(
        {
            "symbol": "AAPL",
            "metadata_input_path": "seed-2.json",
            "metadata_output_path": "metadata-2.json",
            "bundle_output_path": "bundle-2.json",
        }
    )
    path = tmp_path / "workflow.json"
    write_plan(path, plan_payload(artifacts=[first, second]))

    with pytest.raises(OneShotLiveComposedWorkflowPlanError, match="DUPLICATE_SYMBOL:AAPL"):
        load_one_shot_live_composed_workflow_plan(path)


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        (
            {"metadata_output_path": "seed.json"},
            "SAME_CAPTURE_PATH:AAPL",
        ),
        (
            {"bundle_output_path": "seed.json"},
            "SAME_CAPTURE_PATH:AAPL",
        ),
        (
            {"bundle_output_path": "metadata.json"},
            "SAME_CAPTURE_PATH:AAPL",
        ),
        (
            {"metadata_input_path": "manifest.json"},
            "MANIFEST_OUTPUT_COLLISION:AAPL",
        ),
        (
            {"metadata_output_path": "manifest.json"},
            "MANIFEST_OUTPUT_COLLISION:AAPL",
        ),
        (
            {"bundle_output_path": "manifest.json"},
            "MANIFEST_OUTPUT_COLLISION:AAPL",
        ),
    ],
)
def test_single_artifact_path_collisions_are_rejected(tmp_path, updates, expected) -> None:
    payload = plan_payload()
    payload["artifacts"][0].update(updates)
    path = tmp_path / "workflow.json"
    write_plan(path, payload)

    with pytest.raises(OneShotLiveComposedWorkflowPlanError, match=expected):
        load_one_shot_live_composed_workflow_plan(path)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        (
            "metadata_output_path",
            "bundle.json",
            "DUPLICATE_OUTPUT_PATH:artifacts\\[1\\].metadata_output_path",
        ),
        (
            "bundle_output_path",
            "metadata.json",
            "DUPLICATE_OUTPUT_PATH:artifacts\\[1\\].bundle_output_path",
        ),
        (
            "metadata_input_path",
            "metadata.json",
            "DUPLICATE_OUTPUT_PATH:artifacts\\[1\\].metadata_input_path",
        ),
    ],
)
def test_cross_artifact_output_collisions_are_rejected(
    tmp_path,
    field,
    value,
    expected,
) -> None:
    first = plan_payload()["artifacts"][0]
    second = dict(first)
    second.update(
        {
            "symbol": "MSFT",
            "metadata_input_path": "seed-2.json",
            "metadata_output_path": "metadata-2.json",
            "bundle_output_path": "bundle-2.json",
        }
    )
    second[field] = value
    path = tmp_path / "workflow.json"
    write_plan(path, plan_payload(artifacts=[first, second]))

    with pytest.raises(OneShotLiveComposedWorkflowPlanError, match=expected):
        load_one_shot_live_composed_workflow_plan(path)


def test_source_boundaries_are_strict() -> None:
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported.update(
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    )
    call_names = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert imported <= {
        "dataclasses",
        "json",
        "pathlib",
        "typing",
        "market_sentry.data.relative_volume",
    }
    assert not {
        "resolve",
        "absolute",
        "expanduser",
        "exists",
        "is_file",
        "is_dir",
        "glob",
        "rglob",
        "write_text",
    } & call_names
