# Phase 18D — Explicit Local RVOL Artifact Manifest Writer

## Status

**Proposed.**

This phase adds one offline-only command that writes a canonical Phase 18A local RVOL artifact manifest from explicitly supplied command-line artifact triples. It is an operator-convenience and deterministic serialization step only. It does not inspect the metadata/bundle files, audit them, activate a provider, refresh data, or run a scan.

## Goal

Remove hand-authored manifest JSON from the safe pre-live workflow while preserving the explicit-path contract:

```text
explicit symbol + metadata path + bundle path triples
→ validate the exact literal declarations
→ write one canonical Phase 18A manifest JSON file
→ Phase 18C audits the manifest offline
→ Phase 18A may later use the audited manifest for one one-shot live-composed scan
```

The command must be fully local and must never infer, discover, rebase, resolve, or read artifact contents.

## Operator Workflow

After Phase 17E produces an AAPL metadata/bundle pair, create a manifest with:

```powershell
python -m market_sentry `
  --local-rvol-artifact-manifest-write C:\market-sentry\artifacts\aapl-rvol-manifest.json `
  --local-rvol-artifact AAPL C:\market-sentry\artifacts\aapl-metadata.json C:\market-sentry\artifacts\aapl-bundle.json
```

For multiple symbols, repeat `--local-rvol-artifact` in the desired manifest order:

```powershell
python -m market_sentry `
  --local-rvol-artifact-manifest-write C:\market-sentry\artifacts\watchlist-rvol-manifest.json `
  --local-rvol-artifact AAPL C:\market-sentry\artifacts\aapl-metadata.json C:\market-sentry\artifacts\aapl-bundle.json `
  --local-rvol-artifact MSFT C:\market-sentry\artifacts\msft-metadata.json C:\market-sentry\artifacts\msft-bundle.json
```

The generated shape must be exactly compatible with the existing Phase 18A loader:

```json
{
  "schema_version": 1,
  "artifacts": [
    {
      "symbol": "AAPL",
      "metadata_path": "C:\\market-sentry\\artifacts\\aapl-metadata.json",
      "bundle_path": "C:\\market-sentry\\artifacts\\aapl-bundle.json"
    }
  ]
}
```

Immediately after writing, the operator should run the Phase 18C auditor:

```powershell
python -m market_sentry --local-rvol-artifact-preflight C:\market-sentry\artifacts\aapl-rvol-manifest.json
```

A successful write only says the explicit declarations were serialized correctly. It does **not** say the artifact pair exists, is usable, is fresh, or is ready for a live scan.

## Hard Safety Boundaries

Phase 18D must not:

- load application configuration;
- read environment variables;
- require API keys or live-data permission;
- construct a provider, transport, Alpaca fetcher, or FMP fetcher;
- make any network request;
- load, decode, inspect, audit, preflight, or otherwise read any metadata, bundle, or output manifest file;
- call Phase 18A’s manifest loader or `LocalRvolArtifactProvider`;
- call Phase 18C’s auditor;
- run explicit Alpaca capture;
- write metadata, bundles, preflight reports, scanner reports, or anything other than the requested manifest output;
- create directories, resolve, rebase, make paths absolute, glob, discover artifacts, expand user paths, cache, or read back the output;
- infer trading sessions, market status, freshness, eligibility, or RVOL;
- call scanner, alert, voice, loop, or live-readiness behavior;
- change live-composed factory/provider/scanner behavior; or
- add trading, order, broker, or execution behavior.

The command may only write the exact caller-selected manifest output path. It may not read any file.

## Required Files

Create:

```text
docs/73_EXPLICIT_LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER.md
src/market_sentry/data/local_rvol_artifact_manifest_writer.py
src/market_sentry/local_rvol_artifact_manifest_writer_cli.py
tests/test_local_rvol_artifact_manifest_writer.py
tests/test_local_rvol_artifact_manifest_writer_cli.py
```

Modify:

```text
src/market_sentry/main.py
tests/test_main.py
README.md
```

Do not modify:

```text
src/market_sentry/config.py
src/market_sentry/live_readiness.py
src/market_sentry/data/factory.py
src/market_sentry/data/local_rvol_artifact_manifest.py
src/market_sentry/data/local_rvol_artifact_provider.py
src/market_sentry/local_rvol_artifact_manifest_audit_cli.py
src/market_sentry/local_rvol_session_seed_cli.py
src/market_sentry/data/local_rvol_session_seed_plan.py
src/market_sentry/local_json_bundle_preflight_cli.py
src/market_sentry/local_json_bundle_preflight_report_export.py
src/market_sentry/manual_explicit_alpaca_rvol_capture_preflight_cli.py
src/market_sentry/live_composed_provider.py
src/market_sentry/live_provider_builder.py
src/market_sentry/live_candidate_builder.py
src/market_sentry/data/alpaca.py
src/market_sentry/data/http_stdlib.py
any Phase 14–17 writer/capture/preflight module
```

Do not add dependencies.

# Part A — Canonical Manifest Writer

Create `src/market_sentry/data/local_rvol_artifact_manifest_writer.py`.

## Allowed Production Imports

Only these imports are allowed:

```python
from dataclasses import dataclass
import json
from pathlib import Path

