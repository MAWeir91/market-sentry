# Phase 17D — Explicit Alpaca Capture-and-Preflight Orchestrator

## Status

**Planned.** This document defines Phase 17D only.

Phase 17B can manually capture an explicit canonical historical/current RVOL bundle from a caller-injected `AlpacaHistoricalBarsFetcher`. Phase 17C can write caller-supplied historical session metadata records into canonical metadata JSON. Phase 16B can preflight an existing metadata JSON plus bundle JSON through the established RVOL workflow.

Phase 17D composes those existing, reviewed parts into one **manually invoked, explicitly gated data-layer operation**:

```text
caller-supplied metadata records
+ explicit capture request
+ caller-injected AlpacaHistoricalBarsFetcher
+ explicit metadata output path
+ explicit bundle output path (inside capture request)
+ optional explicit report output path
        ↓
strict output-path / live-data guards
        ↓
metadata renderability check in memory
        ↓
Phase 17B explicit capture
        ↓
Phase 17C metadata write
        ↓
existing Phase 15H local metadata workflow preflight
        ↓
capture-and-preflight report
        ↓
optional exact report output
```

This phase is not a scanner, a provider activation, or a CLI command. It does not read configuration, instantiate an HTTP transport, discover files, infer metadata, or schedule recurring work.

The output is an explicit manually produced artifact pair that can be inspected and re-run through the existing Phase 16B local bundle preflight command.

---

## Correction and Intent

This operation may use a caller-injected Alpaca fetcher after an explicit live-data gate. It must be honest about that limited live data access.

It does **not** use FMP. The current FMP component supplies shares-float reference data and cannot create historical session metadata containing:

```text
session_id
session_start_timestamp
session_end_timestamp
cutoff_timestamp
is_complete
```

Phase 17D receives metadata records from the caller. It never invents session calendars, market holidays, session windows, or completeness flags.

---

## Goal

Create a frozen request/result API for a one-shot manual operation that:

1. verifies all output paths before fetches or writes;
2. requires `capture_request.allow_live_data is True` exactly;
3. checks metadata records can be represented before live capture;
4. invokes Phase 17B capture exactly once;
5. writes metadata only after the bundle capture has written its bundle;
6. invokes existing Phase 15H preflight exactly once on the two freshly written files;
7. renders an explicit capture-and-preflight report;
8. optionally writes that exact report string to one caller-selected report path;
9. returns all relevant capture, write, preflight, report, status, and reason artifacts.

No new data calculation, metadata semantic validation, RVOL formula, provider factory, scanner, alert, voice, or trading behavior is introduced.

---

## Hard Safety Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is **not** a trading bot.

Do not add:

```text
CLI flags or argparse changes
main.py changes
configuration or environment reads
provider factory changes
new MARKET_SENTRY_PROVIDER values
automatic provider activation
HTTP transport construction
credentials loading
FMP calls
metadata inference
market-calendar lookup
holiday/session-window calculation
file discovery
directory scans
glob/rglob
background jobs
scheduler/loop behavior
scanner execution
candidate creation
alerts or voice playback
network calls except through the caller-injected 17B fetcher after its exact gate
order placement
position management
trade execution
buy/sell/enter/exit recommendations
portfolio behavior
```

No test may contact Alpaca or any network endpoint. Use `FakeHttpTransport` only.

`live_composed` remains gated and reserved/inactive.

---

## Required Files

Create:

```text
docs/68_EXPLICIT_ALPACA_CAPTURE_AND_PREFLIGHT.md
src/market_sentry/data/explicit_alpaca_rvol_capture_preflight.py
tests/test_explicit_alpaca_rvol_capture_preflight.py
```

Do not modify:

