# Phase 16B — Manual Two-Path Local Bundle Preflight CLI

## Status

**Planned.** This document defines Phase 16B only.

Phase 15J provides a manual offline command for one metadata JSON path plus a fixed deterministic historical-RVOL profile. Phase 16A provides a strict loader for a separate explicit local historical RVOL bundle JSON path.

Phase 16B exposes those two caller-selected paths through a separate manual CLI branch:

```text
explicit metadata JSON path
+ explicit historical RVOL bundle JSON path
        ↓
Phase 16A bundle loader once
+ existing Phase 15H preflight once
        ↓
terminal report
+ optional exact local report export
```

This phase does not activate providers, invoke a scanner, fetch market data, use configuration, or add live market analysis.

The existing Phase 15J / 15K command remains unchanged:

```text
python -m market_sentry --local-json-preflight <METADATA_PATH>
python -m market_sentry --local-json-preflight <METADATA_PATH> --local-json-preflight-report <REPORT_PATH>
```

---

## Goal

Add a **separate**, manually invoked, offline two-input preflight command:

```text
python -m market_sentry --local-json-bundle-preflight <METADATA_PATH> <BUNDLE_PATH>
```

with optional exact report export:

```text
python -m market_sentry --local-json-bundle-preflight <METADATA_PATH> <BUNDLE_PATH> --local-json-bundle-preflight-report <REPORT_PATH>
```

The command must:

1. accept exactly two explicit input paths in fixed order: metadata first, bundle second;
2. load exactly one explicit bundle via Phase 16A;
3. run exactly one existing Phase 15H metadata workflow preflight with the bundle’s existing typed inputs;
4. render a stable diagnostic report without a fixed fixture-profile label;
5. optionally write the exact rendered report string as UTF-8 to one explicit report path;
6. preserve all existing Phase 15J / 15K behavior unchanged;
7. return:
   - `0` only for fully successful bundle load, preflight, and optional export;
   - `1` for returned non-OK workflow diagnostics, expected metadata/bundle input errors, or report-export I/O failure;
   - `2` for invalid command combinations, missing command dependencies, or direct input/report path equality;
8. never resolve, expand, discover, normalize, or otherwise rewrite caller paths;
9. never write either input path.

The command is a manual **offline diagnostics** path. It is not a scanner mode, data acquisition tool, provider activation path, or generic local-file framework.

---

## User-Facing Commands

### Existing one-path command — unchanged

```powershell
python -m market_sentry --local-json-preflight .\metadata.json

python -m market_sentry `
  --local-json-preflight .\metadata.json `
  --local-json-preflight-report .\metadata-preflight-report.txt
```

### New two-path bundle command

```powershell
python -m market_sentry `
  --local-json-bundle-preflight .\metadata.json .\historical-rvol-bundle.json
```

Optional report export:

```powershell
python -m market_sentry `
  --local-json-bundle-preflight .\metadata.json .\historical-rvol-bundle.json `
  --local-json-bundle-preflight-report .\bundle-preflight-report.txt
```

The new command:

```text
reads only the explicit metadata path and explicit bundle path
writes only the explicit report path when supplied
does not create either input
does not create report parent directories
does not discover files
does not use environment or config input
does not activate providers
does not scan candidates
does not call APIs
does not play voice alerts
```

---

## Required Files

Create:

```text
docs/63_MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_CLI.md
src/market_sentry/local_json_bundle_preflight_cli.py
src/market_sentry/local_json_bundle_preflight_report_export.py
tests/test_local_json_bundle_preflight_cli.py
tests/test_local_json_bundle_preflight_report_export.py
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
Phase 15A–15L
Phase 16A loader behavior
src/market_sentry/local_json_preflight_cli.py
src/market_sentry/local_json_preflight_report_export.py
existing Phase 15J / 15K tests
provider/config/factory/readiness modules
transport/fetcher modules
scanner modules
alert modules
voice modules
fixture scenario catalogs/harnesses
metadata JSON source behavior
workflow behavior
```

Phase 16B must preserve existing one-path command output and exit behavior byte-for-byte.

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
provider activation
new MARKET_SENTRY_PROVIDER values
HTTP requests
WebSockets
automatic metadata or bundle acquisition
file discovery
directory scanning
glob/rglob
background jobs
automatic scheduling
scanner-loop integration
alert generation
voice playback
persistent storage
environment/config reads in this command
```

No network calls are permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

# Part A — Two-Path CLI Helper

## Helper Ownership

