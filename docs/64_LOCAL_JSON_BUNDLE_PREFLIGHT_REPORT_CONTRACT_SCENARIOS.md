# Phase 16C — Local JSON Bundle Preflight Report Contract Scenarios

## Status

**Planned.** This document defines Phase 16C only.

Phase 16B adds a manual, offline two-input command:

```text
--local-json-bundle-preflight <METADATA_PATH> <BUNDLE_PATH>
--local-json-bundle-preflight-report <REPORT_PATH>
```

Phase 16C adds deterministic catalog scenarios and a thin test harness around that committed command surface.

```text
named bundle-report contract scenario
+ caller-supplied existing workspace
        ↓
write only explicit metadata / bundle fixture bytes
        ↓
actual market_sentry.main.main(argv) once
        ↓
capture terminal output and inspect only explicit input/report paths
        ↓
frozen test artifact for assertions
```

It does not add a command, modify Phase 16B behavior, change report rendering or exporting, add runtime behavior, or activate any provider.

---

## Goal

Create a fresh deterministic catalog and thin harness covering exactly these eight two-path CLI report contracts:

```text
valid bundle preflight with report export
returned workflow failure with report export
metadata source error with report export
bundle input error with report export
report output write failure
bundle report dependency error
report path equals metadata input command error
report path equals bundle input command error
```

The harness must call the actual existing:

```python
market_sentry.main.main(argv)
```

exactly once per scenario.

The catalog and harness are test utilities only. They must remain entirely offline and must not create a second workflow, renderer, exporter, or CLI path.

---

## Ownership Boundary

```text
Phase 15I owns:
  reusable local metadata fixture bytes

Phase 16A owns:
  historical RVOL bundle schema and loader behavior

Phase 16B owns:
  actual two-path CLI parsing
  command guards
  explicit bundle loading
  existing Phase 15H invocation
  returned/error report rendering
  optional exact report export
  exit-code selection

Phase 16C catalog owns:
  fresh named scenario data
  metadata fixture selection
  pure static bundle fixture byte construction
  expected report-contract assertions

Phase 16C harness owns:
  writing only the scenario's explicit input fixture bytes
  one actual main(argv) call
  terminal stdout capture
  observation of only explicit metadata, bundle, and report paths
  frozen artifact retention for test assertions
```

Phase 16C must not:

```text
parse a metadata file
load a bundle directly
call Phase 16B helper functions directly
call Phase 16B exporter directly
call Phase 16A loader directly
call Phase 15H or any workflow directly
render a report
write a report independently of main(argv)
decode bundle JSON in production code
validate metadata records
validate raw bars
calculate RVOL
construct candidates
register a provider
load config explicitly
call scanners, alerts, speakers, transports, HTTP, WebSockets, or APIs
create workspace or report-parent directories
discover files
schedule work
perform trading or order behavior
```

The actual `main(argv)` call is the only allowed route through the command surface.

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
network calls
automatic metadata or bundle acquisition
file discovery
directory scans
background jobs
persistent databases
scanner-loop integration
alerts
voice playback
```

No network calls are permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

## Required Files

Create:

```text
docs/64_LOCAL_JSON_BUNDLE_PREFLIGHT_REPORT_CONTRACT_SCENARIOS.md
src/market_sentry/local_json_bundle_preflight_report_contract_scenario_catalog.py
src/market_sentry/local_json_bundle_preflight_report_contract_scenario_harness.py
tests/test_local_json_bundle_preflight_report_contract_scenario_catalog.py
tests/test_local_json_bundle_preflight_report_contract_scenario_harness.py
```

Do not modify:

```text
README.md
src/market_sentry/main.py
src/market_sentry/local_json_bundle_preflight_cli.py
src/market_sentry/local_json_bundle_preflight_report_export.py
src/market_sentry/data/json_historical_rvol_bundle.py
tests/test_main.py
tests/test_local_json_bundle_preflight_cli.py
tests/test_local_json_bundle_preflight_report_export.py
tests/test_json_historical_rvol_bundle.py
Phase 14A–14K
Phase 15A–15L
Phase 16A–16B
provider/config/factory/readiness modules
transport/fetcher modules
scanner modules
alert modules
voice modules
metadata source modules
workflow modules
```

Phase 16C is a new deterministic contract layer. Existing production behavior must remain byte-for-byte unchanged.

---

# Part A — Data-Only Bundle Contract Scenario Catalog

## Catalog Rule

The catalog builds fresh data only.

It must not:

```text
write files
create directories
call main
call Phase 16B helper/exporter functions
call Phase 16A loader
read files
run workflows
execute preflight
use environment variables
```

The catalog may:

```text
retrieve metadata fixture bytes from the public Phase 15I catalog
construct static JSON-compatible bundle fixture mappings
serialize those static bundle mappings to UTF-8 bytes with json.dumps
```

It must not import tests or reuse test-only helper functions.

---

## Allowed Catalog Imports

`src/market_sentry/local_json_bundle_preflight_report_contract_scenario_catalog.py` may import only:

```text
standard library:
  dataclasses
  json

