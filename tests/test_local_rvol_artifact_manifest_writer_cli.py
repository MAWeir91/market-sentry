import ast
from dataclasses import FrozenInstanceError
import inspect
from pathlib import Path

import pytest

from market_sentry.data.local_rvol_artifact_manifest import LocalRvolArtifact
from market_sentry.data.local_rvol_artifact_manifest_writer import (
    LocalRvolArtifactManifestWriteError,
)
from market_sentry import local_rvol_artifact_manifest_writer_cli as module
from market_sentry.local_rvol_artifact_manifest_writer_cli import (
    LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_NOTE,
    LocalRvolArtifactManifestWriterCommandError,
    LocalRvolArtifactManifestWriterCommandRequest,
    LocalRvolArtifactManifestWriterCommandResult,
    render_local_rvol_artifact_manifest_writer_command_error,
    render_local_rvol_artifact_manifest_writer_error,
    render_local_rvol_artifact_manifest_writer_success_report,
    run_local_rvol_artifact_manifest_writer,
    validate_local_rvol_artifact_manifest_writer_command,
)


def command(**overrides) -> LocalRvolArtifactManifestWriterCommandRequest:
    values = {
        "output_path": Path("manifest.json"),
        "artifact_declarations": (
            ("aapl", "aapl-metadata.json", "aapl-bundle.json"),
        ),
    }
    values.update(overrides)
    return LocalRvolArtifactManifestWriterCommandRequest(**values)


def test_request_and_result_are_frozen() -> None:
    request = command()
    result = LocalRvolArtifactManifestWriterCommandResult(
        output_path=Path("manifest.json"),
        artifacts=(LocalRvolArtifact("AAPL", Path("m.json"), Path("b.json")),),
    )

    with pytest.raises(FrozenInstanceError):
        request.output_path = Path("other.json")  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.artifacts = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    ("request_value", "expected"),
    [
        (
            object(),
            "command must be a LocalRvolArtifactManifestWriterCommandRequest.",
        ),
        (
            command(output_path=None, artifact_declarations=(("AAPL", "m", "b"),)),
            "--local-rvol-artifact requires --local-rvol-artifact-manifest-write",
        ),
        (
            command(output_path=None, artifact_declarations=()),
            "MISSING_MANIFEST_OUTPUT_PATH",
        ),
        (
            command(output_path="manifest.json"),
            "output_path must be a pathlib.Path.",
        ),
        (
            command(artifact_declarations=[("AAPL", "m", "b")]),
            "artifact_declarations must be a tuple.",
        ),
        (
            command(artifact_declarations=(["AAPL", "m", "b"],)),
            "INVALID_ARTIFACT_DECLARATION:0",
        ),
        (
            command(artifact_declarations=(("AAPL", "m"),)),
            "INVALID_ARTIFACT_DECLARATION:0",
        ),
        (
            command(artifact_declarations=(("AAPL", "m", 7),)),
            "INVALID_ARTIFACT_DECLARATION:0",
        ),
    ],
)
def test_command_validation_errors_are_stable(request_value, expected) -> None:
    error_type = (
        TypeError
        if expected.endswith(".") and "requires" not in expected
        else LocalRvolArtifactManifestWriterCommandError
    )
    with pytest.raises(error_type) as exc_info:
        validate_local_rvol_artifact_manifest_writer_command(request_value)  # type: ignore[arg-type]

    assert str(exc_info.value) == expected


def test_literal_path_construction_and_writer_request(monkeypatch) -> None:
    calls = []
    normalized = (
        LocalRvolArtifact("AAPL", Path("aapl-meta.json"), Path("aapl-bundle.json")),
    )

    def fake_writer(request):
        calls.append(request)
        return normalized

    monkeypatch.setattr(module, "write_local_rvol_artifact_manifest", fake_writer)

    result = run_local_rvol_artifact_manifest_writer(
        command(
            output_path=Path("manifest.json"),
            artifact_declarations=((" aapl ", "aapl-meta.json", "aapl-bundle.json"),),
        )
    )

    assert len(calls) == 1
    writer_request = calls[0]
    assert writer_request.output_path == Path("manifest.json")
    assert writer_request.artifacts == (
        LocalRvolArtifact(" aapl ", Path("aapl-meta.json"), Path("aapl-bundle.json")),
    )
    assert result.output_path == Path("manifest.json")
    assert result.artifacts is normalized


