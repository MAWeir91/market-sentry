# Phase 14J — Offline Manifest-to-Harness Orchestrator

## Status

**Planned.** This document defines Phase 14J only.

Phase 14I validates caller-supplied historical session manifest data and emits ordered `HistoricalIntradaySessionMetadata` records. Phase 14G runs the offline historical-to-time-of-day relative-volume pipeline from explicit metadata records.

Phase 14J adds a deliberately thin coordinator:

```text
raw manifest records
+ Phase 14I manifest request
+ raw historical bars page
+ current intraday series
+ Phase 14G run request
→ Phase 14I manifest result
→ emitted metadata tuple only
→ Phase 14G harness result
→ one immutable combined result
```

The coordinator does not create new metadata, inspect raw bars, execute lower-level Phase 14D/14E/14F stages directly, calculate RVOL, infer request consistency, or activate runtime behavior.

---

## Goal

Create a pure offline composition layer that:

1. calls the Phase 14I manifest adapter exactly once;
2. passes the manifest adapter’s exact emitted `metadata_records` tuple to the Phase 14G harness exactly once;
3. runs Phase 14G even when Phase 14I returns an invalid request, no-valid-metadata result, or partial result;
4. preserves the exact Phase 14I and Phase 14G artifacts without cloning, filtering, sorting, repairing, or synthesizing them;
5. supplies a small coordinator-level status that makes manifest quality and harness execution ownership explicit.

The future workflow becomes:

```text
caller manifest mappings
→ Phase 14I validation + diagnostics
→ Phase 14J coordinator
→ Phase 14G harness
→ 14D assembly
→ 14E historical baseline
→ 14F current-session TOD RVOL
```

Phase 14J adds no runtime call path to this workflow. It is an offline callable utility only.

---

## Core Ownership Boundary

```text
Phase 14I owns:
  manifest request validation
  mapping-field validation
  duplicate policy
  timestamp compatibility
  session window/cutoff/completion rules
  emitted metadata records
  manifest diagnostics

Phase 14G owns:
  14D session assembly
  14E baseline composition
  14F current-session final TOD RVOL composition
  harness diagnostics

Phase 14J owns:
  one Phase 14I call
  one Phase 14G call
  exact artifact retention
  top-level manifest/harness outcome classification only
```

Phase 14J must not:

```text
revalidate manifest records
revalidate either request
compare, align, or reconcile manifest and harness request identities
inspect raw page details, page tokens, bars, timestamps, or session windows
inspect current-series bars
inspect or transform emitted metadata records
inspect or transform Phase 14D/14E/14F internals
fabricate diagnostics or alter stage statuses
```

If the manifest request and harness run request do not agree on symbol, bucket, or current-session identity, Phase 14J forwards both unchanged. The real Phase 14G path owns any resulting execution outcome. The coordinator must not infer or repair consistency.

---

## Hard Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is **not** a trading bot.

Do not add:

```text
runtime activation
provider-factory registration or provider-selection changes
new MARKET_SENTRY_PROVIDER values
CLI flags, reports, polling, scanner-loop, alert, or voice changes
HTTP requests, fetcher construction, pagination, retries, caching, WebSockets, or streaming
environment/config reads
automatic watchlist lookup or broad-market discovery
calendar, holiday, early-close, halt, split, or market-session inference
time-zone conversion or normalization
raw-bar parsing or historical-page inspection
direct Phase 14D assembly calls
direct Phase 14E baseline-composition calls
direct Phase 14F current-session/TOD-RVOL calls
new RVOL calculations
candidate composition, scoring, filtering, or alerts
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

`live_composed` remains gated and reserved/inactive.

---

## Existing Components to Reuse

The coordinator may use only these public Phase 14 interfaces and input models:

```text
market_sentry.data.historical_session_manifest
  HistoricalSessionManifestRequest
  HistoricalSessionManifestResult
  HistoricalSessionManifestStatus
  adapt_historical_session_manifest

market_sentry.data.historical_tod_rvol_harness
  HistoricalToTodRvolRunRequest
  HistoricalToTodRvolRunResult
  HistoricalToTodRvolRunStatus
  run_historical_to_time_of_day_rvol

market_sentry.data.alpaca_historical_bars_fetcher
  AlpacaHistoricalBarsPage

market_sentry.data.intraday_bucket_adapter
  IntradayVolumeSeriesInput
```

Do not import or call:

```text
assemble_historical_sessions_from_page
historical_session_assembly internals
compose_historical_baseline
historical_baseline_composition internals
compose_current_session_time_of_day_rvol
current_session_tod_rvol internals
time_of_day_rvol calculations
raw bar adapters
HTTP transports
fetchers other than the page input model above
provider factory
config
live readiness
fixture providers
LiveCandidateBuilder
LiveComposedMarketDataProvider
scanner engine
alert modules
voice modules
```

The coordinator must not invoke any lower-level Phase 14D/14E/14F function directly.

---

## Expected Files

Create:

```text
docs/48_OFFLINE_MANIFEST_TO_HARNESS_ORCHESTRATOR.md
src/market_sentry/data/manifest_to_harness_orchestrator.py
tests/test_manifest_to_harness_orchestrator.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 13, Phase 14A–14I, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Models

