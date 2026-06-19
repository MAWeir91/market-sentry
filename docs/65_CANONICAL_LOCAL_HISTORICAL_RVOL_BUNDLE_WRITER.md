# Phase 17A — Canonical Local Historical RVOL Bundle Writer

## Status

**Planned.** This document defines Phase 17A only.

Phase 16A loads one explicit versioned historical RVOL bundle JSON file into the four existing non-metadata inputs for Phase 15H. Phase 17A adds the inverse, offline-only producer seam:

```text
existing typed non-metadata inputs
        ↓
Phase 17A canonical JSON rendering
        ↓
one explicit output bundle Path
        ↓
Phase 16A loader
        ↓
value-equivalent typed non-metadata inputs
```

Phase 17A does not collect market data, add a CLI command, add a provider, inspect metadata, run the preflight workflow, calculate RVOL, scan candidates, or change any existing runtime path.

A future Phase 17B may use this writer as the stable output target for explicit manual data capture.

---

## Goal

Create a deterministic, offline writer for the existing Phase 16A `schema_version: 1` bundle format.

The writer accepts:

```text
one caller-selected output Path
one HistoricalBarsPageCollectionResult
one HistoricalSessionManifestRequest
one IntradayVolumeSeriesInput
one HistoricalToTodRvolRunRequest
```

It must:

1. render the canonical Phase 16A bundle envelope;
2. encode real `datetime` values as exact generic `$datetime` tags;
3. preserve typed input values and raw historical bar mapping values without domain normalization;
4. emit deterministic valid UTF-8 JSON;
5. write only the explicit output path;
6. write once, with no parent-directory creation or read-back;
7. produce a file Phase 16A can load into value-equivalent typed inputs.

It must not:

```text
read a bundle file
call the Phase 16A loader
read a metadata file
create a metadata source
call Phase 15H or any workflow
validate raw OHLCV fields
validate or coerce raw bar volumes
validate or coerce current volumes
sort, deduplicate, filter, repair, fabricate, or infer bars
normalize symbols, buckets, sessions, statuses, or request fields
infer market hours, holidays, half-days, halts, or splits
initialize configuration
activate a provider
call a transport, HTTP, WebSocket, API, scanner, alert, or voice component
add CLI wiring
perform trading or order behavior
```

---

## Ownership Boundary

```text
Phase 17A owns:
  canonical JSON representation of existing typed bundle inputs
  generic datetime-to-$datetime encoding
  JSON-serializability validation
  deterministic text rendering
  one explicit output write

Phase 16A owns:
  canonical JSON bundle parsing
  $datetime-to-datetime decoding
  bundle envelope/container validation
  typed input reconstruction

Existing model constructors own:
  their current construction constraints

Phase 13F / Phase 14A–15H existing stages own:
  raw historical-bar semantics
  current timestamp validation
  current volume validation
  collection composition semantics
  metadata/manifest validation
  baseline/final RVOL diagnostics
```

The writer must not duplicate Phase 16A parsing or Phase 15H execution.

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
automatic data capture
directory discovery
glob/rglob
environment/config reads
CLI flags or runtime wiring
scanner loop integration
alerts or voice playback
persistent database storage
```

No live HTTP calls are permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

## Required Files

Create:

```text
docs/65_CANONICAL_LOCAL_HISTORICAL_RVOL_BUNDLE_WRITER.md
src/market_sentry/data/json_historical_rvol_bundle_writer.py
tests/test_json_historical_rvol_bundle_writer.py
```

Do not modify:

```text
README.md
src/market_sentry/main.py
src/market_sentry/data/json_historical_rvol_bundle.py
src/market_sentry/local_json_preflight_cli.py
src/market_sentry/local_json_preflight_report_export.py
src/market_sentry/local_json_bundle_preflight_cli.py
src/market_sentry/local_json_bundle_preflight_report_export.py
Phase 14A–14K
Phase 15A–15L
Phase 16A–16C
provider/config/factory/readiness modules
transport/fetcher modules
scanner modules
alert modules
voice modules
fixture scenario catalogs/harnesses
metadata JSON source behavior
workflow behavior
```

Phase 17A has no user-facing CLI or runtime command.

---

## Public Surface

Create:

```python
class JsonHistoricalRvolBundleWriteError(ValueError):
    """Raised when existing bundle inputs cannot be represented as canonical JSON."""
