# Phase 14F — Offline Current-Session Composition and Final TOD RVOL Adapter

## Status

**Planned.** This document defines Phase 14F only.

Phase 14E produces an inspectable historical baseline artifact:

```text
HistoricalBaselineCompositionResult
  - ordered HistoricalCumulativeVolumeObservation values
  - per-session diagnostics
  - enforced minimum historical-session threshold
  - baseline status
```

Phase 14F combines exactly one explicit current-session `IntradayVolumeSeriesInput` with a successful Phase 14E baseline artifact, evaluates the current series through Phase 13F, and calls the existing Phase 13E final time-of-day RVOL calculator.

```text
current IntradayVolumeSeriesInput
+ successful Phase 14E baseline artifact
→ Phase 13F current cumulative-volume result
→ TimeOfDayRelativeVolumeInput
→ Phase 13E final TOD RVOL result
→ one inspectable composed result
```

This completes the offline, real-data-shaped TOD RVOL path. It does not activate live data or register a runtime provider.

---

## Goal

Create a pure offline final-composition adapter that:

1. accepts one explicit current-session `IntradayVolumeSeriesInput`;
2. accepts one existing `HistoricalBaselineCompositionResult`;
3. requires a successful Phase 14E baseline before evaluating the current series;
4. evaluates the current series exactly once through existing Phase 13F `calculate_cumulative_volume_at_bucket(...)`;
5. confirms the current Phase 13F identity matches the baseline’s symbol, bucket, and current session ID;
6. constructs a fresh `TimeOfDayRelativeVolumeInput` from:
   - current Phase 13F cumulative volume;
   - exact Phase 14E historical observations;
7. calls existing Phase 13E `calculate_time_of_day_relative_volume(...)` exactly once;
8. preserves every lower-level artifact and failure diagnostic.

The intended completed offline pipeline is:

```text
Phase 14A raw historical bars
→ Phase 14D historical-session assembly
→ Phase 14E historical baseline observations
→ Phase 14F current cumulative volume + final Phase 13E TOD RVOL
```

---

## Hard Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is **not** a trading bot.

Do not add:

```text
runtime activation
provider-factory registration or provider-selection changes
new MARKET_SENTRY_PROVIDER values
CLI flags, reports, polling, scanner-loop, alert, or voice changes
HTTP requests, fetcher construction, pagination, retries, caching, WebSockets, or streaming
environment/config reads
automatic watchlist lookup or broad-market discovery
calendar, holiday, early-close, halt, split, or market-session inference
time-zone conversion or normalization
raw-bar parsing, historical session assembly, or baseline composition
candidate composition, scoring, filtering, or alerts
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

`live_composed` remains gated and reserved/inactive.

---

## Existing Components to Reuse

Reuse only:

```text
market_sentry.data.historical_baseline_composition
  HistoricalBaselineCompositionResult
  HistoricalBaselineCompositionStatus

market_sentry.data.intraday_bucket_adapter
  IntradayVolumeSeriesInput
  CumulativeVolumeAtBucketResult
  IntradayBucketStatus
  calculate_cumulative_volume_at_bucket

market_sentry.data.time_of_day_rvol
  TimeOfDayRelativeVolumeInput
  TimeOfDayRelativeVolumeResult
  TimeOfDayRelativeVolumeStatus
  calculate_time_of_day_relative_volume
```

Do not import or call:

```text
alpaca_historical_bars_fetcher
alpaca_historical_bars_adapter
historical_session_assembly
historical_baseline_composition compose function
HTTP transport modules
fetchers
provider factory
config or live readiness
relative_volume_calculator
historical_volume_adapter
time_of_day_rvol internals other than the public models/function above
intraday_rvol_harness
intraday_rvol_fixture_provider
intraday_rvol_candidate_composition_harness
LiveCandidateBuilder
LiveComposedMarketDataProvider
scanner engine
alert modules
voice modules
```

Phase 14F consumes already-built Phase 14E artifacts. It must not rebuild their observations or rerun baseline composition.

---

## Expected Files

Create:

```text
docs/44_OFFLINE_CURRENT_SESSION_FINAL_TOD_RVOL_ADAPTER.md
src/market_sentry/data/current_session_tod_rvol.py
tests/test_current_session_tod_rvol.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 13, Phase 14A–14E, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Result Model

Use one frozen, inspectable result object:

```python
@dataclass(frozen=True)
class CurrentSessionTimeOfDayRvolResult:
    """Final offline TOD RVOL composition result."""

    baseline_result: HistoricalBaselineCompositionResult
    current_result: CumulativeVolumeAtBucketResult | None
    calculation_input: TimeOfDayRelativeVolumeInput | None
    time_of_day_result: TimeOfDayRelativeVolumeResult | None
    status: str
    reason: str | None = None
```

The exact name may vary, but preserve all four lower-level artifacts:

```text
baseline_result
current_result
calculation_input
time_of_day_result
```