market_sentry.data.local_json_metadata_preflight_scenario_catalog:
  get_local_json_metadata_preflight_scenario
```

Do not import:

```text
main
Phase 16B CLI helper
Phase 16B report exporter
Phase 16A bundle loader
Phase 15L catalog or harness
tests
JSON metadata source
config
providers
factory
readiness
scanner
alerts
voice
HTTP/transports
Phase 15H or lower-stage workflow modules
```

---

## Catalog Public Model

Provide an equivalent frozen model:

```python
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
```

Exact field names may vary, but the model must preserve all responsibilities:

```text
scenario identity
metadata fixture provenance and bytes
bundle fixture provenance and bytes
metadata / bundle / report path intent
metadata-input collision intent
bundle-input collision intent
expected exit code
expected terminal category
expected report-file contract
whether input bytes must remain unchanged
required terminal lines
forbidden terminal lines
```

Use stable string constants:

```text
TERMINAL_BUNDLE_PREFLIGHT_REPORT
TERMINAL_INPUT_ERROR
TERMINAL_EXPORT_ERROR
TERMINAL_COMMAND_ERROR

REPORT_ARTIFACT_EQUALS_TERMINAL
REPORT_ARTIFACT_ABSENT
```

These constants are test expectations only. They are not runtime statuses.

---

## Catalog Public Functions

Provide:

```python
def get_local_json_bundle_preflight_report_contract_scenarios(
) -> tuple[LocalJsonBundlePreflightReportContractScenario, ...]:
    """Return fresh deterministic local bundle report-contract scenarios."""
```

and:

```python
def get_local_json_bundle_preflight_report_contract_scenario(
    name: str,
) -> LocalJsonBundlePreflightReportContractScenario:
    """Return one scenario by exact, case-sensitive name."""
```

Unknown names and case-changed names must raise exactly:

```python
KeyError(name)
```

Every catalog call must return fresh scenario objects.

When a metadata fixture is used, retrieve a fresh Phase 15I scenario and retain its fixture bytes by value. Bytes are immutable; tests compare byte content rather than requiring distinct `bytes` identity.

Every bundle fixture byte sequence must be constructed freshly by the Phase 16C catalog. The catalog must not import test helpers to obtain it.

---

## Required Scenario Names and Exact Order

Create exactly these eight scenarios in exactly this order:

```text
valid_bundle_export_success
returned_workflow_failure_export
metadata_source_error_export
bundle_input_error_export
export_error_missing_parent
bundle_report_dependency_error
report_same_metadata_path_command_error
report_same_bundle_path_command_error
```

---

## Bundle Fixture Definitions

### `valid_complete_bundle`

Build a valid JSON bundle equivalent to the Phase 16A compatibility fixture:

```text
schema_version: 1
collection:
  request:
    symbols: ["RVOL"]
    initial_query:
      timeframe: "1Min"
      start: "2026-01-02T09:30:00Z"
      end: "2026-01-21T10:00:00Z"
      limit: 1000
      page_token: null
      sort: "asc"
    max_pages: 5

  collected_pages:
    page 0:
      index: 0
      query uses page_token "p0"
      requested_symbols: ["RVOL"]
      bars_by_symbol["RVOL"]:
        2026-01-02 09:31 volume 25
        2026-01-02 09:35 volume 75
        2026-01-03 through 2026-01-11 at 09:35 volume 100
      next_page_token: null

    page 1:
      index: 1
      query uses page_token "p1"
      requested_symbols: ["RVOL"]
      bars_by_symbol["RVOL"]:
        2026-01-12 through 2026-01-21 at 09:35 volume 100
      next_page_token: null

  status: "COMPLETE"
  page_collection_complete: true
  next_page_token: null
  reason: null

