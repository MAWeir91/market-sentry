# Phase 18A — One-Shot Live-Composed Scanner Activation

## Status

**Planned.** This document defines Phase 18A only.

Phases 17A–17E establish a manually gated way to create:

```text
metadata.json
historical-rvol-bundle.json
```

and validate their time-of-day RVOL result offline.

Phase 18A activates the existing `live_composed` provider for **one scanner run only**:

```text
explicit local RVOL artifact manifest
        ↓
offline preflight of every configured watchlist artifact
        ↓
validated symbol → RVOL mapping
        ↓
live Alpaca snapshot GET + live FMP float-reference GET
        ↓
existing live candidate builder
        ↓
existing scanner report
```

It does not create an RVOL artifact automatically, fetch historical bars, infer metadata, add a capture command, activate the scanner loop, or place orders.

The first real scan is deliberately a composite:

```text
live Alpaca snapshot
+ live FMP float reference
+ caller-maintained local, preflight-validated RVOL artifact
```

The RVOL value is **not refreshed by the scanner command**. The user must first capture and preflight the artifact through Phase 17E (or otherwise produce valid explicit local artifacts).

---

## Goal

Make this existing command run one live-composed scan when all gates and artifact checks pass:

```powershell
python -m market_sentry
```

with:

```text
MARKET_SENTRY_PROVIDER=live_composed
MARKET_SENTRY_ALLOW_LIVE_DATA=true
MARKET_SENTRY_WATCHLIST=<comma-separated symbols>
MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH=<explicit manifest JSON path>
ALPACA_API_KEY=<configured secret>
ALPACA_API_SECRET=<configured secret>
FMP_API_KEY=<configured secret>
```

The active live-composed run must:

1. validate all existing live-provider configuration gates;
2. load one explicit local RVOL artifact manifest;
3. preflight local metadata/bundle pairs for every watchlist symbol;
4. stop before HTTP transport construction when a local artifact is missing or invalid;
5. build a static validated RVOL mapping for the one run;
6. construct one injected `StdlibHttpTransport`, Alpaca snapshot fetcher, and FMP float fetcher;
7. run the existing live candidate builder and existing scanner once;
8. render an explicit source label making clear that RVOL came from local artifacts.

No live-composed loop is permitted in this phase.

---

## Operator Workflow

For each symbol, first produce fresh artifacts with Phase 17E:

```text
metadata-input.json
  → metadata.json + bundle.json + successful capture/preflight report
```

Then create one explicit manifest, for example:

```json
{
  "schema_version": 1,
  "artifacts": [
    {
      "symbol": "ABC",
      "metadata_path": "C:\\market-sentry\\artifacts\\ABC.metadata.json",
      "bundle_path": "C:\\market-sentry\\artifacts\\ABC.bundle.json"
    },
    {
      "symbol": "XYZ",
      "metadata_path": "C:\\market-sentry\\artifacts\\XYZ.metadata.json",
      "bundle_path": "C:\\market-sentry\\artifacts\\XYZ.bundle.json"
    }
  ]
}
```

Then configure the local process and run once:

```powershell
$env:MARKET_SENTRY_PROVIDER = "live_composed"
$env:MARKET_SENTRY_ALLOW_LIVE_DATA = "true"
$env:MARKET_SENTRY_WATCHLIST = "ABC,XYZ"
$env:MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH = "C:\market-sentry\artifacts\rvol-artifacts.json"
$env:ALPACA_API_KEY = "<your key>"
$env:ALPACA_API_SECRET = "<your secret>"
$env:FMP_API_KEY = "<your key>"

python -m market_sentry
```

The command may make network requests only after local artifact validation succeeds.

---

## Non-Goals

Phase 18A must not add:

```text
--loop support for live_composed
automatic historical-bar capture
automatic metadata construction
automatic artifact discovery
directory scanning
glob/rglob
artifact freshness inference
market-calendar inference
time-zone/session inference
relative-volume recalculation during the scan
new CLI flags
new environment variables beyond the manifest path
automatic voice alerts
FMP historical session metadata usage
order placement
brokerage trading
portfolio behavior
position management
buy/sell recommendations
background jobs
scheduling
persistent database storage
```

`--speak` remains an existing explicit opt-in. Phase 18A does not enable voice by default; ordinary one-shot live-composed scans run with `speak=False`.

`--loop` with `live_composed` must be rejected before factory construction and before any HTTP request.