@pytest.mark.parametrize(
    ("declarations", "expected"),
    [
        ((), "MISSING_ARTIFACTS"),
        (((" ", "m.json", "b.json"),), "EMPTY_SYMBOL:artifacts[0].symbol"),
        (
            (("AAPL", "a-m.json", "a-b.json"), ("aapl", "b-m.json", "b-b.json")),
            "DUPLICATE_SYMBOL:AAPL",
        ),
        ((("AAPL", "same.json", "same.json"),), "SAME_ARTIFACT_PATH:AAPL"),
        ((("AAPL", "manifest.json", "bundle.json"),), "OUTPUT_PATH_CONFLICT:AAPL"),
        ((("AAPL", "metadata.json", "manifest.json"),), "OUTPUT_PATH_CONFLICT:AAPL"),
    ],
)
def test_writer_validation_errors_create_no_output(tmp_path, declarations, expected) -> None:
    output_path = tmp_path / "manifest.json"
    actual_declarations = declarations
    if "OUTPUT_PATH_CONFLICT" in expected:
        actual_declarations = tuple(
            (
                symbol,
                str(output_path) if metadata == "manifest.json" else metadata,
                str(output_path) if bundle == "manifest.json" else bundle,
            )
            for symbol, metadata, bundle in declarations
        )

    with pytest.raises(LocalRvolArtifactManifestWriteError) as exc_info:
        run_local_rvol_artifact_manifest_writer(
            command(
                output_path=output_path,
                artifact_declarations=actual_declarations,
            )
        )

    assert str(exc_info.value) == expected
    assert not output_path.exists()


def test_success_report_single_and_multi_artifact(tmp_path) -> None:
    output_path = tmp_path / "manifest.json"
    request = command(
        output_path=output_path,
        artifact_declarations=(
            ("aapl", "aapl-meta.json", "aapl-bundle.json"),
            ("msft", "msft-meta.json", "msft-bundle.json"),
        ),
    )

    result = run_local_rvol_artifact_manifest_writer(request)
    report = render_local_rvol_artifact_manifest_writer_success_report(
        request,
        result,
    )

    assert output_path.exists()
    assert report.splitlines() == [
        "Market Sentry Local RVOL Artifact Manifest Writer",
        f"Manifest Path: {output_path}",
        "Artifacts: 2",
        "Artifact 1 Symbol: AAPL",
        "Artifact 1 Metadata Path: aapl-meta.json",
        "Artifact 1 Bundle Path: aapl-bundle.json",
        "Artifact 2 Symbol: MSFT",
        "Artifact 2 Metadata Path: msft-meta.json",
        "Artifact 2 Bundle Path: msft-bundle.json",
        "Result: OK",
        LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_NOTE,
    ]


def test_error_reports_have_no_traceback() -> None:
    request = command(output_path=None, artifact_declarations=())
    command_report = render_local_rvol_artifact_manifest_writer_command_error(
        request,
        LocalRvolArtifactManifestWriterCommandError("MISSING_MANIFEST_OUTPUT_PATH"),
    )
    operation_report = render_local_rvol_artifact_manifest_writer_error(
        request,
        OSError("disk unavailable"),
    )

    assert command_report.splitlines() == [
        "Market Sentry Local RVOL Artifact Manifest Writer",
        "Manifest Path: N/A",
        "Result: COMMAND_ERROR",
        "Error: MISSING_MANIFEST_OUTPUT_PATH",
        LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_NOTE,
    ]
    assert operation_report.splitlines() == [
        "Market Sentry Local RVOL Artifact Manifest Writer",
        "Manifest Path: N/A",
        "Result: ERROR",
        "Error Type: OSError",
        "Error: disk unavailable",
        LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_NOTE,
    ]
    assert "Traceback" not in command_report
    assert "Traceback" not in operation_report


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
        "pathlib",
        "typing",
        "market_sentry.data.local_rvol_artifact_manifest",
        "market_sentry.data.local_rvol_artifact_manifest_writer",
    }

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("write_local_rvol_artifact_manifest") == 1
    forbidden_calls = {
        "load_config",
        "getenv",
        "load_local_rvol_artifact_manifest",
        "run_local_rvol_artifact_audit",
        "run_manual_local_json_bundle_preflight",
        "create_market_data_provider",
        "StdlibHttpTransport",
        "capture_and_preflight_explicit_alpaca_rvol_bundle",
        "ScannerEngine",
        "LocalTTSSpeaker",
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "mkdir",
        "send",
    }
    assert not forbidden_calls & set(call_names)
