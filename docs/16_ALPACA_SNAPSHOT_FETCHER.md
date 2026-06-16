# Phase 11B — Alpaca Snapshot Fetcher Behind Transport

## Purpose

Phase 11B adds an Alpaca snapshot fetcher that uses the Phase 11A HTTP transport abstraction. This is the first provider-specific fetcher layer, but it must remain controlled, fakeable, and inactive by default.

The goal is to prove that Market Sentry can shape an Alpaca snapshot request, send it through an injected transport, receive a fake HTTP response, parse fixture data, and return normalized Alpaca snapshot data using existing Alpaca parsing helpers.

## Status After This Phase

After Phase 11B:

- Runtime still defaults to mock.
- Fixture provider still works offline.
- `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as a placeholder.
- Alpaca is not a runtime provider yet.
- FMP is not a runtime provider.
- No trading or order functionality exists.
- Tests do not make live network calls.
- Tests do not require API keys.

## Out of Scope

Do not add:

- Runtime activation of Alpaca.
- Runtime activation of FMP.
- Live HTTP calls in tests.
- WebSockets.
- Streaming market data.
- Broad-market scanning.
- SEC ingestion.
- News ingestion.
- Halt ingestion.
- Split ingestion.
- Dashboard UI.
- Persistent database storage.
- Brokerage/order APIs.
- Order placement.
- Trade execution.
- New runtime CLI flags.
- External HTTP dependencies.

Trading/order functionality is never in scope for Market Sentry.

## Alpaca Snapshot Endpoint Context

The Alpaca stock snapshots endpoint is used for market-data snapshots. It can return snapshot data for multiple tickers, including latest trade, latest quote, minute bar, daily bar, and previous daily bar data.

This phase should use the existing Alpaca request-shaping work and the new HTTP transport abstraction to prepare a fetcher, but tests must use fake transport responses only.

## Authentication Boundary

Alpaca market data uses API-key headers:

- `APCA-API-KEY-ID`
- `APCA-API-SECRET-KEY`

Phase 11B may build requests with these headers, but:

- Secrets must not appear in repr output.
- Secrets must not appear in exception messages.
- Tests must not require real secrets.
- Runtime must not require Alpaca credentials unless a future phase explicitly activates Alpaca.

## Data Boundary

Alpaca can provide market movement data such as:

- latest price
- daily volume
- high of day
- previous close
- daily gain inputs
- intraday/bars inputs

Alpaca does not provide the float/reference layer needed by Market Sentry’s scanner rules. FMP remains the planned reference-data source for float data in later composed live-provider phases.

Phase 11B must not claim Alpaca alone can create scanner-ready low-float candidates.

## Desired Architecture

Add a small fetcher layer that depends on abstractions, not concrete network behavior.

Possible structures:

- `AlpacaSnapshotFetcher`
- `AlpacaSnapshotFetchError`, if useful
- `fetch_snapshots(symbols)`
- helper to build the existing snapshot request and convert it into an `HttpRequest`
- helper to parse the `HttpResponse` body using existing Alpaca parser functions

The fetcher should:

1. Accept `AlpacaMarketDataSettings` or equivalent.
2. Accept an injected `HttpTransport`.
3. Build an Alpaca snapshot request for a controlled symbol list.
4. Send the request through the injected transport.
5. Parse the fake response body into normalized Alpaca snapshot objects/data.
6. Return only normalized market-data objects or safe missing values.
7. Avoid any scanner-ready candidate composition.
8. Avoid runtime provider activation.

## Request Expectations

The fetcher should:

- Build a snapshot request for a list of symbols.
- Uppercase symbols.
- Trim symbols.
- Ignore empty symbols or handle them safely.
- Use configured feed, defaulting to `iex`.
- Use Alpaca market-data headers.
- Use the generic `HttpRequest` structure.
- Preserve timeout configuration if present.
- Avoid exposing secrets in repr/errors.

## Response Expectations

The fetcher should:

- Accept a fake `HttpResponse` body.
- Parse dict-style snapshot payloads.
- Handle missing symbols safely.
- Handle missing nested fields safely.
- Reuse existing Alpaca parsing/calculation helpers where practical.
- Return normalized data for symbols that have usable snapshot data.
- Not fabricate missing market data.

## Error Expectations

The fetcher should:

- Allow transport errors to surface as clear, secret-safe errors.
- Avoid leaking headers or API-key params in error messages.
- Not print secrets.
- Not swallow errors in a way that hides provider failures.
- Keep behavior deterministic in tests.

## Testing Requirements

Add tests for:

- Fetcher builds an `HttpRequest` using the injected fake transport.
- Fetcher sends the expected Alpaca snapshot URL/path.
- Fetcher sends symbols as comma-separated uppercase symbols.
- Fetcher includes feed, defaulting to `iex`.
- Fetcher includes Alpaca auth headers when settings contain placeholders.
- Request repr does not expose key/secret values.
- Fake transport returns snapshot fixture payload.
- Fetcher parses snapshot fixture into normalized Alpaca snapshot data.
- Fetcher handles missing symbol data safely.
- Fetcher handles empty symbol lists safely.
- Fetcher propagates or wraps transport timeout errors safely.
- Fetcher propagates or wraps status errors safely.
- Error messages do not expose secrets.
- Tests do not require API keys.
- Tests do not make live network calls.
- Existing runtime provider factory remains unchanged.
- Default mock runtime still works.
- Fixture provider still works offline.
- Alpaca remains runtime placeholder.
- Full test suite passes.

## Runtime Requirements

After implementation:

- `python -m market_sentry` still works with mock mode.
- `MARKET_SENTRY_PROVIDER=fixture` still works offline.
- `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as a placeholder.
- No new CLI flags are added.
- No scanner rule changes are made.
- No scoring changes are made.
- Voice and loop behavior remain unchanged.

## Documentation Requirements

Update README concisely to explain:

- Alpaca snapshot fetcher skeleton exists for future live-provider phases.
- Fetcher uses the generic HTTP transport abstraction.
- Tests use fake transport only.
- Runtime still defaults to mock.
- Fixture provider remains offline/static.
- Alpaca/FMP live providers are still not active.
- Alpaca alone does not provide float/reference data.
- Credentials should not be committed.
- Trading/order functionality remains out of scope.

## Future Phase After 11B

A likely next phase is:

**Phase 11C — FMP Float Fetcher Behind Transport**

That would mirror Phase 11B for FMP float/reference data using the same HTTP transport abstraction, fake transport tests, and no runtime activation.