---

## Required Files

Create:

```text
docs/70_ONE_SHOT_LIVE_COMPOSED_SCANNER_ACTIVATION.md
src/market_sentry/data/local_rvol_artifact_manifest.py
src/market_sentry/data/local_rvol_artifact_provider.py
tests/test_local_rvol_artifact_manifest.py
tests/test_local_rvol_artifact_provider.py
```

Modify:

```text
src/market_sentry/config.py
src/market_sentry/data/factory.py
src/market_sentry/main.py
src/market_sentry/live_readiness.py
tests/test_config.py
tests/test_provider_factory.py
tests/test_main.py
tests/test_live_readiness.py
README.md
```

Do not modify:

```text
src/market_sentry/data/live_composed_provider.py
src/market_sentry/data/live_provider_builder.py
src/market_sentry/data/live_candidate_builder.py
src/market_sentry/data/alpaca.py
src/market_sentry/data/alpaca_fetcher.py
src/market_sentry/data/fmp.py
src/market_sentry/data/fmp_fetcher.py
src/market_sentry/data/http.py
src/market_sentry/data/http_stdlib.py
Phase 14–17 capture, writer, loader, and preflight modules
scanner modules
alert modules
voice modules
manual capture CLI modules
```

Reuse existing components; do not duplicate their parsing, data composition, or transport behavior.

---

# Part A — Configuration and Gate

## New Configuration Field

Add to `AppConfig`:

```python
rvol_artifact_manifest_path: Path | None = None
```

`load_config` must read only:

```text
MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH
```

Rules:

```text
- absent, empty, or whitespace-only → None;
- otherwise → Path(value.strip());
- do not resolve, expanduser, absolutize, verify existence, read the path,
  inspect directories, or discover files during config loading;
- preserve existing config parsing behavior for every other field.
```

## Live Provider Gate

Add:

```python
MISSING_RVOL_ARTIFACT_MANIFEST_PATH = "MISSING_RVOL_ARTIFACT_MANIFEST_PATH"
```

to `LiveProviderGateFailure`.

`validate_live_provider_gate` must append that failure after the existing FMP-key check when:

```text
config.rvol_artifact_manifest_path is None
```

The gate order is exactly:

```text
PROVIDER_NOT_LIVE_COMPOSED
LIVE_DATA_NOT_ALLOWED
MISSING_WATCHLIST
MISSING_ALPACA_API_KEY
MISSING_ALPACA_API_SECRET
MISSING_FMP_API_KEY
MISSING_RVOL_ARTIFACT_MANIFEST_PATH
```

Do not read the manifest during gate validation.

---

# Part B — Explicit Local RVOL Artifact Manifest

## Purpose

The manifest is the only local artifact selector used by live-composed activation.

It maps explicit symbols to explicit metadata and bundle paths. It is not a database, directory convention, glob, or discovery mechanism.

The manifest itself is read only once per provider construction attempt.

## Public Model

Create `src/market_sentry/data/local_rvol_artifact_manifest.py`.

Provide:

```python
class LocalRvolArtifactManifestError(ValueError):
    """Raised for invalid explicit local RVOL artifact manifests."""
```

```python
@dataclass(frozen=True)
class LocalRvolArtifact:
    symbol: str
    metadata_path: Path
    bundle_path: Path
```

```python
@dataclass(frozen=True)
class LocalRvolArtifactManifest:
    path: Path
    artifacts: tuple[LocalRvolArtifact, ...]
```

```python
def load_local_rvol_artifact_manifest(
    path: Path,
) -> LocalRvolArtifactManifest:
    """Load one explicit local RVOL artifact manifest."""
```

## Loader Rules

```text
- `path` must be an actual pathlib.Path, or raise:
  TypeError("path must be a pathlib.Path.")
- retain the exact caller-owned Path object;
- call path.read_text(encoding="utf-8") exactly once per load;
- parse with json.loads;
- no cache;
- no resolve, absolute, expanduser, glob, rglob, directory scan, or fallback;
- standard FileNotFoundError, PermissionError, IsADirectoryError,
  UnicodeDecodeError, and json.JSONDecodeError propagate unchanged.
```

## Manifest Envelope

The root must be a JSON object:

```json
{
  "schema_version": 1,
  "artifacts": []
}
```

Rules:

