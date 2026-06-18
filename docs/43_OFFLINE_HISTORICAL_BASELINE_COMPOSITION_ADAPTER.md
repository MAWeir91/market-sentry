# Phase 14E — Offline Historical Baseline Composition Adapter

## Status

**Planned.** This document defines Phase 14E only.

Phase 14D turns one raw historical-bars page plus explicit historical-session metadata into inspectable `HistoricalSessionAssemblyResult` records. A successful Phase 14D result contains a Phase 14B-adapted `IntradayVolumeSeriesInput`.

Phase 14E composes those assembled historical session results into the exact ordered `HistoricalCumulativeVolumeObservation` objects consumed later by Phase 13E.

```text
Phase 14D assembly results
→ Phase 14E per-session cumulative-volume evaluation
→ ordered HistoricalCumulativeVolumeObservation baseline artifact
→ future current-series + Phase 13E final TOD RVOL calculation
```

Phase 14E does **not** calculate final RVOL. It does **not** build a `TimeOfDayRelativeVolumeInput`, because that requires a separate current-session input and final Phase 13E calculation scope.

---

## Goal

Create a pure offline historical baseline composition adapter that:

1. accepts ordered Phase 14D `HistoricalSessionAssemblyResult` records;
2. retains every source record as an inspectable per-session composition result;
3. uses only successful assembled session series as candidates;
4. validates target symbol, bucket, and current-session exclusion explicitly;
5. evaluates each eligible candidate through the existing Phase 13F `calculate_cumulative_volume_at_bucket(...)` function;
6. converts only Phase 13F-successful evaluations into ordered `HistoricalCumulativeVolumeObservation` values;
7. enforces a minimum of 20 eligible historical observations by default;
8. preserves lower-level Phase 14D and Phase 13F diagnostics rather than failing fast.

The intended future path is:

```text
Phase 14A raw historical bars
→ Phase 14D session assembly
→ Phase 14E historical baseline composition
→ future current-series evaluation
→ Phase 13E calculate_time_of_day_relative_volume
```

---

## Hard Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is **not** a trading bot.

Do not add:

```text
runtime activation
provider-factory registration or selection changes
new MARKET_SENTRY_PROVIDER values
CLI flags, reports, polling, scanner-loop, alert, or voice changes
HTTP requests, fetcher construction, pagination, retries, caching, WebSockets, or streaming
environment/config reads
automatic watchlist lookup or broad-market discovery
calendar, holiday, early-close, halt, split, or market-session inference
time-zone conversion or normalization
raw-bar parsing, adaptation, or session-window assembly
current-session series construction
TimeOfDayRelativeVolumeInput construction
calculate_time_of_day_relative_volume invocation
final RVOL output
candidate composition, scoring, filtering, or alerts
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

`live_composed` remains gated and reserved/inactive.

---

## Existing Components to Reuse

Reuse only:

```text
market_sentry.data.historical_session_assembly
  HistoricalSessionAssemblyResult
  HistoricalSessionAssemblyStatus

market_sentry.data.intraday_bucket_adapter
  CumulativeVolumeAtBucketResult
  IntradayBucketStatus
  calculate_cumulative_volume_at_bucket

market_sentry.data.time_of_day_rvol
  DEFAULT_MINIMUM_HISTORICAL_SESSIONS
  HistoricalCumulativeVolumeObservation
```

Do not import or call:

```text
alpaca_historical_bars_fetcher
alpaca_historical_bars_adapter
historical_session_assembly assemble function
HTTP transport modules
fetchers
provider factory
config or live readiness
relative_volume_calculator
historical_volume_adapter
time_of_day_rvol calculate_time_of_day_relative_volume
TimeOfDayRelativeVolumeInput
intraday_rvol_harness
intraday_rvol_fixture_provider
intraday_rvol_candidate_composition_harness
LiveCandidateBuilder
LiveComposedMarketDataProvider
scanner engine
alert modules
voice modules
```

Phase 14E consumes already-created Phase 14D result objects. It must not reassemble sessions, reparse raw timestamps, or re-read raw pages.

---

## Expected Files

Create:

```text
docs/43_OFFLINE_HISTORICAL_BASELINE_COMPOSITION_ADAPTER.md
src/market_sentry/data/historical_baseline_composition.py
tests/test_historical_baseline_composition.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 13, Phase 14A–14D, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Models