manifest_request:
  symbol: "RVOL"
  bucket: "09:35"
  current_session_id: "CURRENT-001"

current_series:
  symbol: "RVOL"
  session_id: "CURRENT-001"
  bucket: "09:35"
  cutoff_timestamp: {"$datetime": "2026-01-31T09:35:00Z"}
  bars:
    - timestamp: {"$datetime": "2026-01-31T09:35:00Z"}
      volume: 200

harness_request:
  symbol: "RVOL"
  bucket: "09:35"
  current_session_id: "CURRENT-001"
  page_collection_complete: true
  minimum_historical_sessions: 20
```

Raw historical bars must carry the standard raw fields:

```text
t
v
o
h
l
c
```

using `1.0` for OHLC values.

The initial `collection.request.initial_query.page_token` is `null`. Each collected page query uses the listed page token. `next_page_token` is `null` for each page.

This bundle must reach existing final TOD-RVOL `2.0x` when paired with the Phase 15I metadata fixture `valid_json_complete_multi_page`.

### `unsupported_schema_bundle`

Build only the minimal JSON object:

```json
{"schema_version": 2}
```

The Phase 16A loader must reject it with:

```text
JsonHistoricalRvolBundleError
UNSUPPORTED_SCHEMA_VERSION
```

The catalog must not fill missing fields because schema validation occurs first.

---

## Required Scenario Contracts

### 1. `valid_bundle_export_success`

Inputs:

```text
metadata fixture: valid_json_complete_multi_page
metadata path: metadata.json

bundle fixture: valid_complete_bundle
bundle path: historical-rvol-bundle.json

report path: report.txt
```

CLI argv contract:

```text
--local-json-bundle-preflight <metadata> <bundle>
--local-json-bundle-preflight-report <report>
```

Expected:

```text
exit code: 0
terminal kind: TERMINAL_BUNDLE_PREFLIGHT_REPORT
report artifact: REPORT_ARTIFACT_EQUALS_TERMINAL
input integrity: not required by this scenario
```

Required terminal lines:

```text
Market Sentry Local JSON Bundle Preflight
Input Mode: EXPLICIT_LOCAL_BUNDLE
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
Profile:
```

### 2. `returned_workflow_failure_export`

Inputs:

```text
metadata fixture: empty_records_json
metadata path: metadata.json

bundle fixture: valid_complete_bundle
bundle path: historical-rvol-bundle.json

report path: report.txt
```

Expected:

```text
exit code: 1
terminal kind: TERMINAL_BUNDLE_PREFLIGHT_REPORT
report artifact: REPORT_ARTIFACT_EQUALS_TERMINAL
input integrity: not required by this scenario
```

Required terminal lines:

```text
Market Sentry Local JSON Bundle Preflight
Input Mode: EXPLICIT_LOCAL_BUNDLE
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
Profile:
```

This proves a normally returned non-OK workflow report is exported exactly and not converted to an input or export error.

### 3. `metadata_source_error_export`

Inputs:

```text
metadata fixture: unsupported_schema_json_error
metadata path: metadata.json

bundle fixture: valid_complete_bundle
bundle path: historical-rvol-bundle.json

report path: report.txt
```

Expected:

```text
exit code: 1
terminal kind: TERMINAL_INPUT_ERROR
report artifact: REPORT_ARTIFACT_EQUALS_TERMINAL
input integrity: not required by this scenario
```

Required terminal lines:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path:
Bundle Path:
Result: ERROR
Error Type: JsonHistoricalSessionMetadataFileSourceError
Error: UNSUPPORTED_SCHEMA_VERSION
```