```text
- schema_version must be exactly a real integer 1;
- bool, float, string, null, and integers other than 1 are unsupported;
- artifacts must be a JSON array;
- empty artifacts is structurally valid;
- unknown root keys and unknown artifact keys are ignored;
- artifact key names are case-sensitive.
```

Use only these stable manifest errors:

```text
INVALID_ENVELOPE_ROOT
MISSING_SCHEMA_VERSION
UNSUPPORTED_SCHEMA_VERSION
MISSING_REQUIRED_FIELD:<path>
INVALID_MAPPING:<path>
INVALID_SEQUENCE:<path>
INVALID_STRING:<path>
EMPTY_SYMBOL:<path>
DUPLICATE_SYMBOL:<symbol>
SAME_ARTIFACT_PATH:<symbol>
```

Each artifact entry requires:

```text
symbol
metadata_path
bundle_path
```

Rules:

```text
- artifact must be a JSON object;
- symbol must be a string; normalize through existing RVOL symbol normalization;
- an empty/whitespace symbol → EMPTY_SYMBOL:artifacts[index].symbol;
- metadata_path and bundle_path must each be nonempty strings;
- convert their literal strings directly to Path objects;
- do not rebase relative paths to the manifest path;
- do not resolve aliases;
- direct same Path equality for metadata_path/bundle_path → SAME_ARTIFACT_PATH:<normalized symbol>;
- duplicate normalized symbols → DUPLICATE_SYMBOL:<normalized symbol>;
- preserve artifact input order.
```

No manifest loader may read metadata or bundle files.

---

# Part C — Prevalidated Local RVOL Artifact Provider

## Purpose

Create `src/market_sentry/data/local_rvol_artifact_provider.py`.

This provider consumes an already-loaded manifest and uses the existing two-path offline preflight helper to obtain RVOL values for the requested watchlist.

It performs no HTTP work.

## Public Model

Provide:

```python
class LocalRvolArtifactProviderError(ValueError):
    """Raised when an explicit local artifact cannot yield usable RVOL."""
```

```python
@dataclass(frozen=True)
class LocalRvolArtifactPreflightResult:
    symbol: str
    artifact: LocalRvolArtifact
    preflight_result: ManualLocalJsonBundlePreflightResult
```

```python
class LocalRvolArtifactProvider:
    """Read-only RVOL provider backed by explicit local artifact paths."""

    def __init__(self, manifest: LocalRvolArtifactManifest) -> None:
        ...

    @property
    def latest_results(self) -> tuple[LocalRvolArtifactPreflightResult, ...]:
        ...

    def get_relative_volumes(
        self,
        symbols: Sequence[str],
    ) -> dict[str, float]:
        ...
```

The constructor must retain the exact manifest object. It performs no metadata/bundle reads.

## Provider Rules

`get_relative_volumes(symbols)` must:

1. normalize requested symbols through existing `normalize_symbols`;
2. return `{}` without file reads when no normalized symbols are requested;
3. require one manifest artifact for every requested symbol:
   ```text
   MISSING_ARTIFACT:<SYMBOL>
   ```
4. call existing:
   ```python
   run_manual_local_json_bundle_preflight(
       artifact.metadata_path,
       artifact.bundle_path,
   )
   ```
   exactly once for each requested symbol, preserving requested-symbol order;
5. require complete preflight success:
   ```python
   is_manual_local_json_bundle_preflight_success(result)
   ```
6. require a non-`None` final relative volume;
7. return a normalized `dict[str, float]`;
8. retain fresh ordered `LocalRvolArtifactPreflightResult` wrappers in `latest_results`.

For a returned non-success preflight result, raise:

```text
ARTIFACT_PREFLIGHT_FAILED:<SYMBOL>
```

For a success predicate with no final RVOL, raise:

```text
MISSING_RVOL:<SYMBOL>
```

Expected source/load errors from the underlying preflight helper may propagate unchanged. Do not catch, re-render, or convert them.

The provider must not:

```text
call main
call a CLI parser
render reports
write files
call a network API
call a transport
call capture/writer modules
call a scanner
cache RVOL values between calls
```

Every `get_relative_volumes` call must run fresh preflights.

---

# Part D — Live-Composed Factory Activation

## Factory Behavior

Replace the `live_composed` reserved placeholder with one-shot provider construction.

The factory must:

1. normalize provider name as currently implemented;
2. validate the full existing live gate;
3. fail with existing secret-safe `ProviderConfigurationError` formatting when gate fails;
4. load the exact configured artifact manifest;
5. construct `LocalRvolArtifactProvider` from it;
6. call `get_relative_volumes(config.watchlist)` once;
7. only after all local artifact preflights succeed, call existing:
   ```python
   build_live_composed_provider(
       config,
       relative_volume_by_symbol=relative_volumes,
       transport_factory=StdlibHttpTransport,
       alpaca_fetcher_factory=AlpacaSnapshotFetcher,
       fmp_fetcher_factory=FMPFloatFetcher,
   )
   ```
8. return the existing `LiveComposedMarketDataProvider`.

Factory construction must not send HTTP requests. Only calling `provider.get_candidates()` may send network requests through existing fetchers.

## Factory Error Contract

The factory must convert only local artifact manifest/provider errors into:

```text
ProviderConfigurationError(
  "live_composed local RVOL artifacts invalid: <message>."
)
```

Do not expose secret values.

Do not wrap:

```text
FileNotFoundError
PermissionError
IsADirectoryError
UnicodeDecodeError
json.JSONDecodeError
JsonHistoricalSessionMetadataFileSourceError
JsonHistoricalRvolBundleError
```

Those expected local artifact errors should propagate to the existing `main` provider-error boundary only if the existing boundary has been explicitly extended to render them safely. The final main behavior must remain secret-safe and must not show a traceback.

No network transport may be constructed when manifest load or artifact preflight fails.

## Report Label

Add:

```text
live_composed:
  Live Composed One-Shot Scanner Report
  (live Alpaca snapshots + live FMP float + explicit local RVOL artifacts)
```

A single label string is sufficient; do not add hidden data freshness claims.

This report must make it clear that:

```text
- snapshot and float reference data are live;
- RVOL comes from explicit local artifacts;
- this command does not refresh RVOL artifacts.
```

---

# Part E — One-Shot Main Behavior

## No Live-Composed Loop

When `config.provider == "live_composed"` and `args.loop` is true, return exit code `2` before calling the factory or sending HTTP.

Render:

```text
Market Sentry Live Composed Scanner
Result: COMMAND_ERROR
Error: --loop is not available for live_composed in Phase 18A
Note: Phase 18A permits one-shot live-composed scans only. RVOL comes from explicit local artifacts.
```

Loading config is permitted because config selects the provider. No manifest read, artifact preflight, transport construction, fetch, candidate build, or output write may occur on this branch.

`--interval` without `--loop` remains harmless existing syntax and is not newly rejected.

## One-Shot Execution

When `config.provider == "live_composed"` and `args.loop` is false:

```text
load config
→ factory validates local artifacts
→ factory builds provider without HTTP send
→ existing _run_scan executes once
→ provider fetches live snapshots and live float data
→ existing candidate builder and scanner evaluate results
→ existing report prints
```

`--speak` retains its existing explicit opt-in behavior. Default is `False`; Phase 18A introduces no automatic voice output.

Do not change mock, fixture, composed_fixture, manual capture, one-path preflight, bundle preflight, or live-readiness branches.

---

# Part F — Live Readiness

Keep `--live-readiness` local-only. It must not read the manifest, preflight artifacts, construct transport, or call APIs.

Add this check:

```python
RVOL_ARTIFACT_MANIFEST_PATH_PRESENT = "RVOL_ARTIFACT_MANIFEST_PATH_PRESENT"
```

It passes exactly when:

```text
config.rvol_artifact_manifest_path is not None
```

The existing `RELATIVE_VOLUME_SOURCE_PRESENT` signal remains supported, but a Phase 18A-ready report requires both:

```text
RVOL_ARTIFACT_MANIFEST_PATH_PRESENT
RELATIVE_VOLUME_SOURCE_PRESENT
```

The latter still accepts `--relative-volume-configured` as an explicit local readiness signal. This preserves existing CLI syntax while making the live artifact path visible.

Update the readiness report note to state that readiness validates local configuration only and does not read/preflight artifacts or send APIs.

---

# Part G — Required Tests

## Manifest Tests

Create `tests/test_local_rvol_artifact_manifest.py`.

Test:

```text
non-Path error
exact Path object retention
standard file/UTF-8/JSON errors propagate
root/schema/artifact structural errors
strict bool/float/string schema rejection
literal paths are retained without resolve/rebase
empty symbol
duplicate normalized symbols
same direct metadata/bundle path
order preservation
fresh models/no cache
strict source boundary
```

