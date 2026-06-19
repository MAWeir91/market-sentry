# Phase 15D — Historical Session Metadata Source Interface and Static Adapter

## Status

**Planned.** This document defines Phase 15D only.

Phase 15C already accepts caller-supplied raw historical session manifest records and conditionally sends them through the existing Phase 14J manifest-to-TOD-RVOL workflow. What remains missing is a clean, explicit boundary for **where those raw manifest records come from**.

Phase 15D introduces a narrow offline source contract:

```text
caller-supplied metadata source
+ exact HistoricalSessionManifestRequest
→ ordered raw manifest record sequence
→ existing Phase 15C input
```

It adds no market-calendar logic and no provider activation.

---

## Goal

Create a pure offline metadata-source interface and a static in-memory implementation that:

1. accepts the existing `HistoricalSessionManifestRequest` object by identity;
2. requests an ordered raw manifest-record sequence from an injected source exactly once;
3. preserves the exact returned record-sequence object without tuple-wrapping, copying, filtering, or record inspection;
4. distinguishes a usable sequence from an invalid source return container;
5. exposes a simple static source for local tests, fixtures, and future manually curated metadata;
6. propagates source-raised exceptions unchanged;
7. produces an artifact that can be passed directly into the existing Phase 15C workflow bridge.

The intended path is:

```text
explicit metadata source
→ Phase 15D source load
→ exact raw manifest sequence
→ Phase 15C
→ Phase 15B composition + Phase 14J workflow
```

Phase 15D does not itself call Phase 15C, Phase 15B, Phase 14J, Phase 14I, or any lower-level component.

---

## Why This Boundary Exists

Historical bars alone do not establish trustworthy session metadata.

A future metadata source must provide explicit facts for each historical session:

```text
symbol
session_id
bucket
session_start_timestamp
session_end_timestamp
cutoff_timestamp
is_complete
```

The existing Phase 14I adapter validates these raw records. Phase 15D does **not** duplicate that validation.

```text
metadata source owns:
  choosing/providing explicit candidate metadata facts

Phase 15D owns:
  source invocation
  record-sequence container safety
  exact source/request/sequence artifact retention

Phase 14I owns:
  raw manifest record validation
  session identity, timestamp, bucket, completeness, and duplicate diagnostics

Phase 15C owns:
  conditional handoff to Phase 14J after Phase 15B composition
```

---

## Explicit Metadata Policy

Phase 15D deliberately makes no inference from raw bars, dates, or the local clock.

It must not infer:

```text
session IDs
exchange calendar days
holidays
early closes
halts
splits
session start/end timestamps
cutoff timestamps
bucket labels
current session identity
whether a session is complete
whether an absent date was eligible or excluded
```

A source must supply metadata facts explicitly.

### Known incomplete or excluded sessions

A metadata source may emit an explicit record with:

```text
is_complete = False
```

and optional extra provenance fields, such as:

```text
source_reason
source_category
```

Phase 14I already rejects `is_complete=False` from the usable historical metadata tuple while preserving an inspectable per-record diagnostic.

The source may also omit a date/session entirely. Phase 15D must treat that absence as opaque:

```text
missing record
≠ inferred holiday
≠ inferred early close
≠ inferred source failure
≠ inferred eligible session
```

No completeness claim about an expected date range is made by this phase.

### Extra provenance fields

Raw manifest records may include extra mapping keys. Phase 14I permits and preserves top-level source mappings while validating only its required fields.

Phase 15D must not inspect, remove, normalize, or create optional provenance fields.

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
manifest-record field validation
manifest adaptation or workflow execution
Phase 15A collection calls
Phase 15B composition calls
Phase 15C workflow-bridge calls
Phase 14I / 14J / 14G / 14D / 14E / 14F calls
relative-volume calculation
candidate composition, scoring, filtering, alerts, or voice changes
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

No live HTTP calls are permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

## Existing Components to Reuse

Reuse only:

```text
market_sentry.data.historical_session_manifest
  HistoricalSessionManifestRequest
```

Do not import or call:

