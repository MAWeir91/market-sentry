# Phase 14K — Offline Manifest-to-Harness Workflow Scenario Catalog

## Status

**Planned.** This document defines Phase 14K only.

Phase 14I validates raw historical-session manifest records. Phase 14J coordinates Phase 14I and the Phase 14G historical-to-time-of-day RVOL harness. Phase 14K adds a deterministic, reusable **input fixture catalog** for the full workflow.

```text
named workflow fixture inputs
→ actual Phase 14J coordinator in tests
→ actual Phase 14I manifest adapter
→ actual Phase 14G harness
→ actual Phase 14D / 14E / 14F outcomes
```

The catalog creates raw input data plus expected outcome metadata only. It must not run the coordinator, call individual stages, calculate RVOL, or add runtime behavior.

---

## Goal

Create a pure offline scenario catalog that supplies stable full-workflow inputs:

```text
raw manifest records
manifest request
raw historical bars page
current intraday series
harness request
expected outcome metadata
```

The catalog must provide these exact named scenarios in this exact order:

```text
valid_manifest_valid_rvol
partial_manifest_valid_rvol
invalid_manifest_empty_harness_input
duplicate_manifest_records
incomplete_historical_page
historical_cutoff_not_reached
current_invalid_volume
current_identity_mismatch
final_phase_13e_validation_failure
```

Every scenario is executed by tests through the actual Phase 14J coordinator. The catalog itself is data-only.

---

## Core Boundary

```text
Phase 14K catalog:
  creates deterministic raw inputs and expected-outcome metadata only

Phase 14J:
  calls Phase 14I then Phase 14G exactly once
  owns coordinator-level classification

Phase 14I:
  owns manifest validation, diagnostics, duplicate policy, and emitted metadata

Phase 14G:
  owns historical assembly, baseline composition, current-session composition,
  final TOD-RVOL behavior, and harness diagnostics
```

The catalog must not create stage-result artifacts, call stages, inspect runtime state, repair inputs, or calculate expected RVOL dynamically.

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
raw-bar parsing or historical-page inspection logic
manifest adapter execution
manifest-to-harness coordinator execution
Phase 14D / 14E / 14F direct execution
RVOL calculation
candidate composition, scoring, filtering, or alerts
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

`live_composed` remains gated and reserved/inactive.

---

## Existing Components to Reuse

The catalog may import **models and stable status containers only**:

```text
market_sentry.data.historical_session_manifest
  HistoricalSessionManifestRequest
  HistoricalSessionManifestStatus
  HistoricalSessionManifestRecordStatus

market_sentry.data.historical_tod_rvol_harness
  HistoricalToTodRvolRunRequest
  HistoricalToTodRvolRunStatus

market_sentry.data.manifest_to_harness_orchestrator
  ManifestToHarnessStatus

market_sentry.data.alpaca_historical_bars_fetcher
  AlpacaHistoricalBarsPage

market_sentry.data.intraday_bucket_adapter
  IntradayVolumeBar
  IntradayVolumeSeriesInput

market_sentry.data.historical_session_assembly
  HistoricalSessionAssemblyStatus

market_sentry.data.historical_baseline_composition
  HistoricalBaselineCompositionStatus

market_sentry.data.current_session_tod_rvol
  CurrentSessionTimeOfDayRvolStatus

market_sentry.data.time_of_day_rvol
  TimeOfDayRelativeVolumeStatus
```

Do not import or call:

```text
adapt_historical_session_manifest
run_manifest_to_historical_tod_rvol
run_historical_to_time_of_day_rvol
assemble_historical_sessions_from_page
compose_historical_baseline
compose_current_session_time_of_day_rvol
calculate_cumulative_volume_at_bucket
calculate_time_of_day_relative_volume
raw bar adapters
HTTP transports
fetchers other than the page input model above
provider factory
config
live readiness
fixture providers
LiveCandidateBuilder
LiveComposedMarketDataProvider
scanner engine
alert modules
voice modules
candidate modules
```

The catalog must never call any stage function.

---

## Expected Files

Create:

```text
docs/49_OFFLINE_MANIFEST_TO_HARNESS_WORKFLOW_SCENARIO_CATALOG.md
src/market_sentry/data/manifest_to_harness_scenario_catalog.py
tests/test_manifest_to_harness_scenario_catalog.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 13, Phase 14A–14J, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

## Public Scenario Model

Use one frozen scenario model. Exact name may vary, but retain all responsibilities below.

```python
@dataclass(frozen=True)
class ManifestToHarnessWorkflowScenario:
    """Deterministic complete workflow inputs and expected artifacts."""

    name: str
    raw_manifest_records: tuple[object, ...]
    manifest_request: HistoricalSessionManifestRequest
    page: AlpacaHistoricalBarsPage
    current_series: IntradayVolumeSeriesInput
    harness_request: HistoricalToTodRvolRunRequest

    expected_coordinator_status: str
    expected_coordinator_reason: str | None
    expected_manifest_status: str
    expected_manifest_record_statuses: tuple[str, ...]
    expected_harness_status: str
    expected_baseline_status: str
    expected_final_status: str
    expected_time_of_day_status: str | None
    expected_assembly_statuses: tuple[str, ...]
    expected_relative_volume: float | None
```

Expected fields are test metadata only. They must never be used by calculations or stage behavior.

---

## Public Catalog Functions

Provide:

```python
def get_manifest_to_harness_workflow_scenarios() -> tuple[ManifestToHarnessWorkflowScenario, ...]:
    ...
```

Return scenarios in the exact required stable order:

```text
valid_manifest_valid_rvol
partial_manifest_valid_rvol
invalid_manifest_empty_harness_input
duplicate_manifest_records
incomplete_historical_page
historical_cutoff_not_reached
current_invalid_volume
current_identity_mismatch
final_phase_13e_validation_failure
```

Also provide:

```python
def get_manifest_to_harness_workflow_scenario(
    name: str,
) -> ManifestToHarnessWorkflowScenario:
    ...
```

Lookup is exact and case-sensitive. Do not trim, normalize, or fuzzy-match scenario names.

Unknown names must raise:

```text
KeyError
```

with the requested scenario name as the key.

Every call must build fresh protected fixture objects. No cache and no shared mutable state are allowed.

---

## Fixture Construction Rules

### Common valid identity

Use the following standard target identity:

```text
symbol: RVOL
bucket: 09:35
current session ID: CURRENT-001
timezone: UTC
session window: [09:30, 10:00)
cutoff: 09:35
minimum historical sessions: 20
```

Use deterministic distinct historical session IDs:

```text
HIST-01
HIST-02
...
HIST-20
```

Use deterministic sequential calendar dates only as local fixture data. The catalog must not add calendar inference logic.

### Raw manifest record construction

Each valid raw manifest record is a protected mapping with:

```text
symbol
session_id
bucket
session_start_timestamp
session_end_timestamp
cutoff_timestamp
is_complete
```

Extra fields may appear in scenarios specifically designed to prove extras are ignored by Phase 14I, but extra fields must never affect expected workflow outcomes.

### Raw historical page construction

Raw historical bars must retain the Phase 14A shape:

```python
{"t": "<ISO 8601 aware timestamp>", "v": <raw volume>}
```

Valid timestamp strings should use one consistent aware UTC representation such as terminal `Z` or `+00:00`.

`AlpacaHistoricalBarsPage` fixtures must be protected:

```text
requested_symbols tuple
bars_by_symbol immutable
every raw-bar mapping immutable
raw-bar sequences tuples
```

### Current series construction

Use tuple-based `IntradayVolumeBar` values inside `IntradayVolumeSeriesInput`.

### General freshness / immutability

For every catalog call:

```text
new scenario objects
new manifest request objects
new raw manifest mapping objects
new raw historical page object
new page mapping and raw bar mapping objects
new current series object
new harness request object
```

Returned objects must be safe to inspect but not mutable through ordinary assignment.

---

## Required Scenarios

### 1. `valid_manifest_valid_rvol`

Provide:

```text
20 valid raw manifest records
complete raw historical page
each historical cumulative volume = 100
valid current cumulative volume = 200
```

Expected outputs:

```text
coordinator:
  status = OK
  reason = None

manifest:
  status = OK
  20 record statuses = OK

harness:
  status = OK
  20 assembly statuses = OK
  baseline = OK
  final = OK
  TOD = OK
  relative volume = 2.0
```

This is the canonical fully valid workflow scenario.

---

### 2. `partial_manifest_valid_rvol`

Provide:

```text
20 valid raw manifest records
+ 1 invalid raw manifest record missing bucket
complete raw historical page for the 20 valid sessions
valid current series
```

Expected outputs:

```text
coordinator:
  status = MANIFEST_PARTIAL
  reason = MANIFEST_PARTIAL

manifest:
  status = PARTIAL
  20 record statuses = OK
  1 record status = MISSING_REQUIRED_FIELD

