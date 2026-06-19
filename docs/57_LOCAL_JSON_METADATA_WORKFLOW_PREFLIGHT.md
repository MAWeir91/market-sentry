# Phase 15H — Local JSON Metadata Workflow Preflight

## Status

**Planned.** This document defines Phase 15H only.

Phase 15G provides an explicit caller-selected local JSON metadata source. Phase 15E provides the existing metadata-loaded historical workflow.

Phase 15H adds a tiny manually invoked convenience wrapper:

```text
explicit caller Path
+ explicit collection/current/harness inputs
        ↓
construct JsonHistoricalSessionMetadataFileSource
        ↓
call actual Phase 15E once
        ↓
one immutable preflight artifact
```

It does not parse JSON itself, inspect metadata records, add a CLI command, activate a provider, discover files, or create a new workflow path.

---

## Goal

Create a pure offline preflight wrapper that:

1. receives one exact caller-owned `Path` plus explicit existing workflow inputs;
2. constructs exactly one `JsonHistoricalSessionMetadataFileSource` from that exact path;
3. calls `run_metadata_loaded_historical_workflow(...)` exactly once;
4. forwards the exact constructed source and every explicit input by identity;
5. returns a frozen wrapper holding:
   - the exact original path;
   - the exact constructed JSON source;
   - the exact Phase 15E workflow artifact;
6. propagates source-construction, file, JSON, envelope, and Phase 15E exceptions unchanged;
7. adds no status mapping, diagnostic rewriting, or lower-stage result interpretation.

The intended manual path is:

```text
explicit local JSON metadata file
→ Phase 15H preflight wrapper
→ Phase 15G JSON source
→ Phase 15D metadata load
→ Phase 15E metadata gate
→ Phase 15C / 15B / 14J
→ inspectable TOD-RVOL workflow artifact
```

The wrapper is a direct code-level helper only. It is not wired into the CLI, provider factory, scanner, polling loop, alerts, or voice behavior.

---

## Core Ownership Boundary

```text
Phase 15G owns:
  local file read
  strict UTF-8 JSON parsing
  versioned envelope validation
  generic $datetime decoding

Phase 15D owns:
  metadata source invocation
  sequence-container safety
  metadata-load diagnostics

Phase 15E owns:
  conditional Phase 15C invocation
  metadata-not-loaded versus bridge-ran classification

Phase 15H owns:
  constructing the Phase 15G source from an explicit Path
  one Phase 15E call
  exact path/source/workflow artifact retention
```

Phase 15H must not:

```text
read the file directly
call source.load_raw_manifest_records directly
inspect JSON envelope values
inspect raw metadata mappings or fields
inspect the manifest request
inspect page collections, pages, raw bars, or current series fields
interpret Phase 15E, 15C, 15B, 14J, or lower-stage statuses
create substitute metadata records or pages
catch, wrap, retry, or transform exceptions
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
environment/config reads
automatic path lookup
directory scans, recursive search, globbing, file selection, or fallback files
HTTP requests, API clients, transports, fetchers, retries, caching,
WebSockets, or streaming
calendar, holiday, early-close, halt, split, or market-session inference
time-zone conversion or normalization
metadata-record validation, normalization, filtering, or construction
raw-bar parsing, validation, sorting, deduplication, filtering, or repair
Phase 15A collection calls
Phase 15B composition calls
Phase 15C / 15D direct calls
Phase 14I / 14J / 14G / 14D / 14E / 14F direct calls
relative-volume calculation
candidate composition, scoring, filtering, alerts, or voice changes
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

No live HTTP calls are permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

## Expected Files

Create:

```text
docs/57_LOCAL_JSON_METADATA_WORKFLOW_PREFLIGHT.md
src/market_sentry/data/local_json_metadata_workflow_preflight.py
tests/test_local_json_metadata_workflow_preflight.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 14A–14K, Phase 15A–15G, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Existing Components to Reuse

Use only these public interfaces and input models:

```text
market_sentry.data.json_historical_session_metadata_source
  JsonHistoricalSessionMetadataFileSource

market_sentry.data.metadata_loaded_historical_workflow
  MetadataLoadedHistoricalWorkflowResult
  run_metadata_loaded_historical_workflow

market_sentry.data.historical_bars_page_collector
  HistoricalBarsPageCollectionResult

market_sentry.data.historical_session_manifest
  HistoricalSessionManifestRequest

market_sentry.data.intraday_bucket_adapter
  IntradayVolumeSeriesInput

market_sentry.data.historical_tod_rvol_harness
  HistoricalToTodRvolRunRequest
```

