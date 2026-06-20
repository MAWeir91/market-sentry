# Phase 17B — Explicit Alpaca RVOL Bundle Capture Core

## Status

**Planned.** This document defines Phase 17B only.

Phase 16A loads one explicit historical RVOL bundle into existing typed inputs. Phase 17A writes those same typed inputs into canonical `schema_version: 1` bundle JSON.

Phase 17B creates a manually invoked capture coordinator that can assemble those typed inputs from **caller-injected Alpaca historical-bars fetching** and write them through the Phase 17A canonical writer:

```text
explicit capture request
+ injected AlpacaHistoricalBarsFetcher
+ explicit output Path
        ↓
historical page collection
+ current-session page collection
        ↓
compose current pages
+ adapt current bars into IntradayVolumeSeriesInput
        ↓
construct existing manifest / harness requests
        ↓
Phase 17A canonical bundle writer
        ↓
explicit local bundle JSON
```

This phase does not add a command-line flag, does not read configuration, and does not instantiate a real HTTP transport. It is a capture **core** only.

A caller can supply a real `AlpacaHistoricalBarsFetcher` with a real transport in a deliberately manual context. Tests must use only `FakeHttpTransport`.

A later phase may add a separately reviewed, explicitly gated command that loads local configuration and instantiates a real transport. That work is out of scope here.

---

## Goal

Create a deterministic coordinator that:

1. requires an explicit `allow_live_data is True` request gate before **any** fetch or write;
2. uses the existing `collect_historical_bars_pages` function to capture historical bars;
3. uses the same existing collector for current-session bars, so current data cannot be silently truncated at one page;
4. composes the complete current collection with the existing composer;
5. adapts the composed current raw bars using the existing Alpaca-to-intraday adapter;
6. constructs only existing manifest and harness request models;
7. writes the bundle only through `write_local_historical_rvol_bundle`;
8. preserves an incomplete historical collection inside the resulting bundle for later diagnostic preflight;
9. refuses to write a bundle when the current collection cannot be composed or current bars cannot be adapted;
10. does not run the Phase 16A loader, Phase 15H preflight, metadata loader, scanner, alerts, or runtime provider.

No new RVOL calculation is introduced.

---

## Core Ownership Boundary

```text
Phase 17B owns:
  explicit capture sequencing
  one caller-provided live-data gate
  page collection request construction
  current-page composition gate
  current-bar adapter gate
  construction of existing manifest/harness request inputs
  invoking the canonical writer once on successful capture

Existing historical page collector owns:
  pagination
  repeated-token detection
  historical/current collection state

Existing collected-pages composer owns:
  complete-collection validation
  page symbol consistency
  raw-page combination

Existing Alpaca bar adapter owns:
  current raw timestamp parsing
  current raw volume field presence
  current intraday-series construction
  current adapter statuses

Phase 17A writer owns:
  canonical JSON serialization
  generic datetime encoding
  output file write

Phase 16A loader owns:
  later bundle parsing and construction

Phase 15H owns:
  later metadata-loaded workflow execution and RVOL diagnostics
```

Phase 17B must not:

```text
load or read metadata JSON
create a metadata source
call the Phase 16A loader
call Phase 15H / Phase 15E / Phase 15C / Phase 15B / Phase 14J
calculate RVOL
preflight a bundle after writing it
inspect or normalize raw historical bars
inspect or normalize current bar volumes
infer trading sessions, market holidays, or time windows
derive query dates from the system clock
read environment variables
load AppConfig
instantiate StdlibHttpTransport
instantiate AlpacaMarketDataSettings
build a runtime provider
register a provider
scan candidates
generate alerts
play voice
call FMP
perform order or trading behavior
```

---

## Hard Safety Boundaries

Market Sentry is a personal-use scanner with local voice alerts. It is **not** a trading bot.

Do not add:

```text
brokerage orders
position management
trade execution
buy/sell/enter/exit recommendations
portfolio actions
automatic data capture
scheduled capture
background jobs
CLI flags
provider factory wiring
MARKET_SENTRY_PROVIDER changes
environment/config reads
automatic transport construction
HTTP calls in tests
WebSockets
metadata acquisition
file discovery
directory scanning
glob/rglob
scanner-loop integration
candidate generation
alerts
voice playback
persistent storage beyond one explicit writer output file
```

No live HTTP call is permitted in tests.

`live_composed` remains gated and reserved/inactive.