harness:
  status = OK
  20 assembly statuses = OK
  baseline = OK
  final = OK
  TOD = OK
  relative volume = 2.0
```

The Phase 14I output must contain exactly 20 emitted metadata records. The invalid manifest record is never translated into metadata and does not prevent a successful harness run.

---

### 3. `invalid_manifest_empty_harness_input`

Provide:

```text
invalid manifest request symbol, for example " "
at least one intentionally non-mapping raw manifest input
otherwise-valid local page and current series
valid harness request
```

Expected outputs:

```text
coordinator:
  status = MANIFEST_FAILED
  reason = MANIFEST_FAILED:INVALID_TARGET_SYMBOL

manifest:
  status = INVALID_TARGET_SYMBOL
  record statuses = ()
  emitted metadata = ()

harness:
  status = FINAL_COMPOSITION_FAILED
  assembly statuses = ()
  baseline = INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
  final = BASELINE_FAILED
  TOD = None
  relative volume = None
```

This proves the invalid manifest request takes ownership of the coordinator classification while Phase 14J still calls the real harness with the exact empty metadata tuple emitted by Phase 14I.

---

### 4. `duplicate_manifest_records`

Provide:

```text
20 valid unique raw manifest records
+ 2 otherwise-valid raw records with the same duplicate historical session ID
complete raw historical page for the 20 unique valid sessions
valid current series
```

Expected outputs:

```text
coordinator:
  status = MANIFEST_PARTIAL
  reason = MANIFEST_PARTIAL

manifest:
  status = PARTIAL
  20 record statuses = OK
  2 record statuses = DUPLICATE_HISTORICAL_SESSION_ID
  emitted metadata = 20 records

harness:
  status = OK
  20 assembly statuses = OK
  baseline = OK
  final = OK
  TOD = OK
  relative volume = 2.0
```

No duplicate occurrence may become metadata. The harness sees only the 20 exact emitted unique records.

---

### 5. `incomplete_historical_page`

Provide:

```text
20 valid manifest records
page.next_page_token is non-null
harness request page_collection_complete=True
valid current series
```

Expected outputs:

```text
coordinator:
  status = HARNESS_FAILED
  reason = HARNESS_FAILED:FINAL_COMPOSITION_FAILED

manifest:
  status = OK
  20 record statuses = OK

harness:
  status = FINAL_COMPOSITION_FAILED
  every assembly status = INCOMPLETE_PAGE_COLLECTION
  baseline = INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
  final = BASELINE_FAILED
  TOD = None
  relative volume = None
```

The raw page continuation token must cause the actual Phase 14D failure. The catalog must not add its own page-completeness logic.

---

### 6. `historical_cutoff_not_reached`

Provide:

```text
20 valid manifest records
19 raw historical bars at their cutoff
1 raw historical bar inside its session window but before its cutoff
complete page
valid current series
```

Expected outputs:

```text
coordinator:
  status = HARNESS_FAILED
  reason = HARNESS_FAILED:FINAL_COMPOSITION_FAILED

manifest:
  status = OK
  20 record statuses = OK

harness:
  status = FINAL_COMPOSITION_FAILED
  exactly one assembly status = CUT_OFF_NOT_REACHED
  remaining assembly statuses = OK
  baseline = INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
  final = BASELINE_FAILED
  TOD = None
  relative volume = None
```

Expected assembly-status order must match the order of emitted metadata.

---

### 7. `current_invalid_volume`

Provide:

```text
20 valid manifest records
complete valid historical page
current series whose selected bar volume is False
```

Expected outputs:

```text
coordinator:
  status = HARNESS_FAILED
  reason = HARNESS_FAILED:FINAL_COMPOSITION_FAILED

manifest:
  status = OK
  20 record statuses = OK

harness:
  status = FINAL_COMPOSITION_FAILED
  20 assembly statuses = OK
  baseline = OK
  final = CURRENT_CUMULATIVE_VOLUME_FAILED
  TOD = None
  relative volume = None
```

The catalog must preserve `False` unchanged. Actual Phase 13F/14F validation owns the failure.

---

### 8. `current_identity_mismatch`

Provide:

```text
20 valid RVOL manifest records
complete valid RVOL historical page
current series for another valid symbol, for example OTHER
```

Expected outputs:

```text
coordinator:
  status = HARNESS_FAILED
  reason = HARNESS_FAILED:FINAL_COMPOSITION_FAILED

manifest:
  status = OK
  20 record statuses = OK

harness:
  status = FINAL_COMPOSITION_FAILED
  20 assembly statuses = OK
  baseline = OK
  final = MISMATCHED_CURRENT_SYMBOL
  TOD = None
  relative volume = None
