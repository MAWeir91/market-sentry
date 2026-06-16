# Phase 10C — Compose Alpaca + FMP Fixtures into Scanner-Ready Candidates

## Status

Planned.

## Purpose

Phase 10C proves that future live market data can be normalized into the existing scanner model without enabling live HTTP calls, requiring API keys, changing runtime provider behavior, or adding trading functionality.

The goal is to compose fixture-shaped market data from Alpaca with fixture-shaped float/reference data from FMP into `StockCandidate` objects that the existing `ScannerEngine` can evaluate.

This phase is still offline and test-driven.

## Boundary

Market Sentry is a personal-use low-float momentum scanner with local voice alerts.

Market Sentry is not a trading bot.

Trading/order functionality is never in scope.

Do not add:

- live HTTP calls
- required API keys
- runtime activation of Alpaca
- runtime activation of FMP
- broad-market scanning
- WebSockets
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

## Existing Pieces

Phase 10A added an offline Alpaca market-data skeleton for:

- settings
- auth header shaping
- snapshot request shaping
- bars request shaping
- snapshot fixture parsing
- daily gain calculation
- 15-minute change calculation

Phase 10B added an offline FMP float/reference skeleton for:

- settings
- shares-float request shaping
- float fixture parsing
- outstanding shares parsing
- reference date parsing
- float normalization
- low-float reference checks

Phase 10C should connect these shapes into scanner-ready candidates.

## Target Data Flow

```text
Alpaca snapshot fixture + Alpaca bars fixture + FMP float fixture
        ↓
normalized market/reference data
        ↓
StockCandidate
        ↓
ScannerEngine
        ↓
ScanResult / alerts / report
```

## Important Data Responsibilities

### Alpaca skeleton supplies market movement context

Alpaca fixture data may provide:

- symbol
- latest price
- daily volume
- high of day
- previous close
- daily gain percentage
- 15-minute change percentage

### FMP skeleton supplies float/reference context

FMP fixture data may provide:

- symbol
- float shares
- outstanding shares
- reference date

### Composition supplies scanner-ready fields

The composition layer should produce `StockCandidate` with:

- symbol
- price
- float_shares
- daily_gain_pct
- relative_volume
- daily_volume
- high_of_day
- change_15m_pct

## Relative Volume Boundary

Relative volume is required by the existing scanner model and qualification rules.

Alpaca snapshots alone do not necessarily provide relative volume.

For Phase 10C, use an explicit fixture-supplied relative volume value, a small mapping, or a clearly named composition input such as `relative_volume_by_symbol`.

Do not invent relative volume silently.

If relative volume is missing for a symbol, that symbol should not produce a scanner-ready candidate, or the composer should return a clear skip/rejection reason depending on the implementation approach.

## Symbol Matching

Symbol matching should be safe and deterministic:

- normalize symbols to uppercase
- trim whitespace
- match Alpaca and FMP data by symbol
- handle missing Alpaca data safely
- handle missing FMP float data safely
- handle mismatched symbols safely
- do not fabricate missing data

## Suggested Structures

Possible module:

```text
src/market_sentry/data/composer.py
```

Possible structures:

```text
CandidateCompositionError
CandidateCompositionResult
CandidateSkipReason
compose_stock_candidate(...)
compose_stock_candidates(...)
```

A simple implementation is acceptable. Avoid premature abstraction.

One good shape would be:

```text
compose_stock_candidate(
    symbol,
    snapshot,
    float_data,
    relative_volume,
    bars=None,
) -> StockCandidate | None
```

Another acceptable shape is a small result object that contains:

- candidate
- skipped symbol
- reason

Prefer whichever is easier to test and maintain.

## Required Composition Rules

A candidate should only be produced when required scanner fields are valid:

- symbol present
- price positive
- float_shares positive
- daily_gain_pct available
- relative_volume available and positive
- daily_volume positive

Optional fields should be included when available:

- high_of_day
- change_15m_pct

Missing optional fields should not crash composition.

Invalid required data should not crash composition.

The composer should skip invalid candidates or return a structured skipped result.

## Runtime Behavior

Runtime should remain unchanged after Phase 10C.

Expected behavior:

- `python -m market_sentry` still uses mock data.
- `MARKET_SENTRY_PROVIDER=mock` still works.
- `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as a placeholder.
- FMP is not active at runtime.
- Alpaca is not active at runtime.
- Loop mode remains unchanged.
- Voice mode remains unchanged.
- Scanner qualification rules remain unchanged.
- Scoring remains unchanged.

## Testing Requirements

Add tests for:

- composing a valid `StockCandidate` from Alpaca snapshot + FMP float + relative volume fixture
- symbol normalization during composition
- high_of_day is carried into the candidate
- change_15m_pct is carried into the candidate
- daily_gain_pct is calculated from Alpaca snapshot fixture data if not already normalized
- daily_volume is carried from Alpaca snapshot fixture data
- float_shares is carried from FMP fixture data
- relative_volume must be explicit and is not silently fabricated
- missing relative_volume is handled safely
- missing FMP float data is handled safely
- missing Alpaca snapshot data is handled safely
- invalid price is handled safely
- invalid float is handled safely
- invalid daily volume is handled safely
- mismatched symbols are handled safely
- multiple symbols can be composed, with invalid symbols skipped safely
- composed candidates can be scanned by `ScannerEngine`
- composed qualified candidate includes Phase 7 optional metrics in scoring/report behavior if appropriate
- tests do not require API keys
- tests do not use real network calls
- existing CLI tests still pass
- existing scanner/scoring behavior remains unchanged
- full test suite passes

## Documentation Requirements

Update README concisely to mention:

- fixture-based candidate composition exists for future live-provider work
- runtime remains mock by default
- Alpaca and FMP are not active runtime providers yet
- composition currently uses offline fixtures/tests only
- future live scanner-ready candidates will likely require Alpaca market data plus FMP float/reference data
- credentials should not be committed

## Out of Scope

Do not add:

- live HTTP clients
- provider transport classes
- runtime provider activation
- CLI provider flags
- broad-market scanning
- caching
- database storage
- dashboards
- news/catalyst ingestion
- SEC filing ingestion
- halt/resume ingestion
- split ingestion
- WebSockets
- order/trade functionality

## Recommended Next Phase

After Phase 10C, the next likely phase is one of:

### Phase 10D — Controlled live HTTP transport behind explicit tests/fakes

Add a minimal HTTP transport layer, but still keep runtime safe and require explicit configuration.

### Phase 10D Alternative — Fixture-backed live-provider simulation

Create a complete provider implementation that uses fixture files as if they were live responses. This would allow end-to-end runtime testing without network access.

The safer recommendation is the fixture-backed provider simulation before live HTTP.
