# Phase 17C — Canonical Local Historical Session Metadata Writer

## Status

**Planned.** This document defines Phase 17C only.

Phase 15G consumes one explicit local JSON metadata file:

```text
metadata.json
  schema_version: 1
  records: [raw historical session metadata records]
```

Phase 17A writes the separate historical RVOL bundle file. Phase 17C adds the matching offline producer for the metadata-file side:

```text
caller-supplied raw metadata record sequence
→ canonical metadata JSON text
→ explicit metadata JSON Path
→ existing Phase 15G source
```

This phase deliberately does **not** fetch or infer metadata. The current FMP module fetches shares-float reference data only; it does not supply session identifiers, session windows, cutoff timestamps, or completeness. Those metadata records remain caller-owned inputs.

---

## Goal

Create a deterministic offline writer that serializes one caller-supplied raw metadata-record sequence to the exact version-one JSON envelope consumed by `JsonHistoricalSessionMetadataFileSource`.

It must:

1. accept raw records without manifest semantic validation;
2. encode generic `datetime` values using Phase 15G-compatible exact `$datetime` tags;
3. write canonical UTF-8 JSON only to one explicit caller-owned `Path`;
4. render fully in memory before any write;
5. never read the output back, create a parent, scan paths, fetch data, execute a workflow, or load a bundle;
6. allow downstream Phase 14I/15H components to retain all manifest and RVOL diagnostics.

This is the metadata counterpart to Phase 17A:

```text
typed/raw caller records ⇄ canonical metadata JSON ⇄ Phase 15G raw records
```

---

## Hard Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is not a trading bot.

Do not add:

```text
CLI flags or command routing
provider activation
configuration or environment reads
FMP fetches or FMP transport construction
Alpaca fetches or transport construction
metadata inference from bars
market-calendar, holiday, early-close, halt, split, or session inference
workflow/preflight execution
bundle loading or writing
scanner execution
candidate generation
alerts or voice playback
HTTP, WebSockets, retries, caches, scheduling, persistence beyond the explicit output write
order placement, trade execution, portfolio actions, or trading recommendations
```

No live network access is permitted in tests.

---

## Required Files

Create:

```text
docs/67_CANONICAL_LOCAL_HISTORICAL_SESSION_METADATA_WRITER.md
src/market_sentry/data/json_historical_session_metadata_writer.py
tests/test_json_historical_session_metadata_writer.py
```

Do not modify:

```text
README.md
src/market_sentry/main.py
src/market_sentry/data/json_historical_session_metadata_source.py
src/market_sentry/data/json_historical_rvol_bundle.py
src/market_sentry/data/json_historical_rvol_bundle_writer.py
any Phase 15/16/17 modules
provider/config/readiness/factory modules
HTTP/transport modules
FMP modules
Alpaca modules
workflow/preflight modules
scanner/alert/voice modules
fixture catalogs and harnesses
```

Phase 17C adds no user-facing command.

---

## Public API

Create:

```python
class JsonHistoricalSessionMetadataWriteError(ValueError):
    """Raised when metadata records cannot be represented as canonical JSON."""
```

Provide:

```python
def render_local_historical_session_metadata(
    records: Sequence[object],
) -> str:
    """Return canonical schema-version-one metadata JSON text."""
```

and:

```python
def write_local_historical_session_metadata(
    path: Path,
    records: Sequence[object],
) -> None:
    """Write one canonical local metadata JSON file."""
```

`path` must be an actual `pathlib.Path` instance. Any other type must raise exactly:

```python
TypeError("path must be a pathlib.Path.")
```

`records` must be a `collections.abc.Sequence` other than `str`, `bytes`, `bytearray`, or `memoryview`. Otherwise raise:

```text
INVALID_RECORDS_SEQUENCE
```

The writer must neither validate individual record mappings nor require record elements to be mappings. Phase 15G treats them as opaque; Phase 14I later owns manifest record diagnostics.

---

## Canonical Output

The renderer must emit exactly this envelope shape:

```json
{
  "records": [],
  "schema_version": 1
}
```

Requirements:

```text
- records is rendered as a JSON array preserving caller sequence order;
- records are the only non-schema envelope field;
- schema_version is exactly integer 1;
- use json.dumps with ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True;
- append exactly one trailing newline;
- no source_name, timestamp, generated_at, host, environment, or implicit metadata;
- no sorting/reordering/filtering/deduplication of record values.
```

The output must be accepted by the existing Phase 15G source for structurally valid JSON and must yield the equivalent decoded record list.

---

## Generic JSON Value Encoding

The writer owns a generic recursive representation codec only.

Allowed values:

```text
None
bool
str
int
finite float
datetime
list
tuple
Mapping with string keys
```

### Datetime tags

Every real `datetime` becomes exactly:

```json
{"$datetime": "<isoformat>"}
```

Rules:

```text
- naive datetime remains naive;
- fixed-offset datetime remains fixed offset;
- rendered UTC +00:00 uses terminal Z;
- recurse through nested record mappings/lists/tuples;
- do not normalize time zones or infer calendar facts.
```

These rules match Phase 15G decoding behavior.

### Stable representation errors

Use only these writer-specific messages:

```text
INVALID_MAPPING_KEY:<path>
NON_FINITE_FLOAT:<path>
UNSUPPORTED_VALUE:<path>
INVALID_RECORDS_SEQUENCE
```

