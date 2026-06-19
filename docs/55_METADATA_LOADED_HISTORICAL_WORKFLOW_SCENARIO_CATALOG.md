# Phase 15F — Metadata-Loaded Historical Workflow Scenario Catalog and Harness

## Status

**Planned.** This document defines Phase 15F only.

Phases 15A–15E now provide a complete offline path from collected historical raw pages and an explicit metadata source through the existing manifest/TOD-RVOL workflow.

Phase 15F adds a reusable deterministic scenario catalog and a thin end-to-end scenario harness:

```text
named static metadata-source scenario
+ named historical-page collection scenario
+ named current-series scenario
+ named manifest/harness request scenario
        ↓
Phase 15F thin scenario harness
        ↓
actual Phase 15E
        ↓
inspectable complete workflow artifact
```

This phase adds no new market-data behavior. It packages known offline situations into named reproducible fixtures and runs the already-approved Phase 15E orchestration exactly once per scenario invocation.

---

## Goal

Create:

1. a **data-only scenario catalog** of fresh, deterministic end-to-end inputs for the Phase 15E workflow; and
2. a **thin scenario harness** that calls the real `run_metadata_loaded_historical_workflow(...)` exactly once for one selected scenario and returns both exact artifacts.

The catalog must make the most important outer-workflow states repeatable:

```text
successful complete metadata-loaded multi-page workflow
partial manifest with valid RVOL
invalid metadata source container (mapping)
invalid metadata source container (generator)
valid metadata + capped historical collection
valid metadata + repeated-token historical collection
valid metadata + empty complete-shaped collection
valid metadata + mismatched page requested-symbol tuples
valid metadata + invalid manifest request
valid metadata + invalid current selected volume
incomplete metadata record
missing historical metadata record
```

The catalog is not a market-data source, calendar engine, provider, runtime capability, or test of live behavior.

---

## End-to-End Ownership Boundary

```text
Scenario catalog owns:
  named local deterministic fixture construction
  expected nested diagnostic/status values
  fresh scenario objects on every catalog call

Scenario harness owns:
  one Phase 15E call for one supplied scenario
  exact scenario/result retention
  no result interpretation

Phase 15E owns:
  Phase 15D source load
  conditional Phase 15C workflow bridge

Phase 15D owns:
  source invocation and record-sequence container safety

Phase 15C owns:
  collection composition and conditional Phase 14J execution

Phase 14J / lower stages own:
  manifest validation, historical assembly, baseline construction,
  current-session calculation, and TOD-RVOL results
```

Phase 15F must not add new execution, validation, or classification logic beyond the thin call described in this document.

---

## Hard Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is **not** a trading bot.

Do not add:

```text
runtime activation
provider-factory registration or provider-selection changes
new MARKET_SENTRY_PROVIDER values
CLI flags, reports, polling, scanner-loop, alert, or voice changes
HTTP requests, API clients, transports, fetchers, retries, caching,
WebSockets, streaming, files, JSON/YAML loaders, or environment/config reads
calendar, holiday, early-close, halt, split, or market-session inference
time-zone conversion or normalization
raw-bar parsing, validation, sorting, deduplication, filtering, or repair
metadata-record validation, normalization, filtering, or construction in the harness
new Phase 15D / 15C / 15B / 14J behavior
relative-volume calculation logic
candidate composition, scoring, filtering, alerts, or voice changes
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

No live HTTP calls are permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

## Expected Files

Create:

```text
docs/55_METADATA_LOADED_HISTORICAL_WORKFLOW_SCENARIO_CATALOG.md
src/market_sentry/data/metadata_loaded_historical_workflow_scenario_catalog.py
src/market_sentry/data/metadata_loaded_historical_workflow_scenario_harness.py
tests/test_metadata_loaded_historical_workflow_scenario_catalog.py
tests/test_metadata_loaded_historical_workflow_scenario_harness.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 14A–14K, Phase 15A–15E, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

# Part A — Scenario Catalog

## Catalog Purpose

The catalog is **fixture data only**.

It may construct local static source objects, raw mappings, local pages, collector results, requests, and expected status values. It must not invoke:

```text
load_historical_session_metadata_source
run_metadata_loaded_historical_workflow
run_collected_pages_to_manifest_workflow
compose_collected_historical_pages
run_manifest_to_historical_tod_rvol
adapt_historical_session_manifest
```

