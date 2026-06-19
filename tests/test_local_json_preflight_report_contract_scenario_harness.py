import ast
from dataclasses import FrozenInstanceError
import inspect
from pathlib import Path

import pytest

from market_sentry import (
    local_json_preflight_report_contract_scenario_harness as harness,
)
from market_sentry.local_json_preflight_report_contract_scenario_catalog import (
    REPORT_ARTIFACT_ABSENT,
    REPORT_ARTIFACT_EQUALS_TERMINAL,
    REPORT_ARTIFACT_INPUT_UNCHANGED,
    TERMINAL_COMMAND_ERROR,
    TERMINAL_EXPORT_ERROR,
    TERMINAL_PREFLIGHT_REPORT,
    TERMINAL_SOURCE_ERROR,
    LocalJsonPreflightReportContractScenario,
    get_local_json_preflight_report_contract_scenario,
    get_local_json_preflight_report_contract_scenarios,
)
from market_sentry.local_json_preflight_report_contract_scenario_harness import (
    run_local_json_preflight_report_contract_scenario,
)


def make_scenario(
    *,
    name="unit",
    input_fixture_bytes=b"fixture",
    input_relative_path="metadata.json",
    report_relative_path="report.txt",
    report_uses_input_path=False,
) -> LocalJsonPreflightReportContractScenario:
    return LocalJsonPreflightReportContractScenario(
        name=name,
        input_fixture_name="fixture" if input_fixture_bytes is not None else None,
        input_fixture_bytes=input_fixture_bytes,
        input_relative_path=input_relative_path,
        report_relative_path=report_relative_path,
        report_uses_input_path=report_uses_input_path,
        expected_exit_code=0,
        expected_terminal_kind=TERMINAL_PREFLIGHT_REPORT,
        expected_report_artifact=REPORT_ARTIFACT_EQUALS_TERMINAL,
        required_terminal_lines=(),
        forbidden_terminal_lines=(),
    )


def terminal_newline() -> str:
    return "\r\n" if Path("C:/").drive else "\n"


