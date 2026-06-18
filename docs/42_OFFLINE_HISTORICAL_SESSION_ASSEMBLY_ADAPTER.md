# Phase 14D — Offline Historical Session Assembly Adapter

## Status

**Planned.** This document defines Phase 14D only.

Phase 14A fetches one raw historical-bars page through an injected transport. Phase 14B converts a raw page symbol plus explicit metadata into a Phase 13F-compatible `IntradayVolumeSeriesInput`. Phase 14C locks the explicit session, bucket, cutoff, and completeness policy needed before real historical sessions can become comparable data.

Phase 14D implements the first narrow execution layer under that policy:

```text
one raw AlpacaHistoricalBarsPage
+ explicit historical session metadata records
+ explicit page-collection completeness assertion
+ explicit current session ID
→ inspectable per-session eligibility and assembly results
→ Phase 14B adaptation only for an eligible session
```

This phase does **not** calculate RVOL, build a historical baseline, build candidates, or activate any live provider.

---

## Goal

Create a pure offline session assembler that:

1. validates caller-supplied historical session metadata;
2. rejects incomplete or uncertain page collections before adaptation;
3. isolates raw bars whose parsed timestamps fall inside each metadata-defined half-open session window;
4. requires at least one in-window raw bar at or after the explicit cutoff timestamp;
5. calls the existing Phase 14B adapter only after those eligibility checks pass;
6. preserves all failures as stable, inspectable per-session results.

The intended path is:

```text
Phase 14A raw one-page response
  ↓
Phase 14D session eligibility + window membership
  ↓
Phase 14B raw-bar adapter
  ↓
Phase 13F later validates order / volume / cutoff inclusion
  ↓
future phase assembles eligible historical series into Phase 13E inputs
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
HTTP requests, fetcher construction, pagination retrieval, retries, caching, WebSockets, or streaming
environment or config reads
automatic watchlist lookup or broad-market discovery
calendar, holiday, early-close, or halt provider integration
time-zone conversion or normalization
RVOL calculation
historical baseline construction
candidate composition, scoring, or filtering
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

`live_composed` must remain gated and reserved/inactive.

---

## Existing Components to Reuse

Reuse:

```text
market_sentry.data.alpaca_historical_bars_fetcher
  AlpacaHistoricalBarsPage

market_sentry.data.alpaca_historical_bars_adapter
  AlpacaHistoricalBarsIntradaySeriesRequest
  AlpacaHistoricalBarsIntradaySeriesResult
  AlpacaHistoricalBarsAdapterStatus
  build_intraday_series_from_historical_bars

market_sentry.data.intraday_bucket_adapter
  IntradayVolumeSeriesInput
```

Do not instantiate:

```text
AlpacaHistoricalBarsFetcher
HttpTransport
StdlibHttpTransport
OfflineIntradayRelativeVolumeFixtureProvider
OfflineIntradayRvolCandidateCompositionHarness
LiveCandidateBuilder
LiveComposedMarketDataProvider
```

Do not import or call:

```text
time_of_day_rvol
intraday_rvol_harness
intraday_rvol_fixture_provider
intraday_rvol_candidate_composition_harness
relative_volume_calculator
live_provider_builder
provider factory
scanner engine
alert modules
```

---

## Expected Files

Create:

```text
docs/42_OFFLINE_HISTORICAL_SESSION_ASSEMBLY_ADAPTER.md
src/market_sentry/data/historical_session_assembly.py
tests/test_historical_session_assembly.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 14A or Phase 14B code, Phase 13 modules, runtime wiring, factory, CLI, config, readiness, providers, transports, scanner, or alerts.

---

## Public Models

Use frozen dataclasses and explicit caller inputs.

```python
@dataclass(frozen=True)
class HistoricalIntradaySessionMetadata:
    """Caller-supplied metadata for one potential historical session."""

    symbol: str
    session_id: str
    bucket: str
    session_start_timestamp: datetime
    session_end_timestamp: datetime
    cutoff_timestamp: datetime
    is_complete: bool
```

