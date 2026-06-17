# Phase 12D — Live Provider Factory Builder, Still Not Runtime-Active

## Goal

Create a factory helper that can construct a future `LiveComposedMarketDataProvider` from validated configuration and injected component classes, without connecting that helper to the runtime provider factory.

This is a dry-wiring phase only.

The runtime `MARKET_SENTRY_PROVIDER=live_composed` path must remain the Phase 12B gated placeholder. No live provider should become active in this phase.

## Non-Goals

Do not add:

- runtime activation for `live_composed`
- real HTTP calls in tests
- real live-provider calls at runtime
- default provider changes
- broad-market scanning
- all-shares-float crawling
- WebSockets
- streaming market data
- SEC/news/halt/split ingestion
- dashboard UI
- persistent database storage
- order APIs
- order placement
- trade execution
- trading advice behavior
- external HTTP dependencies

Market Sentry remains a scanner and local alerting tool, not a trading bot.

## Current Live-Readiness Chain

Market Sentry now has:

```text
HttpRequest / HttpResponse / HttpTransport
→ StdlibHttpTransport
→ AlpacaSnapshotFetcher
→ FMPFloatFetcher
→ LiveCandidateBuilder
→ LiveComposedMarketDataProvider
→ live_composed gated placeholder path
```

Phase 12D should add the helper that can assemble this chain in tests, while leaving runtime activation untouched.

## Expected Runtime Behavior After Phase 12D

The following behavior must remain unchanged:

1. `python -m market_sentry` defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock` works.
3. `MARKET_SENTRY_PROVIDER=fixture` works offline.
4. `MARKET_SENTRY_PROVIDER=composed_fixture` works offline.
5. `MARKET_SENTRY_PROVIDER=alpaca` fails cleanly as placeholder.
6. `MARKET_SENTRY_PROVIDER=live_composed` still fails through the Phase 12B gated placeholder path.
7. Gate-passing `live_composed` still fails as reserved/inactive.
8. No runtime path instantiates `StdlibHttpTransport` for live data.
9. No runtime path instantiates live Alpaca/FMP fetchers.
10. No runtime path makes live HTTP/network calls.
11. Loop behavior remains unchanged.
12. Voice behavior remains unchanged.
13. Scanner qualification rules remain unchanged.
14. Scoring remains unchanged.
15. Report formatting remains unchanged.

## Expected Files

Create or modify:

- `src/market_sentry/data/live_provider_builder.py`
- `tests/test_live_provider_builder.py`
- `README.md`

Possible only if truly necessary:

- `src/market_sentry/data/live_composed_provider.py`
- `tests/test_live_composed_provider.py`
- `src/market_sentry/config.py`
- `tests/test_config.py`

Do not modify unless absolutely necessary:

- `src/market_sentry/data/factory.py`
- `tests/test_provider_factory.py`
- `src/market_sentry/main.py`
- `tests/test_main.py`
- scanner filters/scoring/tiers
- alert generator/formatter
- speaker/cooldown behavior
- mock provider data
- fixture provider data
- composed fixture provider data

## Implementation Expectations

Add a dry factory/builder helper for the future live provider.

Suggested names:

- `LiveProviderBuilder`
- `LiveProviderBuildError`
- `build_live_composed_provider(...)`

Exact names can vary, but responsibilities should be clear.

The helper should:

1. Accept a validated `AppConfig` or config-like object.
2. Run or require a passed Phase 12A live-provider gate result.
3. Require the gate to pass before constructing the provider.
4. Construct or accept injected component classes/factories for:
   - transport
   - Alpaca snapshot fetcher/source
   - FMP float fetcher/source
   - live candidate builder or provider class
5. Return a `LiveComposedMarketDataProvider` instance.
6. Preserve explicit watchlist behavior.
7. Preserve explicit relative-volume source/mapping behavior.
8. Avoid reading environment variables directly.
9. Avoid making HTTP calls during construction.
10. Avoid activating runtime provider factory behavior.

## Dependency Injection Boundary

Tests should be able to inject fake component classes/factories.

The builder should be easy to test without:

- real API keys
- real HTTP transport calls
- real network access
- real live-provider activation

Acceptable patterns:

```text
build_live_composed_provider(
    config,
    transport_factory=...,            # injectable
    alpaca_fetcher_factory=...,       # injectable
    fmp_fetcher_factory=...,          # injectable
    provider_class=...,               # injectable
    relative_volume_by_symbol=...,    # explicit
)
```

or a small class-based builder with similar injected factories.

The exact API can vary, but the test boundary should prove no network calls are made.

## Important Relative-Volume Boundary

Relative volume still must not be fabricated.

The builder may accept explicit `relative_volume_by_symbol` or a clearly explicit source. It must not calculate or infer relative volume in Phase 12D.

If explicit relative volume is absent, the helper should fail clearly or construct a provider that will skip all symbols due to missing relative volume. Prefer a clear build-time error if that makes the contract safer.

## Error Behavior

The builder should fail safely when:

- the live-provider gate did not pass
- config is missing required live fields
- watchlist is empty
- required injected factories are missing, if not defaulted safely
- explicit relative-volume input is missing, if the chosen API requires it

Errors must not expose secrets.

Do not include:

- Alpaca key values
- Alpaca secret values
- FMP key values
- authorization headers
- raw config repr if it includes secrets
- raw request reprs

## Runtime Boundary

The runtime provider factory must remain unchanged unless absolutely necessary.

`MARKET_SENTRY_PROVIDER=live_composed` should continue using the Phase 12B placeholder path, not this new builder.

This builder is for future wiring and tests only in Phase 12D.

## Testing Requirements

Add tests for:

- builder constructs `LiveComposedMarketDataProvider` using injected fake factories.
- builder requires/preserves passing Phase 12A live gate.
- builder fails safely when gate fails.
- builder uses watchlist from config.
- builder uses explicit relative-volume input and does not fabricate it.
- builder passes injected Alpaca/FMP sources or fetchers into the provider.
- builder does not read environment variables directly.
- builder does not instantiate `StdlibHttpTransport` unless an injected fake factory is explicitly used in a test.
- builder does not make HTTP/network calls.
- builder errors are secret-safe.
- provider returned by builder can produce candidates using fake sources.
- provider returned by builder skips missing relative-volume data.
- runtime provider factory remains the Phase 12B placeholder path for `live_composed`.
- default runtime remains mock.
- fixture provider still works offline.
- composed_fixture still works offline.
- Alpaca remains placeholder.
- full test suite passes.

## Documentation Requirements

Update README concisely:

- A live-provider builder skeleton exists for future phases.
- It can assemble a `LiveComposedMarketDataProvider` from validated config and injected components.
- It is not connected to runtime.
- `MARKET_SENTRY_PROVIDER=live_composed` remains the gated placeholder path.
- Runtime still defaults to mock.
- Fixture and composed_fixture remain offline.
- Alpaca remains placeholder.
- FMP remains inactive.
- Relative volume must not be fabricated.
- Secrets should not be committed.
- Trading/order functionality remains out of scope.

## Commands to Run

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

## Completion Report Required

After building, Codex should respond with:

1. Files created or changed.
2. Summary of what each file does.
3. Exact live-provider builder behavior implemented.
4. Exact config/gate behavior implemented.
5. Exact dependency-injection behavior implemented.
6. Exact watchlist behavior implemented.
7. Exact relative-volume behavior implemented.
8. Exact error behavior implemented.
9. How secrets are protected.
10. Confirmation that runtime still defaults to mock.
11. Confirmation that fixture provider still works offline.
12. Confirmation that composed_fixture still works offline.
13. Confirmation that Alpaca remains runtime placeholder.
14. Confirmation that live_composed remains the Phase 12B placeholder path at runtime.
15. Confirmation that no real HTTP transport is instantiated by runtime.
16. Confirmation that no live Alpaca/FMP fetchers are instantiated by runtime.
17. Confirmation that no live HTTP/network calls are made.
18. Confirmation that no external HTTP dependency was added.
19. Confirmation that no provider factory activation was added.
20. Confirmation that no trading/order behavior was added.
21. Exact test command run.
22. Test results.
23. Example output from default mock run.
24. Example output from fixture provider run.
25. Example output from composed_fixture provider run.
26. Example output from alpaca placeholder run.
27. Example output from live_composed failed-gate run.
28. Example output from live_composed gate-passing placeholder run.
29. Any known issues or follow-up recommendations.
