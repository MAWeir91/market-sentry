# Phase 14I — Offline Session-Metadata Manifest Adapter

## Status

**Planned.** This document defines Phase 14I only.

Phase 14G accepts explicit ordered `HistoricalIntradaySessionMetadata` records. Those records are currently constructed manually in tests and fixtures.

Phase 14I provides a strict offline adapter that converts an explicit caller-supplied manifest of raw record mappings into the exact ordered metadata records consumed by Phase 14G:

```text
raw caller manifest mappings
+ explicit manifest request identity
→ validated record diagnostics
→ ordered HistoricalIntradaySessionMetadata tuple
→ future Phase 14G handoff
```

This phase does not invoke the Phase 14G harness, fetch data, infer calendar behavior, or activate any runtime provider.

---

## Goal

Create a pure offline manifest adapter that:

1. accepts a target manifest request and an ordered sequence of raw mapping records;
2. validates all request fields without normalizing the caller’s original objects in place;
3. validates required manifest record fields;
4. enforces target symbol, bucket, and current-session consistency;
5. validates timestamp types, awareness, exact timezone compatibility, session windows, and cutoff bounds;
6. rejects incomplete sessions and duplicate historical IDs;
7. builds only valid `HistoricalIntradaySessionMetadata` records in input-relative order;
8. preserves every invalid record as an inspectable result instead of failing fast;
9. returns a status distinguishing a fully-valid manifest, a partial manifest, and one with no usable metadata.

The intended future flow is:

```text
raw manifest mappings
→ Phase 14I metadata adapter
→ metadata_records tuple
→ Phase 14G offline end-to-end TOD RVOL harness
```

Phase 14I does not add that future Phase 14G handoff call.

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
Phase 14D session assembly calls
Phase 14E baseline composition calls
Phase 14F final TOD RVOL calls
Phase 14G harness calls
RVOL calculation
candidate composition, scoring, filtering, or alerts
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

`live_composed` remains gated and reserved/inactive.

---

## Existing Components to Reuse

Reuse only these public models:

```text
market_sentry.data.historical_session_assembly
  HistoricalIntradaySessionMetadata
```

Do not import or call:

```text
assemble_historical_sessions_from_page
HistoricalSessionAssemblyResult
HistoricalSessionAssemblyStatus
historical_baseline_composition
current_session_tod_rvol
historical_tod_rvol_harness
alpaca_historical_bars_fetcher
alpaca_historical_bars_adapter
intraday_bucket_adapter
time_of_day_rvol
HTTP transport modules
fetchers
provider factory
config
live readiness
relative volume modules
fixture providers
LiveCandidateBuilder
LiveComposedMarketDataProvider
scanner engine
alert modules
voice modules
```

Phase 14I builds only `HistoricalIntradaySessionMetadata` data objects. It must not perform any stage execution.

---

## Expected Files

Create:

```text
docs/47_OFFLINE_SESSION_METADATA_MANIFEST_ADAPTER.md
src/market_sentry/data/historical_session_manifest.py
tests/test_historical_session_manifest.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 13, Phase 14A–14H, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Models

Use frozen dataclasses.

```python
@dataclass(frozen=True)
class HistoricalSessionManifestRequest:
    """Target identity for one caller-supplied historical metadata manifest."""

    symbol: str
    bucket: str
    current_session_id: str
```

```python
@dataclass(frozen=True)
class HistoricalSessionManifestRecordResult:
    """Inspectable outcome for one raw manifest record."""

    index: int
    source_record: Mapping[str, object] | None
    metadata: HistoricalIntradaySessionMetadata | None
    status: str
    reason: str | None = None
```

```python
@dataclass(frozen=True)
class HistoricalSessionManifestResult:
    """Validated metadata records and diagnostics for one manifest."""

    request: HistoricalSessionManifestRequest
    record_results: tuple[HistoricalSessionManifestRecordResult, ...]
    metadata_records: tuple[HistoricalIntradaySessionMetadata, ...]
    valid_record_count: int
    status: str
    reason: str | None = None