Create `src/market_sentry/local_json_bundle_preflight_cli.py`.

It owns:

```text
one Phase 16A bundle load
one Phase 15H preflight invocation using the loaded bundle’s inputs
stable two-path report rendering
stable two-path expected-input error rendering
complete-success evaluation
exact result artifact retention
```

It does not own:

```text
JSON parsing or bundle validation
metadata source parsing/validation
workflow diagnostics
RVOL calculations
report file writes
CLI parsing
command conflicts
provider/config/scanner/voice behavior
```

---

## Allowed Helper Imports

The new helper may import only:

```text
standard library:
  dataclasses
  json
  pathlib

market_sentry.data.alpaca_historical_bars_fetcher:
  AlpacaHistoricalBarsFetchError

market_sentry.data.json_historical_rvol_bundle:
  JsonHistoricalRvolBundleError
  LocalHistoricalRvolBundle
  load_local_historical_rvol_bundle

market_sentry.data.json_historical_session_metadata_source:
  JsonHistoricalSessionMetadataFileSourceError

market_sentry.data.local_json_metadata_workflow_preflight:
  LocalJsonMetadataWorkflowPreflightResult
  run_local_json_metadata_workflow_preflight
```

Do not import:

```text
main
argparse
local_json_preflight_cli
local_json_preflight_report_export
config
provider/factory/readiness
scanner
alerts
voice
transport/fetcher clients
Phase 15I fixture catalogs/harnesses
Phase 15L catalog/harness
workflow modules below the existing Phase 15H wrapper
HTTP/network modules
```

`AlpacaHistoricalBarsFetchError` is permitted solely because Phase 16A delegates existing strict query construction and this command must render that expected local-input error rather than expose a traceback.

---

## Public Model

Provide:

```python
@dataclass(frozen=True)
class ManualLocalJsonBundlePreflightResult:
    """One explicit local bundle load plus one metadata workflow preflight."""

    metadata_path: Path
    bundle_path: Path
    bundle: LocalHistoricalRvolBundle
    preflight_result: LocalJsonMetadataWorkflowPreflightResult
```

Requirements:

```text
- retain exact caller-owned metadata_path and bundle_path objects;
- retain exact bundle object returned by Phase 16A;
- retain exact preflight result returned by Phase 15H;
- do not add raw payloads, config, provider objects, or derived market facts;
- frozen dataclass only.
```

---

## Public Functions and Constants

Provide:

```python
LOCAL_JSON_BUNDLE_PREFLIGHT_NOTE: str
```

Its exact value:

```text
Note: This command reads only the explicit local metadata JSON path and local historical RVOL bundle path. It does not activate providers, scan candidates, call APIs, or play voice alerts.
```

Provide:

```python
MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS: tuple[type[BaseException], ...]
```

It must include exactly the expected local input/file error families needed by `main.py`:

```text
OSError
UnicodeDecodeError
json.JSONDecodeError
JsonHistoricalSessionMetadataFileSourceError
JsonHistoricalRvolBundleError
AlpacaHistoricalBarsFetchError
```

Provide:

```python
def run_manual_local_json_bundle_preflight(
    metadata_path: Path,
    bundle_path: Path,
) -> ManualLocalJsonBundlePreflightResult:
    ...
```

Required sequence:

```python
bundle = load_local_historical_rvol_bundle(bundle_path)

preflight_result = run_local_json_metadata_workflow_preflight(
    metadata_path,
    bundle.collection,
    bundle.manifest_request,
    bundle.current_series,
    bundle.harness_request,
)
```

Then return one frozen `ManualLocalJsonBundlePreflightResult`.

Requirements:

```text
- call bundle loader exactly once;
- call existing Phase 15H wrapper exactly once after bundle load succeeds;
- never call Phase 15H when bundle loading raises;
- do not catch, wrap, retry, or transform exceptions;
- do not construct a metadata source directly;
- do not call a lower workflow stage directly.
```

Provide:

```python
def render_manual_local_json_bundle_preflight_report(
    metadata_path: Path,
    bundle_path: Path,
    result: ManualLocalJsonBundlePreflightResult,
) -> str:
    ...
```

Provide:

```python
def render_manual_local_json_bundle_preflight_error(
    metadata_path: Path,
    bundle_path: Path,
    error: BaseException,
) -> str:
    ...
```

Provide:

```python
def is_manual_local_json_bundle_preflight_success(
    result: ManualLocalJsonBundlePreflightResult,
) -> bool:
    ...
```

