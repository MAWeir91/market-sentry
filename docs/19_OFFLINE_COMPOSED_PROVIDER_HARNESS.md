# Phase 11E — Offline Composed Provider Harness

## Goal

Create an offline composed provider harness that exercises the Phase 11D live-data candidate builder end-to-end without activating real live data.

The provider should combine:

- static/offline Alpaca-style movement data
- static/offline FMP-style float/reference data
- explicit static relative-volume data
- the existing live candidate builder
- existing scanner/report pipeline

This phase is a bridge between the current fixture provider and a future controlled live provider. It should prove that the composed builder can be used through the normal `MarketDataProvider` interface while remaining entirely offline.

## Non-goals

Do not add:

- live Alpaca provider activation
- live FMP provider activation
- real HTTP calls
- real HTTP transport instantiation
- API-key requirements
- external HTTP dependencies
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

Market Sentry remains a scanner, not a trading bot.

## Runtime boundary

This phase may add a new explicit offline provider option, for example:

```text
MARKET_SENTRY_PROVIDER=composed_fixture
```

The provider must be obviously offline/static in name, documentation, tests, and output label.

Default runtime must remain mock.

`MARKET_SENTRY_PROVIDER=alpaca` must remain a placeholder error.

FMP must remain inactive as a standalone runtime provider.

## Expected runtime behavior after this phase

1. `python -m market_sentry` defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock` works.
3. `MARKET_SENTRY_PROVIDER=fixture` works offline.
4. `MARKET_SENTRY_PROVIDER=composed_fixture` or the chosen offline composed name works offline.
5. `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as placeholder.
6. FMP is not active as a runtime provider.
7. Loop behavior remains unchanged.
8. Voice behavior remains unchanged.
9. Scanner qualification rules remain unchanged.
10. Scoring remains unchanged.
11. Report formatting remains unchanged except for the provider-specific report label.

## Expected files

Create or modify:

- `src/market_sentry/data/composed_fixture_provider.py`
- `tests/test_composed_fixture_provider.py`
- `src/market_sentry/data/factory.py`
- `tests/test_provider_factory.py`
- `src/market_sentry/main.py`
- `tests/test_main.py`
- `README.md`

Only if truly necessary:

- `src/market_sentry/data/live_candidate_builder.py`
- `tests/test_live_candidate_builder.py`
- `src/market_sentry/data/composer.py`
- `tests/test_composer.py`

Do not modify unless absolutely necessary:

- scanner filters
- scanner scoring
- scanner tiers
- alert generator
- alert formatter
- speaker behavior
- cooldown behavior
- Alpaca fetcher behavior
- FMP fetcher behavior
- HTTP transport behavior

## Provider naming

Use a clear offline name. Preferred:

```text
composed_fixture
```

Acceptable alternatives:

```text
offline_composed
live_fixture
```

Avoid names that imply real live connectivity, such as:

```text
live
alpaca_fmp
real
production
```

## Provider behavior

The offline composed provider should:

1. Implement the existing `MarketDataProvider` protocol.
2. Return `list[StockCandidate]` from `get_candidates()`.
3. Use the Phase 11D live candidate builder internally.
4. Use fake/static Alpaca movement source data.
5. Use fake/static FMP float source data.
6. Use explicit static relative-volume data.
7. Never fabricate relative volume.
8. Never make HTTP calls.
9. Never instantiate a real HTTP transport.
10. Never require API keys.
11. Never place orders or interact with trading APIs.

## Static source behavior

The provider may use small in-memory fake source classes such as:

- `StaticAlpacaSnapshotSource`
- `StaticFMPFloatSource`

These should return already-normalized objects expected by `LiveCandidateBuilder`.

Keep these static source classes private to the composed fixture provider module unless tests need import access.

## Data requirements

Static data should include at least:

1. One fully valid qualified symbol.
2. One symbol skipped for missing relative volume.
3. One symbol skipped for missing FMP float data or invalid float.
4. One symbol skipped for missing Alpaca movement data or invalid movement data.

