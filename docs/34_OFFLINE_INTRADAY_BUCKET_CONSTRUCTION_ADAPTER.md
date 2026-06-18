# Phase 13F — Offline Intraday Bucket Construction Adapter

## Status
Planned. This document defines the next offline-only step for Market Sentry’s time-of-day-normalized relative-volume (RVOL) pipeline.

## Goal
Create a pure, fixture-driven adapter that turns explicitly supplied intraday per-bar volumes into cumulative-volume values at a caller-supplied cutoff bucket, and optionally composes those values into Phase 13E `TimeOfDayRelativeVolumeInput` objects.

Expected flow:

```text
explicit fixture intraday per-bar volumes
→ validate series metadata, timestamps, order, and per-bar volume
→ include bars through caller-supplied cutoff timestamp
→ calculate cumulative volume at caller-supplied bucket
→ build Phase 13E-ready cumulative observations
→ Phase 13E calculates time-of-day-normalized RVOL
```

This phase is offline/testable only.

## Non-goals
Phase 13F must not:
- activate `live_composed`;
- modify runtime provider selection or the provider factory;
- make HTTP/network calls;
- fetch Alpaca/FMP data;
- add WebSockets, streaming, market calendars, or external dependencies;
- infer session timing, time zones, early closes, halts, or bucket labels;
- discover symbols or scan a broad market;
- calculate final time-of-day RVOL;
- add trading, order, brokerage, buy/sell, or execution behavior.

`live_composed` remains gated, reserved, and inactive.

## Important limitation
This adapter is not a trading-session/calendar engine.

A caller supplies:
- the symbol;
- session ID;
- bucket label;
- cutoff timestamp;
- intraday bars for one explicit session.

The adapter:
- does no timestamp parsing from strings;
- performs no time-zone conversion;
- performs no market-calendar validation;
- makes no assumption about regular hours, early close, or halt timing;
- does not derive or substitute a bucket.

It only sums validated bars with `timestamp <= cutoff_timestamp` using the caller-provided values.

## Input models

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

@dataclass(frozen=True)
class IntradayVolumeBar:
    timestamp: datetime
    volume: float | int

@dataclass(frozen=True)
class IntradayVolumeSeriesInput:
    symbol: str
    session_id: str
    bucket: str
    cutoff_timestamp: datetime
    bars: Sequence[IntradayVolumeBar]
```

## Result models

```python
@dataclass(frozen=True)
class CumulativeVolumeAtBucketResult:
    symbol: str
    session_id: str
    bucket: str
    cutoff_timestamp: datetime | None
    cumulative_volume: float | None
    status: str
    reason: str | None = None
    included_bar_count: int = 0
    total_bar_count: int = 0

@dataclass(frozen=True)
class TimeOfDayRelativeVolumeInputBuildResult:
    symbol: str
    bucket: str
    calculation_input: TimeOfDayRelativeVolumeInput | None
    current_result: CumulativeVolumeAtBucketResult
    historical_results: tuple[CumulativeVolumeAtBucketResult, ...]
    status: str
    reason: str | None = None
