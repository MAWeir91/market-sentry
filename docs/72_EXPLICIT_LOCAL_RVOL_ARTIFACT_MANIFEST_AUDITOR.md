# Phase 18C — Explicit Local RVOL Artifact Manifest Auditor

## Status

**Proposed.**

This phase adds one offline-only command that validates every metadata/bundle pair explicitly listed by a Phase 18A local RVOL artifact manifest. It is a diagnostic and readiness aid only. It does not activate a provider, refresh data, or run a scan.

## Goal

Provide a deterministic operator check between artifact creation and a Phase 18A one-shot live-composed scan:

```text
explicit manifest JSON
→ load exact manifest path
→ preflight every declared metadata/bundle pair in manifest order
→ render one complete local audit report
→ return success only when every declared artifact yields final RVOL
```

The command must use the same existing manifest loader and the same existing two-path preflight/success rules that Phase 18A relies on. It must remain entirely local and offline.

## Operator Workflow

After creating one or more metadata/bundle pairs, run:

```powershell
python -m market_sentry --local-rvol-artifact-preflight C:\market-sentry\artifacts\aapl-rvol-manifest.json
```

Example manifest shape is unchanged from Phase 18A:

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

This command is useful on a closed market day because it reads only local artifacts. A successful audit does **not** make a live market scan occur and does **not** establish that the artifacts are current enough for a later operator decision.

## Hard Safety Boundaries

Phase 18C must not:

- load application configuration;
- read environment variables;
- require API keys or live-data permission;
- construct a market-data provider, HTTP transport, Alpaca fetcher, or FMP fetcher;
- make any network request;
- run explicit Alpaca capture;
- write, rewrite, discover, rebase, resolve, glob, or cache artifact paths;
- create a bundle, metadata seed, manifest, or preflight report file;
- call the scanner, alert, voice, or loop paths;
- infer a trading calendar, artifact freshness, session eligibility, or market status;
- change the Phase 18A `live_composed` provider/factory/scanner behavior; or
- add trading, order, broker, or execution behavior.

The command may read only:

1. the single caller-selected manifest path; and
2. the exact metadata and bundle paths literally declared by that manifest.

## Required Files

Create:

```text
docs/72_EXPLICIT_LOCAL_RVOL_ARTIFACT_MANIFEST_AUDITOR.md
src/market_sentry/local_rvol_artifact_manifest_audit_cli.py
tests/test_local_rvol_artifact_manifest_audit_cli.py
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
src/market_sentry/live_composed_provider.py
src/market_sentry/live_provider_builder.py
src/market_sentry/live_candidate_builder.py
src/market_sentry/data/alpaca.py
src/market_sentry/data/http_stdlib.py
src/market_sentry/local_json_bundle_preflight_cli.py
src/market_sentry/local_json_bundle_preflight_report_export.py
src/market_sentry/local_rvol_session_seed_cli.py
src/market_sentry/data/local_rvol_session_seed_plan.py
src/market_sentry/manual_explicit_alpaca_rvol_capture_preflight_cli.py
any Phase 14–17 writer/capture/preflight module
```

Do not add dependencies.

# Part A — Offline Artifact Manifest Audit Helper

Create `src/market_sentry/local_rvol_artifact_manifest_audit_cli.py`.

## Allowed Production Imports

Only these modules may be imported:

```python
from dataclasses import dataclass
from pathlib import Path

from market_sentry.data.local_rvol_artifact_manifest import (
    LocalRvolArtifact,
    LocalRvolArtifactManifest,
    LocalRvolArtifactManifestError,
    load_local_rvol_artifact_manifest,
)
from market_sentry.local_json_bundle_preflight_cli import (
    MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS,
    ManualLocalJsonBundlePreflightResult,
    is_manual_local_json_bundle_preflight_success,
    run_manual_local_json_bundle_preflight,
)
```

No `json` import is needed in this helper. JSON decoding belongs to the existing manifest and bundle-preflight components.

## Public Surface

