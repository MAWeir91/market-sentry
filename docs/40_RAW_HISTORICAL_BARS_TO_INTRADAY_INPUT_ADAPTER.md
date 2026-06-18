# Phase 14B — Raw Historical Bars to Intraday Input Adapter

## Status

**Planned.** This document defines Phase 14B only.

Phase 14A added an injected, one-page Alpaca historical-bars fetcher that returns raw immutable bar mappings. Phase 14B adds a strict, offline-only adapter that converts those raw mappings into Phase 13F-compatible `IntradayVolumeSeriesInput` objects.

This phase does **not** call the fetcher, paginate, activate live mode, calculate RVOL, or construct candidates.

---

## Goal

Create this explicit path:

```text
AlpacaHistoricalBarsPage
+ caller-supplied symbol/session ID/bucket/cutoff metadata
→ strict raw timestamp parsing
→ preserve raw bar order and raw volume value
→ IntradayVolumeSeriesInput
→ inspectable per-series success/failure result
```

The caller owns the selected page, symbol, session ID, bucket, cutoff timestamp, and whether the page is complete enough for later use.

Phase 13F remains the owner of bar ordering, duplicate timestamp, downstream volume, and cutoff-inclusion validation. Phase 14B only defines raw timestamp conversion and structural adaptation.

---

## Hard Boundaries

Do not add:

- runtime activation;
- provider-factory registration or new provider values;
- CLI, polling, scanner, report, alert, or voice changes;
- HTTP requests, fetcher construction, pagination, retries, caching, WebSockets, or streaming;
- automatic watchlist/config/environment reads;
- session, bucket, cutoff, calendar, holiday, regular-hours, halt, split, or market-session inference;
- time-zone conversion or normalization;
- raw-bar aggregation;
- RVOL, candidate, scoring, or alert computation;
- live network calls or credentials in tests;
- order APIs, order placement, trade execution, or trading recommendations.

`live_composed` must remain gated and reserved/inactive.

---

## Existing Components to Reuse

Reuse existing public models only:

```text
market_sentry.data.alpaca_historical_bars_fetcher
  AlpacaHistoricalBarsPage

market_sentry.data.intraday_bucket_adapter
  IntradayVolumeBar
  IntradayVolumeSeriesInput
```

Do not instantiate or import:

```text
AlpacaHistoricalBarsFetcher
HttpTransport
StdlibHttpTransport
OfflineIntradayRelativeVolumeFixtureProvider
OfflineIntradayRvolCandidateCompositionHarness
LiveCandidateBuilder
LiveComposedMarketDataProvider
provider factory
time_of_day_rvol
intraday_rvol_harness
intraday_rvol_fixture_provider
intraday_rvol_candidate_composition_harness
```

---

## Expected Files

Create:

```text
docs/40_RAW_HISTORICAL_BARS_TO_INTRADAY_INPUT_ADAPTER.md
src/market_sentry/data/alpaca_historical_bars_adapter.py
tests/test_alpaca_historical_bars_adapter.py
```

Update only if useful:

```text
README.md
```

Do not modify runtime, factory, config, readiness, fetcher, Phase 13 modules, candidate builder, scanner, alert, or existing fixture provider files.

---

## Suggested Public Models

```python
@dataclass(frozen=True)
class AlpacaHistoricalBarsIntradaySeriesRequest:
    symbol: str
    session_id: str
    bucket: str
    cutoff_timestamp: datetime

@dataclass(frozen=True)
class AlpacaHistoricalBarsIntradaySeriesResult:
    symbol: str
    session_id: str
    bucket: str
    cutoff_timestamp: datetime | None
    intraday_series: IntradayVolumeSeriesInput | None
    status: str
    reason: str | None = None
    raw_bar_count: int = 0
    converted_bar_count: int = 0
```

Exact names may vary, but retain the same explicit responsibilities.

Suggested stable status strings:

```text
OK
EMPTY_SYMBOL
INVALID_SESSION_ID
EMPTY_BUCKET
INVALID_CUTOFF_TIMESTAMP
NAIVE_CUTOFF_TIMESTAMP
INVALID_RAW_BAR
MISSING_RAW_TIMESTAMP
INVALID_RAW_TIMESTAMP
NAIVE_RAW_TIMESTAMP
MISMATCHED_TIMESTAMP_TIMEZONE
MISSING_RAW_VOLUME
```

---

## Public Functions

```python
def build_intraday_series_from_historical_bars(
    page: AlpacaHistoricalBarsPage,
    request: AlpacaHistoricalBarsIntradaySeriesRequest,
) -> AlpacaHistoricalBarsIntradaySeriesResult: ...
```

```python
def build_intraday_series_from_historical_bars_results(
    page: AlpacaHistoricalBarsPage,
    requests: Sequence[AlpacaHistoricalBarsIntradaySeriesRequest],
) -> list[AlpacaHistoricalBarsIntradaySeriesResult]: ...
```

The batch helper preserves request order, including duplicate symbols and failures.

No success-only mapping is needed in this phase.

---

## Caller Metadata Validation

