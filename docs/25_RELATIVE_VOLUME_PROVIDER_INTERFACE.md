# Phase 12E — Relative Volume Provider Interface

## Goal

Create a dedicated relative-volume provider interface and offline/fake implementation so the future live composed provider path can receive explicit relative-volume data without fabricating it.

This phase is still non-live and non-runtime-active.

## Project Boundary

Market Sentry is a personal-use low-float momentum scanner with local voice alerts. It is not a trading bot.

Do not add:

- order APIs
- order placement
- trade execution
- trading advice behavior
- live runtime activation
- real HTTP calls
- external HTTP dependencies
- broad-market scanning
- all-shares-float crawling
- WebSockets
- streaming market data
- SEC/news/halt/split ingestion
- dashboard UI
- persistent database storage

## Why This Phase Exists

The live builder currently requires explicit `relative_volume_by_symbol` input. That is safe, but before any future live provider activation, relative volume should have a clean provider boundary like Alpaca and FMP.

This phase creates that boundary without pretending we have a live RVOL calculation yet.

## Expected Runtime Behavior

After this phase:

1. `python -m market_sentry` still defaults to mock.
2. `MARKET_SENTRY_PROVIDER=mock` still works.
3. `MARKET_SENTRY_PROVIDER=fixture` still works offline.
4. `MARKET_SENTRY_PROVIDER=composed_fixture` still works offline.
5. `MARKET_SENTRY_PROVIDER=alpaca` still fails cleanly as placeholder.
6. `MARKET_SENTRY_PROVIDER=live_composed` still fails through the gated placeholder path.
7. Gate-passing `live_composed` still fails as reserved/inactive.
8. No runtime path instantiates live HTTP transports or fetchers.
9. No runtime path makes live network calls.
10. Scanner rules, scoring, alerts, voice, and report formatting remain unchanged.

## Expected Files

Create or modify:

- `src/market_sentry/data/relative_volume.py`
- `tests/test_relative_volume_provider.py`
- `README.md`

Possible only if necessary:

- `src/market_sentry/data/live_provider_builder.py`
- `tests/test_live_provider_builder.py`
- `src/market_sentry/data/live_composed_provider.py`
- `tests/test_live_composed_provider.py`

Avoid unless absolutely necessary:

- `src/market_sentry/data/factory.py`
- `src/market_sentry/main.py`
- scanner filters/scoring/tiers
- alerts/voice/cooldowns
- HTTP transport
- Alpaca/FMP fetchers
- mock/fixture/composed fixture data

## Implementation Requirements

Add a relative-volume provider boundary.

Suggested structures:

- `RelativeVolumeProvider` protocol
- `RelativeVolumeData` dataclass, if useful
- `StaticRelativeVolumeProvider`
- `RelativeVolumeProviderError`, if useful

A simple acceptable interface:

```python
class RelativeVolumeProvider(Protocol):
    def get_relative_volumes(self, symbols: Sequence[str]) -> dict[str, float]: ...
```

Exact names can vary, but responsibilities must remain clear.

## Behavior Requirements

1. Symbols should be normalized by trimming and uppercasing.
2. Empty symbols should be ignored safely.
3. Static provider should return only explicitly configured RVOL values.
4. Static provider must not fabricate missing RVOL values.
5. Missing symbols should be absent from the returned mapping, not assigned defaults.
6. Invalid values should be rejected or omitted safely.
7. Values must be positive numeric values to be considered usable.
8. Duplicate symbols should be handled deterministically.
9. Provider must not make HTTP calls.
10. Provider must not require API keys.
11. Provider must not add external dependencies.
12. Provider must not add trading/order behavior.

## Optional Integration

If small and safe, update `live_provider_builder.py` so it can optionally accept a `relative_volume_provider` or `relative_volume_source`, while still accepting explicit `relative_volume_by_symbol`.

Important:

- Do not break existing explicit mapping behavior.
- Do not calculate RVOL.
- Do not infer RVOL.
- Do not activate runtime.
- Do not connect this to the provider factory.

## Testing Requirements

Add tests for:

- protocol/fake provider shape is usable.
- static provider normalizes symbols.
- static provider ignores empty symbols.
- static provider returns only explicitly configured RVOL values.
- missing RVOL is not fabricated.
- invalid RVOL values are rejected or omitted safely.
- zero/negative RVOL values are not treated as usable.
- duplicate symbols are deterministic.
- provider makes no HTTP/network calls.
- provider requires no credentials.
- no external HTTP dependency is added.
- optional builder integration, if implemented, still requires explicit RVOL source/mapping.
- runtime provider factory remains unchanged.
- default runtime remains mock.
- fixture provider still works offline.
- composed_fixture still works offline.
- alpaca remains placeholder.
- live_composed remains gated placeholder.
- full test suite passes.

## Documentation Requirements

Update README concisely:

- Relative-volume provider interface exists for future live-provider phases.
- Static/offline RVOL provider returns only explicit values.
- Missing RVOL is never fabricated.
- Runtime remains mock by default.
- Fixture and composed_fixture remain offline.
- Alpaca remains placeholder.
- live_composed remains gated placeholder.
- No credentials are required for current working modes.
- Secrets should not be committed.
- Trading/order functionality remains out of scope.
