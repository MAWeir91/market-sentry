# Phase 15J — Manual Local JSON Preflight CLI Command

## Status

**Planned.** This document defines Phase 15J only.

Phase 15H runs one explicit local JSON file path through the existing metadata-loaded historical workflow. Phase 15I provides deterministic fixture inputs for that workflow.

Phase 15J adds one deliberately narrow command:

```text
python -m market_sentry --local-json-preflight <PATH>
```

The command reads **only** the caller-supplied local JSON file path, uses the existing deterministic Phase 15I valid-profile inputs as the explicit non-file workflow inputs, runs Phase 15H once, and prints the already-owned nested diagnostics.

It is a manual offline inspection command. It is not a live data command, provider mode, scanner run, file discovery feature, or trading tool.

---

## Goal

Add a standalone CLI operation that:

1. accepts exactly one explicit caller-supplied JSON file path;
2. constructs the existing deterministic valid Phase 15I input profile only for:
   - historical page collection;
   - manifest request;
   - current intraday series;
   - historical TOD-RVOL harness request;
3. passes the caller path and those exact profile inputs to Phase 15H exactly once;
4. prints a stable, human-readable report of existing nested diagnostics;
5. returns:
   - exit code `0` only for a complete end-to-end `OK` result;
   - exit code `1` for source/file/envelope errors or any returned incomplete/failed workflow branch;
   - exit code `2` for an invalid command combination;
6. does not write, modify, discover, resolve, expand, or otherwise alter the caller path;
7. does not load app configuration, create a provider, build a transport, scan candidates, run alerts, or speak audio.

The command’s fixed input profile is intentionally explicit and bounded:

```text
profile scenario: valid_json_complete_multi_page
symbol: RVOL
bucket: 09:35
current session: CURRENT-001
historical bars: deterministic offline two-page collection
current selected volume: 200
```

The JSON file path is the only user-supplied external input. The fixed profile makes this a reproducible local-file preflight, **not** a generic live or real-market analysis command.

---

## User-Facing Command

The only new command is:

```text
python -m market_sentry --local-json-preflight <PATH>
```

Examples:

```powershell
python -m market_sentry --local-json-preflight .\metadata.json
python -m market_sentry --local-json-preflight C:\market-sentry\fixtures\metadata.json
```

The argument must be parsed as a `pathlib.Path` without:

```text
resolve()
absolute()
expanduser()
environment expansion
glob()
rglob()
directory scan
fallback-path selection
automatic fixture creation
file writing
```

The file must already exist. This phase does not provide a CLI scenario writer. Phase 15I remains the test-only fixture-materialization utility.

---

## Command Exclusivity

`--local-json-preflight` is a standalone operation.

Reject with exit code `2` and a stable user-facing command error if it is combined with any of:

```text
--loop
--live-readiness
--relative-volume-configured
--interval <non-default value>
--speak
--no-speak
```

The error message must be secret-safe and identify the incompatible option(s). The command must not:

```text
construct a JSON source
run Phase 15H
load configuration
create a provider
scan candidates
invoke a speaker
```

when the command combination is invalid.

Existing scanner, loop, voice, and readiness argument behavior must remain unchanged when `--local-json-preflight` is absent.

---

## Required Files

Create:

```text
docs/59_MANUAL_LOCAL_JSON_PREFLIGHT_CLI.md
src/market_sentry/local_json_preflight_cli.py
tests/test_local_json_preflight_cli.py
```

Modify:

```text
src/market_sentry/main.py
tests/test_main.py
README.md
```

Do not modify:

```text
Phase 14A–14K
Phase 15A–15I
provider/config/factory/readiness modules
transport/fetcher modules
scanner modules
alert modules
voice modules
fixture modules
JSON source behavior
workflow behavior
scenario catalog behavior
```

---

## Ownership Boundary

```text
Phase 15G owns:
  explicit file read
  strict UTF-8 JSON parsing
  versioned envelope validation
  generic $datetime decoding

Phase 15D–15E and lower stages own:
  metadata load diagnostics
  composition diagnostics
  manifest diagnostics
  baseline/current/TOD-RVOL diagnostics

Phase 15H owns:
  JSON source construction
  one metadata-loaded workflow call
  exact nested artifact retention

Phase 15I owns:
  deterministic valid profile fixture construction

Phase 15J CLI helper owns:
  retrieving the fixed valid profile inputs
  one Phase 15H invocation
  stable terminal report formatting
  evaluating whether the returned nested result is completely OK

main.py owns:
  argument parsing
  standalone-command validation
  terminal printing
  exit code selection
```