```python
LOCAL_RVOL_ARTIFACT_AUDIT_NOTE: str
LOCAL_RVOL_ARTIFACT_AUDIT_EXPECTED_ERRORS: tuple[type[BaseException], ...]

@dataclass(frozen=True)
class LocalRvolArtifactAuditCommandRequest:
    manifest_path: Path

@dataclass(frozen=True)
class LocalRvolArtifactAuditEntry:
    index: int
    artifact: LocalRvolArtifact
    status: str
    preflight_result: ManualLocalJsonBundlePreflightResult | None
    relative_volume: float | None
    error_type: str | None
    error_message: str | None

@dataclass(frozen=True)
class LocalRvolArtifactAuditResult:
    manifest: LocalRvolArtifactManifest
    entries: tuple[LocalRvolArtifactAuditEntry, ...]

class LocalRvolArtifactAuditCommandError(ValueError):
    ...

validate_local_rvol_artifact_audit_command(
    command: LocalRvolArtifactAuditCommandRequest,
) -> None

run_local_rvol_artifact_audit(
    command: LocalRvolArtifactAuditCommandRequest,
) -> LocalRvolArtifactAuditResult

is_local_rvol_artifact_audit_success(
    result: LocalRvolArtifactAuditResult,
) -> bool

render_local_rvol_artifact_audit_report(
    command: LocalRvolArtifactAuditCommandRequest,
    result: LocalRvolArtifactAuditResult,
) -> str

render_local_rvol_artifact_audit_command_error(
    command: LocalRvolArtifactAuditCommandRequest,
    error: BaseException,
) -> str

render_local_rvol_artifact_audit_error(
    command: LocalRvolArtifactAuditCommandRequest,
    error: BaseException,
) -> str
```

## Command Validation

`validate_local_rvol_artifact_audit_command` must:

- raise `TypeError("manifest_path must be a pathlib.Path.")` when `manifest_path` is not a real `pathlib.Path`;
- otherwise accept the path literally;
- not resolve, make absolute, expand, inspect, read, scan, or cache it.

There is no output path in this phase, so there is no same-path rule.

## Audit Execution

`run_local_rvol_artifact_audit` must:

1. validate the command;
2. call `load_local_rvol_artifact_manifest(command.manifest_path)` exactly once;
3. iterate `manifest.artifacts` exactly once in manifest input order;
4. for each artifact, call `run_manual_local_json_bundle_preflight(artifact.metadata_path, artifact.bundle_path)` exactly once;
5. call `is_manual_local_json_bundle_preflight_success` exactly once for every preflight result that was returned;
6. continue auditing later manifest artifacts after a locally expected per-artifact preflight exception or a returned unsuccessful preflight result;
7. return one immutable entry per manifest artifact; and
8. never write anything or read a path other than the exact manifest-selected paths.

The command must use three exact entry statuses:

```text
OK      returned preflight passed the existing success predicate and yielded RVOL
FAILED  returned preflight did not pass the existing success predicate
ERROR   the preflight runner raised one of its existing expected local errors
```

For `OK` entries:

- `preflight_result` is the returned result;
- `relative_volume` is the final time-of-day RVOL as `float`;
- `error_type` and `error_message` are `None`.

For `FAILED` entries:

- `preflight_result` is the returned result;
- `relative_volume`, `error_type`, and `error_message` are `None`.

For `ERROR` entries:

- `preflight_result` and `relative_volume` are `None`;
- `error_type` is `error.__class__.__name__`;
- `error_message` is `str(error) or error.__class__.__name__`.

Do not call a provider, and do not reuse `LocalRvolArtifactProvider`. Its stop-on-first-error behavior is intentional for live construction, while this command must complete a diagnostic audit of every manifest entry.

Use the existing success predicate as the source of truth. The final RVOL may be reached through the existing nested preflight result only after the predicate returns true. Do not add a new helper or change existing Phase 15/16/18A modules to expose it.

A structurally valid empty manifest returns an audit result with zero entries and is considered audit-successful. The report must make this visible as `Artifacts: 0`. This command does not assert scanner readiness for an unspecified watchlist.

## Expected Errors

Define:

```python
LOCAL_RVOL_ARTIFACT_AUDIT_EXPECTED_ERRORS = (
    OSError,
    UnicodeDecodeError,
    LocalRvolArtifactManifestError,
    *MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS,
)
```

Do not deduplicate the tuple if existing types overlap. This is an explicit public catch surface for `main.py`.

