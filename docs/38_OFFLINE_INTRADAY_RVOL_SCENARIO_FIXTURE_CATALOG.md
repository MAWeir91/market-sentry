# Phase 13J — Offline Intraday RVOL Scenario Fixture Catalog

## Goal

Phase 13J adds a small, curated catalog of deterministic, offline fixture scenarios that exercise the completed Phase 13H/13I intraday-RVOL-to-candidate path.

The catalog is test data only. It does not add a runtime data provider, a new `MARKET_SENTRY_PROVIDER` value, a CLI command, a network source, or live activation.

The intended test-only flow is:

```text
selected named scenario
-> explicit intraday RVOL fixture inputs
-> Phase 13H offline fixture RelativeVolumeProvider
-> Phase 13I offline candidate-composition harness
-> existing LiveCandidateBuilder with local snapshot/float source adapters
-> inspectable candidates and native skipped-symbol diagnostics
```

## Why This Phase Exists

Phases 13E through 13I established reusable offline pieces, but their tests define many fixtures independently. A compact catalog provides stable, readable scenarios that future offline integration tests can reuse without duplicating ad hoc data setup.

The catalog must contain raw explicit inputs only. It must not precompute or override cumulative volume, time-of-day RVOL, candidate fields, candidate scores, or skip reasons.

## Required Scenarios

Expose deterministic named fixtures covering at least:

| Stable name | Purpose |
|---|---|
| `valid_runner` | Valid intraday RVOL, valid snapshot, and valid float produce a candidate. |
| `missing_rvol_invalid_history` | An invalid historical intraday fixture prevents a usable RVOL mapping; Phase 13I must preserve the existing candidate builder's missing-RVOL skip. |
| `missing_snapshot` | A valid RVOL mapping with no local snapshot remains a native missing-snapshot builder skip. |
| `invalid_float` | A valid RVOL mapping and snapshot with invalid float data remains a native invalid-float builder skip. |
| `duplicate_symbols` | Multiple RVOL fixture inputs for the same normalized symbol demonstrate Phase 13H's last-successful-result behavior reaching candidate composition unchanged. |
| `all_skipped` | Multiple requested symbols produce no candidate while preserving their distinct lower-level and builder diagnostics. |

Do not add a broad or generated market universe. These are explicit, hand-curated, deterministic local fixtures only.

## Expected Files

Create:

```text
src/market_sentry/data/intraday_rvol_scenario_catalog.py
tests/test_intraday_rvol_scenario_catalog.py
```

Update only if useful:

```text
README.md
```

Do not modify runtime activation, provider factory registration, the CLI, live readiness, transports, fetchers, Phase 13E/F/G/H/I production modules, scanner logic, alerts, or existing fixture providers.

## Suggested Public Model

A scenario should make all data needed for a local test adapter explicit. For example:

```python
@dataclass(frozen=True)
class OfflineIntradayRvolScenarioFixture:
    name: str
    description: str
    requested_symbols: tuple[str, ...]
    rvol_fixture_inputs: tuple[IntradayRelativeVolumeHarnessInput, ...]
    snapshots_by_symbol: Mapping[str, AlpacaSnapshot]
    float_data_by_symbol: Mapping[str, FMPFloatData | None]
```

Exact field names can vary, but each scenario must expose:

- a stable name and short description;
- explicit requested symbols;
- explicit Phase 13H-compatible intraday RVOL fixture inputs;
- local normalized snapshot fixtures keyed by symbol;
- local normalized float fixtures keyed by symbol, including the ability to represent missing or invalid float data.

The scenario model is data only. It must not create a provider, a candidate builder, a composition harness, a transport, or a fetcher.

## Suggested Public Functions

Provide a small, deterministic public surface, such as:

```python
def get_offline_intraday_rvol_scenarios() -> tuple[OfflineIntradayRvolScenarioFixture, ...]: ...

def get_offline_intraday_rvol_scenario(
    name: str,
) -> OfflineIntradayRvolScenarioFixture: ...

def offline_intraday_rvol_scenario_names() -> tuple[str, ...]: ...
```

Exact names can vary. Required behavior:

