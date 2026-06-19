# Phase 15E — Metadata-Loaded Historical Workflow Orchestrator

## Status

**Planned.** This document defines Phase 15E only.

Phase 15D loads one explicit raw historical-session metadata record sequence from an injected source. Phase 15C conditionally runs the existing historical manifest/TOD-RVOL workflow after it receives that sequence.

Phase 15E adds the narrow offline orchestrator between those completed boundaries:

```text
metadata source
+ manifest request
+ Phase 15A collection
+ current intraday series
+ harness request
        ↓
Phase 15D metadata source load
        ↓
when the source load is LOADED:
  Phase 15C workflow bridge
        ↓
one immutable combined result
```

It does not fetch metadata, infer calendar facts, create metadata records, run Phase 14J directly, calculate RVOL, or activate a runtime path.

---

## Goal

Create a pure offline orchestrator that:

1. calls Phase 15D metadata loading exactly once for every invocation;
2. preserves the exact metadata source, manifest request, and metadata-load result;
3. runs Phase 15C exactly once only when Phase 15D returns a usable loaded record sequence;
4. passes the exact loaded sequence to Phase 15C by identity;
5. preserves the exact Phase 15C workflow-bridge result when it runs;
6. skips Phase 15C when the metadata source does not return a usable sequence;
7. clearly distinguishes:
   - metadata did not load, so no workflow bridge was invoked;
   - metadata loaded, so the Phase 15C bridge was invoked, regardless of its own lower-stage outcome.

The intended offline path is:

```text
explicit metadata source
→ Phase 15D load
→ Phase 15E conditional bridge handoff
→ Phase 15C
→ Phase 15B composition + Phase 14J workflow
→ manifest + TOD-RVOL artifacts
```

Phase 15E remains offline-callable only. It does not register this path with `live_composed`, a provider factory, the polling loop, or the CLI.

---

## Core Ownership Boundary

```text
Phase 15D owns:
  metadata-source invocation
  record-sequence container safety
  source-load diagnostics
  exact source/request/sequence retention

Phase 15C owns:
  Phase 15B composition invocation
  conditional Phase 14J handoff
  collection/composition/workflow artifacts

Phase 15E owns:
  one Phase 15D call
  conditional Phase 15C handoff
  exact artifact retention
  metadata-not-loaded versus workflow-bridge-ran classification
```

Phase 15E must not:

```text
call the metadata source method directly
reinterpret Phase 15D source-load statuses
repair an invalid record sequence
synthesize an empty metadata sequence
inspect metadata record mappings or fields
inspect the manifest request
inspect collection pages or bars
inspect Phase 15C internals
call Phase 15B or Phase 14J directly
flatten lower-stage diagnostics
calculate RVOL, scores, or any market metric
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
HTTP requests, API clients, transports, fetchers, retries, caching,
WebSockets, streaming, files, JSON/YAML loaders, or environment/config reads
calendar, holiday, early-close, halt, split, or market-session inference
time-zone conversion or normalization
raw-bar parsing, validation, sorting, deduplication, filtering, or repair
metadata-record validation, normalization, filtering, or construction
Phase 15A collection calls
Phase 15B composition calls
Phase 14I / 14J / 14G / 14D / 14E / 14F direct calls
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
market_sentry.data.historical_session_metadata_source
  HistoricalSessionMetadataSource
  HistoricalSessionMetadataSourceLoadResult
  HistoricalSessionMetadataSourceLoadStatus
  load_historical_session_metadata_source

market_sentry.data.collected_pages_to_manifest_workflow
  CollectedPagesToManifestWorkflowResult
  run_collected_pages_to_manifest_workflow

market_sentry.data.historical_bars_page_collector
  HistoricalBarsPageCollectionResult

market_sentry.data.historical_session_manifest
  HistoricalSessionManifestRequest

market_sentry.data.intraday_bucket_adapter
  IntradayVolumeSeriesInput

market_sentry.data.historical_tod_rvol_harness
  HistoricalToTodRvolRunRequest
```

Do not import or call:

```text
StaticHistoricalSessionMetadataSource directly in production
adapt_historical_session_manifest
HistoricalSessionManifestResult
historical_session_assembly
alpaca_historical_bars_fetcher
alpaca_historical_bars_adapter
historical_bars_page_collector execution
collected_historical_pages_composer
manifest_to_harness_orchestrator
historical_tod_rvol_harness execution
intraday_bucket_adapter functions
time_of_day_rvol
HTTP transport modules
fetchers
provider factory
config
live readiness
relative-volume modules
fixture providers
LiveCandidateBuilder
LiveComposedMarketDataProvider
scanner engine
alert modules
voice modules
```

Phase 15E must not construct or mutate a metadata source, record sequence, terminal page, or manifest result.

---

## Expected Files

Create:

```text
docs/54_METADATA_LOADED_HISTORICAL_WORKFLOW_ORCHESTRATOR.md
src/market_sentry/data/metadata_loaded_historical_workflow.py
tests/test_metadata_loaded_historical_workflow.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 14A–14K, Phase 15A–15D, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Model

Use a frozen dataclass and explicit stable status container.

```python
@dataclass(frozen=True)
class MetadataLoadedHistoricalWorkflowResult:
    """Metadata source-load artifact and, when eligible, exact Phase 15C artifact."""

    metadata_source: HistoricalSessionMetadataSource
    source_collection: HistoricalBarsPageCollectionResult
    metadata_load_result: HistoricalSessionMetadataSourceLoadResult
    workflow_bridge_result: CollectedPagesToManifestWorkflowResult | None
    status: str
    reason: str | None = None