Manifest-load exceptions occur before there is an audit result and propagate to `main.py` for one operation-level error report. Per-artifact exceptions listed by `MANUAL_LOCAL_JSON_BUNDLE_PREFLIGHT_EXPECTED_ERRORS` are captured into `ERROR` entries so that the rest of the manifest is still audited.

Unexpected exceptions must propagate unchanged.

## Success Predicate

`is_local_rvol_artifact_audit_success` returns `True` only when every entry has `status == "OK"`. An empty tuple therefore returns `True`.

It must not reread files, rerun preflight, or mutate the result.

## Stable Note

Use exactly:

```python
LOCAL_RVOL_ARTIFACT_AUDIT_NOTE = (
    "Note: This command reads only one explicit local RVOL artifact manifest "
    "and the metadata/bundle paths it declares. It does not load config, "
    "call APIs, activate providers, scan candidates, or play voice alerts."
)
```

## Stable Reports

### Successful/Completed Audit Report

`render_local_rvol_artifact_audit_report` must render entries in manifest order using exactly this structure:

```text
Market Sentry Local RVOL Artifact Preflight
Manifest Path: <literal command manifest path>
Input Mode: EXPLICIT_LOCAL_RVOL_ARTIFACT_MANIFEST
Artifacts: <count>
Artifact 1 Symbol: <normalized symbol>
Artifact 1 Metadata Path: <literal manifest metadata path>
Artifact 1 Bundle Path: <literal manifest bundle path>
Artifact 1 Result: <OK|FAILED|ERROR>
Artifact 1 Relative Volume: <1-decimal x value or N/A>
Artifact 1 Error Type: <error type or N/A>
Artifact 1 Error: <error message or N/A>
...
Result: <OK|FAILED>
<LOCAL_RVOL_ARTIFACT_AUDIT_NOTE>
```

Rules:

- numbering begins at 1, independently of the stored zero-based `entry.index`;
- `Relative Volume` uses `f"{value:.1f}x"` when non-`None`, otherwise `N/A`;
- `Error Type` and `Error` use `N/A` when their values are `None`;
- a complete audit with one or more `FAILED` or `ERROR` entries has final `Result: FAILED`;
- an empty valid manifest renders no artifact blocks and has final `Result: OK`;
- paths are rendered with `str(path)` exactly; and
- do not include tracebacks, secrets, environment values, provider names, or live-data claims.

### Command Error Report

```text
Market Sentry Local RVOL Artifact Preflight
Manifest Path: <literal command manifest path>
Result: COMMAND_ERROR
Error: <error message>
<LOCAL_RVOL_ARTIFACT_AUDIT_NOTE>
```

### Operation Error Report

```text
Market Sentry Local RVOL Artifact Preflight
Manifest Path: <literal command manifest path>
Result: ERROR
Error Type: <exception class name>
Error: <error message>
<LOCAL_RVOL_ARTIFACT_AUDIT_NOTE>
```

# Part B — Main CLI Wiring

Modify `src/market_sentry/main.py` only as necessary.

## Parser

Add exactly:

```python
parser.add_argument(
    "--local-rvol-artifact-preflight",
    type=Path,
    default=None,
    metavar="MANIFEST_PATH",
)
```

Do not add report-output, confirmation, live-data, symbol, calendar, freshness, capture, or network options.

## Ordering

The artifact-audit command must run before `load_config()` and before all provider, scanner, manual-capture, local single-pair preflight, local metadata preflight, readiness, alert, voice, and loop work.

Place it after Phase 18B session-seed command handling and before manual capture/local preflight dispatch. It must be selected when its path is present.

## Conflicts

The artifact-audit command is exclusive. It must return exit code `2` before reading the manifest, before config loading, and before any preflight work when combined with any of these:

```text
--loop
--interval <non-default>
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
```

The conflicts must preserve first-occurrence order from raw argv and de-duplicate repeated flags. Render:

```text
Market Sentry Local RVOL Artifact Preflight
Manifest Path: <literal manifest path>
Result: COMMAND_ERROR
Error: --local-rvol-artifact-preflight cannot be combined with: <comma-separated flags>
<LOCAL_RVOL_ARTIFACT_AUDIT_NOTE>
```

