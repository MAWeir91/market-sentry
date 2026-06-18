# Phase 13G — Offline End-to-End Intraday RVOL Harness

## Status

Planned. This phase is **offline, fixture-driven, and non-runtime-active**.

## Goal

Compose the completed Phase 13F intraday bucket-construction adapter with the completed Phase 13E time-of-day-normalized RVOL calculator.

The harness accepts one caller-supplied current intraday series and caller-supplied historical intraday series for each explicitly named symbol. It should:

```text
current intraday fixture series
+ historical intraday fixture series
→ Phase 13F cumulative-volume-at-bucket construction
→ Phase 13E same-bucket historical cumulative baseline
→ time-of-day-normalized RVOL result
→ inspectable success / skipped-symbol results
```

The harness must not fetch data, discover symbols, instantiate providers, activate `live_composed`, or make any HTTP/network calls.

## Existing Modules to Reuse

- `market_sentry.data.intraday_bucket_adapter`
  - `IntradayVolumeSeriesInput`
  - `CumulativeVolumeAtBucketResult`
  - `TimeOfDayRelativeVolumeInputBuildResult`
  - `build_time_of_day_relative_volume_input(...)`
- `market_sentry.data.time_of_day_rvol`
  - `TimeOfDayRelativeVolumeInput`
  - `TimeOfDayRelativeVolumeResult`
  - `calculate_time_of_day_relative_volume(...)`
- `market_sentry.data.relative_volume`
  - Existing public `RelativeVolumeProvider` boundary remains unchanged.

## Non-Goals

Do not add:

- Live runtime activation.
- Provider-factory activation for `live_composed`.
- HTTP/network calls.
- Historical-bar fetching.
- Alpaca/FMP runtime wiring.
- WebSockets, streaming, polling changes, or external dependencies.
- Broad-market scanning, screener sweeps, exchange-wide crawling, or symbol discovery.
- Market-calendar, early-close, halt, session, or time-zone inference.
- Persistent storage, dashboards, or UI changes.
- Trading/order APIs, order placement, execution, or buy/sell/enter/exit guidance.

## Important Limitations

The harness remains only as production-ready as its caller-supplied fixtures.

It does **not**:

- derive intraday bars;
- select a cutoff time;
- assign bucket labels;
- validate an exchange calendar;
- normalize time zones;
- convert time zones;
- infer whether bars represent regular trading hours;
- use a daily-volume baseline;
- unblock `live_composed` activation.

All symbols, session IDs, bucket labels, cutoffs, and bars are explicit caller input. A caller must supply bars that obey the existing Phase 13F and 13E contracts.

## Expected Files

Create:

```text
src/market_sentry/data/intraday_rvol_harness.py
tests/test_intraday_rvol_harness.py
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
src/market_sentry/data/http_stdlib.py
src/market_sentry/data/alpaca_fetcher.py
src/market_sentry/data/fmp_fetcher.py
src/market_sentry/data/live_provider_builder.py
src/market_sentry/data/live_composed_provider.py
src/market_sentry/data/intraday_bucket_adapter.py
src/market_sentry/data/time_of_day_rvol.py
src/market_sentry/data/relative_volume.py
scanner filters/scoring/tiers
alerts/voice/cooldowns
mock/fixture/composed fixture providers
```

## Suggested Models

Exact names may vary, but results must be explicit and inspectable.

```python
from dataclasses import dataclass
from typing import Sequence

@dataclass(frozen=True)
class IntradayRelativeVolumeHarnessInput:
    current_series: IntradayVolumeSeriesInput
    historical_series: Sequence[IntradayVolumeSeriesInput]

@dataclass(frozen=True)
class IntradayRelativeVolumeHarnessResult:
    symbol: str
    bucket: str
    relative_volume: float | None
    status: str
    reason: str | None = None
    time_of_day_input: TimeOfDayRelativeVolumeInput | None = None
    input_build_result: TimeOfDayRelativeVolumeInputBuildResult | None = None
    time_of_day_result: TimeOfDayRelativeVolumeResult | None = None
```

## Stable Harness Status / Reason Codes

Keep Phase 13F and Phase 13E status codes intact. Add a small, stable harness-level status set, for example:

```text
OK
FAILED_INPUT_BUILD
FAILED_TIME_OF_DAY_RVOL
```

The harness may preserve the lower-level failure reason from the input builder or Phase 13E calculator. It must not replace an inspectable lower-level reason with a vague message.

Suggested behavior:

- Build failure → harness `status=FAILED_INPUT_BUILD`, `reason` is the builder reason/status.
- Calculation failure after successful input building → harness `status=FAILED_TIME_OF_DAY_RVOL`, `reason` is the Phase 13E reason/status.
- Full success → harness `status=OK`, `reason=None`, usable positive finite RVOL.

