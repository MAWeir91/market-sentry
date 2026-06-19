# Phase 15L — Local JSON Preflight Report Contract Scenarios

## Status

**Planned.** This document defines Phase 15L only.

Phase 15J provides a manual offline JSON preflight command. Phase 15K optionally writes the exact rendered terminal report to one explicit output path.

Phase 15L adds deterministic **contract scenarios** and a thin **test harness** for the already-committed command surface:

```text
named report-contract scenario
+ caller-supplied existing workspace
        ↓
write only the scenario's explicit input fixture when one exists
        ↓
actual main(argv) once
        ↓
capture terminal output and inspect only the explicit scenario paths
        ↓
contract artifact for test assertions
```

It does not add a user command, change report formatting, modify export behavior, create runtime fixtures, or alter any existing Phase 15J / 15K behavior.

---

## Goal

Create a fresh deterministic catalog and thin harness covering the full local JSON report contract for exactly these six outcomes:

```text
valid preflight with successful report export
returned workflow failure with successful report export
expected JSON source error with successful report export
report-output write failure
report-output dependency error
direct same-path command error
```

The harness runs the actual existing `market_sentry.main.main(argv)` exactly once per scenario. It is a local deterministic test utility, not a production CLI operation or an automatic regression service.

The catalog must make report behavior reproducible without:

```text
network calls
provider activation
scanner execution
voice playback
configuration loading
file discovery
JSON parsing in the harness
new workflow execution paths
new report rendering paths
new export behavior
```

---

## Ownership Boundary

```text
Phase 15I owns:
  local JSON fixture byte construction

Phase 15J owns:
  local JSON preflight execution
  terminal success / returned-failure report rendering
  expected source-error report rendering
  exit-code selection for no-export / normal report paths

Phase 15K owns:
  explicit report output write
  export-I/O error rendering
  report-output dependency and same-path command guards

Phase 15L catalog owns:
  fresh named report-contract data
  input fixture bytes selected from existing Phase 15I scenarios
  expected contract assertions

Phase 15L harness owns:
  writing an explicit scenario input fixture when required
  one actual main(argv) call
  terminal stdout capture
  inspection of only the scenario's explicit input/report paths after main returns
  exact artifact retention for tests
```

Phase 15L must not:

```text
parse JSON
decode $datetime values
validate metadata records
inspect raw metadata mappings
construct workflow inputs
call Phase 15H, Phase 15G, Phase 15E, Phase 15C, Phase 15B,
Phase 14J, or lower-stage functions directly
call the Phase 15I harness
call Phase 15J preflight or report-rendering helper directly
call Phase 15K exporter directly
duplicate Phase 15J or Phase 15K report formatting
modify or classify nested workflow artifacts
write report output independently of main(argv)
create a user-facing command
register a provider
load config explicitly
call scanners, alerts, speakers, transports, HTTP, WebSockets, or APIs
create parent directories
discover files
schedule work
perform trading or order behavior
```

The actual `main(argv)` call is the only allowed route through the existing command surface.

---

## Hard Safety Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is **not** a trading bot.

Do not add:

```text
brokerage APIs
order placement
position management
trade execution
buy/sell/enter/exit recommendations
portfolio actions
live provider activation
new MARKET_SENTRY_PROVIDER values
live HTTP calls
WebSockets
automatic metadata acquisition
automatic report generation or scheduling
file discovery
directory scans
background jobs
persistent database storage
scanner-loop integration
alert generation
voice playback
```

`live_composed` remains gated and reserved/inactive.

No network calls are permitted in tests.

---

## Required Files

Create:

```text
docs/61_LOCAL_JSON_PREFLIGHT_REPORT_CONTRACT_SCENARIOS.md
src/market_sentry/local_json_preflight_report_contract_scenario_catalog.py
src/market_sentry/local_json_preflight_report_contract_scenario_harness.py
tests/test_local_json_preflight_report_contract_scenario_catalog.py
tests/test_local_json_preflight_report_contract_scenario_harness.py
```

Do not modify:

```text
README.md
src/market_sentry/main.py
src/market_sentry/local_json_preflight_cli.py
src/market_sentry/local_json_preflight_report_export.py
tests/test_main.py
tests/test_local_json_preflight_cli.py
tests/test_local_json_preflight_report_export.py
Phase 14A–14K
Phase 15A–15K
provider/config/factory/readiness modules
transport/fetcher modules
scanner modules
alert modules
voice modules
fixture modules
JSON-source behavior
workflow behavior
scenario-catalog/harness behavior
```

