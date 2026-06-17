# Phase 11D — Composed Live-Data Candidate Builder Skeleton

## Status
Planned.

## Purpose
Phase 11D adds a controlled candidate-builder skeleton that combines future Alpaca movement data and FMP float/reference data into scanner-ready `StockCandidate` objects.

This phase is still offline/fake-transport only. It must not activate any live provider at runtime.

## Project Boundary
Market Sentry is a personal-use low-float momentum scanner with local voice alerts.

Market Sentry is not a trading bot.

Do not add:
- brokerage trading APIs
- order placement
- trade execution
- buy/sell/entry/exit recommendations
- automated trading behavior

## Phase 11D Goal
Create a composed live-data candidate builder skeleton that can:

1. Accept an injected `AlpacaSnapshotFetcher` or compatible snapshot source.
2. Accept an injected `FMPFloatFetcher` or compatible float source.
3. Accept an explicit relative-volume source/input.
4. Combine those inputs through the existing candidate composition logic.
5. Return scanner-ready `StockCandidate` objects for usable symbol data.
6. Skip incomplete/unusable data with inspectable skip reasons.

This phase should prove the composition path works without making live network calls.

## Non-Goals
Do not add:
- runtime provider activation
- provider factory activation
- live Alpaca provider
- live FMP provider
- real network calls in tests
- external HTTP dependencies
- broad-market scanning
- all-shares-float crawling
- WebSockets
- streaming market data
- SEC/news/halt/split ingestion
- dashboard UI
- persistent database storage
- new CLI flags
- order APIs
- order placement
- trade execution

## Runtime Expectations After Phase 11D
Runtime behavior must remain unchanged:

1. `python -m market_sentry` still defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock` still works.
3. `MARKET_SENTRY_PROVIDER=fixture` still works offline.
4. `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as placeholder.
5. FMP is still not active as a runtime provider.
6. Loop behavior remains unchanged.
7. Voice behavior remains unchanged.
8. Scanner qualification rules remain unchanged.
9. Scoring remains unchanged.
10. Existing report formatting remains unchanged.

## Data Boundary
Alpaca can provide market movement data, such as:
- latest price
- daily volume
- high of day
- previous close
- daily gain inputs

FMP can provide float/reference data, such as:
- float shares
- outstanding shares, if present
- reported date, if present

Relative volume must still be explicit.

Do not fabricate relative volume. If relative volume is unavailable for a symbol, that symbol must be skipped or marked unusable according to existing composition behavior.

## Expected Files
Create or modify:

- `src/market_sentry/data/live_candidate_builder.py`
- `tests/test_live_candidate_builder.py`
- `README.md`

Possible only if truly necessary:

- `src/market_sentry/data/composer.py`
- `tests/test_composer.py`
- `src/market_sentry/data/alpaca_fetcher.py`
- `tests/test_alpaca_fetcher.py`
- `src/market_sentry/data/fmp_fetcher.py`
- `tests/test_fmp_fetcher.py`

Do not modify unless absolutely necessary:

- `src/market_sentry/main.py`
- `tests/test_main.py`
- `src/market_sentry/data/factory.py`
- `tests/test_provider_factory.py`
- scanner filters
- scanner scoring
- scanner tiers
- alert generator
- alert formatter
- speaker behavior
- cooldown behavior
- mock data contents
- fixture provider contents

## Suggested Structures
Use simple, testable structures. Possible names:

- `LiveCandidateBuilder`
- `LiveCandidateBuildResult`
- `LiveCandidateSkipReason`
- `build_candidates(symbols, relative_volume_by_symbol)`

The exact names can vary, but the responsibilities should be clear.

## Builder Behavior
The builder should:

1. Accept a controlled list of symbols.
2. Normalize symbols by trimming and uppercasing.
3. Ignore empty symbol entries safely.
4. Use the injected Alpaca snapshot fetcher/source for movement data.
5. Use the injected FMP float fetcher/source for float data.
6. Require explicit relative volume by symbol.
7. Reuse existing candidate composition logic where practical.
8. Return usable `StockCandidate` objects.
9. Preserve inspectable skip reasons/results for unusable symbols.
10. Avoid fabricating missing market, float, or relative-volume data.

## Important Composition Rules
A composed candidate must only exist when all required scanner inputs are available and valid:

- symbol
- price
- daily percent change
- relative volume
- daily volume
- float shares

Optional fields may be carried through when available:

- high of day
- 15-minute change percent
- distance from high of day
- rotation

If 15-minute change is not available from the snapshot-only path, do not fabricate it.

If relative volume is missing, skip the symbol.

If float data is missing or unusable, skip the symbol.

If Alpaca movement data is missing or unusable, skip the symbol.

## Fetcher Boundary
The builder may call already-existing fetcher skeletons, but tests must use fake transports or fake source objects.

Do not instantiate a real HTTP transport.

Do not make any live HTTP calls.

Do not require real API credentials.

## Error Behavior
Errors should remain clear and secret-safe.

1. Transport/fetcher errors may propagate or be represented as skip/build errors, but tests should define the expected behavior.
2. Do not leak API keys, request params, headers, or raw request reprs.
3. Do not swallow failures silently.
4. Do not misrepresent skipped symbols as qualified scanner candidates.

## Testing Requirements
Add tests for:

- Builder normalizes symbols.
- Builder ignores empty symbols safely.
- Builder combines fake Alpaca snapshot data + fake FMP float data + explicit relative volume into `StockCandidate` objects.
- Builder reuses existing composition behavior or produces equivalent results.
- Missing relative volume causes a safe skip.
- Missing Alpaca movement data causes a safe skip.
- Missing FMP float data causes a safe skip.
- Invalid float data causes a safe skip.
- Invalid or missing movement fields cause a safe skip.
- Optional HOD data is carried through when present.
- Optional 15-minute data is not fabricated when absent.
- Skip/build results are inspectable.
- No live network calls are made.
- No external HTTP dependency is added.
- No real credentials are required.
- Provider factory remains unchanged.
- Default runtime still works.
- Fixture provider still works offline.
- Alpaca remains runtime placeholder.
- FMP remains inactive as a runtime provider.
- Full test suite passes.

## Documentation Requirements
Update README concisely:

- Live-data candidate builder skeleton exists for future provider phases.
- It combines Alpaca movement data, FMP float data, and explicit relative-volume input.
- It uses fake/offline tests only in this phase.
- Runtime still defaults to mock.
- Fixture provider remains offline/static.
- Alpaca/FMP live providers are still not active.
- Relative volume must not be fabricated.
- Credentials should not be committed.
- Trading/order functionality remains out of scope.

## Verification Commands
Run:

```powershell
python -m pytest
```

Also run:

```powershell
python -m market_sentry
```

Manually verify if practical:

```powershell
$env:MARKET_SENTRY_PROVIDER="fixture"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

Also verify:

```powershell
$env:MARKET_SENTRY_PROVIDER="alpaca"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

## Completion Criteria
Phase 11D is complete when:

1. A builder skeleton exists.
2. It composes scanner-ready candidates from fake Alpaca + fake FMP + explicit relative-volume inputs.
3. Missing required data produces safe, inspectable skips.
4. It does not activate any runtime provider.
5. It does not make live network calls.
6. It does not add external HTTP dependencies.
7. It does not add trading/order behavior.
8. Full tests pass.
