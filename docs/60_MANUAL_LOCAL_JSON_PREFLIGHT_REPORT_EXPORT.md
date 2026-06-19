# Phase 15K — Manual Local JSON Preflight Report Export

## Status

**Planned.** This document defines Phase 15K only.

Phase 15J provides a manual offline command that reads one explicit local JSON metadata file, runs the fixed deterministic preflight profile, prints existing nested diagnostics, and returns a status code.

Phase 15K adds one optional explicit report-output argument:

```text
python -m market_sentry --local-json-preflight <INPUT_PATH> --local-json-preflight-report <OUTPUT_PATH>
```

The command must write the **exact same rendered report string** that it would print to the terminal into the one caller-selected output path, in UTF-8, after preflight has completed.

It does not change any JSON-source, metadata, workflow, diagnostic, provider, scanner, alert, voice, network, or trading behavior.

---

## Goal

Add an optional manual report-export path that:

1. accepts one explicit preflight input path and one explicit report output path;
2. runs the existing Phase 15J preflight branch exactly once;
3. renders the existing success, returned non-OK, or expected local-source error report exactly once;
4. writes that exact rendered report string as UTF-8 to the exact caller-supplied output path;
5. prints that same rendered report only after the export write succeeds;
6. leaves existing no-export Phase 15J command behavior unchanged;
7. returns:
   - `0` only for a fully successful preflight and successful optional export;
   - `1` for returned non-OK preflight results, expected source/file errors, or report-export I/O failure;
   - `2` for invalid local-preflight command combinations or invalid report-output usage;
8. never resolves, expands, discovers, normalizes, or otherwise rewrites either caller path;
9. never writes the input JSON path when the direct parsed input/output `Path` values compare equal.

The report output is an optional local text artifact. It is not a database, cache, log rotation system, background job, provider activation, or generic export framework.

---

## User-Facing Commands

Existing no-export command remains unchanged:

```text
python -m market_sentry --local-json-preflight <INPUT_PATH>
```

New optional export form:

```text
python -m market_sentry --local-json-preflight <INPUT_PATH> --local-json-preflight-report <OUTPUT_PATH>
```

Examples:

```powershell
python -m market_sentry --local-json-preflight .\metadata.json

python -m market_sentry `
  --local-json-preflight .\metadata.json `
  --local-json-preflight-report .\metadata-preflight-report.txt
```

The command:

```text
reads only INPUT_PATH
writes only OUTPUT_PATH when the optional export argument is supplied
does not create INPUT_PATH
does not create parent directories for OUTPUT_PATH
does not scan or discover files
does not create scenario fixture files
```

`OUTPUT_PATH` is exact caller input. Do not call:

```text
resolve()
absolute()
expanduser()
glob()
rglob()
environment expansion
parent.mkdir()
directory scanning
fallback-path selection
timestamped file naming
path normalization
```

The output file content must equal the exact report string returned by the Phase 15J report renderer, encoded as UTF-8:

```python
output_path.read_text(encoding="utf-8") == rendered_report
```

Do not append a newline, header, timestamp, environment information, or any additional export-only content.

---

## Direct Same-Path Guard

Before running preflight or attempting export, reject direct parsed-path equality:

```python
input_path == output_path
```

with exit code `2`.

Use this stable output:

```text
Market Sentry Local JSON Preflight
Path: <input-path>
Report Path: <output-path>
Result: COMMAND_ERROR
Error: --local-json-preflight-report must differ from --local-json-preflight
```

Requirements:

```text
- do not run Phase 15H;
- do not read input;
- do not write output;
- do not load config;
- do not create provider/scanner/speaker/readiness objects;
- do not call resolve or perform alias detection.
```

Because this phase deliberately does not resolve paths, it prevents only direct `Path` equality. The caller must provide distinct paths and is responsible for avoiding filesystem aliases such as symlinks or alternate lexical spellings that refer to the same target.

---

## Report-Argument Dependency Guard

`--local-json-preflight-report` is valid only when `--local-json-preflight` is also present.

For:

```text
python -m market_sentry --local-json-preflight-report .\report.txt
```

return exit code `2` before config/provider/scanner/readiness/preflight/export work.

Use this stable output:

```text
Market Sentry Local JSON Preflight
Path: N/A
Report Path: <output-path>
Result: COMMAND_ERROR
Error: --local-json-preflight-report requires --local-json-preflight
```

