# Phase 10D — Fixture-Composed Provider

## Purpose

Phase 10D adds an offline fixture-based provider that uses the Phase 10A Alpaca market-data skeleton, the Phase 10B FMP float/reference skeleton, and the Phase 10C candidate composer to return scanner-ready `StockCandidate` objects through the existing `MarketDataProvider` contract.

This phase bridges the gap between the simple `MockMarketDataProvider` and a future live composed provider.

## Phase Goal

Create a provider that proves this future data flow can work behind the normal provider interface:

```text
Alpaca-style snapshot fixture
+ Alpaca-style bars fixture
+ FMP-style float/reference fixture
+ explicit relative volume fixture
→ composer
→ StockCandidate objects
→ ScannerEngine
```

The provider must be offline-only and fixture-driven.

## Current Runtime Boundary

The default runtime must remain mock-based.

```powershell
python -m market_sentry
```

must continue to use mock data unless a later phase explicitly approves another runtime provider.

`MARKET_SENTRY_PROVIDER=alpaca` must continue to fail cleanly as a placeholder.

No live Alpaca or FMP provider should become active in this phase.

## In Scope

- Add an offline fixture-composed provider.
- Implement the existing `MarketDataProvider` contract.
- Use static in-code or test fixture payloads.
- Use existing Alpaca parsing helpers where appropriate.
- Use existing FMP parsing helpers where appropriate.
- Use the Phase 10C composer to create `StockCandidate` objects.
- Include explicit relative-volume fixture values.
- Skip invalid fixture records safely.
- Add tests proving the provider returns scanner-ready candidates.
- Add tests proving candidates can be scanned by `ScannerEngine`.
- Optionally register a provider-factory placeholder/name such as `fixture` or `fixture_composed`, but only if it is safe and well tested.
- Keep the default provider as `mock`.

## Out of Scope

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

Trading/order functionality is never in scope for Market Sentry.

## Provider Naming

A fixture-composed provider may use a clear provider name such as:

```text
fixture
```

or:

```text
fixture_composed
```

Recommended: `fixture` for simplicity.

If registered in the provider factory:

```powershell
$env:MARKET_SENTRY_PROVIDER="fixture"
python -m market_sentry
```

may run using the fixture-composed provider.

This is acceptable because it is still offline and fixture-only.

However:

- `mock` must remain the default.
- `alpaca` must remain placeholder/not implemented.
- `fmp` should not become a standalone runtime market-data provider.
- Unknown providers should still fail cleanly.

## Provider Contract

The new provider should satisfy:

```python
get_candidates() -> list[StockCandidate]
```

It should return only successfully composed candidates.

Skipped fixture records should not crash the provider.

The provider may expose skipped composition results for tests/debugging if useful, but the `MarketDataProvider` contract should remain simple.

## Fixture Data Requirements

Fixtures should include at least:

1. A valid high-quality low-float runner.
2. A candidate with strong rotation potential.
3. A candidate with high-of-day context.
4. A candidate with 15-minute change context.
5. At least one invalid/skipped record, such as missing relative volume or missing float.

Relative volume must be explicit.

Do not fabricate relative volume.

## Composition Requirements

The provider should use the composer rather than duplicating composition logic.

Required fields for successful candidate creation:

- symbol
- price
- daily gain percent
- daily volume
- relative volume
- float shares

Optional fields:

- high of day
- 15-minute change

Optional fields should be carried through when available.

## Runtime Behavior Expectations

After Phase 10D:

1. `python -m market_sentry` still works and defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock` still works.
3. `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as placeholder.
4. `MARKET_SENTRY_PROVIDER=fixture` may work if the provider factory registers the fixture provider.
5. Loop mode remains unchanged.
6. Voice mode remains unchanged.
7. Scanner qualification rules remain unchanged.
8. Scoring remains unchanged.
9. No live network behavior is added.
10. No trading/order behavior is added.

## Testing Requirements

Add tests for:

- Fixture-composed provider implements the `MarketDataProvider` contract.
- Fixture-composed provider returns `StockCandidate` objects.
- Provider uses composed Alpaca/FMP-style fixture data.
- Provider carries high-of-day into candidates.
- Provider carries 15-minute change into candidates.
- Provider uses explicit relative-volume fixture data.
- Provider skips invalid fixture records safely.
- Provider returns only successfully composed candidates from `get_candidates()`.
- Skipped records can be inspected if that behavior is exposed.
- Candidates returned by the provider can be scanned by `ScannerEngine`.
- At least one fixture-composed candidate qualifies under existing scanner rules.
- Default provider remains mock.
- Alpaca provider remains placeholder.
- If `fixture` provider is registered, provider factory returns the fixture provider for `fixture`.
- Unknown providers still fail cleanly.
- Tests do not require API keys.
- Tests do not use real network calls.
- Existing CLI tests still pass.
- Existing scanner/scoring behavior remains unchanged.
- Full test suite passes.

## Documentation Requirements

Update README concisely:

- fixture-composed provider exists for offline future-provider testing
- default runtime remains mock
- fixture provider is offline and uses static fixture data
- Alpaca/FMP live providers are still not active
- no credentials are required for fixture mode
- credentials should not be committed
- trading/order functionality remains out of scope

If `fixture` is registered as a provider-factory option, document:

```powershell
$env:MARKET_SENTRY_PROVIDER="fixture"
python -m market_sentry
Remove-Item Env:MARKET_SENTRY_PROVIDER
```

## Acceptance Criteria

Phase 10D is complete when:

- A fixture-composed provider exists.
- It returns scanner-ready `StockCandidate` objects.
- It uses the existing composer.
- It uses Alpaca/FMP-style offline fixtures.
- It requires explicit relative volume.
- It skips invalid records safely.
- It is covered by tests.
- The full test suite passes.
- The default runtime remains mock.
- No live network behavior is added.
- No trading/order behavior is added.
