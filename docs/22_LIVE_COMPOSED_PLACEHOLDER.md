# Phase 12B — `live_composed` Placeholder Provider Error

## Goal

Add a clean placeholder error path for the reserved future provider name:

```text
live_composed
```

This phase improves user experience and safety by making `MARKET_SENTRY_PROVIDER=live_composed` produce an intentional, secret-safe provider configuration message instead of a generic unknown-provider error.

This phase must still not activate live data.

## Core Rules

Market Sentry is a personal-use low-float momentum scanner with local voice alerts. It is not a trading bot.

Do not add:

- live provider activation
- live Alpaca runtime provider behavior
- live FMP runtime provider behavior
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

Trading/order functionality is never in scope for Market Sentry.

## Reserved Provider Behavior

When `MARKET_SENTRY_PROVIDER=live_composed`, runtime should recognize the provider name as reserved.

The path should:

1. Load config normally.
2. Run the Phase 12A live provider config gate.
3. If the gate fails, raise a clean provider configuration error with safe missing-precondition information.
4. If the gate passes, still raise a clean placeholder error explaining that `live_composed` is reserved for a future live provider and is not active yet.
5. Never instantiate `StdlibHttpTransport`.
6. Never instantiate live Alpaca/FMP fetchers.
7. Never make HTTP/network calls.

## Preferred Error Behavior

If the gate fails, the message should be user-friendly and secret-safe.

Example shape:

```text
Provider configuration error: live_composed is not enabled. Missing requirements: LIVE_DATA_NOT_ALLOWED, MISSING_WATCHLIST, MISSING_ALPACA_API_KEY, MISSING_ALPACA_API_SECRET, MISSING_FMP_API_KEY.
```

If the gate passes, the message should clearly state live mode is still inactive.

Example shape:

```text
Provider configuration error: live_composed is reserved for a future live provider and is not active yet.
```

Exact wording can vary, but it must be stable enough for tests and must not expose secret values.

## Runtime Behavior After Phase 12B

Expected behavior:

1. `python -m market_sentry` still defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock` still works.
3. `MARKET_SENTRY_PROVIDER=fixture` still works offline.
4. `MARKET_SENTRY_PROVIDER=composed_fixture` still works offline.
5. `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as placeholder.
6. `MARKET_SENTRY_PROVIDER=live_composed` fails cleanly as reserved/inactive placeholder.
7. FMP remains inactive as a runtime provider.
8. No runtime path instantiates `StdlibHttpTransport` for live data.
9. No runtime path instantiates live Alpaca/FMP fetchers.
10. Loop behavior remains unchanged.
11. Voice behavior remains unchanged.
12. Scanner qualification rules remain unchanged.
13. Scoring remains unchanged.
14. Report formatting remains unchanged except for the clean provider error path.

## Expected Files

Expected files to create or modify:

- `src/market_sentry/data/factory.py`
- `tests/test_provider_factory.py`
- `src/market_sentry/main.py` if needed
- `tests/test_main.py`
- `README.md`

Possible files to modify only if truly necessary:

- `src/market_sentry/config.py`
- `tests/test_config.py`
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

- `live_composed` is recognized as a reserved provider name.
- `live_composed` runs the Phase 12A config gate.
- Missing allow-live flag produces a clean failure.
- Missing watchlist produces a clean failure.
- Missing Alpaca key produces a clean failure.
- Missing Alpaca secret produces a clean failure.
- Missing FMP key produces a clean failure.
- Failure messages do not expose secret values.
- If all gate requirements pass, `live_composed` still fails as reserved/inactive.
- `live_composed` never instantiates `StdlibHttpTransport`.
- `live_composed` never instantiates live Alpaca/FMP fetchers.
- `live_composed` never makes live HTTP/network calls.
- default provider remains mock.
- existing fixture provider still works.
- composed fixture provider still works.
- Alpaca remains placeholder.
- unknown provider still fails cleanly.
- CLI displays a clean provider configuration error for `live_composed`.
- no scanner report header is rendered for `live_composed` errors.
- full test suite passes.

## Documentation Requirements

Update README concisely:

- `live_composed` is a reserved future provider name.
- It now has a clean placeholder/config-gate error path.
- It is still not active.
- The Phase 12A gate checks allow-live flag, watchlist, Alpaca credentials, and FMP key.
- Even if the gate passes, live data remains disabled until a future phase.
- Runtime still defaults to mock.
- Fixture and composed_fixture remain offline.
- Alpaca remains placeholder.
- FMP remains inactive.
- No credentials are required for current working runtime modes.
- Secrets should not be committed.
- Trading/order functionality remains out of scope.

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

Also test a gate-passing placeholder scenario manually if practical, using fake placeholder values:

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

This should still fail as reserved/inactive and should not make live calls.
