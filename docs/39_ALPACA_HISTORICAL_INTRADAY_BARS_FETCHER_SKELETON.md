# Phase 14A — Alpaca Historical Intraday Bars Fetcher Skeleton

## Status

**Planned.** This document defines Phase 14A only.

Phase 13J completed deterministic offline scenarios for the full intraday-RVOL-to-candidate path. Phase 14A begins a carefully isolated real-data plumbing path by adding an Alpaca historical stock-bars fetcher behind the existing injected HTTP transport.

This phase does **not** activate a live provider or scanner runtime.

---

## Goal

Create a watchlist-only, transport-injected Alpaca historical intraday-bars fetcher that:

1. accepts an explicit caller-supplied symbol sequence;
2. builds one Alpaca historical-bars HTTP request;
3. sends the request through the existing injected `HttpTransport`;
4. parses the JSON response envelope;
5. returns raw, immutable per-symbol intraday bar mappings plus an inspectable `next_page_token`;
6. performs no automatic pagination, session inference, time-zone conversion, bucket construction, RVOL calculation, candidate building, or runtime activation.

Expected path:

```text
explicit caller-supplied symbols + explicit historical-bars query
→ Alpaca historical-bars HTTP request
→ injected HttpTransport
→ raw immutable per-symbol bar mappings + next_page_token
```

The Alpaca historical stock-bars endpoint is `GET /v2/stocks/bars`. It accepts a comma-separated symbol list and supports parameters including `timeframe`, `start`, `end`, `limit`, `feed`, `page_token`, and `sort`. Results may be paginated, so this phase must expose the response token but must not follow it automatically.

---

## Why This Is the Next Step

The Phase 13F–13J stack already proves the offline intraday volume / time-of-day RVOL / candidate-composition path. It deliberately requires caller-supplied bars.

Phase 14A introduces only the narrowly scoped boundary needed to obtain raw historical bars later:

```text
Alpaca historical bar response
→ future explicit raw-bar adapter
→ Phase 13F intraday input
→ existing Phase 13E–13I path
```

The raw response is intentionally **not** connected to Phase 13F in this phase. A later dedicated adapter must define timestamp parsing, time-zone policy, session IDs, bucket labels, cutoff selection, and page-completion policy explicitly.

---

## Hard Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is **not** a trading bot.

Do not add:

- runtime activation;
- provider-factory registration or a new `MARKET_SENTRY_PROVIDER` value;
- CLI flags, reports, polling changes, or scanner-loop changes;
- broad-market scanning, screeners, symbol discovery, or crawling;
- automatic watchlist reads from configuration or environment variables;
- WebSockets, streaming, or persistent connections;
- automatic pagination;
- automatic retries, rate-limit backoff, or caching;
- historical-bar aggregation, daily baselines, bucket construction, session assignment, cutoff selection, RVOL calculation, candidate building, or scoring;
- calendar, regular-hours, holiday, early-close, halt, split, or time-zone inference;
- real credentials in tests;
- live HTTP calls in tests;
- order APIs, brokerage actions, order placement, execution, or buy/sell/enter/exit recommendations.

No code in this phase may activate `live_composed`.

---

## Existing Components to Reuse

Reuse existing public interfaces where appropriate:

```text
market_sentry.data.alpaca
  AlpacaMarketDataSettings
  AlpacaRequest
  BARS_PATH
  DEFAULT_FEED
  build_auth_headers(...)
  build_bars_request(...)

market_sentry.data.http
  HttpRequest
  HttpResponse
  HttpTransport
  HttpTransportError
  FakeHttpTransport
```

The fetcher must receive a transport by dependency injection. It must not instantiate `StdlibHttpTransport`, read environment variables, or construct a provider/factory.

It may extend `market_sentry.data.alpaca.build_bars_request(...)` only when that is the smallest way to add explicit historical query parameters. Any extension must preserve current Phase 10A behavior and tests.

Do not import or call:

```text
Phase 13E time_of_day_rvol
Phase 13F intraday_bucket_adapter
Phase 13G intraday_rvol_harness
Phase 13H intraday_rvol_fixture_provider
Phase 13I intraday_rvol_candidate_composition_harness
LiveCandidateBuilder
LiveComposedMarketDataProvider
build_live_composed_provider
```

---

## Expected Files

Create:

```text
docs/39_ALPACA_HISTORICAL_INTRADAY_BARS_FETCHER_SKELETON.md
src/market_sentry/data/alpaca_historical_bars_fetcher.py
tests/test_alpaca_historical_bars_fetcher.py
```