```

Exact names may vary, but retain all responsibilities:

```text
original caller request
per-record source mapping copy or None
per-record emitted metadata or None
stable per-record diagnostics
ordered output metadata tuple
valid record count
manifest-level status and reason
```

---

## Public Function

Provide:

```python
def adapt_historical_session_manifest(
    raw_records: Sequence[object],
    request: HistoricalSessionManifestRequest,
) -> HistoricalSessionManifestResult:
    ...
```

The function returns one `HistoricalSessionManifestRecordResult` for every supplied input record in exact caller order, including duplicate and malformed records.

`metadata_records` contains only successful valid records in their original relative order.

There is no file loader, JSON parser, YAML parser, provider interface, CLI command, or harness call in this phase.

---

## Required Raw Manifest Fields

Each valid raw record must be a mapping with these exact keys:

```text
symbol
session_id
bucket
session_start_timestamp
session_end_timestamp
cutoff_timestamp
is_complete
```

Extra keys are allowed and ignored.

The adapter must copy and protect the top-level source mapping for inspection. A non-mapping source record results in:

```text
INVALID_RECORD
```

with:

```text
source_record = None
metadata = None
```

A mapping missing one or more required fields results in:

```text
MISSING_REQUIRED_FIELD
```

The reason should identify the first missing required field in this fixed order:

```text
symbol
session_id
bucket
session_start_timestamp
session_end_timestamp
cutoff_timestamp
is_complete
```

For example:

```text
MISSING_REQUIRED_FIELD:bucket
```

Do not mutate source mappings.

---

## Stable Status Codes

Use explicit stable status containers or enums.

### Manifest-level statuses

```text
OK
PARTIAL
NO_VALID_METADATA
INVALID_TARGET_SYMBOL
INVALID_TARGET_BUCKET
INVALID_CURRENT_SESSION_ID
```

### Per-record statuses

```text
OK
INVALID_RECORD
MISSING_REQUIRED_FIELD
EMPTY_SYMBOL
MISMATCHED_MANIFEST_SYMBOL
EMPTY_SESSION_ID
CURRENT_SESSION_IN_HISTORY
EMPTY_BUCKET
MISMATCHED_MANIFEST_BUCKET
INVALID_SESSION_START_TIMESTAMP
INVALID_SESSION_END_TIMESTAMP
INVALID_CUTOFF_TIMESTAMP
NAIVE_SESSION_TIMESTAMP
MISMATCHED_SESSION_TIMEZONE
INVALID_SESSION_WINDOW
INVALID_CUTOFF_OUTSIDE_SESSION
INVALID_IS_COMPLETE
INCOMPLETE_SESSION
DUPLICATE_HISTORICAL_SESSION_ID
```

For a successful record:

```text
status = OK
reason = None
metadata = fresh HistoricalIntradaySessionMetadata
```

For a failed record:

```text
metadata = None
reason = stable status text, or the fixed missing-field detail above
```

---

## Request Validation

The manifest request is validated before raw records are inspected.

Normalize internally only:

```text
symbol:
  must be a string
  trim surrounding whitespace
  uppercase
  blank/non-string → INVALID_TARGET_SYMBOL

bucket:
  must be a string
  trim surrounding whitespace
  preserve resulting text exactly
  blank/non-string → INVALID_TARGET_BUCKET

current_session_id:
  must be a string
  trim surrounding whitespace
  preserve resulting case/content exactly
  blank/non-string → INVALID_CURRENT_SESSION_ID