```python
@dataclass(frozen=True)
class HistoricalSessionAssemblyResult:
    """Inspectable result for assembling one historical session."""

    symbol: str
    session_id: str
    bucket: str
    session_start_timestamp: datetime | None
    session_end_timestamp: datetime | None
    cutoff_timestamp: datetime | None
    intraday_series: IntradayVolumeSeriesInput | None
    status: str
    reason: str | None = None
    source_raw_bar_count: int = 0
    in_window_raw_bar_count: int = 0
    adapter_result: AlpacaHistoricalBarsIntradaySeriesResult | None = None
```

Exact names may vary, but retain the same explicit responsibilities.

---

## Public Function

Provide one ordered batch function:

```python
def assemble_historical_sessions_from_page(
    page: AlpacaHistoricalBarsPage,
    metadata_records: Sequence[HistoricalIntradaySessionMetadata],
    *,
    current_session_id: str,
    page_collection_complete: bool,
) -> list[HistoricalSessionAssemblyResult]: ...
```

The function returns one result for every metadata record in the exact caller-provided order. It must preserve duplicate metadata records and failures; do not collapse results into a mapping.

No success-only mapping is needed in Phase 14D.

---

## Stable Status Codes

Use explicit stable strings. A class or enum-like constant container is acceptable.

```text
OK
EMPTY_SYMBOL
INVALID_SESSION_ID
EMPTY_BUCKET
INVALID_SESSION_START_TIMESTAMP
INVALID_SESSION_END_TIMESTAMP
INVALID_CUTOFF_TIMESTAMP
NAIVE_SESSION_TIMESTAMP
MISMATCHED_SESSION_TIMEZONE
INVALID_SESSION_WINDOW
INVALID_CUTOFF_OUTSIDE_SESSION
INVALID_IS_COMPLETE
INVALID_CURRENT_SESSION_ID
CURRENT_SESSION_IN_HISTORY
DUPLICATE_HISTORICAL_SESSION_ID
INCOMPLETE_PAGE_COLLECTION
INCOMPLETE_SESSION
INVALID_RAW_BAR
MISSING_RAW_TIMESTAMP
INVALID_RAW_TIMESTAMP
NAIVE_RAW_TIMESTAMP
MISMATCHED_RAW_TIMESTAMP_TIMEZONE
CUT_OFF_NOT_REACHED
ADAPTER_FAILED
```

A result may use `reason == status` for stable diagnostics.

Do not replace a lower-level Phase 14B adapter failure with a generic assembly status. When Phase 14B returns a failure, set:

```text
status = ADAPTER_FAILED
reason = "ADAPTER_FAILED:<adapter status>"
adapter_result = exact Phase 14B result
```

For example:

```text
ADAPTER_FAILED:INVALID_RAW_BAR
ADAPTER_FAILED:MISSING_RAW_VOLUME
ADAPTER_FAILED:MISMATCHED_TIMESTAMP_TIMEZONE
```

---

## Explicit Metadata Validation

Normalize only textual identifiers:

```text
symbol:
  trim surrounding whitespace
  uppercase
  blank → EMPTY_SYMBOL

session_id:
  non-empty string after trimming
  preserve resulting case/content exactly
  do not parse as a date
  blank/non-string → INVALID_SESSION_ID

bucket:
  non-empty string after trimming
  preserve resulting label exactly
  do not parse as a time
  blank/non-string → EMPTY_BUCKET

current_session_id:
  non-empty string after trimming
  preserve resulting case/content exactly
  invalid global current_session_id → INVALID_CURRENT_SESSION_ID for every record
```

The metadata datetime values:

```text
session_start_timestamp
session_end_timestamp
cutoff_timestamp
```

must each be:

```text
datetime only
not date/string/numeric/bool/missing
timezone-aware
with exactly equal tzinfo values within one record
```

Use:

```text
INVALID_SESSION_START_TIMESTAMP
INVALID_SESSION_END_TIMESTAMP
INVALID_CUTOFF_TIMESTAMP
NAIVE_SESSION_TIMESTAMP
MISMATCHED_SESSION_TIMEZONE
```

as appropriate.

Do not convert or normalize time zones.

The session window is half-open:

```text
session_start_timestamp <= bar.timestamp < session_end_timestamp
```

The session window is valid only if:

```text
session_start_timestamp < session_end_timestamp
```

Otherwise return:

```text
INVALID_SESSION_WINDOW
```

The cutoff is valid only when:

```text
session_start_timestamp <= cutoff_timestamp < session_end_timestamp
```

Otherwise return:

```text
INVALID_CUTOFF_OUTSIDE_SESSION
```

`is_complete` must be a real `bool`, not a truthy value such as `1`, `"true"`, or a custom object.

```text
non-bool → INVALID_IS_COMPLETE
False → INCOMPLETE_SESSION
```

---

## Batch-Level Eligibility Rules

Apply these checks to every record before raw bar membership or Phase 14B adaptation:

```text
page_collection_complete must be a real bool
```

If it is not a `bool`, treat the complete page collection assertion as invalid and return:

```text
INCOMPLETE_PAGE_COLLECTION
```

for every metadata record. Do not attempt adaptation.

If either condition is true:

```text
page_collection_complete is False
page.next_page_token is not None
```

return:

```text
INCOMPLETE_PAGE_COLLECTION
```

for every metadata record. Do not attempt adaptation.

This locks the Phase 14C policy:

```text
non-null next_page_token
→ page collection is incomplete
→ no session from that page is baseline-eligible
```

A terminal `next_page_token is None` only clears this narrow page-collection gate. It does **not** prove exchange calendar completeness or override metadata `is_complete`.

Duplicate historical session IDs must be detected after trimming but case-sensitive, per symbol:

```text
same normalized symbol + same trimmed session_id
→ DUPLICATE_HISTORICAL_SESSION_ID for every duplicate occurrence
```

Do not collapse duplicates. Do not let a first occurrence succeed while a later duplicate is rejected; all records sharing that duplicate key must receive the duplicate status.

A historical record is invalid when its session ID equals the trimmed `current_session_id` exactly:

```text
CURRENT_SESSION_IN_HISTORY
```

This comparison is case-sensitive after trimming.

---

## Raw Bar Membership Rules

For one metadata record, only examine raw bars under:

```text
page.bars_by_symbol[normalized symbol]
```

If the symbol is absent, use an empty raw-bar sequence. Do not borrow bars from any other symbol.

For each raw bar in page-provided order:

```text
raw bar must be a mapping
  otherwise → INVALID_RAW_BAR

raw key "t" must exist
  otherwise → MISSING_RAW_TIMESTAMP

raw timestamp:
  must be a non-empty string with no surrounding whitespace
  must contain T
  terminal Z may become +00:00 only for datetime.fromisoformat parsing syntax
  must parse successfully
  must be timezone-aware
  must have timestamp.tzinfo exactly equal to metadata cutoff_timestamp.tzinfo
```

Use raw timestamp statuses:

```text
INVALID_RAW_TIMESTAMP
NAIVE_RAW_TIMESTAMP
MISMATCHED_RAW_TIMESTAMP_TIMEZONE
```

Important:

```text
Raw v is not read or validated by the assembly layer.
The assembly layer must not require key v.
Phase 14B remains responsible for raw structural t/v requirements.
Phase 13F remains responsible for ordering, duplicate timestamps,
cutoff inclusion, and raw volume validity.
```

A malformed raw bar/timestamp invalidates the full metadata record. Do not skip bad raw bars.

For valid raw timestamps:

```text
bar belongs to this metadata record only when:
session_start_timestamp <= timestamp < session_end_timestamp
```

Raw bars outside the session window are ignored for that metadata record. This is membership selection, not sorting, aggregation, or cutoff filtering.

Preserve the page-provided order of selected in-window raw mappings exactly. Do not sort, deduplicate, aggregate, or mutate mappings.

---

## Cutoff-Reached Rule

A metadata record is eligible to call Phase 14B only if at least one selected in-window raw bar has:

```text
timestamp >= cutoff_timestamp
```

This does **not** require an exact timestamp equal to cutoff, does not infer a bar interval, and does not apply or round a cutoff.

If no selected bar reaches the explicit cutoff:

```text
CUT_OFF_NOT_REACHED
```

Do not call Phase 14B.

This is a coverage check only. Phase 13F later decides which adapted bars are included at or before the cutoff.

---

## Phase 14B Call

Only after all prior eligibility and coverage checks succeed:

1. construct a fresh, immutable session-scoped `AlpacaHistoricalBarsPage`:
   - `requested_symbols=(normalized_symbol,)`
   - `bars_by_symbol` contains the selected in-window raw mappings only for that symbol
   - `next_page_token=None`