Modify only if needed:

```text
src/market_sentry/data/alpaca.py
tests/test_alpaca_provider.py
README.md
```

Do not modify unless unavoidable:

```text
src/market_sentry/main.py
src/market_sentry/__main__.py
src/market_sentry/data/factory.py
src/market_sentry/config.py
src/market_sentry/live_readiness.py
src/market_sentry/data/http.py
src/market_sentry/data/http_stdlib.py
src/market_sentry/data/alpaca_fetcher.py
src/market_sentry/data/fmp_fetcher.py
src/market_sentry/data/live_provider_builder.py
src/market_sentry/data/live_composed_provider.py
src/market_sentry/data/live_candidate_builder.py
src/market_sentry/data/relative_volume.py
src/market_sentry/data/intraday_bucket_adapter.py
src/market_sentry/data/time_of_day_rvol.py
scanner modules
alerts modules
fixture/mock/composed_fixture provider modules
```

---

## Suggested Public Models

The exact names may vary, but preserve the responsibilities and inspectability.

```python
from dataclasses import dataclass
from collections.abc import Mapping

@dataclass(frozen=True)
class AlpacaHistoricalBarsQuery:
    """Explicit query controls for one historical-bars response page."""

    timeframe: str
    start: str
    end: str
    limit: int = 1000
    page_token: str | None = None
    sort: str = "asc"

@dataclass(frozen=True)
class AlpacaHistoricalBarsPage:
    """Raw one-page historical-bar response for requested symbols only."""

    requested_symbols: tuple[str, ...]
    bars_by_symbol: Mapping[str, tuple[Mapping[str, object], ...]]
    next_page_token: str | None
```

A raw bar mapping should preserve Alpaca-style bar fields such as:

```text
t  timestamp
o  open
h  high
l  low
c  close
v  volume
n  trade count
vw volume-weighted price
```

This phase does **not** interpret these fields as valid Phase 13F bars. In particular:

- do not parse `t` into a `datetime`;
- do not convert a time zone;
- do not validate whether `v` is usable downstream;
- do not sort, deduplicate, or aggregate bars;
- do not infer a session or bucket;
- do not alter raw values.

The page must retain only symbols explicitly requested by the caller. A requested symbol with no returned bars should be represented with an empty tuple.

Use `MappingProxyType` or an equivalent copy-protected mapping for outer mappings and every returned raw bar mapping. A frozen dataclass alone is insufficient.

---

## Query Validation

The fetcher request builder may validate only stable request-shape rules:

```text
timeframe
  non-empty trimmed string; no timeframe grammar inference required

start / end
  non-empty trimmed strings; do not parse, compare, or convert them

limit
  integer, not bool, between 1 and 10000 inclusive

sort
  exactly "asc" or "desc"

page_token
  None or non-empty trimmed string
```

Do not derive defaults for absent `start` or `end`. Callers must explicitly provide both.

Use the existing Alpaca settings feed or the current default feed. Do not read a feed, symbol, key, or secret from the environment.

---

## HTTP Request Shape

Provide a testable public helper, for example:

```python
def build_historical_bars_http_request(
    symbols: Sequence[str],
    settings: AlpacaMarketDataSettings,
    query: AlpacaHistoricalBarsQuery,
    *,
    timeout_seconds: float = 10.0,
) -> HttpRequest: ...
```

Required request behavior:

```text
method: GET
url: settings.base_url + /v2/stocks/bars
symbols: normalized, comma-separated explicit caller symbols
feed: settings.feed or current default
timeframe: query timeframe
start: query start
end: query end
limit: query limit
sort: query sort
page_token: present only when query page_token is non-None
headers: existing Alpaca auth-header builder output
```

Any request model containing headers must preserve existing secret-safe representation behavior. Do not log headers, query parameters, or URLs with secret values.

---

## Response Parsing

Provide a testable public parser, for example:

```python
def parse_historical_bars_http_response(
    response: HttpResponse,
    requested_symbols: Sequence[str],
) -> AlpacaHistoricalBarsPage: ...
```

Required parser behavior:

1. Parse response `body` as JSON.
2. Require the top-level payload to be an object.
3. Require `bars` to be an object when present.
4. Normalize requested symbols using the existing project convention: trim and uppercase; ignore blank values.
5. Return only requested normalized symbols.
6. For every requested symbol:
   - absent bar list means an empty tuple;
   - a present bar list must be a JSON array;
   - every bar must be a JSON object;
   - copy/protect each raw bar mapping without interpreting fields.
