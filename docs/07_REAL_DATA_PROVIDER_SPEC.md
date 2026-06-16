# Market Sentry Phase 9A - Real Data Provider Specification

## Status

Phase 9A is documentation/specification only.

Do not add provider implementation code in this phase. Do not add live HTTP calls, API keys, network calls, WebSockets, dashboards, persistent storage, broker order APIs, order placement, or trade execution.

Market Sentry remains a personal-use low-float momentum scanner with local voice alerts. It is not a trading bot.

## Purpose

Market Sentry already has:

- scanner core
- mock data provider
- data provider interface
- CLI report
- voice-ready alert events
- optional local voice playback
- rotation, 15-minute, and high-of-day context
- mock polling loop

Phase 9A defines the real data provider strategy before implementation starts. The goal is to avoid mixing provider concerns, scanner rules, float/reference data, catalysts, halts, and future UI work into one brittle layer.

## Current Runtime Boundary

`MockMarketDataProvider` remains the default and only runtime provider until a future phase explicitly adds real-provider code.

The scanner runtime should continue consuming scanner-ready `StockCandidate` objects. Provider-specific response parsing, composition, and normalization should happen before scanner evaluation.

Current scanner-ready fields include:

| Field | Purpose | Required for Base Qualification? |
| --- | --- | --- |
| `symbol` | Ticker symbol | yes |
| `price` | Current or latest price | yes |
| `daily_gain_percent` | Daily percent change | yes |
| `relative_volume` | Volume compared with normal activity | yes |
| `float_shares` | Public float/reference float | yes |
| `daily_volume` | Current day volume | yes |
| `high_of_day` | Current day high | no |
| `change_15m_pct` | Recent 15-minute move | no |

Derived metrics:

| Metric | Formula |
| --- | --- |
| `rotation` | `daily_volume / float_shares` |
| `distance_from_high_pct` | `((high_of_day - price) / high_of_day) * 100` |

## Recommended First Provider Strategy

The recommended first real-data strategy is:

1. Alpaca Market Data for price, volume, daily movement, high of day, intraday bars, and 15-minute change.
2. Financial Modeling Prep for float/reference data.
3. Keep SEC EDGAR, halt feeds, news, catalysts, splits, WebSockets, dashboards, and broad-market discovery out of the first real-provider implementation.

The first live implementation should use:

- HTTP first
- a small watchlist or controlled symbol universe first
- no broad-market scanner yet
- no WebSockets yet
- no required credentials for tests
- no internet access in tests

## Provider Layers

Future provider responsibilities should stay separated:

```text
MarketDataProvider
  -> price, volume, intraday bars, high of day, 15-minute change

FloatDataProvider
  -> float/reference data by symbol

CatalystProvider
  -> future news, SEC filings, dilution/catalyst context

HaltProvider
  -> future halt/resume context
```

Do not force all provider types into one class. These data sources have different freshness, rate limits, failure modes, and caching needs.

The scanner should not care which upstream providers produced a candidate. It should receive normalized `StockCandidate` objects and evaluate them with the same scanner rules used for mock data.

## Alpaca Market Data

### Intended Use

Alpaca Market Data is the likely first market data provider for:

- latest/current price
- current day volume
- high of day
- intraday bars
- 15-minute change calculation
- daily movement calculation
- relative volume calculation later, if enough historical volume context is available

### Data Quality Notes

Alpaca Basic/free equity data is IEX-only. Broader all-exchange/SIP coverage requires the appropriate Alpaca subscription.

This matters for Market Sentry because IEX-only data may understate true volume for low-float momentum runners. A candidate can look less active than it really is if activity is spread across venues not included in the selected feed.

### Phase 9A Recommendation

Use Alpaca as the likely first live market data provider, but start with HTTP and a controlled symbol universe. Do not add WebSockets in the first real-provider phase.

Future Alpaca code should:

- normalize provider responses into `StockCandidate`
- fail gracefully when credentials are missing
- keep mock mode working without credentials
- keep trading/order endpoints completely unused
- expose feed choice later if needed, such as IEX vs SIP
- avoid treating partial or stale data as a qualifying candidate