Use frozen dataclasses and explicit caller-supplied target metadata.

```python
@dataclass(frozen=True)
class HistoricalBaselineCompositionRequest:
    """Target identity and baseline requirement for a historical composition run."""

    symbol: str
    bucket: str
    current_session_id: str
    minimum_historical_sessions: int = DEFAULT_MINIMUM_HISTORICAL_SESSIONS
```

```python
@dataclass(frozen=True)
class HistoricalBaselineSessionResult:
    """Inspectable outcome for one supplied Phase 14D assembly result."""

    assembly_result: HistoricalSessionAssemblyResult
    cumulative_result: CumulativeVolumeAtBucketResult | None
    observation: HistoricalCumulativeVolumeObservation | None
    status: str
    reason: str | None = None
```

```python
@dataclass(frozen=True)
class HistoricalBaselineCompositionResult:
    """Ordered historical-baseline artifact without final RVOL calculation."""

    symbol: str
    bucket: str
    current_session_id: str
    minimum_historical_sessions: int | None
    observations: tuple[HistoricalCumulativeVolumeObservation, ...]
    session_results: tuple[HistoricalBaselineSessionResult, ...]
    eligible_session_count: int
    status: str
    reason: str | None = None
```

Exact names may vary, but retain the same explicit responsibilities and inspectability.

---

## Public Function

Provide:

```python
def compose_historical_baseline(
    assembly_results: Sequence[HistoricalSessionAssemblyResult],
    request: HistoricalBaselineCompositionRequest,
) -> HistoricalBaselineCompositionResult:
    ...
```

The function must preserve the caller-provided order in `session_results`.

The `observations` tuple must preserve the relative input order of only successful, eligible historical sessions. Do not sort records chronologically, by session ID, or by volume.

---

## Stable Status Codes

Use explicit stable strings. A separate composition and per-session status container is recommended.

### Composition-level statuses

```text
OK
INVALID_TARGET_SYMBOL
INVALID_TARGET_BUCKET
INVALID_CURRENT_SESSION_ID
INVALID_MINIMUM_HISTORICAL_SESSIONS
INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
```

### Per-session statuses

```text
OK
ASSEMBLY_FAILED
MISSING_INTRADAY_SERIES
MISMATCHED_HISTORICAL_SYMBOL
MISMATCHED_HISTORICAL_BUCKET
CURRENT_SESSION_IN_HISTORY
DUPLICATE_HISTORICAL_SESSION_ID
CUMULATIVE_VOLUME_FAILED
```

Use stable reason strings that preserve lower-level diagnostics:

```text
ASSEMBLY_FAILED:<exact Phase 14D status>
CUMULATIVE_VOLUME_FAILED:<exact Phase 13F IntradayBucketStatus>
```

Examples:

```text
ASSEMBLY_FAILED:CUT_OFF_NOT_REACHED
ASSEMBLY_FAILED:ADAPTER_FAILED
CUMULATIVE_VOLUME_FAILED:INVALID_INTRADAY_VOLUME
CUMULATIVE_VOLUME_FAILED:OUT_OF_ORDER_INTRADAY_TIMESTAMP
```

Do not flatten or replace the original lower-level result object. Always preserve it inside the relevant session result.

---

## Request Validation

Normalize explicit caller target text using existing project conventions:

```text
symbol:
  trim surrounding whitespace
  uppercase
  blank → INVALID_TARGET_SYMBOL

bucket:
  trim surrounding whitespace
  preserve resulting label exactly
  blank → INVALID_TARGET_BUCKET

current_session_id:
  trim surrounding whitespace
  preserve resulting case/content exactly
  blank/non-string → INVALID_CURRENT_SESSION_ID
```

