# Phase 18B — Explicit Local RVOL Session Seed Builder

## Status

**Planned.** This document defines Phase 18B only.

Phase 17E can manually capture historical/current Alpaca bars only after the caller provides an explicit metadata seed file. Phase 18A can then use the resulting metadata/bundle artifacts for one live-composed scan.

Phase 18B removes the need to hand-author the metadata seed envelope and `$datetime` tags:

```text
explicit session-plan JSON
        ↓
existing historical-session manifest validation
        ↓
existing canonical metadata JSON writer
        ↓
explicit metadata-seed JSON path
        ↓
existing Phase 17E manual Alpaca capture command
```

This is an **offline-only** preparation command. It must not infer exchange calendars, session hours, holidays, early closes, time zones, or cutoff times. The operator supplies every historical session and every timestamp explicitly.

---

## Goal

Add a narrow manual command that turns one caller-selected JSON session plan into the canonical `schema_version: 1` metadata-seed file already consumed by Phase 17E.

```powershell
python -m market_sentry --local-rvol-session-seed <PLAN_PATH> <METADATA_OUTPUT_PATH>
```

The command must:

1. read exactly one explicit session-plan path;
2. parse its explicit symbol, bucket, current session ID, historical sessions, timestamps, and completeness flags;
3. validate the resulting records through the existing `adapt_historical_session_manifest` behavior;
4. render/write the metadata seed only through the existing `write_local_historical_session_metadata` writer;
5. print a secret-safe local report;
6. exit before configuration loading, transport construction, HTTP, Alpaca, FMP, scanning, alerts, or voice playback.

It must not fetch data, preflight a bundle, create a bundle, or activate `live_composed`.

---

## Operator Workflow

The operator selects the actual historical sessions and their timestamps. Phase 18B does not determine whether a date was a trading day or whether it had a regular or shortened market session.

Example explicit plan:

```json
{
  "schema_version": 1,
  "symbol": "AAPL",
  "bucket": "regular",
  "current_session_id": "2026-06-18",
  "sessions": [
    {
      "session_id": "2026-06-17",
      "session_start_timestamp": "2026-06-17T13:30:00Z",
      "session_end_timestamp": "2026-06-17T20:00:00Z",
      "cutoff_timestamp": "2026-06-17T14:00:00Z",
      "is_complete": true
    },
    {
      "session_id": "2026-06-16",
      "session_start_timestamp": "2026-06-16T13:30:00Z",
      "session_end_timestamp": "2026-06-16T20:00:00Z",
      "cutoff_timestamp": "2026-06-16T14:00:00Z",
      "is_complete": true
    }
  ]
}
```

Run:

```powershell
python -m market_sentry --local-rvol-session-seed C:\market-sentry\artifacts\AAPL.session-plan.json C:\market-sentry\artifacts\AAPL.metadata-seed.json
```

On success, use `AAPL.metadata-seed.json` as the Phase 17E `METADATA_INPUT_PATH`. The Phase 17E command remains separately gated and still requires a caller-confirmed live-data request plus valid Alpaca credentials.

The plan’s `current_session_id` is a validation-only target: it must not appear in the historical `sessions` array and is not emitted as a historical metadata record.

---

## Hard Safety Boundaries

Market Sentry is a personal-use scanner with optional local voice alerts. It is **not** a trading bot.

Phase 18B must not add:

```text
Alpaca, FMP, HTTP, WebSocket, or transport construction
configuration loading or environment reads
live-data gates or secrets
market-calendar, holiday, early-close, time-zone, or session-hour inference
date arithmetic to manufacture sessions
automatic session discovery
filesystem discovery, glob, rglob, fallback selection, or directory scans
bundle construction or bundle preflight
Phase 17E capture invocation
Phase 18A live_composed invocation
scanner, loop, alert, or voice behavior
new provider values
order placement, trade execution, position management, or portfolio behavior
persistent database storage
background jobs or scheduling
```

No live HTTP calls are permitted in any Phase 18B test.

Phase 18B must preserve existing mock, fixture, preflight, capture, writer, bundle, live-composed one-shot, scanner, alert, and voice behavior.

---

## Required Files

Create:

```text
docs/71_EXPLICIT_LOCAL_RVOL_SESSION_SEED_BUILDER.md
src/market_sentry/data/local_rvol_session_seed_plan.py
src/market_sentry/local_rvol_session_seed_cli.py
tests/test_local_rvol_session_seed_plan.py
tests/test_local_rvol_session_seed_cli.py
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
src/market_sentry/data/factory.py
src/market_sentry/live_readiness.py
src/market_sentry/data/local_rvol_artifact_manifest.py
src/market_sentry/data/local_rvol_artifact_provider.py
src/market_sentry/data/live_composed_provider.py
src/market_sentry/data/live_provider_builder.py
src/market_sentry/data/live_candidate_builder.py
src/market_sentry/data/http_stdlib.py
src/market_sentry/data/alpaca_historical_bars_fetcher.py
src/market_sentry/data/explicit_alpaca_rvol_bundle_capture.py
src/market_sentry/data/explicit_alpaca_rvol_capture_preflight.py
src/market_sentry/manual_explicit_alpaca_rvol_capture_preflight_cli.py
src/market_sentry/data/json_historical_session_metadata_writer.py
src/market_sentry/data/json_historical_session_metadata_source.py
src/market_sentry/data/historical_session_manifest.py
all existing Phase 15–18A modules except src/market_sentry/main.py
scanner, alert, voice, and provider modules
```

Reuse the existing historical-session manifest adapter and canonical metadata writer. Do not copy their validation or serialization logic.

---

# Part A — Explicit Session Plan

## Plan JSON Shape

The plan root must be a JSON object with these required fields:

```text
schema_version
symbol
bucket
current_session_id
sessions
```

Only `schema_version`, `symbol`, `bucket`, `current_session_id`, and `sessions` are accepted at the root. Unknown root keys are errors.

`schema_version` must be an actual JSON integer exactly equal to `1`; JSON booleans are not integers for this purpose.

Each `sessions` item must be a JSON object with these required and only accepted fields:

```text
session_id
session_start_timestamp
session_end_timestamp
cutoff_timestamp
is_complete
```

Rules:

```text
- `symbol`, `bucket`, and `current_session_id` must be non-empty strings;
- `sessions` must be a non-empty JSON array;
- each session field named `*_timestamp` must be a non-empty ISO-8601 string;
- a trailing `Z` represents UTC and must be accepted;
- all timestamp strings must parse into aware datetime values;
- `is_complete` must be JSON true, not an equivalent integer/string value;
- caller ordering of sessions must be preserved;
- no sorting, date arithmetic, deduplication, filtering, repair, or inferred records are permitted;
- no plan field is read from the environment or a fallback file.
```

The plan parser builds raw metadata records by adding the root `symbol` and `bucket` to each explicit session item. It must then call the existing `adapt_historical_session_manifest(raw_records, request)` with an existing `HistoricalSessionManifestRequest` constructed from the plan identity fields.

The output must be written only when that result has exact status `OK`. This reuses existing behavior for symbol normalization, bucket normalization, duplicate historical session IDs, current-session exclusion, timestamp window rules, cutoff placement, completeness, and same-timezone validation.

The generated output records are the existing validated `HistoricalIntradaySessionMetadata` records rendered by the Phase 17C writer. They contain the existing normalized symbol/bucket behavior; Phase 18B must not invent a second normalization policy.

## Stable Plan Errors

Create:

```python
class LocalRvolSessionSeedPlanError(ValueError):
    """Raised when an explicit local RVOL session plan cannot create metadata."""
```

Use these stable messages for plan-envelope and parsing failures:

```text
INVALID_ENVELOPE_ROOT
UNKNOWN_FIELD:<path>
MISSING_REQUIRED_FIELD:<path>
INVALID_SCHEMA_VERSION
INVALID_MAPPING:<path>
INVALID_SEQUENCE:<path>
EMPTY_SESSIONS
INVALID_STRING:<path>
EMPTY_STRING:<path>
INVALID_TIMESTAMP:<path>
NAIVE_TIMESTAMP:<path>
INVALID_BOOLEAN:<path>
```

For an existing manifest validation failure, raise exactly:

```text
HISTORICAL_SESSION_MANIFEST_INVALID:<manifest status>:<first failing record index or N/A>:<first failing record reason or N/A>
```

The plan loader must not replace standard filesystem/JSON errors. `FileNotFoundError`, `PermissionError`, `IsADirectoryError`, `UnicodeDecodeError`, and `json.JSONDecodeError` propagate unchanged.

---

# Part B — Plan Module

Create `src/market_sentry/data/local_rvol_session_seed_plan.py`.

## Public Surface

