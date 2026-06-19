from dataclasses import dataclass
import json

from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    get_local_json_metadata_preflight_scenario,
)


TERMINAL_BUNDLE_PREFLIGHT_REPORT = "TERMINAL_BUNDLE_PREFLIGHT_REPORT"
TERMINAL_INPUT_ERROR = "TERMINAL_INPUT_ERROR"
TERMINAL_EXPORT_ERROR = "TERMINAL_EXPORT_ERROR"
TERMINAL_COMMAND_ERROR = "TERMINAL_COMMAND_ERROR"

REPORT_ARTIFACT_EQUALS_TERMINAL = "REPORT_ARTIFACT_EQUALS_TERMINAL"
REPORT_ARTIFACT_ABSENT = "REPORT_ARTIFACT_ABSENT"


@dataclass(frozen=True)
class LocalJsonBundlePreflightReportContractScenario:
    """One deterministic two-path local bundle CLI report/export contract."""

    name: str

    metadata_fixture_name: str | None
    metadata_fixture_bytes: bytes | None
    metadata_relative_path: str | None

    bundle_fixture_name: str | None
    bundle_fixture_bytes: bytes | None
    bundle_relative_path: str | None

    report_relative_path: str | None
    report_uses_metadata_path: bool
    report_uses_bundle_path: bool

    expected_exit_code: int
    expected_terminal_kind: str
    expected_report_artifact: str
    expect_input_bytes_unchanged: bool

    required_terminal_lines: tuple[str, ...]
    forbidden_terminal_lines: tuple[str, ...]


def _metadata_fixture_bytes(name: str) -> bytes:
    scenario = get_local_json_metadata_preflight_scenario(name)
    if scenario.fixture_bytes is None:
        raise ValueError(name)
    return scenario.fixture_bytes


def _datetime_tag(value: str) -> dict[str, str]:
    return {"$datetime": value}


def _raw_bar(day: int, minute: int, volume: int) -> dict[str, object]:
    return {
        "t": f"2026-01-{day:02d}T09:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "h": 1.0,
        "l": 1.0,
        "c": 1.0,
    }


def _query(page_token: str | None = None) -> dict[str, object]:
    return {
        "timeframe": "1Min",
        "start": "2026-01-02T09:30:00Z",
        "end": "2026-01-21T10:00:00Z",
        "limit": 1000,
        "page_token": page_token,
        "sort": "asc",
    }


def _json_bytes(value: object) -> bytes:
    return json.dumps(value).encode("utf-8")


def _valid_bundle_fixture_bytes() -> bytes:
    first_page_bars = [
        _raw_bar(2, 31, 25),
        _raw_bar(2, 35, 75),
    ]
    for day in range(3, 12):
        first_page_bars.append(_raw_bar(day, 35, 100))

    second_page_bars = []
    for day in range(12, 22):
        second_page_bars.append(_raw_bar(day, 35, 100))

    return _json_bytes(
        {
            "schema_version": 1,
            "collection": {
                "request": {
                    "symbols": ["RVOL"],
                    "initial_query": _query(),
                    "max_pages": 5,
                },
                "collected_pages": [
                    {
                        "index": 0,
                        "query": _query(page_token="p0"),
                        "page": {
                            "requested_symbols": ["RVOL"],
                            "bars_by_symbol": {"RVOL": first_page_bars},
                            "next_page_token": None,
                        },
                    },
                    {
                        "index": 1,
                        "query": _query(page_token="p1"),
                        "page": {
                            "requested_symbols": ["RVOL"],
                            "bars_by_symbol": {"RVOL": second_page_bars},
                            "next_page_token": None,
                        },
                    },
                ],
                "status": "COMPLETE",
                "page_collection_complete": True,
                "next_page_token": None,
                "reason": None,
            },
            "manifest_request": {
                "symbol": "RVOL",
                "bucket": "09:35",
                "current_session_id": "CURRENT-001",
            },
            "current_series": {
                "symbol": "RVOL",
                "session_id": "CURRENT-001",
                "bucket": "09:35",
                "cutoff_timestamp": _datetime_tag("2026-01-31T09:35:00Z"),
                "bars": [
                    {
                        "timestamp": _datetime_tag("2026-01-31T09:35:00Z"),
                        "volume": 200,
                    }
                ],
            },
            "harness_request": {
                "symbol": "RVOL",
                "bucket": "09:35",
                "current_session_id": "CURRENT-001",
                "page_collection_complete": True,
                "minimum_historical_sessions": 20,
            },
        }
    )


def _unsupported_schema_bundle_fixture_bytes() -> bytes:
    return _json_bytes({"schema_version": 2})


