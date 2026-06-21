import ast
from dataclasses import FrozenInstanceError
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from market_sentry.data.local_rvol_artifact_manifest import (
    LocalRvolArtifact,
    LocalRvolArtifactManifest,
    LocalRvolArtifactManifestError,
)
from market_sentry import local_rvol_artifact_manifest_audit_cli as module
from market_sentry.local_rvol_artifact_manifest_audit_cli import (
    LOCAL_RVOL_ARTIFACT_AUDIT_NOTE,
    LocalRvolArtifactAuditCommandRequest,
    LocalRvolArtifactAuditEntry,
    LocalRvolArtifactAuditResult,
    is_local_rvol_artifact_audit_success,
    render_local_rvol_artifact_audit_command_error,
    render_local_rvol_artifact_audit_error,
    render_local_rvol_artifact_audit_report,
    run_local_rvol_artifact_audit,
    validate_local_rvol_artifact_audit_command,
)


def artifact(symbol: str, index: int) -> LocalRvolArtifact:
    return LocalRvolArtifact(
        symbol=symbol,
        metadata_path=Path(f"{symbol.lower()}-{index}-metadata.json"),
        bundle_path=Path(f"{symbol.lower()}-{index}-bundle.json"),
    )


def manifest(*artifacts: LocalRvolArtifact) -> LocalRvolArtifactManifest:
    return LocalRvolArtifactManifest(
        path=Path("manifest.json"),
        artifacts=tuple(artifacts),
    )


def command(path: Path = Path("manifest.json")) -> LocalRvolArtifactAuditCommandRequest:
    return LocalRvolArtifactAuditCommandRequest(manifest_path=path)


def preflight_result(relative_volume: float = 2.0):
    return SimpleNamespace(
        preflight_result=SimpleNamespace(
            workflow_result=SimpleNamespace(
                workflow_bridge_result=SimpleNamespace(
                    workflow_result=SimpleNamespace(
                        harness_result=SimpleNamespace(
                            final_result=SimpleNamespace(
                                time_of_day_result=SimpleNamespace(
                                    relative_volume=relative_volume,
                                )
                            )
                        )
                    )
                )
            )
        )
    )


def test_frozen_models_retain_exact_paths() -> None:
    request = command()
    art = artifact("AAPL", 1)
    entry = LocalRvolArtifactAuditEntry(
        index=0,
        artifact=art,
        status="OK",
        preflight_result=object(),
        relative_volume=2.0,
        error_type=None,
        error_message=None,
    )
    result = LocalRvolArtifactAuditResult(
        manifest=manifest(art),
        entries=(entry,),
    )

    assert request.manifest_path == Path("manifest.json")
    assert result.manifest.artifacts[0] is art
    assert result.entries[0] is entry
    with pytest.raises(FrozenInstanceError):
        request.manifest_path = Path("other.json")  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        entry.status = "FAILED"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.entries = ()  # type: ignore[misc]


def test_non_path_manifest_path_type_error() -> None:
    with pytest.raises(TypeError) as exc_info:
        validate_local_rvol_artifact_audit_command(
            LocalRvolArtifactAuditCommandRequest("manifest.json")  # type: ignore[arg-type]
        )

    assert str(exc_info.value) == "manifest_path must be a pathlib.Path."


def test_loader_runner_and_success_predicate_call_order(monkeypatch) -> None:
    artifacts = (artifact("AAPL", 1), artifact("MSFT", 2))
    loaded_manifest = manifest(*artifacts)
    returned = [preflight_result(2.0), preflight_result(3.5)]
    calls = []

    def fake_loader(path):
        calls.append(("load", path))
        return loaded_manifest

    def fake_runner(metadata_path, bundle_path):
        calls.append(("run", metadata_path, bundle_path))
        return returned.pop(0)

    def fake_success(result):
        calls.append(("success", result))
        return True

    monkeypatch.setattr(module, "load_local_rvol_artifact_manifest", fake_loader)
    monkeypatch.setattr(module, "run_manual_local_json_bundle_preflight", fake_runner)
    monkeypatch.setattr(module, "is_manual_local_json_bundle_preflight_success", fake_success)

    result = run_local_rvol_artifact_audit(command(loaded_manifest.path))

    assert [call[0] for call in calls] == [
        "load",
        "run",
        "success",
        "run",
        "success",
    ]
    assert calls[0][1] is loaded_manifest.path
    assert calls[1][1:] == (artifacts[0].metadata_path, artifacts[0].bundle_path)
    assert calls[3][1:] == (artifacts[1].metadata_path, artifacts[1].bundle_path)
    assert [entry.status for entry in result.entries] == ["OK", "OK"]
    assert [entry.relative_volume for entry in result.entries] == [2.0, 3.5]
    assert is_local_rvol_artifact_audit_success(result) is True


