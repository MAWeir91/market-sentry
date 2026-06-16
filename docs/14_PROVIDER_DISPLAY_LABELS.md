# Phase 10E — Provider Display Label Cleanup

## Purpose

Phase 10E is a small display cleanup phase.

Market Sentry now supports more than one offline provider path:

- `mock`, the default mock data provider
- `fixture`, the offline fixture-composed provider

After Phase 10D, fixture mode works correctly, but the CLI report still says `Mock Scanner Report` even when `MARKET_SENTRY_PROVIDER=fixture` is selected. Phase 10E updates the report label so the terminal output reflects the active provider more accurately.

## Project Boundary

Market Sentry is a personal-use low-float momentum scanner with local voice alerts.

Market Sentry is not a trading bot.

Do not add:

- live HTTP calls
- API-key requirements
- runtime activation of Alpaca
- runtime activation of FMP
- WebSockets
- broad-market scanning
- streaming market data
- SEC ingestion
- news ingestion
- halt ingestion
- split ingestion
- dashboard UI
- persistent database storage
- broker order APIs
- order placement
- trade execution
- new runtime CLI flags
- external HTTP dependencies
- real HTTP transport

Trading/order functionality is never in scope.

## Phase 10E Goal

Update the CLI report display label based on the active provider.

Expected examples:

```text
MARKET_SENTRY_PROVIDER=mock
→ Mock Scanner Report
```

```text
MARKET_SENTRY_PROVIDER=fixture
→ Fixture Scanner Report
```

The default command should still show:

```text
Mock Scanner Report
```

because `mock` remains the default provider.

## Approved Runtime Behavior

1. `python -m market_sentry` still works and defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock python -m market_sentry` works and displays `Mock Scanner Report`.
3. `MARKET_SENTRY_PROVIDER=fixture python -m market_sentry` works and displays `Fixture Scanner Report`.
4. `MARKET_SENTRY_PROVIDER=alpaca python -m market_sentry` still fails cleanly as a placeholder.
5. Unknown providers still fail cleanly.
6. Loop mode still works.
7. Voice mode still works.
8. Scanner qualification rules remain unchanged.
9. Scoring remains unchanged.
10. Report content remains unchanged except for the provider label/header.

## Suggested Implementation

Add a small provider display-label helper.

Possible approaches:

- Add a helper in `main.py`, such as `get_provider_display_label(config)`.
- Or add a property/helper to `AppConfig` if that is cleaner.
- Or add a very small provider-label mapping near the CLI/report code.

Preferred labels:

| Provider | Display label |
|---|---|
| `mock` | `Mock Scanner Report` |
| `fixture` | `Fixture Scanner Report` |

Do not add labels for live providers that are not active.

For provider errors, no report label should be printed because scanning should not start.

## Files Expected to Modify

Expected:

- `src/market_sentry/main.py`
- `tests/test_main.py`
- `README.md`

Possible only if cleaner:

- `src/market_sentry/config.py`
- `tests/test_config.py`

Do not modify unless absolutely necessary:

- `src/market_sentry/data/factory.py`
- `src/market_sentry/data/fixture_provider.py`
- `tests/test_fixture_provider.py`
- scanner filters
- scanner scoring
- scanner tiers
- alert generator
- alert formatter
- speaker behavior
- cooldown behavior
- mock data contents
- Alpaca skeleton
- FMP skeleton
- composer

## Testing Requirements

Add or update tests for:

- Default run displays `Mock Scanner Report`.
- Explicit mock provider displays `Mock Scanner Report`.
- Fixture provider displays `Fixture Scanner Report`.
- Fixture provider no longer displays `Mock Scanner Report` as the report header.
- Alpaca placeholder errors do not print a scanner report label.
- Unknown provider errors do not print a scanner report label.
- Loop mode uses the correct report label.
- Voice mode still works with mock/fixture provider paths without real audio in tests.
- No live network calls are made.
- No trading/order behavior is added.
- Full test suite passes.

## Documentation Requirements

Update README concisely:

- Mention that the report header reflects the selected provider.
- Default is still mock.
- Fixture mode is offline/static fixture data.
- Alpaca/FMP live providers are still not active.
- No credentials are required for mock or fixture mode.

Include PowerShell examples if useful:

```powershell
python -m market_sentry

$env:MARKET_SENTRY_PROVIDER="fixture"
python -m market_sentry
Remove-Item Env:MARKET_SENTRY_PROVIDER
```

## Out of Scope

Do not change:

- scanner filters
- scoring
- tier logic
- alert generation
- voice message content
- provider factory behavior
- fixture data
- provider credentials
- API behavior
- network behavior
- CLI flags
- loop interval behavior
- cooldown behavior

## Completion Criteria

Phase 10E is complete when:

1. Default output still shows `Mock Scanner Report`.
2. Fixture provider output shows `Fixture Scanner Report`.
3. Provider error paths do not print scanner report headers.
4. Existing scanner behavior remains unchanged.
5. Existing loop and voice behavior remain unchanged.
6. No live API/network behavior is added.
7. No trading/order behavior is added.
8. Full test suite passes.
