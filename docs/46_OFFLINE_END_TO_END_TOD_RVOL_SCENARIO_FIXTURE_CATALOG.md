# Phase 14H — Offline End-to-End TOD RVOL Scenario Fixture Catalog

## Status

**Planned.** This document defines Phase 14H only.

Phase 14G provides a complete offline harness:

```text
raw historical bars page
+ explicit historical session metadata
+ explicit current intraday series
+ run request
→ Phase 14D assembly
→ Phase 14E baseline composition
→ Phase 14F final TOD RVOL composition
→ immutable end-to-end result
```

Phase 14H adds a deterministic reusable **input fixture catalog** for that harness.

It adds no new calculation, no provider, no runtime activation, and no harness behavior. The catalog creates named raw inputs; tests run the actual Phase 14G harness with those inputs.

---

## Goal

Create an offline scenario catalog that supplies stable, complete end-to-end inputs for the actual approved Phase 14G harness.

Each scenario contains:

```text
one raw AlpacaHistoricalBarsPage
one ordered tuple of HistoricalIntradaySessionMetadata
one explicit current IntradayVolumeSeriesInput
one HistoricalToTodRvolRunRequest
expected outcome metadata for deterministic tests
```

The catalog must provide these scenario names in exactly this order:

```text
valid_20_session_baseline
insufficient_history
incomplete_page_collection
historical_session_cutoff_not_reached
historical_invalid_volume
current_invalid_volume
current_identity_mismatch
final_phase_13e_validation_failure
```

The catalog is data-only. It must never call the harness itself.

---

## Core Boundary

```text
Phase 14H catalog:
  constructs deterministic local fixture inputs only

Phase 14G harness:
  runs Phase 14D → Phase 14E → Phase 14F

Phases 14D / 14E / 14F:
  own all eligibility, validation, composition, and calculation outcomes
```

The catalog may declare expected statuses for test assertions, but it must not construct stage-result objects, calculate cumulative volume, calculate RVOL, or fake failures.

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
session assembly, baseline composition, current composition, or RVOL calculation logic
candidate composition, scoring, filtering, or alerts
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

`live_composed` remains gated and reserved/inactive.

---

## Existing Components to Reuse

The fixture catalog may import models and stable status containers only:

```text
market_sentry.data.alpaca_historical_bars_fetcher
  AlpacaHistoricalBarsPage

market_sentry.data.historical_session_assembly
  HistoricalIntradaySessionMetadata
  HistoricalSessionAssemblyStatus

market_sentry.data.historical_baseline_composition
  HistoricalBaselineCompositionStatus

market_sentry.data.current_session_tod_rvol
  CurrentSessionTimeOfDayRvolStatus

market_sentry.data.historical_tod_rvol_harness
  HistoricalToTodRvolRunRequest
  HistoricalToTodRvolRunStatus

market_sentry.data.intraday_bucket_adapter
  IntradayVolumeBar
  IntradayVolumeSeriesInput

market_sentry.data.time_of_day_rvol
  TimeOfDayRelativeVolumeStatus
```

The catalog must **not** import:

```text
run_historical_to_time_of_day_rvol
assemble_historical_sessions_from_page
compose_historical_baseline
compose_current_session_time_of_day_rvol
calculate_cumulative_volume_at_bucket
calculate_time_of_day_relative_volume
HTTP transport modules
Alpaca/FMP fetchers
provider factory
config
live readiness
scanner engine
alert modules
voice modules
candidate builders
```

No fixture provider, no protocol, and no runtime registration is added.

---

## Expected Files

Create:

```text
docs/46_OFFLINE_END_TO_END_TOD_RVOL_SCENARIO_FIXTURE_CATALOG.md
src/market_sentry/data/historical_tod_rvol_scenario_catalog.py
tests/test_historical_tod_rvol_scenario_catalog.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 13, Phase 14A–14G, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Scenario Model

Use one frozen scenario model. Exact name may vary, but retain the responsibilities below.

```python
@dataclass(frozen=True)
class HistoricalTodRvolScenario:
    """Deterministic raw inputs and expected stage statuses for one harness run."""

    name: str
    page: AlpacaHistoricalBarsPage
    historical_metadata_records: tuple[HistoricalIntradaySessionMetadata, ...]
    current_series: IntradayVolumeSeriesInput
    request: HistoricalToTodRvolRunRequest

    expected_harness_status: str
    expected_baseline_status: str
    expected_final_status: str
    expected_time_of_day_status: str | None
    expected_assembly_statuses: tuple[str, ...]
    expected_relative_volume: float | None
```

Expected fields are test-orientation metadata only. They must not be used by production calculations.

---

## Public Catalog Functions

Provide:

```python
def get_historical_tod_rvol_scenarios() -> tuple[HistoricalTodRvolScenario, ...]:
    ...
