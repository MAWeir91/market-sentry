# Phase 13E — Offline Time-of-Day-Normalized RVOL

## Purpose

Phase 13D produces a simple historical average from completed daily bars. That is useful for offline fixture work, but it is not sufficient for production-quality intraday relative volume because current-day volume accumulates over the trading session.

Phase 13E adds a pure, offline, fixture-driven time-of-day-normalized RVOL calculation layer.

The intended calculation is:

```text
current cumulative volume at a named session bucket
÷
historical average cumulative volume at that same session bucket
=
time-of-day-normalized relative volume
```

This phase must not fetch data, activate `live_composed`, or alter runtime provider behavior.

---

## Project Boundary

Market Sentry is a personal-use low-float momentum scanner with local voice alerts. It is **not** a trading bot.

Do not add:

- order execution or order placement;
- brokerage trading APIs;
- buy/sell/enter/exit recommendations;
- live runtime activation;
- provider-factory activation for live data;
- HTTP/network calls;
- historical-bar fetching;
- Alpaca/FMP runtime wiring;
- WebSockets or streaming;
- broad-market scanning;
- symbol discovery;
- external dependencies;
- persistent storage;
- dashboard UI.

---

## Non-Goals

Phase 13E does **not**:

1. Decide how historical intraday bars will be fetched.
2. Decide how exchange calendars, early closes, holidays, or halts are reconciled.
3. Build a production live intraday RVOL provider.
4. Enable `live_composed`.
5. Replace the existing Phase 13C or Phase 13D modules.

It builds only the calculation/validation core from inputs explicitly supplied by the caller.

---

## Terminology

### Session bucket

A stable label representing a comparable elapsed point in a market session, such as:

```text
09:45
10:00
10:30
11:00
13:00
15:30
```

For Phase 13E, the bucket is an opaque, normalized label. The module must not infer a calendar, time zone, session open, or market schedule.

### Current cumulative volume

The volume accumulated for a symbol from the relevant session start through the supplied session bucket.

### Historical cumulative volume

For each prior completed historical session, the volume accumulated from that session start through the **same** supplied session bucket.

### Historical cumulative baseline

The arithmetic mean of valid historical cumulative volumes at the same bucket.

---

## Calculation

```text
TOD_RVOL = current_cumulative_volume / historical_average_cumulative_volume_at_same_bucket
```

A result is usable only when:

- symbol is normalized and non-empty;
- bucket is normalized and non-empty;
- current cumulative volume is numeric, finite, and positive;
- the required number of historical cumulative-volume observations exists for that exact bucket;
- all historical observations are numeric, finite, and positive;
- the historical average is finite and positive;
- the final TOD_RVOL is finite and positive.

No RVOL, denominator, bucket, or observation may be fabricated.

---

## Expected Files

Create:

```text
src/market_sentry/data/time_of_day_rvol.py
tests/test_time_of_day_rvol.py
```

Update only if useful:

```text
README.md
```

Do not modify unless absolutely necessary:

```text
src/market_sentry/main.py
src/market_sentry/data/factory.py
src/market_sentry/live_readiness.py
src/market_sentry/config.py
HTTP transport
Alpaca/FMP fetchers
live provider builder
live composed provider
existing relative-volume provider implementation
src/market_sentry/data/relative_volume_calculator.py
src/market_sentry/data/historical_volume_adapter.py
scanner filters/scoring/tiers
alerts/voice/cooldowns
mock/fixture/composed fixture data
```

---

## Input Models

Use explicit fixture-style data. Exact class names can vary, but responsibilities must be clear.

Suggested structures:

```python
from dataclasses import dataclass
from typing import Sequence

@dataclass(frozen=True)
class HistoricalCumulativeVolumeObservation:
    session_id: str
    bucket: str
    cumulative_volume: float | int

@dataclass(frozen=True)
class TimeOfDayRelativeVolumeInput:
    symbol: str
    bucket: str
    current_cumulative_volume: float | int
    historical_observations: Sequence[HistoricalCumulativeVolumeObservation]
```

The input must contain observations for completed historical sessions only. Current-session volume must appear only as `current_cumulative_volume`, never as a historical observation.

### Bucket normalization

For Phase 13E, normalize a bucket by trimming surrounding whitespace. Preserve the caller's normalized label exactly after trimming; do not parse or convert the value to a timestamp.

A bucket that is missing or blank after trimming is invalid.

This permits fixture labels like `"10:00"`, `"10:00 ET"`, or an approved structured label in a later phase without adding hidden clock/calendar assumptions now.

### Session identifiers

`session_id` must be a non-empty normalized string after trimming. Duplicate `session_id` values in one input are invalid because each historical session may contribute only one observation per bucket.

The adapter does not validate that an ID represents a real date or trading session.

---

## Minimum Lookback

Use an explicit stable default:

```python
DEFAULT_MINIMUM_HISTORICAL_SESSIONS = 20
```

Allow a caller/test to supply a different positive minimum for controlled fixtures.

A minimum lookback is valid only if it is an integer-like non-boolean positive value. Reject booleans, non-numeric values, zero, and negatives.

Do not fill incomplete lookback windows, substitute other buckets, use daily totals, or silently discard invalid observations to reach the minimum.

---

## Result Model

Suggested structures:

```python
@dataclass(frozen=True)
class TimeOfDayRelativeVolumeResult:
    symbol: str
    bucket: str
    relative_volume: float | None
    historical_average_cumulative_volume: float | None
    status: str
    reason: str | None = None
    observation_count: int = 0
```

Optionally expose a separate baseline result if it makes the module easier to inspect. The final public result must still make the denominator and outcome inspectable.

---

