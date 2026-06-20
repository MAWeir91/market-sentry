# Phase 17E — Manual Explicit Alpaca RVOL Capture Preflight CLI

## Status

**Planned.** This document defines Phase 17E only.

Phase 17D provides a manually invoked, caller-injected Alpaca capture-and-preflight coordinator. It intentionally has no CLI, no configuration loading, no transport construction, and no automatic provider activation.

Phase 17E adds the first explicit command-line wrapper around that coordinator:

```text
explicit metadata seed JSON
+ explicit metadata output JSON
+ explicit RVOL bundle output JSON
+ explicit capture controls
+ explicit CLI live-data confirmation
+ existing environment/credential gate
        ↓
caller-configured Alpaca HTTP fetcher
        ↓
Phase 17D capture-and-preflight coordinator
        ↓
canonical metadata.json + historical-rvol-bundle.json
+ terminal report + optional report file
```

This is a **one-shot manual capture command**, not a scanner command.

It is the first application-surface feature that may make Alpaca API requests. It remains deliberately separate from `live_composed`, scanner candidate construction, FMP float reference data, alerts, voice, and loops.

---

## Goal

Expose a manually invoked command that:

1. reads exactly one explicit local **metadata seed** JSON file;
2. loads its raw metadata records through the existing Phase 15G metadata source;
3. constructs one caller-configured Alpaca historical-bars fetcher using existing environment configuration only after all local command guards pass;
4. delegates the live capture, artifact writes, and offline RVOL preflight to Phase 17D;
5. prints a deterministic terminal report;
6. optionally writes the exact report string to one caller-selected report path.

The command must require **both**:

```text
a dedicated CLI confirmation flag
and
MARKET_SENTRY_ALLOW_LIVE_DATA enabled through existing configuration
```

It must require Alpaca API credentials. It must **not** require:

```text
MARKET_SENTRY_PROVIDER=live_composed
MARKET_SENTRY_WATCHLIST
FMP_API_KEY
```

No scanner is run. No candidate is generated. No alert or voice behavior runs. No order/trading behavior exists.

---

## Why a Metadata Seed Is Required

The historical RVOL pipeline needs metadata for historical trading sessions:

```text
session_id
session_start_timestamp
session_end_timestamp
cutoff_timestamp
is_complete
```

Alpaca bars alone do not safely infer this metadata, and FMP’s existing component provides float/reference data only.

The caller must therefore provide a canonical Phase 15G-compatible metadata seed file. Phase 17E reads those raw records, then Phase 17D writes them to a separate explicit metadata output file alongside the newly captured bar bundle.

The seed input must remain distinct from all output paths.

---

## Command Surface

### Required command

```powershell
python -m market_sentry `
  --manual-alpaca-rvol-capture `
  <METADATA_INPUT_PATH> <METADATA_OUTPUT_PATH> <BUNDLE_OUTPUT_PATH> `
  --manual-alpaca-rvol-capture-confirm-live-data `
  --manual-alpaca-rvol-capture-symbol <SYMBOL> `
  --manual-alpaca-rvol-capture-historical-start <ISO_TIMESTAMP> `
  --manual-alpaca-rvol-capture-historical-end <ISO_TIMESTAMP> `
  --manual-alpaca-rvol-capture-historical-max-pages <INTEGER> `
  --manual-alpaca-rvol-capture-current-start <ISO_TIMESTAMP> `
  --manual-alpaca-rvol-capture-current-end <ISO_TIMESTAMP> `
  --manual-alpaca-rvol-capture-current-max-pages <INTEGER> `
  --manual-alpaca-rvol-capture-current-session-id <SESSION_ID> `
  --manual-alpaca-rvol-capture-bucket <BUCKET> `
  --manual-alpaca-rvol-capture-cutoff <ISO_TIMESTAMP> `
  --manual-alpaca-rvol-capture-minimum-historical-sessions <INTEGER>
```

Exact positional path order:

```text
1. METADATA_INPUT_PATH
2. METADATA_OUTPUT_PATH
3. BUNDLE_OUTPUT_PATH
```

### Optional report output

```powershell
--manual-alpaca-rvol-capture-report <REPORT_PATH>
```