Path conventions:

```text
records[0]
records[0].session_start_timestamp
records[1].nested[0]
```

For a non-string mapping key, report the containing value path:

```text
INVALID_MAPPING_KEY:records[0]
```

For `NaN`, `+inf`, or `-inf`:

```text
NON_FINITE_FLOAT:<path>
```

For unsupported values such as bytes, sets, `date` without time, `Decimal`, arbitrary objects, callables, and generators:

```text
UNSUPPORTED_VALUE:<path>
```

Reject representation errors during rendering, before any filesystem write. A pre-existing target file must remain byte-for-byte unchanged when rendering fails.

---

## Write Behavior

`write_local_historical_session_metadata` must:

```text
1. validate path type;
2. render completely in memory;
3. call path.write_text(rendered, encoding="utf-8") exactly once;
4. return None.
```

It must not:

```text
call resolve, absolute, expanduser, glob, rglob, mkdir, touch, open directly, read_text, read_bytes, exists, stat, rename, replace, or unlink
catch or wrap OSError/FileNotFoundError/PermissionError/IsADirectoryError
retry writes
cache output or input records
```

A missing parent must propagate the normal `FileNotFoundError` unchanged and remain missing.

---

## Ownership Boundaries

```text
Phase 17C owns:
  canonical JSON rendering
  generic datetime tags
  generic representability checks
  one explicit output write

Phase 15G owns:
  reading one explicit metadata file
  UTF-8 JSON parsing
  envelope validation
  generic datetime tag decoding

Phase 14I owns:
  record mapping requirements
  symbol/session/bucket matching
  timestamp awareness/timezone/window/cutoff validation
  completeness validation
  duplicate metadata validation

Phase 15H and lower stages own:
  metadata load/workflow diagnostics
  bar composition
  RVOL diagnostics
```

Phase 17C must not load the JSON file it writes, call Phase 15G, call Phase 15H, call a workflow, create metadata records from bars, or interpret session semantics.

---

## Required Tests

Create `tests/test_json_historical_session_metadata_writer.py`.

### Rendering and write tests

Test:

```text
canonical deterministic JSON shape
exactly one trailing newline
UTF-8 non-ASCII preservation
records order preserved
Path type error exact message
one Path.write_text call with exact rendered text and utf-8
no output read-back
no parent creation
filesystem errors propagate unchanged
fresh writes use fresh current input, no cache
```

### Generic encoding tests

Test:

```text
naive/fixed-offset/UTC datetime tags
recursive datetime encoding through nested lists and mappings
non-string mapping key error
NaN/+inf/-inf error
unsupported values error
invalid records sequence error
representation error leaves existing file unchanged
```

### Loader and workflow compatibility tests

Tests, but not production writer code, may import existing components.

Prove:

```text
raw caller records
→ Phase 17C writer
→ Phase 15G JsonHistoricalSessionMetadataFileSource
→ equivalent decoded raw records
```

Use a valid 20-session metadata record set compatible with existing Phase 15I collection/current/harness inputs:

```text
writer output + existing Phase 15H wrapper
→ metadata LOADED
→ workflow bridge ran
→ composition COMPOSED
→ coordinator OK
→ final TOD-RVOL OK
→ RVOL 2.0
```

Also prove opaque/invalid records are not prevalidated by the writer:

```text
record with is_complete false
→ writer succeeds
→ Phase 15G source loads records
→ downstream Phase 14I/15H reports INCOMPLETE_SESSION
```

### Source-boundary tests

Use AST or focused source checks proving the production writer:

```text
imports only approved standard-library modules;
does not import Phase 15G source, Phase 15H/workflows, metadata/bundle loaders,
main/CLI/export helpers, scenario catalogs/harnesses/tests, config/providers,
FMP/Alpaca/transports, scanner, alerts, voice, HTTP, live/trading modules;
does not call a loader or workflow;
does not use path resolution, read-back, parent creation, environment access,
network calls, or caching.
```

---

## Validation

Run:

```powershell
python -m pytest tests/test_json_historical_session_metadata_writer.py
python -m pytest
python -m market_sentry
python -m market_sentry --local-json-preflight .\does-not-exist.json
python -m market_sentry --local-json-preflight-report .\report.txt
python -m market_sentry --local-json-bundle-preflight .\does-not-exist-metadata.json .\does-not-exist-bundle.json
python -m market_sentry --local-json-bundle-preflight-report .\bundle-report.txt
```

Then rerun fixture, composed fixture, Alpaca placeholder, both `live_composed` placeholder checks, and both readiness modes.

No Phase 17C command is added.

---

## Acceptance Criteria

Phase 17C is complete when:

```text
- raw caller record sequences render as canonical Phase 15G-compatible schema-version-one metadata JSON;
- generic datetime tags round-trip through Phase 15G without timezone normalization;
- record order and opaque values survive serialization/deserialization;
- representation errors happen before output writes;
- writer output plus existing valid inputs reaches final RVOL 2.0 through Phase 15H;
- incomplete metadata records remain downstream-owned diagnostics;
- no FMP/Alpaca/config/CLI/provider/runtime/workflow/scanner/alert/voice/network/trading behavior changes;
- the full project suite remains green.
```
