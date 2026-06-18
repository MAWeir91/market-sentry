# Phase 15C — Collected Pages to Manifest Workflow Orchestrator

## Status

**Planned.** This document defines Phase 15C only.

Phase 15A collects an ordered sequence of raw historical-bars pages. Phase 15B converts only a structurally complete collection into one terminal `AlpacaHistoricalBarsPage`. Phase 14J runs the established offline manifest-to-historical-TOD-RVOL workflow.

Phase 15C adds the narrow composition bridge between those completed paths:

```text
Phase 15A collection result
+ raw historical session manifest records
+ manifest request
+ current intraday series
+ harness request
        ↓
Phase 15B compose collected pages
        ↓
when a terminal raw page exists:
  Phase 14J manifest-to-harness workflow
        ↓
one immutable combined result
```

The orchestrator does not fetch pages, follow tokens, alter collection diagnostics, inspect raw bars, validate manifest records, calculate RVOL, or activate any runtime path.

---

## Goal

Create a pure offline orchestrator that:

1. calls Phase 15B composition exactly once for every invocation;
2. preserves the exact Phase 15B composition result object;
3. runs the existing Phase 14J workflow exactly once only when the composition result contains a real terminal composed page;
4. passes that exact composed page object to Phase 14J;
5. skips Phase 14J when no composed page exists;
6. preserves the exact Phase 14J result object when it runs;
7. clearly distinguishes:
   - collection/composition prevented a workflow run;
   - composition succeeded and the workflow ran, regardless of the workflow’s own internal status.

The intended path is:

```text
one-page historical fetcher
→ Phase 15A bounded page collection
→ Phase 15B terminal page composition
→ Phase 15C conditional workflow handoff
→ Phase 14J
→ Phase 14I manifest validation + Phase 14G TOD-RVOL harness
```

Phase 15C remains offline-callable only. It does not register this path with `live_composed`, the polling loop, or any provider factory.

---

## Core Ownership Boundary

```text
Phase 15A owns:
  page fetch sequencing
  continuation-token progression
  page cap
  repeated-token detection
  collection diagnostics

Phase 15B owns:
  collection eligibility for composition
  page-shape compatibility
  opaque raw-bar sequence concatenation
  composition diagnostics

Phase 14J owns:
  Phase 14I → Phase 14G call flow
  manifest/harness outcome classification
  manifest and RVOL workflow artifacts

Phase 15C owns:
  one Phase 15B call
  conditional Phase 14J handoff
  exact artifact retention
  workflow-ran versus collection-not-composable classification
```

Phase 15C must not:

```text
reinterpret collection or composition statuses
repair incomplete collections
synthesize an empty page
run Phase 14J after composition fails
inspect raw historical bars
inspect manifest records
revalidate requests
alter current series
inspect Phase 14J internals
flatten diagnostics
calculate score, RVOL, or any market metric
```

---

## Hard Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is **not** a trading bot.

Do not add:

```text
runtime activation
provider-factory registration or provider-selection changes
new MARKET_SENTRY_PROVIDER values
CLI flags, reports, polling, scanner-loop, alert, or voice changes
HTTP requests, fetcher construction, transport construction, pagination progression,
retries, caching, WebSockets, or streaming
environment/config reads
automatic watchlist lookup or broad-market discovery
calendar, holiday, early-close, halt, split, or market-session inference
time-zone conversion or normalization
raw-bar parsing, validation, sorting, deduplication, filtering, or repair
manifest validation logic
direct Phase 14D / 14E / 14F calls
direct Phase 14I adapter calls
relative-volume calculation
candidate composition, scoring, filtering, alerts, or voice changes
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

No live HTTP calls are permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

## Existing Components to Reuse

Use only these public interfaces and input models:

```text
market_sentry.data.collected_historical_pages_composer
  CollectedHistoricalPagesCompositionResult
  CollectedHistoricalPagesCompositionStatus
  compose_collected_historical_pages

market_sentry.data.historical_bars_page_collector
  HistoricalBarsPageCollectionResult