from market_sentry.data.local_rvol_artifact_manifest import LocalRvolArtifact
from market_sentry.data.relative_volume import normalize_symbol
```

The writer must not import the manifest loader. The loader is intentionally read-oriented; this phase is write-only.

## Public Surface

```python
class LocalRvolArtifactManifestWriteError(ValueError):
    ...

@dataclass(frozen=True)
class LocalRvolArtifactManifestWriteRequest:
    output_path: Path
    artifacts: tuple[LocalRvolArtifact, ...]

validate_local_rvol_artifact_manifest_write_request(
    request: LocalRvolArtifactManifestWriteRequest,
) -> tuple[LocalRvolArtifact, ...]

render_local_rvol_artifact_manifest(
    artifacts: tuple[LocalRvolArtifact, ...],
) -> str

write_local_rvol_artifact_manifest(
    request: LocalRvolArtifactManifestWriteRequest,
) -> tuple[LocalRvolArtifact, ...]
```

The returned tuple from validation and write must be a new immutable tuple of normalized `LocalRvolArtifact` values in caller declaration order. The request object itself is not mutated.

## Validation

`validate_local_rvol_artifact_manifest_write_request` must:

1. Require `request` to be a real `LocalRvolArtifactManifestWriteRequest`, otherwise raise:

   ```text
   TypeError: request must be a LocalRvolArtifactManifestWriteRequest.
   ```

2. Require `request.output_path` to be a real `pathlib.Path`, otherwise raise:

   ```text
   TypeError: output_path must be a pathlib.Path.
   ```

3. Require `request.artifacts` to be a tuple, otherwise raise:

   ```text
   TypeError: artifacts must be a tuple.
   ```

4. Require at least one artifact, otherwise raise:

   ```text
   MISSING_ARTIFACTS
   ```

5. Require each item to be a real `LocalRvolArtifact`, otherwise raise:

   ```text
   TypeError: artifacts[<index>] must be a LocalRvolArtifact.
   ```

6. Require every `metadata_path` and `bundle_path` to be a real `pathlib.Path`, otherwise raise:

   ```text
   TypeError: artifacts[<index>].metadata_path must be a pathlib.Path.
   TypeError: artifacts[<index>].bundle_path must be a pathlib.Path.
   ```

7. Normalize each `artifact.symbol` through the existing `normalize_symbol` behavior. A non-string symbol or a normalized empty value must raise:

   ```text
   EMPTY_SYMBOL:artifacts[<index>].symbol
   ```

8. Reject duplicate **normalized** symbols in caller declaration order:

   ```text
   DUPLICATE_SYMBOL:<SYMBOL>
   ```

9. Reject direct `Path` equality of an artifact’s metadata and bundle paths:

   ```text
   SAME_ARTIFACT_PATH:<SYMBOL>
   ```

10. Reject direct `Path` equality between the output manifest path and either input path for any artifact:

   ```text
   OUTPUT_PATH_CONFLICT:<SYMBOL>
   ```

The implementation must not call `resolve`, `absolute`, `expanduser`, `exists`, `is_file`, `is_dir`, `read_text`, `open`, `glob`, `rglob`, or any loader/preflight helper. It must use literal `Path` values exactly as supplied.

## Canonical Rendering

`render_local_rvol_artifact_manifest` must accept only the normalized tuple returned by validation. It must render exactly one canonical UTF-8 JSON document with a trailing newline:

```json
{
  "schema_version": 1,
  "artifacts": [
    {
      "symbol": "AAPL",
      "metadata_path": "...",
      "bundle_path": "..."
    }
  ]
}
```

Requirements:

- Root keys must appear in this order: `schema_version`, then `artifacts`.
- Artifact keys must appear in this order: `symbol`, `metadata_path`, then `bundle_path`.
- Preserve normalized artifact declaration order.
- Render paths as `str(path)` only.
- Use `ensure_ascii=False`, `allow_nan=False`, and `indent=2`.
- Do not use `sort_keys=True`, because required key order is semantic contract.
- Do not add unknown fields, timestamps, absolute paths, comments, or a schema extension.
- The writer does not read the rendered file back through Phase 18A’s loader.

`render_local_rvol_artifact_manifest` must raise:

```text
TypeError: artifacts must be a tuple.
```

when `artifacts` is not a tuple, and:

```text
TypeError: artifacts[<index>] must be a LocalRvolArtifact.
```

for non-artifact items. It must not normalize or inspect filesystem paths. The public writer request validation owns full semantic validation.

## Write Behavior

`write_local_rvol_artifact_manifest` must:

1. validate the request once;
2. render the normalized artifacts once;
3. call only:

   ```python
   request.output_path.write_text(rendered, encoding="utf-8")
   ```

4. return the normalized tuple;
5. create no directories; and
6. not read any path after writing.

`OSError` from `write_text` must propagate unchanged to the CLI wrapper. No partial-output cleanup, fallback path, atomic rename, or retry belongs in this phase.

# Part B — Offline CLI Command

Create `src/market_sentry/local_rvol_artifact_manifest_writer_cli.py`.

## Allowed Production Imports

Only these imports are allowed:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from market_sentry.data.local_rvol_artifact_manifest import LocalRvolArtifact
from market_sentry.data.local_rvol_artifact_manifest_writer import (
    LocalRvolArtifactManifestWriteError,
    LocalRvolArtifactManifestWriteRequest,
    write_local_rvol_artifact_manifest,
)
```