The provider’s `get_candidates()` should return only valid candidates.

Tests should be able to inspect build results if the provider exposes a safe inspection method, such as:

```python
composition_results()
```

or:

```python
build_results()
```

This inspection method should be optional for runtime and primarily useful for tests/debugging.

## Report label behavior

Add a provider-specific report label for the offline composed provider.

Preferred label:

```text
Composed Fixture Scanner Report
```

Do not rename existing labels:

```text
Mock Scanner Report
Fixture Scanner Report
```

Do not show the composed fixture label for mock or fixture modes.

Do not show any scanner report label when Alpaca placeholder errors before rendering.

## Factory behavior

The provider factory may register the new offline composed provider.

This is allowed because the provider is offline/static and explicit.

Factory behavior should remain:

- default: mock
- `mock`: mock provider
- `fixture`: existing fixture provider
- `composed_fixture`: new offline composed provider
- `alpaca`: placeholder error
- unknown provider: clean configuration error

Do not activate live Alpaca or FMP runtime providers.

## Testing requirements

Add tests for:

- provider implements/behaves like `MarketDataProvider`
- provider returns only valid `StockCandidate` objects
- provider uses the live candidate builder path
- provider does not fabricate relative volume
- missing relative-volume symbol is skipped
- missing/invalid FMP float symbol is skipped
- missing/invalid Alpaca movement symbol is skipped
- build/composition results are inspectable if exposed
- no live network calls are made
- no real credentials are required
- no external HTTP dependency is added
- factory registers the offline composed provider under the chosen explicit name
- default provider remains mock
- existing fixture provider still works
- Alpaca remains placeholder
- unknown provider still fails cleanly
- CLI label for composed fixture is correct
- CLI labels for mock and fixture are unchanged
- loop behavior remains unchanged if covered by existing tests
- voice behavior remains unchanged if covered by existing tests
- full test suite passes

## Documentation requirements

Update README concisely:

- new offline composed provider harness exists
- it combines static Alpaca-style movement data, static FMP-style float data, and explicit relative-volume data
- it uses the live candidate builder path
- it is not a live provider
- default runtime remains mock
- fixture provider remains offline/static
- Alpaca remains placeholder
- FMP remains inactive as a runtime provider
- no credentials are required for current runtime modes
- secrets should not be committed
- trading/order functionality remains out of scope

## Manual verification commands

Run:

```powershell
python -m pytest
```

Run default mock:

```powershell
python -m market_sentry
```

Run existing fixture:

```powershell
$env:MARKET_SENTRY_PROVIDER="fixture"
python -m market_sentry
Remove-Item Env:MARKET_SENTRY_PROVIDER
```

Run new offline composed provider:

```powershell
$env:MARKET_SENTRY_PROVIDER="composed_fixture"
python -m market_sentry
Remove-Item Env:MARKET_SENTRY_PROVIDER
```

Run Alpaca placeholder:

```powershell
$env:MARKET_SENTRY_PROVIDER="alpaca"
python -m market_sentry
Remove-Item Env:MARKET_SENTRY_PROVIDER
```

## Acceptance criteria

Phase 11E is complete when:

1. The new offline composed provider is explicit and clearly non-live.
2. The provider is selectable only by its explicit offline provider name.
3. The provider uses the live candidate builder path.
4. The provider returns only valid scanner candidates.
5. Skipped symbols remain inspectable in tests/debug methods.
6. Relative volume is explicit and never fabricated.
7. No real HTTP calls are made.
8. No real HTTP transport is instantiated.
9. No API keys are required.
10. No external HTTP dependency is added.
11. Default runtime remains mock.
12. Existing fixture runtime remains unchanged.
13. Alpaca remains a placeholder runtime error.
14. FMP remains inactive as a runtime provider.
15. No trading/order behavior is added.
16. Full tests pass.
