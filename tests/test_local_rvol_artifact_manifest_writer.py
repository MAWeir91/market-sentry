import ast
from dataclasses import FrozenInstanceError
import inspect
import json
from pathlib import Path

import pytest

from market_sentry.data.local_rvol_artifact_manifest import LocalRvolArtifact
from market_sentry.data import local_rvol_artifact_manifest_writer as module
from market_sentry.data.local_rvol_artifact_manifest_writer import (
    LocalRvolArtifactManifestWriteError,
    LocalRvolArtifactManifestWriteRequest,
    render_local_rvol_artifact_manifest,
    validate_local_rvol_artifact_manifest_write_request,
    write_local_rvol_artifact_manifest,
)


def artifact(
    symbol: object = "aapl",
    metadata_path: object = Path("aapl-metadata.json"),
    bundle_path: object = Path("aapl-bundle.json"),
) -> LocalRvolArtifact:
    return LocalRvolArtifact(
        symbol=symbol,  # type: ignore[arg-type]
        metadata_path=metadata_path,  # type: ignore[arg-type]
        bundle_path=bundle_path,  # type: ignore[arg-type]
    )


def request(**overrides) -> LocalRvolArtifactManifestWriteRequest:
    values = {
        "output_path": Path("manifest.json"),
        "artifacts": (artifact(),),
    }
    values.update(overrides)
    return LocalRvolArtifactManifestWriteRequest(**values)


def test_request_is_frozen() -> None:
    value = request()

    with pytest.raises(FrozenInstanceError):
        value.output_path = Path("other.json")  # type: ignore[misc]


def test_validation_returns_normalized_new_tuple_in_order() -> None:
    source_artifacts = (
        artifact(" aapl ", Path("aapl-meta.json"), Path("aapl-bundle.json")),
        artifact(" msft ", Path("msft-meta.json"), Path("msft-bundle.json")),
    )

    normalized = validate_local_rvol_artifact_manifest_write_request(
        request(artifacts=source_artifacts)
    )

    assert normalized is not source_artifacts
    assert [item.symbol for item in normalized] == ["AAPL", "MSFT"]
    assert normalized[0].metadata_path == Path("aapl-meta.json")
    assert normalized[1].bundle_path == Path("msft-bundle.json")


def test_type_errors_are_stable() -> None:
    with pytest.raises(TypeError) as exc_info:
        validate_local_rvol_artifact_manifest_write_request(object())  # type: ignore[arg-type]
    assert str(exc_info.value) == (
        "request must be a LocalRvolArtifactManifestWriteRequest."
    )

    with pytest.raises(TypeError) as exc_info:
        validate_local_rvol_artifact_manifest_write_request(
            request(output_path="manifest.json")  # type: ignore[arg-type]
        )
    assert str(exc_info.value) == "output_path must be a pathlib.Path."

    with pytest.raises(TypeError) as exc_info:
        validate_local_rvol_artifact_manifest_write_request(
            request(artifacts=[artifact()])  # type: ignore[arg-type]
        )
    assert str(exc_info.value) == "artifacts must be a tuple."

    with pytest.raises(TypeError) as exc_info:
        validate_local_rvol_artifact_manifest_write_request(
            request(artifacts=(object(),))  # type: ignore[arg-type]
        )
    assert str(exc_info.value) == "artifacts[0] must be a LocalRvolArtifact."

    with pytest.raises(TypeError) as exc_info:
        validate_local_rvol_artifact_manifest_write_request(
            request(artifacts=(artifact(metadata_path="meta.json"),))
        )
    assert str(exc_info.value) == (
        "artifacts[0].metadata_path must be a pathlib.Path."
    )

    with pytest.raises(TypeError) as exc_info:
        validate_local_rvol_artifact_manifest_write_request(
            request(artifacts=(artifact(bundle_path="bundle.json"),))
        )
    assert str(exc_info.value) == "artifacts[0].bundle_path must be a pathlib.Path."


@pytest.mark.parametrize(
    ("artifacts", "expected"),
    [
        ((), "MISSING_ARTIFACTS"),
        ((artifact(" "),), "EMPTY_SYMBOL:artifacts[0].symbol"),
        ((artifact(None),), "EMPTY_SYMBOL:artifacts[0].symbol"),
        (
            (
                artifact("aapl", Path("a-meta.json"), Path("a-bundle.json")),
                artifact(" AAPL ", Path("b-meta.json"), Path("b-bundle.json")),
            ),
            "DUPLICATE_SYMBOL:AAPL",
        ),
        (
            (artifact("AAPL", Path("same.json"), Path("same.json")),),
            "SAME_ARTIFACT_PATH:AAPL",
        ),
        (
            (artifact("AAPL", Path("manifest.json"), Path("bundle.json")),),
            "OUTPUT_PATH_CONFLICT:AAPL",
        ),
        (
            (artifact("AAPL", Path("metadata.json"), Path("manifest.json")),),
            "OUTPUT_PATH_CONFLICT:AAPL",
        ),
    ],
)
def test_validation_errors_prevent_writes(tmp_path, artifacts, expected) -> None:
    output_path = tmp_path / "manifest.json"

    with pytest.raises(LocalRvolArtifactManifestWriteError) as exc_info:
        write_local_rvol_artifact_manifest(
            LocalRvolArtifactManifestWriteRequest(
                output_path=Path("manifest.json")
                if "OUTPUT_PATH_CONFLICT" in expected
                else output_path,
                artifacts=artifacts,
            )
        )

    assert str(exc_info.value) == expected
    assert not output_path.exists()