Update Phase 18B’s seed-command conflict recognition to reject `--local-rvol-artifact-preflight` in the same no-config/no-work manner. Update any existing raw-argv recognition used to permit local offline command handling with both `--speak` and `--no-speak`, so the new command receives its own deterministic conflict report rather than argparse’s mutually-exclusive error.

No existing command changes its success behavior when this new flag is absent.

## Main Exit Rules

- invalid audit command request → command report, exit `2`;
- manifest-load/operation-level expected exception → operation error report, exit `1`;
- completed audit with every entry `OK` → audit report, exit `0`;
- completed audit containing `FAILED` or `ERROR` entries → audit report, exit `1`.

`main.py` may catch only `LocalRvolArtifactAuditCommandError` for command errors and `LOCAL_RVOL_ARTIFACT_AUDIT_EXPECTED_ERRORS` for operation-level expected errors.

# Part C — Tests

Create `tests/test_local_rvol_artifact_manifest_audit_cli.py`.

Required helper tests:

1. frozen request/result/entry models retain exact literal paths;
2. non-`Path` manifest path produces the exact TypeError;
3. loader is called once with exact path;
4. runner is called once per manifest artifact in manifest order with literal metadata/bundle paths;
5. existing success predicate is called once per returned preflight result;
6. all-OK audit returns `True`, preserves RVOL floats, and renders one-decimal RVOL values;
7. unsuccessful returned preflight becomes `FAILED` and later artifacts are still audited;
8. expected per-artifact source/preflight exception becomes `ERROR`, retains type/message, and later artifacts are still audited;
9. unexpected runner exception propagates unchanged;
10. manifest-load error propagates and no runner is called;
11. valid empty manifest returns a successful zero-entry audit and renders `Artifacts: 0`;
12. reports match exact stable line layouts and contain no traceback; and
13. AST/source boundary proves only the allowed production imports/calls are used and forbids config, env, HTTP, transport, Alpaca, FMP, provider construction, scanner, alert, voice, capture, writer, `resolve`, `absolute`, `expanduser`, `glob`, `rglob`, `mkdir`, `getenv`, and `send`. Check imports and call nodes rather than raw substring presence, because the mandated user-facing note intentionally names excluded behaviors.

Update `tests/test_main.py`.

Required main tests:

1. parser accepts one manifest path and defaults to `None` when absent;
2. successful audit runs before `load_config`, provider construction, scanner, readiness, and network-related seams;
3. malformed/missing manifest returns the stable operation error, exit `1`, and no config/provider work;
4. completed failed audit returns its full report with exit `1` and no config/provider work;
5. raw-order conflict output is deterministic, exit `2`, and the manifest loader/helper is never called;
6. all documented conflicts are rejected independently;
7. `--speak --no-speak` paired with this command yields the command’s conflict report—not argparse’s mutual-exclusivity failure;
8. Phase 18B session seed rejects this new command as a conflict; and
9. existing mock, fixture, composed fixture, local metadata preflight, local bundle preflight, manual capture, one-shot live-composed, readiness, alert, voice, and loop tests retain prior behavior.

# Part D — README

Add one concise “Offline RVOL artifact audit” section.

It must show:

```powershell
python -m market_sentry --local-rvol-artifact-preflight C:\path\to\rvol-artifacts.json
```

It must say that the command preflights only manifest-declared local metadata/bundle paths, reports per-artifact final RVOL when valid, performs no config/API/provider/network/scanner work, and does not refresh or infer data.

Do not document it as live scanning, capture, or automated readiness/freshness verification.

# Part E — Validation

Run:

```powershell
python -m pytest tests/test_local_rvol_artifact_manifest_audit_cli.py
python -m pytest tests/test_main.py
python -m pytest
python -m compileall -q src
```

# Acceptance Checklist

- One explicit manifest path only.
- Manifest uses the existing Phase 18A loader unchanged.
- Every manifest item is audited in order, including later items after earlier local failures.
- Exact literal paths are retained and used.
- No output artifact is written.
- No config, environment, secrets, provider, transport, HTTP, Alpaca, FMP, capture, scanner, alert, voice, or loop work occurs.
- Main exits 0 only when all audited entries are OK.
- Command conflicts exit 2 before any manifest read or local preflight work.
- Existing commands retain behavior.
