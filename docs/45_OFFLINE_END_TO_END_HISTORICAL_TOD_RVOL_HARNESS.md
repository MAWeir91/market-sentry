# Phase 14G — Offline End-to-End Historical-to-TOD RVOL Harness

## Status

**Planned.** This document defines Phase 14G only.

Phase 14A through Phase 14F now form a complete offline, real-data-shaped time-of-day RVOL path:

```text
Phase 14A
  raw one-page historical bars

Phase 14B
  raw-bar timestamp adaptation

Phase 14C
  explicit historical session / bucket / completeness policy

Phase 14D
  historical session assembly

Phase 14E
  historical baseline composition

Phase 14F
  current series + final Phase 13E TOD RVOL composition
```

Phase 14G adds no new financial calculation, raw-data parser, session policy, baseline rule, or runtime behavior. It is a thin orchestrator that runs the existing layers in their approved order and returns a single inspectable end-to-end artifact.

---

## Goal

Create a pure offline harness with this explicit flow:

```text
one AlpacaHistoricalBarsPage
+ explicit historical-session metadata records
+ one explicit current IntradayVolumeSeriesInput
+ one explicit run request
→ Phase 14D assembly results
→ Phase 14E baseline composition result
→ Phase 14F final TOD RVOL composition result
→ one immutable end-to-end result
```

The run result must retain the actual artifacts from all three stages:

```text
Phase 14D:
  ordered HistoricalSessionAssemblyResult records

Phase 14E:
  HistoricalBaselineCompositionRequest
  HistoricalBaselineCompositionResult

Phase 14F:
  CurrentSessionTimeOfDayRvolResult
```

A final failure must be traceable to earlier stages without recomputing or flattening diagnostics.

Examples:

```text
page completeness problem
→ Phase 14D INCOMPLETE_PAGE_COLLECTION
→ Phase 14E partial/insufficient baseline
→ Phase 14F BASELINE_FAILED
→ harness FINAL_COMPOSITION_FAILED

invalid historical raw volume
→ Phase 14D ADAPTER_FAILED
→ Phase 14E ASSEMBLY_FAILED
→ Phase 14F BASELINE_FAILED
→ harness FINAL_COMPOSITION_FAILED

valid baseline + invalid current series
→ Phase 14E OK
→ Phase 14F CURRENT_CUMULATIVE_VOLUME_FAILED
→ harness FINAL_COMPOSITION_FAILED

valid historical and current inputs
→ Phase 14F OK
→ harness OK
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
HTTP requests, fetcher construction, pagination retrieval, retries, caching, WebSockets, or streaming
environment/config reads
automatic watchlist lookup or broad-market discovery
calendar, holiday, early-close, halt, split, or market-session inference
time-zone conversion or normalization
raw-bar parsing or direct raw-bar adaptation
new session-assembly or baseline-composition logic
new RVOL calculation logic
candidate composition, scoring, filtering, or alerts
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

`live_composed` must remain gated and reserved/inactive.

---

## Existing Components to Reuse

Reuse only these public boundaries:

```text
market_sentry.data.alpaca_historical_bars_fetcher
  AlpacaHistoricalBarsPage

market_sentry.data.historical_session_assembly
  HistoricalIntradaySessionMetadata
  HistoricalSessionAssemblyResult
  assemble_historical_sessions_from_page

market_sentry.data.historical_baseline_composition
  HistoricalBaselineCompositionRequest
  HistoricalBaselineCompositionResult
  compose_historical_baseline

market_sentry.data.current_session_tod_rvol
  CurrentSessionTimeOfDayRvolResult
  CurrentSessionTimeOfDayRvolStatus
  compose_current_session_time_of_day_rvol

market_sentry.data.intraday_bucket_adapter
  IntradayVolumeSeriesInput

market_sentry.data.time_of_day_rvol
  DEFAULT_MINIMUM_HISTORICAL_SESSIONS
```

Do not import or call:

```text
alpaca_historical_bars_adapter
Phase 13F cumulative functions directly
Phase 13E final RVOL calculation directly
HTTP transport modules
Alpaca fetchers
FMP fetchers
provider factory
config
live readiness
relative-volume providers/calculators
fixture providers
LiveCandidateBuilder
LiveComposedMarketDataProvider
scanner engine
alert modules
voice modules
```

Phase 14G may only orchestrate 14D, 14E, and 14F. It must not bypass or duplicate their logic.

---

## Expected Files

Create:

```text
docs/45_OFFLINE_END_TO_END_HISTORICAL_TOD_RVOL_HARNESS.md
src/market_sentry/data/historical_tod_rvol_harness.py
tests/test_historical_tod_rvol_harness.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 13, Phase 14A–14F, runtime, provider factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Models