---

## Required Files

Create:

```text
docs/66_EXPLICIT_ALPACA_RVOL_BUNDLE_CAPTURE.md
src/market_sentry/data/explicit_alpaca_rvol_bundle_capture.py
tests/test_explicit_alpaca_rvol_bundle_capture.py
```

Do not modify:

```text
README.md
src/market_sentry/main.py
src/market_sentry/config.py
src/market_sentry/live_readiness.py
src/market_sentry/data/http_stdlib.py
src/market_sentry/data/alpaca.py
src/market_sentry/data/alpaca_historical_bars_fetcher.py
src/market_sentry/data/historical_bars_page_collector.py
src/market_sentry/data/collected_historical_pages_composer.py
src/market_sentry/data/alpaca_historical_bars_adapter.py
src/market_sentry/data/json_historical_rvol_bundle.py
src/market_sentry/data/json_historical_rvol_bundle_writer.py
src/market_sentry/data/local_json_metadata_workflow_preflight.py
src/market_sentry/local_json_bundle_preflight_cli.py
src/market_sentry/local_json_bundle_preflight_report_export.py
Phase 14A–14K
Phase 15A–15L
Phase 16A–16C
Phase 17A
provider/factory/runtime modules
transport modules
scanner modules
alert modules
voice modules
fixture scenario catalogs/harnesses
```

Phase 17B has no CLI or README change.

---

# Public Surface

## Status Constants

Create:

```python
class ExplicitAlpacaRvolBundleCaptureStatus:
    """Stable status/reason codes for one explicit capture request."""

    BUNDLE_WRITTEN = "BUNDLE_WRITTEN"
    LIVE_DATA_NOT_ALLOWED = "LIVE_DATA_NOT_ALLOWED"
    CURRENT_COLLECTION_NOT_COMPOSABLE = "CURRENT_COLLECTION_NOT_COMPOSABLE"
    CURRENT_SERIES_ADAPTATION_FAILED = "CURRENT_SERIES_ADAPTATION_FAILED"
```

Do not add a status for historical incompleteness. Historical collection state belongs to the existing collector and is intentionally serializable into the output bundle.

## Capture Request

Create a frozen request equivalent to:

```python
@dataclass(frozen=True)
class ExplicitAlpacaRvolBundleCaptureRequest:
    """All caller-selected controls for one manual Alpaca bundle capture."""

    symbol: str

    historical_initial_query: AlpacaHistoricalBarsQuery
    historical_max_pages: int

    current_initial_query: AlpacaHistoricalBarsQuery
    current_max_pages: int

    current_session_id: str
    bucket: str
    cutoff_timestamp: datetime
    minimum_historical_sessions: int

    output_path: Path
    allow_live_data: bool
```

All request values are caller supplied.

Requirements:

```text
- do not normalize symbol, labels, query strings, timestamps, or limits;
- use the existing HistoricalBarsPageCollectionRequest constructor for
  max-page validation;
- require `allow_live_data is True` exactly to permit fetching;
- false, 1, "true", None, and every other value must return
  LIVE_DATA_NOT_ALLOWED before any fetch or write;
- require output_path to be a real pathlib.Path before any fetch or write.
```

For non-`Path` `output_path`, raise exactly:

```python
TypeError("output_path must be a pathlib.Path.")
```

Do not call the Phase 17A writer to discover this error after network capture has already occurred.

## Capture Result

Create a frozen result equivalent to:

```python
@dataclass(frozen=True)
class ExplicitAlpacaRvolBundleCaptureResult:
    """Inspectable artifacts from one explicit Alpaca bundle capture."""

    request: ExplicitAlpacaRvolBundleCaptureRequest
    output_path: Path

    historical_collection: HistoricalBarsPageCollectionResult | None
    current_collection: HistoricalBarsPageCollectionResult | None
    current_composition: CollectedHistoricalPagesCompositionResult | None
    current_series_result: AlpacaHistoricalBarsIntradaySeriesResult | None

    manifest_request: HistoricalSessionManifestRequest | None
    harness_request: HistoricalToTodRvolRunRequest | None

    output_written: bool
    status: str
    reason: str | None = None
```

Exact field names may vary, but retain:

```text
exact request object
exact output Path object
historical collection result
current collection result
current composition result
current adapter result
constructed existing manifest/harness requests
output write state
stable status/reason
```

The result must retain exact artifact object references returned or constructed in this call.

