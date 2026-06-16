# Phase 9C — Runtime Provider Wiring

## Purpose

Phase 9C wires the provider configuration and provider factory into the Market Sentry runtime while preserving the current mock-only behavior.

The goal is to make the app use the provider-selection skeleton from Phase 9B without adding any real data provider implementation, API calls, network calls, credentials requirement, or trading behavior.

This phase is an integration/wiring phase, not a live data phase.

---

## Current State

Market Sentry currently has:

- Scanner core
- Mock data provider
- Data provider protocol
- Provider configuration skeleton
- Provider factory skeleton
- Watchlist parsing
- Placeholder environment variables
- CLI report
- Optional local voice playback
- Mock polling loop

However, the CLI runtime still uses the mock provider directly. Phase 9C should make runtime provider creation go through the config/factory path.

---

## Goals

1. Load app configuration at runtime.
2. Use the configured provider name to create the market data provider through the provider factory.
3. Keep `mock` as the default and only functional provider.
4. Preserve current CLI behavior for normal mock usage.
5. Show clear user-friendly errors for unsupported or unknown providers.
6. Keep loop mode, voice mode, scanner output, alert behavior, and scoring unchanged.
7. Add tests proving runtime provider selection is safe and deterministic.

---

## Non-Goals

Do not add:

- Real API calls
- API key requirements
- Network calls
- HTTP dependencies
- WebSockets
- Alpaca provider implementation
- FMP provider implementation
- SEC/news/halt/split ingestion
- Dashboard UI
- Persistent database storage
- Brokerage/order APIs
- Order placement
- Trade execution
- New CLI flags

Trading/order functionality is never in scope for Market Sentry.

---

## Approved Runtime Behavior

### Default Runtime

```powershell
python -m market_sentry
```

Expected behavior:

- Loads app config.
- Provider defaults to `mock`.
- Provider factory returns `MockMarketDataProvider`.
- Scanner report behaves as before.
- Voice-ready alerts behave as before.
- No credentials required.
- No network calls.

---

### Explicit Mock Provider

```powershell
$env:MARKET_SENTRY_PROVIDER="mock"
python -m market_sentry
```

Expected behavior:

- Uses mock provider.
- Same output as default mock runtime.
- No credentials required.
- No network calls.

---

### Alpaca Placeholder Provider

```powershell
$env:MARKET_SENTRY_PROVIDER="alpaca"
python -m market_sentry
```

Expected behavior:

- Runtime should not crash with a traceback in normal CLI usage.
- Runtime should print a clear error message explaining that Alpaca is a future placeholder and live provider implementation is not present yet.
- Runtime should exit cleanly with a non-zero exit code or equivalent error result.
- No network calls.
- No credential validation.

---

### Unknown Provider

```powershell
$env:MARKET_SENTRY_PROVIDER="bad_provider"
python -m market_sentry
```

Expected behavior:

- Runtime should not crash with a traceback in normal CLI usage.
- Runtime should print a clear validation error explaining that the provider is unknown/unsupported.
- Runtime should exit cleanly with a non-zero exit code or equivalent error result.
- No network calls.

---

## Loop Mode Behavior

Loop mode should also use the provider factory.

```powershell
python -m market_sentry --loop --interval 30
```

Expected behavior:

- Default provider is still mock.
- Loop behavior remains unchanged.
- Cooldowns remain unchanged.
- Voice behavior remains unchanged.
- No network calls.

If provider creation fails before the loop starts, the app should print the provider error and exit cleanly rather than entering the loop.

---

## Voice Behavior

Voice behavior should not change.

```powershell
python -m market_sentry --speak
python -m market_sentry --loop --interval 30 --speak
```

Expected behavior:

- Mock provider remains default.
- Report prints before speech attempt.
- Loop cooldown behavior remains intact.
- Provider selection errors should prevent the scanner from running and should not attempt speech.

---

## Implementation Guidance

### Recommended Runtime Flow

1. Load `AppConfig` from environment.
2. Create provider using `create_market_data_provider(config)`.
3. Pass the provider into the existing scanner/report flow.
4. Preserve existing output formatting.
5. Catch provider configuration errors at the CLI boundary.
6. Print clear error messages for user-facing CLI usage.
7. Return an exit code from `main()` if current structure supports it.

---

## Error Handling

Provider configuration errors should be handled clearly.

Recommended wording examples:

```text
Provider configuration error: Alpaca provider is a future placeholder. Live API implementation is not present yet.
```

```text
Provider configuration error: Unknown market data provider: bad_provider
```

Do not include secrets in error messages.

Do not print stack traces for expected provider configuration errors in normal CLI usage.

---

## Testing Expectations

Tests should prove:

- Default runtime still uses mock provider.
- `MARKET_SENTRY_PROVIDER=mock` works.
- `MARKET_SENTRY_PROVIDER=alpaca` exits/returns cleanly with a clear placeholder message.
- Unknown provider exits/returns cleanly with a clear validation message.
- Loop mode uses provider factory while mock remains default.
- Provider creation failure prevents loop execution.
- Voice path still works with mock provider.
- Provider errors do not attempt speech.
- Tests do not require API keys.
- Tests do not use network calls.
- Tests do not require real audio playback.
- Existing test suite passes.

Tests should use environment patching/monkeypatching and fake speakers/sleep functions where needed.

---

## Files Likely to Change

Expected:

- `src/market_sentry/main.py`
- `tests/test_main.py`
- `README.md`

Possible only if needed:

- `src/market_sentry/config.py`
- `src/market_sentry/data/factory.py`
- `tests/test_config.py`
- `tests/test_provider_factory.py`

Do not modify unless absolutely necessary:

- Scanner filters
- Scanner scoring
- Scanner tiers
- Alert generator
- Alert formatter
- Speaker behavior
- Cooldown behavior
- Mock data contents

---

## Documentation Updates

README should mention:

- Runtime now uses provider config/factory internally.
- Mock remains the default and only functional provider.
- `MARKET_SENTRY_PROVIDER=mock` is supported.
- `MARKET_SENTRY_PROVIDER=alpaca` is a placeholder and will show a clear not-implemented message.
- Real API implementation is still not present.
- No credentials are required for mock mode.

Keep README updates concise.

---

## Acceptance Criteria

Phase 9C is complete when:

- Runtime uses provider config/factory for provider creation.
- Default CLI behavior remains mock-based and unchanged from the user's perspective.
- Explicit `mock` provider works.
- Placeholder `alpaca` provider fails cleanly with a clear message.
- Unknown provider fails cleanly with a clear message.
- Loop mode still works with mock provider.
- Voice mode still works with mock provider.
- No live API/network behavior is added.
- No HTTP/WebSocket dependency is added.
- No trading/order behavior is added.
- Tests cover provider runtime wiring.
- Full test suite passes.