## Local RVOL Artifact Provider Tests

Create `tests/test_local_rvol_artifact_provider.py`.

Test:

```text
constructor retains exact manifest
empty requested symbols returns empty mapping without preflight
missing required artifact
requested-symbol ordering
one preflight per requested symbol
successful mapping and float conversion
returned preflight failure
success with missing RVOL
underlying source/load error propagation
fresh preflights on separate calls
latest result retention
no writes, network, CLI parsing, report rendering, or caching
strict source boundary
```

Monkeypatch only the provider module’s direct preflight/helper symbols.

## Configuration and Readiness Tests

Update tests for:

```text
manifest path absent/blank/path parsing
new live gate failure in exact order
readiness manifest-path check
readiness remains local-only and does not read manifest files
existing readiness syntax/behavior remains intact
```

## Factory Tests

Update `tests/test_provider_factory.py` for:

```text
live gate failure before manifest load/transport construction
missing manifest path is a gate failure
invalid manifest before transport construction
invalid local RVOL preflight before transport construction
healthy manifest + successful local artifact preflight:
  creates exactly one StdlibHttpTransport
  builds existing LiveComposedMarketDataProvider
  makes zero HTTP sends during factory construction
provider.get_candidates with FakeHttpTransport:
  sends one Alpaca snapshot request
  sends one FMP float request per requested symbol
  receives prevalidated local RVOL mapping
  returns scanner-ready candidates
factory artifact failures are secret-safe
```

Use monkeypatched `StdlibHttpTransport`, `AlpacaSnapshotFetcher`, `FMPFloatFetcher`, and builder functions. No live HTTP test is permitted.

## Main Tests

Update `tests/test_main.py` for:

```text
live_composed + --loop:
  exit 2
  config read only
  zero factory/network activity
  stable command error report

live_composed one-shot:
  invokes existing _run_scan once
  uses the explicit live-composed report label
  default speak=False

all existing mock/fixture/composed fixture/manual/preflight branches remain unchanged
```

## End-to-End Fake Transport Test

Use real local artifact JSON files constructed by existing writers or Phase 15I fixtures, plus `FakeHttpTransport` responses.

Run:

```text
load config
→ create live_composed provider
→ provider.get_candidates
→ ScannerEngine scan
```

Assert:

```text
local artifacts preflight successfully to RVOL 2.0
live Alpaca snapshot + FMP float create a candidate
scanner filter outcome is inspectable
no actual network is used
```

---

# Part H — Validation

Run:

```powershell
python -m pytest tests/test_local_rvol_artifact_manifest.py
python -m pytest tests/test_local_rvol_artifact_provider.py
python -m pytest tests/test_config.py
python -m pytest tests/test_live_readiness.py
python -m pytest tests/test_provider_factory.py
python -m pytest tests/test_main.py
python -m pytest
python -m market_sentry
python -m market_sentry --loop --interval 30
python -m market_sentry --local-json-preflight .\does-not-exist.json
python -m market_sentry --local-json-preflight-report .\report.txt
python -m market_sentry --local-json-bundle-preflight .\does-not-exist-metadata.json .\does-not-exist-bundle.json
python -m market_sentry --local-json-bundle-preflight-report .\bundle-report.txt
python -m market_sentry --manual-alpaca-rvol-capture-report .\capture-report.txt
```

Then use only placeholder credentials and a fake/invalid manifest path to verify:

```text
live_composed without manifest path → safe provider configuration failure
live_composed with --loop → stable command error before manifest/HTTP work
```

Do not make a real Alpaca or FMP request during validation.

---

## Acceptance Criteria

Phase 18A is complete when:

```text
- live_composed is no longer a reserved placeholder for one-shot scans;
- it requires existing live config gates plus one explicit local artifact manifest path;
- every configured watchlist symbol must have a successful local artifact preflight RVOL result before any HTTP transport is constructed;
- one-shot live-composed scans use existing Alpaca snapshot, FMP float, candidate-builder, and scanner components;
- live-composed loop mode is rejected before factory/network activity;
- default voice behavior remains disabled;
- scanner report labels disclose the local-artifact RVOL source;
- mock, fixture, composed fixture, manual capture, and local preflight behavior remain unchanged;
- no automated RVOL capture, artifact discovery, scanner loop, order behavior, or background task is added;
- full tests remain green.
```