```text
README.md
src/market_sentry/main.py
src/market_sentry/local_json_preflight_cli.py
src/market_sentry/local_json_preflight_report_export.py
src/market_sentry/local_json_bundle_preflight_cli.py
src/market_sentry/local_json_bundle_preflight_report_export.py
src/market_sentry/data/explicit_alpaca_rvol_bundle_capture.py
src/market_sentry/data/json_historical_rvol_bundle_writer.py
src/market_sentry/data/json_historical_session_metadata_writer.py
src/market_sentry/data/json_historical_rvol_bundle.py
src/market_sentry/data/json_historical_session_metadata_source.py
Phase 14A–14K
Phase 15A–15L
Phase 16A–16C
Phase 17A–17C
provider/config/factory/readiness modules
FMP, Alpaca fetcher, HTTP, and transport modules
workflow/preflight modules
scanner modules
alert modules
voice modules
fixture scenario catalogs/harnesses
```

Phase 17D is a new coordinator only. Existing behavior must remain byte-for-byte unchanged.

---

## Ownership Boundary

```text
Phase 17B owns:
  exact live-data gate for its capture request
  historical/current page collection
  current-page composition
  current-series adaptation
  manifest/harness request construction
  canonical bundle write

Phase 17C owns:
  metadata record generic representability
  canonical metadata rendering
  metadata file write

Phase 15H owns:
  metadata source loading
  metadata/workflow composition
  manifest behavior
  historical assembly
  baseline calculation
  current cumulative volume
  time-of-day RVOL calculation
  existing diagnostics

Phase 17D owns:
  cross-artifact output path validation
  top-level no-fetch/no-write live-data gate
  sequencing the existing components
  no-metadata-write behavior after non-written capture
  capture-and-preflight report rendering
  optional explicit report write
  frozen orchestration result
```

Phase 17D must not:

```text
calculate or reimplement RVOL
read bundle JSON through the Phase 16A loader directly
read metadata JSON through the Phase 15G source directly
call Phase 16B CLI helpers
call main
render existing one-path or bundle CLI reports
mutate capture result artifacts
coerce metadata record values
validate metadata record semantics
inspect raw historical bars
repair current intraday values
catch or transform unexpected dependency exceptions
retry a fetch, capture, write, or preflight
perform rollback/delete output artifacts
```

The operation is explicitly **not atomic** across the two files. It prevalidates metadata rendering before capture, but an operating-system write failure after a successful bundle write can leave the written bundle in place. Do not delete or alter explicit caller-owned output files as compensation.

---

# Part A — Public Models and API

## Allowed Production Imports

`src/market_sentry/data/explicit_alpaca_rvol_capture_preflight.py` may import only:

```text
standard library:
  collections.abc
  dataclasses
  pathlib

market_sentry.data.explicit_alpaca_rvol_bundle_capture:
  ExplicitAlpacaRvolBundleCaptureRequest
  ExplicitAlpacaRvolBundleCaptureResult
  ExplicitAlpacaRvolBundleCaptureStatus
  capture_explicit_alpaca_rvol_bundle

market_sentry.data.alpaca_historical_bars_fetcher:
  AlpacaHistoricalBarsFetcher

market_sentry.data.json_historical_session_metadata_writer:
  render_local_historical_session_metadata
  write_local_historical_session_metadata

market_sentry.data.local_json_metadata_workflow_preflight:
  LocalJsonMetadataWorkflowPreflightResult
  run_local_json_metadata_workflow_preflight
```

Do not import:

```text
main
argparse
sys
environment/config
provider/factory/readiness
HTTP transport classes or constructors
FMP
Alpaca request/transport configuration
Phase 16A loader
Phase 16B CLI helper/exporter
Phase 15J/15K helper/exporter
metadata source directly
bundle writer directly
workflow stages below the Phase 15H wrapper
scenario catalogs/harnesses
tests
scanner/alerts/voice
network libraries
trading/order modules
```

Phase 17D uses the Phase 17B coordinator as the only live capture route, the Phase 17C writer as the only metadata output route, and Phase 15H wrapper as the only preflight route.

---

## Status Constants

Provide an equivalent stable status namespace:

```python
class ExplicitAlpacaRvolCapturePreflightStatus:
    """Stable statuses for one explicit capture-and-preflight operation."""

    LIVE_DATA_NOT_ALLOWED = "LIVE_DATA_NOT_ALLOWED"
    OUTPUT_PATH_CONFLICT = "OUTPUT_PATH_CONFLICT"
    CAPTURE_NOT_WRITTEN = "CAPTURE_NOT_WRITTEN"
    PREFLIGHT_SUCCEEDED = "PREFLIGHT_SUCCEEDED"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
```

Do not add a status for unexpected dependency exceptions. Those propagate unchanged.

---

## Request Model

Provide an equivalent frozen request:

```python
@dataclass(frozen=True)
class ExplicitAlpacaRvolCapturePreflightRequest:
    """Caller-selected inputs for one capture, metadata write, and preflight."""

    capture_request: ExplicitAlpacaRvolBundleCaptureRequest
    metadata_records: Sequence[object]
    metadata_output_path: Path
    report_output_path: Path | None = None
```

Responsibilities:

```text
capture_request.output_path is the explicit bundle output path
metadata_output_path is the explicit metadata output path
report_output_path is optional and only receives the final rendered report
metadata_records are caller-supplied opaque records
```

No other output path, fallback path, automatic filename, environment value, timestamped filename, or discovered location exists.

---

## Result Model

Provide an equivalent frozen result:

```python
@dataclass(frozen=True)
class ExplicitAlpacaRvolCapturePreflightResult:
    """Artifacts from one explicit capture-and-preflight attempt."""

    request: ExplicitAlpacaRvolCapturePreflightRequest
    metadata_path: Path
    bundle_path: Path
    report_path: Path | None

    capture_result: ExplicitAlpacaRvolBundleCaptureResult | None
    metadata_written: bool
    preflight_result: LocalJsonMetadataWorkflowPreflightResult | None

    report: str | None
    report_written: bool

    status: str
    reason: str | None = None
```

Exact field names may vary, but retain:

```text
exact request object
exact metadata path object
exact bundle path object from capture_request.output_path
exact optional report path object
capture result reference or None
metadata write outcome
preflight result reference or None
final rendered report or None
report-write outcome
stable status and reason
```

Do not read output files back to populate the result.

---

## Public Functions

Provide:

```python
def capture_and_preflight_explicit_alpaca_rvol_bundle(
    fetcher: AlpacaHistoricalBarsFetcher,
    request: ExplicitAlpacaRvolCapturePreflightRequest,
) -> ExplicitAlpacaRvolCapturePreflightResult:
    """Capture an explicit Alpaca bundle, write metadata, then preflight both."""
```

Provide:

```python
def render_explicit_alpaca_rvol_capture_preflight_report(
    result: ExplicitAlpacaRvolCapturePreflightResult,
) -> str:
    """Render one explicit capture-and-preflight report after preflight exists."""
```

Provide:

```python
def is_explicit_alpaca_rvol_capture_preflight_success(
    result: ExplicitAlpacaRvolCapturePreflightResult,
) -> bool:
    """Return True only when final preflight reached complete RVOL success."""
```

The report renderer may require a result with non-`None` `capture_result`, `preflight_result`, and `report`. It should not be used for denied, path-conflict, or capture-not-written results.

---

# Part B — Exact Validation and Execution Sequence

## 1. Path Type Validation

Before metadata rendering, fetch, capture, output write, or preflight:

```text
- request.capture_request.output_path must be pathlib.Path;
- request.metadata_output_path must be pathlib.Path;
- request.report_output_path must be pathlib.Path or None.
```

Required exact errors:

```python
TypeError("output_path must be a pathlib.Path.")
TypeError("metadata_output_path must be a pathlib.Path.")
TypeError("report_output_path must be a pathlib.Path or None.")
```

Do not call the Phase 17B capture helper merely to discover its output-path error after other work has begun.

---

## 2. Live-Data Gate