Forbidden terminal lines:

```text
Input Mode: EXPLICIT_LOCAL_BUNDLE
Result: EXPORT_ERROR
Result: COMMAND_ERROR
Profile:
```

This proves an expected metadata-source error report remains exportable.

### 4. `bundle_input_error_export`

Inputs:

```text
metadata fixture: valid_json_complete_multi_page
metadata path: metadata.json

bundle fixture: unsupported_schema_bundle
bundle path: historical-rvol-bundle.json

report path: report.txt
```

Expected:

```text
exit code: 1
terminal kind: TERMINAL_INPUT_ERROR
report artifact: REPORT_ARTIFACT_EQUALS_TERMINAL
input integrity: not required by this scenario
```

Required terminal lines:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path:
Bundle Path:
Result: ERROR
Error Type: JsonHistoricalRvolBundleError
Error: UNSUPPORTED_SCHEMA_VERSION
```

Forbidden terminal lines:

```text
Input Mode: EXPLICIT_LOCAL_BUNDLE
Result: EXPORT_ERROR
Result: COMMAND_ERROR
Profile:
```

This proves an expected Phase 16A bundle-loader error remains exportable.

### 5. `export_error_missing_parent`

Inputs:

```text
metadata fixture: valid_json_complete_multi_page
metadata path: metadata.json

bundle fixture: valid_complete_bundle
bundle path: historical-rvol-bundle.json

report path: missing-parent/report.txt
```

The harness must not create `missing-parent`.

Expected:

```text
exit code: 1
terminal kind: TERMINAL_EXPORT_ERROR
report artifact: REPORT_ARTIFACT_ABSENT
input integrity: required
```

Required terminal lines:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path:
Bundle Path:
Report Path:
Result: EXPORT_ERROR
Error Type: FileNotFoundError
```

Forbidden terminal lines:

```text
Input Mode: EXPLICIT_LOCAL_BUNDLE
Relative Volume: 2.0x
Result: ERROR
Result: COMMAND_ERROR
Profile:
```

Both metadata and bundle bytes must remain unchanged after the run.

### 6. `bundle_report_dependency_error`

Inputs:

```text
metadata fixture: none
bundle fixture: none
report path: report.txt
```

CLI argv contract:

```text
--local-json-bundle-preflight-report <report>
```

Expected:

```text
exit code: 2
terminal kind: TERMINAL_COMMAND_ERROR
report artifact: REPORT_ARTIFACT_ABSENT
input integrity: not applicable
```

Required terminal lines:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path: N/A
Bundle Path: N/A
Report Path:
Result: COMMAND_ERROR
Error: --local-json-bundle-preflight-report requires --local-json-bundle-preflight
```

Forbidden terminal lines:

```text
Input Mode: EXPLICIT_LOCAL_BUNDLE
Result: ERROR
Result: EXPORT_ERROR
Relative Volume:
Profile:
```

No report path may exist after the run.

### 7. `report_same_metadata_path_command_error`

Inputs:

```text
metadata fixture: valid_json_complete_multi_page
metadata path: metadata.json

bundle fixture: valid_complete_bundle
bundle path: historical-rvol-bundle.json

report path: exactly the metadata input path
```

Expected:

```text
exit code: 2
terminal kind: TERMINAL_COMMAND_ERROR
report artifact: REPORT_ARTIFACT_ABSENT
input integrity: required
```

Required terminal lines:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path:
Bundle Path:
Report Path:
Result: COMMAND_ERROR
Error: --local-json-bundle-preflight-report must differ from metadata path
```

Forbidden terminal lines:

```text
Input Mode: EXPLICIT_LOCAL_BUNDLE
Result: ERROR
Result: EXPORT_ERROR
Relative Volume:
Profile:
```

Both input files must remain byte-for-byte unchanged.

### 8. `report_same_bundle_path_command_error`

Inputs:

```text
metadata fixture: valid_json_complete_multi_page
metadata path: metadata.json

bundle fixture: valid_complete_bundle
bundle path: historical-rvol-bundle.json

report path: exactly the bundle input path
```

Expected:

```text
exit code: 2
terminal kind: TERMINAL_COMMAND_ERROR
report artifact: REPORT_ARTIFACT_ABSENT
input integrity: required
```

Required terminal lines:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path:
Bundle Path:
Report Path:
Result: COMMAND_ERROR
Error: --local-json-bundle-preflight-report must differ from bundle path
```

Forbidden terminal lines:

```text
Input Mode: EXPLICIT_LOCAL_BUNDLE
Result: ERROR
Result: EXPORT_ERROR
Relative Volume:
Profile:
```

Both input files must remain byte-for-byte unchanged.

---

# Part B — Thin Bundle Contract Scenario Harness

## Harness Rule

The harness is a test utility. It invokes the actual command surface exactly once:

```python
market_sentry.main.main(argv)
```

It must not call Phase 16B helper or exporter functions directly.

The caller supplies an existing workspace `Path`, normally `tmp_path`.

The harness may:

```text
write one explicit metadata fixture file when scenario bytes exist
write one explicit bundle fixture file when scenario bytes exist
capture stdout from one main(argv) call
inspect only the explicit metadata, bundle, and report paths after main returns
```

The harness must not:

```text
create workspace
create report parent directories
write a report itself
write input fixtures when their bytes are None
read unrelated workspace files
parse bundle or metadata JSON
inspect expected scenario fields
catch or transform exceptions from main
call main more than once
```

---

## Allowed Harness Imports

`src/market_sentry/local_json_bundle_preflight_report_contract_scenario_harness.py` may import only:

```text
standard library:
  contextlib
  dataclasses
  io
  pathlib

market_sentry.main:
  main

market_sentry.local_json_bundle_preflight_report_contract_scenario_catalog:
  LocalJsonBundlePreflightReportContractScenario
```

Do not import:

```text
Phase 16B CLI helper
Phase 16B exporter
Phase 16A loader
Phase 15I catalog/harness
metadata sources
workflow modules
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
class LocalJsonBundlePreflightReportContractScenarioRun:
    scenario: LocalJsonBundlePreflightReportContractScenario
    workspace: Path

    metadata_path: Path | None
    bundle_path: Path | None
    report_path: Path | None

    initial_metadata_bytes: bytes | None
    final_metadata_bytes: bytes | None
    initial_bundle_bytes: bytes | None
    final_bundle_bytes: bytes | None

    exit_code: int
    stdout: str

    report_exists: bool
    report_bytes: bytes | None
```

Exact field names may vary, but retain:

```text
exact scenario and workspace references
computed explicit paths
metadata bytes before/after main
bundle bytes before/after main
one exit code
captured stdout
report existence and bytes
```

Return an artifact only when `main(argv)` returns normally. An unexpected exception must propagate unchanged.

---

## Harness Public Function

Provide:

```python
def run_local_json_bundle_preflight_report_contract_scenario(
    scenario: LocalJsonBundlePreflightReportContractScenario,
    workspace: Path,
) -> LocalJsonBundlePreflightReportContractScenarioRun:
    ...
