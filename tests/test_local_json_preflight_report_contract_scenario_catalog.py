import ast
from dataclasses import FrozenInstanceError
import inspect

import pytest

from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    get_local_json_metadata_preflight_scenario,
)
from market_sentry import (
    local_json_preflight_report_contract_scenario_catalog as catalog,
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


SCENARIO_NAMES = (
    "valid_export_success",
    "returned_failure_export",
    "source_error_export",
    "export_error_missing_parent",
    "report_dependency_error",
    "same_path_command_error",
)


def by_name():
    return {
        scenario.name: scenario
        for scenario in get_local_json_preflight_report_contract_scenarios()
    }


def test_exact_scenario_names_and_order() -> None:
    assert tuple(
        scenario.name
        for scenario in get_local_json_preflight_report_contract_scenarios()
    ) == SCENARIO_NAMES


def test_exact_name_lookup_and_key_errors() -> None:
    scenario = get_local_json_preflight_report_contract_scenario(
        "valid_export_success"
    )

    assert scenario.name == "valid_export_success"
    with pytest.raises(KeyError) as unknown:
        get_local_json_preflight_report_contract_scenario("unknown")
    assert unknown.value.args == ("unknown",)
    with pytest.raises(KeyError) as case_changed:
        get_local_json_preflight_report_contract_scenario("VALID_EXPORT_SUCCESS")
    assert case_changed.value.args == ("VALID_EXPORT_SUCCESS",)


def test_scenario_model_is_frozen() -> None:
    scenario = get_local_json_preflight_report_contract_scenario(
        "valid_export_success"
    )

    with pytest.raises(FrozenInstanceError):
        scenario.name = "changed"  # type: ignore[misc]


def test_catalog_returns_fresh_scenario_objects() -> None:
    first = get_local_json_preflight_report_contract_scenario(
        "valid_export_success"
    )
    second = get_local_json_preflight_report_contract_scenario(
        "valid_export_success"
    )

    assert first is not second
    assert first == second
    assert first.input_fixture_bytes == second.input_fixture_bytes


def test_fixture_bytes_match_phase_15i_sources() -> None:
    scenarios = by_name()
    expected_sources = {
        "valid_export_success": "valid_json_complete_multi_page",
        "returned_failure_export": "empty_records_json",
        "source_error_export": "unsupported_schema_json_error",
        "export_error_missing_parent": "valid_json_complete_multi_page",
        "same_path_command_error": "valid_json_complete_multi_page",
    }

    for scenario_name, fixture_name in expected_sources.items():
        phase_15i = get_local_json_metadata_preflight_scenario(fixture_name)
        assert scenarios[scenario_name].input_fixture_name == fixture_name
        assert scenarios[scenario_name].input_fixture_bytes == (
            phase_15i.fixture_bytes
        )

    dependency = scenarios["report_dependency_error"]
    assert dependency.input_fixture_name is None
    assert dependency.input_fixture_bytes is None


def test_expected_contract_fields() -> None:
    scenarios = by_name()

    assert (
        scenarios["valid_export_success"].input_relative_path,
        scenarios["valid_export_success"].report_relative_path,
        scenarios["valid_export_success"].report_uses_input_path,
        scenarios["valid_export_success"].expected_exit_code,
        scenarios["valid_export_success"].expected_terminal_kind,
        scenarios["valid_export_success"].expected_report_artifact,
    ) == (
        "metadata.json",
        "report.txt",
        False,
        0,
        TERMINAL_PREFLIGHT_REPORT,
        REPORT_ARTIFACT_EQUALS_TERMINAL,
    )
    assert "Relative Volume: 2.0x" in (
        scenarios["valid_export_success"].required_terminal_lines
    )

    assert (
        scenarios["returned_failure_export"].input_fixture_name,
        scenarios["returned_failure_export"].expected_exit_code,
        scenarios["returned_failure_export"].expected_terminal_kind,
        scenarios["returned_failure_export"].expected_report_artifact,
    ) == (
        "empty_records_json",
        1,
        TERMINAL_PREFLIGHT_REPORT,
        REPORT_ARTIFACT_EQUALS_TERMINAL,
    )
    assert "Manifest: NO_VALID_METADATA" in (
        scenarios["returned_failure_export"].required_terminal_lines
    )

    assert (
        scenarios["source_error_export"].expected_exit_code,
        scenarios["source_error_export"].expected_terminal_kind,
        scenarios["source_error_export"].expected_report_artifact,
    ) == (1, TERMINAL_SOURCE_ERROR, REPORT_ARTIFACT_EQUALS_TERMINAL)

    assert (
        scenarios["export_error_missing_parent"].report_relative_path,
        scenarios["export_error_missing_parent"].expected_exit_code,
        scenarios["export_error_missing_parent"].expected_terminal_kind,
        scenarios["export_error_missing_parent"].expected_report_artifact,
    ) == (
        "missing-parent/report.txt",
        1,
        TERMINAL_EXPORT_ERROR,
        REPORT_ARTIFACT_ABSENT,
    )

    assert (
        scenarios["report_dependency_error"].input_relative_path,
        scenarios["report_dependency_error"].report_relative_path,
        scenarios["report_dependency_error"].expected_exit_code,
        scenarios["report_dependency_error"].expected_terminal_kind,
        scenarios["report_dependency_error"].expected_report_artifact,
    ) == (
        None,
        "report.txt",
        2,
        TERMINAL_COMMAND_ERROR,
        REPORT_ARTIFACT_ABSENT,
    )

    assert (
        scenarios["same_path_command_error"].report_relative_path,
        scenarios["same_path_command_error"].report_uses_input_path,
        scenarios["same_path_command_error"].expected_exit_code,
        scenarios["same_path_command_error"].expected_terminal_kind,
        scenarios["same_path_command_error"].expected_report_artifact,
    ) == (
        None,
        True,
        2,
        TERMINAL_COMMAND_ERROR,
        REPORT_ARTIFACT_INPUT_UNCHANGED,
    )


def test_catalog_source_boundary() -> None:
    source = inspect.getsource(catalog)
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
        "market_sentry.data.local_json_metadata_preflight_scenario_catalog",
    }

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert imported_names == {
        "dataclass",
        "get_local_json_metadata_preflight_scenario",
    }

    call_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)

    assert "get_local_json_metadata_preflight_scenario" in call_names
    forbidden_calls = {
        "main",
        "run_manual_local_json_preflight",
        "render_manual_local_json_preflight_report",
        "write_manual_local_json_preflight_report",
        "loads",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "mkdir",
    }
    assert not forbidden_calls & call_names

    forbidden_modules = [
        "main",
        "local_json_preflight_cli",
        "local_json_preflight_report_export",
        "local_json_preflight_report_contract_scenario_harness",
        "provider",
        "factory",
        "config",
        "readiness",
        "scanner",
        "alerts",
        "voice",
        "http",
        "transport",
        "workflow",
    ]
    for module_name in imported_modules:
        for forbidden in forbidden_modules:
            assert forbidden not in module_name.lower()


def test_catalog_model_can_be_constructed_without_execution() -> None:
    scenario = LocalJsonPreflightReportContractScenario(
        name="unit",
        input_fixture_name=None,
        input_fixture_bytes=None,
        input_relative_path=None,
        report_relative_path="report.txt",
        report_uses_input_path=False,
        expected_exit_code=2,
        expected_terminal_kind=TERMINAL_COMMAND_ERROR,
        expected_report_artifact=REPORT_ARTIFACT_ABSENT,
        required_terminal_lines=("required",),
        forbidden_terminal_lines=("forbidden",),
    )

    assert scenario.name == "unit"