Do not write the requested output path on this command-error path.

---

## Existing Local-Preflight Command Exclusivity

Phase 15J command exclusivity remains in force.

When `--local-json-preflight` is present, reject with exit code `2` if combined with:

```text
--loop
--live-readiness
--relative-volume-configured
--interval <non-default value>
--speak
--no-speak
```

The optional `--local-json-preflight-report` flag itself is allowed with local preflight.

Existing behavior when `--local-json-preflight` is absent must remain unchanged.

For local-preflight conflicts, preserve raw user-command ordering exactly. This includes the existing special handling for explicit simultaneous `--speak` and `--no-speak`, which must still reach the stable local command-error renderer rather than argparse’s generic mutual-exclusion failure.

When an output path was supplied on a local-preflight conflict, do not write it.

---

## Required Files

Create:

```text
docs/60_MANUAL_LOCAL_JSON_PREFLIGHT_REPORT_EXPORT.md
src/market_sentry/local_json_preflight_report_export.py
tests/test_local_json_preflight_report_export.py
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
Phase 15A–15J
provider/config/factory/readiness modules
transport/fetcher modules
scanner modules
alert modules
voice modules
fixture modules
JSON source behavior
metadata workflow behavior
scenario catalog/harness behavior
local_json_preflight_cli.py
```

Phase 15K must reuse the Phase 15J rendered report strings rather than duplicating report formatting.

---

## Ownership Boundary

```text
Phase 15G owns:
  explicit JSON file read
  strict UTF-8 JSON parsing
  envelope validation
  generic $datetime decoding

Phase 15D–15E and lower stages own:
  metadata, composition, manifest, baseline, current-volume, and TOD-RVOL diagnostics

Phase 15H owns:
  source construction
  one metadata-loaded workflow call
  exact nested artifact retention

Phase 15I owns:
  deterministic fixed-profile fixture construction

Phase 15J owns:
  fixed-profile preflight invocation
  preflight report rendering
  preflight source-error rendering
  complete-success evaluation

Phase 15K export helper owns:
  writing one already-rendered report string to one explicit output Path
  export-I/O error report rendering only

main.py owns:
  argument parsing
  local command validation
  calling Phase 15J
  optional Phase 15K write after rendering
  stdout output and exit-code selection
```

Phase 15K must not:

```text
parse JSON
decode datetimes
validate metadata
inspect raw JSON mappings
inspect nested workflow result fields
re-render or duplicate Phase 15J preflight reports
call Phase 15G, 15D, 15E, 15C, 15B, 14J, or lower stages directly
call Phase 15I fixture harness
call source.load_raw_manifest_records
build providers, transports, scanner, alert, or voice objects
read output files after writing
create parent directories
load configuration
make HTTP/network calls
perform market-session inference
alter RVOL calculations
change statuses/reasons/artifacts
add order/trading behavior
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
automatic report scheduling
file discovery
directory scanning
log rotation
persistent database storage
scanner-loop integration
alert generation
voice playback
```

`live_composed` remains gated and reserved/inactive.

No network calls are permitted in tests.

---

# Part A — Export Helper Module

## Allowed Imports

`src/market_sentry/local_json_preflight_report_export.py` may import only:

```text
standard library:
  pathlib
```

It must not import:

```text
main
argparse
json
config
provider/factory/readiness
scanner
alerts
voice
transport/fetcher
local_json_preflight_cli
Phase 15I catalog or harness
Phase 15G source model
Phase 15D/15E/15C/15B/14J or lower-stage modules
```

## Public Functions

Provide:

```python
def write_manual_local_json_preflight_report(
    path: Path,
    report: str,
) -> None:
    """Write one already-rendered report verbatim as UTF-8."""
```

Required implementation behavior:

```python
path.write_text(report, encoding="utf-8")
```

Requirements:

```text
- exactly one write_text call;
- exact caller Path object receives the write;
- exact report string is forwarded unchanged;
- encoding is exactly UTF-8;
- no newline is appended;
- no path modification;
- no parent-directory creation;
- no read-back;
- no validation, parsing, or result inspection;
- no exception catching, wrapping, retrying, or transformation;
- no cache/global state.
```

Provide:

```python
def render_manual_local_json_preflight_export_error(
    input_path: Path,
    report_path: Path,
    error: OSError,
) -> str:
    """Render a secret-safe export-I/O failure report."""
```

Exact format:

```text
Market Sentry Local JSON Preflight
Path: <input-path>
Report Path: <output-path>
Result: EXPORT_ERROR
Error Type: <exception-class-name>
Error: <exception-string-or-exception-class-name-if-empty>
Note: This command reads only the explicit local JSON path. It does not activate providers, scan candidates, call APIs, or play voice alerts.
```

Requirements:

```text
- no stack trace;
- no raw JSON content;
- no environment variables;
- no API keys;
- no provider labels/configuration;
- explicit input/output paths are allowed;
- does not inspect or change any preflight artifact.
```

---

# Part B — main.py Integration

## Parser

Add:

```text
--local-json-preflight-report PATH
```

The parsed value must be `Path` when supplied and `None` when absent.

Preserve every existing default:

```text
loop default
interval default
speak default
live readiness default
relative-volume-configured default
local-json-preflight default
```

## Dispatch Order

At the beginning of `main(...)`:

1. materialize raw argv once, as Phase 15J already does;
2. preserve Phase 15J’s voice-flag sanitization only for local preflight paths;
3. parse arguments;
4. if report-output is present but input preflight is absent:
   - print the stable dependency command error;
   - return `2`;
5. if input preflight is present:
   - evaluate existing local-preflight conflicts from original raw argv;
   - if conflicts exist, print stable command error and return `2`;
   - if output path is present and direct parsed input/output `Path` values compare equal:
     - print stable same-path command error;
     - return `2`;
   - run Phase 15J preflight exactly once;
   - render exactly one Phase 15J returned-result report or Phase 15J expected-source-error report;
   - when output path is absent:
     - print the rendered report;
     - return existing Phase 15J `0` or `1`;
   - when output path is present:
     - call Phase 15K export helper exactly once with exact output path and exact report string;
     - only after write success, print the same report string;
     - return Phase 15J’s `0` or `1`;
   - on export `OSError`:
     - print Phase 15K export-error report;
     - return `1`;
6. when local preflight and report-output are absent:
   - preserve existing readiness/provider/scanner behavior exactly.

## Expected Exception Boundary

`main.py` may catch only:

```text
During Phase 15J preflight:
  OSError
  UnicodeDecodeError
  json.JSONDecodeError
  JsonHistoricalSessionMetadataFileSourceError

During Phase 15K report output:
  OSError
```

Expected source errors must still render through Phase 15J’s existing error renderer. When an output path is supplied, the exact source-error report is eligible for normal export just like any returned result report.

Unexpected lower-stage and programming exceptions must not be caught or remapped.

---

## Report and Export Semantics

### Successful preflight, no output flag

Preserve Phase 15J behavior exactly:

```text
print existing returned-result report
return 0
```

### Returned non-OK preflight, no output flag

Preserve Phase 15J behavior exactly:

```text
print existing nested report
return 1
```

### Expected source/file error, no output flag

Preserve Phase 15J behavior exactly:

```text
print existing ERROR report
return 1
```

### Any normal rendered report with output flag

For a full success, returned non-OK branch, or expected source/file error:

```text
render report once
write exact report string to output path
print exact same report string
return existing 0 or 1
```

### Output I/O failure

For an export write failure:

```text
do not print normal preflight report
print only EXPORT_ERROR report
return 1
```

Do not retry, create parent directories, substitute a path, or print a traceback.

---

# Part C — Tests

## Export Helper Tests

Create:

```text
tests/test_local_json_preflight_report_export.py
```

Test:

```text
writes exact report content to a temp output path
uses UTF-8 and does not append newline
forwards exact Path and exact report string to Path.write_text once
does not create parent directories
missing parent raises unchanged FileNotFoundError
rendered export error uses exact field order
empty exception string falls back to class name
export error does not include environment values, API keys, provider labels,
raw JSON content, or a stack trace
```

Use AST/focused source checks proving:

```text
only pathlib is imported
no imports of main, config, provider, scanner, alerts, voice, HTTP, transport,
Phase 15J helper, catalog/harness, or data/workflow modules
no output read-back
no directory creation
no cache/global registry
```

## main.py Tests

