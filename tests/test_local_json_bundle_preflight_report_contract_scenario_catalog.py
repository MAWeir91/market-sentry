import ast
from dataclasses import FrozenInstanceError
import inspect
import json

import pytest

from market_sentry import (
    local_json_bundle_preflight_report_contract_scenario_catalog as catalog,
)
from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    get_local_json_metadata_preflight_scenario,
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


SCENARIO_NAMES = (
    "valid_bundle_export_success",
    "returned_workflow_failure_export",
    "metadata_source_error_export",
    "bundle_input_error_export",
    "export_error_missing_parent",
    "bundle_report_dependency_error",
    "report_same_metadata_path_command_error",
    "report_same_bundle_path_command_error",
)


def by_name():
    return {
        scenario.name: scenario
        for scenario in get_local_json_bundle_preflight_report_contract_scenarios()
    }


def test_exact_scenario_names_and_order() -> None:
    assert tuple(
        scenario.name
        for scenario in get_local_json_bundle_preflight_report_contract_scenarios()
    ) == SCENARIO_NAMES


def test_exact_name_lookup_and_key_errors() -> None:
    scenario = get_local_json_bundle_preflight_report_contract_scenario(
        "valid_bundle_export_success"
    )

    assert scenario.name == "valid_bundle_export_success"
    with pytest.raises(KeyError) as unknown:
        get_local_json_bundle_preflight_report_contract_scenario("unknown")
    assert unknown.value.args == ("unknown",)
    with pytest.raises(KeyError) as case_changed:
        get_local_json_bundle_preflight_report_contract_scenario(
            "VALID_BUNDLE_EXPORT_SUCCESS"
        )
    assert case_changed.value.args == ("VALID_BUNDLE_EXPORT_SUCCESS",)


def test_scenario_model_is_frozen() -> None:
    scenario = get_local_json_bundle_preflight_report_contract_scenario(
        "valid_bundle_export_success"
    )

    with pytest.raises(FrozenInstanceError):
        scenario.name = "changed"  # type: ignore[misc]


def test_catalog_returns_fresh_scenario_objects() -> None:
    first = get_local_json_bundle_preflight_report_contract_scenario(
        "valid_bundle_export_success"
    )
    second = get_local_json_bundle_preflight_report_contract_scenario(
        "valid_bundle_export_success"
    )

    assert first is not second
    assert first == second
    assert first.metadata_fixture_bytes == second.metadata_fixture_bytes
    assert first.bundle_fixture_bytes == second.bundle_fixture_bytes


def test_metadata_fixture_bytes_match_phase_15i_sources() -> None:
    scenarios = by_name()
    expected_sources = {
        "valid_bundle_export_success": "valid_json_complete_multi_page",
        "returned_workflow_failure_export": "empty_records_json",
        "metadata_source_error_export": "unsupported_schema_json_error",
        "bundle_input_error_export": "valid_json_complete_multi_page",
        "export_error_missing_parent": "valid_json_complete_multi_page",
        "report_same_metadata_path_command_error": (
            "valid_json_complete_multi_page"
        ),
        "report_same_bundle_path_command_error": "valid_json_complete_multi_page",
    }

    for scenario_name, fixture_name in expected_sources.items():
        phase_15i = get_local_json_metadata_preflight_scenario(fixture_name)
        assert scenarios[scenario_name].metadata_fixture_name == fixture_name
        assert scenarios[scenario_name].metadata_fixture_bytes == (
            phase_15i.fixture_bytes
        )

    dependency = scenarios["bundle_report_dependency_error"]
    assert dependency.metadata_fixture_name is None
    assert dependency.metadata_fixture_bytes is None


def test_bundle_fixture_bytes_are_fresh_static_json_compatible_bytes() -> None:
    first = by_name()
    second = by_name()

    valid = json.loads(
        first["valid_bundle_export_success"].bundle_fixture_bytes.decode("utf-8")
    )
    assert valid["schema_version"] == 1
    assert valid["collection"]["request"]["symbols"] == ["RVOL"]
    assert valid["collection"]["request"]["initial_query"]["page_token"] is None
    assert valid["collection"]["collected_pages"][0]["query"]["page_token"] == "p0"
    assert valid["collection"]["collected_pages"][1]["query"]["page_token"] == "p1"
    assert valid["collection"]["page_collection_complete"] is True
    assert valid["current_series"]["bars"][0]["volume"] == 200
    first_page_bars = valid["collection"]["collected_pages"][0]["page"][
        "bars_by_symbol"
    ]["RVOL"]
    assert first_page_bars[0]["t"] == "2026-01-02T09:31:00Z"
    assert first_page_bars[0]["v"] == 25
    assert first_page_bars[1]["t"] == "2026-01-02T09:35:00Z"
    assert first_page_bars[1]["v"] == 75

    unsupported = json.loads(
        first["bundle_input_error_export"].bundle_fixture_bytes.decode("utf-8")
    )
    assert unsupported == {"schema_version": 2}
    assert (
        first["valid_bundle_export_success"].bundle_fixture_bytes
        == second["valid_bundle_export_success"].bundle_fixture_bytes
    )
    assert (
        first["bundle_input_error_export"].bundle_fixture_bytes
        == second["bundle_input_error_export"].bundle_fixture_bytes
    )


