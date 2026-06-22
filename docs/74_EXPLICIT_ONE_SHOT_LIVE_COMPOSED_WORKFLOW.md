# Phase 18E — Explicit One-Shot Live-Composed Workflow

## Purpose

Phase 18E adds one deliberately gated command that performs a **single explicit
live-composed workflow** from a caller-selected plan:

```text
explicit workflow plan
→ explicit Alpaca historical/current capture for every declared artifact
→ canonical metadata + bundle outputs
→ canonical local RVOL artifact manifest write
→ full manifest-wide offline audit
→ one live-composed scan
```

The operator invokes one command after storing required secrets locally in the
current shell/session:

```powershell
python -m market_sentry --one-shot-live-composed-workflow C:\market-sentry\plans\aapl-workflow.json --one-shot-live-composed-confirm-live-data
```

This is a one-shot **diagnostic scanner**, not a trading system. It must not
place orders, submit trades, activate a loop, infer dates/sessions, refresh
without an explicit plan, or enable voice alerts by default.

## Why this phase exists

The approved components already exist, but an operator must currently run them
one by one:

```text
Phase 18B session seed
→ Phase 17E capture + preflight
→ Phase 18D manifest writer
→ Phase 18C manifest audit
→ Phase 18A one-shot live_composed scan
```

Phase 18E composes those components under one additional explicit command and
one additional explicit CLI confirmation. It does **not** change their
individual behavior or relax their boundaries.

## Non-goals

Phase 18E must not:

- add `--loop` support for `live_composed`;
- infer the current trading day, historical sessions, market calendar, cutoff,
  timestamps, buckets, page limits, or symbols;
- discover seed/metadata/bundle files, search directories, glob, resolve,
  rebase, or fall back to alternate paths;
- create directories;
- add an `.env` loader or persist/read secrets;
- place orders, use trading endpoints, or add broker/trading behavior;
- add automatic alerts or automatic voice playback;
- modify existing Phase 17E capture, Phase 18A factory, Phase 18B seed,
  Phase 18C audit, or Phase 18D writer contracts;
- cache outputs, retry calls, clean up or roll back earlier explicit writes;
- introduce report-file outputs.

A capture or scan result may be printed only to stdout. The only intended writes
are the plan-declared metadata outputs, bundle outputs, and manifest output.

## Operator prerequisites

The operator must set these **locally** before invoking the command:

```powershell
$env:MARKET_SENTRY_ALLOW_LIVE_DATA = "true"
$env:ALPACA_API_KEY = "..."
$env:ALPACA_API_SECRET = "..."
$env:FMP_API_KEY = "..."
```

The command derives all of the following from the explicit workflow plan:

- provider: `live_composed`;
- watchlist: declared artifact symbols in plan order;
- RVOL manifest path: the declared manifest output path.

Therefore it must not require `MARKET_SENTRY_PROVIDER`,
`MARKET_SENTRY_WATCHLIST`, or `MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH` to be
pre-set. Values supplied through those environment variables must not change the
workflow’s plan-derived provider, watchlist, or manifest output path.

## New CLI surface

Add exactly:

```text
--one-shot-live-composed-workflow PLAN_PATH
--one-shot-live-composed-confirm-live-data
```

`--one-shot-live-composed-workflow` takes one `pathlib.Path`.
`--one-shot-live-composed-confirm-live-data` is `store_true`.

The command must require both flags. The confirmation flag without the workflow
flag is a command dependency error. The workflow flag without confirmation is a
command error. Both return exit code `2` before config load, plan read, writes,
transport construction, or HTTP.

The workflow command owns dispatch when its workflow flag is supplied and no
higher-priority local command owns dispatch. Preserve fixed command ownership:

1. Phase 18B session seed
2. Phase 18C artifact audit
3. Phase 18D manifest writer
4. Phase 18E one-shot live-composed workflow
5. existing local/manual/provider paths

When a higher-priority command appears with the workflow flag, the
higher-priority command renders the conflict before any work. When Phase 18E
owns dispatch, reject all existing command/flag modes, including:

- `--loop`, `--interval`, `--live-readiness`,
  `--relative-volume-configured`, `--speak`, `--no-speak`;
- all Phase 15J/15K local JSON preflight and report flags;
- all Phase 17E manual Alpaca capture flags;
- Phase 18B seed flags;
- Phase 18C audit flag;
- Phase 18D writer and declaration flags.