Phase 15L is a separate deterministic test-contract layer. Existing production behavior must remain byte-for-byte unchanged.

---

# Part A — Data-Only Contract Scenario Catalog

## Catalog Rule

The catalog builds fresh scenario data only.

It must not:

```text
write files
create directories
call main
call preflight
call report renderers
call exporters
read files
execute workflows
```

It may retrieve fixture bytes from the existing Phase 15I public catalog:

```python
get_local_json_metadata_preflight_scenario(name)
```

This is fixture selection only. It must not call the Phase 15I harness.

---

## Allowed Catalog Imports

`src/market_sentry/local_json_preflight_report_contract_scenario_catalog.py` may import only:

```text
standard library:
  dataclasses

market_sentry.data.local_json_metadata_preflight_scenario_catalog:
  get_local_json_metadata_preflight_scenario
```

Do not import:

```text
main
local_json_preflight_cli
local_json_preflight_report_export
the Phase 15I harness
JSON parsing
config
providers
factory
readiness
scanner
alerts
voice
HTTP/transports
Phase 15G / 15H / 15E / 15C / 15B / 14J or lower-stage modules
```

---

## Catalog Public Model

Provide an equivalent frozen model:

```python
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
```

Exact field names may vary, but the model must preserve all responsibilities:

```text
scenario identity
source fixture provenance
fresh fixture bytes or no input fixture
input path intent
report path intent
same-path intent
expected exit code
expected terminal report category
expected explicit report-file contract
required terminal lines
forbidden terminal lines
```

Use stable string constants for expected terminal and artifact behavior:

```text
TERMINAL_PREFLIGHT_REPORT
TERMINAL_SOURCE_ERROR
TERMINAL_EXPORT_ERROR
TERMINAL_COMMAND_ERROR

REPORT_ARTIFACT_EQUALS_TERMINAL
REPORT_ARTIFACT_ABSENT
REPORT_ARTIFACT_INPUT_UNCHANGED
```

These are test expectations only. They must not be interpreted by runtime code or used to create a new domain status.

---

## Catalog Public Functions

Provide:

```python
def get_local_json_preflight_report_contract_scenarios(
) -> tuple[LocalJsonPreflightReportContractScenario, ...]:
    """Return fresh deterministic local JSON report-contract scenarios."""
```

and:

```python
def get_local_json_preflight_report_contract_scenario(
    name: str,
) -> LocalJsonPreflightReportContractScenario:
    """Return one scenario by exact, case-sensitive name."""
```

Unknown names and case-changed names must raise exactly:

```python
KeyError(name)
```

Every catalog call must return fresh scenario objects. When a scenario uses an input fixture, retrieve a fresh Phase 15I scenario and retain the fixture bytes by value.

Bytes are immutable. Tests must compare byte content, not require distinct `bytes` identity.

---

## Required Scenario Names and Exact Order

Create exactly these six scenarios in exactly this order:

```text
valid_export_success
returned_failure_export
source_error_export
export_error_missing_parent
report_dependency_error
same_path_command_error
```

### 1. `valid_export_success`

Use Phase 15I fixture source:

```text
valid_json_complete_multi_page
```

Paths under caller workspace:

```text
input: metadata.json
report: report.txt
```

CLI argv contract:

```text
--local-json-preflight <input>
--local-json-preflight-report <report>
```

Expected:

```text
exit code: 0
terminal kind: TERMINAL_PREFLIGHT_REPORT
report artifact: REPORT_ARTIFACT_EQUALS_TERMINAL
```

Required terminal lines:

```text
Market Sentry Local JSON Preflight
Profile: valid_json_complete_multi_page
Metadata Load: LOADED
Workflow: WORKFLOW_BRIDGE_RAN
Bridge: WORKFLOW_RAN
Composition: COMPOSED
Coordinator: OK
Manifest: OK
Harness: OK
Final: OK
Time-of-Day RVOL: OK
Relative Volume: 2.0x
```

Forbidden terminal lines:

```text
Result: ERROR
Result: EXPORT_ERROR
Result: COMMAND_ERROR
```

### 2. `returned_failure_export`

Use Phase 15I fixture source:

```text
empty_records_json
```

Paths:

```text
input: metadata.json
report: report.txt
```

Expected:

```text
exit code: 1
terminal kind: TERMINAL_PREFLIGHT_REPORT
report artifact: REPORT_ARTIFACT_EQUALS_TERMINAL
```

Required terminal lines:

```text
Market Sentry Local JSON Preflight
Profile: valid_json_complete_multi_page
Metadata Load: LOADED
Workflow: WORKFLOW_BRIDGE_RAN
Bridge: WORKFLOW_RAN
Composition: COMPOSED
Coordinator: MANIFEST_FAILED
Manifest: NO_VALID_METADATA
Harness: FINAL_COMPOSITION_FAILED
Final: BASELINE_FAILED
Time-of-Day RVOL: N/A
Relative Volume: N/A
```

Forbidden terminal lines:

```text
Result: ERROR
Result: EXPORT_ERROR
Result: COMMAND_ERROR
```

This scenario proves that a normally returned non-OK preflight report is still exported exactly and is not transformed into a source or export error.

### 3. `source_error_export`

Use Phase 15I fixture source:

```text
unsupported_schema_json_error
```

Paths:

```text
input: metadata.json
report: report.txt
```

Expected:

```text
exit code: 1
terminal kind: TERMINAL_SOURCE_ERROR
report artifact: REPORT_ARTIFACT_EQUALS_TERMINAL
```

Required terminal lines:

```text
Market Sentry Local JSON Preflight
Result: ERROR
Error Type: JsonHistoricalSessionMetadataFileSourceError
Error: UNSUPPORTED_SCHEMA_VERSION
```

Forbidden terminal lines:

```text
Profile: valid_json_complete_multi_page
Result: EXPORT_ERROR
Result: COMMAND_ERROR
```

This scenario proves that an expected source-error report is exportable exactly like a normal report.

### 4. `export_error_missing_parent`

Use Phase 15I fixture source:

```text
valid_json_complete_multi_page
```

Paths:

```text
input: metadata.json
report: missing-parent/report.txt
```

The harness must not create `missing-parent`.

Expected:

```text
exit code: 1
terminal kind: TERMINAL_EXPORT_ERROR
report artifact: REPORT_ARTIFACT_ABSENT
```

Required terminal lines:

```text
Market Sentry Local JSON Preflight
Result: EXPORT_ERROR
Error Type: FileNotFoundError
```

Forbidden terminal lines:

```text
Profile: valid_json_complete_multi_page
Relative Volume: 2.0x
Result: ERROR
Result: COMMAND_ERROR
```

This scenario proves main writes before printing a normal report. The input bytes must remain unchanged after main returns.

### 5. `report_dependency_error`

Input fixture:

```text
None
```

Paths:

```text
input: None
report: report.txt
```

CLI argv contract:

```text
--local-json-preflight-report <report>
```

Expected:

```text
exit code: 2
terminal kind: TERMINAL_COMMAND_ERROR
report artifact: REPORT_ARTIFACT_ABSENT
```

Required terminal lines:

```text
Market Sentry Local JSON Preflight
Path: N/A
Result: COMMAND_ERROR
Error: --local-json-preflight-report requires --local-json-preflight
```

Forbidden terminal lines:

```text
Profile: valid_json_complete_multi_page
Result: ERROR
Result: EXPORT_ERROR
Relative Volume:
```

The report path must not exist after the run.

### 6. `same_path_command_error`

Use Phase 15I fixture source:

```text
valid_json_complete_multi_page
```

Paths:

```text
input: metadata.json
report: input path exactly
```

Expected:

```text
exit code: 2
terminal kind: TERMINAL_COMMAND_ERROR
report artifact: REPORT_ARTIFACT_INPUT_UNCHANGED
```

Required terminal lines:

```text
Market Sentry Local JSON Preflight
Result: COMMAND_ERROR
Error: --local-json-preflight-report must differ from --local-json-preflight
```

Forbidden terminal lines:

```text
Profile: valid_json_complete_multi_page
Result: ERROR
Result: EXPORT_ERROR
Relative Volume:
```

The initial JSON input bytes written by the harness must remain exactly unchanged after the run. This is a direct parsed-path equality guard only; no alias or symlink detection is expected.

---

# Part B — Thin Contract Scenario Harness

## Harness Rule

The harness is a test utility. It invokes the actual command surface exactly once:

```python
market_sentry.main.main(argv)
```

It must not call Phase 15J or 15K helpers directly.

