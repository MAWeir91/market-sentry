# Phase 13I — Offline Intraday RVOL Candidate Composition Harness

## Purpose

Phase 13H exposes successful, fixture-driven Phase 13G intraday RVOL results through the existing `RelativeVolumeProvider` contract. Phase 13I proves that these explicit RVOL values can flow into the existing candidate-composition path without a new runtime provider, network call, or `live_composed` activation.

This phase creates a **pure offline orchestration harness** that combines:

```text
explicit requested symbols
+ injected local snapshot source
+ injected local float source
+ OfflineIntradayRelativeVolumeFixtureProvider
→ requested explicit RVOL mapping
→ existing LiveCandidateBuilder
→ inspectable candidate and skipped-symbol results
```

The harness must not duplicate scanner math, candidate-composition logic, intraday RVOL logic, or provider wiring.

---

## Scope

### In scope

- A small, injectable, fixture-only candidate-composition harness.
- Explicit caller-supplied requested symbols only.
- Reuse of `OfflineIntradayRelativeVolumeFixtureProvider` for RVOL values and inspectable RVOL diagnostics.
- Reuse of the existing `LiveCandidateBuilder` for snapshot + float + RVOL composition.
- Ordered, inspectable output that contains successful `StockCandidate` values and existing skipped-symbol diagnostics.
- Pure local/offline tests using fake snapshot and float sources.
- A brief README roadmap note only if useful.

### Out of scope

- Runtime activation.
- Registering any new factory/provider choice.
- New `MARKET_SENTRY_PROVIDER` values.
- CLI flags or report changes.
- Live API calls, HTTP transports, URLs, WebSockets, or external dependencies.
- Historical-bar fetching.
- Alpaca/FMP fetcher or transport wiring.
- Market-calendar, session, bucket, timestamp, or time-zone inference/conversion.
- Broad-market scanning, symbol discovery, screeners, or exchange crawling.
- Persistent storage, dashboards, or UI.
- Orders, brokerage APIs, trade execution, or buy/sell/enter/exit recommendations.

---

## Existing Components to Reuse

Phase 13I must reuse existing public surfaces rather than copy logic:

```text
market_sentry.data.relative_volume
  normalize_symbols(...)

market_sentry.data.intraday_rvol_fixture_provider
  OfflineIntradayRelativeVolumeFixtureProvider
  get_relative_volumes(...)
  latest_results

market_sentry.data.live_candidate_builder
  LiveCandidateBuilder
  LiveCandidateBuildResult
```

The harness may accept an already constructed `LiveCandidateBuilder`, or accept injected local snapshot/float sources and construct the existing builder in a small controlled constructor. It must not modify the builder and must not instantiate real fetchers, transports, or providers.

The harness must not directly call:

```text
Phase 13F cumulative-volume adapter
Phase 13E time-of-day RVOL calculator
Phase 13G intraday RVOL harness
```

Phase 13H is the only RVOL path used by this phase. `LiveCandidateBuilder` remains the only candidate-composition path used by this phase.

---

## Suggested Models

Use inspectable models with responsibilities that are clear and narrow. Exact names can vary.

```python
@dataclass(frozen=True)
class OfflineIntradayRvolCandidateCompositionRun:
    requested_symbols: tuple[str, ...]
    relative_volumes: Mapping[str, float]
    rvol_results: tuple[IntradayRelativeVolumeHarnessResult, ...]
    candidate_build_results: tuple[LiveCandidateBuildResult, ...]

    @property
    def candidates(self) -> tuple[StockCandidate, ...]: ...

    @property
    def skipped_results(self) -> tuple[LiveCandidateBuildResult, ...]: ...
```

Required output properties:

- `requested_symbols` uses the existing normalized requested-symbol behavior.
- `relative_volumes` contains only successful requested RVOL values returned by Phase 13H.
- `rvol_results` preserves the Phase 13H provider’s latest ordered Phase 13G artifacts, including failures.
- `candidate_build_results` preserves the existing builder’s ordered result objects, including candidate-composition skips.
- `candidates` returns only successful candidate values, in builder-result order.
- `skipped_results` returns only unsuccessful candidate build results, in builder-result order.

Do not replace `LiveCandidateBuildResult` or invent parallel candidate/skip math.

---

## Suggested Public Harness Shape

A clear option is:

```python
class OfflineIntradayRvolCandidateCompositionHarness:
    """Offline-only composition harness for explicit intraday RVOL fixtures."""

    def __init__(
        self,
        candidate_builder: LiveCandidateBuilder,
        relative_volume_provider: OfflineIntradayRelativeVolumeFixtureProvider,
    ) -> None: ...

    @property
    def latest_run(self) -> OfflineIntradayRvolCandidateCompositionRun | None: ...

    def build_run(
        self,
        symbols: Sequence[str],
    ) -> OfflineIntradayRvolCandidateCompositionRun: ...

    def get_candidates(
        self,
        symbols: Sequence[str],
    ) -> list[StockCandidate]: ...
```

Exact class/function names can vary, but the role must be explicitly offline and fixture-only.

`latest_run` begins as `None` and stores the latest completed immutable run object.

---

## Required Behavior

For `build_run(symbols)`:

1. Normalize the caller-supplied requested symbols using existing `normalize_symbols(...)` behavior.
2. Do not add symbols, discover symbols, or use any watchlist/config/environment variable.
3. Call the injected Phase 13H provider’s `get_relative_volumes(normalized_symbols)` exactly once.
4. Capture the provider’s `latest_results` after that call as the run’s `rvol_results`.
5. Pass the same normalized requested symbols plus the provider-returned explicit RVOL mapping into the existing `LiveCandidateBuilder` through its existing public API.
6. Preserve the builder’s result objects as `candidate_build_results` in their returned order.
7. Store and return the completed run as `latest_run`.

Important:

- Pass **all normalized requested symbols** to the existing candidate builder, not only symbols with successful RVOL. This allows the builder’s existing missing-RVOL skip diagnostics to remain visible.
- Do not fabricate a missing RVOL value, a candidate, a snapshot, a float, or a skip reason.
- Do not catch and rewrite valid lower-level diagnostics into generic harness-only errors.
- If the existing builder returns a skip because RVOL is missing, preserve that builder result exactly.
- The harness should not mutate provider results, builder results, fixtures, or caller-supplied symbol sequences.

For `get_candidates(symbols)`:

- Call `build_run(symbols)`.
- Return a list containing only successful `StockCandidate` values from the run, preserving builder-result order.
- An all-skipped run returns `[]`.

---

## Duplicate and Requested-Symbol Behavior

Use the existing `normalize_symbols(...)` behavior exactly. Do not create a second normalization rule.

The harness must:

```text
- only use caller-requested normalized symbols;
- pass those requested symbols to the Phase 13H provider;
- pass those requested symbols to the existing candidate builder;
- return no unrequested candidate merely because a valid fixture exists;
- preserve Phase 13H's last-successful-duplicate RVOL behavior;
- preserve LiveCandidateBuilder's existing duplicate/result behavior rather than reimplementing it;
- expose all RVOL diagnostics and builder diagnostics through the completed run.
```

An empty request must still call the Phase 13H provider’s `get_relative_volumes(())` once, so Phase 13H refreshes `latest_results` as designed. The harness may then call the existing builder with an empty normalized request if its public API supports it; otherwise keep behavior explicit and testable without fabricating build results.

---

## Candidate-Composition Compatibility

The harness should use only existing offline injectable interfaces. A typical local test may use:

```text
fake snapshot source
+ fake float source
+ real LiveCandidateBuilder
+ OfflineIntradayRelativeVolumeFixtureProvider
+ explicit requested symbols
→ run with candidates and skips
```

Do not modify:

```text
LiveCandidateBuilder
LiveComposedMarketDataProvider
build_live_composed_provider
factory.py
main.py
```

Do not instantiate real Alpaca/FMP fetchers, `StdlibHttpTransport`, or any network-capable implementation.

---

## Required Tests

Add focused tests covering at least:

1. A valid requested fixture symbol creates a `StockCandidate` through the real existing `LiveCandidateBuilder` using only fake/local snapshot and float sources.
2. The candidate’s RVOL equals the exact RVOL returned by Phase 13H; the harness does not alter it.
3. A requested symbol with failed/missing Phase 13H RVOL is passed to the builder and remains inspectable as the builder’s existing missing-RVOL skip.
4. A Phase 13H failure for one requested symbol does not block a different valid requested symbol.
5. A candidate-builder failure such as a missing snapshot or invalid float stays inspectable in `candidate_build_results`.
6. `rvol_results` exposes Phase 13H’s lower-level diagnostics for failed fixture data.
7. `candidates` includes successes only, in builder-result order.
8. `skipped_results` includes builder skips only, in builder-result order.
9. `get_candidates(...)` returns the same successful candidate values as the run.
10. Requested-symbol trim/uppercase behavior uses the existing normalizer.
11. Empty/blank requested symbols do not create candidates or fabricated values.
12. Valid but unrequested fixture data does not produce a candidate.
13. A duplicate RVOL fixture’s Phase 13H last-successful behavior reaches candidate composition unchanged.
14. `latest_run` starts as `None` and updates after `build_run(...)` and `get_candidates(...)`.
15. The provider is called exactly once per `build_run(...)` and the builder receives the explicit RVOL mapping.
16. The harness calls no Phase 13E, 13F, or 13G function directly.
17. No HTTP/network calls, credentials, URLs, provider-factory registration, live provider activation, transports, fetchers, or trading/order hooks.
18. Default mock runtime still works.
19. `fixture` and `composed_fixture` remain offline.
20. Alpaca remains a placeholder.
21. `live_composed` remains gated/reserved inactive.
22. Full test suite passes.

---

## README

Keep any README update brief:

```text
Phase 13I adds an offline intraday RVOL candidate-composition harness.
It feeds explicit Phase 13H RVOL mappings into the existing candidate builder with local fixture sources.
It exposes candidates and skipped-symbol diagnostics without fetching data or activating live mode.
It does not fabricate RVOL, snapshot, float, or candidate data.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```

---

## Acceptance Criteria

Phase 13I is complete when:

- The harness is an explicit offline fixture utility, not a runtime/provider-factory choice.
- It calls Phase 13H exactly once for each run and uses its mapping unchanged.
- It passes all requested normalized symbols and that mapping into the existing `LiveCandidateBuilder`.
- It exposes candidates, existing builder skips, and Phase 13H diagnostics without copying their logic.
- It creates no HTTP/network path or live activation path.
- It adds no trading/order functionality.
- The full suite and runtime smoke checks pass.