Conflicts must be de-duplicated and rendered in raw argv first-occurrence order.
For this command, `--speak --no-speak` must reach the workflow’s stable conflict
renderer, not argparse mutual-exclusivity handling.

`--loop` remains prohibited. Do not run `run_loop` from this command.

## Explicit workflow-plan contract

Create a strict plan loader module. It reads exactly one caller-selected UTF-8
JSON file once using `Path.read_text(encoding="utf-8")` and `json.loads`.
Standard filesystem, decode, and JSON parse errors propagate unchanged to the
workflow CLI error renderer.

The loader takes only a real `pathlib.Path`; otherwise raise exactly:

```text
path must be a pathlib.Path.
```

Retain the caller `Path` exactly. Do not resolve, absolute, expand, rebase,
discover, glob, scan, cache, or read any declared artifact path during plan
loading.

Plan envelope:

```json
{
  "schema_version": 1,
  "manifest_output_path": "C:\\market-sentry\\artifacts\\aapl-manifest.json",
  "artifacts": [
    {
      "symbol": "AAPL",
      "metadata_input_path": "C:\\market-sentry\\plans\\aapl-seed.json",
      "metadata_output_path": "C:\\market-sentry\\artifacts\\aapl-metadata.json",
      "bundle_output_path": "C:\\market-sentry\\artifacts\\aapl-bundle.json",
      "historical_start": "2026-05-18T13:30:00Z",
      "historical_end": "2026-06-18T14:00:00Z",
      "historical_max_pages": 25,
      "current_start": "2026-06-18T13:30:00Z",
      "current_end": "2026-06-18T14:00:00Z",
      "current_max_pages": 2,
      "current_session_id": "2026-06-18",
      "bucket": "regular",
      "cutoff": "2026-06-18T14:00:00Z",
      "minimum_historical_sessions": 20,
      "timeframe": "1Min",
      "page_limit": 1000,
      "sort": "asc"
    }
  ]
}
```

- `schema_version` must be exact real `int` 1 (not bool).
- `manifest_output_path` must be a non-empty string and becomes a literal `Path`.
- `artifacts` must be a non-empty JSON array; preserve declaration order.
- Unknown object keys are ignored.
- Each artifact requires every field shown above.
- `symbol` must be normalized by existing `normalize_symbol`.
- All string fields must be non-empty strings; no stripping/reformatting except
  existing symbol normalization.
- Integer fields must be real `int` values, never bool.
- `sort` must be exactly `asc` or `desc`.
- `timeframe` must be passed through as the caller’s non-empty string; the
  existing capture command validates it downstream where appropriate.
- Every artifact’s `metadata_input_path`, `metadata_output_path`, and
  `bundle_output_path` must be literal `Path` values.

Use stable plan errors:

```text
INVALID_ENVELOPE_ROOT
MISSING_SCHEMA_VERSION
UNSUPPORTED_SCHEMA_VERSION
MISSING_REQUIRED_FIELD:<path>
INVALID_MAPPING:<path>
INVALID_SEQUENCE:<path>
INVALID_STRING:<path>
INVALID_INTEGER:<path>
EMPTY_ARTIFACTS
EMPTY_SYMBOL:<path>
DUPLICATE_SYMBOL:<SYMBOL>
INVALID_SORT:<path>
SAME_CAPTURE_PATH:<SYMBOL>
MANIFEST_OUTPUT_COLLISION:<SYMBOL>
DUPLICATE_OUTPUT_PATH:<path>
```

Path conflict policy uses only direct literal `Path` equality:

For each artifact:

- `metadata_input_path`, `metadata_output_path`, and `bundle_output_path` must
  be pairwise distinct; otherwise `SAME_CAPTURE_PATH:<SYMBOL>`.
- `manifest_output_path` must differ from all three; otherwise
  `MANIFEST_OUTPUT_COLLISION:<SYMBOL>`.

Across artifacts, all declared metadata output paths and bundle output paths
must be mutually distinct. No output path may equal another artifact’s input
metadata path. Detect the first conflict in declaration order as:

```text
DUPLICATE_OUTPUT_PATH:<field-path>
```

The plan loader performs only structural/path validation. It must not read the
seed input files or determine whether any declared output exists.

## New plan model

Create frozen public models:

```python
class OneShotLiveComposedWorkflowPlanError(ValueError): ...

@dataclass(frozen=True)
class OneShotLiveComposedWorkflowArtifact:
    symbol: str
    metadata_input_path: Path
    metadata_output_path: Path
    bundle_output_path: Path
    historical_start: str
    historical_end: str
    historical_max_pages: int
    current_start: str
    current_end: str
    current_max_pages: int
    current_session_id: str
    bucket: str
    cutoff: str
    minimum_historical_sessions: int
    timeframe: str
    page_limit: int
    sort: str

@dataclass(frozen=True)
class OneShotLiveComposedWorkflowPlan:
    path: Path
    manifest_output_path: Path
    artifacts: tuple[OneShotLiveComposedWorkflowArtifact, ...]

load_one_shot_live_composed_workflow_plan(path: Path) -> OneShotLiveComposedWorkflowPlan
```

## Workflow execution contract

Create an orchestration module with frozen request/result models and a small
command-facing API. It must reuse existing components rather than duplicate
business logic:

1. Use `run_manual_explicit_alpaca_rvol_capture_preflight` for each plan
   artifact. Construct the existing manual capture command request exactly from
   plan values, with `report_output_path=None` and `confirm_live_data=True`.
   Pass the loaded config and an injected/reused transport as appropriate.
2. Capture artifacts in plan order. Each capture includes existing metadata
   source loading, Alpaca historical/current fetching, canonical metadata and
   bundle writing, and existing offline preflight.
3. A capture must reach existing capture success before moving to the next
   artifact. If it returns a non-success result, stop the workflow. Do not
   write the manifest, audit, build a provider, call FMP, or scan.
4. After every capture succeeds, call the existing Phase 18D manifest writer
   exactly once with the plan manifest output path and `LocalRvolArtifact`
   values in plan order.
5. After the manifest writer succeeds, call existing Phase 18C
   `run_local_rvol_artifact_audit` exactly once on that exact manifest path.
   If the audit is not entirely successful, stop before provider/transport
   construction for the scanner, FMP, snapshots, and scanning.
6. Only after capture, manifest write, and audit all succeed, derive a runtime
   config with `dataclasses.replace` from `load_config()`:

   ```python
   provider=LIVE_COMPOSED_PROVIDER
   watchlist=tuple(artifact.symbol for artifact in plan.artifacts)
   rvol_artifact_manifest_path=plan.manifest_output_path
   ```

   The plan-derived values win even if provider/watchlist/manifest environment
   variables are set.
7. Call existing `create_market_data_provider(derived_config)` once. It retains
   the Phase 18A factory’s final local artifact validation before live transport
   construction.
8. Call the existing scanner/report pathway once, with the existing live report
   label. Voice is not used. Do not call `run_loop`.

The workflow is deliberately not transactional: previously successful explicit
metadata/bundle writes remain if a later capture, manifest write, audit, or
scan fails. Do not delete or modify them after a failure.

## Gate and network ordering

Before plan read, output writes, transport construction, historical Alpaca,
FMP, snapshot, or scanner work:

- require valid command shape;
- require `--one-shot-live-composed-confirm-live-data`;
- reject conflicts.

After successful plan load but before any capture/network:

- call `load_config()` exactly once;
- require `MARKET_SENTRY_ALLOW_LIVE_DATA` through existing config semantics;
- require Alpaca key/secret;
- require FMP key;
- do not require environment provider/watchlist/manifest path.

Use stable command failures:

```text
LIVE_DATA_CONFIRMATION_REQUIRED
ENV_LIVE_DATA_NOT_ALLOWED
MISSING_ALPACA_API_KEY
MISSING_ALPACA_API_SECRET
MISSING_FMP_API_KEY
```

No network may occur before all plan structural validation and the applicable
config/live-key gates succeed.

- historical Alpaca traffic may occur only during explicit capture stages;
- FMP and live snapshot traffic may occur only after all capture stages,
  manifest write, manifest audit, and final factory artifact validation pass;
- nothing can call a network endpoint when the plan is invalid, confirmation is
  absent, configuration/keys fail, any capture fails, manifest writing fails,
  or audit fails.

## Reports and exit statuses

Create a stable combined terminal report with stages in this order:

```text
Market Sentry Explicit One-Shot Live-Composed Workflow
Plan Path: <literal plan path>
Manifest Path: <literal manifest path>
Artifacts: <count>

Capture 1 ...
...
Manifest Write: ...
Artifact Audit: ...
Live Scan: ...
Result: OK | FAILED | ERROR | COMMAND_ERROR
Note: ...
```