The caller supplies an existing workspace `Path`, typically `tmp_path`.

The harness may:

```text
write a scenario input fixture to workspace / input_relative_path
capture stdout from one main(argv) call
inspect whether only the explicit input/report paths exist
read only the explicit input/report paths after main returns
```

The harness must not:

```text
create the workspace
create report parent directories
write a report itself
write a fixture when fixture bytes are None
read unrelated workspace files
parse JSON
inspect report internals
catch or transform exceptions raised by main
call main more than once
```

---

## Allowed Harness Imports

`src/market_sentry/local_json_preflight_report_contract_scenario_harness.py` may import only:

```text
standard library:
  contextlib
  dataclasses
  io
  pathlib

market_sentry.main:
  main

market_sentry.local_json_preflight_report_contract_scenario_catalog:
  LocalJsonPreflightReportContractScenario
```

Do not import:

```text
local_json_preflight_cli
local_json_preflight_report_export
Phase 15I catalog/harness
Phase 15G / 15H / 15E / 15C / 15B / 14J or lower-stage modules
config
providers
factory
readiness
scanner
alerts
voice
HTTP/transports
```

---

## Harness Public Model

Provide an equivalent frozen result:

```python
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
```

Exact field names may vary, but retain:

```text
exact supplied scenario
exact supplied workspace
computed explicit input/report paths
input bytes before/after main
one command exit code
captured stdout
report existence
report bytes after main
```

The run artifact exists only when `main(argv)` returns normally. It must not synthesize a run artifact for an unexpected thrown exception.

---

## Harness Public Function

Provide:

```python
def run_local_json_preflight_report_contract_scenario(
    scenario: LocalJsonPreflightReportContractScenario,
    workspace: Path,
) -> LocalJsonPreflightReportContractScenarioRun:
    ...
```

Required behavior:

1. Derive `input_path`:
   - `None` when `scenario.input_relative_path is None`;
   - otherwise exactly `workspace / scenario.input_relative_path`.

2. Derive `report_path`:
   - `None` when `scenario.report_relative_path is None`;
   - exactly `input_path` when `scenario.report_uses_input_path` is true;
   - otherwise exactly `workspace / scenario.report_relative_path`.

3. When `scenario.input_fixture_bytes is not None`:
   - write those exact bytes once to `input_path`;
   - do not create a parent directory;
   - retain `initial_input_bytes` as those exact fixture bytes.

4. Build only the required argv:
   - when input path exists:
     ```text
     --local-json-preflight <input-path>
     ```
   - when report path exists:
     ```text
     --local-json-preflight-report <report-path>
     ```
   - preserve that input-before-report order when both exist.

5. Call actual `main(argv)` exactly once while capturing stdout.

6. After main returns:
   - read `final_input_bytes` only when input path exists;
   - determine `report_exists` only when report path exists;
   - read `report_bytes` only when report path exists and is not the same direct `Path` as input path.

7. Return one frozen artifact with exact scenario and workspace object references.

Do not:

```text
call resolve/absolute/expanduser
create workspace
create parent directories
call main with an empty or fallback argv
retry main
inspect expected scenario fields
validate stdout
modify input after main
write/read the report through a helper other than direct post-run observation
```

---

## Contract Assertions

The harness produces artifacts. It does not evaluate expectations.

Tests must evaluate scenario contracts using only:

```text
scenario expected fields
run artifact fields
public filesystem bytes
captured stdout
```

For `REPORT_ARTIFACT_EQUALS_TERMINAL`, assert:

```python
run.report_bytes is not None
run.stdout == run.report_bytes.decode("utf-8") + "\n"
```

For `REPORT_ARTIFACT_ABSENT`, assert:

```text
report_exists is false
report_bytes is None
```

For `REPORT_ARTIFACT_INPUT_UNCHANGED`, assert:

```python
run.initial_input_bytes is not None
run.final_input_bytes == run.initial_input_bytes
```

Every scenario must also assert:

```text
exit code equals expected exit code
every required terminal line is present
every forbidden terminal line is absent
```

Additionally assert dynamic paths in terminal output where applicable:

```text
successful / returned-failure / source-error / export-error / same-path:
  Path: <exact input path>

successful / returned-failure / source-error / export-error / dependency / same-path:
  Report Path: <exact report path> when the relevant existing report type includes it
```

Remember that normal Phase 15J reports do not include `Report Path`. Export-error and report-output command-error reports do.

