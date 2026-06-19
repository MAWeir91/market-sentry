import ast
from dataclasses import FrozenInstanceError
import inspect
from pathlib import Path

import pytest

from market_sentry import (
    local_json_bundle_preflight_report_contract_scenario_harness as harness,
)
from market_sentry.local_json_bundle_preflight_report_contract_scenario_catalog import (
    REPORT_ARTIFACT_ABSENT,
    REPORT_ARTIFACT_EQUALS_TERMINAL,
    TERMINAL_BUNDLE_PREFLIGHT_REPORT,
    TERMINAL_COMMAND_ERROR,
    TERMINAL_EXPORT_ERROR,
    TERMINAL_INPUT_ERROR,
    LocalJsonBundlePreflightReportContractScenario,
    get_local_json_bundle_preflight_report_contract_scenario,
    get_local_json_bundle_preflight_report_contract_scenarios,
)
from market_sentry.local_json_bundle_preflight_report_contract_scenario_harness import (
    run_local_json_bundle_preflight_report_contract_scenario,
)


def make_scenario(
    *,
    name="unit",
    metadata_fixture_bytes=b"metadata",
    metadata_relative_path="metadata.json",
    bundle_fixture_bytes=b"bundle",
    bundle_relative_path="historical-rvol-bundle.json",
    report_relative_path="report.txt",
    report_uses_metadata_path=False,
    report_uses_bundle_path=False,
) -> LocalJsonBundlePreflightReportContractScenario:
    return LocalJsonBundlePreflightReportContractScenario(
        name=name,
        metadata_fixture_name=(
            "metadata" if metadata_fixture_bytes is not None else None
        ),
        metadata_fixture_bytes=metadata_fixture_bytes,
        metadata_relative_path=metadata_relative_path,
        bundle_fixture_name="bundle" if bundle_fixture_bytes is not None else None,
        bundle_fixture_bytes=bundle_fixture_bytes,
        bundle_relative_path=bundle_relative_path,
        report_relative_path=report_relative_path,
        report_uses_metadata_path=report_uses_metadata_path,
        report_uses_bundle_path=report_uses_bundle_path,
        expected_exit_code=0,
        expected_terminal_kind=TERMINAL_BUNDLE_PREFLIGHT_REPORT,
        expected_report_artifact=REPORT_ARTIFACT_EQUALS_TERMINAL,
        expect_input_bytes_unchanged=False,
        required_terminal_lines=(),
        forbidden_terminal_lines=(),
    )


def terminal_newline() -> str:
    return "\r\n" if Path("C:/").drive else "\n"


