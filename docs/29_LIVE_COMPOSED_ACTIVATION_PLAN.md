# Phase 13A - Live Composed Activation Plan

Phase 13A is documentation/specification only. It defines the future activation path for the `live_composed` provider, but it does not activate live data, wire runtime HTTP calls, change scanner behavior, or add provider factory activation.

Market Sentry remains a personal-use low-float momentum scanner with local voice alerts. It is not a trading bot and must never add order execution, brokerage trading/order APIs, or anything that can place trades.

## Current Runtime State

Runtime behavior remains unchanged:

- `mock` is the default provider and uses local static mock data.
- `fixture` is offline and uses static Alpaca/FMP-style fixtures.
- `composed_fixture` is offline and exercises candidate composition with static fixture inputs.
- `alpaca` remains a placeholder and is not a live runtime provider.
- `live_composed` remains a gated, reserved placeholder and is not active even when the gate passes.

Phase 13A adds no runtime activation, no provider factory activation, no live HTTP/network behavior, and no live transport/fetcher runtime wiring.

## Future Activation Path

The future live activation path should be:

```text
config gate
+ local preflight guidance
+ provider factory activation
+ StdlibHttpTransport
+ AlpacaSnapshotFetcher
+ FMPFloatFetcher
+ explicit RVOL source
-> LiveCandidateBuilder
-> LiveComposedMarketDataProvider
-> scanner filters/scoring/report/alerts
```

Scanner runtime should continue consuming scanner-ready `StockCandidate` objects. Provider composition and normalization must happen before scanner evaluation.

## Required Config Gate Behavior

Future `live_composed` activation must require the existing config gate to pass before any live provider is constructed.

The required gate inputs are:

- `MARKET_SENTRY_PROVIDER=live_composed`
- `MARKET_SENTRY_ALLOW_LIVE_DATA=true`
- non-empty `MARKET_SENTRY_WATCHLIST`
- `ALPACA_API_KEY`
- `ALPACA_API_SECRET`
- `FMP_API_KEY`

Gate failures must be secret-safe and should identify missing requirement names, not secret values. The gate must run before transport/fetcher construction and before any live request can be attempted.

If the gate fails, future runtime should stop with a clear message such as:

```text
live_composed is not enabled. Missing requirements: watchlist, alpaca_api_key, fmp_api_key
```

Even when the gate passes today, `live_composed` must remain inactive until a later approved activation phase changes the provider factory.

## Required Preflight Behavior

`python -m market_sentry --live-readiness` remains a local preflight diagnostic. It should not call Alpaca, FMP, or any network API.

Future activation should keep the runtime gate authoritative and use preflight as explicit operator guidance:

- Preflight should mirror the gate checks.
- Preflight should include the explicit RVOL-source readiness check.
- Preflight should report READY or NOT_READY without printing secrets.
- Preflight should not be required as persistent state because Market Sentry has no persistent database.
- A passing preflight should not by itself activate live mode.

Before a future activation phase is accepted, `--live-readiness --relative-volume-configured` should pass with placeholder local configuration and should still avoid provider construction and network access.

## Provider Factory Activation Rules

Future provider factory activation for `live_composed` must be explicit and narrow:

- Only `MARKET_SENTRY_PROVIDER=live_composed` may enter the live composed path.
- Factory activation must occur only after the config gate passes.
- Factory activation must use dependency-injected components so tests can use fake transports/fetchers.
- `mock`, `fixture`, and `composed_fixture` behavior must remain unchanged.
- `alpaca` should remain a placeholder unless a later approved phase retires or redefines it.
- Unknown providers must keep failing cleanly.
- The future factory must not activate live behavior from `mock`, `fixture`, or `composed_fixture`.

The provider factory should fail with a stable, secret-safe message while `live_composed` is still inactive:

```text
live_composed is reserved for a future live provider and is not active yet.
```

## Transport And Fetcher Wiring Plan

Future activation should use existing skeletons with dependency injection:

- `StdlibHttpTransport` for standard-library HTTP requests.
- `AlpacaSnapshotFetcher` for Alpaca market-data snapshots.
- `FMPFloatFetcher` for FMP float/reference lookups.
- `LiveCandidateBuilder` for scanner-ready candidate composition.
- `LiveComposedMarketDataProvider` for watchlist-based candidate retrieval.

The runtime wiring should construct these components only after the live gate passes. Tests must inject fake transports and fake fetchers and must not require internet access.

The future HTTP layer must remain read-only:

- GET/read-only market/reference data only.
- No POST/PUT/PATCH/DELETE write behavior.
- No order endpoints.
- No brokerage account endpoints.
- No credentials, headers, or raw secret-bearing request reprs printed.

## Alpaca Snapshot Scope

Alpaca Market Data is the planned first source for price, volume, high of day, intraday bars, 15-minute change, and daily movement.

Future Alpaca wiring should:

- Use `ALPACA_API_KEY` and `ALPACA_API_SECRET` from config.
- Use `ALPACA_DATA_FEED`, defaulting to `iex` unless a later phase changes it.
- Request data only for symbols in `MARKET_SENTRY_WATCHLIST`.
- Surface request construction failures as secret-safe errors.
- Surface HTTP/status/timeout failures as secret-safe errors.
- Skip symbols with missing or invalid price/volume/movement values.
- Preserve partial symbol failures in provider diagnostics when possible.

Important data-quality risk: Alpaca Basic/free equity data is IEX-only. Broader all-exchange/SIP coverage requires the appropriate Alpaca subscription. IEX-only data may understate true volume for low-float runners.

## FMP Float Scope

Financial Modeling Prep is the planned first source for float/reference data.