```

For an invalid manifest request:

```text
record_results = ()
metadata_records = ()
valid_record_count = 0
status = relevant request error
reason = same status
```

Do not inspect, copy, validate, or emit individual raw record results. Do not call other project stages.

---

## Per-Record Validation Rules

For each raw mapping record, perform validation in the following fixed order after required-field presence is confirmed.

### 1. Symbol

```text
record symbol must be a string
trim and uppercase
blank/non-string → EMPTY_SYMBOL
normalized record symbol != normalized request symbol
→ MISMATCHED_MANIFEST_SYMBOL
```

### 2. Session ID

```text
record session_id must be a string
trim
preserve resulting case/content exactly
blank/non-string → EMPTY_SESSION_ID
trimmed record session ID == trimmed request current_session_id
→ CURRENT_SESSION_IN_HISTORY
```

Session ID comparisons are case-sensitive after trimming.

### 3. Bucket

```text
record bucket must be a string
trim
preserve resulting text exactly
blank/non-string → EMPTY_BUCKET
trimmed record bucket != trimmed request bucket
→ MISMATCHED_MANIFEST_BUCKET
```

### 4. Timestamp types and timezone compatibility

These fields must each be actual `datetime` values:

```text
session_start_timestamp
session_end_timestamp
cutoff_timestamp
```

Reject `date`, string, numeric, bool, `None`, and any non-datetime object.

Use field-specific statuses:

```text
invalid session start → INVALID_SESSION_START_TIMESTAMP
invalid session end → INVALID_SESSION_END_TIMESTAMP
invalid cutoff → INVALID_CUTOFF_TIMESTAMP
```

All three datetimes must be timezone-aware:

```text
tzinfo is not None
utcoffset() is not None
```

Any naive value returns:

```text
NAIVE_SESSION_TIMESTAMP
```

All three must have exactly equal `tzinfo` values:

```text
MISMATCHED_SESSION_TIMEZONE
```

Do not convert, normalize, replace, or infer time zones.

### 5. Session window and cutoff

Require:

```text
session_start_timestamp < session_end_timestamp
```

Otherwise:

```text
INVALID_SESSION_WINDOW
```

Require:

```text
session_start_timestamp <= cutoff_timestamp < session_end_timestamp
```

Otherwise:

```text
INVALID_CUTOFF_OUTSIDE_SESSION
```

### 6. Completion flag

```text
is_complete must be a real bool
```

Reject `1`, `0`, `"true"`, `"false"`, custom truthy objects, and `None`:

```text
INVALID_IS_COMPLETE
```

A real `False` results in:

```text
INCOMPLETE_SESSION
```

Only `True` is eligible for metadata emission.

---

## Duplicate Historical Session Rules

Duplicate handling occurs only after a record has passed every prior per-record validation rule.

Duplicate identity is:

```text
normalized record symbol + trimmed, case-sensitive session_id
```

For any duplicate identity:

```text
every duplicate occurrence must receive:
  status = DUPLICATE_HISTORICAL_SESSION_ID
  metadata = None
```

Do not allow the first duplicate to remain successful.

Same session ID under a different normalized symbol is not relevant after target-symbol matching. Differently cased session IDs remain distinct after trimming.

Duplicate detection must preserve original record order in `record_results`.

---

## Output Rules

For every record with final status `OK`, emit a fresh:

```python
HistoricalIntradaySessionMetadata(
    symbol=normalized_symbol,
    session_id=trimmed_session_id,
    bucket=trimmed_bucket,
    session_start_timestamp=original_valid_start_timestamp,
    session_end_timestamp=original_valid_end_timestamp,
    cutoff_timestamp=original_valid_cutoff_timestamp,
    is_complete=True,
)
```

`metadata_records` must contain those successful metadata objects only, preserving relative input order.

After all records:

```text
at least one valid and no invalid records
→ status = OK
→ reason = None

at least one valid and at least one invalid record
→ status = PARTIAL
→ reason = PARTIAL