```

The optional build helper only constructs a Phase 13E input. It does not calculate final RVOL.

## Stable statuses/reasons
Use stable string constants or enum-like values. Suggested codes:

```text
OK
EMPTY_SYMBOL
EMPTY_BUCKET
INVALID_SESSION_ID
INVALID_CUTOFF_TIMESTAMP
NO_INTRADAY_BARS
INVALID_INTRADAY_TIMESTAMP
MISMATCHED_TIMESTAMP_TIMEZONE
DUPLICATE_INTRADAY_TIMESTAMP
OUT_OF_ORDER_INTRADAY_TIMESTAMP
INVALID_INTRADAY_VOLUME
NON_FINITE_INTRADAY_VOLUME
NON_POSITIVE_INTRADAY_VOLUME
NO_BARS_AT_OR_BEFORE_CUTOFF
NO_HISTORICAL_SERIES
MISMATCHED_HISTORICAL_SYMBOL
MISMATCHED_HISTORICAL_BUCKET
CURRENT_SESSION_IN_HISTORY
DUPLICATE_HISTORICAL_SESSION_ID
FAILED_CURRENT_SERIES
FAILED_HISTORICAL_SERIES
```

A smaller set is acceptable only when all behavior remains stable, inspectable, and tested.

## Validation and normalization rules

### Symbol, bucket, and session ID
- Symbol: trim and uppercase.
- Bucket: trim surrounding whitespace only; preserve the resulting label exactly.
- Session ID: require a non-empty trimmed `str`; preserve case after trimming.
- Empty normalized symbol fails with `EMPTY_SYMBOL`.
- Empty trimmed bucket fails with `EMPTY_BUCKET`.
- Blank, non-string, or missing session ID fails with `INVALID_SESSION_ID`.
- Session IDs are not parsed as dates, timestamps, or market sessions.

### Timestamps
- A cutoff timestamp must be a `datetime`, not a `date`, string, number, or boolean.
- Every bar timestamp must be a `datetime`, not a `date`, string, number, or boolean.
- No time-zone conversion is allowed.
- Every bar timestamp must have exactly the same `tzinfo` value as the cutoff timestamp, including `None` for all-naive values. Mismatch fails with `MISMATCHED_TIMESTAMP_TIMEZONE`.
- Bar timestamps must be strictly increasing in the caller-provided order.
- Equal adjacent timestamps fail with `DUPLICATE_INTRADAY_TIMESTAMP`.
- Decreasing timestamps fail with `OUT_OF_ORDER_INTRADAY_TIMESTAMP`.
- All bars are validated, including bars after cutoff.

### Per-bar volume
Each per-bar volume must be:
- numeric;
- finite;
- positive;
- non-boolean.

Reject missing, boolean, non-numeric, zero, negative, NaN, and infinity.

Any invalid bar invalidates the whole series. Do not discard a bad bar and sum the rest.

### Cutoff selection
- Include only bars whose `timestamp <= cutoff_timestamp`.
- Bars after cutoff are valid inputs but are not included in the cumulative sum.
- If no valid bar is at or before cutoff, fail with `NO_BARS_AT_OR_BEFORE_CUTOFF`.
- A usable cumulative result must be finite and positive.
- Do not substitute a nearby bucket, a daily average, zero, or a placeholder.

## Public functions

```python
def calculate_cumulative_volume_at_bucket(
    series: IntradayVolumeSeriesInput,
) -> CumulativeVolumeAtBucketResult: ...
```

```python
def calculate_cumulative_volume_at_bucket_results(
    series_inputs: Sequence[IntradayVolumeSeriesInput],
) -> list[CumulativeVolumeAtBucketResult]: ...
```

Optional helper:

```python
def build_time_of_day_relative_volume_input(
    current_series: IntradayVolumeSeriesInput,
    historical_series: Sequence[IntradayVolumeSeriesInput],
) -> TimeOfDayRelativeVolumeInputBuildResult: ...
```

## Phase 13E input-builder rules
The optional builder:
1. calculates a cumulative result for the current series;
2. calculates a cumulative result for every supplied historical series;
3. requires one or more historical series;
4. requires every historical series to have the same normalized symbol and exact trimmed bucket as the current series;
5. rejects a historical series whose trimmed session ID matches the current session ID;
6. rejects duplicate trimmed historical session IDs;
7. fails if the current series fails;
8. fails if any historical series fails; it must not quietly drop invalid historical series;
9. creates `HistoricalCumulativeVolumeObservation` entries from successful historical cumulative results;
10. builds `TimeOfDayRelativeVolumeInput` without calculating final RVOL.

The helper does not enforce Phase 13E’s 20-session minimum itself. Phase 13E remains responsible for final same-bucket historical-baseline validation and final RVOL calculation. This helper only builds structured inputs from validated series.

## Watchlist-only boundary
This phase does not fetch or discover symbols.

Future callers must supply explicit symbols, and any future live caller must remain limited to `MARKET_SENTRY_WATCHLIST`.

Not allowed:
- broad-market scanning;
- screener sweeps;
- exchange-wide crawling;
- all-shares discovery;
- external symbol discovery.

## Secret safety
This module handles no credentials.

Results and errors must not include:
- credential values;
- authorization headers;
- raw request representations;
- API URLs with secret query values;
- provider secrets.

## Test requirements
Tests must cover:
- valid cumulative sum using bars at or before the cutoff;
- valid exclusion of bars after cutoff;
- symbol normalization, bucket trimming, and session-ID trimming;
- empty symbol, empty bucket, and invalid session-ID failures;
- invalid cutoff timestamp;
- valid `datetime` and rejection of date/non-datetime timestamp values;
- matching naive timestamps and matching aware timestamps;
- mismatch in timestamp `tzinfo`;
- duplicate and out-of-order bar timestamps;
- empty bars and no bars at/before cutoff;
- invalid, zero, negative, NaN, infinity, and boolean per-bar volume;
- a single invalid bar invalidates the entire series;
- batch result order;
- builder creates Phase 13E input with current cumulative volume and historical observations;
- builder rejects no history, failed current history, failed historical series, symbol mismatch, bucket mismatch, current session appearing in history, and duplicate historical session IDs;
- builder does not calculate final time-of-day RVOL;
- no HTTP/network calls;
- no credentials, provider-factory activation, or trading/order hooks;
- default mock runtime works;
- fixture and composed_fixture work offline;
- Alpaca remains placeholder;
- `live_composed` remains gated/reserved inactive;
- full suite passes.

## README
Keep any README update brief:
- Phase 13F adds an offline intraday bucket-construction adapter.
- It sums only caller-supplied validated bars through a caller-supplied cutoff.
- It does not fetch data, infer a calendar/session/time zone, or activate live mode.
- It builds Phase 13E inputs but does not calculate final RVOL.
- Missing/invalid input is never fabricated.
- `live_composed` remains reserved/inactive.
- Trading/order functionality remains out of scope.
