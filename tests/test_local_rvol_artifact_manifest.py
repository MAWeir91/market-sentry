import ast
import inspect
import json
from pathlib import Path

import pytest

from market_sentry.data import local_rvol_artifact_manifest as module
from market_sentry.data.local_rvol_artifact_manifest import (
    LocalRvolArtifactManifestError,
    load_local_rvol_artifact_manifest,
)


def write_manifest(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def valid_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "artifacts": [
            {
                "symbol": " abc ",
                "metadata_path": "artifacts/ABC.metadata.json",
                "bundle_path": "artifacts/ABC.bundle.json",
                "ignored": "ok",
            },
            {
                "symbol": "XYZ",
                "metadata_path": "C:\\market-sentry\\XYZ.metadata.json",
                "bundle_path": "C:\\market-sentry\\XYZ.bundle.json",
            },
        ],
        "ignored_root": True,
    }


def assert_manifest_error(path: Path, payload: object, expected: str) -> None:
    write_manifest(path, payload)
    with pytest.raises(LocalRvolArtifactManifestError) as exc_info:
        load_local_rvol_artifact_manifest(path)
    assert str(exc_info.value) == expected


def test_non_path_error() -> None:
    with pytest.raises(TypeError) as exc_info:
        load_local_rvol_artifact_manifest("manifest.json")  # type: ignore[arg-type]

    assert str(exc_info.value) == "path must be a pathlib.Path."


def test_loads_exact_path_and_literal_artifact_paths(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    write_manifest(path, valid_payload())

    manifest = load_local_rvol_artifact_manifest(path)

    assert manifest.path is path
    assert [artifact.symbol for artifact in manifest.artifacts] == ["ABC", "XYZ"]
    assert manifest.artifacts[0].metadata_path == Path("artifacts/ABC.metadata.json")
    assert manifest.artifacts[0].bundle_path == Path("artifacts/ABC.bundle.json")
    assert str(manifest.artifacts[1].metadata_path) == (
        "C:\\market-sentry\\XYZ.metadata.json"
    )


def test_standard_file_utf8_and_json_errors_propagate(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_local_rvol_artifact_manifest(tmp_path / "missing.json")

    invalid_utf8 = tmp_path / "invalid-utf8.json"
    invalid_utf8.write_bytes(b"\xff")
    with pytest.raises(UnicodeDecodeError):
        load_local_rvol_artifact_manifest(invalid_utf8)

    invalid_json = tmp_path / "invalid-json.json"
    invalid_json.write_text("{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_local_rvol_artifact_manifest(invalid_json)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ([], "INVALID_ENVELOPE_ROOT"),
        ({}, "MISSING_SCHEMA_VERSION"),
        ({"schema_version": True, "artifacts": []}, "UNSUPPORTED_SCHEMA_VERSION"),
        ({"schema_version": 1.0, "artifacts": []}, "UNSUPPORTED_SCHEMA_VERSION"),
        ({"schema_version": "1", "artifacts": []}, "UNSUPPORTED_SCHEMA_VERSION"),
        ({"schema_version": 2, "artifacts": []}, "UNSUPPORTED_SCHEMA_VERSION"),
        ({"schema_version": 1}, "MISSING_REQUIRED_FIELD:artifacts"),
        ({"schema_version": 1, "artifacts": {}}, "INVALID_SEQUENCE:artifacts"),
        (
            {"schema_version": 1, "artifacts": [None]},
            "INVALID_MAPPING:artifacts[0]",
        ),
        (
            {"schema_version": 1, "artifacts": [{"symbol": "ABC"}]},
            "MISSING_REQUIRED_FIELD:artifacts[0].metadata_path",
        ),
        (
            {
                "schema_version": 1,
                "artifacts": [
                    {
                        "symbol": "ABC",
                        "metadata_path": "",
                        "bundle_path": "bundle.json",
                    }
                ],
            },
            "INVALID_STRING:artifacts[0].metadata_path",
        ),
        (
            {
                "schema_version": 1,
                "artifacts": [
                    {
                        "symbol": " ",
                        "metadata_path": "metadata.json",
                        "bundle_path": "bundle.json",
                    }
                ],
            },
            "EMPTY_SYMBOL:artifacts[0].symbol",
        ),
    ],
)
def test_structural_errors(tmp_path, payload, expected) -> None:
    assert_manifest_error(tmp_path / "manifest.json", payload, expected)


def test_duplicate_normalized_symbol_and_same_artifact_path(tmp_path) -> None:
    assert_manifest_error(
        tmp_path / "duplicate.json",
        {
            "schema_version": 1,
            "artifacts": [
                {
                    "symbol": "abc",
                    "metadata_path": "abc-metadata.json",
                    "bundle_path": "abc-bundle.json",
                },
                {
                    "symbol": " ABC ",
                    "metadata_path": "other-metadata.json",
                    "bundle_path": "other-bundle.json",
                },
            ],
        },
        "DUPLICATE_SYMBOL:ABC",
    )
    assert_manifest_error(
        tmp_path / "same-path.json",
        {
            "schema_version": 1,
            "artifacts": [
                {
                    "symbol": "abc",
                    "metadata_path": "same.json",
                    "bundle_path": "same.json",
                }
            ],
        },
        "SAME_ARTIFACT_PATH:ABC",
    )


def test_fresh_models_and_no_cache(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    write_manifest(path, valid_payload())

    first = load_local_rvol_artifact_manifest(path)
    second = load_local_rvol_artifact_manifest(path)

    assert first is not second
    assert first.artifacts[0] is not second.artifacts[0]
    assert first == second


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
        "collections.abc",
        "dataclasses",
        "json",
        "pathlib",
        "typing",
        "market_sentry.data.relative_volume",
    }

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("read_text") == 1
    forbidden_calls = {
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "iterdir",
        "exists",
        "read_bytes",
        "write_text",
        "mkdir",
    }
    assert not forbidden_calls & set(call_names)