`minimum_historical_sessions`:

```text
must be a real int, not bool
must be >= DEFAULT_MINIMUM_HISTORICAL_SESSIONS (20)
```

Anything else returns:

```text
INVALID_MINIMUM_HISTORICAL_SESSIONS
```

Do not permit a lower caller-provided threshold to silently weaken the project’s required 20-session baseline. A caller may request a higher threshold.

For any invalid composition request:

```text
- do not evaluate Phase 13F;
- return no observations;
- return no per-session results;
- set eligible_session_count = 0;
- return the relevant composition-level failure.
```

The raw supplied Phase 14D objects remain untouched.

---

## Per-Session Composition Rules

For every supplied Phase 14D result, in caller order:

### 1. Phase 14D status gate

If:

```text
assembly_result.status != HistoricalSessionAssemblyStatus.OK
```

then create:

```text
status = ASSEMBLY_FAILED
reason = ASSEMBLY_FAILED:<assembly_result.status>
cumulative_result = None
observation = None
```

Do not call Phase 13F for that record.

### 2. Series presence

If Phase 14D reports `OK` but:

```text
assembly_result.intraday_series is None
```

then create:

```text
status = MISSING_INTRADAY_SERIES
reason = MISSING_INTRADAY_SERIES
```

Do not call Phase 13F.

### 3. Target identity checks

For a present series, normalize its symbol, bucket, and session ID with the same project rules.

Require:

```text
series.symbol == normalized request.symbol
series.bucket == trimmed request.bucket
series.session_id != trimmed request.current_session_id
```

If mismatched:

```text
symbol mismatch → MISMATCHED_HISTORICAL_SYMBOL
bucket mismatch → MISMATCHED_HISTORICAL_BUCKET
current session reused → CURRENT_SESSION_IN_HISTORY
```

Do not call Phase 13F for a target-identity mismatch.

### 4. Duplicate session IDs

Detect duplicate eligible candidates after:

```text
- Phase 14D status is OK;
- intraday series exists;
- normalized symbol and bucket match request;
- session ID is not current.
```

Duplicate identity is:

```text
normalized series symbol + trimmed, case-sensitive series session_id
```

Every candidate sharing a duplicate identity must receive:

```text
DUPLICATE_HISTORICAL_SESSION_ID
```

Do not evaluate Phase 13F for duplicate candidates.

Same session ID for a different symbol is not relevant after target-symbol matching. Differently cased session IDs remain distinct after trimming.

### 5. Phase 13F cumulative evaluation

For every remaining unique eligible candidate, call exactly once:

```python
calculate_cumulative_volume_at_bucket(assembly_result.intraday_series)
```

If it succeeds:

```text
status = OK
reason = None
cumulative_result = exact Phase 13F result
observation = HistoricalCumulativeVolumeObservation(
    session_id=cumulative_result.session_id,
    bucket=cumulative_result.bucket,
    cumulative_volume=cumulative_result.cumulative_volume,
)
```

If it fails:

```text
status = CUMULATIVE_VOLUME_FAILED
reason = CUMULATIVE_VOLUME_FAILED:<exact Phase 13F status>
cumulative_result = exact failed Phase 13F result
observation = None
```

Phase 14E does not reinterpret Phase 13F validation statuses. It may not add its own raw-volume, timestamp ordering, duplicate timestamp, or cutoff rules.

---

## Baseline Eligibility and Outcome

`eligible_session_count` is exactly:

```text
len(observations)
```

After all records are processed:

```text
eligible_session_count >= minimum_historical_sessions
→ overall status = OK
→ observations retained in ordered tuple

eligible_session_count < minimum_historical_sessions
→ overall status = INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
→ observations still retained in ordered tuple
→ all per-session diagnostics remain available
```

An insufficient baseline is not a generic failure. It is an inspectable partial artifact with a clear count and reasons for every excluded record.

Do not fabricate observations, substitute a daily-average baseline, include invalid sessions, or pad missing sessions.