```

The mismatch must arise from actual Phase 14F behavior. The catalog must not detect or repair it.

---

### 9. `final_phase_13e_validation_failure`

Provide:

```text
20 valid manifest records
each historical raw bar volume = 1e308
current selected bar volume = 1e308
complete page
```

Each individual historical session should be valid through Phase 14D and Phase 14E.

Expected outputs:

```text
coordinator:
  status = HARNESS_FAILED
  reason = HARNESS_FAILED:FINAL_COMPOSITION_FAILED

manifest:
  status = OK
  20 record statuses = OK

harness:
  status = FINAL_COMPOSITION_FAILED
  20 assembly statuses = OK
  baseline = OK
  final = TIME_OF_DAY_RVOL_FAILED
  TOD = INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME
  relative volume = None
```

This proves that final Phase 13E aggregate validation remains observable through the complete workflow without a fake result, monkeypatch, or bypass.

---

## Required Tests

### Catalog shape and immutability tests

Test:

```text
exact scenario name order
all names unique
exact case-sensitive lookup
unknown lookup raises KeyError with the requested name as its key
all scenario models frozen
raw manifest sequence is tuple-based
raw manifest mappings are protected
page requested symbols are tuple-based
page mappings and raw-bar mappings are protected
current series bars are tuples
separate catalog calls rebuild independent objects
no shared mutable state
```

### Actual workflow tests

For **every** scenario, call the actual Phase 14J coordinator:

```python
run_manifest_to_historical_tod_rvol(
    scenario.raw_manifest_records,
    scenario.manifest_request,
    scenario.page,
    scenario.current_series,
    scenario.harness_request,
)
```

Assert:

```text
coordinator status and reason match expected metadata
manifest status matches expected metadata
manifest record status tuple matches expected metadata exactly
harness status matches expected metadata
assembly status tuple matches expected metadata exactly
baseline status matches expected metadata
final status matches expected metadata
TOD status matches expected metadata when present
relative volume matches expected metadata when present
```

Add focused artifact assertions:

```text
valid:
  coordinator OK
  20 emitted metadata records
  20 baseline observations
  final RVOL == 2.0

partial:
  manifest PARTIAL
  emitted metadata count = 20
  harness remains OK
  coordinator MANIFEST_PARTIAL

invalid request:
  manifest record results = ()
  emitted metadata tuple empty
  actual harness still returns its artifact
  coordinator MANIFEST_FAILED

duplicates:
  both intended duplicate record results are DUPLICATE_HISTORICAL_SESSION_ID
  neither is emitted
  harness retains 20 valid metadata inputs and succeeds

incomplete page:
  every assembly result is INCOMPLETE_PAGE_COLLECTION

historical cutoff:
  only intended session is CUT_OFF_NOT_REACHED

current invalid volume:
  no final TOD result exists

identity mismatch:
  successful current cumulative artifact remains available
  no final TOD result exists

final Phase 13E failure:
  final TOD artifact remains available
  nested TOD status is INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME
```

### Source boundary test

Use AST or focused source inspection to verify the catalog:

```text
does not import or call the Phase 14I adapter
does not import or call the Phase 14J coordinator
does not import or call the Phase 14G harness
does not import or call direct Phase 14D / 14E / 14F functions
does not import or call Phase 13 calculators
does not import HTTP, fetcher, transport, provider, factory, config,
readiness, runtime, scanner, alert, voice, candidate, or trading modules
```

The catalog may import only the approved models and stable status containers.

---

## README Note

Update only if useful:

```text
Phase 14K adds a deterministic offline workflow scenario catalog for the existing Phase 14I → Phase 14J → Phase 14G path.
Named raw-input scenarios exercise complete, partial, invalid-manifest, duplicate-manifest, historical-page, historical-cutoff, current-session, identity-mismatch, and final TOD-RVOL validation outcomes.
It does not fetch data, register a runtime provider, activate live mode, or add trading/order behavior.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 14K is complete when:

```text
- nine named scenarios exist in the exact required order;
- catalog fixtures are deterministic, protected, and rebuilt independently;
- tests run the actual Phase 14J coordinator for every scenario;
- every expected outcome arises from real Phase 14I / 14J / 14G / 14D / 14E / 14F / 13E behavior;
- the catalog itself is data-only and never calls any project stage;
- no runtime, network, provider, candidate, scanner, alert, voice, or trading capability is added;
- the full project suite remains green.
```
