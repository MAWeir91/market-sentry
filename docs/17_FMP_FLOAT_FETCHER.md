# Phase 11C — FMP Float Fetcher Behind Transport

## Status
Planned

## Purpose
Add a controlled Financial Modeling Prep (FMP) float/reference fetcher behind the Phase 11A HTTP transport abstraction.

Phase 11C proves that Market Sentry can:

- Build an FMP shares-float request for a controlled symbol.
- Send it through an injected fake transport.
- Parse a fake HTTP response body.
- Return normalized `FMPFloatData` reference data.

This is still provider plumbing only.

## Hard boundary
Market Sentry is a personal-use low-float momentum scanner with local voice alerts. It is not a trading bot.

Do not add:

- live provider activation
- FMP runtime provider
- Alpaca runtime provider
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
- external HTTP dependencies
- live network calls in tests

Trading/order functionality is never in scope for Market Sentry.

## Data boundary
FMP can provide float/reference-style data used by Market Sentry’s low-float scanner rules.

FMP does not provide the full movement layer by itself for the scanner’s intended live workflow.

Do not make FMP a scanner-ready provider by itself.

Do not compose `StockCandidate` objects in Phase 11C.

Do not activate FMP through the provider factory.

## Expected runtime behavior after Phase 11C

1. `python -m market_sentry` still defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock` still works.
3. `MARKET_SENTRY_PROVIDER=fixture` still works offline.
4. `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as placeholder.
5. FMP is still not active as a runtime provider.
6. Loop behavior remains unchanged.
7. Voice behavior remains unchanged.
8. Scanner qualification rules remain unchanged.
9. Scoring remains unchanged.
10. Existing report formatting remains unchanged.

## Expected files to create or modify

Expected:

- `src/market_sentry/data/fmp_fetcher.py`
- `tests/test_fmp_fetcher.py`
- `README.md`

Possible files to modify only if truly necessary:

- `src/market_sentry/data/fmp.py`
- `src/market_sentry/data/http.py`
- `tests/test_fmp_provider.py`
- `tests/test_http_transport.py`

Do not modify unless absolutely necessary:

- `src/market_sentry/main.py`
- `tests/test_main.py`
- `src/market_sentry/data/factory.py`
- `tests/test_provider_factory.py`
- `src/market_sentry/data/alpaca.py`
- `src/market_sentry/data/alpaca_fetcher.py`
- `src/market_sentry/data/fixture_provider.py`
- `src/market_sentry/data/composer.py`
- scanner filters
- scanner scoring
- scanner tiers
- alert generator
- alert formatter
- speaker behavior
- cooldown behavior
- mock data contents
- fixture provider contents

## Implementation expectations

1. Add an FMP float fetcher module.

2. Keep it focused on:
   - request conversion
   - fake-transport usage
   - response parsing
   - normalized FMP float/reference output

3. Use the Phase 11A HTTP transport abstraction.

4. The fetcher must accept an injected `HttpTransport`.

5. Tests must use `FakeHttpTransport` or an equivalent fake transport only.

6. Do not add real HTTP transport.

7. Do not add external HTTP dependencies.

8. Do not make live network calls in tests.

9. Do not require credentials in tests.

10. Do not activate FMP at runtime.

11. Do not change provider factory behavior.

12. Do not compose `StockCandidate` objects.

13. Do not add WebSocket behavior.

14. Do not add broad-market scanning.

15. Do not add trading/order behavior.

## Suggested structures

- `FMPFloatFetcher`
- `FMPFloatFetchError`, only if useful
- `fetch_float(symbol)`
- optional `fetch_floats(symbols)` if small and useful, but keep scope tight
- helper to convert existing FMP request shape into `HttpRequest`
- helper to parse `HttpResponse.body` with existing FMP parser helpers

## Request behavior

1. Build an FMP shares-float request for a controlled symbol.

2. Symbol should be trimmed and uppercased.

3. Empty symbol should be handled safely.

4. Use existing FMP settings behavior where practical.

5. Include API key through request params when settings contain a placeholder credential.

6. Use the generic `HttpRequest` structure.

7. Preserve timeout configuration if supported.

8. Request repr must not expose API key values.

9. Request helpers should not perform HTTP calls directly.

