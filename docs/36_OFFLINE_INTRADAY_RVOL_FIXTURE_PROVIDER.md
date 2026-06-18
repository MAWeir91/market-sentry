# Phase 13H — Offline Intraday RVOL Fixture Provider

## Status

Planned. This phase is **offline, fixture-driven, and non-runtime-active**.

## Goal

Expose the completed Phase 13G end-to-end intraday RVOL harness through the existing Phase 12E `RelativeVolumeProvider` contract.

The new provider accepts explicitly supplied `IntradayRelativeVolumeHarnessInput` fixtures, runs them through the existing Phase 13G harness, and returns only successful, requested RVOL values in the existing mapping shape:

```text
caller-supplied intraday RVOL fixture inputs
→ Phase 13G harness
→ inspectable harness results
→ requested successful normalized-symbol-to-RVOL mapping
→ existing candidate-building path can consume that explicit mapping
```

This is a controlled offline provider for tests and future injected wiring. It is **not** a new runtime scanner provider and does not activate `live_composed`.

## Existing Modules to Reuse

- `market_sentry.data.relative_volume`
  - `RelativeVolumeProvider`
  - `normalize_symbols(...)`
- `market_sentry.data.intraday_rvol_harness`
  - `IntradayRelativeVolumeHarnessInput`
  - `IntradayRelativeVolumeHarnessResult`
  - `IntradayRelativeVolumeHarnessStatus`
  - `calculate_intraday_time_of_day_relative_volume_results(...)`

The provider must reuse the Phase 13G harness. It must not duplicate or independently calculate:

- cumulative intraday volume;
- cutoff selection;
- historical cumulative volumes;
- same-bucket historical baseline;
- final time-of-day RVOL.

Phase 13F continues to own intraday cumulative-volume construction. Phase 13E continues to own final TOD RVOL validation/calculation. Phase 13G continues to coordinate those two modules. Phase 13H only exposes successful Phase 13G values through the established relative-volume provider contract.

## Non-Goals

Do not add:

- runtime registration in `data/factory.py`;
- a new `MARKET_SENTRY_PROVIDER` value;
- `live_composed` activation;
- CLI flags, CLI report changes, polling changes, or alert/voice changes;
- HTTP/network calls, URLs, API keys, WebSockets, streaming, or external dependencies;
- Alpaca/FMP fetching or transport wiring;
- historical-bar fetching;
- broad-market scanning, screener use, exchange crawling, or symbol discovery;
- calendar/session/time-zone inference or conversion;
- persistent storage, dashboards, or UI;
- order APIs, order placement, trade execution, or buy/sell/enter/exit guidance.

Market Sentry remains a scanner, not a trading bot.

## Important Limitations

All provider input remains caller supplied and fixture driven.

The provider does **not**:

- create or derive bar fixtures;
- choose cutoff timestamps;
- assign bucket labels or session IDs;
- make invalid fixture data usable;
- create default RVOL values for requested symbols;
- return a mapping entry for a failed or missing symbol;
- validate a market calendar, regular-hours status, early close, halt, or exchange session;
- fetch or infer any data.

`live_composed` remains gated and reserved/inactive after this phase.

## Expected Files

Create:

```text
src/market_sentry/data/intraday_rvol_fixture_provider.py
tests/test_intraday_rvol_fixture_provider.py
```

Update only if useful:

```text
README.md
```

Do not modify unless absolutely necessary:

```text
src/market_sentry/main.py
src/market_sentry/data/factory.py
src/market_sentry/config.py
src/market_sentry/live_readiness.py
src/market_sentry/data/live_provider_builder.py
src/market_sentry/data/live_composed_provider.py
src/market_sentry/data/live_candidate_builder.py
src/market_sentry/data/relative_volume.py
src/market_sentry/data/intraday_rvol_harness.py
src/market_sentry/data/intraday_bucket_adapter.py
src/market_sentry/data/time_of_day_rvol.py
src/market_sentry/data/http.py
src/market_sentry/data/http_stdlib.py
src/market_sentry/data/alpaca_fetcher.py
src/market_sentry/data/fmp_fetcher.py
scanner filters/scoring/tiers
alerts/voice/cooldowns
mock/fixture/composed fixture providers
```

## Suggested Provider Shape

Exact names may vary, but the role and inspectability must be clear.

```python
from collections.abc import Sequence

class OfflineIntradayRelativeVolumeFixtureProvider:
    """Fixture-only RelativeVolumeProvider backed by the Phase 13G harness."""

    def __init__(
        self,
        fixture_inputs: Sequence[IntradayRelativeVolumeHarnessInput],
    ) -> None: ...

    def build_results(self) -> tuple[IntradayRelativeVolumeHarnessResult, ...]: ...

    @property
    def latest_results(self) -> tuple[IntradayRelativeVolumeHarnessResult, ...]: ...

    def get_relative_volumes(self, symbols: Sequence[str]) -> dict[str, float]: ...
```

Requirements:

- Store an immutable copy of caller-supplied fixture inputs, preserving supplied input order.
- `build_results()` must run the existing Phase 13G ordered-results function over every stored fixture input and return an immutable tuple of its results.
- `latest_results` must expose the most recently built immutable result tuple for diagnostics. It begins as an empty tuple before a build.
- `get_relative_volumes(symbols)` must build/refresh results and return only successful values for the requested normalized symbols.
- The class must structurally satisfy the existing `RelativeVolumeProvider` protocol without modifying that protocol.