Future FMP wiring should:

- Use `FMP_API_KEY` from config.
- Fetch float/reference data for watchlist symbols only.
- Treat float/reference data as potentially stale.
- Cache future float lookups in memory to reduce repeated requests.
- Skip symbols with missing, non-positive, non-numeric, or otherwise invalid float values.
- Surface HTTP/status/timeout failures as secret-safe errors.
- Preserve partial float failures in provider diagnostics when possible.

FMP is not a scanner-ready market-data provider by itself. It should feed composition, not scanner evaluation directly.

## Relative-Volume Strategy

Real `live_composed` activation remains blocked until a real explicit RVOL source exists.

Relative volume must not be fabricated, inferred from unrelated data, or silently defaulted. Phase 13A does not implement an RVOL source.

Approved future behavior is:

- Production live activation must require an explicit real RVOL source.
- A later static/local RVOL mapping may be used only for controlled testing if separately approved.
- Missing RVOL must either block activation or skip affected symbols, depending on the later implementation phase.
- Missing RVOL must be visible in user-facing diagnostics.

Until this is resolved, `live_composed` must remain a gated placeholder.

## Watchlist-Only Boundary

The first live activation must be watchlist-only.

Future runtime should only request data for symbols listed in `MARKET_SENTRY_WATCHLIST`.

Do not add:

- broad-market scanning
- exchange-wide crawling
- all-shares float discovery
- screener endpoint sweeps
- WebSockets
- streaming market data

If the watchlist is empty, the config gate must fail before any provider or transport is constructed.

## Failure Modes And User-Facing Errors

Future activation should define stable, secret-safe errors for:

- Gate failure: stop before provider construction and list missing requirement names.
- Missing watchlist: gate failure; no requests attempted.
- Missing credentials: gate failure; no credential values printed.
- Live provider still inactive: reserved placeholder message until future activation.
- Alpaca request construction failure: stop or skip affected symbols with a secret-safe explanation.
- Alpaca HTTP/status/timeout failure: report provider failure without printing headers/secrets.
- FMP HTTP/status/timeout failure: report provider failure without printing query secrets.
- Missing RVOL source: block activation until the explicit RVOL source exists.
- Missing RVOL for a symbol: skip affected symbol or block activation, as defined by the future phase.
- Alpaca data missing: skip affected symbol and include a diagnostic reason.
- FMP float missing: skip affected symbol and include a diagnostic reason.
- Invalid price/volume/float: skip affected symbol and include a diagnostic reason.
- Partial candidates skipped: continue with valid candidates and report skipped symbol count/reasons.
- All candidates skipped: fail clearly with an all-candidates-skipped warning/error and no fabricated candidates.
- Live mode safe disable: use mock/offline providers or disable allow-live without code changes.

Error messages must avoid secret values, authorization headers, raw request reprs, and trading advice.

## Runtime Safety Boundaries

The first future live activation must preserve these boundaries:

- no trading/order behavior
- no order endpoints
- no brokerage account endpoints
- no account/position/portfolio endpoints
- no write operations to external services
- GET/read-only market/reference data only
- no broad-market scans
- no WebSockets
- no persistent database state
- no credentials printed in logs, errors, repr output, reports, tests, or docs examples

Alert messages may describe market activity but must not recommend buy, sell, enter, exit, guaranteed, or safe-trade actions.

## Future Activation Test Requirements

A later activation phase should add tests for:

- `live_composed` factory activation only after the gate passes and activation is explicitly implemented.
- Gate failures remain secret-safe.
- Missing watchlist and missing credentials fail before transport/fetcher construction.
- Watchlist-only request construction.
- `StdlibHttpTransport` path remains injectable and fakeable.
- No real network access in tests.
- Alpaca request construction and partial data handling.
- FMP missing/invalid float handling.
- RVOL missing-source behavior.
- RVOL missing-symbol behavior.
- All-candidates-skipped behavior.
- Partial-candidates-skipped diagnostics.
- Normal `mock`, `fixture`, and `composed_fixture` providers remain unchanged.
- `alpaca` placeholder behavior remains unchanged unless separately approved.
- `--live-readiness` remains local and network-free.
- No trading/order functionality appears in runtime code.
- Secrets do not appear in reprs, errors, reports, or test output.

## Rollback And Safe Disable

Future activation must be easy to disable without code changes:

- Unset `MARKET_SENTRY_PROVIDER` to return to the default mock provider.
- Set `MARKET_SENTRY_PROVIDER=mock` to force mock data.
- Set `MARKET_SENTRY_PROVIDER=fixture` for offline fixture behavior.
- Set `MARKET_SENTRY_PROVIDER=composed_fixture` for offline composition behavior.
- Set `MARKET_SENTRY_ALLOW_LIVE_DATA=false` to fail the live gate.
- Remove `ALPACA_API_KEY`, `ALPACA_API_SECRET`, or `FMP_API_KEY` to fail the live gate.

Disable paths must not leave persistent live state because live state should remain in memory only.

## Phase 13A Acceptance Criteria

Phase 13A is complete when:

1. This plan clearly states that no live activation is implemented.
2. The future activation path is documented.
3. Config gate behavior is documented.
4. Local preflight behavior is documented.
5. Provider factory activation rules are documented.
6. Transport/fetcher wiring is documented.
7. RVOL remains an explicit blocker until a real source exists.
8. Watchlist-only scope is documented.
9. Failure modes and secret-safety boundaries are documented.
10. Rollback/safe-disable behavior is documented.
11. Runtime code remains unchanged.
12. No network/provider implementation is added.
13. No trading/order behavior is added.
