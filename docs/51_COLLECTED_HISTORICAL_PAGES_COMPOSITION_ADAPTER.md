# Phase 15B — Collected Historical Pages Composition Adapter

## Status

**Planned.** This document defines Phase 15B only.

Phase 15A collects an ordered trail of opaque raw historical-bars pages through the existing one-page fetcher:

```text
explicit request
→ collected request/page artifacts
→ COMPLETE / MAX_PAGE_LIMIT_REACHED / REPEATED_NEXT_PAGE_TOKEN
```

Phase 15B adds the narrow adapter that turns a **complete** Phase 15A collection into one new downstream-compatible `AlpacaHistoricalBarsPage`:

```text
complete ordered collection
→ concatenate each requested symbol's raw bar sequences in page order
→ new terminal raw page
→ existing Phase 14D-compatible input
```

It does not parse, sort, deduplicate, validate, repair, or otherwise interpret raw bars.

---

## Goal

Create a pure offline composition adapter that:

1. accepts one `HistoricalBarsPageCollectionResult`;
2. preserves the exact source collection artifact in its own result;
3. composes only a terminally complete collection;
4. requires at least one collected page;
5. requires every collected page to have exactly the same ordered `requested_symbols` tuple as the first collected page;
6. concatenates raw bar sequences for each requested symbol in collected-page tuple order;
7. produces a fresh `AlpacaHistoricalBarsPage` with:
   - the first page’s exact `requested_symbols` tuple;
   - the concatenated raw sequences;
   - `next_page_token=None`;
8. returns a stable non-composed diagnostic for incomplete, empty, or incompatible collection artifacts;
9. makes no call to Phase 14D, Phase 14I, Phase 14J, Phase 14G, or any runtime/provider component.

The intended future path is:

```text
Phase 15A complete collection
→ Phase 15B composed raw page
→ future metadata/workflow input assembly
→ existing Phase 14I → 14J → 14G workflow
```

Phase 15B does not add that future handoff.

---

## Core Ownership Boundary

```text
Phase 15A owns:
  fetch sequence
  continuation-token progression
  maximum-page cap
  repeated-token detection
  collected request/page trail
  collection completeness

Phase 15B owns:
  complete-collection eligibility
  page-shape compatibility
  ordered raw-sequence concatenation
  one new terminal composed page
  composition diagnostics

Phase 14D / 14I / 14J / 14G own:
  raw-bar validation
  session metadata
  workflow orchestration
  historical RVOL behavior
```

Phase 15B must not:

```text
fetch pages
follow tokens
rewrite a collection status
inspect raw bar fields such as t, v, o, h, l, or c
parse timestamps
sort, deduplicate, filter, merge-by-timestamp, or repair raw bars
normalize symbols
infer sessions or completeness
construct a manifest
call the manifest adapter or workflow coordinator
calculate relative volume
register or activate a provider/runtime path
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
raw-bar parsing or validation
historical session-manifest construction or Phase 14I execution
Phase 14J coordinator execution
Phase 14G harness execution
direct Phase 14D / 14E / 14F calls
relative-volume calculation
candidate composition, scoring, filtering, or alerts
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

No live HTTP calls are permitted in tests.

---

## Existing Components to Reuse

Reuse only these public models/status containers:

```text
market_sentry.data.alpaca_historical_bars_fetcher
  AlpacaHistoricalBarsPage

market_sentry.data.historical_bars_page_collector
  HistoricalBarsPageCollectionResult
  HistoricalBarsPageCollectionStatus
```

Do not import or call:

```text
AlpacaHistoricalBarsFetcher
AlpacaHistoricalBarsQuery
AlpacaHistoricalBarsFetchError
HTTP transport modules
raw historical-bar adapters
historical_session_manifest
manifest_to_harness_orchestrator
historical_tod_rvol_harness
historical_session_assembly
historical_baseline_composition
current_session_tod_rvol
intraday_bucket_adapter
time_of_day_rvol
relative_volume modules
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

Phase 15B may read only these page fields:

```text
page.requested_symbols
page.bars_by_symbol
```

It may use `page.bars_by_symbol.get(symbol, ())` only to preserve opaque raw-bar sequences. It must not inspect any raw-bar mapping’s fields or values.

---

## Expected Files

Create:

```text
docs/51_COLLECTED_HISTORICAL_PAGES_COMPOSITION_ADAPTER.md
src/market_sentry/data/collected_historical_pages_composer.py
tests/test_collected_historical_pages_composer.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 14A–14K, Phase 15A, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Models

Use frozen dataclasses and a stable status container.

```python
@dataclass(frozen=True)
class CollectedHistoricalPagesCompositionResult:
    """One source collection and, when eligible, one terminal composed raw page."""

    source_collection: HistoricalBarsPageCollectionResult
    composed_page: AlpacaHistoricalBarsPage | None
    status: str
    reason: str | None = None