### Optional query controls

```powershell
--manual-alpaca-rvol-capture-timeframe <TIMEFRAME>
--manual-alpaca-rvol-capture-page-limit <INTEGER>
--manual-alpaca-rvol-capture-sort <asc|desc>
```

Defaults:

```text
timeframe: 1Min
page limit: 1000
sort: asc
```

The same timeframe, page limit, and sort controls are used for both historical and current queries. Historical/current start/end and page-cap controls remain explicit and separate.

### Recommended environment setup

```powershell
$env:MARKET_SENTRY_ALLOW_LIVE_DATA = "true"
$env:ALPACA_API_KEY = "<your key>"
$env:ALPACA_API_SECRET = "<your secret>"
# Optional:
$env:ALPACA_DATA_FEED = "iex"
```

The command must never print keys, secrets, headers, URLs with credentials, or the complete process environment.

---

## Non-Goals

Do not add:

```text
live_composed provider activation
provider-factory changes
scanner candidate construction
FMP float lookup
watchlist scanning
scan loop activation
automatic or scheduled capture
symbol discovery
metadata inference
metadata record editing
metadata seed discovery
directory scans
glob/rglob
order placement
trade execution
portfolio behavior
alerts
voice playback
```

Do not modify existing manual local JSON preflight behavior.

---

## Required Files

Create:

```text
docs/69_MANUAL_EXPLICIT_ALPACA_RVOL_CAPTURE_PREFLIGHT_CLI.md
src/market_sentry/manual_explicit_alpaca_rvol_capture_preflight_cli.py
tests/test_manual_explicit_alpaca_rvol_capture_preflight_cli.py
```

Modify:

```text
src/market_sentry/main.py
tests/test_main.py
README.md
```

Do not modify:

```text
src/market_sentry/data/explicit_alpaca_rvol_capture_preflight.py
src/market_sentry/data/explicit_alpaca_rvol_bundle_capture.py
src/market_sentry/data/json_historical_session_metadata_writer.py
src/market_sentry/data/json_historical_session_metadata_source.py
src/market_sentry/data/json_historical_rvol_bundle_writer.py
src/market_sentry/data/json_historical_rvol_bundle.py
src/market_sentry/data/alpaca_historical_bars_fetcher.py
src/market_sentry/data/http_stdlib.py
src/market_sentry/config.py
src/market_sentry/data/factory.py
provider modules
scanner modules
alert modules
voice modules
existing Phase 15–17 tests except test_main.py
```

---

# Part A — Manual CLI Helper

## Helper Ownership

`manual_explicit_alpaca_rvol_capture_preflight_cli.py` owns:

```text
command argument model
CLI-specific validation of required capture fields
cutoff timestamp parsing
construction of existing Alpaca queries
loading the explicit metadata seed records
existing configuration gate evaluation
existing standard-library transport construction
existing Alpaca fetcher construction
one Phase 17D coordinator call
manual command/error/capture-stop report rendering
```

Phase 17E must not reimplement:

```text
raw historical page collection
current page composition
current intraday-series adaptation
bundle serialization
metadata serialization
metadata workflow preflight
RVOL calculation
report output writing for a completed Phase 17D preflight
```

Those remain owned by Phases 17B, 17C, 17D, and 15H.

---

## Allowed Production Imports

`src/market_sentry/manual_explicit_alpaca_rvol_capture_preflight_cli.py` may import only:

```text
standard library:
  dataclasses
  datetime
  json
  pathlib

market_sentry.config:
  AppConfig

market_sentry.data.alpaca:
  AlpacaMarketDataSettings

market_sentry.data.alpaca_historical_bars_fetcher:
  AlpacaHistoricalBarsFetchError
  AlpacaHistoricalBarsFetcher
  AlpacaHistoricalBarsQuery

market_sentry.data.explicit_alpaca_rvol_bundle_capture:
  ExplicitAlpacaRvolBundleCaptureRequest

market_sentry.data.explicit_alpaca_rvol_capture_preflight:
  ExplicitAlpacaRvolCapturePreflightRequest
  ExplicitAlpacaRvolCapturePreflightResult
  ExplicitAlpacaRvolCapturePreflightStatus
  capture_and_preflight_explicit_alpaca_rvol_bundle
  is_explicit_alpaca_rvol_capture_preflight_success

market_sentry.data.historical_session_manifest:
  HistoricalSessionManifestRequest

market_sentry.data.http:
  HttpTransport
  HttpTransportError

market_sentry.data.http_stdlib:
  StdlibHttpTransport

market_sentry.data.json_historical_session_metadata_source:
  JsonHistoricalSessionMetadataFileSource
  JsonHistoricalSessionMetadataFileSourceError

market_sentry.data.json_historical_session_metadata_writer:
  JsonHistoricalSessionMetadataWriteError
```