```python
@dataclass(frozen=True)
class LocalRvolSessionSeedPlan:
    path: Path
    request: HistoricalSessionManifestRequest
    raw_manifest_records: tuple[Mapping[str, object], ...]


@dataclass(frozen=True)
class LocalRvolSessionSeedBuildResult:
    plan: LocalRvolSessionSeedPlan
    manifest_result: HistoricalSessionManifestResult
    metadata_records: tuple[HistoricalIntradaySessionMetadata, ...]


def load_local_rvol_session_seed_plan(path: Path) -> LocalRvolSessionSeedPlan:
    """Load one explicit JSON session plan without writing output."""


def build_local_rvol_session_seed(
    plan: LocalRvolSessionSeedPlan,
) -> LocalRvolSessionSeedBuildResult:
    """Validate one plan through the existing historical-session manifest."""


def write_local_rvol_session_seed(
    output_path: Path,
    plan: LocalRvolSessionSeedPlan,
) -> LocalRvolSessionSeedBuildResult:
    """Build and write one canonical metadata seed using the existing writer."""
```

Required behavior:

```text
- every public path argument must be an actual pathlib.Path;
- `load_local_rvol_session_seed_plan` non-Path error:
  TypeError("path must be a pathlib.Path.");
- `write_local_rvol_session_seed` non-Path output error:
  TypeError("output_path must be a pathlib.Path.");
- `build_local_rvol_session_seed` wrong plan type error:
  TypeError("plan must be a LocalRvolSessionSeedPlan.");
- retain exact caller-supplied plan and output Paths;
- no resolve, absolute, expanduser, environment expansion, discovery, glob, read-back, directory creation, caching, or output fallback;
- load reads the exact plan once with UTF-8 and json.loads;
- build performs no filesystem writes;
- write completes plan validation before invoking the existing writer;
- write calls `write_local_historical_session_metadata` exactly once after a successful build;
- write returns the build result and does not read the written output.
```

`raw_manifest_records` must be immutable to callers. Use protected copied mappings (for example, `MappingProxyType`) so callers cannot mutate the recorded plan content after load.

### Allowed Production Imports

`local_rvol_session_seed_plan.py` may import only:

```text
standard library:
  collections.abc.Mapping
  dataclasses
  datetime
  json
  pathlib.Path
  types.MappingProxyType

project:
  market_sentry.data.historical_session_assembly.HistoricalIntradaySessionMetadata
  market_sentry.data.historical_session_manifest.HistoricalSessionManifestRequest
  market_sentry.data.historical_session_manifest.HistoricalSessionManifestResult
  market_sentry.data.historical_session_manifest.HistoricalSessionManifestStatus
  market_sentry.data.historical_session_manifest.adapt_historical_session_manifest
  market_sentry.data.json_historical_session_metadata_writer.write_local_historical_session_metadata
```

No CLI, config, network, transport, capture, bundle, preflight, scanner, alerts, or voice imports are allowed.

---

# Part C — Offline CLI Helper

Create `src/market_sentry/local_rvol_session_seed_cli.py`.

## Public Surface

```python
@dataclass(frozen=True)
class LocalRvolSessionSeedCommandRequest:
    plan_path: Path
    metadata_output_path: Path


class LocalRvolSessionSeedCommandError(ValueError):
    """Raised for invalid local RVOL session-seed command inputs."""


def validate_local_rvol_session_seed_command(
    command: LocalRvolSessionSeedCommandRequest,
) -> None:
    ...


def run_local_rvol_session_seed(
    command: LocalRvolSessionSeedCommandRequest,
) -> LocalRvolSessionSeedBuildResult:
    ...


def render_local_rvol_session_seed_report(
    result: LocalRvolSessionSeedBuildResult,
) -> str:
    ...


def render_local_rvol_session_seed_command_error(
    command: LocalRvolSessionSeedCommandRequest,
    error: BaseException,
) -> str:
    ...


def render_local_rvol_session_seed_error(
    command: LocalRvolSessionSeedCommandRequest,
    error: BaseException,
) -> str:
    ...
```

Validation requirements:

```text
- `plan_path` non-Path → TypeError("plan_path must be a pathlib.Path.");
- `metadata_output_path` non-Path → TypeError("metadata_output_path must be a pathlib.Path.");
- equal plan/output Paths → LocalRvolSessionSeedCommandError("PLAN_PATH_EQUALS_METADATA_OUTPUT");
- no configuration, secret, gate, network, capture, bundle, preflight, scanner, alert, or voice behavior.
```

Success report must include:

```text
Market Sentry Local RVOL Session Seed
Plan Path: <exact path>
Metadata Path: <exact path>
Input Mode: EXPLICIT_SESSION_PLAN
Symbol: <normalized symbol>
Bucket: <normalized bucket>
Current Session ID: <normalized current session ID>
Historical Sessions: <count>
Result: WRITTEN
Note: This operation is offline-only. It uses caller-supplied sessions and timestamps, writes only the explicit metadata path, and does not infer calendars or call APIs.
```