No scenario catalog function may execute the actual workflow.

---

## Catalog Public Model

Provide an equivalent frozen data model:

```python
@dataclass(frozen=True)
class MetadataLoadedHistoricalWorkflowScenario:
    """One deterministic complete set of inputs and expected end-to-end artifacts."""

    name: str
    metadata_source: HistoricalSessionMetadataSource
    collection: HistoricalBarsPageCollectionResult
    manifest_request: HistoricalSessionManifestRequest
    current_series: IntradayVolumeSeriesInput
    harness_request: HistoricalToTodRvolRunRequest

    expected_metadata_load_status: str
    expected_workflow_status: str
    expected_workflow_reason: str | None

    expected_bridge_status: str | None
    expected_bridge_reason: str | None
    expected_composition_status: str | None

    expected_coordinator_status: str | None
    expected_manifest_status: str | None
    expected_harness_status: str | None
    expected_final_status: str | None
    expected_time_of_day_status: str | None
    expected_relative_volume: float | None
```

Exact field names may vary, but all responsibilities above must remain explicit.

For a scenario where Phase 15E must not run the Phase 15C bridge:

```text
expected_bridge_status = None
expected_bridge_reason = None
expected_composition_status = None
expected_coordinator_status = None
expected_manifest_status = None
expected_harness_status = None
expected_final_status = None
expected_time_of_day_status = None
expected_relative_volume = None
```

Do not hide lower-stage expected statuses inside opaque scenario-specific assertions.

---

## Catalog Public Functions

Provide:

```python
def get_metadata_loaded_historical_workflow_scenarios(
) -> tuple[MetadataLoadedHistoricalWorkflowScenario, ...]:
    """Return fresh deterministic end-to-end scenarios."""
```

and:

```python
def get_metadata_loaded_historical_workflow_scenario(
    name: str,
) -> MetadataLoadedHistoricalWorkflowScenario:
    """Return one scenario by exact, case-sensitive name."""
```

Unknown names must raise `KeyError(name)`.

Every catalog call must build fresh scenario/input objects. No mutable fixture data may be shared between separate catalog calls.

---

## Scenario Fixture Rules

### Common identity

Use these deterministic local values unless a named scenario intentionally changes one:

```text
symbol = RVOL
bucket = 09:35
current session ID = CURRENT-001
minimum historical sessions = 20
timestamps = aware UTC datetimes in January 2026
```

### Valid historical metadata records

A valid baseline has 20 explicit historical records:

```text
HIST-01 through HIST-20
session days January 2 through January 21
session start 09:30 UTC
session end 10:00 UTC
cutoff 09:35 UTC
is_complete True
```

### Valid multi-page collection

A valid complete collection must contain two source pages. It must prove raw page composition by splitting the first historical session across pages:

```text
page 0:
  Jan 2 09:31 volume 25
  Jan 3–Jan 11 09:35 volume 100

page 1:
  Jan 2 09:35 volume 75
  Jan 12–Jan 21 09:35 volume 100
```

The composed historical cumulative volume for `HIST-01` is therefore:

```text
25 + 75 = 100
```

A valid current series has one `09:35` bar with volume `200`, producing a TOD-RVOL of `2.0` against the 20-session `100` baseline.

### Fixture opacity

The catalog may construct raw mappings because it is fixture data. The Phase 15F harness must not inspect them.

Use fresh raw mapping objects on every catalog call. Protecting source mappings with `MappingProxyType` is encouraged but not mandatory where existing models already protect them.

---

## Required Named Scenarios

Create exactly these names, in exactly this order:

```text
valid_multi_page_metadata_loaded
partial_manifest_multi_page_metadata_loaded
incomplete_metadata_record
missing_historical_metadata_record
invalid_metadata_mapping_no_bridge
invalid_metadata_generator_no_bridge
page_cap_collection_not_composable
repeated_token_collection_not_composable
empty_complete_collection_not_composable
mismatched_page_symbols_not_composable
invalid_manifest_request_workflow_failure
invalid_current_volume_workflow_failure
```

### 1. `valid_multi_page_metadata_loaded`

```text
metadata source:
  StaticHistoricalSessionMetadataSource with 20 valid records

collection:
  complete two-page collection described above

current series:
  valid current 09:35 volume 200
```