market_sentry.data.historical_session_manifest
  HistoricalSessionManifestRequest

market_sentry.data.historical_tod_rvol_harness
  HistoricalToTodRvolRunRequest

market_sentry.data.intraday_bucket_adapter
  IntradayVolumeSeriesInput

market_sentry.data.manifest_to_harness_orchestrator
  ManifestToHarnessResult
  run_manifest_to_historical_tod_rvol
```

Do not import or call:

```text
AlpacaHistoricalBarsFetcher
AlpacaHistoricalBarsPage directly as a constructed object
AlpacaHistoricalBarsQuery
HTTP transport modules
raw historical-bar adapters
adapt_historical_session_manifest
run_historical_to_time_of_day_rvol
assemble_historical_sessions_from_page
compose_historical_baseline
compose_current_session_time_of_day_rvol
time_of_day_rvol calculations
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

Phase 15C must not construct or mutate a terminal page itself. Phase 15B owns all composition.

---

## Expected Files

Create:

```text
docs/52_COLLECTED_PAGES_TO_MANIFEST_WORKFLOW_ORCHESTRATOR.md
src/market_sentry/data/collected_pages_to_manifest_workflow.py
tests/test_collected_pages_to_manifest_workflow.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 14A–14K, Phase 15A–15B, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Model

Use a frozen dataclass and an explicit stable status container.

```python
@dataclass(frozen=True)
class CollectedPagesToManifestWorkflowResult:
    """Composition artifact and, when eligible, the exact downstream workflow artifact."""

    source_collection: HistoricalBarsPageCollectionResult
    composition_result: CollectedHistoricalPagesCompositionResult
    workflow_result: ManifestToHarnessResult | None
    status: str
    reason: str | None = None
