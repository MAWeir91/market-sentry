from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from market_sentry.local_json_preflight_report_contract_scenario_catalog import (
    LocalJsonPreflightReportContractScenario,
)
from market_sentry.main import main


@dataclass(frozen=True)
class LocalJsonPreflightReportContractScenarioRun:
    scenario: LocalJsonPreflightReportContractScenario
    workspace: Path
    input_path: Path | None
    report_path: Path | None
    initial_input_bytes: bytes | None
    final_input_bytes: bytes | None
    exit_code: int
    stdout: str
    report_exists: bool
    report_bytes: bytes | None


def run_local_json_preflight_report_contract_scenario(
    scenario: LocalJsonPreflightReportContractScenario,
    workspace: Path,
) -> LocalJsonPreflightReportContractScenarioRun:
    input_path = (
        None
        if scenario.input_relative_path is None
        else workspace / scenario.input_relative_path
    )
    if scenario.report_uses_input_path:
        report_path = input_path
    elif scenario.report_relative_path is None:
        report_path = None
    else:
        report_path = workspace / scenario.report_relative_path

    initial_input_bytes = scenario.input_fixture_bytes
    if input_path is not None and initial_input_bytes is not None:
        input_path.write_bytes(initial_input_bytes)

    argv = []
    if input_path is not None:
        argv.extend(["--local-json-preflight", str(input_path)])
    if report_path is not None:
        argv.extend(["--local-json-preflight-report", str(report_path)])

    stdout_newline = "\r\n" if Path("C:/").drive else "\n"
    stdout_buffer = StringIO(newline=stdout_newline)
    with redirect_stdout(stdout_buffer):
        exit_code = main(argv)

    final_input_bytes = input_path.read_bytes() if input_path is not None else None
    report_exists = report_path.exists() if report_path is not None else False
    report_bytes = (
        report_path.read_bytes()
        if report_path is not None and report_path != input_path and report_exists
        else None
    )

    return LocalJsonPreflightReportContractScenarioRun(
        scenario=scenario,
        workspace=workspace,
        input_path=input_path,
        report_path=report_path,
        initial_input_bytes=initial_input_bytes,
        final_input_bytes=final_input_bytes,
        exit_code=exit_code,
        stdout=stdout_buffer.getvalue(),
        report_exists=report_exists,
        report_bytes=report_bytes,
    )