10. Avoid broad/all-shares endpoints in Phase 11C. Use single-symbol request behavior only.

## Response behavior

1. Fetcher should accept fake `HttpResponse` body data.

2. Fetcher should parse JSON response bodies.

3. Fetcher should handle dict-style or list-style FMP payloads if the existing parser supports them.

4. Fetcher should handle missing symbol data safely.

5. Fetcher should handle missing float fields safely.

6. Fetcher should reuse existing FMP parsing helpers where practical.

7. Fetcher should return normalized `FMPFloatData` when usable float data exists.

8. Fetcher should return `None` or a safe empty result when usable float data is absent.

9. Fetcher should not fabricate missing float/reference data.

10. Fetcher should not create `StockCandidate` objects.

## Error behavior

1. Transport timeout errors should remain clear and secret-safe.

2. HTTP status errors should remain clear and secret-safe.

3. Generic transport errors should remain clear and secret-safe.

4. Invalid JSON should raise a clear, secret-safe fetch error if implemented.

5. Non-object/non-list JSON should raise a clear, secret-safe fetch error if implemented.

6. Do not leak API keys, request params, headers, or raw request reprs in exception messages.

7. Do not swallow transport failures in a way that hides provider problems.

## Secret-safety requirements

1. Request params must remain accessible through `request.params`.

2. Request repr must not expose `apikey`, `api_key`, or any API-key values.

3. Error messages must not expose API-key values.

4. Tests should explicitly verify placeholder key values are not visible in repr or error strings.

## Testing requirements

Add tests for:

- Fetcher builds an `HttpRequest` using the injected fake transport.
- Fetcher sends expected FMP shares-float URL or path.
- Fetcher sends an uppercase symbol.
- Fetcher includes API key param when settings contain placeholder credentials.
- Request repr does not expose API-key values.
- Fake transport returns float fixture payload.
- Fetcher parses float fixture into normalized `FMPFloatData`.
- Fetcher handles missing symbol data safely.
- Fetcher handles missing float data safely.
- Fetcher handles empty symbol safely.
- Fetcher propagates or wraps timeout errors safely.
- Fetcher propagates or wraps status errors safely.
- Fetcher propagates or wraps generic transport errors safely if supported.
- Invalid JSON behavior is tested if implemented.
- Error messages do not expose secrets.
- Tests do not require API keys.
- Tests do not make live network calls.
- Existing runtime provider factory remains unchanged.
- Default mock runtime still works.
- Fixture provider still works offline.
- Alpaca remains runtime placeholder.
- FMP remains inactive as a runtime provider.
- Full test suite passes.

## Documentation requirements

Update README concisely:

- FMP float fetcher skeleton exists for future live-provider phases.
- Fetcher uses the generic HTTP transport abstraction.
- Tests use fake transport only.
- Runtime still defaults to mock.
- Fixture provider remains offline/static.
- Alpaca/FMP live providers are still not active.
- FMP provides float/reference data but is not a scanner-ready provider by itself.
- Credentials should not be committed.
- Trading/order functionality remains out of scope.

## Acceptance checks

After building, run:

```powershell
python -m pytest
```

Also run:

```powershell
python -m market_sentry
```

Manually verify if practical:

```powershell
$env:MARKET_SENTRY_PROVIDER="fixture"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

Also verify:

```powershell
$env:MARKET_SENTRY_PROVIDER="alpaca"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

## Builder response required

After building, respond with:

1. Files created or changed.
2. Summary of what each file does.
3. Exact FMP float fetcher behavior implemented.
4. Exact request behavior implemented.
5. Exact response parsing behavior implemented.
6. Exact error behavior implemented.
7. How secrets are protected.
8. Confirmation that runtime still defaults to mock.
9. Confirmation that fixture provider still works offline.
10. Confirmation that Alpaca/FMP live providers are not active.
11. Confirmation that no live network calls are made in tests.
12. Confirmation that no external HTTP dependency was added.
13. Confirmation that no `StockCandidate` composition was added.
14. Confirmation that no trading/order behavior was added.
15. Exact test command run.
16. Test results.
17. Example output from default mock run.
18. Example output from fixture provider run, if checked.
19. Example output from alpaca placeholder run, if checked.
20. Any known issues or follow-up recommendations.
