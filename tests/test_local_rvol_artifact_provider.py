import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from market_sentry.data import local_rvol_artifact_provider as module
from market_sentry.data.local_rvol_artifact_manifest import (
    LocalRvolArtifact,
    LocalRvolArtifactManifest,
)
from market_sentry.data.local_rvol_artifact_provider import (
    LocalRvolArtifactProvider,
    LocalRvolArtifactProviderError,
)


def artifact(symbol: str) -> LocalRvolArtifact:
    return LocalRvolArtifact(
        symbol=symbol,
        metadata_path=Path(f"{symbol}.metadata.json"),
        bundle_path=Path(f"{symbol}.bundle.json"),
    )


def manifest(*artifacts: LocalRvolArtifact) -> LocalRvolArtifactManifest:
    return LocalRvolArtifactManifest(
        path=Path("manifest.json"),
        artifacts=artifacts,
    )


def preflight(relative_volume=2.0):
    tod = SimpleNamespace(relative_volume=relative_volume)
    final = SimpleNamespace(time_of_day_result=tod)
    harness = SimpleNamespace(final_result=final)
    coordinator = SimpleNamespace(harness_result=harness)
    bridge = SimpleNamespace(workflow_result=coordinator)
    workflow = SimpleNamespace(workflow_bridge_result=bridge)
    return SimpleNamespace(preflight_result=SimpleNamespace(workflow_result=workflow))


def test_constructor_retains_exact_manifest() -> None:
    loaded = manifest(artifact("ABC"))
    provider = LocalRvolArtifactProvider(loaded)

    assert provider.manifest is loaded
    assert provider.latest_results == ()


def test_empty_requested_symbols_returns_empty_without_preflight(monkeypatch) -> None:
    provider = LocalRvolArtifactProvider(manifest(artifact("ABC")))
    monkeypatch.setattr(
        module,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: pytest.fail("preflight should not run"),
    )

    assert provider.get_relative_volumes([" ", ""]) == {}
    assert provider.latest_results == ()


def test_missing_required_artifact() -> None:
    provider = LocalRvolArtifactProvider(manifest(artifact("ABC")))

    with pytest.raises(LocalRvolArtifactProviderError) as exc_info:
        provider.get_relative_volumes(["ABC", "XYZ"])

    assert str(exc_info.value) == "MISSING_ARTIFACT:XYZ"
    assert provider.latest_results == ()


def test_requested_order_one_preflight_per_symbol_and_mapping(monkeypatch) -> None:
    calls = []
    results = {
        "ABC": preflight(2.0),
        "XYZ": preflight(3.5),
    }

    def fake_preflight(metadata_path, bundle_path):
        symbol = metadata_path.name.split(".")[0]
        calls.append((metadata_path, bundle_path))
        return results[symbol]

    monkeypatch.setattr(module, "run_manual_local_json_bundle_preflight", fake_preflight)
    monkeypatch.setattr(
        module,
        "is_manual_local_json_bundle_preflight_success",
        lambda result: True,
    )
    provider = LocalRvolArtifactProvider(manifest(artifact("ABC"), artifact("XYZ")))

    mapping = provider.get_relative_volumes([" xyz ", "abc"])

    assert mapping == {"XYZ": 3.5, "ABC": 2.0}
    assert calls == [
        (Path("XYZ.metadata.json"), Path("XYZ.bundle.json")),
        (Path("ABC.metadata.json"), Path("ABC.bundle.json")),
    ]
    assert [result.symbol for result in provider.latest_results] == ["XYZ", "ABC"]


def test_returned_preflight_failure_and_missing_rvol(monkeypatch) -> None:
    provider = LocalRvolArtifactProvider(manifest(artifact("ABC")))
    monkeypatch.setattr(
        module,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: preflight(2.0),
    )
    monkeypatch.setattr(
        module,
        "is_manual_local_json_bundle_preflight_success",
        lambda _result: False,
    )

    with pytest.raises(LocalRvolArtifactProviderError) as exc_info:
        provider.get_relative_volumes(["ABC"])
    assert str(exc_info.value) == "ARTIFACT_PREFLIGHT_FAILED:ABC"
    assert len(provider.latest_results) == 1

    provider = LocalRvolArtifactProvider(manifest(artifact("ABC")))
    monkeypatch.setattr(
        module,
        "is_manual_local_json_bundle_preflight_success",
        lambda _result: True,
    )
    monkeypatch.setattr(
        module,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: preflight(None),
    )
    with pytest.raises(LocalRvolArtifactProviderError) as missing_exc:
        provider.get_relative_volumes(["ABC"])
    assert str(missing_exc.value) == "MISSING_RVOL:ABC"


def test_underlying_errors_propagate_and_fresh_preflights(monkeypatch) -> None:
    provider = LocalRvolArtifactProvider(manifest(artifact("ABC")))
    error = FileNotFoundError("missing")
    monkeypatch.setattr(
        module,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: (_ for _ in ()).throw(error),
    )

    with pytest.raises(FileNotFoundError) as exc_info:
        provider.get_relative_volumes(["ABC"])
    assert exc_info.value is error

    calls = []
    monkeypatch.setattr(
        module,
        "run_manual_local_json_bundle_preflight",
        lambda *_args: calls.append("call") or preflight(2.0),
    )
    monkeypatch.setattr(
        module,
        "is_manual_local_json_bundle_preflight_success",
        lambda _result: True,
    )
    assert provider.get_relative_volumes(["ABC"]) == {"ABC": 2.0}
    assert provider.get_relative_volumes(["ABC"]) == {"ABC": 2.0}
    assert calls == ["call", "call"]


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
        "market_sentry.data.local_rvol_artifact_manifest",
        "market_sentry.data.relative_volume",
        "market_sentry.local_json_bundle_preflight_cli",
    }

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("run_manual_local_json_bundle_preflight") == 1
    forbidden_calls = {
        "main",
        "parse_args",
        "render_manual_local_json_bundle_preflight_report",
        "write_text",
        "read_text",
        "send",
        "fetch_bars",
        "capture_explicit_alpaca_rvol_bundle",
        "write_local_historical_rvol_bundle",
        "write_local_historical_session_metadata",
    }
    assert not forbidden_calls & set(call_names)
