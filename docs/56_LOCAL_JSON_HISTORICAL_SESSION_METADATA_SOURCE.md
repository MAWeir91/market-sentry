# Phase 15G — Explicit Local JSON Historical Session Metadata Source

## Status

**Planned.** This document defines Phase 15G only.

Phase 15D defines the offline `HistoricalSessionMetadataSource` contract and a static in-memory implementation. Phase 15E conditionally routes a successfully loaded sequence into the existing historical TOD-RVOL workflow.

Phase 15G adds one concrete, user-controlled local file implementation:

```text
explicit JSON file path
→ strict UTF-8 JSON envelope read
→ generic tagged-value decoding
→ ordered raw manifest-record list
→ existing Phase 15D source interface
```

It does not infer calendar facts, scan directories, select files automatically, activate a provider, or change the runtime.

---

## Goal

Create a local JSON-backed metadata source that:

1. receives an explicit `Path` supplied by the caller;
2. reads exactly that one local file using strict UTF-8;
3. parses a small versioned JSON envelope;
4. returns the exact parsed `records` list from that file load;
5. uses one generic reserved JSON tag to represent Python `datetime` values;
6. leaves all manifest record field validation to the existing Phase 14I adapter;
7. remains directly compatible with the existing Phase 15D loader and Phase 15E workflow;
8. performs no configuration discovery, no network I/O, and no runtime registration.

The intended path is:

```text
caller-selected JSON file
→ JsonHistoricalSessionMetadataFileSource
→ Phase 15D sequence-container load
→ Phase 15E metadata gate
→ existing Phase 15C / 15B / 14J workflow
```

This is a manually curated local metadata source only.

---

## Why JSON Needs a Generic Datetime Tag

JSON does not have a native datetime type, while the existing Phase 14I manifest adapter deliberately requires Python `datetime` instances for:

```text
session_start_timestamp
session_end_timestamp
cutoff_timestamp
```

Phase 15G therefore supports one **generic JSON value representation**:

```json
{
  "$datetime": "2026-01-02T09:30:00Z"
}
```

When an object is exactly one key named `$datetime` whose value is a string that `datetime.fromisoformat(...)` can parse, the JSON decoder converts that value into a Python `datetime`.

This is a representation codec, not manifest validation:

```text
Phase 15G owns:
  JSON parsing
  exact generic $datetime tag decoding
  file and envelope safety

Phase 14I owns:
  timestamp field validity
  timezone awareness
  timezone agreement
  session windows
  cutoff placement
  symbol/session/bucket/completeness validation
  duplicate validation
```

Phase 15G does not know or care which raw record field contains a tagged datetime object. It never reads keys such as:

```text
symbol
session_id
bucket
session_start_timestamp
session_end_timestamp
cutoff_timestamp
is_complete
```

A malformed or non-exact `$datetime` tag remains an ordinary raw mapping and is later handled by Phase 14I when it appears in a manifest field.

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
manifest record validation
raw-bar parsing, validation, sorting, deduplication, filtering, or repair
Phase 15A collection calls
Phase 15B composition calls
Phase 15C / 15D / 15E workflow calls
Phase 14I / 14J / 14G / 14D / 14E / 14F calls
relative-volume calculation
candidate composition, scoring, filtering, alerts, or voice changes
persistent storage beyond reading the one caller-selected source file
order APIs, order placement, trade execution, or trading recommendations
```

No live HTTP calls are permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

## Existing Components to Reuse

Reuse only:

```text
market_sentry.data.historical_session_manifest
  HistoricalSessionManifestRequest