## Stable Status / Reason Codes

Use stable string constants or an enum-like class. Suggested values:

```text
OK
EMPTY_SYMBOL
EMPTY_BUCKET
INVALID_MINIMUM_HISTORICAL_SESSIONS
INVALID_CURRENT_CUMULATIVE_VOLUME
NON_FINITE_CURRENT_CUMULATIVE_VOLUME
NON_POSITIVE_CURRENT_CUMULATIVE_VOLUME
NO_HISTORICAL_OBSERVATIONS
INSUFFICIENT_HISTORICAL_OBSERVATIONS
INVALID_HISTORICAL_SESSION_ID
DUPLICATE_HISTORICAL_SESSION_ID
MISMATCHED_HISTORICAL_BUCKET
INVALID_HISTORICAL_CUMULATIVE_VOLUME
NON_FINITE_HISTORICAL_CUMULATIVE_VOLUME
NON_POSITIVE_HISTORICAL_CUMULATIVE_VOLUME
INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME
NON_FINITE_TIME_OF_DAY_RVOL
```

A smaller set is acceptable only if each invalid state remains clear, stable, inspectable, and tested.

---

## Validation Rules

### Current cumulative volume

Reject:

- missing values;
- booleans;
- non-numeric values;
- NaN;
- infinity;
- zero;
- negatives.

### Historical observations

Every observation in an input must:

- have a non-empty session ID;
- have a bucket that matches the input bucket after trimming;
- have a numeric, finite, positive cumulative volume;
- have a unique normalized session ID within that input.

Conservative rule: **any invalid historical observation invalidates the entire input.** Do not omit bad observations and average the remainder.

### Historical average

The baseline is the arithmetic mean of the valid, supplied historical cumulative-volume observations at the exact bucket. It must be finite and positive.

---

## Public Functions

Suggested public surface:

```python
def calculate_time_of_day_relative_volume(
    symbol: str,
    bucket: str,
    current_cumulative_volume: float | int,
    historical_observations: Sequence[HistoricalCumulativeVolumeObservation],
    *,
    minimum_historical_sessions: int = DEFAULT_MINIMUM_HISTORICAL_SESSIONS,
) -> TimeOfDayRelativeVolumeResult: ...
```

```python
def calculate_time_of_day_relative_volume_results(
    inputs: Sequence[TimeOfDayRelativeVolumeInput],
    *,
    minimum_historical_sessions: int = DEFAULT_MINIMUM_HISTORICAL_SESSIONS,
) -> list[TimeOfDayRelativeVolumeResult]: ...
```

```python
def calculate_time_of_day_relative_volumes(
    inputs: Sequence[TimeOfDayRelativeVolumeInput],
    *,
    minimum_historical_sessions: int = DEFAULT_MINIMUM_HISTORICAL_SESSIONS,
) -> dict[str, float]: ...
```

The mapping function should include only successful values, keyed by normalized symbol.

### Duplicate input symbols

- Result-list function preserves every input result in original order.
- Mapping uses normalized symbol keys.
- Last successful duplicate normalized input wins.
- Invalid duplicate inputs do not erase a prior successful mapping value.

---

## Missing and Invalid Behavior

For one input:

- return an inspectable failed result;
- return no usable `relative_volume`;
- return no fallback denominator;
- do not substitute a daily average from Phase 13D;
- do not substitute a nearby bucket;
- do not default to 0 or 1.

For a batch mapping:

- omit invalid inputs;
- return an empty mapping when all inputs fail;
- retain inspectable results through the result-list function.

---

## Watchlist-Only Boundary

This module does not fetch, discover, or screen symbols.

Future live callers may calculate TOD RVOL only for symbols explicitly listed in `MARKET_SENTRY_WATCHLIST`.

Not allowed:

- broad-market scanning;
- exchange-wide crawling;
- screener sweeps;
- external symbol discovery;
- all-shares discovery.

---

## Secret Safety

This module handles no credentials and makes no requests.

Results and errors must not include:

- credentials;
- authorization headers;
- raw request representations;
- API URLs with secret query values;
- provider secrets.

---

## Tests Required

Add coverage for:

- valid TOD RVOL calculation from explicit fixture observations;
- arithmetic baseline calculation;
- bucket trimming and symbol normalization;
- blank symbol and blank bucket failures;
- default 20-session lookback;
- configurable smaller fixture lookback;
- invalid minimum lookback;
- no observations and insufficient observations;
- mismatched observation bucket;
- invalid/blank session ID;
- duplicate historical session ID;
- invalid historical cumulative volume;
- zero/negative historical volume;
- NaN/infinity rejection;
- boolean rejection;
- invalid historical observation invalidates the full input;
- invalid current cumulative volume;
- non-finite/non-positive final output handling;
- batch order and successful mapping only;
- all-invalid batch returns empty mapping;
- deterministic duplicate input symbol behavior;
- module contains no network/credential/provider-factory/trading hooks;
- default mock runtime still works;
- fixture and composed_fixture still work offline;
- alpaca remains placeholder;
- live_composed remains gated placeholder;
- full suite passes.

---

## README

Keep any README change brief:

- Phase 13E adds an offline time-of-day-normalized RVOL calculation skeleton.
- It uses explicitly supplied current cumulative volume and historical cumulative observations at the same bucket.
- It does not fetch market data or activate live mode.
- It does not handle market-calendar/session normalization.
- Missing or invalid input is not fabricated.
- `live_composed` remains reserved/inactive.
- Trading/order functionality remains out of scope.

---

## Completion Boundary

Phase 13E completes only when the pure calculation module and offline tests exist. `live_composed` remains gated/reserved/inactive after this phase.