2. construct:
   ```python
   AlpacaHistoricalBarsIntradaySeriesRequest(
       symbol=normalized_symbol,
       session_id=trimmed_session_id,
       bucket=trimmed_bucket,
       cutoff_timestamp=cutoff_timestamp,
   )
   ```
3. call existing `build_intraday_series_from_historical_bars(...)` exactly once for that eligible record.

If the adapter succeeds:

```text
status = OK
reason = None
intraday_series = adapter_result.intraday_series
adapter_result = exact successful Phase 14B result
```

If the adapter fails:

```text
status = ADAPTER_FAILED
reason = ADAPTER_FAILED:<adapter result status>
intraday_series = None
adapter_result = exact failed Phase 14B result
```

No Phase 13F cumulative-volume function may be called in this phase.

---

## Immutability and Ownership

- New result models must be frozen.
- Do not mutate the supplied page, page mappings, raw mappings, metadata records, or any lower-level result.
- Session-scoped raw mappings passed to Phase 14B must be copied/protected.
- The session-scoped page must not include a raw page token.
- `source_raw_bar_count` is the number of raw bars under the requested symbol before session membership selection.
- `in_window_raw_bar_count` is the number selected by the half-open session window.
- Keep all inspectable artifacts available to callers through the result.

---

## Required Tests

Use manually constructed `AlpacaHistoricalBarsPage` and metadata fixtures only.

Test:

```text
valid single-session assembly calls Phase 14B and returns OK
selected in-window raw order is preserved
out-of-window bars are ignored rather than fed to Phase 14B
bar at session_start is included
bar at session_end is excluded
bar at cutoff is enough to satisfy coverage
bar after cutoff satisfies coverage but Phase 13F remains uncalled
no bar at/after cutoff → CUT_OFF_NOT_REACHED
absent page symbol → CUT_OFF_NOT_REACHED
symbol normalization and per-symbol bar isolation
metadata session ID and bucket trim/preservation
invalid symbol/session ID/bucket behavior
invalid datetime types, including date/string/numeric/bool
naive metadata timestamp behavior
metadata tzinfo mismatch
invalid session window
cutoff outside window, including cutoff exactly equal to session_end
is_complete non-bool and False behavior
invalid current_session_id behavior
current session in historical records
duplicate IDs:
  same normalized symbol + same trimmed/case-sensitive session ID
  all duplicate occurrences rejected
  same ID for different symbols is allowed
  differently cased IDs are distinct
page_collection_complete false
page_collection_complete non-bool
non-null page next_page_token
all page-completeness failures occur before adapter call
raw non-mapping / missing t / bad timestamp / naive timestamp / tz mismatch
malformed raw bar fails full session record
v is absent:
  assembly does not fail before adapter
  adapter result is captured as ADAPTER_FAILED:MISSING_RAW_VOLUME
adapter raw v pass-through is not revalidated here
adapter failure reason preserves exact lower-level status
batch result order, duplicate metadata records, and failures are preserved
source/in-window raw counts are correct
page and raw mappings are not mutated
no direct Phase 13F / Phase 13E–13I / transport / fetcher / runtime / factory / scanner / alert / trading hooks
```

Add a source-boundary test using AST or focused source inspection that rejects imports/references to disallowed modules and confirms the module calls only the approved Phase 14B adapter boundary for successful records.

Run the focused suite, full suite, and existing runtime smoke checks.

---

## README Note

Update only if useful:

```text
Phase 14D adds an offline historical-session assembler that applies explicit caller session metadata to a raw historical-bars page before delegating eligible session bars to the Phase 14B adapter.
It excludes incomplete page collections and incomplete/invalid sessions, and does not infer calendars or execute RVOL calculations.
It adds no runtime provider, network behavior, pagination, candidate composition, or live activation.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```

---

## Acceptance Criteria

Phase 14D is complete when:

```text
- explicit metadata records can produce inspectable per-session assembly results;
- incomplete page collections, incomplete sessions, invalid metadata, duplicate historical IDs, and current-session reuse are rejected deterministically;
- only bars in the half-open session window are passed to Phase 14B;
- an explicit coverage check requires a selected bar at or after cutoff;
- lower-level Phase 14B failure detail is preserved;
- no Phase 13F or RVOL calculation is run;
- no fetcher/network/runtime/provider/factory/candidate/trading capability is added;
- the full project suite remains green.
```
