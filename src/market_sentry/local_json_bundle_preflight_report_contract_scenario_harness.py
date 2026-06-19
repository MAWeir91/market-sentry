import contextlib
from dataclasses import dataclass
import io
import pathlib

from market_sentry.local_json_bundle_preflight_report_contract_scenario_catalog import (
    LocalJsonBundlePreflightReportContractScenario,
)
from market_sentry.main import main


@dataclass(frozen=True)
class LocalJsonBundlePreflightReportContractScenarioRun:
    scenario: LocalJsonBundlePreflightReportContractScenario
    workspace: pathlib.Path

    metadata_path: pathlib.Path | None
    bundle_path: pathlib.Path | None
    report_path: pathlib.Path | None

    initial_metadata_bytes: bytes | None
    final_metadata_bytes: bytes | None
    initial_bundle_bytes: bytes | None
    final_bundle_bytes: bytes | None

    exit_code: int
    stdout: str

    report_exists: bool
    report_bytes: bytes | None


def run_local_json_bundle_preflight_report_contract_scenario(
    scenario: LocalJsonBundlePreflightReportContractScenario,
    workspace: pathlib.Path,
) -> LocalJsonBundlePreflightReportContractScenarioRun:
    metadata_path = (
        None
        if scenario.metadata_relative_path is None
        else workspace / scenario.metadata_relative_path
    )
    bundle_path = (
        None
        if scenario.bundle_relative_path is None
        else workspace / scenario.bundle_relative_path
    )
    if scenario.report_uses_metadata_path:
        report_path = metadata_path
    elif scenario.report_uses_bundle_path:
        report_path = bundle_path
    elif scenario.report_relative_path is None:
        report_path = None
    else:
        report_path = workspace / scenario.report_relative_path

    initial_metadata_bytes = scenario.metadata_fixture_bytes
    if metadata_path is not None and initial_metadata_bytes is not None:
        metadata_path.write_bytes(initial_metadata_bytes)

    initial_bundle_bytes = scenario.bundle_fixture_bytes
    if bundle_path is not None and initial_bundle_bytes is not None:
        bundle_path.write_bytes(initial_bundle_bytes)

    argv = []
    if metadata_path is not None and bundle_path is not None:
        argv.extend(
            [
                "--local-json-bundle-preflight",
                str(metadata_path),
                str(bundle_path),
            ]
        )
    if report_path is not None:
        argv.extend(["--local-json-bundle-preflight-report", str(report_path)])

    stdout_newline = "\r\n" if pathlib.Path("C:/").drive else "\n"
    stdout_buffer = io.StringIO(newline=stdout_newline)
    with contextlib.redirect_stdout(stdout_buffer):
        exit_code = main(argv)

    final_metadata_bytes = (
        metadata_path.read_bytes() if metadata_path is not None else None
    )
    final_bundle_bytes = bundle_path.read_bytes() if bundle_path is not None else None
    report_is_distinct_input = (
        report_path is not None
        and report_path != metadata_path
        and report_path != bundle_path
    )
    report_exists = report_is_distinct_input and report_path.exists()
    report_bytes = report_path.read_bytes() if report_exists else None

    return LocalJsonBundlePreflightReportContractScenarioRun(
        scenario=scenario,
        workspace=workspace,
        metadata_path=metadata_path,
        bundle_path=bundle_path,
        report_path=report_path,
        initial_metadata_bytes=initial_metadata_bytes,
        final_metadata_bytes=final_metadata_bytes,
        initial_bundle_bytes=initial_bundle_bytes,
        final_bundle_bytes=final_bundle_bytes,
        exit_code=exit_code,
        stdout=stdout_buffer.getvalue(),
        report_exists=report_exists,
        report_bytes=report_bytes,
    )
