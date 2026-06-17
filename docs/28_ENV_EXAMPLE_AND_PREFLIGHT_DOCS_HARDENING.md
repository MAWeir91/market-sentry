# Phase 12H — Env Example and Preflight Docs Hardening

## Goal

Harden the local live-readiness documentation and `.env.example` guidance so a user can understand how to run the Phase 12G CLI preflight without guessing which environment variables are required.

This phase is documentation/config-example polish only. It must not activate live data, connect live providers, instantiate HTTP transports, call external APIs, or change scanner behavior.

## Context

Market Sentry now has a safe live-readiness path:

```powershell
python -m market_sentry --live-readiness
python -m market_sentry --live-readiness --relative-volume-configured
```

The preflight checks local readiness only. It does not call Alpaca, FMP, or any other network API. It does not activate `live_composed` as a scanner provider.

Phase 12H should make that boundary clear in `.env.example`, README, and tests.

## Required Boundary

Market Sentry is a personal-use low-float momentum scanner with local voice alerts. It is not a trading bot.

Do not add:

- order APIs
- order placement
- trade execution
- trading advice behavior
- live provider activation
- real HTTP calls
- external HTTP dependencies
- provider factory activation for working live data
- real Alpaca/FMP fetcher runtime wiring
- broad-market scanning
- all-shares-float crawling
- WebSockets
- streaming market data
- SEC/news/halt/split ingestion
- dashboard UI
- persistent database storage

## Expected Runtime Behavior After Phase 12H

When no preflight flag is used:

1. `python -m market_sentry` still defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock` still works.
3. `MARKET_SENTRY_PROVIDER=fixture` still works offline.
4. `MARKET_SENTRY_PROVIDER=composed_fixture` still works offline.
5. `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as placeholder.
6. `MARKET_SENTRY_PROVIDER=live_composed` still fails through the gated placeholder path.
7. Gate-passing `live_composed` still fails as reserved/inactive.
8. No runtime path instantiates live HTTP transports or fetchers.
9. No runtime path makes live network calls.
10. Scanner rules, scoring, alerts, voice, and report formatting remain unchanged.

When `--live-readiness` is used:

1. The CLI prints diagnostics only.
2. The scanner report is not rendered.
3. Providers are not built.
4. The factory is not used to activate live data.
5. No network calls occur.

## Files Expected to Modify

- `.env.example`
- `README.md`
- tests that cover README/env guidance if useful, likely `tests/test_main.py` or `tests/test_config.py`

Optional only if truly useful:

- a lightweight docs test file such as `tests/test_env_example.py`

Do not modify unless absolutely necessary:

- `src/market_sentry/main.py`
- `src/market_sentry/data/factory.py`
- `src/market_sentry/live_readiness.py`
- `src/market_sentry/config.py`
- HTTP transport
- Alpaca/FMP fetchers
- live provider builder
- live composed provider
- scanner filters/scoring/tiers
- alerts/voice/cooldowns
- mock/fixture/composed fixture data

## `.env.example` Requirements

Update `.env.example` to clearly document current working providers and reserved future providers.

It should include safe commented examples for:

```dotenv
# MARKET_SENTRY_PROVIDER=mock
# MARKET_SENTRY_PROVIDER=fixture
# MARKET_SENTRY_PROVIDER=composed_fixture
# MARKET_SENTRY_PROVIDER=live_composed

# MARKET_SENTRY_ALLOW_LIVE_DATA=false
# MARKET_SENTRY_WATCHLIST=AAPL,MSFT

# ALPACA_API_KEY=
# ALPACA_API_SECRET=
# ALPACA_DATA_FEED=iex
# FMP_API_KEY=
```

Guidance should make clear:

- default provider is mock
- fixture and composed_fixture are offline
- alpaca remains placeholder
- live_composed remains gated placeholder
- `MARKET_SENTRY_ALLOW_LIVE_DATA=true` is only a local readiness gate today
- setting live env vars does not activate live scanning yet
- secrets must not be committed
- readiness preflight is no-network
- RVOL readiness requires an explicit local signal using `--relative-volume-configured`

Do not put real credentials in `.env.example`.

## README Requirements

Add or harden a small section that shows:

### Normal offline runs

