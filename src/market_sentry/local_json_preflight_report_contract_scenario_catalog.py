from dataclasses import dataclass

from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    get_local_json_metadata_preflight_scenario,
)


TERMINAL_PREFLIGHT_REPORT = "TERMINAL_PREFLIGHT_REPORT"
TERMINAL_SOURCE_ERROR = "TERMINAL_SOURCE_ERROR"
TERMINAL_EXPORT_ERROR = "TERMINAL_EXPORT_ERROR"
TERMINAL_COMMAND_ERROR = "TERMINAL_COMMAND_ERROR"

REPORT_ARTIFACT_EQUALS_TERMINAL = "REPORT_ARTIFACT_EQUALS_TERMINAL"
REPORT_ARTIFACT_ABSENT = "REPORT_ARTIFACT_ABSENT"
REPORT_ARTIFACT_INPUT_UNCHANGED = "REPORT_ARTIFACT_INPUT_UNCHANGED"


@dataclass(frozen=True)
class LocalJsonPreflightReportContractScenario:
    """One deterministic end-to-end CLI report/export contract case."""

    name: str
    input_fixture_name: str | None
    input_fixture_bytes: bytes | None
    input_relative_path: str | None
    report_relative_path: str | None
    report_uses_input_path: bool
    expected_exit_code: int
    expected_terminal_kind: str
    expected_report_artifact: str
    required_terminal_lines: tuple[str, ...]
    forbidden_terminal_lines: tuple[str, ...]


def _fixture_bytes(name: str) -> bytes:
    scenario = get_local_json_metadata_preflight_scenario(name)
    if scenario.fixture_bytes is None:
        raise ValueError(name)
    return scenario.fixture_bytes