Modify `tests/test_main.py`.

### Parser/default tests

Verify:

```text
--local-json-preflight-report path parses to Path
absence remains None
all existing defaults remain unchanged
```

### Dependency and same-path command errors

Test:

```text
--local-json-preflight-report report.txt
→ exit 2
→ exact dependency command-error output
→ no preflight/export/config/provider/scanner/readiness/speaker work
→ report file does not exist

--local-json-preflight input.json --local-json-preflight-report input.json
→ exit 2
→ exact same-path command-error output
→ no preflight/export/config/provider/scanner/readiness/speaker work
→ input file remains untouched
```

### Existing conflict behavior

Test:

```text
--local-json-preflight input.json --local-json-preflight-report report.txt --loop
→ exit 2
→ local conflict output
→ no export write
→ no report file created

--no-speak --local-json-preflight input.json --local-json-preflight-report report.txt --loop --speak
→ exit 2
→ conflict list remains --no-speak, --loop, --speak
→ no export write
```

### Export success and non-OK paths

Monkeypatch Phase 15J helper functions and Phase 15K writer as direct main-module dependencies where appropriate. Verify:

```text
full success:
  preflight called once
  report rendered once
  writer called once with exact output Path and report string
  stdout exact report
  exit 0
  no config/provider/scanner/readiness/speaker work

returned non-OK:
  writer still called once with exact nested report
  stdout exact report
  exit 1
  no config/provider/scanner/readiness/speaker work

expected source error:
  error report rendered once
  writer called once with exact error report
  stdout exact error report
  exit 1
  no config/provider/scanner/readiness/speaker work
```

### Export failure

Test:

```text
writer raises OSError("disk unavailable")
→ stdout only EXPORT_ERROR report
→ no normal report text
→ exit 1
→ no config/provider/scanner/readiness/speaker work
```

### Actual end-to-end CLI tests

Using `tmp_path` and Phase 15I fixture bytes:

```text
valid JSON input + separate output
→ exit 0
→ stdout includes Relative Volume: 2.0x
→ output exists
→ output text equals stdout stripped of final print newline
→ no provider creation

unsupported-schema JSON input + separate output
→ exit 1
→ stdout ERROR report includes UNSUPPORTED_SCHEMA_VERSION
→ output text equals stdout stripped of final print newline

missing input + separate output
→ exit 1
→ stdout ERROR report includes FileNotFoundError
→ output text equals stdout stripped of final print newline

valid JSON input + output under missing parent
→ exit 1
→ stdout EXPORT_ERROR report
→ no output file
→ input file unchanged
```

No test may use API keys, network, provider activation, audio, or file discovery.

---

## README

Extend the existing manual local preflight section with:

```text
Optional local report export:

python -m market_sentry --local-json-preflight <INPUT_PATH> --local-json-preflight-report <OUTPUT_PATH>

The optional output path receives the exact same UTF-8 report shown in the terminal.
The command reads only INPUT_PATH and writes only OUTPUT_PATH. It does not create parent directories, discover files, activate providers, scan candidates, call APIs, or play voice alerts.
Use distinct input and output paths.
```

Do not add live-data, provider, credential, or automated scheduling instructions.

---

## Validation

Run:

```powershell
python -m pytest tests/test_local_json_preflight_report_export.py
python -m pytest tests/test_main.py
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

Manually verify with local paths:

```powershell
python -m market_sentry `
  --local-json-preflight .\valid-metadata.json `
  --local-json-preflight-report .\preflight-report.txt
```

Expected:

```text
exit 0
Relative Volume: 2.0x
preflight-report.txt equals terminal report content
no provider creation
no API calls
no voice playback
```

---

## Acceptance Criteria

Phase 15K is complete when:

```text
- an optional explicit report output path is accepted only with explicit local preflight input;
- exactly the existing Phase 15J rendered report string is written in UTF-8 to the output path;
- no trailing newline or export-only content is added;
- direct equal parsed input/output paths are rejected before input read or output write;
- missing output parent or any output OSError produces a stable EXPORT_ERROR report and exit 1;
- expected input/source errors remain reportable and exportable;
- existing no-export Phase 15J behavior is unchanged;
- invalid command combinations never write output;
- config/provider/scanner/alert/voice/network/trading behavior remains untouched;
- full project tests remain green.
```