- scenarios are returned in a stable documented order;
- names are stable and unique;
- lookup is exact and must fail clearly for an unknown name rather than fabricate a scenario;
- caller mutations cannot alter catalog state or another call's returned scenario data;
- the catalog returns no random, current, fetched, or environment-derived data.

Use immutable tuples and immutable/copy-protected mappings where practical. A frozen dataclass alone is not enough if its mappings remain mutable.

## Fixture Rules

### Intraday RVOL Inputs

Use actual existing fixture models only:

```text
IntradayRelativeVolumeHarnessInput
IntradayVolumeSeriesInput
IntradayVolumeBar
```

Each valid RVOL input must be sufficiently complete for the existing Phase 13H provider and Phase 13G harness to calculate a valid Phase 13E result under their current validation rules. This means supplying the required number of historical series for the existing default time-of-day RVOL lookback; do not lower or bypass that validation.

For invalid-history scenarios, make the historical series explicitly invalid through existing Phase 13F validation rules. Do not add a custom error code or special-case behavior in the catalog.

The catalog must not call Phase 13E, 13F, 13G, or 13H to calculate or validate any value while being built.

### Snapshot and Float Inputs

Use actual existing models only:

```text
AlpacaSnapshot
FMPFloatData
```

The catalog may contain a missing snapshot by omitting the requested symbol from the snapshot mapping. It may represent an invalid float with an explicit `FMPFloatData` fixture that the existing candidate composition path will reject. Do not create new candidate-validation logic in the catalog.

Keep all snapshot and float values local, fixed, and non-secret.

### No Calendar or Time-Zone Inference

Timestamps, session IDs, cutoff timestamps, and bucket labels are fixed caller-supplied fixture values. The catalog must not:

- parse strings into timestamps;
- derive or convert time zones;
- infer regular trading hours;
- infer exchange sessions, holidays, early closes, halts, or split adjustments;
- generate session IDs from dates.

## Integration-Test Expectations

The catalog module itself remains data-only. Its tests may create local fake snapshot and float source adapters using the scenario's exposed mappings, then compose the existing layers explicitly:

```text
scenario fixture inputs
-> OfflineIntradayRelativeVolumeFixtureProvider
-> local fake snapshot source + local fake float source
-> LiveCandidateBuilder
-> OfflineIntradayRvolCandidateCompositionHarness
```

At a minimum, test that:

- `valid_runner` produces one successful candidate and the candidate RVOL equals the RVOL returned through Phase 13H;
- `missing_rvol_invalid_history` produces no candidate and retains Phase 13H diagnostic results plus the builder's native missing-RVOL skip;
- `missing_snapshot` produces no candidate and remains a native builder missing-snapshot skip;
- `invalid_float` produces no candidate and remains a native builder invalid-float skip;
- `duplicate_symbols` proves the last successful normalized Phase 13H RVOL reaches the candidate unchanged;
- `all_skipped` produces no candidates while retaining every requested symbol's relevant diagnostics/skips;
- scenarios are immutable/deterministic and return in stable order;
- unknown lookup fails clearly;
- no scenario constructs providers, factories, transports, fetchers, or runtime configurations;
- no network/HTTP, credentials, URLs, environment variables, or trading/order hooks are introduced;
- existing mock, fixture, composed-fixture, Alpaca-placeholder, live-composed-placeholder, and readiness smoke behavior remains unchanged.

## Explicit Non-Goals

Phase 13J must not:

- register a new provider or modify provider factory behavior;
- add a `MARKET_SENTRY_PROVIDER` value;
- activate `live_composed`;
- fetch intraday bars, snapshots, floats, or RVOL;
- construct `StdlibHttpTransport`, Alpaca/FMP fetchers, or live providers;
- alter the `LiveCandidateBuilder`, Phase 13H provider, or Phase 13I harness;
- calculate candidate scores or produce scanner reports;
- enable order placement, trade execution, buy/sell/enter/exit guidance, or trading automation.

## README Note

If the README is updated, keep it brief:

```text
Phase 13J adds a deterministic offline intraday RVOL scenario fixture catalog.
It supplies explicit reusable test scenarios for the existing offline RVOL-to-candidate path.
It does not fetch data, register a runtime provider, infer market sessions, or activate live mode.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```
