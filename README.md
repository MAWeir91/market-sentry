# Market Sentry

Market Sentry is a personal-use low-float momentum scanner project with optional local voice alerts.

This repository currently includes the project scaffold, local development setup, scanner core, provider interface, mock-data command-line runner, voice-ready alert event display, optional local voice playback, and a mock polling loop.

## Safety Boundary

Market Sentry is not a trading bot. It does not place trades, does not execute orders, and does not connect to brokerage trading or order APIs.

The current runner uses local static mock data only. It displays voice-ready alert messages in the terminal and can optionally attempt local text-to-speech playback with `--speak`. It does not include real market-data integrations, dashboard UI, order execution, or any capability that can place trades.

## Roadmap Note

Real data provider implementation is not present yet. Phase 9A documents the planned provider strategy: Alpaca Market Data is the likely first price/volume/intraday provider, and Financial Modeling Prep is the likely first float/reference provider. The current runtime remains mock-data based until a future phase explicitly adds real-provider code.

Phase 9B adds a provider configuration skeleton for future phases. `mock` is still the default and only functional provider. Placeholder environment variables exist for future Alpaca/FMP configuration, but real provider implementation is not present yet and secrets should never be committed.

Runtime now uses the provider config/factory path internally. `MARKET_SENTRY_PROVIDER=mock` is supported and requires no credentials. `MARKET_SENTRY_PROVIDER=alpaca` is a placeholder and exits with a clear not-implemented message; real API implementation is still not present.

Phase 10A adds an offline Alpaca market-data skeleton for future request shaping and fixture parsing. Runtime still defaults to mock, real Alpaca integration is not active, and tests use fixtures only. Alpaca is not the planned source of float/reference data; future scanner-ready live candidates will likely require Alpaca market data plus FMP float/reference data. Do not commit credentials.

Phase 10B adds an offline FMP float/reference skeleton for future request shaping and fixture parsing. Runtime still defaults to mock, real FMP integration is not active, and tests use fixtures only. FMP is planned for float/reference data, not intraday market movement; future scanner-ready live candidates will likely compose Alpaca market data with FMP float/reference data. Do not commit credentials.

Phase 10C adds offline fixture-based candidate composition for future live-provider work. Runtime still defaults to mock, Alpaca and FMP are not active runtime providers, and composition currently uses offline fixtures/tests only. Future live scanner-ready candidates will likely require Alpaca market data plus FMP float/reference data. Do not commit credentials.

Phase 10D adds an offline fixture-composed provider for future-provider testing. The default runtime remains mock, but `MARKET_SENTRY_PROVIDER=fixture` can run static Alpaca/FMP-style fixtures through the composer without credentials or network calls. Phase 10E updates the report header so it reflects the selected provider, such as `Mock Scanner Report` or `Fixture Scanner Report`. Alpaca/FMP live providers are still not active. Trading/order functionality remains out of scope.

Phase 11A adds a generic HTTP transport skeleton for future live-provider phases. Current runtime modes still require no credentials: mock remains the default, fixture remains offline/static, and Alpaca/FMP live providers are not active. Do not commit secrets. Trading/order functionality remains out of scope.

Phase 11B adds an Alpaca snapshot fetcher skeleton behind the generic HTTP transport abstraction. Tests use fake transport responses only, runtime still defaults to mock, fixture remains offline/static, and Alpaca/FMP live providers are not active. Alpaca alone does not provide the float/reference data needed for scanner-ready low-float candidates. Do not commit credentials.

Phase 11C adds an FMP float/reference fetcher skeleton behind the generic HTTP transport abstraction. Tests use fake transport responses only, runtime still defaults to mock, fixture remains offline/static, and Alpaca/FMP live providers are not active. FMP provides float/reference data but is not a scanner-ready provider by itself. Do not commit credentials.

Phase 11D adds a live-data candidate builder skeleton for future provider phases. It combines Alpaca movement data, FMP float data, and explicit relative-volume input through offline/fake tests only. Runtime still defaults to mock, fixture remains offline/static, Alpaca/FMP live providers are not active, and relative volume must not be fabricated. Do not commit credentials.

Phase 11E adds an offline composed provider harness named `composed_fixture`. It combines static Alpaca-style movement data, static FMP-style float data, and explicit relative-volume data through the live candidate builder path. It is not a live provider, requires no credentials, and does not activate Alpaca or FMP runtime providers. Trading/order functionality remains out of scope.

Phase 11F adds a standard-library HTTP transport for future live-provider phases. It is not active at runtime, tests mock standard-library networking and make no real network calls, and current runtime modes still require no API credentials. Secrets should not be committed.

Phase 12A adds a strict config gate for a future live composed provider named `live_composed`. Live data is not active yet; the gate only validates that `MARKET_SENTRY_ALLOW_LIVE_DATA=true` or equivalent, a non-empty watchlist, Alpaca credentials, and an FMP key are present before future live mode could be considered. Runtime still defaults to mock, fixture and composed_fixture remain offline, Alpaca remains a placeholder, FMP remains inactive, and secrets should not be committed.

Phase 12B reserves `MARKET_SENTRY_PROVIDER=live_composed` with a clean placeholder/config-gate error path. The Phase 12A gate checks the allow-live flag, watchlist, Alpaca credentials, and FMP key, but even a passing gate still exits because live data remains disabled until a future phase. Current working runtime modes require no credentials, and trading/order functionality remains out of scope.

Phase 12C adds a dependency-injected live composed provider skeleton for future live-data phases. It is tested with fake components only, is not active at runtime, does not fabricate relative volume, and leaves `live_composed` on the reserved/gated placeholder path. Runtime still defaults to mock, fixture and composed_fixture remain offline, Alpaca remains a placeholder, FMP remains inactive as a standalone runtime provider, credentials should not be committed, and trading/order functionality remains out of scope.

## Development

Install the local development dependencies with:

```powershell
python -m pip install -e ".[dev]"
```

Install optional local voice playback support with:

```powershell
python -m pip install -e ".[voice]"
```

Run the test suite with:

```powershell
python -m pytest
```

Run the mock scanner report and voice-ready alert messages with:

```powershell
python -m market_sentry
```

Run the offline fixture-composed provider with:

```powershell
$env:MARKET_SENTRY_PROVIDER="fixture"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

Run the offline composed provider harness with:

```powershell
$env:MARKET_SENTRY_PROVIDER="composed_fixture"; python -m market_sentry; Remove-Item Env:MARKET_SENTRY_PROVIDER
```

This command does not speak by default. To explicitly attempt local text-to-speech playback for generated alert messages, run:

```powershell
python -m market_sentry --speak
```

To explicitly keep playback disabled, run:

```powershell
python -m market_sentry --no-speak
```

Run the mock scanner repeatedly with:

```powershell
python -m market_sentry --loop --interval 30
```

Run the mock scanner loop with explicit local voice playback:

```powershell
python -m market_sentry --loop --interval 30 --speak
```

The loop interval defaults to 30 seconds. Values below 5 seconds are clamped to 5 seconds. Press `Ctrl+C` to stop loop mode cleanly.

Loop mode still uses local static mock data only. It does not connect to market-data APIs, WebSockets, brokerage trading/order APIs, or any service that can place trades.