```

Use standard-library modules only:

```text
collections.abc
dataclasses
datetime
json
pathlib
typing
```

Do not import or call:

```text
load_historical_session_metadata_source
StaticHistoricalSessionMetadataSource
adapt_historical_session_manifest
HistoricalSessionManifestResult
historical_session_assembly
alpaca_historical_bars_fetcher
alpaca_historical_bars_adapter
historical_bars_page_collector
collected_historical_pages_composer
collected_pages_to_manifest_workflow
metadata_loaded_historical_workflow
manifest_to_harness_orchestrator
historical_tod_rvol_harness
intraday_bucket_adapter
time_of_day_rvol
HTTP transport modules
fetchers
provider factory
config
live readiness
relative-volume modules
fixture providers
LiveCandidateBuilder
LiveComposedMarketDataProvider
scanner engine
alert modules
voice modules
```

The production Phase 15G module must never import downstream workflow, provider, runtime, or scanner code.

---

## Expected Files

Create:

```text
docs/56_LOCAL_JSON_HISTORICAL_SESSION_METADATA_SOURCE.md
src/market_sentry/data/json_historical_session_metadata_source.py
tests/test_json_historical_session_metadata_source.py
```

Modify only if useful:

```text
README.md
```

Do not modify Phase 14A–14K, Phase 15A–15F, runtime, factory, CLI, config, readiness, provider, transport, scanner, alert, voice, or fixture modules.

---

# JSON File Contract

## Caller-selected path

The source accepts one caller-provided `Path` object:

```python
JsonHistoricalSessionMetadataFileSource(path=Path(r"C:\market-sentry\data\metadata.json"))
```

Rules:

```text
- require an actual pathlib.Path instance;
- do not coerce a str into Path;
- do not call resolve(), absolute(), expanduser(), expandvars(), glob(), or rglob();
- do not derive a path from request fields, environment, config, current date, or defaults;
- read exactly the path object supplied at construction;
- do not cache parsed file data;
- each source load opens and parses the file again.
```

A relative `Path` is caller-owned and follows ordinary `Path.read_text(...)` behavior. The source must not reinterpret it.

A non-`Path` constructor value must raise `TypeError`.

---

## Versioned envelope

A valid file contains one UTF-8 JSON object:

```json
{
  "schema_version": 1,
  "records": [
    {
      "symbol": "RVOL",
      "session_id": "HIST-01",
      "bucket": "09:35",
      "session_start_timestamp": {"$datetime": "2026-01-02T09:30:00Z"},
      "session_end_timestamp": {"$datetime": "2026-01-02T10:00:00Z"},
      "cutoff_timestamp": {"$datetime": "2026-01-02T09:35:00Z"},
      "is_complete": true,
      "source_reason": "manually curated"
    }
  ],
  "source_name": "manual historical metadata"
}
```

Envelope requirements:

```text
root must be a JSON object;
schema_version must exist;
schema_version must be exactly the real integer 1, not bool;
records must exist;
records must be a JSON array;
additional envelope keys are permitted and ignored;
record list elements are opaque to Phase 15G;
empty records array is valid and returns an empty list.
```

The source must return the parsed `records` list object exactly as created by that one JSON load. It must not tuple-wrap, copy, filter, sort, normalize, or validate the list or its elements.

---

## Generic `$datetime` tagged values

A parsed JSON object converts to `datetime` only if it is exactly:

```json
{"$datetime": "<isoformat string>"}
```

Examples that decode:

```json
{"$datetime": "2026-01-02T09:30:00Z"}
{"$datetime": "2026-01-02T09:30:00+00:00"}
{"$datetime": "2026-01-02T09:30:00-05:00"}
{"$datetime": "2026-01-02T09:30:00"}
```

Rules:

```text
- decode with datetime.fromisoformat();
- do not convert or normalize the resulting datetime;
- preserve a naive decoded datetime as naive so Phase 14I can reject it;
- preserve a non-UTC fixed offset as parsed so Phase 14I can compare timezones;
- do not associate the tag with a particular manifest field;
- do not reject a bad tag at source level;
- a tag string that cannot be parsed remains the original mapping;
- an object with extra keys remains the original mapping;
- a $datetime value that is not a string remains the original mapping.
```

Examples that remain raw mappings:

```json
{"$datetime": "not-a-datetime"}
{"$datetime": 123}
{"$datetime": "2026-01-02T09:30:00Z", "note": "extra key"}
```

This preserves Phase 14I’s responsibility for field-specific diagnostics. For example, a non-decoded object used as `cutoff_timestamp` will become `INVALID_CUTOFF_TIMESTAMP` in Phase 14I.

---

# Public Source

## Error class and stable envelope errors

Provide:

```python
class JsonHistoricalSessionMetadataFileSourceError(ValueError):
    ...
```

Use stable exact error messages:

```text
INVALID_ENVELOPE_ROOT
MISSING_SCHEMA_VERSION
UNSUPPORTED_SCHEMA_VERSION
MISSING_RECORDS_FIELD
INVALID_RECORDS_CONTAINER
```

These are source-level file/envelope errors only.

```text
INVALID_ENVELOPE_ROOT
  parsed JSON root is not a mapping

MISSING_SCHEMA_VERSION
  root mapping lacks schema_version

UNSUPPORTED_SCHEMA_VERSION
  schema_version is not exactly real int 1

MISSING_RECORDS_FIELD
  root mapping lacks records

INVALID_RECORDS_CONTAINER
  records is not a list
```

Do not use this custom error class for ordinary file/parsing errors. The following must propagate unchanged from the standard library:

```text
FileNotFoundError
PermissionError
IsADirectoryError
UnicodeDecodeError
json.JSONDecodeError
```

No retry, fallback file, wrapping, or recovery behavior is allowed.

---

## Public model

Provide:

```python
@dataclass(frozen=True)
class JsonHistoricalSessionMetadataFileSource:
    path: Path

    def load_raw_manifest_records(
        self,
        request: HistoricalSessionManifestRequest,
    ) -> Sequence[object]:
        ...