```

This returns fresh, protected scenario objects in the exact stable order:

```text
valid_20_session_baseline
insufficient_history
incomplete_page_collection
historical_session_cutoff_not_reached
historical_invalid_volume
current_invalid_volume
current_identity_mismatch
final_phase_13e_validation_failure
```

Also provide:

```python
def get_historical_tod_rvol_scenario(name: str) -> HistoricalTodRvolScenario:
    ...
```

Lookup is exact and case-sensitive. Do not trim, normalize, or fuzzy-match scenario names.

Unknown names must raise:

```text
KeyError
```

with the requested scenario name as the key.

Each catalog call must return independently constructed fixture objects. No cache or shared mutable state is allowed.

---

## Fixture Construction Rules

### Common deterministic identity

Use one common valid historical target:

```text
symbol: RVOL
bucket: 09:35
current_session_id: CURRENT-001
timezone: UTC
session window: [09:30, 10:00)
cutoff: 09:35
```

Historical session IDs must be distinct and must not equal:

```text
CURRENT-001
```

Use deterministic historical session IDs, for example:

```text
HIST-01
HIST-02
...
HIST-20
```

Use deterministic sequential calendar dates only as fixture data. The catalog must not add any general calendar inference logic.

### Raw page construction

Raw bars must remain Phase 14A-shaped mappings:

```python
{"t": "<ISO 8601 aware timestamp>", "v": <raw volume>}
```

Use a terminal `Z` or explicit `+00:00` timestamp format consistently for valid fixture bars.

`AlpacaHistoricalBarsPage` inputs must be protected:

```text
requested_symbols is a tuple
bars_by_symbol is immutable
every raw-bar mapping is immutable
raw bar sequences are tuples
```

The catalog must not use mutable dictionaries or lists exposed through returned scenarios.

### Metadata construction

Historical metadata must be tuples of frozen `HistoricalIntradaySessionMetadata` objects.

Current series bars must be tuple-based `IntradayVolumeBar` sequences.

All standard valid scenarios should use:

```text
page_collection_complete=True
page.next_page_token=None
minimum_historical_sessions=20
```

unless the scenario expressly tests the opposite.

---

## Required Scenarios

### 1. `valid_20_session_baseline`

Provide:

```text
20 valid historical sessions
one valid raw bar at or after each historical cutoff
each historical cumulative volume = 100
valid current series cumulative volume = 200
```

Expected outcomes:

```text
assembly:
  20 × OK

baseline:
  OK

final:
  OK

harness:
  OK

time_of_day:
  OK

relative volume:
  2.0
```

This is the catalog’s canonical successful end-to-end case.

---

### 2. `insufficient_history`

Provide:

```text
19 valid historical sessions
each historical cumulative volume = 100
valid current series cumulative volume = 200
```

Expected outcomes:

```text
assembly:
  19 × OK

baseline:
  INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS

final:
  BASELINE_FAILED

harness:
  FINAL_COMPOSITION_FAILED

time_of_day:
  None

relative volume:
  None
```

Do not lower the required minimum to make this scenario pass.

---

### 3. `incomplete_page_collection`

Provide:

```text
20 otherwise-valid historical metadata records
page.next_page_token is a non-null token
page_collection_complete=True
valid current series
```

Expected outcomes:

```text
assembly:
  every record is INCOMPLETE_PAGE_COLLECTION

baseline:
  INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS

final:
  BASELINE_FAILED

harness:
  FINAL_COMPOSITION_FAILED
```

The non-null page token—not a custom catalog validation—must trigger the actual Phase 14D failure.

---

### 4. `historical_session_cutoff_not_reached`

Provide:

```text
20 historical metadata records
19 valid historical session bars at their cutoff
1 historical session bar that is inside its session window but before its cutoff
valid current series
```

Expected outcomes:

```text
one assembly record:
  CUT_OFF_NOT_REACHED

remaining assembly records:
  OK

baseline:
  INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS

final:
  BASELINE_FAILED

harness:
  FINAL_COMPOSITION_FAILED
```

The order of expected assembly statuses must match metadata order.

---

### 5. `historical_invalid_volume`

Provide:

```text
20 historical metadata records
19 valid historical raw bars
1 in-window raw bar at/after cutoff with no v key
valid current series
```

Expected outcomes:

```text
affected assembly record:
  ADAPTER_FAILED

affected adapter result:
  MISSING_RAW_VOLUME

remaining assembly records:
  OK

baseline:
  INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS

final:
  BASELINE_FAILED

harness:
  FINAL_COMPOSITION_FAILED
```

The catalog must not pre-validate the missing `v`. The actual Phase 14D → Phase 14B path must produce it.

---

### 6. `current_invalid_volume`

Provide:

```text
20 valid historical sessions
valid complete page
current series with a bar volume of False
```

Expected outcomes:

```text
assembly:
  20 × OK

