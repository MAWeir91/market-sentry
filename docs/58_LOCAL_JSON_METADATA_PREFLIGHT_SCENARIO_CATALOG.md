# Phase 15I — Local JSON Metadata Preflight Scenario Catalog and Harness

## Status

**Planned.** This document defines Phase 15I only.

Phase 15H provides a manually invoked wrapper from one explicit JSON file path through the existing metadata-loaded historical workflow. Phase 15G owns JSON parsing; Phase 15D–15E and lower stages own all diagnostics.

Phase 15I adds deterministic **JSON-file fixtures** and a thin **fixture materialization + preflight harness**:

```text
named JSON-file scenario
+ caller-supplied target Path
        ↓
write exact fixture bytes when applicable
        ↓
actual Phase 15H preflight once
        ↓
exact preflight artifact or unchanged exception
```

It adds no new metadata source behavior, no workflow logic, no status classification, no runtime activation, and no live data behavior.

---

## Goal

Create:

1. a data-only catalog of fresh named JSON-file preflight scenarios; and
2. a thin harness that writes a scenario’s exact byte payload to one caller-supplied local target path when the scenario supplies one, then calls the existing Phase 15H preflight exactly once.

The catalog must make the important JSON-file and end-to-end workflow outcomes reproducible:

```text
valid local JSON → final TOD-RVOL 2.0
partial manifest with valid RVOL
non-decoded malformed $datetime cutoff tag
empty JSON records list
page-cap collection
repeated-token collection
invalid manifest request
invalid current volume
unsupported schema version
malformed JSON
invalid UTF-8
missing JSON file
```

The catalog is not a runtime source selector, directory discovery mechanism, local metadata editor, market-calendar engine, or live-data feature.

---

## Ownership Boundary

```text
Phase 15I catalog owns:
  named fixture byte payloads
  explicit workflow input fixtures
  expected nested outcomes
  fresh scenario construction

Phase 15I harness owns:
  writing exact scenario bytes to exactly one caller-selected target Path
  one Phase 15H preflight call
  exact scenario/path/preflight artifact retention
  no result interpretation

Phase 15H owns:
  constructing the Phase 15G source
  one Phase 15E call
  exact preflight artifact retention

Phase 15G owns:
  file read
  UTF-8 JSON parsing
  envelope validation
  generic $datetime decoding

Phase 15D–15E and lower stages own:
  source-load diagnostics
  composition and workflow gates
  manifest diagnostics
  RVOL diagnostics
```

Phase 15I must not:

```text
parse JSON
decode $datetime values
inspect JSON envelope mappings
inspect raw metadata mappings or fields
inspect the manifest request
inspect collection pages, raw bars, current series fields, or result statuses
call Phase 15G, 15D, 15E, 15C, 15B, 14J, or lower stages directly
reclassify any source, manifest, or RVOL diagnostic
create source substitutions or fallback fixture data
read files after writing them
catch, wrap, retry, or transform exceptions
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
environment/config reads
automatic path lookup
directory scans, recursive search, globbing, file selection, or fallback files
HTTP requests, API clients, transports, fetchers, retries, caching,
WebSockets, or streaming
calendar, holiday, early-close, halt, split, or market-session inference
time-zone conversion or normalization
metadata-record validation, normalization, filtering, or construction in the harness
raw-bar parsing, validation, sorting, deduplication, filtering, or repair
new Phase 15H / 15G / 15E behavior
relative-volume calculation logic
candidate composition, scoring, filtering, alerts, or voice changes
persistent storage beyond writing one caller-selected scenario fixture target
order APIs, order placement, trade execution, or trading recommendations
```

No live HTTP calls are permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

## Expected Files

Create:

```text
docs/58_LOCAL_JSON_METADATA_PREFLIGHT_SCENARIO_CATALOG.md
src/market_sentry/data/local_json_metadata_preflight_scenario_catalog.py
src/market_sentry/data/local_json_metadata_preflight_scenario_harness.py
tests/test_local_json_metadata_preflight_scenario_catalog.py
tests/test_local_json_metadata_preflight_scenario_harness.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 14A–14K, Phase 15A–15H, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

# Part A — Data-Only Scenario Catalog

## Catalog Rule

The catalog must construct fixture data only. It must not write a file or execute any workflow.

It must not import or call:

```text
run_local_json_metadata_workflow_preflight
JsonHistoricalSessionMetadataFileSource
load_historical_session_metadata_source
run_metadata_loaded_historical_workflow
run_collected_pages_to_manifest_workflow
compose_collected_historical_pages
run_manifest_to_historical_tod_rvol
adapt_historical_session_manifest
```

The catalog may use standard-library `json.dumps(...)` to serialize its own fixture payload mappings into fresh UTF-8 bytes. This is fixture construction only, not source parsing.

---

## Catalog Public Model

Provide an equivalent frozen data model:

```python
@dataclass(frozen=True)
class LocalJsonMetadataPreflightScenario:
    """One deterministic local-file payload, explicit workflow inputs, and expected outcome."""

    name: str
    fixture_bytes: bytes | None

    collection: HistoricalBarsPageCollectionResult
    manifest_request: HistoricalSessionManifestRequest
    current_series: IntradayVolumeSeriesInput
    harness_request: HistoricalToTodRvolRunRequest

    expected_exception_type: type[BaseException] | None
    expected_exception_message: str | None

    expected_metadata_load_status: str | None
    expected_outer_status: str | None
    expected_outer_reason: str | None

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