def get_local_json_bundle_preflight_report_contract_scenarios(
) -> tuple[LocalJsonBundlePreflightReportContractScenario, ...]:
    """Return fresh deterministic local bundle report-contract scenarios."""

    valid_metadata = _metadata_fixture_bytes("valid_json_complete_multi_page")
    empty_metadata = _metadata_fixture_bytes("empty_records_json")
    unsupported_metadata = _metadata_fixture_bytes("unsupported_schema_json_error")
    valid_bundle = _valid_bundle_fixture_bytes()
    unsupported_bundle = _unsupported_schema_bundle_fixture_bytes()

    return (
        LocalJsonBundlePreflightReportContractScenario(
            name="valid_bundle_export_success",
            metadata_fixture_name="valid_json_complete_multi_page",
            metadata_fixture_bytes=valid_metadata,
            metadata_relative_path="metadata.json",
            bundle_fixture_name="valid_complete_bundle",
            bundle_fixture_bytes=valid_bundle,
            bundle_relative_path="historical-rvol-bundle.json",
            report_relative_path="report.txt",
            report_uses_metadata_path=False,
            report_uses_bundle_path=False,
            expected_exit_code=0,
            expected_terminal_kind=TERMINAL_BUNDLE_PREFLIGHT_REPORT,
            expected_report_artifact=REPORT_ARTIFACT_EQUALS_TERMINAL,
            expect_input_bytes_unchanged=False,
            required_terminal_lines=(
                "Market Sentry Local JSON Bundle Preflight",
                "Input Mode: EXPLICIT_LOCAL_BUNDLE",
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
                "Profile:",
            ),
        ),
        LocalJsonBundlePreflightReportContractScenario(
            name="returned_workflow_failure_export",
            metadata_fixture_name="empty_records_json",
            metadata_fixture_bytes=empty_metadata,
            metadata_relative_path="metadata.json",
            bundle_fixture_name="valid_complete_bundle",
            bundle_fixture_bytes=valid_bundle,
            bundle_relative_path="historical-rvol-bundle.json",
            report_relative_path="report.txt",
            report_uses_metadata_path=False,
            report_uses_bundle_path=False,
            expected_exit_code=1,
            expected_terminal_kind=TERMINAL_BUNDLE_PREFLIGHT_REPORT,
            expected_report_artifact=REPORT_ARTIFACT_EQUALS_TERMINAL,
            expect_input_bytes_unchanged=False,
            required_terminal_lines=(
                "Market Sentry Local JSON Bundle Preflight",
                "Input Mode: EXPLICIT_LOCAL_BUNDLE",
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
                "Profile:",
            ),
        ),
        LocalJsonBundlePreflightReportContractScenario(
            name="metadata_source_error_export",
            metadata_fixture_name="unsupported_schema_json_error",
            metadata_fixture_bytes=unsupported_metadata,
            metadata_relative_path="metadata.json",
            bundle_fixture_name="valid_complete_bundle",
            bundle_fixture_bytes=valid_bundle,
            bundle_relative_path="historical-rvol-bundle.json",
            report_relative_path="report.txt",
            report_uses_metadata_path=False,
            report_uses_bundle_path=False,
            expected_exit_code=1,
            expected_terminal_kind=TERMINAL_INPUT_ERROR,
            expected_report_artifact=REPORT_ARTIFACT_EQUALS_TERMINAL,
            expect_input_bytes_unchanged=False,
            required_terminal_lines=(
                "Market Sentry Local JSON Bundle Preflight",
                "Metadata Path:",
                "Bundle Path:",
                "Result: ERROR",
                "Error Type: JsonHistoricalSessionMetadataFileSourceError",
                "Error: UNSUPPORTED_SCHEMA_VERSION",
            ),
            forbidden_terminal_lines=(
                "Input Mode: EXPLICIT_LOCAL_BUNDLE",
                "Result: EXPORT_ERROR",
                "Result: COMMAND_ERROR",
                "Profile:",
            ),
        ),
        LocalJsonBundlePreflightReportContractScenario(
            name="bundle_input_error_export",
            metadata_fixture_name="valid_json_complete_multi_page",
            metadata_fixture_bytes=valid_metadata,
            metadata_relative_path="metadata.json",
            bundle_fixture_name="unsupported_schema_bundle",
            bundle_fixture_bytes=unsupported_bundle,
            bundle_relative_path="historical-rvol-bundle.json",
            report_relative_path="report.txt",
            report_uses_metadata_path=False,
            report_uses_bundle_path=False,
            expected_exit_code=1,
            expected_terminal_kind=TERMINAL_INPUT_ERROR,
            expected_report_artifact=REPORT_ARTIFACT_EQUALS_TERMINAL,
            expect_input_bytes_unchanged=False,
            required_terminal_lines=(
                "Market Sentry Local JSON Bundle Preflight",
                "Metadata Path:",
                "Bundle Path:",
                "Result: ERROR",
                "Error Type: JsonHistoricalRvolBundleError",
                "Error: UNSUPPORTED_SCHEMA_VERSION",
            ),
            forbidden_terminal_lines=(
                "Input Mode: EXPLICIT_LOCAL_BUNDLE",
                "Result: EXPORT_ERROR",
                "Result: COMMAND_ERROR",
                "Profile:",
            ),
        ),
        LocalJsonBundlePreflightReportContractScenario(
            name="export_error_missing_parent",
            metadata_fixture_name="valid_json_complete_multi_page",
            metadata_fixture_bytes=valid_metadata,
            metadata_relative_path="metadata.json",
            bundle_fixture_name="valid_complete_bundle",
            bundle_fixture_bytes=valid_bundle,
            bundle_relative_path="historical-rvol-bundle.json",
            report_relative_path="missing-parent/report.txt",
            report_uses_metadata_path=False,
            report_uses_bundle_path=False,
            expected_exit_code=1,
            expected_terminal_kind=TERMINAL_EXPORT_ERROR,
            expected_report_artifact=REPORT_ARTIFACT_ABSENT,
            expect_input_bytes_unchanged=True,
            required_terminal_lines=(
                "Market Sentry Local JSON Bundle Preflight",
                "Metadata Path:",
                "Bundle Path:",
                "Report Path:",
                "Result: EXPORT_ERROR",
                "Error Type: FileNotFoundError",
            ),
            forbidden_terminal_lines=(
                "Input Mode: EXPLICIT_LOCAL_BUNDLE",
                "Relative Volume: 2.0x",
                "Result: ERROR",
                "Result: COMMAND_ERROR",
                "Profile:",
            ),
        ),
        LocalJsonBundlePreflightReportContractScenario(
            name="bundle_report_dependency_error",
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
            required_terminal_lines=(
                "Market Sentry Local JSON Bundle Preflight",
                "Metadata Path: N/A",
                "Bundle Path: N/A",
                "Report Path:",
                "Result: COMMAND_ERROR",
                (
                    "Error: --local-json-bundle-preflight-report requires "
                    "--local-json-bundle-preflight"
                ),
            ),
            forbidden_terminal_lines=(
                "Input Mode: EXPLICIT_LOCAL_BUNDLE",
                "Result: ERROR",
                "Result: EXPORT_ERROR",
                "Relative Volume:",
                "Profile:",
            ),
        ),
        LocalJsonBundlePreflightReportContractScenario(
            name="report_same_metadata_path_command_error",
            metadata_fixture_name="valid_json_complete_multi_page",
            metadata_fixture_bytes=valid_metadata,
            metadata_relative_path="metadata.json",
            bundle_fixture_name="valid_complete_bundle",
            bundle_fixture_bytes=valid_bundle,
            bundle_relative_path="historical-rvol-bundle.json",
            report_relative_path=None,
            report_uses_metadata_path=True,
            report_uses_bundle_path=False,
            expected_exit_code=2,
            expected_terminal_kind=TERMINAL_COMMAND_ERROR,
            expected_report_artifact=REPORT_ARTIFACT_ABSENT,
            expect_input_bytes_unchanged=True,
            required_terminal_lines=(
                "Market Sentry Local JSON Bundle Preflight",
                "Metadata Path:",
                "Bundle Path:",
                "Report Path:",
                "Result: COMMAND_ERROR",
                (
                    "Error: --local-json-bundle-preflight-report must differ "
                    "from metadata path"
                ),
            ),
            forbidden_terminal_lines=(
                "Input Mode: EXPLICIT_LOCAL_BUNDLE",
                "Result: ERROR",
                "Result: EXPORT_ERROR",
                "Relative Volume:",
                "Profile:",
            ),
        ),
        LocalJsonBundlePreflightReportContractScenario(
            name="report_same_bundle_path_command_error",
            metadata_fixture_name="valid_json_complete_multi_page",
            metadata_fixture_bytes=valid_metadata,
            metadata_relative_path="metadata.json",
            bundle_fixture_name="valid_complete_bundle",
            bundle_fixture_bytes=valid_bundle,
            bundle_relative_path="historical-rvol-bundle.json",
            report_relative_path=None,
            report_uses_metadata_path=False,
            report_uses_bundle_path=True,
            expected_exit_code=2,
            expected_terminal_kind=TERMINAL_COMMAND_ERROR,
            expected_report_artifact=REPORT_ARTIFACT_ABSENT,
            expect_input_bytes_unchanged=True,
            required_terminal_lines=(
                "Market Sentry Local JSON Bundle Preflight",
                "Metadata Path:",
                "Bundle Path:",
                "Report Path:",
                "Result: COMMAND_ERROR",
                (
                    "Error: --local-json-bundle-preflight-report must differ "
                    "from bundle path"
                ),
            ),
            forbidden_terminal_lines=(
                "Input Mode: EXPLICIT_LOCAL_BUNDLE",
                "Result: ERROR",
                "Result: EXPORT_ERROR",
                "Relative Volume:",
                "Profile:",
            ),
        ),
    )


def get_local_json_bundle_preflight_report_contract_scenario(
    name: str,
) -> LocalJsonBundlePreflightReportContractScenario:
    """Return one scenario by exact, case-sensitive name."""

    for scenario in get_local_json_bundle_preflight_report_contract_scenarios():
        if scenario.name == name:
            return scenario
    raise KeyError(name)
