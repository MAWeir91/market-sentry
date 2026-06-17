# Phase 12F — Live Readiness Diagnostics

## Goal

Create a live-readiness diagnostic helper for the future `live_composed` provider that checks whether the local configuration appears ready for live data without calling any APIs, instantiating live transports, or activating runtime live behavior.

This phase is preflight only.

## Non-goals

Do not add:

- live runtime activation
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
- order APIs
- order placement
- trade execution
- trading advice behavior

Market Sentry remains a scanner only, not a trading bot.

## Runtime boundary

After Phase 12F:

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

## Expected files

Expected files to create or modify:

- `src/market_sentry/live_readiness.py` or `src/market_sentry/data/live_readiness.py`
- `tests/test_live_readiness.py`
- `README.md`

Possible files to modify only if small and useful:

- `src/market_sentry/config.py`
- `tests/test_config.py`
- `.env.example`

Do not modify unless absolutely necessary:

- `src/market_sentry/data/factory.py`
- `src/market_sentry/main.py`
- scanner filters/scoring/tiers
- alerts/voice/cooldowns
- HTTP transport
- Alpaca/FMP fetchers
- live provider builder
- live composed provider
- mock/fixture/composed fixture data

## Diagnostic behavior

The diagnostic should inspect config and report whether live readiness preconditions are present.

Suggested structures:

- `LiveReadinessStatus`
- `LiveReadinessCheck`
- `LiveReadinessReport`
- `evaluate_live_readiness(config, relative_volume_configured=False)`

Exact names can vary, but responsibilities should remain clear.

The diagnostic should check:

1. Provider is `live_composed`.
2. `MARKET_SENTRY_ALLOW_LIVE_DATA` / config allow-live is enabled.
3. Watchlist is non-empty.
4. Alpaca API key is present.
5. Alpaca API secret is present.
6. FMP API key is present.
7. Relative-volume source is explicitly configured or provided.

The diagnostic should return an inspectable report, not print directly.

## Result behavior

The report should include:

- whether all checks passed
- a stable list of check results
- stable check names/reason codes
- safe user-facing summary text, if useful

Suggested check names:

- `PROVIDER_SELECTED`
- `LIVE_DATA_ALLOWED`
- `WATCHLIST_PRESENT`
- `ALPACA_API_KEY_PRESENT`
- `ALPACA_API_SECRET_PRESENT`
- `FMP_API_KEY_PRESENT`
- `RELATIVE_VOLUME_SOURCE_PRESENT`

Each check can include:

- name/code
- passed boolean
- safe message

## Secret safety

Diagnostics must not expose secret values.

Do not include:

- Alpaca key value
- Alpaca secret value
- FMP key value
- authorization headers
- raw config repr if it includes secrets
- raw request reprs

Messages should say whether a required value is present or missing, never what the value is.

## Relative-volume readiness

The diagnostic should not calculate relative volume.

It should only report whether a relative-volume source/configuration was explicitly provided.

Acceptable test-facing input examples:

- `relative_volume_configured=True`
- `relative_volume_provider=...`
- `relative_volume_by_symbol={...}`

Do not infer RVOL readiness from unrelated data.

## Optional CLI behavior

Preferred Phase 12F path:

- Add diagnostic helper only.
- Do not add CLI flags yet.

If a CLI pathway is added, it must be explicitly non-live and must not make network calls. But the safer path is helper-only in this phase.

## Testing requirements

Add tests for:

- report fails when provider is not `live_composed`.
- report fails when allow-live is false/missing.
- report fails when watchlist is empty.
- report fails when Alpaca key is missing.
- report fails when Alpaca secret is missing.
- report fails when FMP key is missing.
- report fails when RVOL source/configuration is missing.
- report passes when all preconditions are present.
- report exposes stable check names/results.
- report messages do not expose secrets.
- report does not instantiate `StdlibHttpTransport`.
- report does not instantiate live Alpaca/FMP fetchers.
- report does not make HTTP/network calls.
- no external HTTP dependency is added.
- runtime provider factory remains unchanged.
- default runtime remains mock.
- fixture provider still works offline.
- composed_fixture still works offline.
- alpaca remains placeholder.
- live_composed remains gated placeholder.
- full test suite passes.

## Documentation requirements

Update README concisely:

- Live readiness diagnostics exist for future live-provider phases.
- Diagnostics validate local preconditions only.
- Diagnostics do not call Alpaca, FMP, or any network API.
- Diagnostics do not activate `live_composed`.
- Runtime remains mock by default.
- Fixture and composed_fixture remain offline.
- Alpaca remains placeholder.
- live_composed remains gated placeholder.
- RVOL source must be explicit and is not fabricated.
- Secrets should not be committed.
- Trading/order functionality remains out of scope.

## Verification commands

After building, run:

```powershell
python -m pytest
```

Also run:

```powershell
python -m market_sentry
```

Manually verify:

```powershell
$env:MARKET_SENTRY_PROVIDER="fixture"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

```powershell
$env:MARKET_SENTRY_PROVIDER="composed_fixture"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

```powershell
$env:MARKET_SENTRY_PROVIDER="alpaca"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

```powershell
$env:MARKET_SENTRY_PROVIDER="live_composed"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

Verify the gate-passing placeholder case still fails as reserved/inactive:

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
