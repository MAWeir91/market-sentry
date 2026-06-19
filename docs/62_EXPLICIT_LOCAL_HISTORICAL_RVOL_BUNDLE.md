# Phase 16A — Explicit Local Historical RVOL Bundle

## Status

**Planned.** This document defines Phase 16A only.

Phase 15J validates a caller-provided local metadata JSON file using a fixed deterministic historical-bars profile. Phase 16A introduces a separate, explicit **historical RVOL bundle** file that supplies the non-metadata inputs needed by the existing Phase 15H preflight workflow:

```text
explicit metadata JSON path
+ explicit historical RVOL bundle JSON path
        ↓
Phase 15G metadata source
+ Phase 16A bundle loader
        ↓
existing Phase 15H preflight inputs
        ↓
existing Phase 15D–15E / 15C / 14J diagnostics
```

Phase 16A is an offline input adapter only. It does not add a CLI flag, modify Phase 15J’s fixed-profile command, activate a provider, fetch data, scan candidates, or alter RVOL calculations.

A future Phase 16B may expose these two explicit paths through a separate manual CLI operation after this loader is tested and reviewed.

---

## Goal

Create a strict UTF-8 JSON loader for one caller-selected historical RVOL bundle file.

The loader must:

1. accept exactly one caller-owned `pathlib.Path`;
2. read only that path;
3. parse one versioned JSON envelope;
4. recursively decode only exact generic `$datetime` tags;
5. build and return existing typed inputs:
   - `HistoricalBarsPageCollectionResult`;
   - `HistoricalSessionManifestRequest`;
   - `IntradayVolumeSeriesInput`;
   - `HistoricalToTodRvolRunRequest`;
6. preserve opaque raw historical bar mappings and values unchanged;
7. preserve malformed current-series timestamps and volumes for existing downstream validation where the existing model can represent them;
8. not invoke Phase 15H or any workflow;
9. not inspect a metadata file or construct a metadata source;
10. not use configuration, providers, transports, HTTP, scanners, alerts, voice, or network behavior.

The phase must make it possible for a later manual command to pass:

```python
run_local_json_metadata_workflow_preflight(
    metadata_path,
    bundle.collection,
    bundle.manifest_request,
    bundle.current_series,
    bundle.harness_request,
)
```

No new workflow or status model is introduced.

---

## Core Ownership Boundary

```text
Phase 15G owns:
  explicit metadata JSON file read
  metadata envelope validation
  metadata records decoding

Phase 16A owns:
  explicit non-metadata historical RVOL bundle file read
  bundle envelope validation
  generic $datetime tag decoding
  construction of existing typed preflight inputs

Existing model constructors own:
  strict query/request model constraints they already enforce

Phase 13F / Phase 14A–15H existing stages own:
  raw historical-bar interpretation
  raw historical-volume validation
  current intraday timestamp validation
  current intraday volume validation
  collection composition behavior
  metadata/manifest validation
  historical assembly, baseline, final RVOL, and diagnostics
```

Phase 16A must not:

```text
validate or normalize raw historical OHLCV fields
coerce historical bar volumes
coerce current intraday volumes
sort, deduplicate, filter, repair, or fabricate bars
infer sessions, market hours, holidays, half-days, halts, or splits
inspect metadata records
read a metadata JSON file
create a metadata source
run Phase 15H, 15E, 15C, 15B, 14J, or lower stages
calculate RVOL
generate a candidate
change status/reason codes
```

The loader is deliberately a parser and typed-input constructor, not a market-data validator.

---

## Hard Safety Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is **not** a trading bot.

Do not add:

```text
brokerage APIs
order placement
position management
trade execution
buy/sell/enter/exit recommendations
portfolio actions
live provider activation
new MARKET_SENTRY_PROVIDER values
HTTP requests
WebSockets
automatic metadata acquisition
automatic bundle discovery
directory scans
glob/rglob
environment/config reads
CLI flags or runtime wiring
scanner loop integration
alerts or voice playback
persistent storage beyond reading the explicit bundle file
```

No live HTTP calls are permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

## Required Files

Create:

```text
docs/62_EXPLICIT_LOCAL_HISTORICAL_RVOL_BUNDLE.md
src/market_sentry/data/json_historical_rvol_bundle.py
tests/test_json_historical_rvol_bundle.py
```

Do not modify:

```text
README.md
src/market_sentry/main.py
src/market_sentry/local_json_preflight_cli.py
src/market_sentry/local_json_preflight_report_export.py
Phase 14A–14K
Phase 15A–15L
provider/config/factory/readiness modules
transport/fetcher modules
scanner modules
alert modules
voice modules
fixture scenario catalogs/harnesses
metadata JSON source behavior
workflow behavior
```

Phase 16A has no CLI or user-facing runtime command yet.

---

## Public Surface

Create:

```python
class JsonHistoricalRvolBundleError(ValueError):
    """Raised for invalid local historical RVOL bundle envelopes or structures."""
```

Create a frozen result model:

```python
@dataclass(frozen=True)
class LocalHistoricalRvolBundle:
    """Explicit local non-metadata inputs for one existing preflight run."""

    path: Path
    collection: HistoricalBarsPageCollectionResult
    manifest_request: HistoricalSessionManifestRequest
    current_series: IntradayVolumeSeriesInput
    harness_request: HistoricalToTodRvolRunRequest
```

Provide:

```python
def load_local_historical_rvol_bundle(
    path: Path,
) -> LocalHistoricalRvolBundle:
    """Load one explicit local RVOL bundle into existing typed workflow inputs."""
```

Required behavior:

```text
- `path` must be an actual pathlib.Path instance;
- retain the exact caller-owned Path object;
- read exactly that path using UTF-8;
- read the file on every invocation; no cache;
- do not resolve, absolutize, expanduser, expand variables, glob, rglob,
  scan directories, select fallback files, or create files/directories;
- return a fresh frozen bundle object for each successful call;
- create fresh typed inputs on each successful call;
- do not call a workflow function.
```

Non-`Path` values must raise:

```python
TypeError("path must be a pathlib.Path.")
```

---

## File and JSON Error Policy

The loader must allow these standard errors to propagate unchanged:

```text
FileNotFoundError
PermissionError
IsADirectoryError
UnicodeDecodeError
json.JSONDecodeError
```

Do not catch, wrap, retry, or remap them.

Existing typed model constructor errors may propagate unchanged. In particular, strict invalid query values may produce existing `AlpacaHistoricalBarsFetchError` errors.

Phase 16A’s own structural/envelope errors must use only `JsonHistoricalRvolBundleError` with these stable messages:

```text
INVALID_ENVELOPE_ROOT
MISSING_SCHEMA_VERSION
UNSUPPORTED_SCHEMA_VERSION
MISSING_REQUIRED_FIELD:<path>
INVALID_MAPPING:<path>
INVALID_SEQUENCE:<path>
INVALID_STRING_OR_NULL:<path>
INVALID_INTEGER:<path>
INVALID_BOOLEAN:<path>
```

Examples:

```text
MISSING_REQUIRED_FIELD:collection
INVALID_MAPPING:collection.request
INVALID_SEQUENCE:collection.collected_pages
MISSING_REQUIRED_FIELD:current_series.bars
INVALID_SEQUENCE:current_series.bars
INVALID_MAPPING:collection.collected_pages[0].page.bars_by_symbol
INVALID_STRING_OR_NULL:collection.next_page_token
INVALID_INTEGER:collection.collected_pages[0].index
INVALID_BOOLEAN:collection.page_collection_complete
```

The parser must never use `assert` for user-controlled file content.

---

## JSON Envelope

The root must be a JSON object:

```json
{
  "schema_version": 1,
  "collection": { },
  "manifest_request": { },
  "current_series": { },
  "harness_request": { }
}
```

Requirements:

```text
- root must be a JSON object;
- `schema_version` must exist;
- schema version must be exactly the real integer 1;
- bool, float, string, null, and any integer other than 1 are unsupported;
- `collection`, `manifest_request`, `current_series`, and `harness_request`
  must all exist and be JSON objects;
- extra root keys are allowed and ignored;
- unknown keys inside nested payloads are allowed and ignored;
- bundle field key names are case-sensitive.
```

Phase 16A has no envelope `kind` field. `schema_version: 1` is sufficient.

---

## Generic `$datetime` Decoding

Before typed input construction, recursively decode generic exact tags:

```json
{"$datetime": "2026-01-02T09:35:00Z"}
```

Rules must match Phase 15G behavior:

```text
- only a mapping containing exactly one key named `$datetime` qualifies;
- the tag value must be a string;
- a terminal `Z` may be mechanically converted to `+00:00` before parsing;
- parse with datetime.fromisoformat;
- decoded datetime is returned unchanged;
- naive datetimes remain naive;
- fixed offsets remain fixed offsets;
- invalid timestamp string leaves the original mapping unchanged;
- non-string `$datetime` leaves the original mapping unchanged;
- mappings with extra keys leave the original mapping unchanged;
- lists recurse into elements;
- all other mappings recurse by value.
```