Phase 15J must never:

```text
parse JSON
decode datetime tags
validate metadata records
inspect raw JSON mappings
mutate metadata payloads
write a file
create a fixture file
call Phase 15D, 15E, 15C, 15B, 14J, or lower stages directly
call the Phase 15I fixture harness
call source.load_raw_manifest_records directly
create provider/config/transport objects
call scanner/alert/voice code
call any HTTP/network client
perform market-session inference
perform RVOL calculations
change existing statuses, reasons, or nested artifacts
```

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
file discovery
environment/config input for this command
scanner-loop integration
alert generation
voice playback
persistent storage
```

`live_composed` remains gated and reserved/inactive.

No network calls are permitted in tests.

---

# Part A — CLI Helper Module

## Allowed Imports

`src/market_sentry/local_json_preflight_cli.py` may import only:

```text
standard library:
  json
  pathlib

market_sentry.data.json_historical_session_metadata_source:
  JsonHistoricalSessionMetadataFileSourceError

market_sentry.data.local_json_metadata_preflight_scenario_catalog:
  get_local_json_metadata_preflight_scenario

market_sentry.data.local_json_metadata_workflow_preflight:
  LocalJsonMetadataWorkflowPreflightResult
  run_local_json_metadata_workflow_preflight
```

Do not import:

```text
main
argparse
config
provider/factory/readiness
scanner
alerts
voice
transport/fetcher
Phase 15I harness
Phase 15G source model
Phase 15D / 15E / 15C / 15B / 14J or lower-stage modules
```

The helper must obtain all non-file workflow inputs only from:

```python
get_local_json_metadata_preflight_scenario(
    "valid_json_complete_multi_page"
)
```

It must not inspect or use that scenario’s `fixture_bytes`.

---

## Public Helper Functions

Provide:

```python
def run_manual_local_json_preflight(
    path: Path,
) -> LocalJsonMetadataWorkflowPreflightResult:
    """Run one caller-supplied path through the fixed offline valid profile."""
```

Required behavior:

```python
scenario = get_local_json_metadata_preflight_scenario(
    "valid_json_complete_multi_page"
)

return run_local_json_metadata_workflow_preflight(
    path,
    scenario.collection,
    scenario.manifest_request,
    scenario.current_series,
    scenario.harness_request,
)
```

Requirements:

```text
- get exactly one fresh valid-profile scenario;
- call Phase 15H exactly once;
- forward exact path and scenario inputs by identity;
- never write fixture bytes;
- never read from the path directly;
- never inspect result fields;
- never catch, wrap, retry, or transform exceptions;
- no cache or shared mutable state.
```

Provide:

```python
def render_manual_local_json_preflight_report(
    path: Path,
    result: LocalJsonMetadataWorkflowPreflightResult,
) -> str:
    """Render existing nested diagnostics without changing them."""
```

Provide:

```python
def render_manual_local_json_preflight_error(
    path: Path,
    error: BaseException,
) -> str:
    """Render a secret-safe expected local-file failure."""
```

Provide:

```python
def is_manual_local_json_preflight_success(
    result: LocalJsonMetadataWorkflowPreflightResult,
) -> bool:
    """Return true only for the fully successful existing nested path."""