Command-error and operation-error reports must include the two exact paths, a distinct `Result: COMMAND_ERROR` or `Result: ERROR`, and a secret-safe error message. Do not emit a traceback, process environment, credentials, headers, or URLs.

Allowed imports are standard library plus only `local_rvol_session_seed_plan` public surfaces and `pathlib.Path` / `dataclasses` / `typing` support.

---

# Part D — Main CLI Wiring

Modify `src/market_sentry/main.py` only as needed to expose:

```text
--local-rvol-session-seed PLAN_PATH METADATA_OUTPUT_PATH
```

Requirements:

```text
- parse both values as Path;
- the command is mutually exclusive with:
  --loop
  non-default --interval
  --live-readiness
  --relative-volume-configured
  --speak / --no-speak
  --local-json-preflight
  --local-json-preflight-report
  --local-json-bundle-preflight
  --local-json-bundle-preflight-report
  --manual-alpaca-rvol-capture and every manual capture option;
- a conflicting invocation prints one stable command error listing conflicting flags in raw argument order and exits 2;
- a valid seed command runs before load_config, provider factory construction, live readiness, scanner, alerts, voice, transport, or HTTP;
- command validation errors exit 2;
- filesystem/JSON/plan/write operational errors exit 1;
- successful seed generation exits 0;
- normal app behavior and every existing command’s parsing/exit behavior stay unchanged.
```

Add narrowly scoped helper functions rather than changing existing preflight/capture semantics. The new command must not reuse manual capture confirmation, live-data config, or provider gates.

---

# Part E — README

Add a concise “Build an Explicit RVOL Session Seed” section near the existing manual capture material.

It must show:

```text
1. the exact plan JSON shape;
2. one command invocation;
3. that every date/time/session is caller supplied;
4. that the command does no API call and needs no keys;
5. that output is an input to the existing Phase 17E manual capture command;
6. that the plan/output path must be distinct.
```

Do not advertise automatic captures, calendars, scheduled scans, loop activation, trading, or order behavior.

---

# Part F — Tests

Create `tests/test_local_rvol_session_seed_plan.py` covering at minimum:

```text
- canonical successful plan → existing writer-compatible metadata JSON;
- exact plan/output Path retention;
- no output on invalid plan;
- plan loader does not write output;
- no output-parent creation;
- `Z` timestamp parsing and canonical `$datetime` output;
- non-Path stable TypeErrors;
- empty sessions;
- unknown/missing root and session keys;
- bool schema version rejection;
- empty identity fields;
- invalid/naive timestamp input;
- incomplete session;
- current session present in history;
- duplicate historical session ID;
- invalid start/end window;
- cutoff outside session;
- manifest failure exact stable wrapped error;
- tuple/mapping immutability;
- no environment/config/network/capture/bundle/preflight/scanner imports or calls.
```

Create `tests/test_local_rvol_session_seed_cli.py` covering at minimum:

```text
- success report and exit-compatible result;
- distinct path requirement;
- command path type errors;
- invalid plan creates no metadata output;
- output write failure surfaces as operation error;
- no config load, environment read, transport construction, HTTP, capture, bundle, preflight, scanner, alerts, or voice work.
```

Extend `tests/test_main.py` covering at minimum:

```text
- exact flag parsing;
- success exit 0 and report;
- command validation exit 2;
- plan/operational failure exit 1;
- command runs before load_config/provider/transport;
- every listed conflict exits 2;
- raw conflicting flag order remains deterministic;
- normal mock/fixture/composed/live-composed one-shot behavior remains unchanged;
- existing manual preflight/capture command behavior remains unchanged.
```

Run:

```powershell
python -m pytest tests/test_local_rvol_session_seed_plan.py
python -m pytest tests/test_local_rvol_session_seed_cli.py
python -m pytest tests/test_main.py
python -m pytest
python -m compileall -q src
```

---

## Acceptance Checklist

Phase 18B is complete only when:

```text
[ ] The operator can build canonical metadata seed JSON from one explicit session plan.
[ ] The session plan contains all dates/timestamps; no market calendar or session inference exists.
[ ] Existing manifest validation and canonical metadata writing are reused, not copied.
[ ] The command does not load configuration and does not require or read API keys.
[ ] The command makes no live request and constructs no transport.
[ ] Invalid plans produce no output file.
[ ] The plan/output paths must be distinct.
[ ] Existing manual capture can consume the generated output as its metadata input.
[ ] Existing live-composed one-shot remains one-shot only.
[ ] Full test suite and compile checks pass.
[ ] No trading or order behavior exists.
```
