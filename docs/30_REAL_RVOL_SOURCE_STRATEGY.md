# Phase 13B - Real Relative Volume Source Strategy

Phase 13B is a strategy/data-contract phase only. It defines how Market Sentry should obtain real relative-volume data in a future phase without fabricating RVOL, broad scanning, or activating `live_composed`.

This phase does not implement an RVOL source, live provider activation, provider factory activation, real HTTP calls, real Alpaca/FMP runtime wiring, external dependencies, or trading/order behavior.

Market Sentry is a personal-use low-float momentum scanner with local voice alerts. It is not a trading bot. Trading/order functionality is never in scope.

## Current Context

Market Sentry already has:

- a live provider config gate
- a gated and reserved `live_composed` placeholder path
- a live composed provider skeleton
- a dry live-provider builder
- a relative-volume provider interface
- live-readiness diagnostics
- CLI live-readiness preflight
- a live composed activation plan

Phase 13A intentionally keeps real `live_composed` activation blocked until a real explicit RVOL source exists. Phase 13B defines that future RVOL strategy and keeps runtime behavior unchanged.

## Chosen RVOL Strategy

Use this strategy for future work:

```text
Primary future strategy:
calculate RVOL from watchlist-only historical volume data.

Initial implementation target:
offline/testable RVOL calculation skeleton before any live activation.

Static/local RVOL:
allowed only for controlled tests, not production live activation.

Provider-supplied RVOL:
deferred until endpoint semantics are documented and approved.
```

The first future implementation should be an offline/testable calculation skeleton. Live runtime activation remains blocked until that skeleton and its inputs are approved for live use.

## RVOL Must Not Be Fabricated

RVOL is a scanner input used for qualification, scoring, tiers, alerts, and future voice output. Fabricating it would make scanner output misleading.

RVOL must not be fabricated.

RVOL must not be inferred from unrelated data.

RVOL must not be:

- fabricated
- inferred from unrelated data
- silently defaulted to `1`
- silently defaulted to `0`
- silently defaulted to any placeholder
- copied from stale or undocumented inputs without a status/reason

Missing RVOL source blocks real live activation. Missing RVOL for a specific symbol should skip that symbol once a real source exists. If all symbols have missing or invalid RVOL, the provider should produce a clear, secret-safe no-candidates/error state.

## RVOL Options Compared

### Option A - Calculate RVOL From Historical Average Volume Bars

Calculate RVOL from current volume divided by a documented historical average volume.

Simple daily formula:

```text
relative_volume = current_day_volume / average_daily_volume_over_lookback
```

Future intraday-aware formula:

```text
relative_volume = current_intraday_volume / average_intraday_volume_for_same_time_window
```

Advantages:

- transparent and auditable
- works from documented inputs
- can be tested with fixture bars
- keeps provider semantics under Market Sentry control
- supports watchlist-only requests

Risks:

- requires historical volume data
- lookback window must be defined
- half days, holidays, and missing bars can distort averages
- intraday-aware RVOL is more accurate but more complex

Decision: This is the primary future strategy. Start with an offline/testable calculation skeleton before any live activation.

### Option B - Pull RVOL From A Provider Endpoint

Use provider-supplied RVOL only if a provider endpoint exposes a clear, documented relative-volume field.

Advantages:

- simpler if semantics are reliable
- may avoid local formula choices

Risks:

- endpoint semantics may be unclear
- field may be unavailable, paid, stale, or provider-specific
- may not support watchlist-only behavior cleanly
- harder to audit than local calculation

Decision: Deferred until endpoint semantics, freshness, watchlist-only behavior, and tests are documented and approved.

### Option C - Use Static/Local RVOL For Controlled Testing

Use explicit static/local RVOL mappings only for controlled tests and offline harnesses.

Advantages:

- deterministic and testable
- already compatible with the current `RelativeVolumeProvider` boundary
- useful for testing composed-provider wiring

Risks:

- not real live RVOL
- can mislead if treated as production data

Decision: Allowed only for controlled tests, fixtures, and local harnesses. Static/local RVOL is not production live activation.

## Future RVOL Data Contract

Keep the existing public provider boundary:

```python
class RelativeVolumeProvider(Protocol):
    def get_relative_volumes(self, symbols: Sequence[str]) -> dict[str, float]: ...
```

Future internal models may be added to make calculation and failures inspectable:

```python
@dataclass(frozen=True)
class RelativeVolumeCalculationInput:
    symbol: str
    current_volume: int
    historical_average_volume: float
    lookback_days: int
```

```python
@dataclass(frozen=True)
class RelativeVolumeResult:
    symbol: str
    relative_volume: float | None
    status: str
    reason: str | None = None
```

Exact model names can vary, but future RVOL data must remain:

- symbol-normalized
- explicit
- positive numeric only when valid
- finite
- inspectable
- failure-aware
- secret-safe

Potential stable reason codes:

- `NO_RVOL_SOURCE_CONFIGURED`
- `RVOL_SYMBOL_MISSING`
- `CURRENT_VOLUME_INVALID`
- `HISTORICAL_VOLUME_MISSING`
- `HISTORICAL_AVERAGE_INVALID`
- `LOOKBACK_INSUFFICIENT`
- `RVOL_PROVIDER_FAILURE`
- `RVOL_NON_NUMERIC`
- `RVOL_NOT_FINITE`
- `RVOL_NOT_POSITIVE`
- `ALL_RVOL_RESULTS_INVALID`
- `PARTIAL_RVOL_RESULTS_INVALID`