7. Expose `next_page_token` exactly when it is `null` or a non-empty string.
8. Do not follow pagination tokens automatically.
9. Do not sort, validate, or transform raw bar data.

Suggested fetcher-specific error type:

```python
class AlpacaHistoricalBarsFetchError(ValueError):
    """Raised for invalid request shape or unparseable historical-bar response."""
```

Error messages must remain secret-safe and must not include credential values or request headers.

Transport errors should propagate through the existing transport error types rather than being converted into generic fetch errors.

---

## Fetcher Class

Provide an injected, non-runtime fetcher:

```python
class AlpacaHistoricalBarsFetcher:
    """Fetch one raw Alpaca historical-bars page through an injected transport."""

    def __init__(
        self,
        *,
        settings: AlpacaMarketDataSettings,
        transport: HttpTransport,
        timeout_seconds: float = 10.0,
    ) -> None: ...

    def build_request(
        self,
        symbols: Sequence[str],
        query: AlpacaHistoricalBarsQuery,
    ) -> HttpRequest: ...

    def fetch_bars(
        self,
        symbols: Sequence[str],
        query: AlpacaHistoricalBarsQuery,
    ) -> AlpacaHistoricalBarsPage: ...
```

Required fetch behavior:

```text
- build the request through the public request helper;
- normalize explicit caller symbols only;
- if the normalized symbol sequence is empty:
    do not call transport;
    return an empty page with requested_symbols == ();
- otherwise:
    send exactly one request through the injected transport;
    parse exactly one response page;
    surface the next_page_token;
    do not automatically request another page.
```

This is watchlist-only by construction: the only symbols it may request are its explicit `symbols` argument.

---

## Tests Required

Add focused offline tests covering:

```text
query validation:
  valid values
  empty/non-string timeframe/start/end
  invalid limit including bool, zero, >10000
  invalid sort
  invalid/blank page token

request construction:
  GET URL/path
  normalized explicit symbol list
  required params
  optional page token only when supplied
  feed fallback
  existing auth header behavior remains accessible but secret-safe in repr

response parsing:
  valid one-symbol response
  valid multi-symbol response
  preserves raw bar timestamp/volume values without parsing
  preserves raw input order
  returns only requested symbols and ignores extra payload symbols
  absent requested symbol returns empty tuple
  null next_page_token
  valid non-empty next_page_token
  invalid JSON
  non-object payload
  invalid bars container
  invalid symbol bar list
  invalid non-object bar
  invalid next_page_token type or blank token

fetcher behavior:
  uses injected FakeHttpTransport
  makes exactly one send for nonempty symbols
  does not send for an empty/blank normalized symbol list
  surfaces next_page_token but does not auto-page
  propagates HttpTransportError / HttpStatusError / HttpTimeoutError
  no live HTTP is used

boundaries:
  no environment/config reads
  no provider factory/runtime registration
  no StdlibHttpTransport instantiation
  no direct imports or calls into Phase 13E–13I
  no candidate/scanner/alert/trading hooks
  no credentials/URLs embedded beyond the existing safe Alpaca data base URL and path constants

regression:
  existing Alpaca snapshot tests still pass
  default mock runtime works
  fixture and composed_fixture remain offline
  alpaca remains placeholder
  live_composed remains gated/reserved inactive
  full suite passes
```

Tests must use `FakeHttpTransport` and fixture JSON only. Do not make external network calls or use actual credentials.

---

## Documentation / README

Add a short README roadmap note only if useful:

```text
Phase 14A adds an injected Alpaca historical intraday-bars fetcher skeleton.
It returns one raw, inspectable response page for explicitly supplied symbols.
Pagination tokens are surfaced but never followed automatically.
It does not build RVOL inputs, fetch a watchlist, register a runtime provider, or activate live mode.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```

---

## Acceptance Criteria

Phase 14A is complete when:

```text
- one injected-transport historical-bars fetcher exists;
- it sends at most one HTTP request per non-empty fetch call;
- it accepts only explicit caller symbol input;
- it exposes raw immutable bars plus next_page_token;
- it performs no automatic paging or raw-bar interpretation;
- all tests are offline and deterministic;
- no runtime provider is activated or registered;
- no order/trading capability is added;
- the existing project suite remains green.
```