You may reuse existing capture and audit renderers as embedded stage content,
but do not write their reports to files. The final scanner section must use the
existing ordinary scan report with the existing Phase 18A live-composed label.

Exit statuses:

- `0`: every capture, manifest write, audit, provider build, and one scan
  succeeds;
- `1`: expected operational failure, returned capture/audit failure,
  provider configuration failure, output `OSError`, expected HTTP/fetch error,
  or other expected workflow error;
- `2`: invalid command shape, confirmation missing, conflicts, bad plan
  structure, or missing required live configuration/key gate.

Do not print secrets.

## Required code boundaries

Create only:

```text
src/market_sentry/data/one_shot_live_composed_workflow_plan.py
src/market_sentry/one_shot_live_composed_workflow_cli.py
tests/test_one_shot_live_composed_workflow_plan.py
tests/test_one_shot_live_composed_workflow_cli.py
```

Modify only:

```text
src/market_sentry/main.py
tests/test_main.py
README.md
docs/74_EXPLICIT_ONE_SHOT_LIVE_COMPOSED_WORKFLOW.md
```

Do not modify:

```text
src/market_sentry/config.py
src/market_sentry/data/factory.py
src/market_sentry/data/local_rvol_artifact_manifest.py
src/market_sentry/data/local_rvol_artifact_provider.py
src/market_sentry/data/local_rvol_artifact_manifest_writer.py
src/market_sentry/local_rvol_artifact_manifest_writer_cli.py
src/market_sentry/local_rvol_artifact_manifest_audit_cli.py
src/market_sentry/manual_explicit_alpaca_rvol_capture_preflight_cli.py
src/market_sentry/data/explicit_alpaca_rvol_capture_preflight.py
src/market_sentry/data/explicit_alpaca_rvol_bundle_capture.py
src/market_sentry/data/alpaca*.py
src/market_sentry/data/fmp*.py
src/market_sentry/data/http*.py
src/market_sentry/data/live_*.py
src/market_sentry/scanner/
src/market_sentry/alerts/
```

The command may import and invoke public existing interfaces from those modules.
It must not alter them.

## Required tests

Plan tests must cover:

- exact caller plan `Path` retention, no cache/resolve/discovery;
- envelope/field/type/boolean-as-int rejection;
- empty artifacts;
- symbol normalization and duplicate normalized symbols;
- sort validation;
- literal direct path conflicts, output collisions, cross-artifact output
  collisions, and first-error ordering;
- loader reads plan exactly once and does not read declared artifacts;
- AST/source boundary: allowed standard-library/import dependencies only.

Workflow/CLI tests must cover:

- confirmation absent: exit 2 before plan read/config/transport/HTTP;
- malformed plan: exit 2 before config/transport/HTTP/writes;
- environment/key gate errors before capture/network;
- plan provider/watchlist/manifest values override incompatible environment
  values;
- capture request construction exactly reflects each artifact plan entry;
- each capture executes in declared order;
- returned failed capture stops later capture/manifest/audit/provider/FMP/scan;
- expected capture exception stops subsequent stages;
- manifest writer occurs exactly once after all captures succeed;
- audit occurs exactly once after writer and before provider construction;
- audit failure blocks provider/FMP/snapshot/scan;
- provider factory called exactly once only after audit success;
- scanner runs exactly once with voice disabled and no loop;
- fake transport proves historical Alpaca requests precede FMP/snapshot work;
- no FMP/snapshot request before all local safety stages pass;
- no command output writes beyond explicit metadata/bundle/manifest files;
- command conflicts in raw first-occurrence/de-duplicated order;
- seed and audit retain fixed higher-priority ownership;
- existing mock, fixture, composed fixture, local preflights, manual capture,
  readiness, 18A one-shot scan, 18B seed, 18C audit, and 18D writer tests
  remain unchanged.

## Manual verification target

With a saved explicit AAPL workflow plan and local secrets present, the final
operator command should be one line:

```powershell
python -m market_sentry --one-shot-live-composed-workflow "C:\market-sentry\plans\aapl-workflow.json" --one-shot-live-composed-confirm-live-data
```

It must remain meaningful only when every caller-selected timestamp in the plan
corresponds to real intended market sessions. It must not substitute Saturday,
a holiday, or inferred calendar assumptions on the operator’s behalf.