No JSON, config, environment, provider, preflight, capture, scanner, alert, voice, or transport imports are allowed.

## Public Surface

```python
LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_NOTE: str
LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_EXPECTED_ERRORS: tuple[type[BaseException], ...]

@dataclass(frozen=True)
class LocalRvolArtifactManifestWriterCommandRequest:
    output_path: Path | None
    artifact_declarations: tuple[tuple[str, str, str], ...]

@dataclass(frozen=True)
class LocalRvolArtifactManifestWriterCommandResult:
    output_path: Path
    artifacts: tuple[LocalRvolArtifact, ...]

class LocalRvolArtifactManifestWriterCommandError(ValueError):
    ...

validate_local_rvol_artifact_manifest_writer_command(
    command: LocalRvolArtifactManifestWriterCommandRequest,
) -> LocalRvolArtifactManifestWriteRequest

run_local_rvol_artifact_manifest_writer(
    command: LocalRvolArtifactManifestWriterCommandRequest,
) -> LocalRvolArtifactManifestWriterCommandResult

render_local_rvol_artifact_manifest_writer_success_report(
    command: LocalRvolArtifactManifestWriterCommandRequest,
    result: LocalRvolArtifactManifestWriterCommandResult,
) -> str

render_local_rvol_artifact_manifest_writer_command_error(
    command: LocalRvolArtifactManifestWriterCommandRequest,
    error: BaseException,
) -> str

render_local_rvol_artifact_manifest_writer_error(
    command: LocalRvolArtifactManifestWriterCommandRequest,
    error: BaseException,
) -> str
```

Use exactly:

```python
LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_EXPECTED_ERRORS = (
    OSError,
    LocalRvolArtifactManifestWriteError,
)
```

Use exactly:

```python
LOCAL_RVOL_ARTIFACT_MANIFEST_WRITER_NOTE = (
    "Note: This command writes one explicit local RVOL artifact manifest from "
    "command-supplied paths. It does not read artifacts, load config, call APIs, "
    "activate providers, scan candidates, or play voice alerts."
)
```

## Command Validation and Execution

The CLI command request accepts raw artifact declarations only as a tuple of `(symbol, metadata_path_text, bundle_path_text)` triples. The CLI wrapper converts the supplied metadata/bundle text to literal `Path` objects exactly once; it does not inspect those paths.

Validation must enforce:

- `command` otherwise raises `TypeError("command must be a LocalRvolArtifactManifestWriterCommandRequest.")`;
- `output_path is None` with one or more declarations raises `LocalRvolArtifactManifestWriterCommandError("--local-rvol-artifact requires --local-rvol-artifact-manifest-write")`;
- `output_path is None` with zero declarations raises `LocalRvolArtifactManifestWriterCommandError("MISSING_MANIFEST_OUTPUT_PATH")`;
- non-`Path` non-None output path raises `TypeError("output_path must be a pathlib.Path.")`;
- non-tuple `artifact_declarations` raises `TypeError("artifact_declarations must be a tuple.")`;
- each declaration must be a tuple of exactly three real strings, otherwise raise:

  ```text
  INVALID_ARTIFACT_DECLARATION:<index>
  ```

`run_local_rvol_artifact_manifest_writer` must validate once, call `write_local_rvol_artifact_manifest` exactly once, and return a result containing the exact output `Path` plus the normalized immutable artifact tuple returned by the writer.

It must not write before complete validation succeeds. Invalid command or writer inputs therefore create no output file.

## Stable Reports

Success report:

```text
Market Sentry Local RVOL Artifact Manifest Writer
Manifest Path: <literal output path>
Artifacts: <count>
Artifact 1 Symbol: <normalized symbol>
Artifact 1 Metadata Path: <literal metadata path>
Artifact 1 Bundle Path: <literal bundle path>
...
Result: OK
<exact note>
```

Command-error report:

```text
Market Sentry Local RVOL Artifact Manifest Writer
Manifest Path: <literal output path or N/A>
Result: COMMAND_ERROR
Error: <message>
<exact note>
```

Operational-error report:

```text
Market Sentry Local RVOL Artifact Manifest Writer
Manifest Path: <literal output path or N/A>
Result: ERROR
Error Type: <exception class name>
Error: <message or exception class name>
<exact note>
```

No traceback, unredacted secret, artifact content, or filesystem discovery information may be printed.

# Part C — `main.py` Integration

## Parser

Add:

```python
parser.add_argument(
    "--local-rvol-artifact-manifest-write",
    type=Path,
    default=None,
    metavar="MANIFEST_OUTPUT_PATH",
)
parser.add_argument(
    "--local-rvol-artifact",
    action="append",
    nargs=3,
    default=None,
    metavar=("SYMBOL", "METADATA_PATH", "BUNDLE_PATH"),
)
```

The `--local-rvol-artifact` values must remain raw strings until command-wrapper validation constructs literal `Path` objects.

Update the existing raw-argv speak sanitization detector so this mode also receives stable conflict reporting when both `--speak` and `--no-speak` are supplied.

## Dispatch and Ownership

Build a command request from parsed values as:

```python
LocalRvolArtifactManifestWriterCommandRequest(
    output_path=args.local_rvol_artifact_manifest_write,
    artifact_declarations=tuple(
        tuple(item) for item in (args.local_rvol_artifact or [])
    ),
)
```

Use fixed command ownership:

```text
Phase 18B seed command → Phase 18C artifact audit command → Phase 18D manifest writer command → all earlier paths
```

Therefore:

- the Phase 18B seed command must treat `--local-rvol-artifact-manifest-write` and `--local-rvol-artifact` as conflicts and retain ownership when its flag is present;
- the Phase 18C audit command must treat those two flags as conflicts and retain ownership when its flag is present;
- the Phase 18D writer runs when either of its two flags is present and neither earlier owner applies.

The writer branch must appear before all report dependency, manual capture, local bundle/local JSON preflight, live-readiness, configuration, provider, scanner, alert, voice, and loop behavior.

## Writer Conflicts

When Phase 18D owns dispatch, reject these exact flags in first raw-occurrence order with duplicates removed:

```text
--loop
--interval             (only if non-default)
--live-readiness
--relative-volume-configured
--speak
--no-speak
--local-json-preflight
--local-json-preflight-report
--local-json-bundle-preflight
--local-json-bundle-preflight-report
--manual-alpaca-rvol-capture
--manual-alpaca-rvol-capture-report
--manual-alpaca-rvol-capture-confirm-live-data
--manual-alpaca-rvol-capture-symbol
--manual-alpaca-rvol-capture-historical-start
--manual-alpaca-rvol-capture-historical-end
--manual-alpaca-rvol-capture-historical-max-pages
--manual-alpaca-rvol-capture-current-start
--manual-alpaca-rvol-capture-current-end
--manual-alpaca-rvol-capture-current-max-pages
--manual-alpaca-rvol-capture-current-session-id
--manual-alpaca-rvol-capture-bucket
--manual-alpaca-rvol-capture-cutoff
--manual-alpaca-rvol-capture-minimum-historical-sessions
--manual-alpaca-rvol-capture-timeframe
--manual-alpaca-rvol-capture-page-limit
--manual-alpaca-rvol-capture-sort
--local-rvol-session-seed
--local-rvol-artifact-preflight
```

Render exact writer conflict report:

```text
Market Sentry Local RVOL Artifact Manifest Writer
Manifest Path: <literal output path or N/A>
Result: COMMAND_ERROR
Error: --local-rvol-artifact-manifest-write cannot be combined with: <comma-separated conflicts>
<exact note>
```

Return exit `2` before file writes, artifact reads, configuration, provider construction, transport construction, capture, preflight, scanner, alert, voice, or HTTP.

When only `--local-rvol-artifact` is provided, render the specified dependency error and return exit `2` before any work.

When `--local-rvol-artifact-manifest-write` is provided with no declarations, render `MISSING_ARTIFACTS` as a command error and return exit `2` before writing.

For valid command execution:

- writer validation failures are command errors, exit `2`;
- `OSError` is an operational error, exit `1`;
- success is exit `0`.

# Part D — Tests

## `tests/test_local_rvol_artifact_manifest_writer.py`

Cover at minimum:

- immutable request;
- `Path` and tuple type errors;
- empty artifacts;
- invalid artifact item/path types;
- symbol normalization;
- duplicate normalized symbols;
- same metadata/bundle direct path equality;
- output collision with declared metadata or bundle direct path equality;
- no `resolve`, filesystem inspection, loader, preflight, or read calls;
- exact canonical JSON key/order/indent/trailing newline;
- deterministic multi-artifact declaration order;
- write calls `write_text` exactly once with UTF-8;
- no directory creation/readback;
- `OSError` propagates unchanged;
- AST import/call boundary.

## `tests/test_local_rvol_artifact_manifest_writer_cli.py`

Cover at minimum:

- request/result frozen models;
- missing output dependency behavior;
- no output path with no declarations;
- raw declaration shape checks;
- exact literal Path construction;
- writer called exactly once only after validation;
- malformed/duplicate/same-path/output-collision inputs write nothing;
- one/multi artifact success reports;
- error reports have no traceback;
- no config, environment, loader, preflight, provider, transport, capture, scanner, alert, voice, or network imports/calls;
- AST import boundary.

## `tests/test_main.py`

Add coverage for:

- parser support and defaults;
- valid single/multi write before config/provider/scanner/readiness;
- only-artifact dependency error, no writer;
- no-artifact error, no write;
- duplicate/same-path/output-collision errors, no output;
- `OSError` exit `1` operational report;
- all documented writer conflicts, including raw-order/deduplication;
- `--speak --no-speak` gets the writer conflict report rather than argparse’s mutual-exclusivity failure;
- Phase 18B seed owns seed+writer conflicts;
- Phase 18C audit owns audit+writer conflicts;
- existing mock, fixture, composed fixture, local preflight, bundle preflight, manual capture, session seed, artifact audit, live readiness, one-shot live-composed, blocked live loop, alert, voice, scanner, and no-trading behavior remain unchanged.

# Part E — README

Add a concise “Build an explicit local RVOL artifact manifest” section that:

1. shows the one-artifact command;
2. shows repeating `--local-rvol-artifact` for multiple symbols;
3. states it writes only the manifest and does not inspect artifact files;
4. directs the operator to run `--local-rvol-artifact-preflight` immediately afterward;
5. states no API keys or `.env` file are needed; and
6. states this does not activate a live scan.

## Definition of Done

Phase 18D is complete only when:

- it writes the canonical Phase 18A-compatible manifest from explicit command declarations;
- it preserves declaration order and normalized symbols;
- every validation/collision failure prevents output writing;
- it is strictly offline and performs no artifact read or configuration/network/live work;
- it coexists deterministically with Phase 18B and 18C command ownership; and
- all focused tests, the full suite, and compile check pass.