```text
adapt_historical_session_manifest
HistoricalSessionManifestResult
historical_session_assembly
alpaca_historical_bars_fetcher
alpaca_historical_bars_adapter
historical_bars_page_collector
collected_historical_pages_composer
collected_pages_to_manifest_workflow
manifest_to_harness_orchestrator
historical_tod_rvol_harness
intraday_bucket_adapter
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

The production Phase 15D module must not inspect individual raw record mappings or their fields.

---

## Expected Files

Create:

```text
docs/53_HISTORICAL_SESSION_METADATA_SOURCE_INTERFACE.md
src/market_sentry/data/historical_session_metadata_source.py
tests/test_historical_session_metadata_source.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 14A–14K, Phase 15A–15C, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Source Protocol

Use a runtime-checkable protocol or equivalent structural interface:

```python
@runtime_checkable
class HistoricalSessionMetadataSource(Protocol):
    """One explicit source of raw historical session-manifest records."""

    def load_raw_manifest_records(
        self,
        request: HistoricalSessionManifestRequest,
    ) -> Sequence[object]:
        ...
```

Contract:

```text
- receives the exact caller-owned HistoricalSessionManifestRequest object;
- returns one caller/source-owned ordered raw record sequence;
- does not need to validate the records;
- must not mutate the request;
- may be implemented later by a separate explicitly scoped local/file/network/calendar source;
- Phase 15D includes only the static in-memory implementation below.
```

No source registration or global factory is permitted.

---

## Static In-Memory Source

Provide an immutable static source suitable for tests, fixtures, and manually curated data:

```python
@dataclass(frozen=True)
class StaticHistoricalSessionMetadataSource:
    raw_manifest_records: Sequence[object]

    def load_raw_manifest_records(
        self,
        request: HistoricalSessionManifestRequest,
    ) -> Sequence[object]:
        ...
```

Requirements:

```text
- return the exact raw_manifest_records object by identity;
- do not inspect, copy, tuple-wrap, filter, normalize, or validate records;
- do not inspect request fields;
- do not mutate source or request;
- no caching or mutable shared state.
```

The request parameter is intentional: it makes the static source substitutable for a future request-aware source without adding any inference now.

---

## Public Result Model

Use a frozen dataclass:

```python
@dataclass(frozen=True)
class HistoricalSessionMetadataSourceLoadResult:
    """One exact source/request pair and one usable raw record sequence, if loaded."""

    source: HistoricalSessionMetadataSource
    request: HistoricalSessionManifestRequest
    raw_manifest_records: Sequence[object] | None
    status: str
    reason: str | None = None
```

Exact names may vary, but retain:

```text
exact source object
exact request object
exact raw record-sequence object or None
stable source-load status
stable source-load reason
```

Do not duplicate or transform raw records in the result.

---

## Public Loader Function

Provide:

```python
def load_historical_session_metadata_source(
    source: HistoricalSessionMetadataSource,
    request: HistoricalSessionManifestRequest,
) -> HistoricalSessionMetadataSourceLoadResult:
    ...
```

Required behavior:

```text
1. Invoke source.load_raw_manifest_records(request) exactly once.
2. Do not catch/wrap/retry exceptions from the source.
3. Validate only the returned container shape.
4. Preserve a usable sequence object by identity.
5. Do not inspect any element within the sequence.
6. Return a fresh frozen result object.
```

---

## Stable Statuses

Use exactly:

```text
LOADED
INVALID_RECORD_SEQUENCE
```

### LOADED

A valid source result must be an ordered `collections.abc.Sequence` but not one of these text/binary pseudo-sequences:

```text
str
bytes
bytearray
memoryview
```

For a valid sequence:

```text
status = LOADED
reason = None
raw_manifest_records = exact source-returned sequence object
```

An empty tuple/list is still a valid loaded sequence:

```text
status = LOADED
reason = None
raw_manifest_records = exact empty sequence
```

Its lack of valid metadata is owned later by Phase 14I.

### INVALID_RECORD_SEQUENCE

If the source returns any object that is not an accepted sequence container:

```text
status = INVALID_RECORD_SEQUENCE
reason = INVALID_RECORD_SEQUENCE
raw_manifest_records = None
```

Examples:

```text
None
a generator
a mapping
an integer
str
bytes
bytearray
memoryview
```

Phase 15D must not call or imply downstream workflow behavior. It only returns the load diagnostic.

---

## Identity and Immutability

Phase 15D must preserve:

```text
exact source object
exact request object
exact accepted record-sequence object
every raw record element object by containment, without copying
```

Phase 15D must not guarantee immutability of a caller-owned list or its mappings. It guarantees only that it will not mutate, copy, or replace them.

The static source and load-result models must be frozen.