Use standard-library modules only:

```text
dataclasses
pathlib
```

Do not import or call:

```text
JsonHistoricalSessionMetadataFileSourceError
load_historical_session_metadata_source
StaticHistoricalSessionMetadataSource
adapt_historical_session_manifest
HistoricalSessionManifestResult
historical_session_assembly
alpaca_historical_bars_fetcher
alpaca_historical_bars_adapter
historical_bars_page_collector execution
collected_historical_pages_composer
collected_pages_to_manifest_workflow
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

The production Phase 15H module must never import downstream internals or status containers.

---

## Public Model

Use a frozen dataclass:

```python
@dataclass(frozen=True)
class LocalJsonMetadataWorkflowPreflightResult:
    """One explicit path, one exact JSON source, and one exact Phase 15E artifact."""

    path: Path
    metadata_source: JsonHistoricalSessionMetadataFileSource
    workflow_result: MetadataLoadedHistoricalWorkflowResult
```

Exact names may vary, but retain all responsibilities:

```text
exact caller-owned Path object
exact constructed JSON metadata-source object
exact Phase 15E workflow result object
```

Do not add top-level status, reason, duplicate diagnostics, or copied lower-stage artifacts. The exact `workflow_result` already exposes:

```text
metadata_load_result
workflow_bridge_result
Phase 15C collection/composition diagnostics
Phase 14J manifest/harness/final/TOD-RVOL diagnostics when applicable
```

---

## Public Function

Provide:

```python
def run_local_json_metadata_workflow_preflight(
    path: Path,
    collection: HistoricalBarsPageCollectionResult,
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> LocalJsonMetadataWorkflowPreflightResult:
    ...
```

The function must do exactly this:

```python
metadata_source = JsonHistoricalSessionMetadataFileSource(path=path)

workflow_result = run_metadata_loaded_historical_workflow(
    metadata_source,
    collection,
    manifest_request,
    current_series,
    harness_request,
)

return LocalJsonMetadataWorkflowPreflightResult(
    path=path,
    metadata_source=metadata_source,
    workflow_result=workflow_result,
)
```

Required behavior:

```text
- construct the JSON source exactly once;
- call Phase 15E exactly once after successful source construction;
- pass the exact constructed source object to Phase 15E;
- forward collection, request, current series, and harness request by identity;
- retain exact path/source/workflow result objects;
- create a fresh frozen wrapper result;
- do not read the source file directly;
- do not inspect workflow results;
- do not catch, wrap, retry, or transform exceptions;
- have no cache or shared mutable state.
```

The JSON source constructor owns non-Path `TypeError`. No Phase 15E call may occur when source construction fails.

File, parsing, envelope, and downstream workflow exceptions originate inside the Phase 15E call and must propagate unchanged. No wrapper result is returned in an exceptional path.

---

## Identity and Immutability

Phase 15H must preserve:

```text
exact caller-owned Path object
exact constructed JsonHistoricalSessionMetadataFileSource object
exact source path object retained by that source
exact HistoricalBarsPageCollectionResult object
exact HistoricalSessionManifestRequest object
exact IntradayVolumeSeriesInput object
exact HistoricalToTodRvolRunRequest object
exact MetadataLoadedHistoricalWorkflowResult object
```

The preflight result and the JSON source model are frozen. No cache or shared mutable state is permitted.

Separate successful preflight calls with the same input objects must create:

```text
distinct JSON source objects
distinct Phase 15E result objects
distinct preflight wrapper objects
```

while forwarding the original explicit inputs by identity each time.

---

## Error Policy

Phase 15H catches nothing.

The following must propagate unchanged:

```text
non-Path TypeError from JsonHistoricalSessionMetadataFileSource construction
FileNotFoundError
PermissionError
IsADirectoryError
UnicodeDecodeError
json.JSONDecodeError
JsonHistoricalSessionMetadataFileSourceError
RuntimeError from an internally inconsistent lower-stage artifact
ValueError/custom exception from Phase 15E or lower stages
```

No fallback file, automatic retry, source substitution, empty-record sequence, or synthetic diagnostic result is allowed.

---

## Required Tests

### Unit construction and forwarding tests

Monkeypatch only these public dependencies inside the Phase 15H module:

```text
JsonHistoricalSessionMetadataFileSource
run_metadata_loaded_historical_workflow
```

Test:

```text
JSON source constructed exactly once with exact Path identity
Phase 15E called exactly once after construction
exact constructed source object forwarded to Phase 15E
collection forwarded by identity
manifest request forwarded by identity
current series forwarded by identity
harness request forwarded by identity
wrapper retains exact path, source, and workflow result
wrapper frozen
separate calls create independent source/result/wrapper objects
no shared mutable state
```

### Exception propagation tests

Test:

```text
JSON source constructor raises TypeError
→ exact exception propagates
→ Phase 15E is not called

Phase 15E raises ValueError
→ exact exception propagates
→ source constructed once

Phase 15E raises a custom exception
→ exact exception propagates
→ source constructed once
```

The wrapper must not catch or remap errors.

### Actual Phase 15G / 15E integration tests

Use real Phase 15G and Phase 15E with deterministic local temp files and local explicit workflow inputs.

1. **Complete success**

```text
valid local JSON metadata file
+ 20 valid raw records using generic $datetime tags
+ complete two-page collection with split HIST-01 bars
+ valid current series and harness request
→ preflight result path is exact input Path
→ source is JsonHistoricalSessionMetadataFileSource
→ exact source.path is the caller Path
→ Phase 15D metadata load LOADED
→ Phase 15E status WORKFLOW_BRIDGE_RAN
→ Phase 15C status WORKFLOW_RAN
→ Phase 14J status OK
→ final TOD-RVOL 2.0
```

2. **Missing file**

```text
explicit nonexistent Path
→ FileNotFoundError propagates unchanged
→ no preflight wrapper result
```

3. **Invalid envelope**

```text
JSON envelope with schema_version = 2
→ JsonHistoricalSessionMetadataFileSourceError
→ exact message UNSUPPORTED_SCHEMA_VERSION
→ no preflight wrapper result
```

4. **Record-level failure remains downstream**

```text
valid JSON envelope
+ one raw record whose cutoff_timestamp is a non-decoded invalid $datetime mapping
→ source file opens successfully
→ Phase 15D LOADED
→ Phase 15E workflow bridge runs
→ Phase 14J manifest status PARTIAL
→ affected record INVALID_CUTOFF_TIMESTAMP
```

This proves Phase 15H does not absorb or rewrite Phase 15G/14I diagnostics.

5. **Non-composable collection remains downstream**

```text
valid JSON envelope with valid records
+ MAX_PAGE_LIMIT_REACHED collection
→ Phase 15D LOADED
→ Phase 15E status WORKFLOW_BRIDGE_RAN
→ Phase 15C status COLLECTION_NOT_COMPOSABLE
→ no Phase 14J result
```

This proves Phase 15H does not fabricate a collection or call lower stages directly.

### Source-boundary test

Use AST or focused source inspection to verify Phase 15H:

```text
imports only approved Phase 15G / 15E public interfaces and explicit input models
does not import JSON parsing, json source errors, metadata loaders, Phase 15D,
Phase 15C, Phase 15B, Phase 14I, Phase 14J, RVOL, providers, runtime,
HTTP, transports, config, scanner, alerts, voice, candidates, or trading modules
does not call source.load_raw_manifest_records directly
does not inspect path properties/methods beyond forwarding it
does not inspect request fields, collection pages, metadata mappings, raw bars,
or workflow-result statuses
does not construct a page, record sequence, or lower-stage result
does not cache or register anything globally
```

---

## README Note

Update only if useful:

```text
Phase 15H adds a manually invoked local JSON workflow preflight wrapper. It builds the explicit Phase 15G JSON metadata source from a caller-provided Path and calls the existing Phase 15E workflow once, preserving exact nested diagnostics.
It does not discover files, add CLI/runtime/provider activation, or add network or trading/order functionality.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 15H is complete when:

```text
- one caller-supplied Path constructs exactly one Phase 15G JSON source;
- the exact constructed source and all explicit workflow inputs are forwarded once to Phase 15E;
- the result retains exact path/source/workflow artifacts without duplicate status mapping;
- constructor/file/envelope/workflow exceptions propagate unchanged;
- actual valid JSON preflight reaches final TOD-RVOL 2.0;
- missing-file, invalid-envelope, record-level validation, and non-composable-collection diagnostics remain attributable to their existing owners;
- no file discovery, metadata inference, fetcher/transport, runtime/provider, scanner, alert, voice, or trading behavior is added;
- the full project suite remains green.
```