```

Requirements:

```text
- satisfy the structural HistoricalSessionMetadataSource protocol;
- store the exact caller-provided Path object;
- be frozen;
- do not inspect the request or any request field;
- read exactly one file per call;
- return the exact decoded records list object from that load;
- return a fresh parsed list and fresh nested JSON values for each separate load call;
- do not cache;
- do not mutate records, nested mappings, tags, or request.
```

No global source registration is permitted.

---

# Required Tests

## Construction and request opacity

Test:

```text
Path instance accepted and retained by identity
non-Path path values raise TypeError
source model is frozen
load succeeds when passed an uninitialized HistoricalSessionManifestRequest instance,
proving no request field is accessed
```

## Happy-path envelope loading

With a temp file containing a valid envelope:

```text
source returns list
returned list has expected ordering
additional envelope keys are ignored
raw optional provenance fields are retained
record mappings are not copied after parsing
empty records list returns exact empty list
each separate source call returns a fresh parsed list and fresh nested objects
```

The test should compare the returned records to expected values but must not require source-level manifest validation.

## Generic datetime tag behavior

Test:

```text
exact valid tag becomes a datetime
Z, +00:00, and fixed-offset strings decode
naive datetime string decodes to naive datetime without source rejection
invalid tag string remains a mapping
non-string tag value remains a mapping
tag object with extra key remains a mapping
generic tag can occur in an optional provenance value and decode without the source knowing field meaning
```

Verify no UTC conversion or timezone normalization is performed.

## File and JSON error propagation

Test:

```text
missing file → FileNotFoundError unchanged
invalid UTF-8 bytes → UnicodeDecodeError unchanged
invalid JSON text → json.JSONDecodeError unchanged
directory path → IsADirectoryError unchanged where supported by the local platform
```

Do not test `PermissionError` in a platform-dependent way unless the environment makes it deterministic.

## Envelope validation

Test every stable envelope error:

```text
root list / scalar → INVALID_ENVELOPE_ROOT
missing schema_version → MISSING_SCHEMA_VERSION
schema_version false / string / 2 → UNSUPPORTED_SCHEMA_VERSION
missing records → MISSING_RECORDS_FIELD
records null / mapping / string → INVALID_RECORDS_CONTAINER
```

Assert exact exception class and exact message.

## Source ownership and no record validation

Test:

```text
JSON records that are scalars, malformed mappings, incomplete mappings,
and mappings with arbitrary extra fields load successfully as list elements;
the source does not reject them;
the source does not inspect required manifest field names.
```

Use a source-boundary AST test to ensure production code:

```text
imports only standard library and HistoricalSessionManifestRequest;
does not import/call Phase 14I, Phase 14J, Phase 15A–15F,
providers, runtime, HTTP, transports, config, scanner, alerts, voice,
candidates, or trading modules;
does not mention or access manifest record field names;
does not call resolve, absolute, expanduser, expandvars, glob, rglob,
or environment/config functions;
does not cache file contents;
does not inspect request fields.
```

The generic `$datetime` tag key is explicitly allowed.

## Actual Phase 15D compatibility

The Phase 15G production module must not import Phase 15D. The test module may.

Write a valid local JSON envelope with 20 valid raw manifest records using generic `$datetime` values.

```text
JsonHistoricalSessionMetadataFileSource
→ actual Phase 15D loader
→ LOADED
→ exact returned records list retained by identity
→ actual Phase 14I manifest adapter
→ manifest status OK
→ 20 emitted metadata records
```

## Actual Phase 15E compatibility

The Phase 15G production module must not import Phase 15E. The test module may.

Write a valid local JSON envelope with 20 explicit valid raw records using generic `$datetime` tags. Use a local complete two-page historical collection with the first historical session split across pages, plus a valid current series and harness request.

```text
JsonHistoricalSessionMetadataFileSource
→ actual Phase 15E
→ metadata load LOADED
→ workflow bridge ran
→ Phase 14J status OK
→ final TOD-RVOL 2.0
```

This proves the JSON representation is usable by the existing offline workflow without adding workflow code to the file source.

## Failure stays downstream

Use JSON record values that the file source deliberately permits, then prove Phase 14I owns the diagnostic:

```text
invalid non-decoded $datetime object in cutoff_timestamp
→ Phase 15D LOADED
→ actual Phase 14I manifest result PARTIAL
→ affected record status INVALID_CUTOFF_TIMESTAMP
```

The source must not convert this to a file-envelope error.

---

## README Note

Update only if useful:

```text
Phase 15G adds an explicit caller-selected local JSON metadata source for Phase 15D.
It reads a versioned UTF-8 JSON envelope and supports a generic $datetime tagged value to represent Python datetime objects without inferring or validating historical session facts.
Manifest record validation remains in Phase 14I; no runtime provider, network source, or trading/order behavior is added.
live_composed remains reserved/inactive.
```

---

## Acceptance Criteria

Phase 15G is complete when:

```text
- one caller-selected Path is read exactly once per source load with no path discovery or cache;
- a strict version-1 JSON envelope returns its exact parsed records list;
- generic exact $datetime tags decode mechanically without manifest field awareness;
- malformed/non-exact tags remain raw values for Phase 14I diagnostics;
- file I/O and JSON parsing errors propagate unchanged;
- source-level envelope errors use stable exact custom messages;
- source does not inspect request fields or manifest record fields;
- actual Phase 15D and complete Phase 15E workflows succeed from a local JSON file and produce RVOL 2.0;
- no metadata inference, fetcher/transport, runtime/provider, scanner, alert, voice, or trading behavior is added;
- the full project suite remains green.
```