Expected:

```text
metadata load status = LOADED
Phase 15E status = WORKFLOW_BRIDGE_RAN
Phase 15E reason = None
Phase 15C status = WORKFLOW_RAN
Phase 15C reason = None
Phase 15B composition status = COMPOSED
Phase 14J coordinator status = OK
manifest status = OK
harness status = OK
final status = OK
TOD-RVOL status = OK
relative volume = 2.0
```

### 2. `partial_manifest_multi_page_metadata_loaded`

Use the valid scenario plus one extra raw metadata mapping missing the required `bucket` field.

Expected:

```text
metadata load status = LOADED
Phase 15E = WORKFLOW_BRIDGE_RAN
Phase 15C = WORKFLOW_RAN
composition = COMPOSED
Phase 14J = MANIFEST_PARTIAL
manifest = PARTIAL
harness = OK
final = OK
TOD-RVOL = OK
relative volume = 2.0
```

The catalog need not duplicate every per-record status field; tests must separately verify the final extra manifest record is `MISSING_REQUIRED_FIELD`.

### 3. `incomplete_metadata_record`

Use 20 otherwise-valid records but mark one raw record:

```text
is_complete = False
```

Expected:

```text
metadata load = LOADED
Phase 15E = WORKFLOW_BRIDGE_RAN
Phase 15C = WORKFLOW_RAN
composition = COMPOSED
Phase 14J = MANIFEST_PARTIAL_AND_HARNESS_FAILED
manifest = PARTIAL
harness = FINAL_COMPOSITION_FAILED
final = BASELINE_FAILED
TOD-RVOL status = None
relative volume = None
```

Tests must verify the affected manifest record carries `INCOMPLETE_SESSION` and only 19 usable metadata records remain.

### 4. `missing_historical_metadata_record`

Use only 19 valid explicit records. Do not infer the missing one.

Expected:

```text
metadata load = LOADED
Phase 15E = WORKFLOW_BRIDGE_RAN
Phase 15C = WORKFLOW_RAN
composition = COMPOSED
Phase 14J = HARNESS_FAILED
manifest = OK
harness = FINAL_COMPOSITION_FAILED
final = BASELINE_FAILED
TOD-RVOL status = None
relative volume = None
```

This proves “record absent” remains opaque in Phase 15D, while downstream baseline sufficiency behaves normally.

### 5. `invalid_metadata_mapping_no_bridge`

Use a local structural source whose method returns a mapping rather than a sequence.

Expected:

```text
metadata load = INVALID_RECORD_SEQUENCE
Phase 15E = METADATA_NOT_LOADED
Phase 15E reason = METADATA_NOT_LOADED:INVALID_RECORD_SEQUENCE
all bridge/composition/coordinator/manifest/harness/final/TOD statuses = None
relative volume = None
```

### 6. `invalid_metadata_generator_no_bridge`

Use a local structural source whose method returns a generator rather than a sequence.

Expected exactly the same top-level outcome as scenario 5.

### 7. `page_cap_collection_not_composable`

Use valid metadata plus one collected page with an unresolved `NEXT` token:

```text
collection status = MAX_PAGE_LIMIT_REACHED
page_collection_complete = False
next_page_token = NEXT
```

Expected:

```text
metadata load = LOADED
Phase 15E = WORKFLOW_BRIDGE_RAN
Phase 15C = COLLECTION_NOT_COMPOSABLE
Phase 15C reason = COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION
composition = INCOMPLETE_COLLECTION
all Phase 14J and lower-workflow statuses = None
relative volume = None
```

### 8. `repeated_token_collection_not_composable`

Use valid metadata plus a structurally repeated-token collection result:

```text
collection status = REPEATED_NEXT_PAGE_TOKEN
page_collection_complete = False
next_page_token = LOOP
```

Expected the same `Phase 15C COLLECTION_NOT_COMPOSABLE` branch as scenario 7, with composition `INCOMPLETE_COLLECTION`.

### 9. `empty_complete_collection_not_composable`

Use valid metadata plus a manually constructed complete-shaped collection with no collected pages:

```text
collection status = COMPLETE
page_collection_complete = True
next_page_token = None
collected_pages = ()
```

Expected:

```text
metadata load = LOADED
Phase 15E = WORKFLOW_BRIDGE_RAN
Phase 15C = COLLECTION_NOT_COMPOSABLE
Phase 15C reason = COLLECTION_NOT_COMPOSABLE:EMPTY_COMPLETE_COLLECTION
composition = EMPTY_COMPLETE_COLLECTION
all Phase 14J and lower-workflow statuses = None
relative volume = None
```

### 10. `mismatched_page_symbols_not_composable`

Use valid metadata plus a complete-shaped two-page collection where the first page has:

```text
requested_symbols = (RVOL,)
```

and the later page has a different ordered tuple, such as:

```text
requested_symbols = (OTHER, RVOL)
```

Expected:

```text
metadata load = LOADED
Phase 15E = WORKFLOW_BRIDGE_RAN
Phase 15C = COLLECTION_NOT_COMPOSABLE
Phase 15C reason = COLLECTION_NOT_COMPOSABLE:MISMATCHED_PAGE_REQUESTED_SYMBOLS
composition = MISMATCHED_PAGE_REQUESTED_SYMBOLS
all Phase 14J and lower-workflow statuses = None
relative volume = None
```

### 11. `invalid_manifest_request_workflow_failure`

Use a valid metadata sequence container and complete valid two-page collection, but make the manifest request invalid:

```text
symbol = " "
```

The raw sequence itself may contain opaque non-mapping records because the invalid target request is the intended downstream failure trigger.

Expected:

```text
metadata load = LOADED
Phase 15E = WORKFLOW_BRIDGE_RAN
Phase 15C = WORKFLOW_RAN
composition = COMPOSED
Phase 14J = MANIFEST_FAILED
manifest = INVALID_TARGET_SYMBOL
harness = FINAL_COMPOSITION_FAILED
final = BASELINE_FAILED
TOD-RVOL status = None
relative volume = None
```

### 12. `invalid_current_volume_workflow_failure`

Use valid metadata and complete two-page collection, but use:

```text
current selected 09:35 volume = False
```

Expected:

```text
metadata load = LOADED
Phase 15E = WORKFLOW_BRIDGE_RAN
Phase 15C = WORKFLOW_RAN
composition = COMPOSED
Phase 14J = HARNESS_FAILED
manifest = OK
harness = FINAL_COMPOSITION_FAILED
final = CURRENT_CUMULATIVE_VOLUME_FAILED
TOD-RVOL status = None
relative volume = None
```

Tests must verify the nested current-bucket result is `INVALID_INTRADAY_VOLUME`.

---

# Part B — Thin Scenario Harness

## Harness Public Model

Create a frozen wrapper:

```python
@dataclass(frozen=True)
class MetadataLoadedHistoricalWorkflowScenarioRun:
    """One exact scenario and one exact Phase 15E result."""

    scenario: MetadataLoadedHistoricalWorkflowScenario
    result: MetadataLoadedHistoricalWorkflowResult
```

## Harness Public Function

Provide:

```python
def run_metadata_loaded_historical_workflow_scenario(
    scenario: MetadataLoadedHistoricalWorkflowScenario,
) -> MetadataLoadedHistoricalWorkflowScenarioRun:
    ...
```

It must do exactly this:

```python
result = run_metadata_loaded_historical_workflow(
    scenario.metadata_source,
    scenario.collection,
    scenario.manifest_request,
    scenario.current_series,
    scenario.harness_request,
)
return MetadataLoadedHistoricalWorkflowScenarioRun(
    scenario=scenario,
    result=result,
)
```

Required behavior:

```text
- calls Phase 15E exactly once;
- passes every scenario input by identity;
- retains exact scenario and result objects;
- creates a fresh frozen wrapper;
- does not inspect or classify the result;
- does not compare result values against scenario expected fields;
- does not catch, wrap, retry, or transform exceptions;
- has no cache or shared mutable state.
```

The harness is not a new business workflow. It is merely a reusable direct call wrapper for catalog scenarios.

---

## Required Tests

### Catalog tests

Test:

```text
exact required scenario names and exact order
exact-name lookup success
unknown/case-changed name raises KeyError(name)
every scenario dataclass is frozen
separate catalog calls produce fresh independent scenario objects
fresh metadata source, collection, request, current series, and harness request objects
raw source records and raw bar mappings are fresh between catalog calls
```

