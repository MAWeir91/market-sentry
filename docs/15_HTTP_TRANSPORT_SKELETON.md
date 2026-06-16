# Phase 11A — Live HTTP Transport Skeleton

## Status

Planned.

Phase 11A introduces a safe, generic HTTP transport abstraction that future live data providers can use, without activating live providers or making real network calls in runtime by default.

This phase is about plumbing only.

It does not make Alpaca live. It does not make FMP live. It does not change the default provider. It does not add trading behavior.

---

## Goal

Create a small, testable HTTP transport layer that can eventually support live provider requests while keeping all tests offline and deterministic.

The transport should provide:

- a simple request object
- a simple response object
- clear timeout configuration
- clear HTTP error behavior
- secret-safe error messages and repr behavior
- fakeable/injectable behavior for tests

---

## Non-goals

Do not add:

- live provider activation
- Alpaca runtime provider
- FMP runtime provider
- SEC/news/halt/split ingestion
- WebSockets
- streaming market data
- broad-market scanning
- dashboard UI
- persistent database storage
- broker order APIs
- order placement
- trade execution
- new runtime CLI flags
- required credentials for tests

Trading/order functionality is never in scope for Market Sentry.

---

## Runtime behavior

After Phase 11A:

- `python -m market_sentry` still defaults to mock.
- `MARKET_SENTRY_PROVIDER=mock` still works.
- `MARKET_SENTRY_PROVIDER=fixture` still works offline.
- `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as a placeholder.
- FMP is not active as a runtime provider.
- Loop behavior remains unchanged.
- Voice behavior remains unchanged.
- Scanner rules remain unchanged.
- Scoring remains unchanged.

The new transport should not be used by runtime providers yet unless a future phase explicitly wires it in.

---

## Suggested module

Create:

```text
src/market_sentry/data/http.py
```

Add tests:

```text
tests/test_http_transport.py
```

---

## Suggested structures

Possible structures:

```python
@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    params: Mapping[str, str] = field(default_factory=dict, repr=False)
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    timeout_seconds: float = 10.0
```

```python
@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: str
    headers: Mapping[str, str] = field(default_factory=dict)
```

```python
class HttpTransportError(Exception):
    pass
```

```python
class HttpStatusError(HttpTransportError):
    pass
```

```python
class HttpTimeoutError(HttpTransportError):
    pass
```

```python
class HttpTransport(Protocol):
    def send(self, request: HttpRequest) -> HttpResponse:
        ...
```

Potential helper:

```python
def redact_sensitive_headers(headers: Mapping[str, str]) -> dict[str, str]:
    ...
```

Potential fake test transport:

```python
class FakeHttpTransport:
    def send(self, request: HttpRequest) -> HttpResponse:
        ...
```

The exact shape can vary if it stays simple, testable, and secret-safe.

---

## Secret safety

HTTP requests may eventually contain API credentials in headers or params.

Therefore:

- request repr must not expose headers
- request repr must not expose params if params can contain API keys
- error messages must not include raw headers
- error messages must not include raw query params containing secrets
- tests should verify secret values do not appear in repr or expected errors

Sensitive names should include at least:

- `APCA-API-KEY-ID`
- `APCA-API-SECRET-KEY`
- `apikey`
- `api_key`
- `apiSecret`
- `authorization`

---

## Real transport policy

Phase 11A may do either of the following:

1. Add only protocols, request/response models, and fake transport tests.
2. Add a minimal standard-library transport using `urllib.request`, but do not wire it into runtime.

Preferred path: keep Phase 11A mostly abstraction + fake transport unless implementation is very small and low-risk.

Do not add external HTTP dependencies such as:

- `requests`
- `httpx`
- `aiohttp`
- `websockets`

---

## Error behavior

The transport layer should make future provider code easier to reason about.

Expected behavior:

- successful responses are returned as `HttpResponse`
- non-2xx responses can raise `HttpStatusError` or be represented clearly, depending on chosen design
- timeout-like errors should map to `HttpTimeoutError`
- network-like errors should map to `HttpTransportError`
- errors should be secret-safe
- errors should be testable without network access

---

## Testing expectations

Add tests for:

- `HttpRequest` repr does not expose headers
- `HttpRequest` repr does not expose params containing API keys
- headers remain accessible on the request object
- params remain accessible on the request object
- fake transport returns fixture response
- fake transport records sent requests if useful
- fake transport can simulate status errors
- fake transport can simulate timeout errors
- errors do not expose secrets
- no external HTTP dependencies are required
- tests do not require internet access
- tests do not require API keys
- existing provider factory behavior remains unchanged
- default runtime remains mock
- fixture provider still works
- Alpaca remains placeholder
- full test suite passes

---

## Documentation expectations

Update README concisely:

- HTTP transport skeleton exists for future live-provider phases
- runtime remains mock by default
- fixture provider remains offline/static
- Alpaca/FMP live providers are still not active
- no credentials are required for current runtime modes
- secrets should not be committed
- trading/order functionality remains out of scope

---

## Acceptance criteria

Phase 11A is complete when:

- transport request/response abstractions exist
- tests prove secret-safe repr/error behavior
- tests use fakes and require no internet
- runtime default remains mock
- fixture mode still works offline
- Alpaca still fails cleanly as placeholder
- no live provider runtime activation occurred
- no trading/order behavior was added
- full test suite passes
