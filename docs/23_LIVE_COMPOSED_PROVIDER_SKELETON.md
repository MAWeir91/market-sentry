# Phase 12C — Live Composed Provider Skeleton, Still No Network Calls

## Goal

Create the structural skeleton for a future `live_composed` provider without activating live data.

The provider skeleton should define the final composition shape:

```text
StdlibHttpTransport
→ AlpacaSnapshotFetcher
→ FMPFloatFetcher
→ LiveCandidateBuilder
→ live_composed provider
```

But this phase must still remain non-live, test-only, and safe.

## Absolute Boundaries

Market Sentry is a personal-use low-float momentum scanner with local voice alerts. It is not a trading bot.

Do not add:

- order APIs
- order placement
- trade execution
- trading advice behavior
- brokerage trading API behavior
- live runtime activation
- real HTTP calls in tests
- broad-market scanning
- all-shares-float crawling
- WebSockets
- streaming market data
- SEC/news/halt/split ingestion
- dashboard UI
- persistent database storage

## Runtime Boundary

After Phase 12C:

1. `python -m market_sentry` still defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock` still works.
3. `MARKET_SENTRY_PROVIDER=fixture` still works offline.
4. `MARKET_SENTRY_PROVIDER=composed_fixture` still works offline.
5. `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as placeholder.
6. `MARKET_SENTRY_PROVIDER=live_composed` still fails cleanly through the Phase 12B gated placeholder path.
7. FMP remains inactive as a standalone runtime provider.
8. No runtime path instantiates `StdlibHttpTransport` for live data.
9. No runtime path instantiates live Alpaca/FMP fetchers.
10. No runtime path performs live HTTP/network calls.

## Intended Provider Skeleton

Add a new provider class skeleton, suggested name:

```text
LiveComposedMarketDataProvider
```

Suggested module:

```text
src/market_sentry/data/live_composed_provider.py
```

The provider should be constructed from injected dependencies, not from environment variables directly:

- an Alpaca snapshot fetcher/source
- an FMP float fetcher/source
- relative-volume input/source
- a watchlist
- optionally a builder, or enough components to create/use `LiveCandidateBuilder`

The provider may implement `MarketDataProvider` structurally by exposing:

```python
get_candidates() -> list[StockCandidate]
```

But it must not be registered as the working provider for `MARKET_SENTRY_PROVIDER=live_composed` yet.

## Dependency Injection Boundary

The skeleton should be easy to test with fake injected components.

Do not instantiate these from runtime/provider factory in Phase 12C:

- `StdlibHttpTransport`
- `AlpacaSnapshotFetcher`
- `FMPFloatFetcher`
- live credential-backed sources

Tests may instantiate the provider with fake objects only.

## Relative Volume Boundary

Relative volume must remain explicit.

Do not fabricate relative volume.

If relative volume is missing for a symbol, the provider/builder path must skip that symbol according to existing builder/composer behavior.

## Expected Files

Expected files to create or modify:

- `src/market_sentry/data/live_composed_provider.py`
- `tests/test_live_composed_provider.py`
- `README.md`

Possible files to modify only if truly necessary:

- `src/market_sentry/data/live_candidate_builder.py`
- `tests/test_live_candidate_builder.py`

Do not modify unless absolutely necessary:

- `src/market_sentry/data/factory.py`
- `tests/test_provider_factory.py`
- `src/market_sentry/main.py`
- `tests/test_main.py`
- scanner filters
- scanner scoring
- scanner tiers
- alert generator
- alert formatter
- speaker behavior
- cooldown behavior
- HTTP transport behavior
- Alpaca fetcher behavior
- FMP fetcher behavior
- mock provider data
- fixture provider data
- composed fixture provider data

## Implementation Expectations

The skeleton should:

1. Define the future live composed provider class.
2. Use injected dependencies.
3. Accept a controlled watchlist.
4. Normalize symbols safely if not already handled by the builder.
5. Use the existing `LiveCandidateBuilder` path where practical.
6. Return only successful `StockCandidate` objects from `get_candidates()`.
7. Provide optional inspectable build results if useful for tests/debugging.
8. Require explicit relative-volume input/source.
9. Avoid fabricating missing data.
10. Avoid all runtime activation.
11. Avoid real HTTP calls.
12. Avoid real credential requirements.
13. Avoid external HTTP dependencies.
14. Avoid trading/order behavior.

## Testing Requirements

Add tests for:

- provider can be instantiated with fake injected components
- provider returns only successful `StockCandidate` objects
- provider uses the `LiveCandidateBuilder` path
- provider requires explicit relative volume
- missing relative volume is skipped
- missing Alpaca movement data is skipped
- missing FMP float data is skipped
- watchlist symbols are handled safely
- optional inspectable build results work, if exposed
- provider does not instantiate `StdlibHttpTransport`
- provider does not instantiate live Alpaca/FMP fetchers internally
- provider does not make network calls
- provider is not registered in the runtime factory as active live provider
- `MARKET_SENTRY_PROVIDER=live_composed` still uses the Phase 12B placeholder path
- default runtime remains mock
- fixture provider still works offline
- composed_fixture still works offline
- Alpaca remains placeholder
- full test suite passes

## Documentation Requirements

Update README concisely:

- live composed provider skeleton exists for future live-data phases
- it is dependency-injected and tested with fake components only
- it is not active at runtime
- `live_composed` remains a reserved/gated placeholder
- runtime still defaults to mock
- fixture and composed_fixture remain offline
- Alpaca remains placeholder
- FMP remains inactive as a standalone runtime provider
- relative volume must not be fabricated
- credentials should not be committed
- trading/order functionality remains out of scope

## Manual Verification

After building, run:

```powershell
python -m pytest
python -m market_sentry
$env:MARKET_SENTRY_PROVIDER="fixture"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
$env:MARKET_SENTRY_PROVIDER="composed_fixture"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
$env:MARKET_SENTRY_PROVIDER="alpaca"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
$env:MARKET_SENTRY_PROVIDER="live_composed"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

Also verify the gate-passing placeholder case still fails as reserved/inactive:

```powershell
$env:MARKET_SENTRY_PROVIDER="live_composed"
$env:MARKET_SENTRY_ALLOW_LIVE_DATA="true"
$env:MARKET_SENTRY_WATCHLIST="AAPL"
$env:ALPACA_API_KEY="placeholder-key"
$env:ALPACA_API_SECRET="placeholder-secret"
$env:FMP_API_KEY="placeholder-fmp-key"
python -m market_sentry
Remove-Item Env:MARKET_SENTRY_PROVIDER
Remove-Item Env:MARKET_SENTRY_ALLOW_LIVE_DATA
Remove-Item Env:MARKET_SENTRY_WATCHLIST
Remove-Item Env:ALPACA_API_KEY
Remove-Item Env:ALPACA_API_SECRET
Remove-Item Env:FMP_API_KEY
```