```

Create one public renderer:

```python
def render_local_historical_rvol_bundle(
    collection: HistoricalBarsPageCollectionResult,
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> str:
    """Return canonical schema-version-one local RVOL bundle JSON text."""
```

Create one public writer:

```python
def write_local_historical_rvol_bundle(
    path: Path,
    collection: HistoricalBarsPageCollectionResult,
    manifest_request: HistoricalSessionManifestRequest,
    current_series: IntradayVolumeSeriesInput,
    harness_request: HistoricalToTodRvolRunRequest,
) -> None:
    """Render and write one canonical local historical RVOL bundle."""
```

Required behavior:

```text
- `path` must be an actual pathlib.Path instance;
- non-Path values raise exactly:
  TypeError("path must be a pathlib.Path.");
- retain and use the exact caller-supplied Path;
- do not resolve, absolutize, expanduser, expand variables, glob, rglob,
  scan directories, select fallback files, read existing output, or create directories;
- render fully before writing;
- write exactly once using UTF-8;
- do not append text after the rendered canonical output;
- do not return a loader result, workflow result, report, or status artifact;
- do not cache output, inputs, paths, or rendered text.
```

The writer may overwrite the explicit output file if its parent exists and normal filesystem permissions allow it. It is not a report exporter and has no protected input paths because it has no input file paths.

---

## Allowed Production Imports

`src/market_sentry/data/json_historical_rvol_bundle_writer.py` may import only:

```text
standard library:
  collections.abc.Mapping
  dataclasses
  datetime
  json
  math
  pathlib
  typing

market_sentry.data.alpaca_historical_bars_fetcher:
  AlpacaHistoricalBarsPage
  AlpacaHistoricalBarsQuery

market_sentry.data.historical_bars_page_collector:
  HistoricalBarsCollectedPage
  HistoricalBarsPageCollectionRequest
  HistoricalBarsPageCollectionResult

market_sentry.data.historical_session_manifest:
  HistoricalSessionManifestRequest

market_sentry.data.historical_tod_rvol_harness:
  HistoricalToTodRvolRunRequest

market_sentry.data.intraday_bucket_adapter:
  IntradayVolumeBar
  IntradayVolumeSeriesInput
```

Do not import:

```text
json_historical_rvol_bundle
Phase 15H or any workflow module
metadata sources
main
CLI helpers/exporters
Phase 15I / 15L / 16C scenario catalogs or harnesses
config/providers/factory/readiness
scanner/alerts/voice
HTTP/transports
live candidate modules
trading modules
```

The writer must not call the Phase 16A loader. Tests own loader round-trip verification.

---

## Canonical Envelope

The renderer must produce exactly this top-level shape:

```json
{
  "schema_version": 1,
  "collection": {},
  "manifest_request": {},
  "current_series": {},
  "harness_request": {}
}
```

Top-level key order in the returned text must be deterministic. The canonical writer must use:

```text
ensure_ascii=False
allow_nan=False
indent=2
sort_keys=True
one trailing newline
```

The output must be valid JSON and must decode using `json.loads`.

`sort_keys=True` makes nested mappings deterministic as well. It does not alter typed input objects.

---

## Canonical Schema Mapping

### `collection`

Render exactly:

```json
{
  "request": {
    "symbols": [],
    "initial_query": {
      "timeframe": "...",
      "start": "...",
      "end": "...",
      "limit": 1000,
      "page_token": null,
      "sort": "asc"
    },
    "max_pages": 1
  },
  "collected_pages": [
    {
      "index": 0,
      "query": {
        "timeframe": "...",
        "start": "...",
        "end": "...",
        "limit": 1000,
        "page_token": null,
        "sort": "asc"
      },
      "page": {
        "requested_symbols": [],
        "bars_by_symbol": {},
        "next_page_token": null
      }
    }
  ],
  "status": "COMPLETE",
  "page_collection_complete": true,
  "next_page_token": null,
  "reason": null
}
```

Map from existing model attributes directly:

```text
collection.request.symbols
collection.request.initial_query
collection.request.max_pages
collection.collected_pages
collection.status
collection.page_collection_complete
collection.next_page_token
collection.reason
```

For every `HistoricalBarsCollectedPage`, serialize:

```text
index
query
page.requested_symbols
page.bars_by_symbol
page.next_page_token
```

Raw historical bars are opaque mappings. Serialize their keys and values recursively; do not require fields such as `t`, `v`, `o`, `h`, `l`, or `c`, and do not change their values.

### `manifest_request`

Render exactly:

```json
{
  "symbol": "...",
  "bucket": "...",
  "current_session_id": "..."
}
```

Map model attributes directly. Do not normalize them.

### `current_series`

Render exactly:

```json
{
  "symbol": "...",
  "session_id": "...",
  "bucket": "...",
  "cutoff_timestamp": {
    "$datetime": "..."
  },
  "bars": [
    {
      "timestamp": {
        "$datetime": "..."
      },
      "volume": 123
    }
  ]
}
```

Map model attributes directly. The writer must preserve invalid-but-representable current values, including `False`, arbitrary strings, mappings, and `None`, exactly through standard recursive JSON encoding. It must not reject a volume merely because downstream Phase 13F would later classify it as invalid.

### `harness_request`

Render exactly:

```json
{
  "symbol": "...",
  "bucket": "...",
  "current_session_id": "...",
  "page_collection_complete": true,
  "minimum_historical_sessions": 20
}
```

Map model attributes directly. Do not take ownership of semantic validation.

---

## Generic Value Encoding

Implement one private recursive JSON-value encoder equivalent in behavior to:

```python
def _encode_json_value(value: Any, path: str) -> Any:
    ...
```

### Datetimes

For every actual `datetime` value:

```text
- encode to an exact one-key mapping:
  {"$datetime": "<canonical ISO text>"};
- preserve naive datetimes as naive ISO text;
- preserve fixed offsets;
- for a UTC +00:00 ISO suffix, use terminal Z canonically;
- do not attach, strip, or convert time zones;
- do not apply market/session calendar logic.
```

Examples:

```text
datetime(2026, 1, 31, 9, 35)            → {"$datetime": "2026-01-31T09:35:00"}
datetime(..., tzinfo=UTC)               → {"$datetime": "2026-01-31T09:35:00Z"}
datetime(..., tzinfo=UTC-05:00)         → {"$datetime": "2026-01-31T09:35:00-05:00"}
```

### Mappings

For every `collections.abc.Mapping`:

```text
- every key must be a str;
- recursively encode each value;
- retain keys and values by content;
- do not mutate the original mapping;
- non-string keys raise:
  INVALID_MAPPING_KEY:<path>
```

`MappingProxyType` from existing historical-page models must work.

### Sequences

For `list` and `tuple` values:

```text
- recursively encode each element;
- emit a JSON array;
- do not mutate the original sequence.
```

Do not treat strings, bytes, sets, generators, or arbitrary iterables as JSON arrays.

### JSON Primitive Values

Allow and preserve:

```text
None
bool
str
int
finite float
```

For non-finite float values (`NaN`, `+inf`, `-inf`), raise:

```text
NON_FINITE_FLOAT:<path>
```

For all other unsupported values, raise:

```text
UNSUPPORTED_VALUE:<path>
```

Examples:

```text
bytes
bytearray
set
frozenset
date (not datetime)
Decimal
object()
callable
generator
```

The writer must perform this validation before the output file write. If rendering fails, it must not write or truncate the output file.

### Exact Generic Tag Ambiguity

The existing Phase 16A grammar gives special meaning to any exact valid mapping:

```json
{"$datetime": "<parseable ISO string>"}
```

When supplied directly as a raw typed value, such a mapping is inherently interpreted as a datetime on a subsequent Phase 16A load. Phase 17A must not invent an escaping convention or mutate it. This is established bundle grammar, not a new Phase 17A semantic rule.

Mappings with invalid `$datetime` values or additional keys remain ordinary mappings under Phase 16A and must round-trip as mappings.

---

## Error Policy

The writer must allow filesystem write errors to propagate unchanged:

```text
FileNotFoundError
PermissionError
IsADirectoryError
OSError
```

Do not catch, wrap, retry, or remap them.

Phase 17A’s own representation errors must be exactly:

```text
INVALID_MAPPING_KEY:<path>
NON_FINITE_FLOAT:<path>
UNSUPPORTED_VALUE:<path>
```

Do not use `assert` for caller-supplied data.

The writer must render in memory before its one `path.write_text(...)` call. Representation errors must therefore leave an existing output file untouched.

---

## Round-Trip Contract

Tests must demonstrate this primary acceptance path:

```text
typed inputs
    ↓
render/write Phase 17A canonical JSON
    ↓
load_local_historical_rvol_bundle from Phase 16A
    ↓
value-equivalent typed inputs
```

For canonical inputs, assert equality for:

```text
collection
manifest_request
current_series
harness_request
```

and exact output file text equivalence with:

```python
render_local_historical_rvol_bundle(...)
```

Use a valid 20-session/two-page input set compatible with the existing Phase 15H valid workflow. Then prove the loaded output works with separate valid metadata through the existing Phase 15H function:

```text
metadata load = LOADED
workflow status = WORKFLOW_BRIDGE_RAN
composition = COMPOSED
coordinator = OK
final TOD-RVOL status = OK
relative volume = 2.0
```

The writer itself must not import or call Phase 15H.

---

## Required Tests

Create:

```text
tests/test_json_historical_rvol_bundle_writer.py
```

### Public API and deterministic rendering

Test:

```text
non-Path output raises exact TypeError
canonical renderer returns valid JSON
rendered top-level shape and schema version equal Phase 16A format
deterministic text for equivalent inputs
indent=2, sort_keys=True, ensure_ascii=False, one trailing newline
writer writes exactly the rendered UTF-8 text
writer returns None
no read-back occurs
no parent directory is created
fresh repeated writes do not use cached source data
```

### Datetime and raw-value preservation

Test:

```text
naive, UTC, and fixed-offset datetimes encode correctly
datetime values nested in raw historical bars encode recursively
raw custom historical bar fields survive
raw historical `v: false` survives unchanged
invalid current volume false survives unchanged
invalid current timestamp mapping survives unchanged
invalid/extra-key $datetime mappings remain mappings through writer + loader
```

### Error tests

Test:

```text
non-string mapping key → INVALID_MAPPING_KEY:<path>
NaN/+inf/-inf → NON_FINITE_FLOAT:<path>
bytes/set/date/Decimal/object/generator → UNSUPPORTED_VALUE:<path>
representation error before write leaves existing output bytes unchanged
missing parent propagates FileNotFoundError unchanged
directory path propagates IsADirectoryError unchanged
```

### Phase 16A loader / Phase 15H compatibility

Test:

```text
valid typed inputs → writer → Phase 16A loader → value-equivalent typed inputs
valid output + valid Phase 15I metadata → existing Phase 15H → RVOL 2.0
invalid current volume false → writer → loader → existing Phase 15H
→ CURRENT_CUMULATIVE_VOLUME_FAILED with nested INVALID_INTRADAY_VOLUME
```

### Source-Boundary Tests

Use AST or focused source inspection to prove the production writer:

```text
imports only approved standard library and existing typed-input models
does not import Phase 16A loader
does not import/call Phase 15H or any workflow
does not import metadata sources
does not import main/CLI helpers/exporters
does not import scenario catalogs/harnesses/tests
does not import config/providers/factory/readiness
does not import scanner/alert/voice/HTTP/transport/live/trading modules
does not call resolve, absolute, expanduser, glob, rglob, mkdir,
read_text, read_bytes, environment reads, network calls, or caches
uses exactly one write_text call in the public writer
```

---

## README

Do not modify README. Phase 17A adds no user-facing command.

---

## Validation

Run:

```powershell
python -m pytest tests/test_json_historical_rvol_bundle_writer.py
python -m pytest
python -m market_sentry
python -m market_sentry --local-json-preflight .\does-not-exist.json
python -m market_sentry --local-json-preflight-report .\report.txt
python -m market_sentry --local-json-bundle-preflight .\does-not-exist-metadata.json .\does-not-exist-bundle.json
python -m market_sentry --local-json-bundle-preflight-report .\bundle-report.txt
```

Then rerun:

```text
fixture
composed_fixture
Alpaca placeholder
both live_composed placeholder checks
both readiness checks
```

No Phase 17A CLI command is added.

---

## Acceptance Criteria

Phase 17A is complete when:

```text
- one explicit output Path can receive a canonical Phase 16A schema-version-one bundle;
- output is deterministic valid UTF-8 JSON;
- real datetime values use canonical exact $datetime tags;
- raw historical mappings and invalid-but-representable current values are preserved;
- unsupported JSON values fail before write with stable writer errors;
- Phase 16A loads writer output into value-equivalent typed inputs;
- valid writer output plus existing metadata reaches existing Phase 15H RVOL 2.0;
- invalid current volume false still reaches existing downstream INVALID_INTRADAY_VOLUME;
- no CLI, provider, runtime, network, scanner, alert, voice, or trading behavior changes;
- the full project suite remains green.
```