Catalog tests must verify expected fields for all scenario definitions without running the workflow.

### Harness unit tests

Monkeypatch only:

```text
run_metadata_loaded_historical_workflow
```

inside the harness module.

Test:

```text
Phase 15E called exactly once
metadata source forwarded by identity
collection forwarded by identity
manifest request forwarded by identity
current series forwarded by identity
harness request forwarded by identity
returned wrapper retains exact scenario and result
wrapper is frozen
separate runs create independent wrapper objects
exception from Phase 15E propagates unchanged
```

### Actual end-to-end catalog tests

For every scenario returned by the catalog, run the actual Phase 15F harness, which must use the actual Phase 15E orchestration.

Assert:

```text
outer metadata load status equals expected_metadata_load_status
Phase 15E status/reason equals expected_workflow_status/reason

when expected bridge status is None:
  workflow_bridge_result is None

when expected bridge status exists:
  workflow_bridge_result exists
  bridge status/reason match expected values
  composition status matches expected value

when expected coordinator status is None:
  no Phase 14J result exists beneath the bridge

when expected coordinator status exists:
  coordinator, manifest, harness, final, TOD-RVOL statuses match
  relative volume matches expected value
```

Add targeted assertions:

```text
valid_multi_page_metadata_loaded:
  first historical session assembly sees two in-window raw bars
  final RVOL 2.0

partial_manifest_multi_page_metadata_loaded:
  final extra manifest record = MISSING_REQUIRED_FIELD
  20 emitted metadata records remain
  RVOL 2.0

incomplete_metadata_record:
  affected record = INCOMPLETE_SESSION
  19 emitted metadata records remain

missing_historical_metadata_record:
  manifest is OK with 19 emitted records
  no calendar inference occurs
  baseline fails only for insufficient eligible historical sessions

invalid metadata mapping/generator:
  no bridge result exists

page-cap/repeated-token:
  no Phase 14J result exists
  composition remains INCOMPLETE_COLLECTION

empty/mismatched collection:
  no Phase 14J result exists
  exact Phase 15C diagnostic is retained

invalid manifest request:
  manifest request failure remains visible
  no synthetic source-load failure appears

invalid current volume:
  nested current cumulative result status = INVALID_INTRADAY_VOLUME
```

No network, HTTP, runtime, provider, environment, file, or global fixture changes.

### Source-boundary tests

#### Catalog source boundary

The catalog may import input models, static metadata source, relevant stable status containers, and standard-library fixture-construction utilities.

It must not import or call:

```text
run_metadata_loaded_historical_workflow
load_historical_session_metadata_source
run_collected_pages_to_manifest_workflow
compose_collected_historical_pages
run_manifest_to_historical_tod_rvol
adapt_historical_session_manifest
HTTP, transports, providers, factory, config, readiness, runtime,
scanner, alert, voice, candidate, or trading modules
```

#### Harness source boundary

The harness may import only:

```text
MetadataLoadedHistoricalWorkflowScenario
MetadataLoadedHistoricalWorkflowResult
run_metadata_loaded_historical_workflow
standard-library dataclass
```

It must not import or call any lower stage directly and must not inspect:

```text
metadata record mappings
manifest request fields
collection pages
raw bars
result statuses
```

---

## README Note

Update only if useful:

```text
Phase 15F adds a deterministic offline scenario catalog and thin harness for the complete Phase 15E metadata-loaded historical workflow.
Scenarios cover valid, partial, incomplete, invalid-source, non-composable, and nested workflow-failure diagnostics without adding data fetching, calendar inference, runtime activation, or trading/order functionality.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 15F is complete when:

```text
- exactly 12 named fresh deterministic scenarios are available in the required order;
- the catalog itself performs no workflow execution;
- the thin harness calls actual Phase 15E exactly once per scenario;
- all expected outer, bridge, composition, coordinator, manifest, harness, final, and TOD-RVOL diagnostics are testable;
- valid multi-page input proves split historical bars survive composition and produce RVOL 2.0;
- invalid metadata containers stop before Phase 15C;
- non-composable collections stop before Phase 14J while retaining exact diagnostics;
- partial/incomplete/missing metadata and downstream failures remain inspectable;
- no metadata inference, fetcher/transport, provider/runtime, scanner, alert, voice, or trading behavior is added;
- the full project suite remains green.
```