```text
symbol:
  trim surrounding whitespace and uppercase
  blank → EMPTY_SYMBOL

session_id:
  non-empty string after trimming
  preserve case/content after trimming
  do not parse as date/timestamp
  invalid → INVALID_SESSION_ID

bucket:
  non-empty string after trimming
  preserve resulting label exactly
  do not parse as time
  invalid → EMPTY_BUCKET

cutoff_timestamp:
  must be datetime, not date/string/numeric/bool/missing
  must be timezone-aware
  no conversion, normalization, or calendar validation
  invalid type → INVALID_CUTOFF_TIMESTAMP
  naive → NAIVE_CUTOFF_TIMESTAMP
```

Use only `page.bars_by_symbol` entries for the normalized explicit symbol.

If the normalized requested symbol is absent from the page mapping, treat it as an empty raw sequence and return a successful `IntradayVolumeSeriesInput` with `bars == ()`. Phase 13F later owns the `NO_INTRADAY_BARS` decision.

Do not invent a missing bar, timestamp, volume, bucket, session ID, or cutoff.

---

## Raw Bar Rules

For every raw bar, in exact page-provided order:

```text
raw bar must be a mapping → INVALID_RAW_BAR
raw key "t" must exist → otherwise MISSING_RAW_TIMESTAMP
raw key "v" must exist → otherwise MISSING_RAW_VOLUME

raw timestamp:
  must be a non-empty string with no surrounding whitespace
  must contain a T separator
  parse via datetime.fromisoformat after terminal Z is changed to +00:00 only for parsing syntax
  parsed timestamp must be timezone-aware
  parsed timestamp tzinfo must equal cutoff_timestamp.tzinfo exactly
```

Construct:

```python
IntradayVolumeBar(
    timestamp=parsed_timestamp,
    volume=raw_bar["v"],
)
```

Important:

```text
Preserve raw bar order exactly.
Do not sort, deduplicate, group, aggregate, filter, or apply the cutoff.
Do not compare bar timestamps to each other.
Do not convert time zones.
Do not infer sessions/buckets from raw data.
Do not coerce or validate raw volume beyond requiring the v key to exist.
Pass raw v through unchanged; Phase 13F owns numeric/finite/positive/non-bool volume validation.
Any malformed raw bar invalidates the full requested series. Do not skip it.
```

Replacing a terminal `Z` with `+00:00` is accepted only for ISO parsing syntax; it is not a time-zone conversion.

---

## Immutability

- Result models are frozen.
- Successful `IntradayVolumeSeriesInput.bars` must be a tuple copy of `IntradayVolumeBar` values.
- Do not mutate page, mappings, raw bars, or request objects.
- `raw_bar_count` is the raw page sequence length for the requested symbol.
- `converted_bar_count` is zero on failure; on success it equals `raw_bar_count`.

---

## Required Tests

Use manually constructed `AlpacaHistoricalBarsPage` objects only. Do not instantiate the fetcher or HTTP transport.

Test:

```text
Z-suffixed timestamp parses as aware datetime
explicit +00:00 timestamp parses without conversion
raw bar order is preserved
raw volume passes through unchanged, including a deliberately invalid downstream value
missing page symbol yields successful empty input series
symbol trim/uppercase behavior
session ID trim/preservation and invalid session
bucket trim/preservation and invalid bucket
cutoff rejects date/string/numeric/bool/missing values
naive cutoff is rejected
missing t
missing v
non-mapping raw bar
empty/whitespace/surrounding-whitespace raw timestamps
timestamp lacking T separator
invalid timestamp syntax
naive raw timestamp
raw timestamp timezone mismatch
one invalid raw bar invalidates whole series
batch preserves order, duplicate symbols, and failures
successful series owns tuple bar data independently
no raw sorting/dedup/filtering/cutoff application
no raw-volume coercion or downstream volume validation
no fetcher/transport/env/config/factory/Phase13E-13I/candidate/scanner/alert/trading hooks
existing Phase 14A tests remain green
mock, fixture, and composed_fixture runtime behavior remains unchanged
alpaca remains placeholder
live_composed remains gated/reserved inactive
full suite passes
```

Include one small handoff test proving a successful result can be sent to the existing Phase 13F function and that **Phase 13F**, not this adapter, rejects a passed-through invalid raw volume.

---

## README

Update only if useful:

```text
Phase 14B adds a strict offline adapter from raw Alpaca historical-bar mappings to Phase 13F intraday input models.
Caller-supplied metadata determines symbol, session ID, bucket, and cutoff.
The adapter parses timestamps but does not fetch data, infer sessions, convert time zones, validate downstream volume, calculate RVOL, register a runtime provider, or activate live mode.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```

---

## Acceptance Criteria

```text
Raw one-page mappings adapt to explicit Phase 13F IntradayVolumeSeriesInput objects.
Timestamp parsing and exact tzinfo compatibility are deterministic and test-covered.
Raw volume values pass to Phase 13F unchanged.
Caller metadata remains explicit.
Malformed raw data returns stable inspectable failures.
No fetcher/network/runtime/factory/RVOL/candidate path is activated.
The project suite remains green.
```