```

Exact names may vary, but retain all responsibilities:

```text
exact source object
exact original collection object
exact Phase 15D load result object
exact Phase 15C bridge result object or None
one stable Phase 15E status
one stable Phase 15E reason
```

Do not duplicate raw metadata records, pages, collection diagnostics, manifest diagnostics, or RVOL diagnostics. They remain accessible inside the exact lower-stage artifacts.

---

## Public Function

Provide:

```python
def run_metadata_loaded_historical_workflow(
    metadata_source: HistoricalSessionMetadataSource,
    collection: HistoricalBarsPageCollectionResult,
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> MetadataLoadedHistoricalWorkflowResult:
    ...
```

The orchestrator must first call:

```python
metadata_load_result = load_historical_session_metadata_source(
    metadata_source,
    manifest_request,
)
```

exactly once.

Then:

```text
if metadata_load_result.status == LOADED:
  use exact metadata_load_result.raw_manifest_records
  run Phase 15C exactly once
else:
  do not run Phase 15C
```

When the load status is `LOADED`, `metadata_load_result.raw_manifest_records` must be non-null. The code may assert this narrow invariant or use a local guard that raises `RuntimeError` only for an internally inconsistent mocked result. It must not synthesize a replacement sequence.

For a loaded result, call exactly:

```python
workflow_bridge_result = run_collected_pages_to_manifest_workflow(
    collection,
    metadata_load_result.raw_manifest_records,
    manifest_request,
    current_series,
    harness_request,
)
```

The exact loaded sequence object must be passed to Phase 15C by identity.

---

## Stable Phase 15E Statuses

Use exactly:

```text
WORKFLOW_BRIDGE_RAN
METADATA_NOT_LOADED
```

### 1. Metadata loaded

When:

```text
metadata_load_result.status == HistoricalSessionMetadataSourceLoadStatus.LOADED
```

return:

```text
status = WORKFLOW_BRIDGE_RAN
reason = None
workflow_bridge_result = exact Phase 15C result object
```

`WORKFLOW_BRIDGE_RAN` means only that Phase 15C was invoked. It does not imply Phase 15C reached Phase 14J.

Examples:

```text
metadata LOADED + 15C WORKFLOW_RAN + Phase 14J OK
→ 15E WORKFLOW_BRIDGE_RAN

metadata LOADED + 15C WORKFLOW_RAN + Phase 14J MANIFEST_PARTIAL
→ 15E WORKFLOW_BRIDGE_RAN

metadata LOADED + 15C WORKFLOW_RAN + Phase 14J HARNESS_FAILED
→ 15E WORKFLOW_BRIDGE_RAN

metadata LOADED + 15C COLLECTION_NOT_COMPOSABLE
→ 15E WORKFLOW_BRIDGE_RAN
→ Phase 15C carries the collection diagnostic
```

Phase 15E must not reclassify any Phase 15C or lower-stage outcome.

### 2. Metadata did not load

When:

```text
metadata_load_result.status != LOADED
```

return:

```text
status = METADATA_NOT_LOADED
reason = METADATA_NOT_LOADED:<exact metadata_load_result.status>
workflow_bridge_result = None
```

This includes:

```text
INVALID_RECORD_SEQUENCE
```

No Phase 15C call is permitted. No synthetic bridge result is allowed.

An unexpected future source-load status that is not `LOADED` must follow the same safe branch.

No other Phase 15E statuses are permitted.

---

## Artifact and Identity Preservation

Phase 15E must preserve:

```text
exact metadata source object supplied by caller
exact source collection object supplied by caller
exact metadata-load result object returned by Phase 15D
exact workflow-bridge result object returned by Phase 15C, when run
exact manifest request object forwarded to Phase 15D and Phase 15C
exact loaded raw metadata sequence object forwarded to Phase 15C
exact current series object forwarded to Phase 15C
exact harness request object forwarded to Phase 15C
```

It must not:

```text
copy or tuple-wrap the metadata sequence
reconstruct requests
rebuild a metadata source
build a terminal page
inspect record mappings or collection pages
clone workflow output
filter or adjust metadata records
repair mismatched inputs
```

`metadata_source` must be the exact same object as `metadata_load_result.source` under the real Phase 15D contract. Phase 15E does not need to independently validate this lower-stage invariant.

The result model must be frozen. No cache or shared mutable state is permitted.

---

## Conditional Execution Policy

Phase 15E deliberately differs from Phase 15C:

```text
Phase 15C:
  has a raw metadata record sequence as an input
  conditionally calls Phase 14J only when a terminal page exists

Phase 15E:
  may not have a usable metadata record sequence
  conditionally calls Phase 15C only when Phase 15D loaded one
```

The rule is:

```text
real loaded metadata sequence exists
→ run Phase 15C exactly once

no usable loaded metadata sequence
→ preserve Phase 15D diagnostic
→ skip Phase 15C entirely
```

This prevents an invalid source container from being silently converted into a valid empty metadata sequence.

---

## Required Tests

### Unit call-flow and artifact tests

Monkeypatch only these two public dependencies inside the Phase 15E module:

```text
load_historical_session_metadata_source
run_collected_pages_to_manifest_workflow
```

Test:

```text
metadata loader called exactly once for every invocation
workflow bridge called exactly once when load result is LOADED
workflow bridge not called when load result has a non-LOADED status
metadata source forwarded by identity to Phase 15D
manifest request forwarded by identity to Phase 15D
collection forwarded by identity to Phase 15C
exact loaded metadata sequence forwarded by identity to Phase 15C
manifest request forwarded by identity to Phase 15C
current series forwarded by identity to Phase 15C
harness request forwarded by identity to Phase 15C
exact metadata-load result retained
exact workflow-bridge result retained
source and collection retained by identity
result model frozen
no shared mutable state
```

### Phase 15E status mapping tests

Cover:

```text
LOADED + Phase 15C WORKFLOW_RAN
→ WORKFLOW_BRIDGE_RAN / None

LOADED + Phase 15C COLLECTION_NOT_COMPOSABLE
→ WORKFLOW_BRIDGE_RAN / None

INVALID_RECORD_SEQUENCE
→ METADATA_NOT_LOADED
→ METADATA_NOT_LOADED:INVALID_RECORD_SEQUENCE
→ workflow bridge None

unexpected non-LOADED status
→ METADATA_NOT_LOADED
→ workflow bridge None
```

### Loaded-sequence invariant test

With a patched `LOADED` load result whose `raw_manifest_records` is unexpectedly `None`:

```text
raise RuntimeError
do not call Phase 15C
```

This is only an internal-invariant defense. It does not replace Phase 15D diagnostics or introduce a new user-facing Phase 15E status.

### Source exception propagation test

With a patched loader that raises:

```text
ValueError
custom exception
```

assert the exact exception propagates unchanged and Phase 15C is not called.

### Actual integration-style tests

Use actual Phase 15D and actual Phase 15C with deterministic local artifacts only.

1. **Fully valid path**

```text
StaticHistoricalSessionMetadataSource
+ exact tuple of 20 valid raw manifest records
+ complete two-page collection
+ valid current series
+ valid harness request
→ Phase 15D LOADED
→ Phase 15C runs
→ Phase 15E WORKFLOW_BRIDGE_RAN
→ Phase 15C WORKFLOW_RAN
→ Phase 14J status OK
→ final RVOL 2.0
```

At least one historical session’s raw bars must span both source pages.

2. **Invalid source container: bridge must not run**

```text
custom local metadata source returns a mapping or generator
+ otherwise-valid collection/current/request inputs
→ Phase 15D INVALID_RECORD_SEQUENCE
→ Phase 15E METADATA_NOT_LOADED
→ workflow_bridge_result None
```

Use a monkeypatch/wrapper or a dedicated test seam to prove no Phase 15C call occurred while retaining real Phase 15D behavior.

3. **Loaded source + incomplete collection**

```text
StaticHistoricalSessionMetadataSource
+ valid raw metadata sequence
+ MAX_PAGE_LIMIT_REACHED collection
→ Phase 15D LOADED
→ Phase 15C runs
→ Phase 15E WORKFLOW_BRIDGE_RAN
→ Phase 15C COLLECTION_NOT_COMPOSABLE
→ no Phase 14J result inside Phase 15C
```

This proves Phase 15E preserves Phase 15C’s lower-stage diagnostic instead of overriding it.

4. **Loaded source + partial manifest**

```text
StaticHistoricalSessionMetadataSource
+ 20 valid manifest records
+ one invalid manifest record
+ complete collection
+ valid current series
→ Phase 15D LOADED
→ Phase 15C runs
→ Phase 15E WORKFLOW_BRIDGE_RAN
→ Phase 15C WORKFLOW_RAN
→ Phase 14J status MANIFEST_PARTIAL
→ final RVOL 2.0
```

5. **Loaded source + workflow failure**

```text
StaticHistoricalSessionMetadataSource
+ 20 valid manifest records
+ complete collection
+ current series with invalid selected volume False
→ Phase 15D LOADED
→ Phase 15C runs
→ Phase 15E WORKFLOW_BRIDGE_RAN
→ Phase 15C WORKFLOW_RAN
→ Phase 14J status HARNESS_FAILED
→ final current cumulative-volume failure retained
```

No HTTP, fetcher, transport, provider, runtime, or global fixture change.

### Source-boundary test

Use AST or focused source inspection to verify Phase 15E:

```text
imports only approved Phase 15D / 15C public interfaces and input models
does not import/call metadata source methods directly
does not import/call Phase 15A execution, Phase 15B composition,
Phase 14I adapter, Phase 14J, Phase 14G harness,
Phase 14D / 14E / 14F functions, or Phase 13 calculators
does not import HTTP, transport, provider, factory, config,
readiness, runtime, scanner, alert, voice, candidate, or trading modules
does not inspect metadata record fields, request fields, collection pages, or raw bars
does not build metadata sequences or terminal pages
```

---

## README Note

Update only if useful:

```text
Phase 15E adds an offline orchestrator that loads explicit historical-session metadata through Phase 15D and invokes the existing Phase 15C workflow bridge only when a usable record sequence was loaded.
It preserves source-load and lower-stage workflow diagnostics without inferring calendar/session facts, activating a runtime provider, or adding trading/order functionality.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 15E is complete when:

```text
- Phase 15D load runs exactly once for every invocation;
- Phase 15C runs exactly once only when Phase 15D returns LOADED with a real sequence;
- exact source, collection, load-result, metadata-sequence, and bridge-result artifacts are retained;
- invalid source containers produce stable Phase 15E diagnostics with no bridge execution;
- Phase 15C and lower-stage outcomes remain visible and unmodified beneath WORKFLOW_BRIDGE_RAN;
- integration tests cover valid, invalid-source/no-bridge, loaded/incomplete-collection,
  partial-manifest, and workflow-failure paths;
- no metadata validation, calendar/session inference, fetcher/transport, raw-bar adaptation,
  RVOL, runtime/provider, scanner, alert, voice, or trading behavior is added;
- the full project suite remains green.
```