This success predicate must apply the same nested workflow success standard as Phase 15J, but it must operate on `result.preflight_result`. It must not import Phase 15J’s helper or fixed profile.

---

## Report Format

### Returned workflow report

For a normal returned workflow result, render exactly:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path: <metadata-path>
Bundle Path: <bundle-path>
Input Mode: EXPLICIT_LOCAL_BUNDLE
Metadata Load: <value or N/A>
Metadata Load Reason: <value or N/A>
Workflow: <value or N/A>
Workflow Reason: <value or N/A>
Bridge: <value or N/A>
Bridge Reason: <value or N/A>
Composition: <value or N/A>
Coordinator: <value or N/A>
Coordinator Reason: <value or N/A>
Manifest: <value or N/A>
Manifest Reason: <value or N/A>
Harness: <value or N/A>
Harness Reason: <value or N/A>
Final: <value or N/A>
Final Reason: <value or N/A>
Time-of-Day RVOL: <value or N/A>
Time-of-Day RVOL Reason: <value or N/A>
Relative Volume: <one-decimal x or N/A>
Note: This command reads only the explicit local metadata JSON path and local historical RVOL bundle path. It does not activate providers, scan candidates, call APIs, or play voice alerts.
```

Use the same nested artifact traversal and `N/A` behavior as Phase 15J. Do not add a fixed fixture profile field.

### Expected metadata/bundle input error

For any expected exception in `MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS`, render exactly:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path: <metadata-path>
Bundle Path: <bundle-path>
Result: ERROR
Error Type: <exception class name>
Error: <str(error), or class name when empty>
Note: This command reads only the explicit local metadata JSON path and local historical RVOL bundle path. It does not activate providers, scan candidates, call APIs, or play voice alerts.
```

Do not add:

```text
tracebacks
raw JSON
API keys
environment/config values
provider/scanner state
error-source inference
```

Both explicit input paths are always shown. File error messages already identify the attempted filesystem target where the operating system provides one.

---

# Part B — Dedicated Bundle Report Export Helper

## Required Module

Create:

```text
src/market_sentry/local_json_bundle_preflight_report_export.py
```

Do not modify the existing Phase 15K exporter.

## Allowed Exporter Imports

The dedicated exporter may import only:

```text
standard library:
  pathlib
```

Provide:

```python
LOCAL_JSON_BUNDLE_PREFLIGHT_EXPORT_NOTE: str
```

Its exact value equals `LOCAL_JSON_BUNDLE_PREFLIGHT_NOTE`.

Provide:

```python
def write_manual_local_json_bundle_preflight_report(
    path: Path,
    report: str,
) -> None:
    ...
```

Required implementation behavior:

```python
path.write_text(report, encoding="utf-8")
```

Requirements:

```text
- write exactly the supplied report string;
- UTF-8;
- do not append a newline;
- no read-back;
- no parent-directory creation;
- no resolve/absolute/expanduser;
- no error catching.
```

Provide:

```python
def render_manual_local_json_bundle_preflight_export_error(
    metadata_path: Path,
    bundle_path: Path,
    report_path: Path,
    error: OSError,
) -> str:
    ...
```

Exact output:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path: <metadata-path>
Bundle Path: <bundle-path>
Report Path: <report-path>
Result: EXPORT_ERROR
Error Type: <exception class name>
Error: <str(error), or class name when empty>
Note: This command reads only the explicit local metadata JSON path and local historical RVOL bundle path. It does not activate providers, scan candidates, call APIs, or play voice alerts.
```

---

# Part C — `main.py` Command Surface

## New Arguments

Add:

```text
--local-json-bundle-preflight METADATA_PATH BUNDLE_PATH
--local-json-bundle-preflight-report REPORT_PATH
```

Parse as explicit `Path` values.

The preflight argument must accept exactly two paths, in this exact order:

```text
metadata path first
bundle path second
```

No defaults, environment fallbacks, discovery, or additional bundle inputs.

Existing arguments remain unchanged.

---

## Preflight Mode Exclusivity

There are now two distinct local-preflight modes:

```text
--local-json-preflight
--local-json-bundle-preflight
```

They cannot be combined.

When both are present, return exit code `2` before file reads, report writes, config, providers, scanner, readiness, voice, or workflow work.

Render exactly:

```text
Market Sentry Local JSON Preflight
Path: N/A
Result: COMMAND_ERROR
Error: --local-json-preflight and --local-json-bundle-preflight cannot be combined
```

Do not write either optional report path.

This is a command-surface guard only; it does not change either standalone mode.

---

## Report-Flag Dependency Rules

Existing Phase 15K rule remains unchanged:

```text
--local-json-preflight-report requires --local-json-preflight
```

New Phase 16B rule:

```text
--local-json-bundle-preflight-report requires --local-json-bundle-preflight
```

For bundle report without bundle command, return exit code `2` before all work:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path: N/A
Bundle Path: N/A
Report Path: <report-path>
Result: COMMAND_ERROR
Error: --local-json-bundle-preflight-report requires --local-json-bundle-preflight
```