Do not import:

```text
main
argparse
sys
os
provider/factory/readiness
FMP
Phase 16A loader
Phase 16B CLI/export helpers
Phase 15J/15K CLI/export helpers
metadata/bundle writers directly
metadata workflow preflight directly
lower workflow stages
scanner/alerts/voice
tests
scenario catalogs/harnesses
network libraries other than the existing StdlibHttpTransport module
trading/order modules
```

The helper may instantiate `StdlibHttpTransport` only after all command validation, output collision guards, explicit confirmation, configuration gate checks, capture request construction, and metadata seed loading have succeeded.

---

## Public Models and Functions

Create:

```python
class ManualExplicitAlpacaRvolCaptureCommandError(ValueError):
    """Raised for invalid manual explicit Alpaca capture command inputs."""
```

Create a frozen command request:

```python
@dataclass(frozen=True)
class ManualExplicitAlpacaRvolCaptureCommandRequest:
    """Fully explicit inputs for one manual Alpaca capture command."""

    metadata_input_path: Path
    metadata_output_path: Path
    bundle_output_path: Path
    report_output_path: Path | None

    confirm_live_data: bool

    symbol: str | None
    historical_start: str | None
    historical_end: str | None
    historical_max_pages: int | None

    current_start: str | None
    current_end: str | None
    current_max_pages: int | None

    current_session_id: str | None
    bucket: str | None
    cutoff: str | None
    minimum_historical_sessions: int | None

    timeframe: str = "1Min"
    page_limit: int = 1000
    sort: str = "asc"
```

This request retains parsed `Path` objects exactly. It does not resolve, normalize, or read them.

Provide:

```python
def run_manual_explicit_alpaca_rvol_capture_preflight(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
    config: AppConfig,
    transport: HttpTransport | None = None,
) -> ExplicitAlpacaRvolCapturePreflightResult:
    """Run one explicitly confirmed, configuration-gated Alpaca capture."""
```

`transport=None` means construct one existing `StdlibHttpTransport` only after all non-network work succeeds. A supplied transport exists for tests and must be used exactly as provided.

Provide:

```python
def render_manual_explicit_alpaca_rvol_capture_command_error(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
    error: BaseException,
) -> str:
    ...
```

Provide:

```python
def render_manual_explicit_alpaca_rvol_capture_error(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
    error: BaseException,
) -> str:
    ...
```

Provide:

```python
def render_manual_explicit_alpaca_rvol_capture_stopped_report(
    result: ExplicitAlpacaRvolCapturePreflightResult,
) -> str:
    ...
```

The stopped report is for returned `LIVE_DATA_NOT_ALLOWED`, `OUTPUT_PATH_CONFLICT`, or `CAPTURE_NOT_WRITTEN` outcomes. It is not a substitute for a full preflight report.

Provide:

```python
def is_manual_explicit_alpaca_rvol_capture_success(
    result: ExplicitAlpacaRvolCapturePreflightResult,
) -> bool:
    ...
```

This must delegate success semantics only to:

```python
is_explicit_alpaca_rvol_capture_preflight_success(result)
```

No duplicate RVOL status traversal.

---

## Stable Command Validation Errors

Use exactly these stable message values in `ManualExplicitAlpacaRvolCaptureCommandError`:

```text
MISSING_CAPTURE_ARGUMENTS:<comma-separated flag names>
METADATA_INPUT_EQUALS_METADATA_OUTPUT
METADATA_INPUT_EQUALS_BUNDLE_OUTPUT
METADATA_INPUT_EQUALS_REPORT_OUTPUT
LIVE_DATA_CONFIRMATION_REQUIRED
ENV_LIVE_DATA_NOT_ALLOWED
MISSING_ALPACA_API_KEY
MISSING_ALPACA_API_SECRET
INVALID_CUTOFF_TIMESTAMP
```