```

Exact names may vary, but retain all responsibilities:

```text
exact source collection artifact
new composed page or None
stable composition status
stable composition reason
```

Do not duplicate the source collection’s request, collected pages, unresolved token, or original diagnostics. Callers inspect `source_collection` directly.

---

## Public Function

Provide:

```python
def compose_collected_historical_pages(
    collection: HistoricalBarsPageCollectionResult,
) -> CollectedHistoricalPagesCompositionResult:
    ...
```

The adapter does not mutate `collection`, its request, any collected-page artifact, any source page, any page mapping, or any raw-bar mapping.

---

## Stable Statuses

Use exactly:

```text
COMPOSED
INCOMPLETE_COLLECTION
EMPTY_COMPLETE_COLLECTION
MISMATCHED_PAGE_REQUESTED_SYMBOLS
```

### 1. Eligible complete collection

A collection is eligible only if all of the following are true:

```text
collection.status == HistoricalBarsPageCollectionStatus.COMPLETE
collection.page_collection_complete is True
collection.next_page_token is None
```

If eligible and it contains at least one page with compatible symbol tuples:

```text
status = COMPOSED
reason = None
composed_page is a new AlpacaHistoricalBarsPage
```

### 2. Incomplete collection

Any collection that does not meet all three complete-collection conditions above must return:

```text
status = INCOMPLETE_COLLECTION
reason = INCOMPLETE_COLLECTION:<exact collection.status>
composed_page = None
```

This includes normal Phase 15A incomplete outcomes:

```text
MAX_PAGE_LIMIT_REACHED
REPEATED_NEXT_PAGE_TOKEN
```

It also safely prevents composition of a malformed manually constructed collection artifact that claims `COMPLETE` but has incomplete flags or an unresolved token.

Phase 15B must preserve the source collection’s exact diagnostics. It must not relabel, repair, or complete it.

### 3. Empty complete collection

A complete-shaped collection with:

```text
collection.collected_pages == ()
```

must return:

```text
status = EMPTY_COMPLETE_COLLECTION
reason = EMPTY_COMPLETE_COLLECTION
composed_page = None
```

This is a defensive structural result. Phase 15A itself should never produce an empty complete collection because it fetches at least one page before a terminal outcome.

### 4. Incompatible page symbol tuples

Use the first collected page’s exact `page.requested_symbols` tuple as the required page-shape contract.

Every later collected page must have an exactly equal ordered tuple. Do not compare sets and do not normalize symbols.

When any later page does not match:

```text
status = MISMATCHED_PAGE_REQUESTED_SYMBOLS
reason = MISMATCHED_PAGE_REQUESTED_SYMBOLS:<zero-based collected-page index>
composed_page = None
```

The index refers to the source collection’s tuple order, not its `HistoricalBarsCollectedPage.index` field. Do not sort or use the artifact index to establish order.

This does not inspect or validate page bar content.

---

## Composition Algorithm

For an eligible non-empty collection:

1. Retain the exact source collection in the result.
2. Read the first page’s exact tuple:

```python
requested_symbols = collection.collected_pages[0].page.requested_symbols
```

3. Verify every later source page has:

```python
page.requested_symbols == requested_symbols
```

4. For each symbol in `requested_symbols`, in tuple order:
   - visit collected pages in their existing tuple order;
   - obtain the page sequence with:

```python
page.bars_by_symbol.get(symbol, ())
```

   - concatenate the raw mapping sequence exactly in that order;
   - do not inspect a raw mapping;
   - do not sort, deduplicate, filter, or mutate it.

5. Construct one fresh terminal page:

```python
AlpacaHistoricalBarsPage(
    requested_symbols=requested_symbols,
    bars_by_symbol=composed_bars_by_symbol,
    next_page_token=None,
)
```

The `AlpacaHistoricalBarsPage` model owns its usual immutable storage/copying behavior.

The adapter must not guarantee source raw-mapping object identity in the new page, because the existing page model deliberately protects/copies mappings on construction. It must guarantee:

```text
raw-bar sequence order is preserved
raw-bar mapping values are passed through unchanged
symbol tuple order is preserved
no bar is intentionally added, removed, sorted, deduplicated, or interpreted
```

---

## Examples

### Valid two-page collection

```text
page 0:
  requested_symbols = (RVOL, OTHER)
  RVOL bars = [R1, R2]
  OTHER bars = [O1]

page 1:
  requested_symbols = (RVOL, OTHER)
  RVOL bars = [R3]
  OTHER bars = [O2, O3]