baseline:
  OK

final:
  CURRENT_CUMULATIVE_VOLUME_FAILED

harness:
  FINAL_COMPOSITION_FAILED

time_of_day:
  None
```

The catalog must preserve `False` as raw fixture data. It must not coerce it.

---

### 7. `current_identity_mismatch`

Provide:

```text
20 valid historical sessions for symbol RVOL
valid complete page
current series with a different valid symbol, for example OTHER
```

Expected outcomes:

```text
assembly:
  20 × OK

baseline:
  OK

final:
  MISMATCHED_CURRENT_SYMBOL

harness:
  FINAL_COMPOSITION_FAILED

time_of_day:
  None
```

The mismatch must be surfaced by actual Phase 14F identity logic.

---

### 8. `final_phase_13e_validation_failure`

Provide:

```text
20 valid historical sessions
each individual historical raw volume is finite and positive: 1e308
valid current series with finite positive cumulative volume: 1e308
valid complete page
```

Phase 14D and Phase 14E should succeed because each session’s own cumulative volume is finite and positive.

When Phase 13E computes the historical average, summing the 20 individually finite historical values overflows to a non-finite aggregate.

Expected outcomes:

```text
assembly:
  20 × OK

baseline:
  OK

final:
  TIME_OF_DAY_RVOL_FAILED

harness:
  FINAL_COMPOSITION_FAILED

time_of_day:
  INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME

relative volume:
  None
```

This scenario proves the actual final Phase 13E validation layer remains observable without monkeypatching, data repair, or bypassing the approved pipeline.

---

## Immutability and Freshness Requirements

For every catalog scenario:

```text
scenario object is frozen
page requested symbols are immutable
page bars mapping is immutable
every raw bar mapping is immutable
raw-bar sequences are tuples
metadata records are a tuple
current-series bars are a tuple
run request is frozen
```

For separate catalog calls:

```text
scenario instances are new objects
page objects are new objects
metadata tuples are new objects
current-series objects are new objects
raw mappings are not shared mutable state
```

Returned data should be safe to inspect but impossible to mutate through ordinary assignment.

---

## Required Tests

### Catalog-shape and fixture tests

Test:

```text
exact scenario name order
exact lookup behavior
unknown lookup raises KeyError with requested key
each scenario has all expected fields
all scenario names are unique
all fixture objects are frozen / tuple-based / mapping-protected
separate catalog calls produce independently constructed scenarios
attempted mutation of returned mappings fails
```

### Actual end-to-end harness tests

For every scenario:

```text
run the actual run_historical_to_time_of_day_rvol(...)
assert:
  harness status matches expected_harness_status
  baseline status matches expected_baseline_status
  final status matches expected_final_status
  final time_of_day status matches expected_time_of_day_status when present
  final relative volume matches expected_relative_volume when present
  assembly statuses match expected_assembly_statuses exactly
```

Add focused assertions for:

```text
valid:
  final RVOL == 2.0
  20 observations
  final status OK

incomplete page:
  every assembly result is INCOMPLETE_PAGE_COLLECTION

historical cutoff:
  only intended session is CUT_OFF_NOT_REACHED

historical invalid volume:
  intended session is ADAPTER_FAILED
  nested adapter status is MISSING_RAW_VOLUME

current invalid volume:
  Phase 14F retains current cumulative failure
  no final TOD result is created

identity mismatch:
  Phase 14F retains successful current cumulative result
  no final TOD result is created

final Phase 13E failure:
  Phase 14F retains TOD result
  nested TOD status is INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME
```

### Source boundary test

Use AST or focused source inspection to verify the catalog:

```text
does not import or call the harness function
does not import or call Phase 14D assembly function
does not import or call Phase 14E composition function
does not import or call Phase 14F composition function
does not call Phase 13F or Phase 13E functions
does not import HTTP, fetcher, provider, factory, config, runtime, scanner,
alert, voice, candidate, or trading modules
```

The catalog may import approved models and status containers only.

---

## README Note

Update only if useful:

```text
Phase 14H adds a deterministic offline scenario fixture catalog for the existing Phase 14G historical-to-TOD RVOL harness.
Named raw-input scenarios exercise valid history, insufficient/incomplete history, historical and current validation failures, identity mismatch, and a final Phase 13E validation failure.
It does not fetch data, register a runtime provider, or activate live mode.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```

---

## Acceptance Criteria

Phase 14H is complete when:

```text
- eight named scenarios exist in the exact required order;
- scenarios are deterministic, immutable, and rebuilt independently;
- tests run actual Phase 14G with every catalog scenario;
- expected outcomes come from real Phase 14D/14E/14F/13E behavior, not fake stage results;
- the catalog itself does not run the harness or calculate RVOL;
- no runtime, network, provider, candidate, scanner, alert, voice, or trading capability is added;
- the full project suite remains green.
```