```

These functions must only read already-produced result fields. They must not call workflow functions or modify artifacts.

---

## Stable Success Report

For a returned result, report must begin exactly:

```text
Market Sentry Local JSON Preflight
Path: <caller-path>
Profile: valid_json_complete_multi_page
```

Then report these values in this exact order:

```text
Metadata Load: <status>
Metadata Load Reason: <reason-or-N/A>
Workflow: <status>
Workflow Reason: <reason-or-N/A>
Bridge: <status-or-N/A>
Bridge Reason: <reason-or-N/A>
Composition: <status-or-N/A>
Coordinator: <status-or-N/A>
Coordinator Reason: <reason-or-N/A>
Manifest: <status-or-N/A>
Manifest Reason: <reason-or-N/A>
Harness: <status-or-N/A>
Harness Reason: <reason-or-N/A>
Final: <status-or-N/A>
Final Reason: <reason-or-N/A>
Time-of-Day RVOL: <status-or-N/A>
Time-of-Day RVOL Reason: <reason-or-N/A>
Relative Volume: <formatted-number-or-N/A>
```

Then append exactly:

```text
Note: This command reads only the explicit local JSON path. It does not activate providers, scan candidates, call APIs, or play voice alerts.
```

Formatting rules:

```text
- reason None renders N/A;
- absent nested artifact renders N/A;
- relative volume None renders N/A;
- otherwise relative volume renders one decimal followed by x, for example 2.0x;
- do not suppress non-OK nested diagnostics;
- do not add a new domain status or reclassify existing statuses;
- do not print raw metadata records, API keys, environment variables, or secrets.
```

A valid end-to-end run must visibly include:

```text
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

A returned non-OK branch must still render every available existing nested diagnostic and `N/A` for unreachable artifacts.

---

## Stable Expected-Error Report

Expected local source/file errors must render:

```text
Market Sentry Local JSON Preflight
Path: <caller-path>
Result: ERROR
Error Type: <exception-class-name>
Error: <exception-string-or-exception-class-name-if-empty>
Note: This command reads only the explicit local JSON path. It does not activate providers, scan candidates, call APIs, or play voice alerts.
```

`render_manual_local_json_preflight_error(...)` must be secret-safe and not include:

```text
environment values
API keys
provider labels
stack traces
raw JSON payload content
```

It may include the explicit caller path and source exception message.

---

## Expected Exception Boundary

The helper catches nothing.

`main.py` may catch only these expected local-file/source exceptions for rendering:

```text
OSError
UnicodeDecodeError
json.JSONDecodeError
JsonHistoricalSessionMetadataFileSourceError
```

Unexpected programming errors and unexpected lower-stage exceptions must not be caught or remapped by this phase.

---

## Full-Success Predicate

`is_manual_local_json_preflight_success(...)` must return `True` only when all reachable final success conditions are true:

```text
metadata load status = LOADED
outer workflow status = WORKFLOW_BRIDGE_RAN
bridge exists and bridge status = WORKFLOW_RAN
composition status = COMPOSED
coordinator exists and status = OK
manifest status = OK
harness status = OK
final status = OK
time-of-day RVOL result exists and status = OK
relative volume is not None
```

It returns `False` for:

```text
partial manifest
invalid cutoff tag
empty records
non-composable collection
invalid manifest request
invalid current volume
any other returned non-OK branch
```

Use existing string status values only. Do not import lower-stage status containers solely for the predicate.

---

# Part B — main.py Integration

## Parser

Add:

```text
--local-json-preflight PATH
```

The parsed value must be `Path` when provided and `None` when absent.

Preserve all current default parsing behavior, including:

```text
loop default
interval default
speak default
live readiness default
relative-volume-configured default
```

## Dispatch Order

In `main(...)`:

1. parse args;
2. reject invalid local-preflight flag combinations before any config/provider/source/preflight work;
3. when `--local-json-preflight` is present:
   - call `run_manual_local_json_preflight(path)` exactly once;
   - on returned result, print success report and return `0` or `1` using the full-success predicate;
   - on an expected local source/file error, print expected-error report and return `1`;
   - do not call `load_config`, `create_market_data_provider`, scanner, alerts, speaker, or readiness;
4. when local preflight is absent, preserve all existing readiness/provider/scanner behavior.

## Invalid-Combination Message

Use a stable command error format:

```text
Market Sentry Local JSON Preflight
Path: <caller-path>
Result: COMMAND_ERROR
Error: --local-json-preflight cannot be combined with: <comma-separated-options>
```

Return `2`.

List conflicting options in the order they appear in the user command.

Do not run Phase 15H or load configuration for command-error paths.

---

# Part C — Tests

## New Helper Tests

Create `tests/test_local_json_preflight_cli.py`.

Monkeypatch only direct public helper dependencies where applicable:

```text
get_local_json_metadata_preflight_scenario
run_local_json_metadata_workflow_preflight
```

Verify:

```text
valid profile looked up exactly once by exact name
Phase 15H called exactly once
caller Path forwarded by identity
scenario collection/request/current/harness inputs forwarded by identity
fixture_bytes is not read or written
returned Phase 15H result retained exactly
fresh helper calls invoke fresh catalog retrieval and preflight each time
exceptions propagate unchanged from helper
```

Test formatter output for:

```text
fully successful result
partial manifest result
non-composable collection result
expected file/source error
N/A behavior for missing nested artifacts
one-decimal RVOL formatting
required note
no secret/environment/provider content
```

Test full-success predicate:

```text
true only for complete final OK result
false for partial manifest, failed final, missing bridge/coordinator/TOD result,
or relative volume None
```

Add AST/source-boundary checks proving the helper:

```text
imports only approved modules
does not import main/config/providers/scanner/alerts/voice/HTTP/transports
does not import the Phase 15I harness
does not write files
does not parse JSON
does not call lower stages directly
does not call source.load_raw_manifest_records
```

## main.py Tests

Modify `tests/test_main.py` only as needed.

Test parser behavior:

```text
--local-json-preflight path → Path value
no flag → None
existing defaults unchanged
```

Test local command dispatch:

```text
successful result:
  prints full report
  returns 0
  does not load config
  does not create provider
  does not scan candidates
  does not invoke speaker

returned partial/failure result:
  prints existing nested diagnostics
  returns 1
  does not load config/provider/scanner/speaker

expected FileNotFoundError:
  prints ERROR report
  returns 1
  does not load config/provider/scanner/speaker

expected JsonHistoricalSessionMetadataFileSourceError:
  prints ERROR report with class/message
  returns 1
  does not load config/provider/scanner/speaker

invalid combination:
  prints COMMAND_ERROR
  returns 2
  does not call helper
  does not load config/provider/scanner/speaker
```

Test actual end-to-end CLI behavior with a temp JSON path:

```text
valid local JSON file from the Phase 15I valid scenario bytes
→ main(["--local-json-preflight", str(path)])
→ return 0
→ report includes final RVOL 2.0
→ no provider creation

unsupported schema file
→ return 1
→ report includes ERROR, JsonHistoricalSessionMetadataFileSourceError,
  and UNSUPPORTED_SCHEMA_VERSION

missing path
→ return 1
→ report includes ERROR and FileNotFoundError
```

No test may use real API keys, network, provider activation, audio, or file discovery.

---

## README

Add a concise section documenting:

```text
Manual Local JSON Preflight
python -m market_sentry --local-json-preflight <PATH>

This reads only the explicit local JSON file path and runs it through a fixed offline RVOL diagnostic profile.
It does not discover files, activate providers, scan candidates, call APIs, or play voice alerts.
It returns 0 only for a complete end-to-end OK result; returned nested diagnostics or expected source errors return nonzero.
The command is not live market analysis and does not execute trades.
```

Do not add any provider setup, credential, or live-data instructions.

---

## Validation

Run:

```powershell
python -m pytest tests/test_local_json_preflight_cli.py
python -m pytest tests/test_main.py
python -m pytest
python -m market_sentry
python -m market_sentry --local-json-preflight .\does-not-exist.json
```

Then rerun:

```text
fixture
composed_fixture
Alpaca placeholder
both live_composed placeholder checks
both readiness checks
```

Also manually verify:

```powershell
# use a known valid local Phase 15I fixture JSON path
python -m market_sentry --local-json-preflight .\path\to\valid_metadata.json
```

Expected:

```text
exit 0
final RVOL 2.0x
no provider creation
no API calls
no voice playback
```

Do not commit.
Do not push.

---

## Acceptance Criteria

Phase 15J is complete when:

```text
- exactly one explicit local JSON CLI command exists;
- the command reads only the caller path and never writes or discovers files;
- fixed deterministic offline profile inputs come only from Phase 15I valid scenario construction;
- Phase 15H is called exactly once;
- the command reports all already-owned reachable nested diagnostics in stable order;
- valid end-to-end data exits 0 with RVOL 2.0x;
- returned partial/failed diagnostics and expected source exceptions exit nonzero without being reclassified;
- invalid command combinations exit 2 before source/config/provider/scanner work;
- existing scanner, readiness, fixture, provider gate, and voice behavior remain unchanged when the new flag is absent;
- no live data, network, provider activation, scanner, alert, voice, or trading behavior is added;
- the full project suite remains green.
```