## Valid RVOL Rules

Valid RVOL must be:

- explicit
- numeric
- finite
- positive
- associated with a normalized symbol
- derived from documented historical/current volume inputs or supplied by an approved provider endpoint

Valid RVOL examples:

- `2.0` for two times normal volume
- `5.4` for five point four times normal volume

## Invalid RVOL Rules

Invalid RVOL includes:

- missing value
- zero
- negative value
- NaN
- infinity
- non-numeric value
- fabricated default
- inferred placeholder
- default `1`
- default `0`
- undocumented provider value
- value associated with an unnormalized or unknown symbol

Invalid values should not become `StockCandidate.relative_volume`. They should create failure-aware status/reason data and skip affected symbols once a real source exists.

## Missing RVOL Behavior

Future live behavior should be:

- No RVOL source configured: block real live activation.
- RVOL source configured but a symbol is missing: skip that symbol with `RVOL_SYMBOL_MISSING`.
- Current volume invalid: skip that symbol with `CURRENT_VOLUME_INVALID`.
- Historical volume data missing: skip that symbol with `HISTORICAL_VOLUME_MISSING`.
- Historical average volume invalid: skip that symbol with `HISTORICAL_AVERAGE_INVALID`.
- Insufficient lookback data: skip that symbol with `LOOKBACK_INSUFFICIENT`.
- Provider failure: report `RVOL_PROVIDER_FAILURE` without exposing secrets.
- Partial invalid RVOL: continue with valid symbols and report skipped symbols/reasons.
- All invalid RVOL: return a clear secret-safe no-candidates/error state.

Missing or invalid RVOL must not be repaired with placeholders.

## Watchlist-Only RVOL Boundary

All future RVOL fetching and calculation must be watchlist-only.

Allowed:

- request data only for symbols from `MARKET_SENTRY_WATCHLIST`
- calculate RVOL only for symbols from `MARKET_SENTRY_WATCHLIST`
- use fixture/static mappings for tests
- normalize requested symbols before lookup/calculation

Not allowed:

- broad-market scanning
- exchange-wide crawling
- all-shares float discovery
- screener endpoint sweep
- symbol discovery from external APIs
- RVOL calculation for symbols not explicitly requested by the watchlist

The RVOL source must not expand the symbol universe.

## Future RVOL Failure Modes

Future implementation must define stable, inspectable, secret-safe failures for:

- no RVOL source configured
- missing symbol from RVOL source
- invalid current volume
- missing historical volume data
- invalid historical average volume
- insufficient lookback data
- provider timeout/status/network failure
- non-numeric RVOL
- NaN or infinite RVOL
- zero/negative RVOL
- all RVOL results invalid
- partial RVOL results invalid

Failure messages must not expose credentials, authorization headers, raw request reprs, provider secrets, or API URLs containing secret query values.

## Future Test Requirements Before Live Activation

Before any live activation is approved, tests should prove:

- Phase 13B itself added no live activation.
- RVOL is never fabricated.
- Historical-volume calculation is the primary future path.
- Static/local RVOL is testing-only.
- Provider-supplied RVOL remains deferred until endpoint semantics are approved.
- RVOL fetching/calculation is watchlist-only.
- Missing RVOL source blocks live activation.
- Missing RVOL for a symbol skips that symbol.
- Invalid RVOL values are rejected.
- All invalid RVOL creates a clear no-candidates/error state.
- The public `RelativeVolumeProvider` contract remains usable.
- Internal result/status models are inspectable and secret-safe if added.
- Tests do not require API keys or internet access.
- No broad scanning or external symbol discovery occurs.
- No provider factory activation occurs accidentally.
- No trading/order behavior appears.

## Why Phase 13B Does Not Activate Live Mode

Phase 13B is intentionally docs/spec only because RVOL is still a blocker for live scanner-ready candidates. Activating live mode before RVOL is real, explicit, validated, and watchlist-only would make scanner results unreliable.

This phase does not add:

- live runtime activation
- provider factory activation for live data
- real HTTP calls
- real Alpaca/FMP fetcher runtime wiring
- real RVOL fetching
- external HTTP dependencies
- broad-market scanning
- WebSockets or streaming data
- SEC/news/halt/split ingestion
- dashboard UI
- persistent database storage
- order APIs
- order placement
- trade execution
- trading advice behavior

## Acceptance Criteria

Phase 13B is complete when:

1. The primary RVOL strategy is documented as historical-volume calculation.
2. Static/local RVOL is limited to controlled tests.
3. Provider-supplied RVOL is deferred.
4. Valid and invalid RVOL rules are documented.
5. Missing RVOL behavior is documented.
6. Watchlist-only RVOL boundaries are documented.
7. Future RVOL failure modes are documented.
8. Secret-safety boundaries are documented.
9. No runtime code activates live behavior.
10. No provider factory activation is added.
11. No real RVOL fetching is added.
12. No network behavior is added.
13. No trading/order behavior is added.