def get_local_json_preflight_report_contract_scenarios(
) -> tuple[LocalJsonPreflightReportContractScenario, ...]:
    """Return fresh deterministic local JSON report-contract scenarios."""

    return (
        LocalJsonPreflightReportContractScenario(
            name="valid_export_success",
            input_fixture_name="valid_json_complete_multi_page",
            input_fixture_bytes=_fixture_bytes("valid_json_complete_multi_page"),
            input_relative_path="metadata.json",
            report_relative_path="report.txt",
            report_uses_input_path=False,
            expected_exit_code=0,
            expected_terminal_kind=TERMINAL_PREFLIGHT_REPORT,
            expected_report_artifact=REPORT_ARTIFACT_EQUALS_TERMINAL,
            required_terminal_lines=(
                "Market Sentry Local JSON Preflight",
                "Profile: valid_json_complete_multi_page",
                "Metadata Load: LOADED",
                "Workflow: WORKFLOW_BRIDGE_RAN",
                "Bridge: WORKFLOW_RAN",
                "Composition: COMPOSED",
                "Coordinator: OK",
                "Manifest: OK",
                "Harness: OK",
                "Final: OK",
                "Time-of-Day RVOL: OK",
                "Relative Volume: 2.0x",
            ),
            forbidden_terminal_lines=(
                "Result: ERROR",
                "Result: EXPORT_ERROR",
                "Result: COMMAND_ERROR",
            ),
        ),
        LocalJsonPreflightReportContractScenario(
            name="returned_failure_export",
            input_fixture_name="empty_records_json",
            input_fixture_bytes=_fixture_bytes("empty_records_json"),
            input_relative_path="metadata.json",
            report_relative_path="report.txt",
            report_uses_input_path=False,
            expected_exit_code=1,
            expected_terminal_kind=TERMINAL_PREFLIGHT_REPORT,
            expected_report_artifact=REPORT_ARTIFACT_EQUALS_TERMINAL,
            required_terminal_lines=(
                "Market Sentry Local JSON Preflight",
                "Profile: valid_json_complete_multi_page",
                "Metadata Load: LOADED",
                "Workflow: WORKFLOW_BRIDGE_RAN",
                "Bridge: WORKFLOW_RAN",
                "Composition: COMPOSED",
                "Coordinator: MANIFEST_FAILED",
                "Manifest: NO_VALID_METADATA",
                "Harness: FINAL_COMPOSITION_FAILED",
                "Final: BASELINE_FAILED",
                "Time-of-Day RVOL: N/A",
                "Relative Volume: N/A",
            ),
            forbidden_terminal_lines=(
                "Result: ERROR",
                "Result: EXPORT_ERROR",
                "Result: COMMAND_ERROR",
            ),
        ),
        LocalJsonPreflightReportContractScenario(
            name="source_error_export",
            input_fixture_name="unsupported_schema_json_error",
            input_fixture_bytes=_fixture_bytes("unsupported_schema_json_error"),
            input_relative_path="metadata.json",
            report_relative_path="report.txt",
            report_uses_input_path=False,
            expected_exit_code=1,
            expected_terminal_kind=TERMINAL_SOURCE_ERROR,
            expected_report_artifact=REPORT_ARTIFACT_EQUALS_TERMINAL,
            required_terminal_lines=(
                "Market Sentry Local JSON Preflight",
                "Result: ERROR",
                "Error Type: JsonHistoricalSessionMetadataFileSourceError",
                "Error: UNSUPPORTED_SCHEMA_VERSION",
            ),
            forbidden_terminal_lines=(
                "Profile: valid_json_complete_multi_page",
                "Result: EXPORT_ERROR",
                "Result: COMMAND_ERROR",
            ),
        ),
        LocalJsonPreflightReportContractScenario(
            name="export_error_missing_parent",
            input_fixture_name="valid_json_complete_multi_page",
            input_fixture_bytes=_fixture_bytes("valid_json_complete_multi_page"),
            input_relative_path="metadata.json",
            report_relative_path="missing-parent/report.txt",
            report_uses_input_path=False,
            expected_exit_code=1,
            expected_terminal_kind=TERMINAL_EXPORT_ERROR,
            expected_report_artifact=REPORT_ARTIFACT_ABSENT,
            required_terminal_lines=(
                "Market Sentry Local JSON Preflight",
                "Result: EXPORT_ERROR",
                "Error Type: FileNotFoundError",
            ),
            forbidden_terminal_lines=(
                "Profile: valid_json_complete_multi_page",
                "Relative Volume: 2.0x",
                "Result: ERROR",
                "Result: COMMAND_ERROR",
            ),
        ),
        LocalJsonPreflightReportContractScenario(
            name="report_dependency_error",
            input_fixture_name=None,
            input_fixture_bytes=None,
            input_relative_path=None,
            report_relative_path="report.txt",
            report_uses_input_path=False,
            expected_exit_code=2,
            expected_terminal_kind=TERMINAL_COMMAND_ERROR,
            expected_report_artifact=REPORT_ARTIFACT_ABSENT,
            required_terminal_lines=(
                "Market Sentry Local JSON Preflight",
                "Path: N/A",
                "Result: COMMAND_ERROR",
                "Error: --local-json-preflight-report requires --local-json-preflight",
            ),
            forbidden_terminal_lines=(
                "Profile: valid_json_complete_multi_page",
                "Result: ERROR",
                "Result: EXPORT_ERROR",
                "Relative Volume:",
            ),
        ),
        LocalJsonPreflightReportContractScenario(
            name="same_path_command_error",
            input_fixture_name="valid_json_complete_multi_page",
            input_fixture_bytes=_fixture_bytes("valid_json_complete_multi_page"),
            input_relative_path="metadata.json",
            report_relative_path=None,
            report_uses_input_path=True,
            expected_exit_code=2,
            expected_terminal_kind=TERMINAL_COMMAND_ERROR,
            expected_report_artifact=REPORT_ARTIFACT_INPUT_UNCHANGED,
            required_terminal_lines=(
                "Market Sentry Local JSON Preflight",
                "Result: COMMAND_ERROR",
                (
                    "Error: --local-json-preflight-report must differ from "
                    "--local-json-preflight"
                ),
            ),
            forbidden_terminal_lines=(
                "Profile: valid_json_complete_multi_page",
                "Result: ERROR",
                "Result: EXPORT_ERROR",
                "Relative Volume:",
            ),
        ),
    )


def get_local_json_preflight_report_contract_scenario(
    name: str,
) -> LocalJsonPreflightReportContractScenario:
    """Return one scenario by exact, case-sensitive name."""

    for scenario in get_local_json_preflight_report_contract_scenarios():
        if scenario.name == name:
            return scenario
    raise KeyError(name)