Do not return a bare float or a success-only mapping.

---

## Public Function

Provide:

```python
def compose_current_session_time_of_day_rvol(
    current_series: IntradayVolumeSeriesInput,
    baseline_result: HistoricalBaselineCompositionResult,
) -> CurrentSessionTimeOfDayRvolResult:
    ...
```

There is no batch API in Phase 14F.

---

## Stable Status Codes

Use explicit stable strings. A status container is recommended.

```text
OK
BASELINE_FAILED
CURRENT_CUMULATIVE_VOLUME_FAILED
MISMATCHED_CURRENT_SYMBOL
MISMATCHED_CURRENT_BUCKET
MISMATCHED_CURRENT_SESSION_ID
TIME_OF_DAY_RVOL_FAILED
```

Use stable reason strings that preserve lower-level detail:

```text
BASELINE_FAILED:<exact Phase 14E status>
CURRENT_CUMULATIVE_VOLUME_FAILED:<exact Phase 13F status>
TIME_OF_DAY_RVOL_FAILED:<exact Phase 13E status>
```

Examples:

```text
BASELINE_FAILED:INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
CURRENT_CUMULATIVE_VOLUME_FAILED:INVALID_INTRADAY_VOLUME
CURRENT_CUMULATIVE_VOLUME_FAILED:OUT_OF_ORDER_INTRADAY_TIMESTAMP
TIME_OF_DAY_RVOL_FAILED:NON_FINITE_TIME_OF_DAY_RVOL
```

For target-identity failures:

```text
status = MISMATCHED_CURRENT_SYMBOL
reason = MISMATCHED_CURRENT_SYMBOL

status = MISMATCHED_CURRENT_BUCKET
reason = MISMATCHED_CURRENT_BUCKET

status = MISMATCHED_CURRENT_SESSION_ID
reason = MISMATCHED_CURRENT_SESSION_ID
```

Do not flatten or replace the original Phase 14E, Phase 13F, or Phase 13E result objects.

---

## Composition Rules

### 1. Phase 14E baseline gate

The Phase 14E baseline artifact is the authority for historical eligibility.

If:

```text
baseline_result.status != HistoricalBaselineCompositionStatus.OK
```

return:

```text
status = BASELINE_FAILED
reason = BASELINE_FAILED:<exact baseline_result.status>
current_result = None
calculation_input = None
time_of_day_result = None
```

Do not call Phase 13F for current data. Do not call Phase 13E.

This includes, for example:

```text
BASELINE_FAILED:INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
BASELINE_FAILED:INVALID_TARGET_SYMBOL
BASELINE_FAILED:INVALID_MINIMUM_HISTORICAL_SESSIONS
```

A baseline status of `OK` is required even if it contains 20 or more observations in a manually constructed inconsistent object.

---

### 2. Current Phase 13F evaluation

Only after a successful baseline gate, call exactly once:

```python
calculate_cumulative_volume_at_bucket(current_series)
```

If Phase 13F fails:

```text
status = CURRENT_CUMULATIVE_VOLUME_FAILED
reason = CURRENT_CUMULATIVE_VOLUME_FAILED:<exact IntradayBucketStatus>
current_result = exact failed Phase 13F result
calculation_input = None
time_of_day_result = None
```

Do not call Phase 13E.

Phase 14F must not manually revalidate current raw bars, timestamps, order, cutoff inclusion, or volumes.

---

### 3. Current-to-baseline identity compatibility

For a successful current Phase 13F result, require exact compatibility with the already-normalized Phase 14E baseline artifact:

```text
current_result.symbol == baseline_result.symbol
current_result.bucket == baseline_result.bucket
current_result.session_id == baseline_result.current_session_id
```

All three values are the normalized/trimmed values returned by lower layers. The session-ID comparison remains case-sensitive.

If current identity does not match:

```text
symbol mismatch → MISMATCHED_CURRENT_SYMBOL
bucket mismatch → MISMATCHED_CURRENT_BUCKET
session ID mismatch → MISMATCHED_CURRENT_SESSION_ID
```

In each identity mismatch:

```text
current_result = exact successful Phase 13F result
calculation_input = None
time_of_day_result = None
```

Do not call Phase 13E.

Phase 14F must not search for a matching baseline, change the baseline target identity, rewrite a session ID, or substitute a bucket.

---

### 4. Final Phase 13E handoff

Only after both:

```text
baseline_result.status == OK
current_result.status == OK
current identity exactly matches baseline identity
```

construct a fresh:

```python
TimeOfDayRelativeVolumeInput(
    symbol=current_result.symbol,
    bucket=current_result.bucket,
    current_cumulative_volume=current_result.cumulative_volume,
    historical_observations=baseline_result.observations,
)
```

Then call exactly once:

```python
calculate_time_of_day_relative_volume(
    calculation_input.symbol,
    calculation_input.bucket,
    calculation_input.current_cumulative_volume,
    calculation_input.historical_observations,
    minimum_historical_sessions=baseline_result.minimum_historical_sessions,
)
```

