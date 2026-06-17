# Phase 11F — Standard-Library HTTP Transport, Not Activated

## Purpose

Add a minimal real HTTP transport implementation behind the existing `HttpTransport` protocol using only Python standard-library modules.

This phase provides the missing infrastructure needed for future controlled live-provider work while keeping runtime behavior unchanged and tests fully offline.

## Non-goals

Do not add live provider activation.

Do not activate Alpaca or FMP.

Do not make real network calls in tests.

Do not require API credentials.

Do not add external HTTP dependencies.

Do not add WebSockets, streaming data, broad scanning, dashboard UI, persistence, or trading/order behavior.

Market Sentry is not a trading bot.

## Runtime boundary

After this phase:

- `python -m market_sentry` still defaults to mock.
- `MARKET_SENTRY_PROVIDER=fixture` still works offline.
- `MARKET_SENTRY_PROVIDER=composed_fixture` still works offline.
- `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as a placeholder.
- FMP remains inactive as a runtime provider.
- No runtime mode should instantiate or use the new HTTP transport.

## Expected files

Create or modify:

- `src/market_sentry/data/http_stdlib.py`
- `tests/test_http_stdlib_transport.py`
- `README.md`

Modify only if truly necessary:

- `src/market_sentry/data/http.py`
- `tests/test_http_transport.py`

Do not modify unless absolutely necessary:

- runtime CLI
- provider factory
- mock provider
- fixture provider
- composed fixture provider
- scanner filters/scoring/tiers
- alert/voice/cooldown behavior
- Alpaca fetcher behavior
- FMP fetcher behavior
- live candidate builder behavior

## Implementation expectations

Add a standard-library implementation such as `StdlibHttpTransport`.

It should:

- implement the existing `HttpTransport` protocol
- accept an `HttpRequest`
- return an `HttpResponse`
- support GET requests initially
- encode query params safely
- attach headers
- use configured request timeout
- decode response bodies as text
- convert timeout errors to `HttpTimeoutError`
- convert URL/network errors to `HttpTransportError`
- convert non-2xx HTTP responses to `HttpStatusError` or preserve the existing status-error behavior
- avoid leaking headers, API keys, request params, or raw request reprs in exception messages

Keep it small and boring.

## Testing expectations

Tests must mock or monkeypatch standard-library networking calls.

Tests must not call the internet.

Test:

- successful GET request returns `HttpResponse`
- query params are encoded into URL
- headers are passed to the request object
- timeout value is passed through
- response body is decoded
- non-2xx status raises/returns expected status error behavior
- timeout errors become `HttpTimeoutError`
- URL/network errors become `HttpTransportError`
- secret values do not appear in exception messages
- no external HTTP dependency is required
- runtime/provider factory behavior remains unchanged
- full suite passes

## Documentation expectations

Update README concisely:

- standard-library HTTP transport exists for future live-provider phases
- it is not active at runtime
- tests mock standard-library networking and do not make real network calls
- current runtime modes still require no API credentials
- secrets should not be committed
- trading/order functionality remains out of scope

## Acceptance criteria

Phase 11F is complete when:

- the transport implementation exists
- tests prove it works without live network calls
- runtime still defaults to mock
- fixture and composed_fixture remain offline
- Alpaca remains placeholder
- FMP remains inactive
- no external HTTP dependency is added
- no trading/order behavior is added
- full test suite passes