### Required capture argument order

When reporting missing fields, use this exact flag order:

```text
--manual-alpaca-rvol-capture-symbol
--manual-alpaca-rvol-capture-historical-start
--manual-alpaca-rvol-capture-historical-end
--manual-alpaca-rvol-capture-historical-max-pages
--manual-alpaca-rvol-capture-current-start
--manual-alpaca-rvol-capture-current-end
--manual-alpaca-rvol-capture-current-max-pages
--manual-alpaca-rvol-capture-current-session-id
--manual-alpaca-rvol-capture-bucket
--manual-alpaca-rvol-capture-cutoff
--manual-alpaca-rvol-capture-minimum-historical-sessions
```

A present `None`/empty string is missing for string fields. For integer values, only `None` is missing; existing typed model constructors retain validation ownership for invalid numeric ranges/types once parsed by argparse.

### Cutoff timestamp parsing

`command.cutoff` must be a non-empty ISO string. For parsing only:

```text
terminal Z may be mechanically converted to +00:00
datetime.fromisoformat is used
naive timestamps remain naive
fixed offsets remain fixed offsets
```

An invalid or empty cutoff raises exactly:

```text
INVALID_CUTOFF_TIMESTAMP
```

Do not infer a cutoff from current time or market hours.

### Query construction

Build both `AlpacaHistoricalBarsQuery` objects from:

```text
timeframe: command.timeframe
limit: command.page_limit
sort: command.sort

historical start/end: command.historical_start / command.historical_end
current start/end: command.current_start / command.current_end
```

Allow existing `AlpacaHistoricalBarsFetchError` exceptions from query construction to propagate unchanged. Do not duplicate its validation.

---

# Part B — Exact Helper Execution Order

The helper must execute exactly in this order:

```text
1. validate command path types
2. validate required capture arguments
3. validate metadata-seed/output path collisions
4. require command.confirm_live_data is True
5. require config.allow_live_data is True
6. require config.alpaca_api_key
7. require config.alpaca_api_secret
8. parse cutoff and construct existing query/request objects
9. load raw records from the explicit metadata input file
10. construct existing StdlibHttpTransport only when no transport is supplied
11. construct one AlpacaHistoricalBarsFetcher
12. construct Phase 17D request
13. call Phase 17D exactly once
14. return its exact result reference
```

### Path type validation

Required exact errors:

```python
TypeError("metadata_input_path must be a pathlib.Path.")
TypeError("metadata_output_path must be a pathlib.Path.")
TypeError("bundle_output_path must be a pathlib.Path.")
TypeError("report_output_path must be a pathlib.Path or None.")
```

### Metadata seed path collision precedence

Before confirmation, config, source load, transport construction, fetch, output write, or preflight:

```text
1. metadata_input_path == metadata_output_path
   → METADATA_INPUT_EQUALS_METADATA_OUTPUT

2. metadata_input_path == bundle_output_path
   → METADATA_INPUT_EQUALS_BUNDLE_OUTPUT

3. metadata_input_path == report_output_path
   → METADATA_INPUT_EQUALS_REPORT_OUTPUT
```

Use direct parsed `Path` equality only.

The Phase 17D coordinator owns the remaining output-only collisions:

```text
metadata_output_path == bundle_output_path
report_output_path == metadata_output_path
report_output_path == bundle_output_path
```

It must receive the exact command paths and retain its existing stable reasons.

### Explicit confirmation and configuration gate

Both checks are mandatory:

```python
command.confirm_live_data is True
config.allow_live_data is True
```

The dedicated CLI confirmation guard comes first. It prevents configuration loading from accidentally enabling capture solely through a persistent environment setting.

Only after both gates pass may the helper load metadata, instantiate a transport, or invoke the injected/live capture path.

### Credential behavior

Only these values are required:

```text
config.alpaca_api_key
config.alpaca_api_secret
```

`config.alpaca_data_feed` is optional and falls back to existing `AlpacaMarketDataSettings` behavior.

