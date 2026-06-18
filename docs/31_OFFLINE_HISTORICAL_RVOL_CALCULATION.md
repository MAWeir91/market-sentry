# Phase 13C — Offline Historical RVOL Calculation Skeleton

## Status
Planned.

## Purpose
Create an offline, pure relative-volume calculation module that can compute RVOL from explicitly supplied inputs:

- current volume
- historical average volume
- normalized symbol

This phase builds only the calculation core. It does not fetch historical bars, call APIs, activate `live_composed`, or wire runtime provider behavior.

## Project Boundary
Market Sentry is a personal-use low-float momentum stock scanner with local voice alerts. It is not a trading bot.

Never add:

- order placement
- order execution
- brokerage trading API calls
- buy/sell/enter/exit recommendations
- trading advice behavior

## Phase 13C Goal
Build a pure, offline/testable RVOL calculation skeleton that follows the Phase 13B strategy:

```text
RVOL = current volume / historical average volume
```

The calculation must be deterministic, inspectable, and failure-aware.

## Non-Goals
Phase 13C must not add:

- live runtime activation
- provider factory activation for live data
- real HTTP calls
- historical-bar fetching
- Alpaca/FMP runtime wiring
- real RVOL provider runtime wiring
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

## Expected Runtime Behavior After Phase 13C
Unchanged.

When no preflight flag is used:

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

When `--live-readiness` is used:

1. The CLI prints diagnostics only.
2. The scanner report is not rendered.
3. Providers are not built.
4. The factory is not used to activate live data.
5. No network calls occur.

## Expected Files
Recommended files:

- `src/market_sentry/data/relative_volume_calculator.py`
- `tests/test_relative_volume_calculator.py`
- `README.md`, only for a brief roadmap/status note if useful

Optional only if useful:

- `docs/31_OFFLINE_HISTORICAL_RVOL_CALCULATION.md`

Avoid runtime-code modifications.

Do not modify unless absolutely necessary:

- `src/market_sentry/main.py`
- `src/market_sentry/data/factory.py`
- `src/market_sentry/live_readiness.py`
- `src/market_sentry/config.py`
- HTTP transport
- Alpaca/FMP fetchers
- live provider builder
- live composed provider
- existing relative-volume provider implementation
- scanner filters/scoring/tiers
- alerts/voice/cooldowns
- mock/fixture/composed fixture data

## Required Calculation Behavior
The core calculation should compute:

```text
relative_volume = current_volume / historical_average_volume
```

It must only return usable RVOL when:

- symbol is present after normalization
- current volume is numeric
- current volume is finite
- current volume is positive
- historical average volume is numeric
- historical average volume is finite
- historical average volume is positive
- calculated RVOL is finite and positive

It must not fabricate RVOL.

It must not default missing values to:

- `1`
- `0`
- `None` as a usable value
- any placeholder

## Suggested Data Models
Exact names can vary, but the implementation should be explicit and inspectable.

Suggested structures:

```python
@dataclass(frozen=True)
class RelativeVolumeCalculationInput:
    symbol: str
    current_volume: float | int
    historical_average_volume: float | int

@dataclass(frozen=True)
class RelativeVolumeResult:
    symbol: str
    relative_volume: float | None
    status: str
    reason: str | None = None
```

Suggested stable status/reason codes:

```text
OK
EMPTY_SYMBOL
INVALID_CURRENT_VOLUME
INVALID_HISTORICAL_AVERAGE_VOLUME
NON_POSITIVE_CURRENT_VOLUME
NON_POSITIVE_HISTORICAL_AVERAGE_VOLUME
NON_FINITE_CURRENT_VOLUME
NON_FINITE_HISTORICAL_AVERAGE_VOLUME
NON_FINITE_RELATIVE_VOLUME
```

The implementation may use enums or string constants, but tests should verify stable values.

## Suggested Functions
Suggested public functions:

```python
def calculate_relative_volume(symbol, current_volume, historical_average_volume) -> RelativeVolumeResult: ...

def calculate_relative_volumes(inputs: Sequence[RelativeVolumeCalculationInput]) -> dict[str, float]: ...

def calculate_relative_volume_results(inputs: Sequence[RelativeVolumeCalculationInput]) -> list[RelativeVolumeResult]: ...
```

Exact names can vary, but the module should support both:

- getting successful mapping results for use by existing `RelativeVolumeProvider` boundaries
- inspecting failures in tests/future diagnostics

## Symbol Normalization
Symbols should be:

- stripped
- uppercased
- empty symbols rejected with a stable failure reason

Duplicate symbols should be deterministic.

Preferred behavior:

- results list preserves input order
- success mapping uses normalized symbols
- if duplicate normalized symbols appear, the later valid value may override earlier mapping values, or the first valid value may win; choose one deterministic rule and test it clearly

## Valid RVOL Rules
Valid RVOL must be:

- explicit
- calculated from supplied inputs
- numeric
- finite
- positive
- associated with a normalized symbol

## Invalid RVOL Rules
Invalid inputs/results include:

- missing symbol
- empty symbol
- missing current volume
- missing historical average volume
- boolean current volume
- boolean historical average volume
- non-numeric current volume
- non-numeric historical average volume
- NaN current volume
- NaN historical average volume
- infinity current volume
- infinity historical average volume
- zero current volume
- zero historical average volume
- negative current volume
- negative historical average volume
- calculated NaN
- calculated infinity

## Missing RVOL Behavior
For a single calculation:

- return an inspectable failed result
- do not return a usable RVOL value

For batch mapping:

- omit invalid symbols from the returned usable mapping
- do not fabricate missing values

For all-invalid batches:

- return an empty mapping
- preserve inspectable failed results if using the result-list function

## Watchlist Boundary
This phase does not fetch or discover symbols.

Future users of this module must provide explicit symbols, and future live usage must remain limited to `MARKET_SENTRY_WATCHLIST`.

This module must not perform:

- broad-market scanning
- external symbol discovery
- screener sweep
- exchange-wide crawling
- all-shares discovery

## Secret Safety
This phase should not handle credentials at all.

Errors/results must not expose:

- credentials
- headers
- request reprs
- API URLs with secret query values
- provider secrets

## Testing Requirements
Add tests for:

- valid RVOL calculation
- symbol normalization
- empty symbol failure
- missing/invalid current volume
- missing/invalid historical average volume
- zero/negative current volume
- zero/negative historical average volume
- NaN/infinity rejection
- booleans rejected even though Python treats bool as int subclass
- batch mapping returns only successful values
- all-invalid batch returns empty mapping
- duplicate symbol behavior is deterministic
- results expose stable status/reason codes
- no HTTP/network calls
- no credentials required
- no external HTTP dependency added
- no provider factory activation added
- runtime default remains mock
- fixture provider still works offline
- composed_fixture provider still works offline
- alpaca remains placeholder
- live_composed remains gated placeholder
- full test suite passes

## Documentation Requirements
If README is updated, keep it brief:

- Phase 13C adds an offline RVOL calculation skeleton.
- RVOL is calculated only from supplied inputs.
- The module does not fetch data.
- The module does not activate live mode.
- Missing/invalid RVOL is not fabricated.
- Live composed remains reserved/inactive.
- Trading/order functionality remains out of scope.

## Acceptance Criteria
Phase 13C is complete when:

1. Offline RVOL calculation models/functions exist.
2. Valid RVOL calculations are deterministic and tested.
3. Invalid/missing inputs produce stable inspectable failures.
4. Batch usable mapping omits invalid symbols without fabrication.
5. No runtime behavior changes.
6. No provider factory activation is added.
7. No network behavior is added.
8. No real RVOL fetching is added.
9. No trading/order behavior is added.
10. Full test suite passes.