```powershell
python -m market_sentry

$env:MARKET_SENTRY_PROVIDER="fixture"
python -m market_sentry
Remove-Item Env:MARKET_SENTRY_PROVIDER

$env:MARKET_SENTRY_PROVIDER="composed_fixture"
python -m market_sentry
Remove-Item Env:MARKET_SENTRY_PROVIDER
```

### Live readiness preflight

```powershell
python -m market_sentry --live-readiness
```

### Local preflight with placeholder values

```powershell
$env:MARKET_SENTRY_PROVIDER="live_composed"
$env:MARKET_SENTRY_ALLOW_LIVE_DATA="true"
$env:MARKET_SENTRY_WATCHLIST="AAPL"
$env:ALPACA_API_KEY="placeholder-key"
$env:ALPACA_API_SECRET="placeholder-secret"
$env:FMP_API_KEY="placeholder-fmp-key"
python -m market_sentry --live-readiness --relative-volume-configured
Remove-Item Env:MARKET_SENTRY_PROVIDER
Remove-Item Env:MARKET_SENTRY_ALLOW_LIVE_DATA
Remove-Item Env:MARKET_SENTRY_WATCHLIST
Remove-Item Env:ALPACA_API_KEY
Remove-Item Env:ALPACA_API_SECRET
Remove-Item Env:FMP_API_KEY
```

The README must clearly say:

- `--live-readiness` performs local checks only
- no API calls are made
- no live provider is activated
- no scanner report is rendered on preflight path
- `--relative-volume-configured` is only an explicit local signal
- RVOL is not calculated, fetched, inferred, or fabricated
- `live_composed` remains reserved/inactive as a scanner provider
- Alpaca remains placeholder
- trading/order functionality is out of scope

## Testing Requirements

Add or update tests to verify:

1. `.env.example` documents the live readiness variables without real values.
2. `.env.example` includes `MARKET_SENTRY_ALLOW_LIVE_DATA` as disabled/commented by default.
3. `.env.example` includes `MARKET_SENTRY_PROVIDER` options or examples.
4. `.env.example` includes Alpaca/FMP credential placeholders but no actual secrets.
5. README includes `--live-readiness` usage.
6. README includes `--relative-volume-configured` usage.
7. README says preflight does not call APIs or activate `live_composed`.
8. README says RVOL is explicit and not fabricated.
9. Runtime provider factory remains unchanged.
10. Default runtime remains mock.
11. Fixture provider still works offline.
12. Composed fixture provider still works offline.
13. Alpaca remains placeholder.
14. live_composed remains gated placeholder.
15. Full test suite passes.

## Manual Verification Commands

Run:

```powershell
python -m pytest
python -m market_sentry
```

Verify offline providers:

```powershell
$env:MARKET_SENTRY_PROVIDER="fixture"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
$env:MARKET_SENTRY_PROVIDER="composed_fixture"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
$env:MARKET_SENTRY_PROVIDER="alpaca"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
$env:MARKET_SENTRY_PROVIDER="live_composed"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

Verify preflight:

```powershell
python -m market_sentry --live-readiness
```

Verify local-ready preflight path:

```powershell
$env:MARKET_SENTRY_PROVIDER="live_composed"
$env:MARKET_SENTRY_ALLOW_LIVE_DATA="true"
$env:MARKET_SENTRY_WATCHLIST="AAPL"
$env:ALPACA_API_KEY="placeholder-key"
$env:ALPACA_API_SECRET="placeholder-secret"
$env:FMP_API_KEY="placeholder-fmp-key"
python -m market_sentry --live-readiness --relative-volume-configured
Remove-Item Env:MARKET_SENTRY_PROVIDER
Remove-Item Env:MARKET_SENTRY_ALLOW_LIVE_DATA
Remove-Item Env:MARKET_SENTRY_WATCHLIST
Remove-Item Env:ALPACA_API_KEY
Remove-Item Env:ALPACA_API_SECRET
Remove-Item Env:FMP_API_KEY
```

Verify provider path still reserved:

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

## Definition of Done

Phase 12H is complete when:

1. `.env.example` clearly documents current offline providers and future live readiness variables.
2. README clearly documents the preflight command and safe boundaries.
3. Tests cover the docs/env guidance.
4. Full test suite passes.
5. Runtime behavior is unchanged.
6. No live provider activation is added.
7. No network behavior is added.
8. No trading/order behavior is added.