Do not inspect:

```text
config.provider
config.watchlist
config.fmp_api_key
```

Do not call the provider factory or live-readiness evaluator.

### Metadata seed load

Before transport construction and before any Alpaca request:

```python
seed_request = HistoricalSessionManifestRequest(
    symbol=command.symbol,
    bucket=command.bucket,
    current_session_id=command.current_session_id,
)

records = JsonHistoricalSessionMetadataFileSource(
    command.metadata_input_path,
).load_raw_manifest_records(seed_request)
```

The source may throw existing standard or source errors. Let them propagate unchanged.

The source read is the only Phase 17E input-file read.

### Existing settings and fetcher construction

Use:

```python
settings = AlpacaMarketDataSettings(
    api_key=config.alpaca_api_key,
    api_secret=config.alpaca_api_secret,
    feed=config.alpaca_data_feed or existing default,
)
```

Then exactly one:

```python
AlpacaHistoricalBarsFetcher(
    settings=settings,
    transport=transport if transport is not None else StdlibHttpTransport(),
)
```

No request is sent until Phase 17D delegates into Phase 17B’s existing collector.

---

# Part C — Main CLI Integration

## Parser Additions

Add:

```text
--manual-alpaca-rvol-capture
    nargs=3
    metavar=(METADATA_INPUT_PATH, METADATA_OUTPUT_PATH, BUNDLE_OUTPUT_PATH)

--manual-alpaca-rvol-capture-report PATH
--manual-alpaca-rvol-capture-confirm-live-data

--manual-alpaca-rvol-capture-symbol SYMBOL
--manual-alpaca-rvol-capture-historical-start ISO_TIMESTAMP
--manual-alpaca-rvol-capture-historical-end ISO_TIMESTAMP
--manual-alpaca-rvol-capture-historical-max-pages INTEGER

--manual-alpaca-rvol-capture-current-start ISO_TIMESTAMP
--manual-alpaca-rvol-capture-current-end ISO_TIMESTAMP
--manual-alpaca-rvol-capture-current-max-pages INTEGER

--manual-alpaca-rvol-capture-current-session-id SESSION_ID
--manual-alpaca-rvol-capture-bucket BUCKET
--manual-alpaca-rvol-capture-cutoff ISO_TIMESTAMP
--manual-alpaca-rvol-capture-minimum-historical-sessions INTEGER

--manual-alpaca-rvol-capture-timeframe TIMEFRAME
--manual-alpaca-rvol-capture-page-limit INTEGER
--manual-alpaca-rvol-capture-sort {asc,desc}
```

The three optional query controls use defaults:

```text
timeframe: 1Min
page limit: 1000
sort: asc
```

All other capture fields default to `None` unless the manual command is selected.

## Raw argv sanitation

Extend the existing raw argv voice-flag sanitation so the new manual capture mode behaves like the two existing local preflight modes:

```text
simultaneous --speak and --no-speak
+ manual capture mode
→ stable manual command conflict report, not argparse mutual-exclusion output
```

Do not alter existing behavior when the new mode is absent.

## Main Guard Order

Use this exact command-level guard order:

```text
1. existing one-path report dependency
2. existing bundle report dependency
3. manual capture report dependency
4. manual capture option dependency
5. one-path/bundle/manual mode exclusivity
6. mode-specific local/manual conflicts
7. build manual command request
8. load config once
9. run manual helper once
10. render/print exact result report
```

### Manual report dependency

When:

```text
--manual-alpaca-rvol-capture-report
```

is supplied without:

```text
--manual-alpaca-rvol-capture
```

print an exit-2 command error before any config load, metadata read, transport construction, or output write:

```text
Market Sentry Manual Alpaca RVOL Capture Preflight
Metadata Input Path: N/A
Metadata Path: N/A
Bundle Path: N/A
Report Path: <report>
Result: COMMAND_ERROR
Error: --manual-alpaca-rvol-capture-report requires --manual-alpaca-rvol-capture
```

### Manual capture option dependency

If any manual capture option other than the mode flag itself is present without `--manual-alpaca-rvol-capture`, print:

```text
Market Sentry Manual Alpaca RVOL Capture Preflight
Metadata Input Path: N/A
Metadata Path: N/A
Bundle Path: N/A
Report Path: N/A
Result: COMMAND_ERROR
Error: manual Alpaca capture options require --manual-alpaca-rvol-capture
```

The report option dependency above has precedence over this broader option dependency.

### Mode exclusivity

The manual mode may not be combined with either:

```text
--local-json-preflight
--local-json-bundle-preflight
```

Return exit 2 before config/load/fetch/write.

Stable error:

```text
--manual-alpaca-rvol-capture cannot be combined with local JSON preflight modes
```

The existing old/bundle exclusivity behavior must remain unchanged.

### Manual capture conflicts

When manual mode is selected, conflict with:

```text
--loop
--live-readiness
--relative-volume-configured
non-default --interval
--speak
--no-speak
```

Use the existing raw-order conflict behavior and a dedicated manual command-error renderer.

No config load, metadata read, transport construction, or live request may occur after a conflict.

## Configuration and network boundary

Only the selected manual capture branch calls:

```python
load_config()
run_manual_explicit_alpaca_rvol_capture_preflight(...)
```

No other branch may import or construct the manual live capture dependencies at execution time.

No provider factory or `live_composed` branch is used.

---

# Part D — Reports, Exit Codes, and Expected Errors

## Full Phase 17D report

When Phase 17D reaches preflight, print its exact `result.report` string and return:

```text
0 when Phase 17D success predicate is true
1 when Phase 17D returns PREFLIGHT_FAILED
```

The Phase 17D optional report path is passed through exactly. It writes the report before the helper returns; no CLI-level report write occurs for completed preflights.

## Capture-stopped report

When Phase 17D returns with no preflight:

```text
Market Sentry Manual Alpaca RVOL Capture Preflight
Metadata Input Path: <seed>
Metadata Path: <output>
Bundle Path: <output>
Report Path: <report or N/A>
Input Mode: EXPLICIT_ALPACA_CAPTURE
Capture: <capture status or N/A>
Result: <Phase 17D status>
Reason: <reason or N/A>
Note: This manually invoked command can use caller-configured Alpaca fetching only after explicit CLI confirmation and MARKET_SENTRY_ALLOW_LIVE_DATA are both enabled. It does not activate providers, scan candidates, call FMP, or play voice alerts.
```


The stopped report is terminal-only. No report output is written because Phase 17D does not write a report without preflight.

## Command error report

For command validation, confirmation, configuration, and path errors:

```text
Market Sentry Manual Alpaca RVOL Capture Preflight
Metadata Input Path: <seed or N/A>
Metadata Path: <output or N/A>
Bundle Path: <output or N/A>
Report Path: <report or N/A>
Result: COMMAND_ERROR
Error: <stable error message>
Note: This command is one-shot and does not activate providers, scan candidates, call FMP, or play voice alerts.
```

Command errors return `2` and do not write artifacts.

## Expected operational error report

Catch only these expected errors in the selected manual capture branch:

```text
OSError
UnicodeDecodeError
json.JSONDecodeError
JsonHistoricalSessionMetadataFileSourceError
JsonHistoricalSessionMetadataWriteError
AlpacaHistoricalBarsFetchError
HttpTransportError
```

Render:

```text
Market Sentry Manual Alpaca RVOL Capture Preflight
Metadata Input Path: <seed>
Metadata Path: <output>
Bundle Path: <output>
Report Path: <report or N/A>
Result: ERROR
Error Type: <class name>
Error: <message or class name>
Note: This command can use caller-configured Alpaca fetching only after explicit CLI confirmation and MARKET_SENTRY_ALLOW_LIVE_DATA are both enabled. It does not activate providers, scan candidates, call FMP, or play voice alerts.
```


Operational errors return `1`.

Do not catch unexpected programming errors or transform them into reports.

## Report output failure

Phase 17D directly writes a requested report after successful metadata/bundle artifacts and preflight report construction. If that report write raises `OSError`, the selected CLI branch catches it as an expected operational error:

```text
metadata and bundle may already exist
do not delete or roll back them
print the expected operational ERROR report
return 1
```

---

# Part E — Tests

## New helper tests