def test_failed_return_and_expected_error_continue_to_later_artifacts(monkeypatch) -> None:
    artifacts = (artifact("AAPL", 1), artifact("MSFT", 2), artifact("TSLA", 3))
    loaded_manifest = manifest(*artifacts)
    calls = []
    first = preflight_result(2.0)
    third = preflight_result(4.2)

    def fake_runner(metadata_path, bundle_path):
        calls.append((metadata_path, bundle_path))
        if len(calls) == 1:
            return first
        if len(calls) == 2:
            raise OSError("missing bundle")
        return third

    def fake_success(result):
        return result is third

    monkeypatch.setattr(
        module,
        "load_local_rvol_artifact_manifest",
        lambda _path: loaded_manifest,
    )
    monkeypatch.setattr(module, "run_manual_local_json_bundle_preflight", fake_runner)
    monkeypatch.setattr(module, "is_manual_local_json_bundle_preflight_success", fake_success)

    result = run_local_rvol_artifact_audit(command())

    assert len(calls) == 3
    assert [entry.status for entry in result.entries] == ["FAILED", "ERROR", "OK"]
    assert result.entries[0].preflight_result is first
    assert result.entries[0].relative_volume is None
    assert result.entries[1].preflight_result is None
    assert result.entries[1].error_type == "OSError"
    assert result.entries[1].error_message == "missing bundle"
    assert result.entries[2].preflight_result is third
    assert result.entries[2].relative_volume == 4.2
    assert is_local_rvol_artifact_audit_success(result) is False


def test_unexpected_runner_exception_propagates(monkeypatch) -> None:
    error = RuntimeError("unexpected")
    monkeypatch.setattr(
        module,
        "load_local_rvol_artifact_manifest",
        lambda _path: manifest(artifact("AAPL", 1)),
    )
    monkeypatch.setattr(
        module,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: (_ for _ in ()).throw(error),
    )

    with pytest.raises(RuntimeError) as exc_info:
        run_local_rvol_artifact_audit(command())

    assert exc_info.value is error


def test_manifest_load_error_propagates_and_skips_runner(monkeypatch) -> None:
    error = LocalRvolArtifactManifestError("UNSUPPORTED_SCHEMA_VERSION")
    monkeypatch.setattr(
        module,
        "load_local_rvol_artifact_manifest",
        lambda _path: (_ for _ in ()).throw(error),
    )
    monkeypatch.setattr(
        module,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: pytest.fail("runner should not run"),
    )

    with pytest.raises(LocalRvolArtifactManifestError) as exc_info:
        run_local_rvol_artifact_audit(command())

    assert exc_info.value is error


def test_empty_manifest_is_success_and_renders_artifacts_zero(monkeypatch) -> None:
    loaded_manifest = manifest()
    monkeypatch.setattr(
        module,
        "load_local_rvol_artifact_manifest",
        lambda _path: loaded_manifest,
    )
    monkeypatch.setattr(
        module,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: pytest.fail("runner should not run for empty manifest"),
    )

    result = run_local_rvol_artifact_audit(command())
    report = render_local_rvol_artifact_audit_report(command(), result)

    assert result.entries == ()
    assert is_local_rvol_artifact_audit_success(result) is True
    assert report.splitlines() == [
        "Market Sentry Local RVOL Artifact Preflight",
        "Manifest Path: manifest.json",
        "Input Mode: EXPLICIT_LOCAL_RVOL_ARTIFACT_MANIFEST",
        "Artifacts: 0",
        "Result: OK",
        LOCAL_RVOL_ARTIFACT_AUDIT_NOTE,
    ]


