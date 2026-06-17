# Phase 12A — Opt-in Live Provider Configuration Gate

## Status
Planned

## Purpose
Add a strict configuration gate for a future live composed provider without activating live data yet.

This phase is a safety layer. It should make it impossible for live-provider code to run accidentally just because API keys exist in the environment.

## Boundary
Market Sentry is a personal-use low-float momentum scanner with local voice alerts. It is not a trading bot.

Do not add:
- live provider activation
- live Alpaca provider runtime behavior
- live FMP provider runtime behavior
- real HTTP calls
- real HTTP transport instantiation from runtime
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

Trading/order functionality is never in scope.

## Goal
Create config validation for a future live composed provider that requires all of the following before live mode could be considered allowed:

1. Explicit provider name for the future live composed provider.
2. Explicit allow-live flag.
3. Non-empty watchlist.
4. Alpaca API key.
5. Alpaca API secret.
6. FMP API key.

This phase must not actually instantiate a live provider or perform live HTTP calls.

## Preferred Future Live Provider Name
Use this reserved provider name for validation only:

```text
live_composed
```

`live_composed` must remain unavailable as a runtime provider in Phase 12A unless the existing architecture needs a clean placeholder error. If added to the factory, it must fail cleanly before any network setup and must not instantiate live transports/fetchers.

Preferred approach: add config validation helpers only, and keep provider factory behavior unchanged unless tests require a placeholder error.

## Environment Variables
Existing relevant environment variables include:

```text
MARKET_SENTRY_PROVIDER
MARKET_SENTRY_WATCHLIST
ALPACA_API_KEY
ALPACA_API_SECRET
ALPACA_DATA_FEED
FMP_API_KEY
```

Add a new explicit allow-live flag:

```text
MARKET_SENTRY_ALLOW_LIVE_DATA
```

Recommended accepted truthy values:

```text
1
true
yes
on
```

Values should be treated case-insensitively and with surrounding whitespace ignored.

Any missing, empty, or false-like value should mean live data is not allowed.

## Validation Behavior
Add a safe validation function or structure that can determine whether live composed data is allowed.

Suggested names:
- `LiveProviderGate`
- `LiveProviderGateResult`
- `validate_live_provider_gate(config)`

The exact names can vary, but the responsibilities should be clear.

The validation should check:
- selected provider is exactly `live_composed`
- allow-live flag is explicitly enabled
- watchlist contains at least one symbol
- Alpaca API key is present
- Alpaca API secret is present
- FMP API key is present

The result should be inspectable and testable.

It should include:
- whether the gate passed
- stable failure reasons
- safe, user-facing error message if useful

## Failure Reasons
Use stable failure reasons so tests can assert behavior.

Suggested reasons:
- `PROVIDER_NOT_LIVE_COMPOSED`
- `LIVE_DATA_NOT_ALLOWED`
- `MISSING_WATCHLIST`
- `MISSING_ALPACA_API_KEY`
- `MISSING_ALPACA_API_SECRET`
- `MISSING_FMP_API_KEY`

Exact enum names can vary, but they should be stable and clear.

## Secret Safety
Validation failures must not expose secret values.

Do not print or include:
- Alpaca key value
- Alpaca secret value
- FMP key value
- authorization headers
- raw config repr if it includes secrets

Error messages should name missing fields, not values.

## Runtime Behavior After Phase 12A
Expected runtime behavior after this phase:

1. `python -m market_sentry` still defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock` still works.
3. `MARKET_SENTRY_PROVIDER=fixture` still works offline.
4. `MARKET_SENTRY_PROVIDER=composed_fixture` still works offline.
5. `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as placeholder.
6. FMP remains inactive as a runtime provider.
7. `live_composed` does not perform live calls.
8. No runtime path should instantiate `StdlibHttpTransport` for live data.
9. Loop behavior remains unchanged.
10. Voice behavior remains unchanged.
11. Scanner qualification rules remain unchanged.
12. Scoring remains unchanged.
13. Report formatting remains unchanged except for any explicit placeholder error if added.

## Expected Files
Expected files to create or modify:

- `src/market_sentry/config.py`
- `tests/test_config.py` or `tests/test_live_provider_gate.py`
- `README.md`

Possible files to modify only if truly necessary:

- `src/market_sentry/data/factory.py`
- `tests/test_provider_factory.py`
- `src/market_sentry/main.py`
- `tests/test_main.py`
- `.env.example`

Do not modify unless absolutely necessary:

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
- live candidate builder behavior
- mock provider data
- fixture provider data
- composed fixture provider data

## Testing Requirements
Add tests for:

- allow-live flag truthy parsing
- allow-live flag false/missing behavior
- gate fails if provider is not `live_composed`
- gate fails if allow-live flag is missing/false
- gate fails if watchlist is empty
- gate fails if Alpaca API key is missing
- gate fails if Alpaca API secret is missing
- gate fails if FMP API key is missing
- gate passes only when all required fields are present and provider is `live_composed`
- failure reasons are stable and inspectable
- error messages do not expose secret values
- default runtime remains mock
- fixture provider still works offline
- composed_fixture still works offline
- Alpaca remains placeholder
- no real HTTP/network calls are made
- no real HTTP transport is instantiated by runtime
- no external HTTP dependency is added
- no trading/order behavior is added
- full test suite passes

## Documentation Requirements
Update README concisely:

- A future live composed provider now has a strict config gate.
- The reserved future provider name is `live_composed`.
- Live data requires explicit `MARKET_SENTRY_ALLOW_LIVE_DATA=true` or equivalent.
- Live data also requires watchlist, Alpaca credentials, and FMP key.
- The gate does not activate live data yet.
- Runtime still defaults to mock.
- Fixture and composed_fixture remain offline.
- Alpaca remains placeholder.
- FMP remains inactive as a runtime provider.
- Secrets should not be committed.
- Trading/order functionality remains out of scope.

If `.env.example` is updated, include the new allow-live flag as a disabled example:

```text
# MARKET_SENTRY_ALLOW_LIVE_DATA=false
```

## Acceptance Criteria
Phase 12A is complete when:

- The live provider config gate exists.
- The gate is fully tested.
- Secret values are never exposed in errors.
- Runtime modes remain unchanged.
- No live provider is activated.
- No live HTTP calls are made.
- No provider factory activation for live data is added unless it is a clean placeholder that performs no network setup.
- The full test suite passes.