Do not normalize time zones, attach time zones, or apply calendar/session rules.

Typed fields that require a real datetime for object construction are specified below. Current-series bar timestamps are intentionally not prevalidated and can remain non-datetime values for Phase 13F ownership.

---

# Bundle Schema

## `collection`

`collection` must be an object:

```json
{
  "request": {
    "symbols": ["RVOL"],
    "initial_query": {
      "timeframe": "1Min",
      "start": "2026-01-02T09:30:00Z",
      "end": "2026-01-21T10:00:00Z",
      "limit": 1000,
      "page_token": null,
      "sort": "asc"
    },
    "max_pages": 5
  },
  "collected_pages": [],
  "status": "COMPLETE",
  "page_collection_complete": true,
  "next_page_token": null,
  "reason": null
}
```

Required keys:

```text
request
collected_pages
status
page_collection_complete
next_page_token
reason
```

### `collection.request`

Required mapping keys:

```text
symbols
initial_query
max_pages
```

`symbols` must be a JSON array. Pass its values through unchanged to `HistoricalBarsPageCollectionRequest`, which owns its current constructor behavior.

`max_pages` must be a real JSON integer, not bool. Pass it to the existing constructor unchanged.

### Query mappings

Both `collection.request.initial_query` and every collected page’s `query` must be a mapping with required keys:

```text
timeframe
start
end
limit
page_token
sort
```

Requirements:

```text
- timeframe/start/end/sort must be strings;
- page_token must be string or null;
- limit must be a real integer, not bool;
- use `AlpacaHistoricalBarsQuery(...)` directly;
- do not normalize strings;
- existing query constructor errors propagate unchanged.
```

### `collection.collected_pages`

Must be a JSON array. Each entry must be an object with required keys:

```text
index
query
page
```

`index` must be a real JSON integer, not bool.

### Collected page `page`

Each `page` must be a mapping with required keys:

```text
requested_symbols
bars_by_symbol
next_page_token
```

Requirements:

```text
- `requested_symbols` must be a JSON array;
- `bars_by_symbol` must be a JSON object;
- every bars-by-symbol value must be a JSON array;
- every raw bar array element must be a JSON object;
- `next_page_token` must be a string or null;
- use `AlpacaHistoricalBarsPage(...)` directly;
- raw bar mapping keys and values are opaque and must be forwarded unchanged.
```

Do not require raw historical bar keys such as `t`, `v`, `o`, `h`, `l`, or `c`. Existing later stages own those validations.

### Collection status and optional strings

`collection.status` must be a JSON string.

`collection.page_collection_complete` must be a JSON boolean.

Non-boolean values for `collection.page_collection_complete` must raise:

```text
INVALID_BOOLEAN:collection.page_collection_complete
```

`collection.next_page_token` must be string or null.

`collection.reason` must be string or null.

Build the existing:

```python
HistoricalBarsPageCollectionResult(
    request=...,
    collected_pages=...,
    status=...,
    page_collection_complete=...,
    next_page_token=...,
    reason=...,
)
```

Do not interpret whether the status and completeness values agree. Existing Phase 15B owns that behavior.

---

## `manifest_request`

`manifest_request` must be an object with required keys:

```text
symbol
bucket
current_session_id
```

Pass values unchanged to:

```python
HistoricalSessionManifestRequest(
    symbol=value,
    bucket=value,
    current_session_id=value,
)
```

Do not require strings here. Existing Phase 14I owns target request validation and must retain diagnostics such as invalid target symbol/bucket/current session ID.

---

## `current_series`

`current_series` must be an object with required keys:

```text
symbol
session_id
bucket
cutoff_timestamp
bars
```

`bars` must be a JSON array. Every current bar must be a mapping with required keys:

```text
timestamp
volume
```

Pass values unchanged to:

```python
IntradayVolumeBar(
    timestamp=value,
    volume=value,
)
```

then:

```python
IntradayVolumeSeriesInput(
    symbol=value,
    session_id=value,
    bucket=value,
    cutoff_timestamp=value,
    bars=tuple(...),
)
```

Do not require current-series identity values to be strings. Do not require `cutoff_timestamp` or individual bar `timestamp` values to be decoded datetimes. Do not coerce volume values.