## Financial Modeling Prep Float Data

### Intended Use

Financial Modeling Prep is the likely first float/reference provider for:

- `float_shares`
- shares outstanding/reference context, if needed later

### Data Quality Notes

Float data is reference data and may be stale. It should not be treated like live price or volume data.

Future float lookups should be cached in memory during a run or polling session. The scanner should not call a float endpoint every loop interval for the same symbol.

Future float provider behavior should:

- look up float by symbol
- handle missing float cleanly
- avoid turning missing float into a false qualifying candidate
- expose stale/reference nature clearly in later diagnostics if needed

## Later Provider Layers

### SEC EDGAR

SEC EDGAR should be a later catalyst/dossier layer, not part of the first real market data provider.

Potential future uses:

- recent filings
- registration statements
- S-1, S-3, 424B, 8-K context
- dilution-risk badges
- issuer dossier context

SEC data requires respectful request behavior and a declared user agent.

### Nasdaq Trader Halt RSS

Nasdaq Trader halt/resume data should be a later halt alert layer.

The Nasdaq halt RSS feed should not be queried more than once per minute. Halt data should not be part of the first price/volume provider implementation.

### News, Catalysts, Splits, WebSockets, Dashboard

These are future phases:

- news/catalyst feeds
- SEC/catalyst enrichment
- halt/resume alerts
- split/reverse split tracking
- WebSockets
- dashboard UI

Trading/order functionality is never in scope.

## Candidate Universe Strategy

Do not attempt broad-market scanning in the first real-provider implementation.

Start with one of:

1. Static watchlist from configuration.
2. Small manually maintained symbol list.
3. Later: provider-supported top-gainers or screener endpoint.
4. Later: broader universe after rate limits, coverage, and data quality are understood.

This controlled approach keeps provider limits, data quality, and scanner behavior testable.

## Data Freshness Expectations

Different data fields have different freshness expectations:

| Field | Freshness Type |
| --- | --- |
| price | live/recent |
| daily volume | live/recent |
| high of day | live/recent |
| 15-minute change | intraday/recent |
| float | reference/stale acceptable |
| SEC filings | event/reference |
| halts | event/recent |
| news | event/recent |

Do not treat all fields as equally real-time.

## Failure Handling Expectations

Future real providers should:

- fail closed, not qualify bad data
- surface clear messages when credentials are missing
- handle rate-limit responses clearly
- handle provider outages gracefully
- keep mock mode working without credentials
- avoid crashing when optional reference/catalyst data is missing
- avoid silently mixing old reference data with fresh market data without future diagnostics

## Testing Expectations For Future Provider Work

Future provider tests must not require:

- real API keys
- internet access
- live provider accounts
- paid market data subscriptions

Future tests should use:

- mocked HTTP responses
- local fixtures
- fake providers
- explicit missing-credential cases
- rate-limit/error fixtures
- candidate normalization assertions

Mock mode must remain testable without credentials.

## Recommended Phase 9B Direction

Phase 9B should add a real-provider configuration/interface skeleton without live HTTP calls.

Recommended Phase 9B scope:

- provider selection strategy
- configuration placeholders
- environment variable names only
- optional expanded interfaces if needed
- watchlist/controlled symbol-universe strategy
- no required credentials
- no internet access in tests
- no live API calls
- no scanner qualification changes
- no trading/order behavior

Reserved environment variable names for later phases:

```text
MARKET_SENTRY_DATA_PROVIDER=mock|alpaca
MARKET_SENTRY_WATCHLIST=
ALPACA_API_KEY_ID=
ALPACA_API_SECRET_KEY=
ALPACA_DATA_FEED=iex|sip
FMP_API_KEY=
```

Do not add these to runtime configuration in Phase 9A unless a future phase explicitly approves it.

## Phase 9A Definition Of Done

Phase 9A is complete when:

- the provider strategy is documented
- Alpaca and FMP roles are clear
- data-quality risks are documented
- future SEC, halt, news, split, WebSocket, dashboard, and catalyst layers are out of scope
- Phase 9B direction is documented
- no runtime code has changed
- no provider implementation has been added
- no API/network behavior has been added