Do not write the requested report path.

These dependency checks deliberately reject cross-paired flags:

```text
--local-json-preflight ... --local-json-bundle-preflight-report ...
→ bundle report dependency error

--local-json-bundle-preflight ... --local-json-preflight-report ...
→ existing Phase 15K report dependency error
```

The existing one-path dependency renderer and string must remain unchanged.

Apply report-flag dependency guards before mode execution. Apply the existing one-path dependency guard first, then the new bundle-report dependency guard, then the two-mode exclusivity guard.

---

## Existing Conflict Rules for Both Local Modes

When either local-preflight mode is present, reject with exit code `2` if combined with:

```text
--loop
--live-readiness
--relative-volume-configured
--interval <non-default value>
--speak
--no-speak
```

The preflight mode’s own report flag is allowed.

For the bundle mode, preserve raw user-argument ordering exactly. This includes simultaneous explicit `--speak` and `--no-speak`: sanitize only for argparse parsing when either preflight mode is present, then render the stable local command error using raw argv ordering.

Bundle conflict output:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path: <metadata-path>
Bundle Path: <bundle-path>
Result: COMMAND_ERROR
Error: --local-json-bundle-preflight cannot be combined with: <raw ordered flags>
```

Do not write a report path on conflict.

Existing one-path conflict behavior and wording must remain unchanged.

---

## Direct Input/Report Equality Guards

For bundle mode with an output path, reject direct parsed `Path` equality before bundle load or report write:

```python
report_path == metadata_path
```

Output, exit `2`:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path: <metadata-path>
Bundle Path: <bundle-path>
Report Path: <report-path>
Result: COMMAND_ERROR
Error: --local-json-bundle-preflight-report must differ from metadata path
```

Also reject:

```python
report_path == bundle_path
```

Output, exit `2`:

```text
Market Sentry Local JSON Bundle Preflight
Metadata Path: <metadata-path>
Bundle Path: <bundle-path>
Report Path: <report-path>
Result: COMMAND_ERROR
Error: --local-json-bundle-preflight-report must differ from bundle path
```

Requirements:

```text
- direct parsed Path equality only;
- do not resolve or perform alias/symlink detection;
- do not read either input;
- do not write output;
- do not create config/provider/scanner/speaker/readiness objects.
```

The two read-only input paths are not required to differ by a command guard. If they point to the same file, Phase 16A or existing metadata behavior may determine the resulting input error.

---

## Bundle Mode Execution Flow

After all command guards succeed:

1. set default exit code to `1`;
2. call `run_manual_local_json_bundle_preflight(metadata_path, bundle_path)` exactly once;
3. on expected local error, render the bundle error report;
4. on returned result, render the normal bundle report and set exit code:
   - `0` if fully successful;
   - `1` otherwise;
5. if output path supplied:
   - write exact report first;
   - on `OSError`, print only bundle `EXPORT_ERROR` report and return `1`;
6. only after successful optional export, print normal/error report;
7. return exit code.

The normal report must be rendered once and reused for write/print. Do not run helper or renderer twice. Do not read report back.

No config/provider/scanner/alert/voice behavior may execute on this branch.

---

## Source Boundaries in `main.py`

`main.py` may import the new helper’s public functions/constants and new dedicated exporter’s public functions.

Do not use the new bundle branch to alter:

```text
default mock scan
fixture mode
composed fixture mode
Alpaca placeholder
live_composed gates
live-readiness
existing one-path local preflight
existing one-path report export
```

---

# Part D — Required Tests

## New helper tests

Create:

```text
tests/test_local_json_bundle_preflight_cli.py
```

Test:

```text
helper calls Phase 16A bundle loader exactly once;
helper calls Phase 15H wrapper exactly once after successful load;
helper passes the exact loaded bundle input objects to Phase 15H;
helper retains exact path, bundle, and preflight-result references;
bundle-loader failure propagates unchanged and prevents Phase 15H call;
Phase 15H failure propagates unchanged;
returned workflow report formatting has exact line order, no fixed profile label,
and correct RVOL formatting;
error report formatting is stable and safe;
success predicate accepts only complete nested success;
valid actual metadata + valid actual bundle reaches RVOL 2.0;
invalid current bundle volume false reaches existing downstream
CURRENT_CUMULATIVE_VOLUME_FAILED / INVALID_INTRADAY_VOLUME;
helper source boundary imports only approved modules;
helper does not import Phase 15I fixtures, old CLI helper, main, config/provider,
scanner, voice, HTTP, network, or lower workflow stages.
```

## New export helper tests

Create:

```text
tests/test_local_json_bundle_preflight_report_export.py
```

Test:

```text
exact UTF-8 write with no appended newline;
exact path/report forwarded once;
missing parent raises FileNotFoundError and is not created;
stable export-error output and empty-message fallback;
AST/source boundary: pathlib only, write_text allowed, no reads/mkdir/resolve/etc.
```

## `main.py` tests

Modify `tests/test_main.py`.

Test parsing:

```text
new two-path argument parses exactly two Path objects in metadata/bundle order;
new report path parses as Path;
existing argument defaults and old parsing remain unchanged.
```

Test command guards:

```text
bundle report without bundle command → exit 2, stable dependency report, no write;
old report flag with bundle command → existing old dependency error, no work;
bundle report flag with old command → bundle dependency error, no work;
old and bundle commands together → exit 2, stable exclusivity error, no work;
bundle conflicts preserve raw ordering;
bundle with simultaneous --speak and --no-speak reaches stable command error;
bundle default interval remains allowed;
bundle non-default --interval conflicts;
report equals metadata path → exit 2, no read/write;
report equals bundle path → exit 2, no read/write.
```

Test main execution using monkeypatches of direct symbols in `main.py`:

```text
complete result → exit 0, normal report, no runtime work;
returned non-OK → exit 1, nested diagnostics;
expected input exception → exit 1, stable ERROR report;
successful export writes exact report and stdout is report plus terminal newline;
returned non-OK export writes exact report;
expected input error export writes exact error report;
report write OSError prints only EXPORT_ERROR and returns 1;
no config/provider/scanner/voice execution on every bundle branch.
```

Test actual end-to-end command calls:

```text
real valid metadata fixture + real valid bundle → exit 0, no provider activation;
same inputs + report output → exact output bytes equal terminal report sans final print newline;
real invalid bundle schema → exit 1, Result: ERROR, JsonHistoricalRvolBundleError,
UNSUPPORTED_SCHEMA_VERSION;
real metadata unsupported schema + real valid bundle → exit 1, Result: ERROR,
JsonHistoricalSessionMetadataFileSourceError, UNSUPPORTED_SCHEMA_VERSION;
missing report parent → exit 1, only EXPORT_ERROR, no parent created;
invalid current bundle volume false → exit 1 with existing downstream
CURRENT_CUMULATIVE_VOLUME_FAILED and INVALID_INTRADAY_VOLUME diagnostics.
```

Do not modify existing Phase 15J / 15K tests.

---

## README

Add a concise user-facing section directly after the existing one-path local JSON preflight/report-export section.

Document:

```text
new two-path command
optional two-path report export
metadata path first, bundle path second
explicit paths only
offline diagnostics only
no parent-directory creation
use report path distinct from both input paths
no provider activation, scans, APIs, or voice alerts
no live analysis or trading behavior
```

Do not overstate that the command fetches or validates live data. It validates only caller-provided local files through the existing offline workflow.

---

## Validation

Run:

```powershell
python -m pytest tests/test_local_json_bundle_preflight_cli.py
python -m pytest tests/test_local_json_bundle_preflight_report_export.py
python -m pytest tests/test_main.py
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

No network calls are permitted.

---

## Acceptance Criteria

Phase 16B is complete when:

```text
- a separate explicit two-path command exists;
- metadata path is first and bundle path is second;
- bundle loader runs once and existing Phase 15H runs once after successful load;
- no fixed Phase 15I profile is used;
- returned workflow diagnostics render through a stable bundle-mode report;
- expected bundle/metadata input errors render safely without tracebacks;
- optional output contains exactly the report string printed to terminal;
- output paths cannot directly equal either bundle-mode input path;
- existing one-path preflight/report behavior remains unchanged;
- all conflict/dependency branches avoid file reads, report writes, config, providers,
  scanner, alerts, and voice;
- no live/provider/network/trading behavior changes;
- full project suite remains green.
```