This ensures existing Phase 13F owns:

```text
invalid timestamp
mismatched timezone
duplicate/out-of-order timestamp
invalid/non-finite/non-positive volume
no bars through cutoff
```

---

## `harness_request`

`harness_request` must be an object with required keys:

```text
symbol
bucket
current_session_id
page_collection_complete
minimum_historical_sessions
```

Pass values unchanged to:

```python
HistoricalToTodRvolRunRequest(
    symbol=value,
    bucket=value,
    current_session_id=value,
    page_collection_complete=value,
    minimum_historical_sessions=value,
)
```

Do not require strings, booleans, or integers here beyond required-key presence. Existing lower stages own these semantics.

The `harness_request.page_collection_complete` value remains pass-through. Phase 16A does not type-validate that field.

---

# Example Valid Bundle

This is illustrative only. It omits most historical bars for brevity.

```json
{
  "schema_version": 1,
  "collection": {
    "request": {
      "symbols": ["RVOL"],
      "initial_query": {
        "timeframe": "1Min",
        "start": "2026-01-02T09:30:00Z",
        "end": "2026-01-21T10:00:00Z",
        "limit": 1000,
        "page_token": null,
        "sort": "asc"
      },
      "max_pages": 5
    },
    "collected_pages": [
      {
        "index": 0,
        "query": {
          "timeframe": "1Min",
          "start": "2026-01-02T09:30:00Z",
          "end": "2026-01-21T10:00:00Z",
          "limit": 1000,
          "page_token": "p0",
          "sort": "asc"
        },
        "page": {
          "requested_symbols": ["RVOL"],
          "bars_by_symbol": {
            "RVOL": [
              {
                "t": "2026-01-02T09:31:00Z",
                "v": 25,
                "o": 1.0,
                "h": 1.0,
                "l": 1.0,
                "c": 1.0
              }
            ]
          },
          "next_page_token": null
        }
      }
    ],
    "status": "COMPLETE",
    "page_collection_complete": true,
    "next_page_token": null,
    "reason": null
  },
  "manifest_request": {
    "symbol": "RVOL",
    "bucket": "09:35",
    "current_session_id": "CURRENT-001"
  },
  "current_series": {
    "symbol": "RVOL",
    "session_id": "CURRENT-001",
    "bucket": "09:35",
    "cutoff_timestamp": {
      "$datetime": "2026-01-31T09:35:00Z"
    },
    "bars": [
      {
        "timestamp": {
          "$datetime": "2026-01-31T09:35:00Z"
        },
        "volume": 200
      }
    ]
  },
  "harness_request": {
    "symbol": "RVOL",
    "bucket": "09:35",
    "current_session_id": "CURRENT-001",
    "page_collection_complete": true,
    "minimum_historical_sessions": 20
  }
}
```

The separate Phase 15G metadata file still contains the historical session metadata records.

---

## Identity and Immutability

The loader must retain:

```text
exact caller Path object
fresh HistoricalBarsPageCollectionResult
fresh HistoricalBarsPageCollectionRequest
fresh HistoricalBarsCollectedPage objects
fresh AlpacaHistoricalBarsQuery objects
fresh AlpacaHistoricalBarsPage objects
fresh HistoricalSessionManifestRequest
fresh IntradayVolumeSeriesInput
fresh IntradayVolumeBar objects
fresh HistoricalToTodRvolRunRequest
```

Existing page models may protect raw mapping objects. Phase 16A must not mutate parsed JSON payloads after construction.

Separate successful loads from the same file must return:

```text
distinct LocalHistoricalRvolBundle objects
distinct typed input objects
equal value content where the file has not changed
```

No cache, singleton, registry, global mutable fixture, or path-based memoization is allowed.

---

## Required Tests

Create `tests/test_json_historical_rvol_bundle.py`.

### Construction and path tests

Test:

```text
path must be Path, not str
exact Path object retained
missing file propagates FileNotFoundError unchanged
directory path propagates IsADirectoryError unchanged
invalid UTF-8 propagates UnicodeDecodeError unchanged
malformed JSON propagates json.JSONDecodeError unchanged
file read occurs on every call; no cache
separate successful loads return fresh bundle and typed-input objects
bundle model is frozen
```

### Envelope and structural tests

Test every stable Phase 16A error family, including:

```text
root array → INVALID_ENVELOPE_ROOT
missing schema_version → MISSING_SCHEMA_VERSION
schema_version false, 1.0, "1", 2 → UNSUPPORTED_SCHEMA_VERSION
missing collection / manifest_request / current_series / harness_request
→ MISSING_REQUIRED_FIELD:<path>

non-mapping required sections → INVALID_MAPPING:<path>
non-sequence symbols / collected_pages / raw-bars / current bars
→ INVALID_SEQUENCE:<path>

invalid page token / collection next token / reason value
→ INVALID_STRING_OR_NULL:<path>

bool/float index, bool/float query limit, bool/float max_pages
→ INVALID_INTEGER:<path>

non-boolean collection.page_collection_complete
→ INVALID_BOOLEAN:collection.page_collection_complete
```

Test query structural fields and existing constructor errors separately. Do not change existing `AlpacaHistoricalBarsQuery` error behavior.

### Decoder and opaque-value tests

Test:

```text
exact generic $datetime tag decodes to datetime
terminal Z decodes to aware UTC datetime
fixed offset remains fixed offset
naive datetime remains naive
invalid/non-string/extra-key datetime tags remain mappings
decoder applies recursively through current bar lists
```

Test that the loader preserves opaque raw historical bars:

```text
raw historical bar custom fields survive
raw historical bar `v: false` survives unchanged
raw historical bar text/invalid values are not coerced or rejected by loader
```

Test that current-series invalid values remain owned downstream:

```text
invalid current bar timestamp tag remains mapping
volume false remains false
loader succeeds
existing Phase 13F calculation later returns INVALID_INTRADAY_TIMESTAMP
```

### Actual workflow compatibility test

Use:

```text
real valid Phase 15I metadata fixture bytes written to a separate metadata file
real Phase 16A valid bundle file representing the matching 20-session,
two-page collection/current series/harness inputs
```

Then call the existing Phase 15H function in the test:

```python
run_local_json_metadata_workflow_preflight(
    metadata_path,
    bundle.collection,
    bundle.manifest_request,
    bundle.current_series,
    bundle.harness_request,
)
```

Assert:

```text
bundle remains an input-only adapter
metadata load = LOADED
workflow status = WORKFLOW_BRIDGE_RAN
composition = COMPOSED
coordinator = OK
final TOD-RVOL status = OK
relative volume = 2.0
```

Add a second compatibility test with an invalid current `volume: false` in the bundle:

```text
loader succeeds
metadata source still loads
existing downstream final status is CURRENT_CUMULATIVE_VOLUME_FAILED
nested current cumulative volume status is INVALID_INTRADAY_VOLUME
```

This proves Phase 16A does not take ownership of existing volume validation.

### Source-boundary tests

Use AST or focused source inspection to prove the Phase 16A production module:

```text
imports only approved standard library and existing input models
does not import Phase 15H, Phase 15E, Phase 15C, Phase 15B, Phase 14J,
the metadata source, provider/factory/config/readiness, scanner, alerts,
voice, HTTP, transport, live candidate, or trading modules
does not import or use Phase 15I scenario catalogs/harnesses
does not call workflow functions
does not use resolve, absolute, expanduser, glob, rglob, mkdir,
environment reads, network calls, or caching
does not coerce raw historical bars or current volumes
```

---

## README

Do not modify README. Phase 16A does not add a user-facing CLI command.

---

## Validation

Run:

```powershell
python -m pytest tests/test_json_historical_rvol_bundle.py
python -m pytest
python -m market_sentry
python -m market_sentry --local-json-preflight .\does-not-exist.json
python -m market_sentry --local-json-preflight-report .\report.txt
```

Then rerun:

```text
fixture
composed_fixture
Alpaca placeholder
both live_composed placeholder checks
both readiness checks
```

No Phase 16A CLI command is added yet.

---

## Acceptance Criteria

Phase 16A is complete when:

```text
- an explicit local bundle file yields the four existing Phase 15H non-metadata inputs;
- the loader preserves the exact caller Path and reads no other path;
- strict UTF-8/JSON/envelope/container structural errors are stable;
- exact generic $datetime tags decode without timezone normalization;
- raw historical bar values and current-series volume/timestamp values are not silently corrected;
- existing downstream stages retain ownership of semantic validation and diagnostics;
- a real valid metadata file plus a real valid bundle reaches final TOD-RVOL 2.0 through existing Phase 15H;
- an invalid current bundle volume reaches existing INVALID_INTRADAY_VOLUME diagnostics downstream;
- no CLI, provider, runtime, network, scanner, alert, voice, or trading behavior changes;
- the full project suite remains green.
```