```

Output:

```text
requested_symbols = (RVOL, OTHER)
RVOL bars = [R1, R2, R3]
OTHER bars = [O1, O2, O3]
next_page_token = None
status = COMPOSED
```

No timestamps are parsed or compared.

### Incomplete collection

```text
source status = MAX_PAGE_LIMIT_REACHED
source next_page_token = NEXT
```

Output:

```text
composed_page = None
status = INCOMPLETE_COLLECTION
reason = INCOMPLETE_COLLECTION:MAX_PAGE_LIMIT_REACHED
```

### Symbol tuple mismatch

```text
page 0 requested_symbols = (RVOL, OTHER)
page 1 requested_symbols = (OTHER, RVOL)
```

Output:

```text
composed_page = None
status = MISMATCHED_PAGE_REQUESTED_SYMBOLS
reason = MISMATCHED_PAGE_REQUESTED_SYMBOLS:1
```

No page sorting or symbol reordering is permitted.

---

## Required Tests

### Source collection result helpers

Tests may manually construct `HistoricalBarsPageCollectionResult` and `HistoricalBarsCollectedPage` objects with local immutable pages. They must not construct fetchers, transports, or perform network calls.

### Complete composition behavior

Test:

```text
one-page complete collection:
  COMPOSED
  output requested_symbols preserve exact tuple order
  output page token None
  output sequences equal input raw sequences

multi-page complete collection:
  requested symbols with at least two symbols
  concatenate each symbol in source collection tuple order
  no sorting by timestamps
  no deduplication of identical raw mappings
  missing symbol key in a source page contributes an empty sequence
  source collection artifacts remain unchanged

raw-bar opacity:
  use raw mappings with deliberately malformed / mixed-type fields
  composition succeeds and preserves their order/value content
  proves no t/v/timestamp validation occurs
```

### Eligibility and compatibility behavior

Test:

```text
MAX_PAGE_LIMIT_REACHED:
  INCOMPLETE_COLLECTION
  exact source collection retained
  None composed page
  reason uses exact source status

REPEATED_NEXT_PAGE_TOKEN:
  INCOMPLETE_COLLECTION
  exact source collection retained
  None composed page

malformed complete-status collection:
  COMPLETE with page_collection_complete False
  → INCOMPLETE_COLLECTION

malformed complete-status collection:
  COMPLETE with non-null next_page_token
  → INCOMPLETE_COLLECTION

empty complete-shaped collection:
  EMPTY_COMPLETE_COLLECTION
  None composed page

page tuple mismatch:
  mismatched tuple ordering
  MISMATCHED_PAGE_REQUESTED_SYMBOLS:1
  None composed page

later mismatch:
  correct first/second, mismatch third
  MISMATCHED_PAGE_REQUESTED_SYMBOLS:2
```

### Identity and immutability

Test:

```text
result stores exact source collection object
source request / artifacts / pages remain unchanged
source collection pages are never mutated
result model is frozen
output composed page is a distinct new object
output raw mapping sequences are immutable through normal assignment
separate composition calls produce independent result and composed-page objects
```

### Downstream compatibility integration test

The composition module itself must not import or call Phase 14D. The test module may.

Create a complete two-page collection where a symbol’s raw historical bars are split across pages. Use explicit valid local historical-session metadata and invoke the actual Phase 14D public session assembly function with the composed page.

Assert:

```text
composition status = COMPOSED
composed page includes raw bars from both source pages in page order
actual Phase 14D receives the complete composed page
actual assembly status = OK
source raw bar count reflects both page sequences
```

The test must use local deterministic raw values only and no fetcher/transport/runtime behavior.

### Source-boundary test

Use AST or focused source inspection to verify the composition module:

```text
imports only approved page and collection models/status container
does not import/call fetchers, transports, raw adapters, Phase 14I / 14J / 14G,
Phase 14D / 14E / 14F, Phase 13 calculators, provider/factory/config/readiness/
runtime/scanner/alert/voice/candidate/trading modules
does not access raw bar mapping keys or values
does not sort, deduplicate, or parse raw bars
```

---

## README Note

Update only if useful:

```text
Phase 15B adds an offline adapter that turns a complete bounded historical-page collection into one terminal raw historical-bars page by preserving page order and concatenating each requested symbol's opaque raw-bar sequences.
Incomplete or incompatible collections remain diagnostic artifacts and are not composed.
It does not fetch data, parse or repair bars, build metadata, activate a runtime provider, or add trading/order functionality.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 15B is complete when:

```text
- only complete Phase 15A collection artifacts are eligible for composition;
- incomplete, capped, looped, empty, and incompatible collections return stable non-composed diagnostics;
- successful composition preserves requested-symbol order and raw-bar page-order sequences;
- raw bars are not parsed, sorted, deduplicated, filtered, or repaired;
- the exact source collection remains available in the result;
- a local downstream compatibility test demonstrates the composed page can feed actual Phase 14D assembly;
- no fetcher/transport, metadata/workflow, RVOL, runtime/provider, scanner, alert, voice, or trading capability is added;
- the full project suite remains green.
```
