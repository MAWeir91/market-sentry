# Phase 10A — Alpaca Market Data Skeleton

## Purpose

Phase 10A prepares Market Sentry for an eventual Alpaca market-data integration without changing the default runtime behavior and without making live network calls in tests.

This is a **provider skeleton / adapter groundwork phase**, not a full live-data phase.

Market Sentry should remain safe, deterministic, and mock-first while we add the structure needed to parse Alpaca-style market data later.

## Current Project State

Market Sentry already has:

- scanner core
- `StockCandidate` model
- mock provider
- provider configuration
- provider factory
- runtime provider wiring
- mock polling loop
- optional local voice alerts
- rotation, 15-minute change, HOD, and HOD-distance metrics

Phase 9C wired runtime provider selection through config/factory, but `mock` remains the only functional provider.

## Phase 10A Goal

Add an Alpaca market-data skeleton that can:

1. Represent Alpaca market-data configuration safely.
2. Build Alpaca market-data request information without sending it by default.
3. Parse/normalize Alpaca-style fixture responses.
4. Prepare for future watchlist-based live market snapshots.
5. Keep all tests offline and deterministic.
6. Keep runtime default as `mock`.
7. Keep `MARKET_SENTRY_PROVIDER=alpaca` as a clear placeholder unless a later phase explicitly wires live behavior.

## Non-Goals

Do **not** add:

- live API calls from tests
- required API keys
- broad-market scanning
- WebSockets
- streaming market data
- SEC/news/halt/split ingestion
- dashboard UI
- persistent database storage
- broker order APIs
- order placement
- trade execution
- automatic trading

Trading/order functionality is never in scope for Market Sentry.

## Alpaca Research Notes

Alpaca provides stock market-data endpoints under `https://data.alpaca.markets`.

Relevant endpoints for future phases:

- Multi-symbol snapshots: `/v2/stocks/snapshots`
- Latest bars: `/v2/stocks/bars/latest`
- Historical bars: `/v2/stocks/bars`

The multi-symbol snapshot endpoint can return latest trade, latest quote, minute bar, daily bar, and previous daily bar data for requested symbols.

Authentication uses Alpaca API credentials, commonly through headers such as:

- `APCA-API-KEY-ID`
- `APCA-API-SECRET-KEY`

Feed choice matters. Alpaca Basic/free equity data can be IEX-only, while broader SIP/all-exchange coverage requires the appropriate paid market-data subscription. IEX-only data may understate volume and price activity for low-float momentum names.

## Design Direction

Phase 10A should focus on **offline-safe adapter structure**.

Suggested components:

- `AlpacaMarketDataSettings`
- Alpaca request builder utilities
- Alpaca response parsing utilities
- normalized snapshot/bar data models if useful
- fake/injected transport for tests
- no default live transport

The runtime provider factory may continue to raise the existing placeholder error for `alpaca`.

That means Phase 10A can add Alpaca parsing/request-shaping code while still preserving the safe runtime behavior from Phase 9C.

## Why Not Wire Alpaca Runtime Yet?

The scanner currently needs `StockCandidate` objects with float data.

Alpaca is a market-data source for price, volume, bars, high of day, and recent intraday movement. It is **not** the planned source of float/reference data.

A complete scanner-ready live provider will likely need composition:

```text
Alpaca market data + FMP float/reference data -> StockCandidate objects -> ScannerEngine
```

Therefore, Phase 10A should avoid pretending Alpaca alone can produce the full scanner-ready candidate set unless fake/test float data is explicitly injected.

## Candidate Future Data Mapping

Future Alpaca-derived fields may map approximately as follows:

| Market Sentry field | Likely Alpaca source |
|---|---|
| symbol | requested symbol / response key |
| price | latest trade price or daily bar close |
| daily_volume | daily bar volume |
| high_of_day | daily bar high |
| daily_gain_pct | latest price vs previous daily close |
| change_15m_pct | recent 1-minute bars over a 15-minute window |
| relative_volume | later derived from historical average volume, not Phase 10A |
| float_shares | later FMP/reference provider, not Alpaca |

Phase 10A should document and test this mapping where useful, but should not overstate completeness.

## Watchlist Boundary

Any future live provider should start with a small controlled watchlist from `MARKET_SENTRY_WATCHLIST`.

Phase 10A may reuse existing watchlist parsing, but it should not add broad-market scanning.

## Runtime Behavior

After Phase 10A:

- `python -m market_sentry` should still use mock data and work normally.
- `MARKET_SENTRY_PROVIDER=mock python -m market_sentry` should still work.
- `MARKET_SENTRY_PROVIDER=alpaca python -m market_sentry` may continue to fail cleanly with the placeholder message unless a later phase explicitly changes that behavior.
- loop mode should remain unchanged.
- voice mode should remain unchanged.

## Testing Requirements

Tests must:

- use fixtures/fakes only
- not require Alpaca credentials
- not use real network calls
- not depend on current market hours
- not depend on real symbols being active
- not depend on paid market-data subscriptions
- not add HTTP/WebSocket dependencies unless explicitly approved

Recommended tests:

- Alpaca auth headers are built without printing secrets.
- Snapshot request path/params are built for a watchlist.
- Feed defaults safely, likely to `iex` unless config specifies otherwise.
- Empty watchlist is handled safely.
- Alpaca snapshot fixture parses price, daily volume, HOD, and previous close.
- Daily gain calculation handles missing previous close safely.
- 15-minute change calculation handles insufficient bars safely.
- 15-minute change calculation works from fixture bars when enough data exists.
- Response parsing handles missing symbol data safely.
- Runtime factory still keeps Alpaca as placeholder if that is the chosen boundary.
- Full test suite passes.

## Documentation Requirements

Update README only if useful, with a concise note that:

- an Alpaca market-data skeleton exists for future phases
- runtime still defaults to mock
- real Alpaca runtime integration is not active yet
- credentials should not be committed
- tests use fakes/fixtures only

## Acceptance Criteria

Phase 10A is complete when:

- Alpaca adapter/request/parse skeleton exists.
- Tests cover request-building and fixture parsing.
- No live network calls are made in tests.
- No credentials are required.
- Runtime remains mock by default.
- Alpaca runtime behavior does not silently fall back to mock.
- No trading/order functionality is added.
- Full test suite passes.