## Public Functions

Suggested public surface:

```python
def calculate_intraday_time_of_day_relative_volume(
    input: IntradayRelativeVolumeHarnessInput,
) -> IntradayRelativeVolumeHarnessResult: ...
```

```python
def calculate_intraday_time_of_day_relative_volume_results(
    inputs: Sequence[IntradayRelativeVolumeHarnessInput],
) -> list[IntradayRelativeVolumeHarnessResult]: ...
```

```python
def calculate_intraday_time_of_day_relative_volumes(
    inputs: Sequence[IntradayRelativeVolumeHarnessInput],
) -> dict[str, float]: ...
```

Exact names can vary. The module must support both:

1. an ordered result list that preserves successes and failures; and
2. a usable normalized-symbol-to-RVOL mapping containing only successful results.

## Required Harness Behavior

For a single harness input:

1. Call the existing Phase 13F `build_time_of_day_relative_volume_input(...)` helper.
2. Preserve the returned `TimeOfDayRelativeVolumeInputBuildResult` in the harness result.
3. If input building fails, return an inspectable failed harness result and **do not** call Phase 13E final RVOL calculation.
4. If input building succeeds, call the existing Phase 13E `calculate_time_of_day_relative_volume(...)` function using the built input.
5. Preserve the returned `TimeOfDayRelativeVolumeResult` in the harness result.
6. If Phase 13E fails, return an inspectable failed harness result with no usable RVOL.
7. If Phase 13E succeeds, return an `OK` harness result with the same positive, finite RVOL.
8. Do not recompute the cumulative baseline, historical mean, or final RVOL inside the harness.
9. Do not create defaults for missing history, bars, buckets, sessions, current volume, or RVOL.

## Symbol and Duplicate Rules

The component modules own their normalization and validation. The harness should use the normalized symbol/bucket exposed by the successful or failed lower-level results.

For the batch usable mapping:

```text
- preserve original input order in the result list;
- include only successful harness results in the mapping;
- use normalized symbol as mapping key;
- last successful duplicate normalized symbol wins;
- invalid duplicate inputs do not erase a previously successful mapping value;
- all-invalid input batches return {}.
```

## Watchlist-Only Boundary

This phase does not accept a watchlist configuration or fetch symbols.

Future live callers must provide only symbols explicitly listed in `MARKET_SENTRY_WATCHLIST`. The harness must not perform symbol discovery, broad scanning, exchange-wide crawling, or screener use.

## Secret Safety

The harness must not accept, store, print, or log:

- credentials;
- authorization headers;
- raw request representations;
- provider secrets;
- API URLs containing secret query values.

This module should be independent of HTTP and provider configurations.

## Testing Requirements

Add coverage for:

- Valid end-to-end result from explicit current and historical intraday fixture series.
- Harness RVOL equals the Phase 13E calculation derived from the constructed input.
- Current-series Phase 13F failure produces `FAILED_INPUT_BUILD` and does not call the Phase 13E calculator.
- Historical-series Phase 13F failure produces `FAILED_INPUT_BUILD` and preserves lower-level diagnostic context.
- Phase 13E calculation failure after a successful input build produces `FAILED_TIME_OF_DAY_RVOL` and preserves lower-level diagnostic context.
- Result includes inspectable input-builder and Phase 13E calculation artifacts as applicable.
- Batch result list preserves input order.
- Batch usable mapping contains successes only.
- Duplicate normalized symbol behavior is deterministic: last successful result wins; invalid duplicates do not erase prior success.
- All-invalid batch returns an empty mapping.
- Harness does not independently calculate or alter current cumulative volume, historical baseline, or final RVOL.
- No HTTP/network calls.
- No credentials, provider factory, transport, fetcher, or trading/order hooks.
- Default mock runtime still works.
- Fixture and composed_fixture remain offline.
- Alpaca remains a placeholder.
- `live_composed` remains gated/reserved inactive.
- Full test suite passes.

## README

Keep any README update brief:

- Phase 13G adds an offline end-to-end intraday RVOL harness.
- It composes caller-supplied fixture series through the existing Phase 13F and Phase 13E modules.
- It does not fetch market data, infer calendar/session behavior, or activate live mode.
- It does not fabricate missing RVOL data.
- `live_composed` remains reserved/inactive.
- Trading/order functionality remains out of scope.

## Acceptance Boundary

After Phase 13G:

- The complete fixture-only intraday RVOL flow is testable end to end.
- The harness may be reused by a future historical-bar-source adapter.
- `live_composed` remains inactive.
- No real network behavior exists in the harness or runtime path.