Use frozen dataclasses and stable status containers.

```python
@dataclass(frozen=True)
class ManifestToHarnessResult:
    """Combined immutable artifacts from Phase 14I and Phase 14G."""

    manifest_result: HistoricalSessionManifestResult
    harness_result: HistoricalToTodRvolRunResult
    status: str
    reason: str | None = None
```

Exact name may vary, but retain all responsibilities:

```text
exact Phase 14I result object
exact Phase 14G result object
one stable coordinator-level status
one stable coordinator-level reason
```

Do not duplicate raw inputs, requests, diagnostics, metadata records, or lower-level status fields into this result. They remain available in the two exact stage artifacts.

---

## Public Function

Provide:

```python
def run_manifest_to_historical_tod_rvol(
    raw_manifest_records: Sequence[object],
    manifest_request: HistoricalSessionManifestRequest,
    page: AlpacaHistoricalBarsPage,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> ManifestToHarnessResult:
    ...
```

The coordinator must make exactly these two calls, in exactly this order:

```python
manifest_result = adapt_historical_session_manifest(
    raw_manifest_records,
    manifest_request,
)

harness_result = run_historical_to_time_of_day_rvol(
    page,
    manifest_result.metadata_records,
    current_series,
    harness_request,
)
```

Requirements:

```text
call Phase 14I exactly once
call Phase 14G exactly once
never early return
never conditionally skip Phase 14G
never tuple-wrap, copy, filter, sort, deduplicate, or mutate
manifest_result.metadata_records before passing it to Phase 14G
```

The exact `metadata_records` tuple object returned by Phase 14I must be the object passed to Phase 14G.

---

## Stable Coordinator Statuses

Use explicit stable status values:

```text
OK
MANIFEST_PARTIAL
MANIFEST_FAILED
HARNESS_FAILED
MANIFEST_PARTIAL_AND_HARNESS_FAILED
```

Map statuses after both calls have completed.

### 1. Fully valid manifest and successful harness

```text
manifest_result.status == OK
harness_result.status == OK
```

Return:

```text
status = OK
reason = None
```

### 2. Partial manifest and successful harness

```text
manifest_result.status == PARTIAL
harness_result.status == OK
```

Return:

```text
status = MANIFEST_PARTIAL
reason = MANIFEST_PARTIAL
```

This means emitted valid records were sufficient for a successful Phase 14G run, but the manifest still contains preserved failed-record diagnostics.

### 3. Failed manifest

A failed manifest is any Phase 14I result whose status is neither:

```text
OK
PARTIAL
```

This includes:

```text
NO_VALID_METADATA
INVALID_TARGET_SYMBOL
INVALID_TARGET_BUCKET
INVALID_CURRENT_SESSION_ID
```

Return:

```text
status = MANIFEST_FAILED
reason = MANIFEST_FAILED:<exact manifest_result.status>
```

`harness_result` is still required and must be preserved exactly. Its status is not hidden; callers inspect `harness_result` for the downstream consequence. Manifest failure has deliberate coordinator-level precedence because Phase 14I is the first failed ownership boundary.

### 4. Valid manifest and failed harness

```text
manifest_result.status == OK
harness_result.status != OK
```

Return:

```text
status = HARNESS_FAILED
reason = HARNESS_FAILED:<exact harness_result.status>
```

### 5. Partial manifest and failed harness

```text
manifest_result.status == PARTIAL
harness_result.status != OK
```

Return:

```text
status = MANIFEST_PARTIAL_AND_HARNESS_FAILED
reason = MANIFEST_PARTIAL_AND_HARNESS_FAILED:<exact harness_result.status>
```

No other coordinator statuses are permitted. Any unexpected future manifest status is handled as `MANIFEST_FAILED`; any unexpected future harness status that is not `OK` is handled as a harness failure.

The coordinator does not synthesize a combined reason containing lower-level field diagnostics. Those remain owned by the exact stage artifacts.

---

## Artifact Preservation Rules

The result must preserve:

```text
exact manifest_result object returned by Phase 14I
exact harness_result object returned by Phase 14G
```

And Phase 14G must receive:

```text
exact manifest_result.metadata_records tuple object
```

Do not:

```text
reconstruct request objects
clone raw mappings
clone or rebuild metadata records
convert metadata tuple to list or a new tuple
read/write nested diagnostics
inject source labels
flatten result fields
change status strings
```

The coordinator is a composition boundary, not a data repair boundary.

---

## Manifest and Harness Request Mismatch Policy

Phase 14J deliberately performs no cross-request consistency check.

Examples:

```text
manifest_request.symbol differs from harness_request.symbol
manifest_request.bucket differs from harness_request.bucket
manifest_request.current_session_id differs from harness_request.current_session_id
```