Exact field names may vary, but all responsibilities must remain explicit.

### Scenarios that raise before a preflight artifact

For file/source-error scenarios:

```text
expected_exception_type != None
expected_metadata_load_status = None
expected_outer_status = None
expected_outer_reason = None
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

### Scenarios that return a preflight artifact

For all returned-result scenarios:

```text
expected_exception_type = None
expected_exception_message = None
```

The catalog must not hide lower-stage diagnostics behind a single scenario-specific boolean.

---

## Catalog Public Functions

Provide:

```python
def get_local_json_metadata_preflight_scenarios(
) -> tuple[LocalJsonMetadataPreflightScenario, ...]:
    """Return fresh deterministic JSON-file preflight scenarios."""
```

and:

```python
def get_local_json_metadata_preflight_scenario(
    name: str,
) -> LocalJsonMetadataPreflightScenario:
    """Return one scenario by exact, case-sensitive name."""
```

Unknown names must raise:

```python
KeyError(name)
```

Every catalog call must build fresh scenario/input objects, fresh payload bytes, fresh raw JSON fixture mappings, and fresh raw historical bar mappings. No mutable fixture data may be shared between separate catalog calls.

---

## Common Fixture Values

Use these deterministic local values unless a scenario deliberately changes one:

```text
symbol = RVOL
bucket = 09:35
current session ID = CURRENT-001
minimum historical sessions = 20
timestamps = aware UTC values in January 2026
```

### Valid JSON metadata records

A normal fixture has 20 JSON raw record objects:

```text
HIST-01 through HIST-20
session days January 2 through January 21
session start 09:30 UTC
session end 10:00 UTC
cutoff 09:35 UTC
is_complete true
```

Every timestamp in normal JSON fixture records must use the generic representation:

```json
{"$datetime": "2026-01-02T09:30:00Z"}
```

### Valid multi-page collection

A normal complete collection must contain two source pages and prove historical page composition by splitting the first session:

```text
page 0:
  Jan 2 09:31 volume 25
  Jan 3–Jan 11 09:35 volume 100

page 1:
  Jan 2 09:35 volume 75
  Jan 12–Jan 21 09:35 volume 100
