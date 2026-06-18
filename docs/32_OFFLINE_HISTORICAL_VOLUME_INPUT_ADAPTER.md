# Phase 13D — Offline Historical-Volume Input Adapter

## Status
Planned.

## Purpose
Build a pure, fixture-driven adapter that turns explicitly supplied **completed historical daily-volume bars** into validated historical average-volume baselines for the Phase 13C RVOL calculator.

This phase supplies the historical denominator only:

```text
explicit completed historical daily-volume bars
→ validate bars and lookback sufficiency
→ calculate historical average daily volume
→ construct Phase 13C calculation inputs
→ Phase 13C calculates RVOL from supplied current volume / average historical volume
```

It does not fetch bars, discover symbols, activate `live_composed`, or make any network request.

## Project Boundary
Market Sentry is a personal-use low-float momentum scanner with local voice alerts. It is not a trading bot.

Never add:

- order placement
- order execution
- brokerage trading API calls
- buy/sell/enter/exit recommendations
- trading advice behavior

## Phase 13D Goal
Create an offline/testable historical-volume adapter that:

1. accepts explicit fixture-style historical daily-volume bars for explicit symbols;
2. validates symbols, bar dates, volumes, duplicates, and lookback sufficiency;
3. calculates a finite, positive arithmetic historical average volume;
4. exposes inspectable success/failure results with stable reason codes; and
5. can build `RelativeVolumeCalculationInput` values for the existing Phase 13C calculator from explicit current-volume values.

The adapter must not fabricate averages or RVOL values.

## Important Limitation
This phase produces a **simple completed-daily-volume average**. It is not time-of-day normalized.

Current intraday volume divided by a full-day historical average can be useful for an offline calculation skeleton, but it is not enough by itself to approve production live intraday RVOL. A later phase must explicitly choose and test any time-aligned/intraday cumulative-volume baseline before live activation can be reconsidered.

Accordingly, Phase 13D must not unblock `live_composed` activation.

## Non-Goals
Phase 13D must not add:

- live runtime activation
- provider factory activation for live data
- real HTTP calls
- Alpaca/FMP runtime wiring
- historical-bar fetching
- real RVOL provider runtime wiring
- real RVOL fetching
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

## Expected Runtime Behavior After Phase 13D
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

- `src/market_sentry/data/historical_volume_adapter.py`
- `tests/test_historical_volume_adapter.py`
- `README.md`, only for a brief roadmap/status note if useful

Do not modify runtime code unless absolutely necessary.

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
- `relative_volume_calculator.py`
- scanner filters/scoring/tiers
- alerts/voice/cooldowns
- mock/fixture/composed fixture data

## Input Contract
The adapter should use explicit daily-bar inputs. Exact names can vary, but responsibilities must remain clear.

Suggested structures:

```python
from dataclasses import dataclass
from datetime import date
from typing import Sequence

@dataclass(frozen=True)
class HistoricalDailyVolumeBar:
    session_date: date
    volume: float | int

@dataclass(frozen=True)
class HistoricalVolumeSeriesInput:
    symbol: str
    bars: Sequence[HistoricalDailyVolumeBar]
```

The symbol belongs to the series, not each bar, to avoid mismatched-symbol ambiguity.

### Caller Contract
- Bars must represent prior, completed daily sessions only.
- The current session’s cumulative volume must **not** be inserted into the historical baseline.
- Bars should be unique by `session_date` and may arrive in either ascending or descending date order.
- The adapter may sort bars deterministically by date before averaging.
- This phase does not fetch or validate a market calendar. It validates only the supplied, offline input contract.

## Historical Average Rules
The default minimum lookback should be explicit and stable:

```text
DEFAULT_MINIMUM_HISTORICAL_DAYS = 20
```

The adapter should allow a caller/test to supply a different positive minimum for controlled fixtures.

A successful historical average must be:

- associated with a normalized non-empty symbol;
- based on at least the required number of supplied daily bars;
- based only on positive, finite, numeric daily-volume values;
- the arithmetic mean of the supplied valid completed daily bars;
- finite and positive.

The adapter must not:

- replace missing bars with defaults;
- fill incomplete lookback windows;
- treat zero as a valid historical daily volume;
- silently discard invalid bars and average the remainder;
- use the current session’s cumulative volume as a historical bar;
- manufacture an average from unrelated values.

For this skeleton, any invalid bar should make that series invalid. This preserves an inspectable, conservative data contract rather than silently changing the denominator.

## Suggested Result Structures
Exact names can vary. Results must be inspectable and failure-aware.

```python
@dataclass(frozen=True)
class HistoricalAverageVolumeResult:
    symbol: str
    historical_average_volume: float | None
    status: str
    reason: str | None = None
    bar_count: int = 0
```

Optional batch-composition result:

```python
@dataclass(frozen=True)
class RelativeVolumeInputBuildResult:
    symbol: str
    calculation_input: RelativeVolumeCalculationInput | None
    historical_result: HistoricalAverageVolumeResult
    reason: str | None = None
```

## Stable Status / Reason Codes
Use stable string constants or enums. Suggested values:

```text
OK
EMPTY_SYMBOL
NO_HISTORICAL_BARS
INSUFFICIENT_HISTORICAL_BARS
INVALID_MINIMUM_HISTORICAL_DAYS
INVALID_SESSION_DATE
DUPLICATE_SESSION_DATE
INVALID_HISTORICAL_VOLUME
NON_FINITE_HISTORICAL_VOLUME
NON_POSITIVE_HISTORICAL_VOLUME
INVALID_HISTORICAL_AVERAGE_VOLUME
MISSING_CURRENT_VOLUME
```

It is acceptable to use a smaller set only if the behavior remains clear, stable, and covered by tests.

## Public Functions
Suggested public surface:

```python
def calculate_historical_average_volume(
    symbol: str,
    bars: Sequence[HistoricalDailyVolumeBar],
    *,
    minimum_historical_days: int = DEFAULT_MINIMUM_HISTORICAL_DAYS,
) -> HistoricalAverageVolumeResult: ...
```

```python
def calculate_historical_average_volume_results(
    inputs: Sequence[HistoricalVolumeSeriesInput],
    *,
    minimum_historical_days: int = DEFAULT_MINIMUM_HISTORICAL_DAYS,
) -> list[HistoricalAverageVolumeResult]: ...
```

```python
def calculate_historical_average_volumes(
    inputs: Sequence[HistoricalVolumeSeriesInput],
    *,
    minimum_historical_days: int = DEFAULT_MINIMUM_HISTORICAL_DAYS,
) -> dict[str, float]: ...
```

To feed Phase 13C without changing its implementation, add one explicit adapter helper if it remains small and pure:

```python
def build_relative_volume_calculation_inputs(
    current_volume_by_symbol: Mapping[str, float | int],
    historical_inputs: Sequence[HistoricalVolumeSeriesInput],
    *,
    minimum_historical_days: int = DEFAULT_MINIMUM_HISTORICAL_DAYS,
) -> list[RelativeVolumeInputBuildResult]: ...
```

This helper should:

1. normalize symbols consistently;
2. use only successful historical-average results;
3. require an explicit current volume for the same normalized symbol;
4. build `RelativeVolumeCalculationInput` without calculating RVOL itself; and
5. preserve inspectable failures for missing current volume or failed history.

Phase 13C’s calculator remains the sole source of the final division and final RVOL validation.

## Symbol and Duplicate Behavior
Symbols should be stripped and uppercased.

- Empty normalized symbols return `EMPTY_SYMBOL`.
- Batch result lists preserve original input order.
- Usable average mappings use normalized symbols only.
- For duplicate normalized series, use one deterministic rule and test it explicitly.

Preferred rule:

```text
last successful series wins in the usable mapping;
invalid duplicate series do not erase a prior successful mapping value;
all individual results remain available in original input order.
```

For `build_relative_volume_calculation_inputs`, duplicate current-volume mapping keys should normalize deterministically using the mapping’s final provided normalized value. Missing or invalid current volume should remain an inspectable build failure, not an invented value.

## Invalid Input Behavior
Invalid historical inputs include:

- missing/empty symbol;
- no bars;
- insufficient bars for configured minimum;
- invalid minimum lookback (including boolean, non-numeric, zero, or negative);
- invalid/missing session date;
- duplicate session date;
- boolean volume;
- non-numeric volume;
- NaN volume;
- infinite volume;
- zero volume;
- negative volume;
- non-finite or non-positive calculated average.

For a single series:

- return an inspectable failed result;
- set `historical_average_volume=None`;
- do not calculate a fallback average.

For a batch mapping:

- omit invalid symbols;
- do not fabricate a baseline;
- return an empty mapping if every series is invalid.

## Watchlist-Only Boundary
This phase does not fetch or discover symbols.

Future callers must supply explicit symbols. Future live usage must remain limited to symbols explicitly listed in `MARKET_SENTRY_WATCHLIST`.

This module must not perform:

- broad-market scanning;
- external symbol discovery;
- screener sweep;
- exchange-wide crawling;
- all-shares discovery.

## Secret Safety
This phase must not handle credentials at all.

Results and errors must not include:

- credentials;
- authorization headers;
- raw request representations;
- API URLs containing secret query values;
- provider secrets.

## Testing Requirements
Add tests for:

- valid arithmetic average from explicit bars;
- bars accepted in different date orders with deterministic average;
- normalized symbols;
- empty symbol failure;
- no-bars failure;
- minimum-lookback validation;
- insufficient lookback failure;
- valid 20-bar default lookback;
- configurable smaller fixture lookback;
- invalid session date rejection;
- duplicate session-date rejection;
- missing/invalid historical volume rejection;
- zero/negative historical volume rejection;
- NaN/infinity rejection;
- boolean volume rejection;
- invalid series does not silently average remaining bars;
- batch results preserve input order;
- usable average mapping includes successes only;
- all-invalid batch returns empty mapping;
- duplicate-series mapping behavior is deterministic;
- build helper creates Phase 13C inputs only when both history and current volume are explicit/usable;
- build helper preserves failures for failed historical baseline or missing current volume;
- the adapter itself does not calculate final RVOL if using the build helper;
- no HTTP/network calls;
- no credentials required;
- no external HTTP dependency;
- no provider factory activation;
- runtime default remains mock;
- fixture provider still works offline;
- composed_fixture provider still works offline;
- Alpaca remains placeholder;
- `live_composed` remains gated placeholder;
- full test suite passes.

## Documentation Requirements
If README is updated, keep it brief:

- Phase 13D adds an offline historical-volume input adapter.
- Historical average volume uses explicit supplied completed daily bars only.
- The adapter does not fetch data or activate live mode.
- It does not time-normalize intraday RVOL and therefore does not unblock production live activation.
- Missing/invalid history is not fabricated.
- `live_composed` remains reserved/inactive.
- Trading/order functionality remains out of scope.

## Acceptance Criteria
Phase 13D is complete only when:

1. historical averages are pure, deterministic, and derived only from supplied valid completed daily bars;
2. insufficient, malformed, duplicate-date, non-finite, zero, negative, and boolean inputs fail inspectably;
3. batch behavior and duplicate handling are deterministic and tested;
4. Phase 13C inputs can be built only from explicit current volume plus successful baseline history, without duplicating Phase 13C’s final RVOL calculation;
5. no runtime/provider/fetcher/network activation is added; and
6. existing offline runtime modes and test suite remain green.