A different class name is acceptable only if its offline, fixture-only role is obvious.

## Provider Behavior

### Input fixtures

- Fixture inputs are `IntradayRelativeVolumeHarnessInput` objects already governed by the Phase 13F/13E/13G contracts.
- Preserve fixture input order.
- Do not mutate fixture inputs or lower-level result objects.
- Do not validate or reinterpret lower-level fields independently.

### Result construction

- `build_results()` must call Phase 13G's `calculate_intraday_time_of_day_relative_volume_results(...)` exactly as the source of harness outcomes.
- Do not call Phase 13E or Phase 13F directly from this provider.
- Do not recompute or alter RVOL values.
- Each build result—including failures—must remain visible through `latest_results`.

### Requested symbol handling

Use existing Phase 12E symbol normalization behavior:

```text
trim surrounding whitespace
uppercase
ignore empty requested symbols
preserve requested-symbol order for lookup purposes
```

The returned mapping must:

- contain only requested normalized symbols;
- contain only Phase 13G results where `status == OK` and `relative_volume` is present;
- retain the successful RVOL value exactly as returned by Phase 13G;
- omit requested symbols with no fixture result;
- omit failed fixture results;
- never manufacture `0`, `1`, or any default RVOL value.

### Duplicate fixture-input behavior

For all stored fixtures, Phase 13G runs in supplied order.

For requested successful outputs:

```text
- keys use the normalized symbol exposed by the Phase 13G result;
- last successful duplicate normalized symbol wins;
- failed duplicate inputs do not erase a prior successful mapping value;
- an unsuccessful first duplicate followed by a successful duplicate produces the later success;
- all failed/missing requested symbols produce no mapping entry.
```

A failed fixture for one symbol must not prevent a separate valid requested symbol from being returned.

### Empty cases

- No fixture inputs → `build_results() == ()`; every request returns `{}`.
- Empty requested symbol sequence → `{}`. It may still refresh diagnostic results, but it must not return values for unrequested symbols.
- All fixture inputs fail → `{}`; `latest_results` preserves the failures.

## Existing Candidate-Building Compatibility

This phase may demonstrate, using local fake/fixture sources only, that the mapping returned by this provider is accepted by the existing candidate-building interface that takes `relative_volume_by_symbol`.

This is only contract compatibility:

```text
fixture provider get_relative_volumes(requested_symbols)
→ explicit mapping
→ existing candidate builder accepts that mapping
```

It must not:

- register the provider in a factory;
- call `build_live_composed_provider` as a runtime activation path;
- change `LiveCandidateBuilder` or `LiveComposedMarketDataProvider`;
- create a real transport/fetcher;
- cause a network request.

## Secret Safety

This module must not accept, store, print, or log:

- credentials;
- authorization headers;
- raw request representations;
- API keys;
- provider secrets;
- URLs containing secrets.

The source must stay independent of provider configuration and HTTP modules.

## Tests Required

Add coverage for:

- provider structurally works as a `RelativeVolumeProvider` without changing the protocol;
- valid Phase 13G fixture input produces a requested RVOL mapping;
- returned RVOL exactly matches the Phase 13G harness result;
- requested symbols normalize with trim/uppercase;
- empty requested symbols are ignored;
- unrequested valid fixture symbols are excluded;
- missing requested symbols are omitted rather than defaulted;
- empty fixture input collection returns empty results and `{}`;
- failed fixture result is omitted while remaining inspectable via `latest_results`;
- a failed fixture for one symbol does not block another valid requested symbol;
- all-invalid fixture inputs return `{}` while preserving diagnostics;
- deterministic duplicate behavior: last successful normalized fixture result wins; failed duplicate does not erase earlier success; later success replaces earlier success;
- `build_results()` preserves fixture order and returns an immutable tuple;
- `latest_results` starts empty and is updated after builds;
- the provider invokes the Phase 13G ordered result path, not direct Phase 13E/13F calculation;
- optional local compatibility test: mapping can be passed to the existing candidate-building path using fake/offline snapshot/float sources;
- no HTTP/network calls;
- no credentials, URLs, provider-factory, transport, fetcher, runtime activation, or trading/order hooks;
- default mock runtime still works;
- fixture and composed_fixture remain offline;
- Alpaca remains placeholder;
- `live_composed` remains gated/reserved inactive;
- full test suite passes.

## README

Keep any README update brief:

- Phase 13H adds an offline intraday RVOL fixture provider.
- It exposes Phase 13G fixture-harness results through the existing relative-volume provider contract.
- It returns only successful requested RVOL values and never fabricates missing values.
- It does not fetch data, infer calendar/session behavior, register a runtime provider, or activate live mode.
- `live_composed` remains reserved/inactive.
- Trading/order functionality remains out of scope.

## Acceptance Boundary

After Phase 13H:

- Explicit, fixture-derived intraday TOD RVOL can be exposed through the established `RelativeVolumeProvider` interface.
- The results stay inspectable for successful and failed fixtures.
- Existing candidate-building code can consume the returned explicit mapping without any runtime/factory change.
- No live provider is registered or activated.
- No HTTP/network behavior exists in the provider or runtime path.