---

## Public Function

Provide:

```python
def capture_explicit_alpaca_rvol_bundle(
    fetcher: AlpacaHistoricalBarsFetcher,
    request: ExplicitAlpacaRvolBundleCaptureRequest,
) -> ExplicitAlpacaRvolBundleCaptureResult:
    """Capture one explicit Alpaca historical/current bar bundle."""
```

Required execution order:

```text
1. Validate `request.output_path` is Path.
2. Require `request.allow_live_data is True`.
3. Build one historical HistoricalBarsPageCollectionRequest:
   symbols=(request.symbol,)
   initial_query=request.historical_initial_query
   max_pages=request.historical_max_pages
4. Call existing collect_historical_bars_pages(fetcher, historical_request) once.
5. Build one current HistoricalBarsPageCollectionRequest:
   symbols=(request.symbol,)
   initial_query=request.current_initial_query
   max_pages=request.current_max_pages
6. Call existing collect_historical_bars_pages(fetcher, current_request) once.
7. Call existing compose_collected_historical_pages(current_collection) once.
8. When current composition is not COMPOSED:
   return CURRENT_COLLECTION_NOT_COMPOSABLE; do not adapt or write.
9. Build one AlpacaHistoricalBarsIntradaySeriesRequest from:
   symbol=request.symbol
   session_id=request.current_session_id
   bucket=request.bucket
   cutoff_timestamp=request.cutoff_timestamp
10. Call existing build_intraday_series_from_historical_bars once.
11. When current adapter status is not OK:
    return CURRENT_SERIES_ADAPTATION_FAILED; do not write.
12. Construct:
    HistoricalSessionManifestRequest(
        symbol=request.symbol,
        bucket=request.bucket,
        current_session_id=request.current_session_id,
    )
13. Construct:
    HistoricalToTodRvolRunRequest(
        symbol=request.symbol,
        bucket=request.bucket,
        current_session_id=request.current_session_id,
        page_collection_complete=historical_collection.page_collection_complete,
        minimum_historical_sessions=request.minimum_historical_sessions,
    )
14. Call write_local_historical_rvol_bundle exactly once with:
    request.output_path,
    historical_collection,
    manifest_request,
    adapted current series,
    harness_request
15. Return BUNDLE_WRITTEN with output_written=True.
```

No fetch or write may occur before the explicit live-data gate passes.

Do not call `fetcher.fetch_bars` directly. The only fetch route is the existing page collector.

Do not call a writer/render function on any denied, uncomposable-current, or adapter-failed path.

Do not catch or wrap:

```text
Alpaca historical fetch/transport errors
collector exceptions
composer exceptions
writer representation errors
writer filesystem errors
```

They must propagate unchanged and no synthetic success/failure result should be returned for unexpected exceptions.

---

# Capture Semantics

## Historical Collection

Historical collection is captured and written even when it is incomplete.

Examples:

```text
MAX_PAGE_LIMIT_REACHED
REPEATED_NEXT_PAGE_TOKEN
```

must be preserved in the serialized `HistoricalBarsPageCollectionResult`. The resulting bundle can later be manually preflighted to surface existing incomplete-collection diagnostics.

Phase 17B must not attempt to compose the historical collection.

## Current Collection

Current collection is different: it must compose successfully before any bundle is written.

This ensures a paginated or structurally mismatched current query does not silently become an incomplete `IntradayVolumeSeriesInput`.

When current collection composition is not `COMPOSED`, return:

```text
status: CURRENT_COLLECTION_NOT_COMPOSABLE
reason: CURRENT_COLLECTION_NOT_COMPOSABLE:<current composition status>
output_written: false
```

Keep historical and current collection artifacts in the result.

## Current Adapter

When current raw bars cannot be adapted, return:

```text
status: CURRENT_SERIES_ADAPTATION_FAILED
reason: CURRENT_SERIES_ADAPTATION_FAILED:<adapter status>
output_written: false
```

Do not reinterpret adapter reasons.

## Writer

The Phase 17A writer is the only output route.

A successful Phase 17B result does not read output bytes back or run the loader/preflight. Tests may do so.

---

# Required Tests

Create:

```text
tests/test_explicit_alpaca_rvol_bundle_capture.py
```

Use only `FakeHttpTransport` and deterministic in-memory JSON response bodies. No test may contact Alpaca or any live service.

## Gate and Request Tests

Test:

```text
allow_live_data is True permits capture
False / 1 / "true" / None all return LIVE_DATA_NOT_ALLOWED
denied capture makes zero fetches
denied capture makes zero writer calls
denied capture leaves a preexisting output file unchanged
non-Path output_path raises exact TypeError before fetch/write
historical/current collection request values use exact caller values
historical/current symbols are exactly (request.symbol,)
```

## Capture Sequencing Tests

Use a paginated historical response followed by a paginated current response.

Assert:

```text
historical collector consumes historical pages first
current collector consumes current pages second
current page collection combines all current raw bars before adaptation
exactly two collector calls occur
exactly one current composer call occurs
exactly one adapter call occurs
exactly one writer call occurs on successful capture
writer receives exact historical collection, manifest request,
adapted current series, and harness request objects
```

Monkeypatch only direct imported function symbols in the capture module for unit sequencing tests.

## Historical Incomplete Preservation

Use a historical page response with a continuation token and `historical_max_pages=1`.

Assert:

```text
historical collection status is MAX_PAGE_LIMIT_REACHED
historical page_collection_complete is false
capture still reaches BUNDLE_WRITTEN
writer receives harness_request.page_collection_complete is false
```

This is intentional. Do not treat it as a capture failure.

## Current Failure Tests

Cover:

```text
current continuation + current_max_pages=1
→ CURRENT_COLLECTION_NOT_COMPOSABLE
→ no adapter
→ no writer

current complete but empty collection
→ CURRENT_COLLECTION_NOT_COMPOSABLE
→ no adapter
→ no writer

current page requested-symbol mismatch across pages
→ CURRENT_COLLECTION_NOT_COMPOSABLE
→ no adapter
→ no writer

current raw bar invalid for adapter
→ CURRENT_SERIES_ADAPTATION_FAILED
→ no writer
```

## Error Propagation Tests

Test unchanged propagation for:

```text
fetcher / transport error
collector exception
composer exception
adapter exception
writer representation error
writer filesystem error
```

No synthetic result may appear after an unexpected exception.

## Actual Writer / Loader Compatibility

With deterministic fake Alpaca pages and actual Phase 17A writer:

```text
capture into temp output Path
→ output file exists
→ load with Phase 16A loader in the test
→ output typed collection, manifest request, current series, and
  harness request equal the capture result artifacts by value
```

Then pair that loaded bundle with real valid Phase 15I metadata fixture bytes in a test and invoke existing Phase 15H:

```text
metadata load = LOADED
workflow status = WORKFLOW_BRIDGE_RAN
composition = COMPOSED
coordinator = OK
final TOD-RVOL status = OK
relative volume = 2.0
```

The capture module must not import the loader, fixtures, or workflow. Tests own this compatibility check.

## Source-Boundary Tests

Use AST/focused source checks to prove production Phase 17B:

```text
imports only:
  dataclasses
  datetime
  pathlib
  existing collector/composer/adapter/request models
  Phase 17A writer

does not import:
  main/CLI modules
  config/live-readiness
  Alpaca settings
  HTTP transports or StdlibHttpTransport
  metadata source or loader
  Phase 15H/workflow modules
  providers/factories
  scanner/alerts/voice
  FMP
  tests/scenario catalogs/harnesses
  live/trading modules

does not call:
  direct fetcher.fetch_bars
  writer render helper
  loader
  workflow/preflight
  resolve/absolute/expanduser/glob/rglob/mkdir
  environment reads
  network/HTTP construction
  caching
```

---

## README

Do not modify README. Phase 17B does not add a user-facing command.

---

## Validation

Run:

```powershell
python -m pytest tests/test_explicit_alpaca_rvol_bundle_capture.py
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

No Phase 17B CLI command is added.

---

## Acceptance Criteria

Phase 17B is complete when:

```text
- capture is explicitly gated by `allow_live_data is True`;
- no denied capture fetches or writes;
- historical and current collection use the existing collector only;
- historical incomplete collection state is preserved and serializable;
- current collection must compose before bundle output;
- current adapter must succeed before bundle output;
- the canonical writer is the only bundle output route;
- no loader/preflight/workflow runs in production capture code;
- fake-response capture output loads through Phase 16A and succeeds through Phase 15H with RVOL 2.0 in tests;
- no config, CLI, provider, runtime, scanner, alert, voice, network-construction, or trading behavior is added;
- full project suite remains green.
```