```

Required behavior:

1. Derive `metadata_path`:
   - `None` when `scenario.metadata_relative_path is None`;
   - otherwise exactly `workspace / scenario.metadata_relative_path`.

2. Derive `bundle_path`:
   - `None` when `scenario.bundle_relative_path is None`;
   - otherwise exactly `workspace / scenario.bundle_relative_path`.

3. Derive `report_path`:
   - exact `metadata_path` when `scenario.report_uses_metadata_path`;
   - exact `bundle_path` when `scenario.report_uses_bundle_path`;
   - `None` when neither collision intent applies and `report_relative_path is None`;
   - otherwise exactly `workspace / scenario.report_relative_path`.

4. When metadata bytes are present:
   - write those exact bytes once to `metadata_path`;
   - do not create a parent directory;
   - retain the exact bytes as `initial_metadata_bytes`.

5. When bundle bytes are present:
   - write those exact bytes once to `bundle_path`;
   - do not create a parent directory;
   - retain the exact bytes as `initial_bundle_bytes`.

6. Build only the required argv:
   - when both metadata and bundle paths exist:
     ```text
     --local-json-bundle-preflight <metadata-path> <bundle-path>
     ```
   - when report path exists:
     ```text
     --local-json-bundle-preflight-report <report-path>
     ```
   - preserve preflight-before-report order.

7. Invoke actual `main(argv)` exactly once while capturing stdout.

8. After main returns:
   - read final metadata bytes only when metadata path exists;
   - read final bundle bytes only when bundle path exists;
   - determine report existence only when report path exists;
   - read report bytes only when report path exists, exists on disk, and is distinct from both direct input paths.

9. Return one frozen artifact retaining exact scenario and workspace object references.

Do not:

```text
call resolve/absolute/expanduser
create workspace
create parents
call main with fallback argv
retry main
validate stdout
read report bytes when report path equals either input
mutate input files after main
write/read through Phase 16B helpers
```

---

# Part C — Contract Assertions

The harness only produces artifacts. Tests evaluate scenario expectations using:

```text
scenario expected fields
run artifact fields
captured stdout
explicit input/report file bytes
```

For `REPORT_ARTIFACT_EQUALS_TERMINAL`, assert:

```python
run.report_bytes is not None
run.stdout == run.report_bytes.decode("utf-8") + platform_terminal_newline
```

Use the same platform terminal-newline treatment as Phase 15L’s harness tests.

For `REPORT_ARTIFACT_ABSENT`, assert:

```text
report_exists is false
report_bytes is None
```

For scenarios with `expect_input_bytes_unchanged`:

```python
run.initial_metadata_bytes is not None
run.final_metadata_bytes == run.initial_metadata_bytes

run.initial_bundle_bytes is not None
run.final_bundle_bytes == run.initial_bundle_bytes
```

Every scenario must also assert:

```text
exit code equals expected exit code
every required terminal line is present
every forbidden terminal line is absent
```

Use dynamic path assertions where each report category includes a path:

```text
normal returned bundle report:
  Metadata Path: <exact metadata path>
  Bundle Path: <exact bundle path>

input-error report:
  Metadata Path: <exact metadata path>
  Bundle Path: <exact bundle path>

export-error report:
  Metadata Path: <exact metadata path>
  Bundle Path: <exact bundle path>
  Report Path: <exact report path>

dependency report:
  Metadata Path: N/A
  Bundle Path: N/A
  Report Path: <exact report path>

input collision errors:
  Metadata Path: <exact metadata path>
  Bundle Path: <exact bundle path>
  Report Path: <same direct metadata or bundle path>
```

Do not add a duplicate report renderer or compare against hard-coded whole multiline report strings.

---

# Part D — Required Tests

## Catalog Tests

Create:

```text
tests/test_local_json_bundle_preflight_report_contract_scenario_catalog.py
```

Test:

```text
exact eight names and exact order
exact-name lookup
unknown and case-changed names raise KeyError(name)
frozen scenario model
fresh scenario objects on separate catalog calls
metadata fixture byte content matches fresh Phase 15I fixture bytes
valid bundle fixture bytes are fresh valid JSON-compatible bytes
unsupported bundle fixture has schema_version 2
expected fields match all eight scenario contracts
catalog source imports only approved modules
catalog never executes main, loaders, helpers, exporters, or workflows
```

Test valid complete bundle bytes only as fixture data. Do not duplicate the Phase 16A loader’s structural validation in this catalog test.

## Harness Unit Tests

Create:

```text
tests/test_local_json_bundle_preflight_report_contract_scenario_harness.py
```

Monkeypatch only the direct `main` symbol inside the harness module.

Test:

```text
metadata and bundle fixture bytes each write once to exact workspace children
argv contains metadata first, bundle second, then report flag/path
main is called exactly once
stdout capture is retained exactly
metadata/bundle final bytes are observed after main
report bytes are observed only for a distinct report path
metadata collision uses exact same direct Path string for input and report argv values
bundle collision uses exact same direct Path string for input and report argv values
dependency scenario writes no metadata or bundle fixture
harness does not create report parents
fresh successful runs create fresh frozen wrapper artifacts
main exception propagates unchanged without synthetic run artifact
```

Use AST or focused source checks proving the harness:

```text
imports only approved modules
does not import Phase 16A/16B helpers or exporter
does not import metadata/workflow/provider/runtime/scanner/voice/HTTP modules
does not parse JSON
does not create directories
does not inspect expected scenario fields
does not call main more than once
```

## Actual End-to-End Contract Matrix

Run all eight catalog scenarios through real harness plus actual `main(argv)` in a fresh workspace.

For every scenario, assert its expected exit code, required/forbidden terminal lines, dynamic paths, and expected report artifact contract.

Targeted assertions:

```text
valid_bundle_export_success:
  report exists
  report exactly equals terminal report without terminal print newline
  Relative Volume: 2.0x
  exit 0