Phase 14J must:

```text
call Phase 14I unchanged
call Phase 14G unchanged with emitted metadata tuple
preserve both results
classify only the two stage statuses
```

It must not:

```text
block the run
create a new mismatch status
coerce identities
adjust current-session ID
filter emitted metadata
repair or reinterpret the results
```

A test must prove this pass-through behavior using monkeypatched Phase 14I and Phase 14G public functions.

---

## Required Tests

### Unit call-flow and artifact tests

Monkeypatch only these two Phase-level public functions inside the Phase 14J module:

```text
adapt_historical_session_manifest
run_historical_to_time_of_day_rvol
```

Test:

```text
Phase 14I called exactly once
Phase 14G called exactly once
calls occur in Phase 14I → Phase 14G order
raw manifest sequence forwarded by identity
manifest request forwarded by identity
page forwarded by identity
current series forwarded by identity
harness request forwarded by identity
exact manifest_result.metadata_records tuple forwarded by identity
exact result objects retained in final coordinator result
frozen coordinator model
no shared mutable state
```

### Coordinator status-mapping tests

Cover:

```text
manifest OK + harness OK
→ OK / None

manifest PARTIAL + harness OK
→ MANIFEST_PARTIAL / MANIFEST_PARTIAL

manifest failed + harness OK
→ MANIFEST_FAILED / MANIFEST_FAILED:<manifest status>

manifest failed + harness failed
→ MANIFEST_FAILED / MANIFEST_FAILED:<manifest status>

manifest OK + harness failed
→ HARNESS_FAILED / HARNESS_FAILED:<harness status>

manifest PARTIAL + harness failed
→ MANIFEST_PARTIAL_AND_HARNESS_FAILED
  / MANIFEST_PARTIAL_AND_HARNESS_FAILED:<harness status>
```

Use real phase status values in test artifacts, including:

```text
NO_VALID_METADATA
INVALID_TARGET_SYMBOL
BASELINE_FAILED
FINAL_COMPOSITION_FAILED
```

The tests should verify that unexpected non-OK manifest/harness status values follow the same fail-safe branch without adding new statuses.

### No-early-return tests

Specifically prove Phase 14G still runs:

```text
when the manifest request is invalid
when the manifest has no usable metadata
when the manifest is partial
```

Use patched Phase 14I result objects to make call ownership explicit.

### Actual integration-style tests

Use the real Phase 14I, real Phase 14G, and deterministic local data only.

1. **Fully valid run**

```text
20 valid raw manifest records
+ complete valid local raw page
+ valid current series
→ manifest status OK
→ harness status OK
→ coordinator status OK
→ final RVOL 2.0
```

2. **Partial manifest but successful harness**

```text
20 valid raw manifest records
+ one invalid manifest record (for example missing bucket)
+ complete valid local raw page for the 20 valid records
+ valid current series
→ manifest status PARTIAL
→ 20 emitted metadata records
→ harness status OK
→ coordinator status MANIFEST_PARTIAL
→ final RVOL 2.0
```

This test proves Phase 14J forwards only the actual Phase 14I emitted valid metadata and does not convert a partial manifest into a coordinator failure when the harness succeeds.

3. **Manifest failure still invokes real harness**

```text
invalid manifest request
+ local page/current series
→ manifest returns invalid-request status
→ emitted metadata tuple empty
→ actual harness still runs and returns its own outcome
→ coordinator status MANIFEST_FAILED
```

No network, provider, runtime, or global-fixture changes.

### Source-boundary test

Use AST or focused source inspection to confirm Phase 14J:

```text
imports only approved Phase 14I/14G public interfaces and input models
does not import/call Phase 14D, 14E, or 14F functions
does not import raw adapters, Phase 13 calculators, HTTP/fetcher/transport,
provider/factory/config/readiness/runtime/scanner/alert/voice/candidate/trading modules
does not inspect or copy raw bars or metadata records
```

---

## README Note

Update only if useful:

```text
Phase 14J adds an offline coordinator that runs the Phase 14I session-manifest adapter and Phase 14G historical-to-TOD-RVOL harness in sequence, preserving both artifacts and distinguishing complete, partial-manifest, manifest-failure, and harness-failure outcomes.
It does not fetch data, register a runtime provider, activate live mode, or add trading/order functionality.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 14J is complete when:

```text
- Phase 14I and Phase 14G are each called exactly once in order;
- Phase 14G always receives the exact emitted metadata tuple from Phase 14I;
- Phase 14G runs even after invalid/no-valid/partial manifest outcomes;
- coordinator status precedence and reasons follow this specification;
- exact Phase 14I and Phase 14G artifacts are retained;
- no new manifest validation, raw-bar logic, RVOL math, provider/runtime behavior, or trading functionality is added;
- real offline integration tests cover valid, partial-but-successful, and manifest-failure paths;
- the full project suite remains green.
```
