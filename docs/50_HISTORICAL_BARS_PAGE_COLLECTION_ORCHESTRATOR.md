# Phase 15A — Historical Bars Page Collection Orchestrator

## Status

**Planned.** This document defines Phase 15A only.

Phase 14A introduced `AlpacaHistoricalBarsFetcher`, a single-page raw historical-bars fetcher behind an injected HTTP transport. Its one-page behavior was intentional: it exposed continuation tokens without assigning pagination ownership.

Phase 15A adds the explicit higher-level owner for bounded page collection:

```text
explicit symbols
+ one explicit historical-bars query
+ explicit maximum page limit
+ caller-supplied single-page fetcher
→ ordered raw page/request trail
→ terminal / page-limit / repeated-token collection outcome
```

The fetcher remains a one-page component. Phase 15A is the only component in this phase allowed to follow its `next_page_token` values.

This phase does not merge pages, adapt raw bars, build sessions, create metadata manifests, calculate relative volume, register a provider, or activate any runtime path.

---

## Goal

Create a pure, transport-injected historical-page collection orchestrator that:

1. accepts a caller-supplied `AlpacaHistoricalBarsFetcher`;
2. accepts explicit symbols, an explicit initial `AlpacaHistoricalBarsQuery`, and an explicit maximum page count;
3. calls the existing single-page fetcher in sequence;
4. preserves each exact successful page and the exact query used to request it;
5. follows opaque continuation tokens only through fresh follow-up query objects;
6. stops deterministically when:
   - a page returns `next_page_token is None`;
   - the configured page limit is reached while a token remains;
   - a response returns a token that has already been used to request any page in this collection;
7. exposes a stable completion/incompletion diagnostic with the unresolved token when applicable;
8. propagates existing fetcher and transport errors unchanged.

The intended future path is:

```text
explicit historical collection request
→ Phase 15A ordered raw pages
→ future raw-page composition / session-scoped page preparation
→ existing Phase 14I → 14J → 14G workflow
```

Phase 15A does not add that future composition or workflow handoff.

---

## Why This Is a Separate Phase

Phase 14A correctly made automatic pagination out of scope for a low-level fetcher. A fetcher should perform one explicit request and return one immutable raw response page.

Pagination has different responsibilities:

```text
continuation-token progression
request/page ordering
maximum-page safety
loop detection
incomplete-collection status
partial successful-page retention
```

Those responsibilities belong in a small, separately testable collector. This phase makes them explicit without changing the single-page fetcher contract.

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
automatic watchlist lookup, screeners, broad-market discovery, or crawling
WebSockets, streaming, persistent connections, retries, rate-limit backoff, caching, or background work
raw-bar parsing, timestamp parsing, time-zone conversion, session inference, bucket construction, or aggregation
merging, sorting, deduplicating, or filtering raw bars across pages
historical session-manifest construction or Phase 14I execution
Phase 14J coordinator execution
Phase 14G harness execution
direct Phase 14D / 14E / 14F calls
relative-volume calculation
candidate composition, scoring, filtering, alerts, or voice changes
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

`live_composed` remains gated and reserved/inactive.

No live HTTP calls are permitted in tests. Tests must use fake or stubbed injected fetcher/transport behavior only.

---

## Existing Components to Reuse

Reuse only these public interfaces:

```text
market_sentry.data.alpaca_historical_bars_fetcher
  AlpacaHistoricalBarsFetcher
  AlpacaHistoricalBarsFetchError
  AlpacaHistoricalBarsPage
  AlpacaHistoricalBarsQuery
```

The collector must receive a fetcher by caller injection. It must not construct:

```text
AlpacaMarketDataSettings
HttpTransport
FakeHttpTransport
StdlibHttpTransport
AlpacaHistoricalBarsFetcher
provider/factory/config objects
```

The collector may call only:

```python
fetcher.fetch_bars(symbols, query)
```

Do not import or call:

```text
build_historical_bars_http_request
parse_historical_bars_http_response
market_sentry.data.http
market_sentry.data.http_stdlib
alpaca_historical_bars_adapter
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

Phase 15A must not inspect raw bar contents or page `bars_by_symbol` values. It treats each `AlpacaHistoricalBarsPage` as an opaque immutable artifact, except for reading `next_page_token`.

---

## Expected Files

Create:

```text
docs/50_HISTORICAL_BARS_PAGE_COLLECTION_ORCHESTRATOR.md
src/market_sentry/data/historical_bars_page_collector.py
tests/test_historical_bars_page_collector.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 14A or Phase 14B–14K, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Models

Use frozen dataclasses and stable status containers.

```python
@dataclass(frozen=True)
class HistoricalBarsPageCollectionRequest:
    """Explicit inputs for one bounded historical-bars page collection."""

    symbols: tuple[str, ...]
    initial_query: AlpacaHistoricalBarsQuery
    max_pages: int
```

The request must preserve the caller’s supplied symbol values and initial query object. It must not normalize symbols, inspect timeframe/start/end semantics, or alter an existing initial page token.

`max_pages` must be:

```text
a real integer, not bool
at least 1
at most 1000
```

Invalid values must raise a dedicated value error at request construction:

```text
HistoricalBarsPageCollectionError
```

No default page cap is permitted. The caller must choose one explicitly.

```python
@dataclass(frozen=True)
class HistoricalBarsCollectedPage:
    """One successful fetch request and its exact raw response page."""

    index: int
    query: AlpacaHistoricalBarsQuery
    page: AlpacaHistoricalBarsPage
```

```python
@dataclass(frozen=True)
class HistoricalBarsPageCollectionResult:
    """Ordered raw page artifacts and terminal collection state."""

    request: HistoricalBarsPageCollectionRequest
    collected_pages: tuple[HistoricalBarsCollectedPage, ...]
    status: str
    page_collection_complete: bool
    next_page_token: str | None
    reason: str | None = None
```

Exact names may vary, but retain these responsibilities:

```text
original request object
ordered request/page artifact trail
stable terminal status
explicit completion boolean
exact unresolved response token, if incomplete
stable reason
```

Do not flatten raw pages, copy bars into a new aggregate, or duplicate page internals in the result.

---

## Public Function

Provide:

```python
def collect_historical_bars_pages(
    fetcher: AlpacaHistoricalBarsFetcher,
    request: HistoricalBarsPageCollectionRequest,
) -> HistoricalBarsPageCollectionResult:
    ...
```

The collector must use:

```text
request.symbols
request.initial_query
request.max_pages
```

It must not mutate the request or initial query.

---

## Stable Statuses

Use explicit stable status values:

```text
COMPLETE
MAX_PAGE_LIMIT_REACHED
REPEATED_NEXT_PAGE_TOKEN
```

### Complete collection

When a fetched page returns:

```text
next_page_token is None
```

return:

```text
status = COMPLETE
page_collection_complete = True
next_page_token = None
reason = None
```

### Maximum page limit

When a page returns a non-null continuation token but the collection has already retained `max_pages` successful pages, return:

```text
status = MAX_PAGE_LIMIT_REACHED
page_collection_complete = False
next_page_token = exact unresolved response token
reason = MAX_PAGE_LIMIT_REACHED:<exact unresolved response token>
```

Do not fetch another page.

### Repeated token

When a fetched page returns a non-null continuation token that is equal to a token already used to request any page in the same collection, return:

```text
status = REPEATED_NEXT_PAGE_TOKEN
page_collection_complete = False
next_page_token = exact repeated response token
reason = REPEATED_NEXT_PAGE_TOKEN:<exact repeated response token>
```

Do not fetch another page.

A token used by the initial query counts as already used if `initial_query.page_token` is non-null.

No other collector statuses are permitted.

---

## Page-Collection Algorithm

Use this exact high-level behavior.

### Initialization

```text
current_query = request.initial_query
used_request_tokens = set()
if current_query.page_token is not None:
  add that exact query token to used_request_tokens
collected_pages = []
```

The collector itself must not trim, normalize, uppercase, lowercase, or otherwise alter any token.

### One fetch iteration

For each iteration:

1. Call the fetcher exactly once:

```python
page = fetcher.fetch_bars(request.symbols, current_query)
```

2. Retain a fresh `HistoricalBarsCollectedPage`:

```python
index = zero-based fetched-page index
query = exact current_query object
page = exact page object returned by the fetcher
```

3. Read only:

```python
page.next_page_token
```

4. Apply terminal checks in this exact priority:

```text
a. token is None
   → COMPLETE

b. token is already in used_request_tokens
   → REPEATED_NEXT_PAGE_TOKEN

c. collected successful page count is now max_pages
   → MAX_PAGE_LIMIT_REACHED

d. otherwise:
   add the exact token to used_request_tokens
   build the next query
   continue
```

The repeated-token check intentionally takes precedence over the page-cap result when both could apply after the same final fetched page. It gives the caller the more specific collection failure.

### Follow-up queries

For a continuation token that is neither terminal, repeated, nor blocked by the cap:

```python
next_query = replace(current_query, page_token=page.next_page_token)
```

Requirements:

```text
follow-up query is a fresh object
timeframe is unchanged
start is unchanged
end is unchanged
limit is unchanged
sort is unchanged
only page_token changes
```

Pass the returned response token directly into the follow-up query construction. The collector must add no independent token cleanup or normalization.

The current `AlpacaHistoricalBarsQuery` model owns its own construction-time validation behavior. The collector must not duplicate it.

---

## Fetcher Error Policy

Do not catch, wrap, translate, suppress, or retry existing fetcher/transport errors.

For example, these must propagate unchanged from the fetcher:

```text
AlpacaHistoricalBarsFetchError
HttpTransportError
HttpTimeoutError
HttpStatusError
```

If a later page fetch raises, no collection result is returned. Earlier successful page artifacts are not exposed through an alternate global cache or side channel.

This phase’s result diagnostics are deliberately reserved for successful-response continuation outcomes:

```text
COMPLETE
MAX_PAGE_LIMIT_REACHED
REPEATED_NEXT_PAGE_TOKEN
```

---

## Artifact Preservation Rules

The result must preserve:

```text
exact request object passed by caller
exact `AlpacaHistoricalBarsQuery` object used for each fetch
exact `AlpacaHistoricalBarsPage` object returned by each successful fetch
page order matching fetch order
```

Do not:

```text
copy or reconstruct the request
copy or mutate queries
copy, merge, inspect, sort, filter, or deduplicate page bars
rewrite tokens
insert synthetic pages
fetch past terminal/limit/repeated-token state
```

The `collected_pages` tuple itself must be immutable. `HistoricalBarsCollectedPage` and `HistoricalBarsPageCollectionResult` must be frozen.

No cache, global state, or shared mutable state is permitted.

---

## Required Tests

### Request tests

Test:

```text
max_pages accepts 1 and 1000
max_pages rejects bool
max_pages rejects non-int
max_pages rejects 0 and negative values
max_pages rejects values above 1000
request is frozen
symbols are tuple-protected
initial query object is retained
```

Do not add new symbol normalization/validation behavior in the request model.

### Call flow and token progression

Use a lightweight recording fetcher stub that implements `fetch_bars(symbols, query)` and returns caller-controlled `AlpacaHistoricalBarsPage` objects.

Test:

```text
one terminal page:
  one fetch
  one collected page
  COMPLETE
  page_collection_complete True
  next_page_token None

multi-page token progression:
  page tokens A → B → None
  three fetches
  three collected pages in exact order
  query page tokens:
    initial token
    A
    B
  only page_token changes across follow-up queries

non-null initial query page token:
  first fetch uses exact initial query object
  continuation follows normally
```

### Page-cap behavior

Test:

```text
max_pages = 1
first response token = NEXT
→ one fetch only
→ one retained artifact
→ MAX_PAGE_LIMIT_REACHED
→ incomplete
→ unresolved token NEXT
→ exact reason
```

Also test a cap after multiple successful pages.

### Repeated-token behavior

Test:

```text
initial query token None
page tokens A → A
→ two fetches
→ two retained artifacts
→ REPEATED_NEXT_PAGE_TOKEN
→ incomplete
→ unresolved token A
→ exact reason
```

Test a non-adjacent loop:

```text
A → B → A
```

Test initial-token loop:

```text
initial query page_token = SEED
first response next_page_token = SEED
→ one fetch only
→ REPEATED_NEXT_PAGE_TOKEN
```

Test status precedence when the repeated token occurs on the final allowed fetched page:

```text
REPEATED_NEXT_PAGE_TOKEN wins over MAX_PAGE_LIMIT_REACHED
```

### Identity and immutability

Test:

```text
fetcher receives request.symbols by identity
first fetch receives request.initial_query by identity
each collected artifact stores exact query/page object identities
result stores exact request object identity
collected_pages is a tuple
artifact/result models are frozen
separate calls have no shared collection state
original request/query/page objects remain unchanged
```

### Fetcher-error propagation

With a recording fetcher that raises supplied exceptions, verify that:

```text
AlpacaHistoricalBarsFetchError propagates unchanged
a transport-style error propagates unchanged
no retry occurs
no follow-up fetch occurs
```

### Existing-fetcher integration test

Use the real `AlpacaHistoricalBarsFetcher` with the existing fake injected transport and deterministic JSON responses:

```text
first response:
  next_page_token = NEXT

second response:
  next_page_token = None
```

Assert:

```text
collection COMPLETE
two transport requests
first HTTP request omits page_token
second HTTP request includes page_token NEXT
both raw pages are retained in order
no live HTTP or credentials
```

### Source boundary test

Use AST or focused source inspection to verify the collector:

```text
imports only the approved Phase 14A public fetcher/page/query interfaces
does not import or call raw adapters
does not import or call Phase 14I / 14J / 14G
does not import or call Phase 14D / 14E / 14F
does not import or call Phase 13 calculations
does not import HTTP transport/config/provider/factory/readiness/runtime/
scanner/alert/voice/candidate/trading modules
does not access page.bars_by_symbol
```

---

## README Note

Update only if useful:

```text
Phase 15A adds an explicit, bounded, transport-injected historical-bars page collector above the existing one-page Alpaca fetcher.
It retains the ordered raw request/page trail and reports complete, page-limit, or repeated-token outcomes.
It does not merge or parse bars, create session metadata, wire runtime providers, activate live mode, or add trading/order functionality.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 15A is complete when:

```text
- the collector follows continuation tokens only through the existing single-page fetcher;
- collection is bounded by caller-selected max_pages;
- terminal, page-limit, and repeated-token outcomes are deterministic and inspectable;
- every successful request/page pair is retained in order without raw-bar transformation;
- fetcher/transport errors propagate unchanged and are not retried;
- tests include both recording-stub behavior and real-fetcher + fake-transport integration;
- no raw-bar composition, session metadata, historical RVOL workflow handoff, runtime/provider activation, or trading capability is added;
- the full project suite remains green.
```
