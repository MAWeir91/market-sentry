# Phase 9B — Provider Configuration and Interface Skeleton

## Status

Planning/build phase. This phase prepares Market Sentry for future real market data providers without adding live HTTP calls or requiring credentials.

Phase 9B is an architecture skeleton only.

## Project Boundary

Market Sentry is a personal-use low-float momentum scanner with local voice alerts.

Market Sentry is not a trading bot.

Do not add:

- order execution
- broker trading/order APIs
- order placement
- trade execution
- real API calls
- network calls
- WebSockets
- required credentials
- dashboard UI
- news ingestion
- SEC ingestion
- halt ingestion
- split ingestion
- persistent database storage

Trading/order functionality is never in scope.

## Goal

Prepare the codebase for future real provider implementation by adding:

- provider selection configuration
- environment variable names/placeholders
- watchlist configuration
- provider interface skeletons if needed
- tests using fakes only

The application should remain mock-data based by default.

No live provider should be implemented in this phase.

## Current Provider State

Current runtime provider:

- `MockMarketDataProvider`

Current scanner input:

- `StockCandidate` objects

Current data provider contract:

- scanner-ready candidates are returned to the scanner engine

This behavior should remain intact.

## Provider Strategy from Phase 9A

Likely first future real provider split:

- Alpaca Market Data for price, volume, daily movement, high of day, intraday bars, and 15-minute change
- Financial Modeling Prep for float/reference data
- SEC EDGAR later for filings/catalyst context
- Nasdaq Trader Halt RSS later for halts/resumes
- News feeds later for catalyst context

Phase 9B should not implement any of these live integrations.

## Recommended Architecture

### Runtime Provider Selection

Add a configuration concept for selecting the active market data provider.

Approved initial provider names:

- `mock`
- `alpaca` as a placeholder only, not functional yet

Default provider:

- `mock`

If `alpaca` or any unimplemented provider is selected, the program should fail clearly or fall back only if explicitly designed and tested.

Recommended behavior for Phase 9B:

- `mock` works.
- `alpaca` raises a clear `NotImplementedError` or configuration error explaining that live provider implementation is a future phase.
- Unknown provider names raise a clear validation error.

Do not silently use a live provider.

### Environment Variable Placeholders

Document and optionally parse future environment variable names, but do not require them.

Potential future variables:

- `MARKET_SENTRY_PROVIDER`
- `MARKET_SENTRY_WATCHLIST`
- `ALPACA_API_KEY`
- `ALPACA_API_SECRET`
- `ALPACA_DATA_FEED`
- `FMP_API_KEY`

Rules:

- No variable should be required for default mock runtime.
- No secrets should be printed.
- No validation should call external services.
- Missing live-provider credentials should not affect mock mode.

### Watchlist Strategy

Add or document a controlled symbol universe strategy.

Future real provider implementation should start with a small watchlist rather than broad-market scanning.

Potential default watchlist for future phases:

- empty list unless explicitly configured, or
- a small sample list used only for docs/examples

If implemented in config, watchlist parsing should be simple:

```text
MARKET_SENTRY_WATCHLIST=XTRM,CRVO,ATAI
```

Expected parsed form:

```python
["XTRM", "CRVO", "ATAI"]
```

Rules:

- trim spaces
- uppercase symbols
- ignore empty entries
- no network calls
- no symbol validation against external services

### Interface Skeletons

Phase 9B may add interface skeletons if useful.

Possible interfaces:

- `MarketDataProvider`
- `FloatDataProvider`
- `CatalystProvider`
- `HaltProvider`

However, do not overbuild. If the existing `MarketDataProvider` protocol is sufficient for Phase 9B, keep changes minimal.

Recommended approach:

1. Preserve the existing scanner-facing provider that returns `list[StockCandidate]`.
2. Add config/provider selection utilities around it.
3. Only add split provider interfaces if the implementation plan needs them now.

Scanner runtime should continue consuming scanner-ready `StockCandidate` objects.

Provider composition and normalization should happen before scanner evaluation in a future phase.

## Suggested Files

Expected files to modify:

- `src/market_sentry/config.py`
- `src/market_sentry/data/provider.py`
- `src/market_sentry/data/mock_provider.py` only if needed
- `src/market_sentry/main.py` only if needed for provider selection wiring
- `README.md`
- `.env.example`

Expected tests to add or modify:

- `tests/test_config.py`
- `tests/test_provider_contract.py`
- `tests/test_main.py` only if provider selection affects CLI behavior

Possible file to create:

- `src/market_sentry/data/factory.py`
- `tests/test_provider_factory.py`

Do not modify unless absolutely necessary:

- scanner filters
- scanner tiers
- scanner scoring
- alert generator
- alert formatter
- speaker behavior
- cooldown behavior

## Configuration Behavior

Recommended configuration object fields:

- provider name, default `mock`
- watchlist, default empty list or configured list
- Alpaca API key placeholder, optional
- Alpaca API secret placeholder, optional
- Alpaca data feed placeholder, optional
- FMP API key placeholder, optional

Keep config loading deterministic and testable.

No config loading should make network calls.

## Provider Factory Behavior

If a provider factory is added, expected behavior:

- `mock` returns `MockMarketDataProvider`.
- `alpaca` raises a clear not-implemented/configuration error.
- unknown provider raises a clear validation error.

Factory tests should not require credentials or internet.

## CLI Behavior

Default CLI behavior should remain unchanged:

```powershell
python -m market_sentry
```

Loop behavior should remain unchanged:

```powershell
python -m market_sentry --loop --interval 30
```

Voice behavior should remain unchanged:

```powershell
python -m market_sentry --speak
```

Phase 9B should not add new CLI flags unless specifically approved.

Provider selection should preferably happen through config/environment variables, not new CLI flags, in this phase.

## Testing Requirements

Tests should verify:

- default provider is mock
- mock mode requires no credentials
- future API credentials are optional placeholders
- watchlist parser trims spaces
- watchlist parser uppercases symbols
- watchlist parser ignores empty values
- provider factory returns mock provider for `mock`
- provider factory raises clear error for `alpaca` placeholder
- provider factory raises clear error for unknown provider
- no tests require internet access
- no tests require API keys
- no scanner qualification rules changed
- existing CLI tests still pass
- full test suite passes

## Out of Scope

Do not add:

- Alpaca HTTP client
- FMP HTTP client
- requests/httpx/aiohttp dependencies
- WebSocket client
- retry/backoff logic
- rate limiter
- live provider normalization
- broad-market scanner
- SEC client
- halt client
- news client
- database/cache persistence
- dashboard
- trading/order behavior

## Completion Criteria

Phase 9B is complete when:

- provider configuration skeleton exists
- provider selection strategy is testable
- mock remains the default provider
- live providers are placeholders only
- watchlist parsing exists or is clearly documented
- no API/network calls are added
- no credentials are required
- README and `.env.example` document future placeholders
- full test suite passes
