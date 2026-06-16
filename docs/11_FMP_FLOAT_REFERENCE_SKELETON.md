# Phase 10B — FMP Float / Reference Skeleton

## Status

Planning/specification for an offline provider skeleton phase.

Phase 10B prepares Market Sentry for a future Financial Modeling Prep (FMP) float/reference-data integration. It should not activate a live FMP provider, require credentials, or perform network calls in tests.

## Goal

Add a safe FMP float/reference skeleton that can shape requests, protect API-key values, parse fixture responses, and normalize float/reference data for future scanner-ready candidate composition.

This phase complements Phase 10A:

```text
Alpaca = price, volume, high of day, bars, intraday movement
FMP    = float/reference data
Future = Alpaca market data + FMP float/reference data -> StockCandidate
```

## Non-goals

Do not add:

- live HTTP calls
- required API keys for tests or default runtime
- runtime activation of FMP
- runtime activation of Alpaca
- broad-market scanning
- WebSockets
- SEC ingestion
- news ingestion
- halt ingestion
- split ingestion
- dashboard UI
- persistent database storage
- trading/order functionality
- broker order APIs
- order placement
- trade execution

Trading/order functionality is never in scope for Market Sentry.

## Data Source Notes

FMP provides a Company Share Float & Liquidity API for retrieving publicly traded share/float information by symbol. The documented stable endpoint shape is:

```text
/stable/shares-float?symbol=AAPL
```

FMP's cycle-time documentation lists `Shares Float` as daily, so Market Sentry should treat float as reference data rather than real-time intraday data.

## Runtime Boundary

After Phase 10B:

- `python -m market_sentry` should still use the mock provider by default.
- `MARKET_SENTRY_PROVIDER=mock` should still work.
- `MARKET_SENTRY_PROVIDER=alpaca` should still fail cleanly as a placeholder.
- FMP should not become an active runtime provider.
- No runtime provider should silently fall back to mock when a non-mock provider is requested.
- Existing loop and voice behavior should remain unchanged.

## Expected Files

Create:

- `src/market_sentry/data/fmp.py`
- `tests/test_fmp_provider.py`

Modify:

- `README.md`

Possible only if necessary:

- `src/market_sentry/config.py`
- `src/market_sentry/data/provider.py`
- `src/market_sentry/data/factory.py`
- `tests/test_config.py`
- `tests/test_provider_factory.py`

Do not modify unless absolutely necessary:

- `src/market_sentry/main.py`
- scanner filters/scoring/tiers
- alert generator/formatter
- speaker/cooldown behavior
- mock data contents

## Suggested Structures

The implementation may include names like:

- `FMPReferenceSettings`
- `FMPRequest`
- `FMPFloatData`
- `build_auth_params(...)`
- `build_shares_float_request(...)`
- `parse_shares_float_response(...)`
- `normalize_float_shares(...)`
- `is_valid_low_float_reference(...)`

Exact names may vary, but behavior should stay focused and testable.

## Settings and Secret Safety

FMP settings should support:

- API key placeholder, optional
- base URL for request shaping

The API key must not appear in:

- dataclass repr output
- request repr output
- logs
- exceptions
- README examples
- test failure messages

Use `repr=False` or equivalent protections for secret-bearing fields.

## Request-Building Expectations

The FMP skeleton should shape request data only. It should not perform HTTP calls.

Expected behavior:

- Build a shares-float request path such as `/stable/shares-float`.
- Include `symbol` as an uppercase trimmed value.
- Include `apikey` as a query parameter only when present.
- Handle missing/empty symbol safely.
- Keep request objects deterministic and easy to inspect in tests.
- Hide API-key values from request repr output.

## Response Parsing Expectations

Fixture parsing should handle likely FMP response shapes safely.

Expected behavior:

- Parse symbol.
- Parse float shares from likely keys such as:
  - `floatShares`
  - `freeFloat`
  - `float`
- Parse outstanding shares if present from likely keys such as:
  - `outstandingShares`
  - `sharesOutstanding`
- Parse date if present.
- Return `None` for missing symbol data or unusable float data.
- Treat zero, negative, non-numeric, or missing float values as invalid.
- Preserve values as integers when valid.
- Do not fabricate float values.

## Data Quality Rules

Float/reference data can be stale. Phase 10B should explicitly treat FMP float data as reference data.

Future phases may add:

- in-memory float caching
- timestamp/date display
- stale-data warnings
- provider composition with Alpaca market data

Do not add caching yet unless explicitly approved.

## Testing Requirements

Add tests for:

- FMP settings repr does not expose API key.
- FMP request repr does not expose API key.
- API key remains accessible in request params for future execution.
- Shares-float request path is correct.
- Symbol is trimmed and uppercased.
- Empty symbol is handled safely.
- Fixture parses float shares.
- Fixture parses outstanding shares when present.
- Fixture parses date when present.
- Parser handles list-style responses.
- Parser handles dict-style responses if useful.
- Parser handles missing symbol data safely.
- Parser handles missing float safely.
- Parser handles zero/negative float safely.
- Parser handles non-numeric float safely.
- Normalized float data does not fabricate missing values.
- Runtime provider factory remains unchanged unless explicitly needed.
- No API keys are required for tests.
- No network calls occur in tests.
- Existing CLI tests still pass.
- Existing scanner/scoring behavior remains unchanged.
- Full test suite passes.

## Documentation Requirements

Update README concisely:

- FMP float/reference skeleton exists for future phases.
- Runtime remains mock by default.
- Real FMP runtime integration is not active yet.
- FMP is planned for float/reference data, not intraday market movement.
- Future scanner-ready candidates will likely compose Alpaca market data with FMP float/reference data.
- Credentials should not be committed.
- Tests use fakes/fixtures only.

## Future Phase Direction

Recommended next phase after Phase 10B:

```text
Phase 10C — Compose Alpaca + FMP fixture data into scanner-ready StockCandidate objects.
```

Phase 10C should still be offline/fixture-based unless explicitly approved otherwise.