def test_report_layout_for_ok_failed_and_error_entries() -> None:
    artifacts = (artifact("AAPL", 1), artifact("MSFT", 2), artifact("TSLA", 3))
    result = LocalRvolArtifactAuditResult(
        manifest=manifest(*artifacts),
        entries=(
            LocalRvolArtifactAuditEntry(0, artifacts[0], "OK", object(), 2.0, None, None),
            LocalRvolArtifactAuditEntry(1, artifacts[1], "FAILED", object(), None, None, None),
            LocalRvolArtifactAuditEntry(2, artifacts[2], "ERROR", None, None, "OSError", "missing"),
        ),
    )

    report = render_local_rvol_artifact_audit_report(command(), result)

    assert report.splitlines() == [
        "Market Sentry Local RVOL Artifact Preflight",
        "Manifest Path: manifest.json",
        "Input Mode: EXPLICIT_LOCAL_RVOL_ARTIFACT_MANIFEST",
        "Artifacts: 3",
        "Artifact 1 Symbol: AAPL",
        "Artifact 1 Metadata Path: aapl-1-metadata.json",
        "Artifact 1 Bundle Path: aapl-1-bundle.json",
        "Artifact 1 Result: OK",
        "Artifact 1 Relative Volume: 2.0x",
        "Artifact 1 Error Type: N/A",
        "Artifact 1 Error: N/A",
        "Artifact 2 Symbol: MSFT",
        "Artifact 2 Metadata Path: msft-2-metadata.json",
        "Artifact 2 Bundle Path: msft-2-bundle.json",
        "Artifact 2 Result: FAILED",
        "Artifact 2 Relative Volume: N/A",
        "Artifact 2 Error Type: N/A",
        "Artifact 2 Error: N/A",
        "Artifact 3 Symbol: TSLA",
        "Artifact 3 Metadata Path: tsla-3-metadata.json",
        "Artifact 3 Bundle Path: tsla-3-bundle.json",
        "Artifact 3 Result: ERROR",
        "Artifact 3 Relative Volume: N/A",
        "Artifact 3 Error Type: OSError",
        "Artifact 3 Error: missing",
        "Result: FAILED",
        LOCAL_RVOL_ARTIFACT_AUDIT_NOTE,
    ]
    assert "Traceback" not in report


def test_error_reports_are_stable() -> None:
    request = command()
    command_report = render_local_rvol_artifact_audit_command_error(
        request,
        TypeError("manifest_path must be a pathlib.Path."),
    )
    operation_report = render_local_rvol_artifact_audit_error(
        request,
        FileNotFoundError("missing"),
    )

    assert command_report.splitlines() == [
        "Market Sentry Local RVOL Artifact Preflight",
        "Manifest Path: manifest.json",
        "Result: COMMAND_ERROR",
        "Error: manifest_path must be a pathlib.Path.",
        LOCAL_RVOL_ARTIFACT_AUDIT_NOTE,
    ]
    assert operation_report.splitlines() == [
        "Market Sentry Local RVOL Artifact Preflight",
        "Manifest Path: manifest.json",
        "Result: ERROR",
        "Error Type: FileNotFoundError",
        "Error: missing",
        LOCAL_RVOL_ARTIFACT_AUDIT_NOTE,
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
    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }

    assert imported_modules == {
        "dataclasses",
        "pathlib",
        "market_sentry.data.local_rvol_artifact_manifest",
        "market_sentry.local_json_bundle_preflight_cli",
    }
    assert "_final_relative_volume" not in function_names

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("load_local_rvol_artifact_manifest") == 1
    assert call_names.count("run_manual_local_json_bundle_preflight") == 1
    assert call_names.count("is_manual_local_json_bundle_preflight_success") == 1
    forbidden_calls = {
        "load_config",
        "getenv",
        "create_market_data_provider",
        "StdlibHttpTransport",
        "AlpacaHistoricalBarsFetcher",
        "FMPFloatFetcher",
        "LocalRvolArtifactProvider",
        "capture_and_preflight_explicit_alpaca_rvol_bundle",
        "write_local_historical_rvol_bundle",
        "write_local_historical_session_metadata",
        "write_text",
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "mkdir",
        "send",
    }
    assert not forbidden_calls & set(call_names)

    imported_lower = {module_name.lower() for module_name in imported_modules}
    for forbidden in (
        "config",
        "env",
        "http",
        "transport",
        "alpaca",
        "fmp",
        "provider",
        "scanner",
        "alert",
        "voice",
        "capture",
        "writer",
    ):
        assert not any(forbidden in module_name for module_name in imported_lower)