returned_workflow_failure_export:
  report exists
  report exactly equals terminal report without terminal print newline
  Manifest: NO_VALID_METADATA
  Relative Volume: N/A
  exit 1

metadata_source_error_export:
  report exists
  report exactly equals terminal ERROR report without terminal print newline
  JsonHistoricalSessionMetadataFileSourceError
  UNSUPPORTED_SCHEMA_VERSION
  exit 1

bundle_input_error_export:
  report exists
  report exactly equals terminal ERROR report without terminal print newline
  JsonHistoricalRvolBundleError
  UNSUPPORTED_SCHEMA_VERSION
  exit 1

export_error_missing_parent:
  missing-parent remains absent
  report does not exist
  stdout is only the EXPORT_ERROR report category
  normal Input Mode / RVOL output absent
  both input files remain unchanged
  exit 1

bundle_report_dependency_error:
  no input files
  report path does not exist
  requires-bundle-preflight error
  exit 2

report_same_metadata_path_command_error:
  report path directly equals metadata path
  metadata and bundle files remain unchanged
  no normal Input Mode / RVOL output
  metadata-protection message
  exit 2

report_same_bundle_path_command_error:
  report path directly equals bundle path
  metadata and bundle files remain unchanged
  no normal Input Mode / RVOL output
  bundle-protection message
  exit 2
```

No test may use:

```text
network
API keys
provider activation
audio
configuration mutation
file discovery
live data
trading/order behavior
```

---

## README

Do not modify README. Phase 16C adds no user-facing command or runtime capability.

---

## Validation

Run:

```powershell
python -m pytest tests/test_local_json_bundle_preflight_report_contract_scenario_catalog.py
python -m pytest tests/test_local_json_bundle_preflight_report_contract_scenario_harness.py
python -m pytest
python -m market_sentry
python -m market_sentry --local-json-preflight .\does-not-exist.json
python -m market_sentry --local-json-preflight-report .\report.txt
python -m market_sentry --local-json-bundle-preflight .\does-not-exist-metadata.json .\does-not-exist-bundle.json
python -m market_sentry --local-json-bundle-preflight-report .\bundle-report.txt
```

Then rerun:

```text
fixture
composed_fixture
Alpaca placeholder
both live_composed placeholder checks
both readiness checks
```

No Phase 16C CLI command is added.

---

## Acceptance Criteria

Phase 16C is complete when:

```text
- exactly eight fresh named scenarios exist in required order;
- the catalog is data-only and obtains metadata bytes only through the Phase 15I public catalog;
- valid and invalid bundle bytes are constructed as fresh pure fixture data;
- the harness invokes actual main(argv) exactly once per scenario;
- success, returned workflow failure, metadata error, bundle error, export failure, dependency, and both input-collision report contracts are covered end to end;
- normal and expected-input-error reports export exactly;
- export failure emits only EXPORT_ERROR and does not create its missing parent;
- dependency and input-collision guards do not write reports;
- protected metadata/bundle input files remain unchanged after guard and export-failure paths;
- no existing command or runtime behavior changes;
- no provider, network, scanner, alert, voice, or trading behavior is added;
- the full project suite remains green.
```