def test_harness_writes_fixtures_builds_ordered_argv_and_captures_stdout(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []
    scenario = make_scenario()

    def fake_main(argv):
        calls.append(tuple(argv))
        print("captured")
        return 7

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    metadata_path = tmp_path / "metadata.json"
    bundle_path = tmp_path / "historical-rvol-bundle.json"
    report_path = tmp_path / "report.txt"
    assert calls == [
        (
            "--local-json-bundle-preflight",
            str(metadata_path),
            str(bundle_path),
            "--local-json-bundle-preflight-report",
            str(report_path),
        )
    ]
    assert metadata_path.read_bytes() == b"metadata"
    assert bundle_path.read_bytes() == b"bundle"
    assert run.scenario is scenario
    assert run.workspace is tmp_path
    assert run.metadata_path == metadata_path
    assert run.bundle_path == bundle_path
    assert run.report_path == report_path
    assert run.initial_metadata_bytes == b"metadata"
    assert run.final_metadata_bytes == b"metadata"
    assert run.initial_bundle_bytes == b"bundle"
    assert run.final_bundle_bytes == b"bundle"
    assert run.exit_code == 7
    assert run.stdout == f"captured{terminal_newline()}"
    assert run.report_exists is False
    assert run.report_bytes is None


def test_harness_distinct_report_bytes_are_observed(monkeypatch, tmp_path) -> None:
    scenario = make_scenario()

    def fake_main(argv):
        Path(argv[4]).write_bytes(b"terminal report")
        print("terminal report")
        return 0

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert run.stdout == f"terminal report{terminal_newline()}"
    assert run.report_exists is True
    assert run.report_bytes == b"terminal report"


def test_metadata_collision_uses_same_direct_path_and_does_not_read_report(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []
    scenario = make_scenario(
        report_relative_path=None,
        report_uses_metadata_path=True,
    )

    def fake_main(argv):
        calls.append(tuple(argv))
        return 2

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    metadata_path = tmp_path / "metadata.json"
    bundle_path = tmp_path / "historical-rvol-bundle.json"
    assert calls == [
        (
            "--local-json-bundle-preflight",
            str(metadata_path),
            str(bundle_path),
            "--local-json-bundle-preflight-report",
            str(metadata_path),
        )
    ]
    assert run.metadata_path == metadata_path
    assert run.report_path == metadata_path
    assert metadata_path.exists()
    assert run.report_exists is False
    assert run.report_bytes is None
    assert run.final_metadata_bytes == b"metadata"
    assert run.final_bundle_bytes == b"bundle"


def test_bundle_collision_uses_same_direct_path_and_does_not_read_report(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []
    scenario = make_scenario(
        report_relative_path=None,
        report_uses_bundle_path=True,
    )

    def fake_main(argv):
        calls.append(tuple(argv))
        return 2

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    metadata_path = tmp_path / "metadata.json"
    bundle_path = tmp_path / "historical-rvol-bundle.json"
    assert calls == [
        (
            "--local-json-bundle-preflight",
            str(metadata_path),
            str(bundle_path),
            "--local-json-bundle-preflight-report",
            str(bundle_path),
        )
    ]
    assert run.bundle_path == bundle_path
    assert run.report_path == bundle_path
    assert bundle_path.exists()
    assert run.report_exists is False
    assert run.report_bytes is None
    assert run.final_metadata_bytes == b"metadata"
    assert run.final_bundle_bytes == b"bundle"


def test_dependency_scenario_writes_no_metadata_or_bundle_fixture(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []
    scenario = make_scenario(
        metadata_fixture_bytes=None,
        metadata_relative_path=None,
        bundle_fixture_bytes=None,
        bundle_relative_path=None,
        report_relative_path="report.txt",
    )

    def fake_main(argv):
        calls.append(tuple(argv))
        return 2

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert calls == [
        ("--local-json-bundle-preflight-report", str(tmp_path / "report.txt"))
    ]
    assert run.metadata_path is None
    assert run.bundle_path is None
    assert run.initial_metadata_bytes is None
    assert run.initial_bundle_bytes is None
    assert run.final_metadata_bytes is None
    assert run.final_bundle_bytes is None
    assert not (tmp_path / "metadata.json").exists()
    assert not (tmp_path / "historical-rvol-bundle.json").exists()
    assert run.report_exists is False


def test_harness_does_not_create_report_parent(monkeypatch, tmp_path) -> None:
    scenario = make_scenario(report_relative_path="missing-parent/report.txt")

    def fake_main(_argv):
        return 1

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert not (tmp_path / "missing-parent").exists()
    assert run.report_path == tmp_path / "missing-parent/report.txt"
    assert run.report_exists is False
    assert run.report_bytes is None


def test_harness_returns_fresh_frozen_artifacts(monkeypatch, tmp_path) -> None:
    scenario = make_scenario()

    def fake_main(_argv):
        return 0

    monkeypatch.setattr(harness, "main", fake_main)

    first = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )
    second = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert first is not second
    assert first.scenario is scenario
    assert second.scenario is scenario
    with pytest.raises(FrozenInstanceError):
        first.exit_code = 99  # type: ignore[misc]


def test_harness_main_exception_propagates_unchanged(monkeypatch, tmp_path) -> None:
    scenario = make_scenario()
    error = RuntimeError("boom")

    def fake_main(_argv):
        raise error

    monkeypatch.setattr(harness, "main", fake_main)

    with pytest.raises(RuntimeError) as exc_info:
        run_local_json_bundle_preflight_report_contract_scenario(
            scenario,
            tmp_path,
        )

    assert exc_info.value is error


def assert_contract(run) -> None:
    scenario = run.scenario
    assert run.exit_code == scenario.expected_exit_code
    for required in scenario.required_terminal_lines:
        assert required in run.stdout
    for forbidden in scenario.forbidden_terminal_lines:
        assert forbidden not in run.stdout

    if scenario.expected_report_artifact == REPORT_ARTIFACT_EQUALS_TERMINAL:
        assert run.report_bytes is not None
        assert run.stdout == run.report_bytes.decode("utf-8") + terminal_newline()
        assert run.report_exists is True
    elif scenario.expected_report_artifact == REPORT_ARTIFACT_ABSENT:
        assert run.report_exists is False
        assert run.report_bytes is None

    if scenario.expect_input_bytes_unchanged:
        assert run.initial_metadata_bytes is not None
        assert run.final_metadata_bytes == run.initial_metadata_bytes
        assert run.initial_bundle_bytes is not None
        assert run.final_bundle_bytes == run.initial_bundle_bytes


def assert_dynamic_paths(run) -> None:
    if run.scenario.expected_terminal_kind in {
        TERMINAL_BUNDLE_PREFLIGHT_REPORT,
        TERMINAL_INPUT_ERROR,
    }:
        assert f"Metadata Path: {run.metadata_path}" in run.stdout
        assert f"Bundle Path: {run.bundle_path}" in run.stdout
    elif run.scenario.expected_terminal_kind == TERMINAL_EXPORT_ERROR:
        assert f"Metadata Path: {run.metadata_path}" in run.stdout
        assert f"Bundle Path: {run.bundle_path}" in run.stdout
        assert f"Report Path: {run.report_path}" in run.stdout
    elif run.scenario.name == "bundle_report_dependency_error":
        assert "Metadata Path: N/A" in run.stdout
        assert "Bundle Path: N/A" in run.stdout
        assert f"Report Path: {run.report_path}" in run.stdout
    else:
        assert f"Metadata Path: {run.metadata_path}" in run.stdout
        assert f"Bundle Path: {run.bundle_path}" in run.stdout
        assert f"Report Path: {run.report_path}" in run.stdout


def test_all_bundle_report_contract_scenarios_run_through_real_main(
    tmp_path,
) -> None:
    for scenario in get_local_json_bundle_preflight_report_contract_scenarios():
        workspace = tmp_path / scenario.name
        workspace.mkdir()

        run = run_local_json_bundle_preflight_report_contract_scenario(
            scenario,
            workspace,
        )

        assert_contract(run)
        assert_dynamic_paths(run)


def test_valid_bundle_export_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_bundle_preflight_report_contract_scenario(
        "valid_bundle_export_success"
    )
    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert run.exit_code == 0
    assert run.report_exists is True
    assert run.report_bytes.decode("utf-8") + terminal_newline() == run.stdout
    assert "Relative Volume: 2.0x" in run.stdout


def test_returned_workflow_failure_export_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_bundle_preflight_report_contract_scenario(
        "returned_workflow_failure_export"
    )
    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert run.exit_code == 1
    assert run.report_exists is True
    assert run.report_bytes.decode("utf-8") + terminal_newline() == run.stdout
    assert "Manifest: NO_VALID_METADATA" in run.stdout
    assert "Relative Volume: N/A" in run.stdout


def test_metadata_source_error_export_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_bundle_preflight_report_contract_scenario(
        "metadata_source_error_export"
    )
    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert run.exit_code == 1
    assert run.report_exists is True
    assert run.report_bytes.decode("utf-8") + terminal_newline() == run.stdout
    assert "Result: ERROR" in run.stdout
    assert "JsonHistoricalSessionMetadataFileSourceError" in run.stdout
    assert "UNSUPPORTED_SCHEMA_VERSION" in run.stdout


def test_bundle_input_error_export_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_bundle_preflight_report_contract_scenario(
        "bundle_input_error_export"
    )
    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert run.exit_code == 1
    assert run.report_exists is True
    assert run.report_bytes.decode("utf-8") + terminal_newline() == run.stdout
    assert "Result: ERROR" in run.stdout
    assert "JsonHistoricalRvolBundleError" in run.stdout
    assert "UNSUPPORTED_SCHEMA_VERSION" in run.stdout


def test_export_error_missing_parent_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_bundle_preflight_report_contract_scenario(
        "export_error_missing_parent"
    )
    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert run.exit_code == 1
    assert not (tmp_path / "missing-parent").exists()
    assert run.report_exists is False
    assert run.report_bytes is None
    assert "Result: EXPORT_ERROR" in run.stdout
    assert "Input Mode: EXPLICIT_LOCAL_BUNDLE" not in run.stdout
    assert "Relative Volume: 2.0x" not in run.stdout
    assert run.final_metadata_bytes == run.initial_metadata_bytes
    assert run.final_bundle_bytes == run.initial_bundle_bytes


def test_bundle_report_dependency_error_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_bundle_preflight_report_contract_scenario(
        "bundle_report_dependency_error"
    )
    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert run.exit_code == 2
    assert run.metadata_path is None
    assert run.bundle_path is None
    assert run.report_exists is False
    assert not (tmp_path / "metadata.json").exists()
    assert not (tmp_path / "historical-rvol-bundle.json").exists()
    assert "--local-json-bundle-preflight-report requires" in run.stdout


def test_report_same_metadata_path_command_error_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_bundle_preflight_report_contract_scenario(
        "report_same_metadata_path_command_error"
    )
    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert run.exit_code == 2
    assert run.report_path == run.metadata_path
    assert run.metadata_path.exists()
    assert run.report_exists is False
    assert run.report_bytes is None
    assert run.final_metadata_bytes == run.initial_metadata_bytes
    assert run.final_bundle_bytes == run.initial_bundle_bytes
    assert "Input Mode: EXPLICIT_LOCAL_BUNDLE" not in run.stdout
    assert "Relative Volume:" not in run.stdout
    assert "must differ from metadata path" in run.stdout


def test_report_same_bundle_path_command_error_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_bundle_preflight_report_contract_scenario(
        "report_same_bundle_path_command_error"
    )
    run = run_local_json_bundle_preflight_report_contract_scenario(
        scenario,
        tmp_path,
    )

    assert run.exit_code == 2
    assert run.report_path == run.bundle_path
    assert run.bundle_path.exists()
    assert run.report_exists is False
    assert run.report_bytes is None
    assert run.final_metadata_bytes == run.initial_metadata_bytes
    assert run.final_bundle_bytes == run.initial_bundle_bytes
    assert "Input Mode: EXPLICIT_LOCAL_BUNDLE" not in run.stdout
    assert "Relative Volume:" not in run.stdout
    assert "must differ from bundle path" in run.stdout


def test_harness_source_boundary() -> None:
    source = inspect.getsource(harness)
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
        "contextlib",
        "dataclasses",
        "io",
        "pathlib",
        "market_sentry.local_json_bundle_preflight_report_contract_scenario_catalog",
        "market_sentry.main",
    }

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert imported_names == {
        "dataclass",
        "LocalJsonBundlePreflightReportContractScenario",
        "main",
    }

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert call_names.count("main") == 1
    forbidden_calls = {
        "run_manual_local_json_bundle_preflight",
        "render_manual_local_json_bundle_preflight_report",
        "write_manual_local_json_bundle_preflight_report",
        "load_local_historical_rvol_bundle",
        "loads",
        "mkdir",
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
    }
    assert not forbidden_calls & set(call_names)

    forbidden_terms = [
        "local_json_bundle_preflight_cli",
        "local_json_bundle_preflight_report_export",
        "json_historical_rvol_bundle",
        "local_json_metadata_workflow_preflight",
        "workflow",
        "provider",
        "factory",
        "config",
        "readiness",
        "scanner",
        "alerts",
        "voice",
        "http",
        "transport",
        "expected_exit_code",
        "expected_terminal_kind",
        "expected_report_artifact",
        "required_terminal_lines",
        "forbidden_terminal_lines",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