Use the exact ordered `baseline_result.observations` tuple. Do not filter, sort, deduplicate, clone with changed values, pad, substitute, or calculate a new historical average.

If Phase 13E returns `OK`:

```text
status = OK
reason = None
```

If Phase 13E fails:

```text
status = TIME_OF_DAY_RVOL_FAILED
reason = TIME_OF_DAY_RVOL_FAILED:<exact TimeOfDayRelativeVolumeStatus>
```

Preserve the exact returned `TimeOfDayRelativeVolumeResult`.

Phase 14F does not inspect or reinterpret any Phase 13E final calculation diagnostic.

---

## Minimum-Historical-Session Ownership

Phase 14E has already enforced:

```text
minimum_historical_sessions >= 20
```

Phase 14F must pass exactly:

```text
baseline_result.minimum_historical_sessions
```

to Phase 13E.

Phase 14F must not:

```text
replace it with a default
lower it
raise it
infer it from observation count
```

A successful Phase 14E baseline should therefore normally yield a Phase 13E observation count at or above its required minimum.

If a manually inconsistent baseline artifact causes Phase 13E to fail, preserve the failure under:

```text
TIME_OF_DAY_RVOL_FAILED:<exact Phase 13E status>
```

Do not silently repair the baseline artifact.

---

## Immutability and Ownership

- The new result model must be frozen.
- Do not mutate `current_series`, `baseline_result`, baseline observations, or lower-level result objects.
- `calculation_input` must be freshly constructed.
- It must reference the exact immutable `baseline_result.observations` tuple.
- No state is cached between calls.
- Repeated calls must not share mutable state.

---

## Required Tests

Use manually constructed `HistoricalBaselineCompositionResult` and `IntradayVolumeSeriesInput` fixtures only.

Do not call Phase 14E composition, Phase 14D assembly, Phase 14A/14B, fetchers, transports, providers, config, or runtime setup.

Test:

```text
successful baseline + valid current series:
  current series evaluated exactly once through Phase 13F
  Phase 13E called exactly once
  status OK
  exact RVOL / historical average / count preserved
  calculation input is fresh
  exact baseline observations tuple is used

baseline not OK:
  BASELINE_FAILED:<exact Phase 14E status>
  no Phase 13F current evaluation
  no Phase 13E call

current Phase 13F failures:
  invalid raw volume
  out-of-order timestamps
  duplicate timestamps
  no bars
  no bars at or before cutoff
  each preserves CURRENT_CUMULATIVE_VOLUME_FAILED:<exact status>
  no Phase 13E call

successful current Phase 13F identity mismatches:
  symbol mismatch
  bucket mismatch
  current session ID mismatch
  current cumulative result retained
  no Phase 13E call

final handoff:
  receives exact ordered baseline observations
  receives baseline minimum exactly
  does not sort/filter/pad observations
  final Phase 13E result artifact preserved exactly

manually inconsistent OK baseline:
  fewer observations than its stated minimum
  reaches Phase 13E
  returns TIME_OF_DAY_RVOL_FAILED:INSUFFICIENT_HISTORICAL_OBSERVATIONS

manually inconsistent OK baseline:
  invalid observation volume or duplicate historical session ID
  reaches Phase 13E
  preserves exact Phase 13E failure status

immutability:
  result frozen
  no mutation of baseline/current inputs
  repeated calls share no mutable state

source boundary:
  no fetcher, transport, config, factory, provider, runtime, scanner,
  alert, voice, candidate, raw-page, adapter, session-assembly, baseline-
  composition function, Phase 14E re-composition, or trading hooks
```

Use dependency injection only if it is necessary to prove call counts without monkeypatching global behavior. Prefer straightforward public-function monkeypatching in the dedicated unit tests. Do not create a general framework or runtime dependency container.

Run focused tests, the full project suite, and established runtime smoke checks.

---

## README Note

Update only if useful:

```text
Phase 14F adds an offline current-session TOD RVOL adapter. It combines a successful Phase 14E baseline artifact with one explicit current intraday series, reuses Phase 13F for current cumulative volume, and reuses Phase 13E for the final time-of-day RVOL calculation.
It does not fetch data, infer sessions or calendars, register a runtime provider, or activate live mode.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```

---

## Acceptance Criteria

Phase 14F is complete when:

```text
- a successful Phase 14E baseline and valid current series produce an inspectable final Phase 13E TOD RVOL result;
- Phase 14E baseline failures block current and final evaluation;
- Phase 13F current failures block final evaluation with exact preserved diagnostics;
- exact current-to-baseline symbol/bucket/session identity is required;
- Phase 14E observations and minimum are forwarded unchanged;
- Phase 13E failures are preserved exactly;
- no live provider, network, runtime, candidate, scanner, alert, voice, or trading capability is added;
- the full project suite remains green.
```
