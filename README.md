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