```

The historical cumulative volume for `HIST-01` is therefore:

```text
25 + 75 = 100
```

A current series with a single `09:35` bar of volume `200` produces final TOD-RVOL `2.0` against the 20-session `100` baseline.

---

## Required Scenario Names and Exact Order

Create exactly these 12 names, in this exact order:

```text
valid_json_complete_multi_page
partial_manifest_json_complete_multi_page
invalid_cutoff_datetime_json
empty_records_json
page_cap_json_collection_not_composable
repeated_token_json_collection_not_composable
invalid_manifest_request_json
invalid_current_volume_json
unsupported_schema_json_error
malformed_json_error
invalid_utf8_json_error
missing_json_file_error
```

### 1. `valid_json_complete_multi_page`

Fixture bytes: valid UTF-8 version-1 JSON envelope with 20 valid generic `$datetime` records.

Expected:

```text
exception = None
metadata load = LOADED
Phase 15E outer = WORKFLOW_BRIDGE_RAN / None
Phase 15C bridge = WORKFLOW_RAN / None
composition = COMPOSED
Phase 14J coordinator = OK
manifest = OK
harness = OK
final = OK
TOD-RVOL = OK
relative volume = 2.0
```

### 2. `partial_manifest_json_complete_multi_page`

Fixture bytes: normal 20 valid JSON records plus one extra raw record mapping missing required `bucket`.

Expected:

```text
exception = None
metadata load = LOADED
outer = WORKFLOW_BRIDGE_RAN / None
bridge = WORKFLOW_RAN / None
composition = COMPOSED
coordinator = MANIFEST_PARTIAL
manifest = PARTIAL
harness = OK
final = OK
TOD-RVOL = OK
relative volume = 2.0
```

Targeted test must verify:

```text
the final extra manifest record status = MISSING_REQUIRED_FIELD
20 emitted metadata records remain
```

### 3. `invalid_cutoff_datetime_json`

Fixture bytes: normal 20 valid JSON records except the first record’s `cutoff_timestamp` is:

```json
{"$datetime": "not-a-datetime"}
```

That tag is intentionally non-decoded and must remain a raw mapping through Phase 15G.

Expected:

```text
exception = None
metadata load = LOADED
outer = WORKFLOW_BRIDGE_RAN / None
bridge = WORKFLOW_RAN / None
composition = COMPOSED
coordinator = MANIFEST_PARTIAL_AND_HARNESS_FAILED
manifest = PARTIAL
harness = FINAL_COMPOSITION_FAILED
final = BASELINE_FAILED
TOD-RVOL = None
relative volume = None
```

Targeted test must verify:

```text
first manifest record = INVALID_CUTOFF_TIMESTAMP
19 emitted metadata records remain
```

### 4. `empty_records_json`

Fixture bytes: valid version-1 JSON envelope with:

```json
"records": []
```

Expected:

```text
exception = None
metadata load = LOADED
outer = WORKFLOW_BRIDGE_RAN / None
bridge = WORKFLOW_RAN / None
composition = COMPOSED
coordinator = MANIFEST_FAILED
manifest = NO_VALID_METADATA
harness = FINAL_COMPOSITION_FAILED
final = BASELINE_FAILED
TOD-RVOL = None
relative volume = None
```

This proves an empty valid JSON list is a source-load success and remains a downstream baseline/manifest condition, not a source-envelope error.

### 5. `page_cap_json_collection_not_composable`

Fixture bytes: normal valid JSON envelope.

Collection:

```text
status = MAX_PAGE_LIMIT_REACHED
page_collection_complete = False
next_page_token = NEXT
```

Expected:

```text
exception = None
metadata load = LOADED
outer = WORKFLOW_BRIDGE_RAN / None
bridge = COLLECTION_NOT_COMPOSABLE
bridge reason = COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION
composition = INCOMPLETE_COLLECTION
coordinator/manifest/harness/final/TOD-RVOL = None
relative volume = None
```

### 6. `repeated_token_json_collection_not_composable`

Fixture bytes: normal valid JSON envelope.

Collection:

```text
status = REPEATED_NEXT_PAGE_TOKEN
page_collection_complete = False
next_page_token = LOOP
```

Expected exactly the same returned workflow branch as scenario 5:

```text
metadata load = LOADED
outer = WORKFLOW_BRIDGE_RAN / None
bridge = COLLECTION_NOT_COMPOSABLE
bridge reason = COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION
composition = INCOMPLETE_COLLECTION
coordinator/manifest/harness/final/TOD-RVOL = None
relative volume = None
```

### 7. `invalid_manifest_request_json`

Fixture bytes: normal valid JSON envelope.

Manifest request:

```text
symbol = " "
```

Expected:

```text
exception = None
metadata load = LOADED
outer = WORKFLOW_BRIDGE_RAN / None
bridge = WORKFLOW_RAN / None
composition = COMPOSED
coordinator = MANIFEST_FAILED
manifest = INVALID_TARGET_SYMBOL
harness = FINAL_COMPOSITION_FAILED
final = BASELINE_FAILED
TOD-RVOL = None
relative volume = None
```

### 8. `invalid_current_volume_json`

Fixture bytes: normal valid JSON envelope.

Current series selected `09:35` bar:

```text
volume = False
```

Expected:

```text
exception = None
metadata load = LOADED
outer = WORKFLOW_BRIDGE_RAN / None
bridge = WORKFLOW_RAN / None
composition = COMPOSED
coordinator = HARNESS_FAILED
manifest = OK
harness = FINAL_COMPOSITION_FAILED
final = CURRENT_CUMULATIVE_VOLUME_FAILED
TOD-RVOL = None
relative volume = None
```

Targeted test must verify the nested current cumulative-volume result is:

```text
INVALID_INTRADAY_VOLUME
```

### 9. `unsupported_schema_json_error`

Fixture bytes:

```json
{"schema_version": 2, "records": []}
```

Expected:

```text
exception type = JsonHistoricalSessionMetadataFileSourceError
exception message = UNSUPPORTED_SCHEMA_VERSION
all returned-result expected fields = None
```

No preflight wrapper artifact exists.

### 10. `malformed_json_error`

Fixture bytes must be syntactically malformed UTF-8 text, such as:

```text
{"schema_version": 1, "records": [
```

Expected:

```text
exception type = json.JSONDecodeError
exception message = None
all returned-result expected fields = None
```

No preflight wrapper artifact exists.

### 11. `invalid_utf8_json_error`

Fixture bytes must be invalid UTF-8 bytes, such as:

```text
b"\xff\xfe\xfa"
```

Expected:

```text
exception type = UnicodeDecodeError
exception message = None
all returned-result expected fields = None
```

No preflight wrapper artifact exists.

### 12. `missing_json_file_error`

Fixture bytes:

```text
None
```

The harness must not write a file for this scenario. The caller/test must supply a fresh nonexistent target path.

Expected:

```text
exception type = FileNotFoundError
exception message = None
all returned-result expected fields = None
```

No preflight wrapper artifact exists.

---

# Part B — Thin Fixture Materialization and Preflight Harness

## Harness Public Model

Provide a frozen wrapper:

```python
@dataclass(frozen=True)
class LocalJsonMetadataPreflightScenarioRun:
    """One exact scenario, target path, and exact Phase 15H artifact."""

    scenario: LocalJsonMetadataPreflightScenario
    path: Path
    result: LocalJsonMetadataWorkflowPreflightResult
```

## Harness Public Function

Provide:

```python
def run_local_json_metadata_preflight_scenario(
    scenario: LocalJsonMetadataPreflightScenario,
    path: Path,
) -> LocalJsonMetadataPreflightScenarioRun:
    ...
```

The harness must do exactly this:

```python
if scenario.fixture_bytes is not None:
    path.write_bytes(scenario.fixture_bytes)

result = run_local_json_metadata_workflow_preflight(
    path,
    scenario.collection,
    scenario.manifest_request,
    scenario.current_series,
    scenario.harness_request,
)

return LocalJsonMetadataPreflightScenarioRun(
    scenario=scenario,
    path=path,
    result=result,
)
```

Required behavior:

```text
- write fixture bytes exactly once only when fixture_bytes is not None;
- write to exactly the caller-supplied path;
- do not create parent directories;
- do not resolve, expand, scan, glob, derive, or otherwise alter the path;
- do not write a fixture for missing_json_file_error;
- call Phase 15H exactly once after any required successful write;
- forward exact scenario inputs by identity;
- retain exact scenario, path, and preflight result objects;
- create a fresh frozen wrapper;
- do not read the file after writing;
- do not inspect or classify the result;
- do not compare result values against scenario expected fields;
- do not catch, wrap, retry, or transform file/preflight exceptions;
- have no cache or shared mutable state.
```

The harness is a fixture utility. Callers are responsible for supplying a writable existing parent directory, and for supplying a nonexistent target path for `missing_json_file_error`.

---

## Identity and Freshness

Phase 15I must preserve:

```text
exact scenario object supplied by caller
exact target Path object supplied by caller
exact collection object from scenario
exact manifest request from scenario
exact current series from scenario
exact harness request from scenario
exact Phase 15H result object returned by preflight
```

The catalog must make fresh independent scenarios for every catalog call. The harness must make fresh run-wrapper objects for every successful invocation.

No cache, global fixture store, or shared mutable state is permitted.

---

## Error Policy

The harness catches nothing.

The following must propagate unchanged:

```text
OSError from path.write_bytes
FileNotFoundError from missing scenario target
UnicodeDecodeError
json.JSONDecodeError
JsonHistoricalSessionMetadataFileSourceError
FileNotFoundError / envelope / record-level exceptions from Phase 15H
ValueError or custom exceptions from Phase 15H or lower stages
```

No wrapper result is returned on an exceptional path.

---

## Required Tests

### Catalog tests

Test:

```text
exact required scenario names and exact order
exact-name lookup success
unknown/case-changed name raises KeyError(name)
every scenario model is frozen
separate catalog calls create fresh independent scenario objects
fresh collection/request/current/harness objects across calls
fresh payload bytes and fresh raw JSON fixture mappings across calls
all expected fields match the exact required scenario outcomes
catalog does not import or call Phase 15H or any workflow execution function
```

For scenario payload checks, tests may parse fixture bytes in the **test module**. The catalog production module must not parse its payload after constructing it.

### Harness unit tests

Monkeypatch only:

```text
run_local_json_metadata_workflow_preflight
```

inside the harness module.

Test:

```text
fixture bytes are written exactly once to the exact supplied path
fixture write occurs before Phase 15H call
Phase 15H called exactly once
collection forwarded by identity
manifest request forwarded by identity
current series forwarded by identity
harness request forwarded by identity
exact scenario/path/result retained
wrapper is frozen
separate successful runs create independent wrappers
Phase 15H exception propagates unchanged
```

For `fixture_bytes is None`:

```text
no write occurs
Phase 15H is still called once with the exact target path
```

Test a write failure by using a monkeypatched Path-like object only if compatible with the harness typing, or use a deterministic filesystem failure. Do not add exception handling to the harness.

### Actual end-to-end catalog tests

For every catalog scenario:

1. obtain a fresh scenario;
2. create a fresh caller-selected target path under `tmp_path`;
3. invoke the real Phase 15I harness;
4. for expected-error scenarios, assert the exact exception type and any exact required message;
5. for returned-result scenarios, assert every expected outer and nested status.

Assert:

```text
metadata load status equals expected_metadata_load_status
Phase 15E outer status/reason equals expected_outer_status/reason

when expected_bridge_status is None:
  no returned result exists because the scenario is expected to raise

when expected_bridge_status exists:
  Phase 15C bridge exists
  bridge status/reason match expected values
  composition status matches expected value

when expected_coordinator_status is None:
  no Phase 14J result exists beneath the bridge

when expected_coordinator_status exists:
  coordinator, manifest, harness, final, TOD-RVOL statuses match
  relative volume matches expected value
```

Add targeted assertions:

```text
valid_json_complete_multi_page:
  first historical session assembly sees two in-window raw bars
  final RVOL 2.0

partial_manifest_json_complete_multi_page:
  final extra record = MISSING_REQUIRED_FIELD
  20 emitted metadata records remain
  RVOL 2.0

invalid_cutoff_datetime_json:
  first record = INVALID_CUTOFF_TIMESTAMP
  19 emitted metadata records remain
  baseline fails downstream

empty_records_json:
  source/load succeeds
  manifest = NO_VALID_METADATA
  no source-envelope error is synthesized

page-cap/repeated-token:
  no Phase 14J result exists
  composition = INCOMPLETE_COLLECTION
  exact Phase 15C reason retained

invalid_manifest_request_json:
  manifest failure remains nested after normal JSON source load

invalid_current_volume_json:
  nested current cumulative-volume result = INVALID_INTRADAY_VOLUME

unsupported/malformed/invalid-UTF8/missing:
  no Phase 15H result wrapper exists
```

No network, HTTP, runtime, provider, environment, file discovery, or global fixture changes.

### Source-boundary tests

#### Catalog source boundary

The catalog may import:

```text
standard-library dataclass/datetime/json tools
fixture input models
stable status containers
JsonHistoricalSessionMetadataFileSourceError for expected exception type
```

It must not import or call:

```text
run_local_json_metadata_workflow_preflight
JsonHistoricalSessionMetadataFileSource
load_historical_session_metadata_source
run_metadata_loaded_historical_workflow
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
LocalJsonMetadataPreflightScenario
LocalJsonMetadataWorkflowPreflightResult
run_local_json_metadata_workflow_preflight
standard-library dataclass/pathlib
```

It must not import/call JSON parsing, JSON file source, Phase 15G, Phase 15D, Phase 15E, Phase 15C, Phase 15B, Phase 14I, Phase 14J, or lower stages.

It must not inspect:

```text
fixture bytes
metadata mappings
manifest request fields
collection pages
raw bars
preflight result fields
statuses
```

The one permitted fixture payload operation is forwarding `scenario.fixture_bytes` directly into `path.write_bytes(...)`.

---

## README Note

Update only if useful:

```text
Phase 15I adds a deterministic local JSON preflight scenario catalog and thin fixture harness. The catalog covers JSON source and downstream workflow diagnostics through the existing Phase 15H preflight wrapper without adding file discovery, runtime activation, network data, or trading/order functionality.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 15I is complete when:

```text
- exactly 12 fresh deterministic local JSON preflight scenarios exist in the required order;
- the catalog itself never writes files or executes preflight/workflow code;
- the harness writes exact fixture bytes only to the caller-selected target Path and calls Phase 15H exactly once;
- source-file exceptions remain unchanged and result-bearing scenarios preserve exact nested diagnostics;
- valid JSON multi-page input proves final RVOL 2.0;
- partial, invalid-tag, empty-record, non-composable, invalid-manifest, and invalid-current-volume outcomes remain attributable to their existing owners;
- unsupported schema, malformed JSON, invalid UTF-8, and missing-file scenarios raise unchanged expected exceptions;
- no metadata inference, fetcher/transport, provider/runtime, scanner, alert, voice, or trading behavior is added;
- the full project suite remains green.
```