Use frozen dataclasses.

```python
@dataclass(frozen=True)
class HistoricalToTodRvolRunRequest:
    """Explicit controls for one complete offline historical-to-TOD run."""

    symbol: str
    bucket: str
    current_session_id: str
    page_collection_complete: bool
    minimum_historical_sessions: int = DEFAULT_MINIMUM_HISTORICAL_SESSIONS
```

```python
@dataclass(frozen=True)
class HistoricalToTodRvolRunResult:
    """Inspectable artifacts from one full offline historical-to-TOD run."""

    request: HistoricalToTodRvolRunRequest
    baseline_request: HistoricalBaselineCompositionRequest
    assembly_results: tuple[HistoricalSessionAssemblyResult, ...]
    baseline_result: HistoricalBaselineCompositionResult
    final_result: CurrentSessionTimeOfDayRvolResult
    status: str
    reason: str | None = None
```

Exact public names may vary, but retain all of these responsibilities:

```text
original run request
fresh Phase 14E baseline request
ordered Phase 14D assembly results
exact Phase 14E baseline result
exact Phase 14F final result
simple harness-level status/reason
```

Do not return a bare float, a success-only structure, or a flattened error.

---

## Public Function

Provide:

```python
def run_historical_to_time_of_day_rvol(
    page: AlpacaHistoricalBarsPage,
    historical_metadata_records: Sequence[HistoricalIntradaySessionMetadata],
    current_series: IntradayVolumeSeriesInput,
    request: HistoricalToTodRvolRunRequest,
) -> HistoricalToTodRvolRunResult:
    ...
```

There is no provider interface, CLI command, polling loop, or batch API in this phase.

---

## Stable Harness Status Codes

Use a small harness-level status container:

```text
OK
FINAL_COMPOSITION_FAILED
```

The harness result is:

```text
status = OK
reason = None
```

only when:

```text
final_result.status == CurrentSessionTimeOfDayRvolStatus.OK
```

Otherwise:

```text
status = FINAL_COMPOSITION_FAILED
reason = FINAL_COMPOSITION_FAILED:<exact final_result.status>
```

The detailed root cause must remain in:

```text
assembly_results
baseline_result
final_result
```

Do not introduce broad harness statuses such as `INVALID_REQUEST`, `BASELINE_FAILED`, or `CURRENT_FAILED`. Those decisions belong to Phase 14D, Phase 14E, and Phase 14F.

---

## Strict Orchestration Rules

### 1. Preserve input order once

Convert:

```text
historical_metadata_records
```

to a tuple once at the start of the run.

Use that same ordered tuple for the Phase 14D call. Do not sort, filter, deduplicate, mutate, or rebuild caller metadata.

The harness must not inspect raw metadata values or validate them itself. Phase 14D owns those diagnostics.

---

### 2. Always call Phase 14D exactly once

Call:

```python
assembly_results = assemble_historical_sessions_from_page(
    page,
    metadata_records_tuple,
    current_session_id=request.current_session_id,
    page_collection_complete=request.page_collection_complete,
)
```

The harness must forward exactly:

```text
page
the ordered metadata tuple
request.current_session_id
request.page_collection_complete
```

It must not:

```text
validate page_collection_complete
reject a non-bool itself
inspect page.next_page_token
inspect raw bars
parse timestamps
rebuild session metadata
```

Phase 14D owns all of that behavior.

Convert the returned assembly sequence to an immutable tuple for the end-to-end result and for the Phase 14E call.

---

### 3. Always build a fresh Phase 14E request

Construct exactly one fresh:

```python
HistoricalBaselineCompositionRequest(
    symbol=request.symbol,
    bucket=request.bucket,
    current_session_id=request.current_session_id,
    minimum_historical_sessions=request.minimum_historical_sessions,
)
```

Do not normalize, validate, modify, or infer any request field in Phase 14G.

Then call exactly once:

```python
baseline_result = compose_historical_baseline(
    assembly_results_tuple,
    baseline_request,
)
```

The harness must not:

```text
short-circuit on failed Phase 14D records
count successful sessions
manufacture observations
revalidate a 20-session threshold
repair baseline artifacts
```

Phase 14E owns baseline request validation, identity filtering, duplicate handling, Phase 13F historical cumulative evaluation, and the minimum-session requirement.

---

### 4. Always call Phase 14F exactly once

Call exactly once:

```python
final_result = compose_current_session_time_of_day_rvol(
    current_series,
    baseline_result,
)
```

Call it even when:

```text
Phase 14D returns all failures
Phase 14E baseline status is not OK
Phase 14E request is invalid
Phase 14E has no observations
```