Separate load calls must produce distinct result objects but retain the exact same source, request, and returned record-sequence identities where applicable.

No cache or global state is permitted.

---

## Error Policy

Source-raised exceptions are source-owned and must propagate unchanged:

```text
source raises ValueError
→ caller receives that exact ValueError
→ no result object
→ no retry

source raises custom exception
→ caller receives the exact custom exception
→ no wrapping
```

Do not convert a source exception into `INVALID_RECORD_SEQUENCE`. That status is for a normally returned invalid container only.

---

## Downstream Compatibility Policy

Phase 15D itself must not import or call Phase 14I or Phase 15C.

The output contract is deliberately direct:

```text
load_result.status == LOADED
→ load_result.raw_manifest_records
→ may be supplied unchanged as Phase 15C raw_manifest_records
```

A future orchestration phase may choose whether to:
- halt on `INVALID_RECORD_SEQUENCE`, or
- surface it as a higher-level metadata-source diagnostic.

Phase 15D does not decide that policy.

---

## Required Tests

### Static source behavior

Test:

```text
static source returns exact caller-owned tuple by identity
static source returns exact caller-owned list by identity
static source does not inspect request fields
static source is frozen
```

Use raw mappings with deliberately malformed or mixed field values. The static source must return them unchanged.

### Loader call and identity behavior

Use a local recording source implementing the protocol.

Test:

```text
source called exactly once
exact request object passed by identity
accepted tuple result retained by identity
accepted list result retained by identity
result retains exact source object
result is frozen
separate calls create distinct results without shared result state
empty tuple/list returns LOADED
```

### Container validation

Test each of:

```text
None
generator
mapping
integer
str
bytes
bytearray
memoryview
```

All must return:

```text
status = INVALID_RECORD_SEQUENCE
reason = INVALID_RECORD_SEQUENCE
raw_manifest_records = None
```

Do not test or validate individual record fields in the production module.

### Error propagation

Test:

```text
source raises ValueError
→ same exception propagates
→ exactly one source call

source raises custom exception
→ same exception object/type propagates
→ exactly one source call
```

### Actual downstream compatibility test

The production Phase 15D module must not import downstream modules. The test module may.

Create:

```text
StaticHistoricalSessionMetadataSource
+ exact tuple of 20 valid raw manifest mappings
+ HistoricalSessionManifestRequest
→ load result LOADED
→ exact raw record sequence passed to actual Phase 14I manifest adapter
→ manifest status OK
→ emitted metadata count 20
```

Add one complete workflow compatibility test:

```text
StaticHistoricalSessionMetadataSource
+ exact tuple of 20 valid raw manifest mappings
+ a local complete two-page Phase 15A collection
+ valid current series and harness request
→ Phase 15D load result LOADED
→ use its exact raw sequence in actual Phase 15C
→ WORKFLOW_RAN
→ Phase 14J status OK
→ final RVOL 2.0
```

This proves the source contract plugs into the already-built offline workflow without adding downstream calls to the Phase 15D production module.

### Source-boundary test

Use AST or focused source inspection to verify the production module:

```text
imports only HistoricalSessionManifestRequest plus standard-library typing/dataclass/collections abstractions
does not import/call manifest adapter, Phase 15A/15B/15C, Phase 14J, RVOL, providers,
runtime, HTTP, transports, config, scanner, alerts, voice, candidates, or trading modules
does not access mapping keys/values or raw record fields
does not construct raw mapping records
does not inspect request fields
does not register sources globally
```

---

## README Note

Update only if useful:

```text
Phase 15D adds a narrow offline metadata-source interface and static in-memory source for explicit historical-session manifest record sequences.
It preserves caller-provided metadata records exactly and leaves all record validation to the existing Phase 14I manifest adapter.
It does not infer market calendars or sessions, fetch data, activate a runtime provider, or add trading/order functionality.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 15D is complete when:

```text
- an injected metadata source receives the exact manifest request once;
- a valid returned record sequence is retained by identity without element inspection or copying;
- invalid source return containers produce a stable load diagnostic;
- source exceptions propagate unchanged;
- the static in-memory source provides a safe deterministic offline implementation;
- tests demonstrate compatibility with actual Phase 14I and the full existing Phase 15C workflow;
- no calendar/session inference, raw-record validation, fetcher/transport, workflow, RVOL,
  runtime/provider, scanner, alert, voice, or trading functionality is added;
- the full project suite remains green.
```