Create:

```text
tests/test_manual_explicit_alpaca_rvol_capture_preflight_cli.py
```

Use injected `FakeHttpTransport` only. No live HTTP.

Test:

```text
frozen command model
exact input/output Path retention
all path type errors before config/source/transport/capture
required capture fields and stable missing-field ordering
metadata seed output collision precedence
confirmation gate before config/source/transport/capture
environment allow-live gate before source/transport/capture
missing Alpaca key/secret before source/transport/capture
does not inspect provider/watchlist/FMP config fields
invalid cutoff before source/transport/capture
existing query validation errors propagate unchanged
metadata seed source errors propagate unchanged before transport/capture
provided transport is retained and used
transport=None creates exactly one StdlibHttpTransport after metadata seed load
constructs exact Alpaca settings and queries
loads metadata seed once with exact manifest request
calls Phase 17D exactly once with exact fetcher/request/path/records
success predicate delegates to Phase 17D predicate
expected helper source boundaries
```

## `test_main.py` additions

Test:

```text
parser defaults and values
manual report dependency
manual option dependency
manual/old/bundle mode exclusivity
manual conflicts in raw argv order
both voice flags render stable conflict rather than argparse error
manual command errors return 2 and avoid load_config/helper
configuration gate errors return 2 and avoid live capture
metadata input errors return 1 and avoid transport/live capture
valid result exit 0 and prints exact Phase 17D report
returned preflight failure exit 1 and prints exact Phase 17D report
capture stopped exit 1 and prints stopped report
expected operational error exit 1 with error report
report output failure preserves the operational error behavior
no provider factory/scanner/voice/readiness work runs in manual branch
existing one-path/bundle/default behavior remains unchanged
```

## End-to-end command compatibility

Use `FakeHttpTransport` via helper injection tests to demonstrate:

```text
canonical metadata seed
+ fake Alpaca page responses
→ Phase 17D
→ metadata output + bundle output + report output
→ final RVOL 2.0
```

Use a current-side incomplete capture response to demonstrate:

```text
no metadata output
no report output
exit 1 capture-stopped terminal report
```

Use a historical incomplete response to demonstrate:

```text
metadata and bundle output exist
report output exists
returned preflight failure
existing incomplete-history diagnostics are preserved
```

---

# Part F — README

Add a concise **manual one-shot Alpaca capture preflight** section:

```text
- this command may call Alpaca only when both confirmation mechanisms are enabled;
- it requires only Alpaca credentials, not FMP or live_composed;
- it requires a caller-supplied metadata seed file;
- it writes explicit metadata/bundle/report artifacts;
- it is not scanner activation and does not trade.
```

Do not include keys or secrets in examples.

---

## Validation

Run:

```powershell
python -m pytest tests/test_manual_explicit_alpaca_rvol_capture_preflight_cli.py
python -m pytest tests/test_main.py
python -m pytest
python -m market_sentry
python -m market_sentry --local-json-preflight .\does-not-exist.json
python -m market_sentry --local-json-preflight-report .\report.txt
python -m market_sentry --local-json-bundle-preflight .\does-not-exist-metadata.json .\does-not-exist-bundle.json
python -m market_sentry --local-json-bundle-preflight-report .\bundle-report.txt
python -m market_sentry --manual-alpaca-rvol-capture-report .\capture-report.txt
```

Then rerun:

```text
fixture
composed_fixture
Alpaca placeholder
both live_composed placeholder checks
both readiness checks
```

Do not make a real network request during validation.

---

## Acceptance Criteria

Phase 17E is complete when:

```text
- a manual one-shot CLI branch exists for the Phase 17D coordinator;
- it requires both explicit CLI confirmation and configured environment live-data permission;
- it requires Alpaca key/secret but not FMP, live_composed, or watchlist;
- it loads only the caller-selected metadata seed file before live transport construction;
- it delegates capture/preflight only through Phase 17D;
- it prints deterministic reports and preserves Phase 17D report output semantics;
- all denial/validation/conflict paths avoid network, metadata output, bundle output, and report output;
- no scanner, provider, alert, voice, loop, or trading behavior is activated;
- existing CLI branches are unchanged;
- full tests remain green.
```