---

## Immutability and Ownership

- New result models must be frozen.
- Output collections must be tuples.
- Do not mutate the supplied Phase 14D result objects, their embedded Phase 14B objects, their `IntradayVolumeSeriesInput`, or any Phase 13F result.
- The `HistoricalCumulativeVolumeObservation` objects must be freshly constructed from successful Phase 13F results.
- No mapping or list returned by a caller may remain mutable through an output reference.
- No state is cached between function calls.

---

## Required Tests

Use manually constructed `HistoricalSessionAssemblyResult` and `IntradayVolumeSeriesInput` fixtures only.

Do not call Phase 14D’s assembler, Phase 14A/14B, a fetcher, transport, provider, or runtime setup.

Test:

```text
exactly 20 successful assembled sessions
→ 20 ordered observations
→ eligible_session_count 20
→ overall OK

more than 20 valid sessions
→ overall OK
→ order preserved

19 valid sessions
→ INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
→ partial ordered observations retained

caller may require a higher minimum
→ insufficient/OK behavior respects the higher value

invalid target symbol, bucket, current session ID, and minimum:
  no Phase 13F evaluation
  no observations
  no session results

successful Phase 14D result with no intraday series
→ MISSING_INTRADAY_SERIES

non-OK Phase 14D result
→ ASSEMBLY_FAILED:<exact Phase 14D status>
→ no Phase 13F evaluation

mismatched series symbol
→ MISMATCHED_HISTORICAL_SYMBOL
→ no Phase 13F evaluation

mismatched series bucket
→ MISMATCHED_HISTORICAL_BUCKET
→ no Phase 13F evaluation

current series ID appearing in history
→ CURRENT_SESSION_IN_HISTORY
→ no Phase 13F evaluation

duplicate eligible candidate IDs:
  every duplicate rejected
  no Phase 13F evaluation for duplicates
  differently cased IDs distinct
  input order preserved

Phase 13F handoff:
  valid bars create exact HistoricalCumulativeVolumeObservation
  invalid raw volume becomes CUMULATIVE_VOLUME_FAILED:INVALID_INTRADAY_VOLUME
  out-of-order bar timestamps preserve exact lower-level status
  no adapter/session/reassembly logic is rerun

observations:
  only successful Phase 13F candidates
  ordered relative to original supplied records
  exact session ID and bucket copied from Phase 13F result
  no sorting or time-zone conversion

immutability:
  results frozen
  tuples used
  input assembly artifacts unchanged
  repeated calls have no shared mutable state

source boundary:
  no fetcher, transport, config, factory, provider, runtime, scanner,
  alert, voice, candidate, Phase 14A/14B raw handling, Phase 13E final
  RVOL calculation, TimeOfDayRelativeVolumeInput, or trading hooks
```

Add a focused source-boundary test using AST or targeted source inspection. The module should call only the approved Phase 13F cumulative evaluator and use the Phase 13E observation model as a data artifact.

Run focused tests, the full suite, and all established runtime smoke checks.

---

## README Note

Update only if useful:

```text
Phase 14E adds an offline historical baseline composer. It evaluates eligible Phase 14D session series through the existing Phase 13F cumulative-volume validator and produces ordered historical cumulative-volume observations for a later Phase 13E TOD RVOL calculation.
It does not build a current-series input, calculate final RVOL, fetch data, infer calendars, register a runtime provider, or activate live mode.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```

---

## Acceptance Criteria

Phase 14E is complete when:

```text
- Phase 14D results are retained as inspectable per-session composition records;
- only valid, unique, non-current sessions produce Phase 13F evaluations;
- only Phase 13F-successful results produce Phase 13E observation artifacts;
- ordered observations are retained even for an insufficient baseline;
- the baseline requires at least 20 eligible sessions by default;
- lower-level Phase 14D/13F diagnostics are preserved;
- no final RVOL, live provider, network, runtime, candidate, or trading capability is added;
- the full project suite remains green.
```