def test_harness_writes_input_builds_ordered_argv_and_captures_stdout(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []
    scenario = make_scenario()

    def fake_main(argv):
        calls.append(tuple(argv))
        return 7

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    input_path = tmp_path / "metadata.json"
    report_path = tmp_path / "report.txt"
    assert calls == [
        (
            "--local-json-preflight",
            str(input_path),
            "--local-json-preflight-report",
            str(report_path),
        )
    ]
    assert input_path.read_bytes() == b"fixture"
    assert run.scenario is scenario
    assert run.workspace is tmp_path
    assert run.input_path == input_path
    assert run.report_path == report_path
    assert run.initial_input_bytes == b"fixture"
    assert run.final_input_bytes == b"fixture"
    assert run.exit_code == 7
    assert run.stdout == ""
    assert run.report_exists is False
    assert run.report_bytes is None


def test_harness_stdout_and_distinct_report_bytes_are_observed(
    monkeypatch,
    tmp_path,
) -> None:
    scenario = make_scenario()

    def fake_main(argv):
        Path(argv[3]).write_bytes(b"terminal report")
        print("terminal report")
        return 0

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    assert run.stdout == f"terminal report{terminal_newline()}"
    assert run.report_exists is True
    assert run.report_bytes == b"terminal report"


def test_harness_same_path_uses_same_direct_path_and_does_not_read_report(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []
    scenario = make_scenario(
        report_relative_path=None,
        report_uses_input_path=True,
    )

    def fake_main(argv):
        calls.append(tuple(argv))
        return 2

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    input_path = tmp_path / "metadata.json"
    assert calls == [
        (
            "--local-json-preflight",
            str(input_path),
            "--local-json-preflight-report",
            str(input_path),
        )
    ]
    assert run.input_path == input_path
    assert run.report_path == input_path
    assert run.report_exists is True
    assert run.report_bytes is None
    assert run.final_input_bytes == b"fixture"


def test_harness_no_input_fixture_writes_nothing(monkeypatch, tmp_path) -> None:
    calls = []
    scenario = make_scenario(
        input_fixture_bytes=None,
        input_relative_path=None,
        report_relative_path="report.txt",
    )

    def fake_main(argv):
        calls.append(tuple(argv))
        return 2

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    assert calls == [("--local-json-preflight-report", str(tmp_path / "report.txt"))]
    assert run.input_path is None
    assert run.initial_input_bytes is None
    assert run.final_input_bytes is None
    assert not (tmp_path / "metadata.json").exists()
    assert run.report_exists is False


def test_harness_does_not_create_report_parent(monkeypatch, tmp_path) -> None:
    scenario = make_scenario(report_relative_path="missing-parent/report.txt")

    def fake_main(_argv):
        return 1

    monkeypatch.setattr(harness, "main", fake_main)

    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    assert not (tmp_path / "missing-parent").exists()
    assert run.report_path == tmp_path / "missing-parent/report.txt"
    assert run.report_exists is False
    assert run.report_bytes is None


def test_harness_returns_fresh_frozen_artifacts(monkeypatch, tmp_path) -> None:
    scenario = make_scenario()

    def fake_main(_argv):
        return 0

    monkeypatch.setattr(harness, "main", fake_main)

    first = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)
    second = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

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
        run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

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
    elif scenario.expected_report_artifact == REPORT_ARTIFACT_INPUT_UNCHANGED:
        assert run.initial_input_bytes is not None
        assert run.final_input_bytes == run.initial_input_bytes
        assert run.report_bytes is None


def test_all_report_contract_scenarios_run_through_real_main(tmp_path) -> None:
    for scenario in get_local_json_preflight_report_contract_scenarios():
        workspace = tmp_path / scenario.name
        workspace.mkdir()

        run = run_local_json_preflight_report_contract_scenario(
            scenario,
            workspace,
        )

        assert_contract(run)
        if run.input_path is not None:
            assert f"Path: {run.input_path}" in run.stdout
        if scenario.expected_terminal_kind in {
            TERMINAL_EXPORT_ERROR,
            TERMINAL_COMMAND_ERROR,
        }:
            assert f"Report Path: {run.report_path}" in run.stdout


def test_valid_export_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_preflight_report_contract_scenario(
        "valid_export_success"
    )
    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    assert run.exit_code == 0
    assert run.report_bytes.decode("utf-8") + terminal_newline() == run.stdout
    assert "Relative Volume: 2.0x" in run.stdout


def test_returned_failure_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_preflight_report_contract_scenario(
        "returned_failure_export"
    )
    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    assert run.exit_code == 1
    assert run.report_bytes.decode("utf-8") + terminal_newline() == run.stdout
    assert "Manifest: NO_VALID_METADATA" in run.stdout
    assert "Relative Volume: N/A" in run.stdout


def test_source_error_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_preflight_report_contract_scenario(
        "source_error_export"
    )
    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    assert run.exit_code == 1
    assert run.report_bytes.decode("utf-8") + terminal_newline() == run.stdout
    assert "Result: ERROR" in run.stdout
    assert "JsonHistoricalSessionMetadataFileSourceError" in run.stdout
    assert "UNSUPPORTED_SCHEMA_VERSION" in run.stdout


def test_export_error_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_preflight_report_contract_scenario(
        "export_error_missing_parent"
    )
    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    assert run.exit_code == 1
    assert not (tmp_path / "missing-parent").exists()
    assert run.report_exists is False
    assert "Result: EXPORT_ERROR" in run.stdout
    assert "Result: ERROR" not in run.stdout
    assert "Result: COMMAND_ERROR" not in run.stdout
    assert "Profile: valid_json_complete_multi_page" not in run.stdout
    assert "Relative Volume: 2.0x" not in run.stdout
    assert run.final_input_bytes == run.initial_input_bytes


def test_dependency_error_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_preflight_report_contract_scenario(
        "report_dependency_error"
    )
    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    assert run.exit_code == 2
    assert run.input_path is None
    assert run.report_exists is False
    assert "Path: N/A" in run.stdout
    assert "--local-json-preflight-report requires --local-json-preflight" in (
        run.stdout
    )


def test_same_path_contract_targeted(tmp_path) -> None:
    scenario = get_local_json_preflight_report_contract_scenario(
        "same_path_command_error"
    )
    run = run_local_json_preflight_report_contract_scenario(scenario, tmp_path)

    assert run.exit_code == 2
    assert run.input_path == run.report_path
    assert run.final_input_bytes == run.initial_input_bytes
    assert "Profile: valid_json_complete_multi_page" not in run.stdout
    assert "Relative Volume:" not in run.stdout
    assert "--local-json-preflight-report must differ from --local-json-preflight" in (
        run.stdout
    )


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
        "market_sentry.local_json_preflight_report_contract_scenario_catalog",
        "market_sentry.main",
    }

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert imported_names == {
        "redirect_stdout",
        "dataclass",
        "StringIO",
        "Path",
        "LocalJsonPreflightReportContractScenario",
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
        "run_manual_local_json_preflight",
        "render_manual_local_json_preflight_report",
        "write_manual_local_json_preflight_report",
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
        "local_json_preflight_cli",
        "local_json_preflight_report_export",
        "local_json_metadata_preflight",
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