After path type validation and before metadata render, capture, fetch, output write, or preflight:

```python
if request.capture_request.allow_live_data is not True:
    ...
```

Return:

```text
status: LIVE_DATA_NOT_ALLOWED
reason: LIVE_DATA_NOT_ALLOWED
capture_result: None
metadata_written: False
preflight_result: None
report: None
report_written: False
```

This top-level gate guarantees a denied capture performs:

```text
zero fetches
zero metadata renders
zero bundle writes
zero metadata writes
zero preflight calls
zero report writes
```

`False`, `1`, `"true"`, `None`, and every non-`True` value must deny.

---

## 3. Direct Output Path Collision Guards

After path type validation and before the live-data gate, metadata render, fetch, write, or preflight, compare paths with direct parsed `Path` equality only:

```text
metadata_output_path == capture_request.output_path
report_output_path == metadata_output_path
report_output_path == capture_request.output_path
```

No `resolve`, `absolute`, `expanduser`, symlink test, alias detection, existence check, file read, or file write is permitted.

For conflicts return:

```text
status: OUTPUT_PATH_CONFLICT
capture_result: None
metadata_written: False
preflight_result: None
report: None
report_written: False
```

Use exactly these reason strings:

```text
METADATA_PATH_EQUALS_BUNDLE_PATH
REPORT_PATH_EQUALS_METADATA_PATH
REPORT_PATH_EQUALS_BUNDLE_PATH
```

Precedence:

```text
1. METADATA_PATH_EQUALS_BUNDLE_PATH
2. REPORT_PATH_EQUALS_METADATA_PATH
3. REPORT_PATH_EQUALS_BUNDLE_PATH
4. live-data gate
5. metadata renderability
6. capture
```

This allows deterministic results without altering caller-owned files.

---

## 4. Metadata Renderability Preflight

After successful path/gate validation and before the Phase 17B capture:

```python
render_local_historical_session_metadata(request.metadata_records)
```

Call it exactly once for this prevalidation purpose.

Do not retain, modify, write, or expose the rendered string. Its sole purpose is to ensure generic representation errors happen **before any live fetch or bundle write**.

`JsonHistoricalSessionMetadataWriteError` and other unexpected exceptions propagate unchanged. No synthetic result follows an exception.

The subsequent metadata writer call will render again internally when it writes. This intentional second rendering is permitted because the Phase 17C public writer owns the actual output write.

---

## 5. Phase 17B Capture

Call exactly once:

```python
capture_explicit_alpaca_rvol_bundle(fetcher, request.capture_request)
```

If it returns any status other than `BUNDLE_WRITTEN`, do not write metadata, do not preflight, do not render a report, and do not write a report.

Return:

```text
status: CAPTURE_NOT_WRITTEN
reason: CAPTURE_NOT_WRITTEN:<capture status>
capture_result: exact returned capture result
metadata_written: False
preflight_result: None
report: None
report_written: False
```

This includes Phase 17B’s expected:

```text
LIVE_DATA_NOT_ALLOWED
CURRENT_COLLECTION_NOT_COMPOSABLE
CURRENT_SERIES_ADAPTATION_FAILED
```

The top-level exact gate should make returned `LIVE_DATA_NOT_ALLOWED` practically unreachable, but preserve it correctly if a substituted test dependency returns it.

---

## 6. Write Metadata

Only after capture returns `BUNDLE_WRITTEN`, call exactly once:

```python
write_local_historical_session_metadata(
    request.metadata_output_path,
    request.metadata_records,
)
```

Do not call `Path.write_text` directly. The Phase 17C writer is the only metadata output route.

After the call returns, `metadata_written` is `True`.

Filesystem and representation exceptions propagate unchanged. Do not delete the already-written bundle if this write fails.

---

## 7. Existing Offline Preflight

After successful metadata write, call exactly once:

```python
run_local_json_metadata_workflow_preflight(
    request.metadata_output_path,
    capture_result.historical_collection,
    capture_result.manifest_request,
    capture_result.current_series_result.intraday_series,
    capture_result.harness_request,
)
```

Use exact references returned by the successful Phase 17B result.

Do not call the Phase 16A bundle loader. The just-captured typed inputs are already available from Phase 17B, and Phase 15H is the existing preflight core.

Unexpected preflight exceptions propagate unchanged. Do not synthesize an error report in this data-layer phase.

---

## 8. Render Report

After preflight returns, build a result with:

```text
capture_result: exact capture result
metadata_written: True
preflight_result: exact returned preflight result
report: None initially
report_written: False initially
```

Then render report text using `render_explicit_alpaca_rvol_capture_preflight_report`.

The renderer must use exactly this line order:

```text
Market Sentry Explicit Alpaca RVOL Capture Preflight
Metadata Path: <metadata path>
Bundle Path: <bundle path>
Input Mode: EXPLICIT_ALPACA_CAPTURE
Capture: BUNDLE_WRITTEN
Metadata Load: <status or N/A>
Metadata Load Reason: <reason or N/A>
Workflow: <status or N/A>
Workflow Reason: <reason or N/A>
Bridge: <status or N/A>
Bridge Reason: <reason or N/A>
Composition: <status or N/A>
Coordinator: <status or N/A>
Coordinator Reason: <reason or N/A>
Manifest: <status or N/A>
Manifest Reason: <reason or N/A>
Harness: <status or N/A>
Harness Reason: <reason or N/A>
Final: <status or N/A>
Final Reason: <reason or N/A>
Time-of-Day RVOL: <status or N/A>
Time-of-Day RVOL Reason: <reason or N/A>
Relative Volume: <one decimal>x or N/A
Note: This operation uses caller-injected Alpaca fetching only after explicit allow_live_data=True. It writes only the explicit metadata and bundle paths, then runs offline RVOL preflight. It does not activate providers, scan candidates, call FMP, or play voice alerts.
```

Rules:

```text
- no fixed fixture profile label;
- do not claim no API calls;
- no trailing newline in the rendered report string;
- `Relative Volume` formatting exactly one decimal with `x`;
- N/A for absent nested artifacts;
- normal preflight failure is a report, not an exception.
```

---

## 9. Optional Report Output

When `report_output_path is not None`, after report rendering call exactly once:

```python
request.report_output_path.write_text(report, encoding="utf-8")
```

The report output must equal the rendered report string exactly, without an appended newline and without read-back.

When `report_output_path is None`, no report write occurs.

Do not:

```text
create report parent directories
read report content back
retry
catch report write errors
render an EXPORT_ERROR report
delete metadata or bundle
```

An `OSError` from report output propagates unchanged. The explicit metadata and bundle files may remain written.

---

## 10. Final Status

Use the same complete nested preflight success meaning as the reviewed local bundle preflight:

```text
metadata load = LOADED
workflow = WORKFLOW_BRIDGE_RAN
bridge = WORKFLOW_RAN
composition = COMPOSED
coordinator = OK
manifest = OK
harness = OK
final = OK
time-of-day RVOL = OK
relative volume is not None
```

On complete success:

```text
status: PREFLIGHT_SUCCEEDED
reason: None
```

On any normal returned preflight non-success:

```text
status: PREFLIGHT_FAILED
reason: PREFLIGHT_FAILED
```

The report still renders and optional report output still writes for both successful and returned-failure preflights.

`is_explicit_alpaca_rvol_capture_preflight_success` returns true only for `PREFLIGHT_SUCCEEDED` and must not re-run or mutate anything.

---

# Part C — Required Tests

Create:

```text
tests/test_explicit_alpaca_rvol_capture_preflight.py
```

## Unit Boundary and Sequencing Tests

Monkeypatch only direct imported symbols in the Phase 17D module.

Test:

```text
frozen request/result models
exact request/path references retained
capture output-path type error before any render/fetch/write
metadata output-path type error before any render/fetch/write
report output-path type error before any render/fetch/write

each direct collision reason and exact precedence:
  metadata == bundle
  report == metadata
  report == bundle
no render/fetch/write/preflight on collision

False / 1 / "true" / None:
  LIVE_DATA_NOT_ALLOWED
  no metadata render
  no capture/fetch
  no metadata write
  no preflight
  no report write

metadata pre-render happens once before capture
metadata representation error propagates before capture/fetch/write
capture happens exactly once
capture non-BUNDLE_WRITTEN:
  no metadata write
  no preflight
  no report render/write
  CAPTURE_NOT_WRITTEN:<capture status>

successful capture:
  metadata writer once after capture
  preflight once after metadata write
  exact capture artifacts forwarded to preflight
  report rendered once
  optional report written once and matches exact report text
  no report output path performs no report write

returned non-success preflight:
  metadata/bundle remain written
  report still returns and optional output writes
  status PREFLIGHT_FAILED

unexpected metadata writer, capture, preflight, report-output errors:
  propagate unchanged
  no synthetic result
```

## Actual Fake-Alpaca Compatibility Tests

Use `FakeHttpTransport` only.

Test successful actual orchestration:

```text
fake injected Alpaca fetcher
+ valid metadata records
+ explicit output paths
→ canonical bundle file
→ canonical metadata file
→ Phase 17D preflight
→ PREFLIGHT_SUCCEEDED
→ report contains Input Mode: EXPLICIT_ALPACA_CAPTURE
→ report output equals exact returned report
→ RVOL 2.0x
```

Test historical incomplete behavior:

```text
historical collector result incomplete
+ current collection valid/composable
→ bundle and metadata still written
→ preflight runs
→ status PREFLIGHT_FAILED
→ existing incomplete collection diagnostic appears in report
```

Test current failure behavior:

```text
current collection uncomposable
→ CAPTURE_NOT_WRITTEN
→ no metadata file
→ no report file
→ no preflight
```

Test report output missing parent:

```text
capture and metadata writes succeed
preflight succeeds
report output OSError propagates
no missing report parent is created
metadata/bundle files remain written
```

## Source-Boundary Tests

Use AST or focused source inspection to prove the Phase 17D production module:

```text
imports only approved modules
does not import main or argparse
does not import config/environment/provider/factory/readiness
does not import HTTP transport or instantiate transport
does not import FMP
does not import Phase 16A loader
does not import Phase 16B CLI helper/exporter
does not import metadata source directly
does not import bundle writer directly
does not import lower workflow stages
does not import scanner/alerts/voice/trading modules
does not call resolve/absolute/expanduser/glob/rglob/mkdir
does not read environment
does not cache
does not call Path.read_text/read_bytes
does not call direct fetch_bars
does not call direct Path.write_text for metadata or bundle paths
```

The one permitted direct report write is `report_output_path.write_text(report, encoding="utf-8")`.

---

## README

Do not modify README. Phase 17D adds no user-facing CLI command.

---

## Validation

Run:

```powershell
python -m pytest tests/test_explicit_alpaca_rvol_capture_preflight.py
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
both readiness modes
```

No Phase 17D command is added.

---

## Acceptance Criteria

Phase 17D is complete when:

```text
- it performs no work until path checks, collision guards, and the exact live-data gate pass;
- invalid metadata representation errors occur before live fetch or any output write;
- it calls Phase 17B exactly once;
- capture failures leave metadata/report unwritten and preflight uncalled;
- successful capture writes metadata through Phase 17C exactly once;
- existing Phase 15H preflight runs exactly once using exact Phase 17B artifacts;
- successful and returned-failure preflight reports render deterministically;
- optional report output equals the returned report exactly;
- direct output-path collisions never touch caller files;
- no CLI, configuration, provider activation, scanner, alert, voice, FMP, automatic transport, or trading behavior is added;
- full project tests remain green.
```