Phase 14F owns its baseline gate and will return a `BASELINE_FAILED` artifact without evaluating the current series or Phase 13E.

Phase 14G must not inspect current-series bars, normalize identifiers, compare identity, invoke Phase 13F, construct a TOD input, or invoke Phase 13E directly.

---

### 5. Preserve stage artifacts exactly

The run result must retain:

```text
request:
  exact caller request object

baseline_request:
  fresh object built directly from request fields

assembly_results:
  exact Phase 14D results, converted only to a tuple

baseline_result:
  exact Phase 14E result object

final_result:
  exact Phase 14F result object
```

Do not replace lower-level result objects. Do not clone their diagnostics. Do not flatten errors into a new message that hides the underlying stage artifact.

---

## Immutability and Ownership

- New run models must be frozen.
- `assembly_results` must be a tuple.
- The caller-supplied page, metadata sequence, metadata objects, current series, and run request must not be mutated.
- The harness owns only its newly created `HistoricalBaselineCompositionRequest` and run result.
- No state may be cached between calls.
- Repeated calls must not share mutable state.

---

## Required Tests

Use manually constructed input objects and focused monkeypatching only for the three approved stage functions:

```text
assemble_historical_sessions_from_page
compose_historical_baseline
compose_current_session_time_of_day_rvol
```

Do not use network, fetchers, transports, providers, config, factory, runtime, scanner, or alert setup.

Test:

```text
successful run:
  Phase 14D called exactly once
  Phase 14E called exactly once
  Phase 14F called exactly once
  exact arguments forwarded
  returns OK
  exact stage artifacts retained

Phase 14D failures:
  Phase 14E still called once with exact assembly artifacts
  Phase 14F still called once with exact baseline artifact
  final/harness failure is preserved without early exit

Phase 14E failure:
  Phase 14F still called once
  harness returns FINAL_COMPOSITION_FAILED:<exact final status>
  no direct current-series evaluation exists in harness

Phase 14F current failure:
  harness returns FINAL_COMPOSITION_FAILED:CURRENT_CUMULATIVE_VOLUME_FAILED
  exact final artifact retained

Phase 14F identity mismatch:
  harness returns FINAL_COMPOSITION_FAILED:<exact mismatch status>
  exact final artifact retained

Phase 14F Phase 13E failure:
  harness returns FINAL_COMPOSITION_FAILED:TIME_OF_DAY_RVOL_FAILED
  exact final artifact retained

argument forwarding:
  metadata caller order and duplicate records preserved
  page identity preserved
  current series identity preserved
  request fields passed verbatim to Phase 14D and fresh Phase 14E request
  default and higher minimum values forwarded unchanged

request boundary:
  invalid/blank/non-bool fields are forwarded to lower stages
  harness does not add request validation or short-circuit

immutability:
  run result frozen
  assembly tuple is immutable
  caller inputs unchanged
  repeated runs do not share mutable state

source boundary:
  no direct Phase 13F/Phase 13E calls
  no raw page adapter
  no HTTP/fetcher/transport
  no config/factory/provider/runtime/scanner/alert/voice/candidate hooks
  no trading/order hooks
```

Add at least one integration-style test using the actual approved Stage 14D/14E/14F functions and a deterministic offline fixture set that produces a successful final TOD RVOL result. It must not use HTTP or any live provider.

The integration test should demonstrate:

```text
20 eligible historical metadata sessions
+ explicit complete raw page
+ explicit current series
→ final_result.status == OK
→ harness.status == OK
```

Keep fixture construction local to the test. Do not modify the global scenario catalog or existing fixture providers.

---

## README Note

Update only if useful:

```text
Phase 14G adds a thin offline end-to-end harness that orchestrates the existing Phase 14D historical-session assembly, Phase 14E baseline composition, and Phase 14F final TOD RVOL composition layers.
It retains all stage artifacts and diagnostics for one explicit input run.
It does not fetch data, paginate, infer calendars, register a runtime provider, or activate live mode.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```

---

## Acceptance Criteria

Phase 14G is complete when:

```text
- the harness calls Phase 14D, Phase 14E, and Phase 14F exactly once in order;
- every stage artifact is available in one immutable run result;
- a stage failure is preserved rather than short-circuited or flattened;
- only the final Phase 14F status determines the simple harness-level status;
- no direct Phase 13F/Phase 13E calculation occurs in the harness;
- no runtime, network, provider, candidate, scanner, alert, voice, or trading capability is added;
- an actual offline integration fixture demonstrates a successful end-to-end TOD RVOL result;
- the full project suite remains green.
```