zero valid records
→ status = NO_VALID_METADATA
→ reason = NO_VALID_METADATA
```

An empty valid request with zero raw records is:

```text
NO_VALID_METADATA
```

No fallback metadata, duplicate repair, calendar inference, or partial-session promotion is allowed.

---

## Immutability and Freshness

- New result models must be frozen.
- `record_results` and `metadata_records` must be tuples.
- `source_record` must be a copied, mapping-protected top-level mapping when input is a mapping.
- No source record, request, datetime, metadata object, or input sequence may be mutated.
- Catalog/adapter calls must not cache data.
- Repeated calls must build new result and record-result objects.
- Extra raw record fields may remain in protected `source_record` for inspection but never affect validation or output metadata.

---

## Required Tests

Use manually constructed raw mapping and non-mapping inputs only.

Do not invoke Phase 14D, Phase 14E, Phase 14F, Phase 14G, any fetcher, transport, provider, config, or runtime setup.

Test:

```text
valid 20-record manifest:
  status OK
  20 record results OK
  20 metadata records in source-relative order
  normalized symbol
  trimmed session ID/bucket
  original valid datetime objects preserved
  is_complete True

partial manifest:
  valid records retained
  failed record diagnostics retained
  status PARTIAL
  metadata output preserves valid input-relative order

empty manifest:
  NO_VALID_METADATA
  empty tuples
  valid request preserved

invalid request fields:
  INVALID_TARGET_SYMBOL
  INVALID_TARGET_BUCKET
  INVALID_CURRENT_SESSION_ID
  no raw records inspected
  no record results
  no output metadata

non-mapping raw record:
  INVALID_RECORD
  source_record None

missing required fields:
  fixed first-missing-field order
  extra fields allowed/ignored

symbol:
  trim/uppercase
  empty/non-string
  target mismatch

session IDs:
  trim/preserve
  empty/non-string
  current-session reuse
  case-sensitive comparison
  duplicate identity behavior
  every duplicate occurrence rejected
  differently cased IDs distinct

bucket:
  trim/preserve
  empty/non-string
  target mismatch
  exact-label behavior

timestamps:
  field-specific bad-type statuses
  date is rejected
  bool is rejected
  naive timestamps
  tzinfo mismatch
  invalid session window
  cutoff outside window
  cutoff equals end is invalid
  cutoff equals start is valid

completion:
  non-bool rejected
  False yields INCOMPLETE_SESSION
  True emits metadata

immutability:
  result and record results frozen
  output collections tuples
  source_record mapping protected
  caller raw mappings unchanged
  separate calls create distinct result/record-result/source-record objects
  extra fields survive inspection but do not affect output

source boundary:
  no 14D/14E/14F/14G execution functions
  no raw-page/fetcher/transport
  no config/factory/provider/runtime/scanner/alert/voice/candidate/trading modules
```

Add at least one small integration-style handoff test that takes `manifest_result.metadata_records` from a fully valid 20-record manifest and passes those records into the actual Phase 14G harness with a deterministic local raw page/current series fixture. The test must demonstrate:

```text
manifest status OK
→ metadata_records length 20
→ actual harness status OK
```

The manifest adapter itself must not import or call the harness function; the test module may do so.

---

## README Note

Update only if useful:

```text
Phase 14I adds an offline session-metadata manifest adapter that validates explicit caller-supplied historical session records and emits ordered Phase 14G-compatible metadata objects with per-record diagnostics.
It does not inspect raw bars, infer calendars or sessions, fetch data, register a runtime provider, or activate live mode.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```

---

## Acceptance Criteria

Phase 14I is complete when:

```text
- raw caller manifest records adapt into validated, ordered HistoricalIntradaySessionMetadata values;
- target identity, timestamp compatibility, session window, cutoff, completion, current-session, and duplicate policies are enforced deterministically;
- partial manifests retain valid records and failed-record diagnostics;
- fully invalid or empty manifests produce NO_VALID_METADATA;
- no stage execution, runtime, network, provider, candidate, scanner, alert, voice, or trading capability is added;
- an integration-style test proves emitted metadata can drive the actual Phase 14G harness;
- the full project suite remains green.
```