---

# Part C — Required Tests

## Catalog Tests

Create:

```text
tests/test_local_json_preflight_report_contract_scenario_catalog.py
```

Test:

```text
exact six names and exact order
exact-name lookup
unknown and case-changed names raise KeyError(name)
frozen scenario model
fresh scenario objects on separate catalog calls
input fixture byte content equals the appropriate fresh Phase 15I fixture bytes
expected field values match every required scenario contract
source boundary: catalog never imports main, CLI helper, export helper, harness,
JSON parser, providers, scanner, voice, HTTP, or workflow modules
catalog never executes main/preflight/export logic
```

For immutable bytes, compare content rather than relying on distinct object identity.

## Harness Unit Tests

Create:

```text
tests/test_local_json_preflight_report_contract_scenario_harness.py
```

Monkeypatch only the direct `main` symbol inside the harness module.

Test:

```text
input fixture writes once to exact workspace child path
argv input-before-report ordering
main called exactly once
stdout capture is retained exactly
final input bytes are observed after main
report bytes are observed only for a distinct report path
same-path scenario uses exact same path string for input and report argv values
input fixture None writes nothing
harness does not create report parents
fresh successful runs create fresh frozen wrapper artifacts
main exception propagates unchanged and no synthetic run artifact is returned
```

Use AST/focused source checks proving the harness:

```text
imports only approved modules
does not import or call Phase 15J/15K helpers directly
does not import source/workflow/provider/runtime/scanner/voice/HTTP modules
does not parse JSON
does not create directories
does not call main more than once
does not inspect expected scenario fields
```

## Actual End-to-End Contract Matrix

Run each of the six catalog scenarios through real harness + actual `main(argv)` using a fresh `tmp_path` workspace.

For every scenario, assert its expected exit, required/forbidden terminal lines, and expected report artifact contract.

Targeted assertions:

```text
valid_export_success:
  output exists
  output UTF-8 bytes decode exactly to stdout without its final print newline
  final terminal line contains Relative Volume: 2.0x

returned_failure_export:
  output exists
  output exactly equals stdout without final newline
  Manifest: NO_VALID_METADATA
  Relative Volume: N/A
  exit 1

source_error_export:
  output exists
  output exactly equals stdout without final newline
  Result: ERROR
  JsonHistoricalSessionMetadataFileSourceError
  UNSUPPORTED_SCHEMA_VERSION
  exit 1

export_error_missing_parent:
  missing-parent is not created
  report does not exist
  stdout contains only EXPORT_ERROR report category
  normal Profile / RVOL report lines are absent
  input bytes are unchanged
  exit 1

report_dependency_error:
  no input path
  report file does not exist
  Path: N/A
  requires-local-preflight message
  exit 2

same_path_command_error:
  input path equals report path directly
  input bytes remain unchanged
  no normal Profile / RVOL report lines
  direct same-path guard message
  exit 2
```

No test may use:

```text
network
API keys
provider activation
audio
file discovery
configuration mutation
live data
trading/order behavior
```

---

## README

Do not modify README. Phase 15L adds no user-facing command or runtime capability.

---

## Validation

Run:

```powershell
python -m pytest tests/test_local_json_preflight_report_contract_scenario_catalog.py
python -m pytest tests/test_local_json_preflight_report_contract_scenario_harness.py
python -m pytest
python -m market_sentry
python -m market_sentry --local-json-preflight .\does-not-exist.json
python -m market_sentry --local-json-preflight-report .\report.txt
```

Then rerun:

```text
fixture
composed_fixture
Alpaca placeholder
both live_composed placeholder checks
both readiness checks
```

No Phase 15L command is added. The existing local preflight command remains the only manual user-facing path.

---

## Acceptance Criteria

Phase 15L is complete when:

```text
- exactly six fresh named contract scenarios exist in required order;
- the catalog only selects existing Phase 15I fixture bytes and builds expectation data;
- the harness invokes actual main(argv) exactly once per scenario;
- valid, returned-failure, source-error, export-error, dependency, and same-path report contracts are covered end to end;
- report bytes equal terminal report content for normal export paths;
- export failure emits only EXPORT_ERROR and does not create a missing report parent;
- dependency and same-path guards do not write a report;
- no existing command or runtime behavior changes;
- no provider, network, scanner, alert, voice, or trading behavior is added;
- the full project suite remains green.
```