def test_canonical_rendering_preserves_order_and_key_order() -> None:
    artifacts = (
        LocalRvolArtifact("AAPL", Path("aapl-metadata.json"), Path("aapl-bundle.json")),
        LocalRvolArtifact("MSFT", Path("msft-metadata.json"), Path("msft-bundle.json")),
    )

    rendered = render_local_rvol_artifact_manifest(artifacts)

    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")
    assert rendered == (
        "{\n"
        '  "schema_version": 1,\n'
        '  "artifacts": [\n'
        "    {\n"
        '      "symbol": "AAPL",\n'
        '      "metadata_path": "aapl-metadata.json",\n'
        '      "bundle_path": "aapl-bundle.json"\n'
        "    },\n"
        "    {\n"
        '      "symbol": "MSFT",\n'
        '      "metadata_path": "msft-metadata.json",\n'
        '      "bundle_path": "msft-bundle.json"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )
    payload = json.loads(rendered)
    assert [item["symbol"] for item in payload["artifacts"]] == ["AAPL", "MSFT"]


def test_render_type_errors_are_stable() -> None:
    with pytest.raises(TypeError) as exc_info:
        render_local_rvol_artifact_manifest([artifact()])  # type: ignore[arg-type]
    assert str(exc_info.value) == "artifacts must be a tuple."

    with pytest.raises(TypeError) as exc_info:
        render_local_rvol_artifact_manifest((object(),))  # type: ignore[arg-type]
    assert str(exc_info.value) == "artifacts[0] must be a LocalRvolArtifact."


def test_write_text_once_with_utf8_after_render(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "manifest.json"
    calls = []
    original_write_text = Path.write_text

    def tracked_write_text(self, data, *, encoding=None, errors=None, newline=None):
        calls.append((self, data, encoding))
        return original_write_text(
            self,
            data,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )

    monkeypatch.setattr(Path, "write_text", tracked_write_text)

    normalized = write_local_rvol_artifact_manifest(
        request(
            output_path=output_path,
            artifacts=(artifact("aapl", Path("metadata.json"), Path("bundle.json")),),
        )
    )

    assert [item.symbol for item in normalized] == ["AAPL"]
    assert calls == [
        (
            output_path,
            render_local_rvol_artifact_manifest(normalized),
            "utf-8",
        )
    ]
    assert output_path.read_text(encoding="utf-8") == (
        render_local_rvol_artifact_manifest(normalized)
    )


def test_no_directory_creation_or_readback(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "missing-parent" / "manifest.json"
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *_args, **_kwargs: pytest.fail("read_text should not run"),
    )
    monkeypatch.setattr(
        Path,
        "exists",
        lambda *_args, **_kwargs: pytest.fail("exists should not run"),
    )

    with pytest.raises(FileNotFoundError):
        write_local_rvol_artifact_manifest(request(output_path=output_path))

    assert not output_path.parent.is_dir()


def test_os_error_propagates_unchanged(monkeypatch, tmp_path) -> None:
    error = OSError("disk unavailable")

    def fake_write_text(self, data, *, encoding=None):
        raise error

    monkeypatch.setattr(Path, "write_text", fake_write_text)

    with pytest.raises(OSError) as exc_info:
        write_local_rvol_artifact_manifest(request(output_path=tmp_path / "out.json"))

    assert exc_info.value is error


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
        "dataclasses",
        "json",
        "pathlib",
        "market_sentry.data.local_rvol_artifact_manifest",
        "market_sentry.data.relative_volume",
    }

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("write_text") == 1
    forbidden_calls = {
        "load_local_rvol_artifact_manifest",
        "LocalRvolArtifactProvider",
        "run_local_rvol_artifact_audit",
        "run_manual_local_json_bundle_preflight",
        "load_config",
        "getenv",
        "resolve",
        "absolute",
        "expanduser",
        "exists",
        "is_file",
        "is_dir",
        "read_text",
        "open",
        "glob",
        "rglob",
        "mkdir",
        "send",
    }
    assert not forbidden_calls & set(call_names)
