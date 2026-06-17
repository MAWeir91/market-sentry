# Phase 12G — CLI Live Readiness Preflight

## Goal

Expose the Phase 12F live-readiness diagnostics through a safe CLI preflight flag.

The preflight command should let the user inspect whether local configuration appears ready for a future `live_composed` provider without activating live scanning, instantiating live providers, or calling any APIs.

This phase is CLI/reporting only.

## Non-goals

Do not add:

- live runtime activation
- working `live_composed` provider factory activation
- real HTTP calls
- external HTTP dependencies
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

Market Sentry is a scanner and alerting tool only. It must not become a trading bot.

## Expected CLI Behavior

Add a CLI flag such as:

```powershell
python -m market_sentry --live-readiness
```

or an equivalent clear name if the existing CLI parser strongly prefers another pattern.

The command should:

1. Load local config the same way normal runtime does.
2. Evaluate Phase 12F readiness diagnostics.
3. Print a human-readable readiness report.
4. Exit without running scanner provider selection/reporting.
5. Exit without creating any market-data provider.
6. Exit without creating `StdlibHttpTransport`.
7. Exit without creating Alpaca/FMP fetchers.
8. Exit without any HTTP/network calls.
9. Preserve all existing runtime behavior when the flag is not used.

## Exit Code Guidance

Preferred behavior:

- Exit `0` when all readiness checks pass.
- Exit `1` when one or more readiness checks fail.

This makes the preflight useful in scripts while remaining safe.

## Relative-Volume Readiness Signal

The existing diagnostics require an explicit RVOL readiness signal.

For this phase, add a safe CLI-only signal such as:

```powershell
python -m market_sentry --live-readiness --relative-volume-configured
```

or an equivalent clear flag name.

This flag should only tell the diagnostic helper that an explicit RVOL source has been configured/provided. It must not calculate RVOL, fetch RVOL, infer RVOL, or activate any RVOL provider.

If the flag is not present, the readiness report should fail the RVOL-source check.

## Output Requirements

The CLI output should be clear, stable, and secret-safe.

Suggested output shape:

```text
Market Sentry Live Readiness
Status: NOT_READY

[PASS] PROVIDER_SELECTED - Provider is live_composed.
[FAIL] LIVE_DATA_ALLOWED - Live data is not explicitly enabled.
[PASS] WATCHLIST_PRESENT - Watchlist is present.
[PASS] ALPACA_API_KEY_PRESENT - Alpaca API key is present.
[PASS] ALPACA_API_SECRET_PRESENT - Alpaca API secret is present.
[PASS] FMP_API_KEY_PRESENT - FMP API key is present.
[FAIL] RELATIVE_VOLUME_SOURCE_PRESENT - Relative-volume source is not explicitly configured.

Summary: Live readiness checks failed.
Note: This preflight does not call APIs and does not activate live_composed.
```

Exact wording can vary, but it must remain safe and clear.

## Secret Safety

The CLI output must never print:

- Alpaca key values
- Alpaca secret values
- FMP key values
- authorization headers
- raw config reprs if they include secrets
- raw request reprs

Messages may say only whether each secret is present or missing.

## Expected Runtime Behavior After Phase 12G

When the readiness flag is not used:

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

When the readiness flag is used:

1. The CLI prints diagnostics only.
2. The scanner report is not rendered.
3. Providers are not built.
4. The factory is not used to activate live data.
5. No network calls occur.

## Expected Files

Likely files to modify:

- `src/market_sentry/main.py`
- `tests/test_main.py`
- `README.md`

Possible files to modify if useful:

- `src/market_sentry/live_readiness.py`
- `tests/test_live_readiness.py`

Do not modify unless absolutely necessary:

- `src/market_sentry/data/factory.py`
- `src/market_sentry/data/http_stdlib.py`
- Alpaca/FMP fetchers
- live provider builder
- live composed provider
- scanner filters/scoring/tiers
- alerts/voice/cooldowns
- mock/fixture/composed fixture data

## Testing Requirements

Add or update tests for:

- `--live-readiness` prints a readiness report.
- Failed readiness exits `1`.
- Passing readiness exits `0`.
- Output includes stable check codes.
- Output does not expose secret values.
- Missing RVOL source fails when the explicit RVOL flag is absent.
- RVOL source passes when the explicit RVOL flag is present.
- Readiness command does not render the scanner report.
- Readiness command does not instantiate provider factory live behavior.
- Readiness command does not instantiate `StdlibHttpTransport`.
- Readiness command does not instantiate Alpaca/FMP fetchers.
- Readiness command does not make HTTP/network calls.
- Normal default runtime still works.
- `fixture` runtime still works offline.
- `composed_fixture` runtime still works offline.
- `alpaca` remains placeholder.
- `live_composed` remains gated placeholder when run as provider.
- Full test suite passes.

## Documentation Requirements

Update README concisely with:

- `--live-readiness` usage.
- Optional explicit RVOL readiness flag.
- Diagnostics do not call Alpaca, FMP, or any network API.
- Diagnostics do not activate `live_composed`.
- Runtime remains mock by default.
- Fixture and composed_fixture remain offline.
- Alpaca remains placeholder.
- live_composed remains gated placeholder.
- RVOL source must be explicit and is not fabricated.
- Secrets should not be committed.
- Trading/order functionality remains out of scope.

## Acceptance Criteria

Phase 12G is acceptable only if:

- readiness CLI is report-only
- no live provider activation occurs
- no live fetcher/transport runtime construction occurs
- no network calls occur
- secret values are never printed
- existing scanner runtime behavior is unchanged
- full test suite passes