```

Exact names may vary, but retain all responsibilities:

```text
exact original collection object
exact Phase 15B composition result object
exact Phase 14J result object or None
one stable 15C-level status
one stable 15C-level reason
```

Do not duplicate raw page data, collection diagnostics, manifest diagnostics, or RVOL diagnostics into this result. Those remain in the exact lower-stage artifacts.

---

## Public Function

Provide:

```python
def run_collected_pages_to_manifest_workflow(
    collection: HistoricalBarsPageCollectionResult,
    raw_manifest_records: Sequence[object],
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> CollectedPagesToManifestWorkflowResult:
    ...
```

The orchestrator must first call:

```python
composition_result = compose_collected_historical_pages(collection)
```

exactly once.

Then:

```text
if composition_result.status == COMPOSED:
  workflow_result = run_manifest_to_historical_tod_rvol(
      raw_manifest_records,
      manifest_request,
      composition_result.composed_page,
      current_series,
      harness_request,
  )
else:
  workflow_result = None
```

When the composition status is `COMPOSED`, `composition_result.composed_page` must be non-null. The code may assert this narrow invariant or use a local guard that raises `RuntimeError` only for an internally inconsistent mocked result. It must not build a substitute page.

The exact composed page object returned by Phase 15B must be passed to Phase 14J by identity.

---

## Stable Phase 15C Statuses

Use exactly:

```text
WORKFLOW_RAN
COLLECTION_NOT_COMPOSABLE
```

### 1. Composition succeeded

When:

```text
composition_result.status == COMPOSED
```

return:

```text
status = WORKFLOW_RAN
reason = None
workflow_result = exact Phase 14J result object
```

`WORKFLOW_RAN` does **not** imply the Phase 14J workflow itself succeeded. Its detailed status remains in:

```text
workflow_result.status
workflow_result.reason
```

Examples:

```text
COMPOSED + workflow OK
→ 15C WORKFLOW_RAN
→ Phase 14J status OK

COMPOSED + workflow MANIFEST_PARTIAL
→ 15C WORKFLOW_RAN
→ Phase 14J status MANIFEST_PARTIAL

COMPOSED + workflow MANIFEST_FAILED
→ 15C WORKFLOW_RAN
→ Phase 14J status MANIFEST_FAILED

COMPOSED + workflow HARNESS_FAILED
→ 15C WORKFLOW_RAN
→ Phase 14J status HARNESS_FAILED
```

Phase 15C must not reclassify those workflow outcomes.

### 2. Composition did not succeed

When:

```text
composition_result.status != COMPOSED
```

return:

```text
status = COLLECTION_NOT_COMPOSABLE
reason = COLLECTION_NOT_COMPOSABLE:<exact composition_result.status>
workflow_result = None
```

This includes:

```text
INCOMPLETE_COLLECTION
EMPTY_COMPLETE_COLLECTION
MISMATCHED_PAGE_REQUESTED_SYMBOLS
```

Do not run Phase 14J. Do not fabricate a page. Do not make a workflow result with synthetic errors.

No other 15C statuses are permitted. An unexpected future composition status that is not `COMPOSED` must follow the same safe branch.

---

## Artifact and Identity Preservation

Phase 15C must preserve:

```text
exact collection object supplied by caller
exact composition_result object returned by Phase 15B
exact workflow_result object returned by Phase 14J, when run
exact raw_manifest_records object forwarded to Phase 14J
exact manifest_request object forwarded to Phase 14J
exact composed_page object forwarded to Phase 14J
exact current_series object forwarded to Phase 14J
exact harness_request object forwarded to Phase 14J
```

It must not:

```text
copy or tuple-wrap raw manifest records
reconstruct requests
copy the composition result
build a new page
inspect page raw sequences
clone workflow output
filter or adjust manifest records
repair mismatched inputs
```

`source_collection` must be the exact same object as `composition_result.source_collection` under the real Phase 15B contract. Phase 15C does not need to independently validate this lower-stage invariant.

The result model must be frozen. No cache or shared mutable state is permitted.

---

## Conditional Execution Policy

Phase 15C deliberately differs from Phase 14J’s “always run downstream” rule.

```text
Phase 14J:
  a manifest adapter result always exists
  so it always calls its harness

Phase 15C:
  a terminal historical page may not exist
  so it must not call the manifest workflow without one
```

The rule is:

```text
real composed terminal page exists
→ run downstream workflow exactly once

no composed terminal page
→ preserve composition diagnostics
→ skip downstream workflow entirely
```

This prevents incomplete or incompatible raw historical collections from being misrepresented as a valid terminal historical page.

---

## Required Tests

### Unit call-flow and artifact tests

Monkeypatch only these two public dependencies inside the Phase 15C module:

```text
compose_collected_historical_pages
run_manifest_to_historical_tod_rvol
```

Test:

```text
composition function called exactly once for every invocation
workflow function called exactly once when composition returns COMPOSED
workflow function not called when composition returns a non-COMPOSED status
collection forwarded by identity to Phase 15B
raw manifest records forwarded by identity to Phase 14J
manifest request forwarded by identity
exact composed page forwarded by identity
current series forwarded by identity
harness request forwarded by identity
exact composition result retained
exact workflow result retained
source collection retained by identity
result model frozen
no shared mutable state
```

### Phase 15C status mapping tests

Cover:

```text
COMPOSED + workflow status OK
→ WORKFLOW_RAN / None

COMPOSED + workflow status MANIFEST_PARTIAL
→ WORKFLOW_RAN / None

COMPOSED + workflow status MANIFEST_FAILED
→ WORKFLOW_RAN / None

COMPOSED + workflow status HARNESS_FAILED
→ WORKFLOW_RAN / None

INCOMPLETE_COLLECTION
→ COLLECTION_NOT_COMPOSABLE
→ COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION
→ workflow None

EMPTY_COMPLETE_COLLECTION
→ COLLECTION_NOT_COMPOSABLE
→ COLLECTION_NOT_COMPOSABLE:EMPTY_COMPLETE_COLLECTION
→ workflow None

MISMATCHED_PAGE_REQUESTED_SYMBOLS
→ COLLECTION_NOT_COMPOSABLE
→ COLLECTION_NOT_COMPOSABLE:MISMATCHED_PAGE_REQUESTED_SYMBOLS
→ workflow None

unexpected non-COMPOSED status
→ COLLECTION_NOT_COMPOSABLE
→ workflow None
```

Use real lower-stage status values in test artifacts where practical.

### Composed-page invariant test

With a patched `COMPOSED` result whose `composed_page` is unexpectedly `None`:

```text
raise RuntimeError
do not call Phase 14J
```

This is only an internal-invariant defense. It is not a new user-facing composition status and does not replace Phase 15B diagnostics.

### Actual integration-style tests

Use actual Phase 15B and Phase 14J with deterministic local artifacts only.

1. **Fully valid path**

```text
complete two-page collection
+ 20 valid raw manifest records
+ valid current series
+ valid harness request
→ composition COMPOSED
→ Phase 14J runs
→ Phase 15C WORKFLOW_RAN
→ Phase 14J status OK
→ final RVOL 2.0
```

Make at least one historical session’s raw bars span the two source pages so the test proves composition plus downstream use of the composed page.

2. **Collection incomplete: workflow must not run**

```text
MAX_PAGE_LIMIT_REACHED collection
+ otherwise valid manifest/current/request inputs
→ composition INCOMPLETE_COLLECTION
→ Phase 15C COLLECTION_NOT_COMPOSABLE
→ workflow_result None
```

Use a monkeypatch/wrapper or a dedicated test seam to prove no Phase 14J call occurred while retaining real Phase 15B behavior.

3. **Composed page + partial manifest**

```text
complete collection
+ 20 valid manifest records
+ one invalid manifest record
+ valid current series
→ composition COMPOSED
→ Phase 14J runs
→ Phase 15C WORKFLOW_RAN
→ Phase 14J status MANIFEST_PARTIAL
→ final RVOL 2.0
```

This proves 15C does not absorb or rewrite Phase 14J classification.

4. **Composed page + workflow failure**

```text
complete collection
+ 20 valid manifest records
+ current series with invalid selected volume False
→ composition COMPOSED
→ Phase 14J runs
→ Phase 15C WORKFLOW_RAN
→ Phase 14J status HARNESS_FAILED
→ final current cumulative volume failure retained
```

No HTTP, fetcher, transport, provider, runtime, or global fixture change.

### Source-boundary test

Use AST or focused source inspection to verify Phase 15C:

```text
imports only approved Phase 15B / 14J public interfaces and input models
does not import/call Phase 15A fetcher/collector execution
does not import/call raw bar adapters
does not import/call Phase 14I adapter, Phase 14G harness,
Phase 14D / 14E / 14F functions, or Phase 13 calculators
does not import HTTP, transport, provider, factory, config,
readiness, runtime, scanner, alert, voice, candidate, or trading modules
does not inspect page bars or manifest-record fields
does not rebuild a terminal page
```

---

## README Note

Update only if useful:

```text
Phase 15C adds an offline bridge from Phase 15B's complete historical-page composition result into the existing Phase 14J manifest-to-TOD-RVOL workflow.
It runs the workflow only when a real terminal composed page exists, preserving collection/composition diagnostics otherwise.
It does not fetch data, construct manifests, activate a runtime provider, or add trading/order functionality.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 15C is complete when:

```text
- Phase 15B composition runs exactly once for every invocation;
- Phase 14J runs exactly once only when Phase 15B returns COMPOSED with a real page;
- exact collection, composition, composed-page, and workflow artifacts are retained;
- non-composable collections produce stable 15C diagnostics with no workflow execution;
- Phase 14J outcomes remain visible and unmodified beneath WORKFLOW_RAN;
- integration tests cover complete valid, incomplete/no-workflow, partial-manifest, and workflow-failure paths;
- no fetcher/transport, raw-bar adaptation, metadata validation, RVOL, runtime/provider, scanner, alert, voice, or trading behavior is added;
- the full project suite remains green.
```