def test_expected_contract_fields() -> None:
    scenarios = by_name()

    assert (
        scenarios["valid_bundle_export_success"].metadata_relative_path,
        scenarios["valid_bundle_export_success"].bundle_relative_path,
        scenarios["valid_bundle_export_success"].report_relative_path,
        scenarios["valid_bundle_export_success"].expected_exit_code,
        scenarios["valid_bundle_export_success"].expected_terminal_kind,
        scenarios["valid_bundle_export_success"].expected_report_artifact,
    ) == (
        "metadata.json",
        "historical-rvol-bundle.json",
        "report.txt",
        0,
        TERMINAL_BUNDLE_PREFLIGHT_REPORT,
        REPORT_ARTIFACT_EQUALS_TERMINAL,
    )
    assert "Relative Volume: 2.0x" in (
        scenarios["valid_bundle_export_success"].required_terminal_lines
    )

    assert (
        scenarios["returned_workflow_failure_export"].metadata_fixture_name,
        scenarios["returned_workflow_failure_export"].expected_exit_code,
        scenarios["returned_workflow_failure_export"].expected_terminal_kind,
        scenarios["returned_workflow_failure_export"].expected_report_artifact,
    ) == (
        "empty_records_json",
        1,
        TERMINAL_BUNDLE_PREFLIGHT_REPORT,
        REPORT_ARTIFACT_EQUALS_TERMINAL,
    )
    assert "Manifest: NO_VALID_METADATA" in (
        scenarios["returned_workflow_failure_export"].required_terminal_lines
    )

    assert (
        scenarios["metadata_source_error_export"].metadata_fixture_name,
        scenarios["metadata_source_error_export"].expected_exit_code,
        scenarios["metadata_source_error_export"].expected_terminal_kind,
    ) == ("unsupported_schema_json_error", 1, TERMINAL_INPUT_ERROR)

    assert (
        scenarios["bundle_input_error_export"].bundle_fixture_name,
        scenarios["bundle_input_error_export"].expected_exit_code,
        scenarios["bundle_input_error_export"].expected_terminal_kind,
    ) == ("unsupported_schema_bundle", 1, TERMINAL_INPUT_ERROR)

    assert (
        scenarios["export_error_missing_parent"].report_relative_path,
        scenarios["export_error_missing_parent"].expected_exit_code,
        scenarios["export_error_missing_parent"].expected_terminal_kind,
        scenarios["export_error_missing_parent"].expected_report_artifact,
        scenarios["export_error_missing_parent"].expect_input_bytes_unchanged,
    ) == (
        "missing-parent/report.txt",
        1,
        TERMINAL_EXPORT_ERROR,
        REPORT_ARTIFACT_ABSENT,
        True,
    )

    assert (
        scenarios["bundle_report_dependency_error"].metadata_relative_path,
        scenarios["bundle_report_dependency_error"].bundle_relative_path,
        scenarios["bundle_report_dependency_error"].report_relative_path,
        scenarios["bundle_report_dependency_error"].expected_exit_code,
        scenarios["bundle_report_dependency_error"].expected_terminal_kind,
    ) == (None, None, "report.txt", 2, TERMINAL_COMMAND_ERROR)

    assert (
        scenarios["report_same_metadata_path_command_error"].report_relative_path,
        scenarios["report_same_metadata_path_command_error"].report_uses_metadata_path,
        scenarios["report_same_metadata_path_command_error"].report_uses_bundle_path,
        scenarios["report_same_metadata_path_command_error"].expected_exit_code,
        scenarios["report_same_metadata_path_command_error"].expected_terminal_kind,
        scenarios["report_same_metadata_path_command_error"].expected_report_artifact,
        scenarios[
            "report_same_metadata_path_command_error"
        ].expect_input_bytes_unchanged,
    ) == (None, True, False, 2, TERMINAL_COMMAND_ERROR, REPORT_ARTIFACT_ABSENT, True)

    assert (
        scenarios["report_same_bundle_path_command_error"].report_relative_path,
        scenarios["report_same_bundle_path_command_error"].report_uses_metadata_path,
        scenarios["report_same_bundle_path_command_error"].report_uses_bundle_path,
        scenarios["report_same_bundle_path_command_error"].expected_exit_code,
        scenarios["report_same_bundle_path_command_error"].expected_terminal_kind,
        scenarios["report_same_bundle_path_command_error"].expected_report_artifact,
        scenarios["report_same_bundle_path_command_error"].expect_input_bytes_unchanged,
    ) == (None, False, True, 2, TERMINAL_COMMAND_ERROR, REPORT_ARTIFACT_ABSENT, True)


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
        "json",
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
    assert "dumps" in call_names
    forbidden_calls = {
        "main",
        "load_local_historical_rvol_bundle",
        "run_manual_local_json_bundle_preflight",
        "render_manual_local_json_bundle_preflight_report",
        "write_manual_local_json_bundle_preflight_report",
        "run_local_json_metadata_workflow_preflight",
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
        "local_json_bundle_preflight_cli",
        "local_json_bundle_preflight_report_export",
        "local_json_bundle_preflight_report_contract_scenario_harness",
        "json_historical_rvol_bundle",
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
        "tests",
    ]
    for module_name in imported_modules:
        for forbidden in forbidden_modules:
            assert forbidden not in module_name.lower()


def test_catalog_model_can_be_constructed_without_command_execution() -> None:
    scenario = LocalJsonBundlePreflightReportContractScenario(
        name="unit",
        metadata_fixture_name=None,
        metadata_fixture_bytes=None,
        metadata_relative_path=None,
        bundle_fixture_name=None,
        bundle_fixture_bytes=None,
        bundle_relative_path=None,
        report_relative_path="report.txt",
        report_uses_metadata_path=False,
        report_uses_bundle_path=False,
        expected_exit_code=2,
        expected_terminal_kind=TERMINAL_COMMAND_ERROR,
        expected_report_artifact=REPORT_ARTIFACT_ABSENT,
        expect_input_bytes_unchanged=False,
        required_terminal_lines=("required",),
        forbidden_terminal_lines=("forbidden",),
    )

    assert scenario.name == "unit"
