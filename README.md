# Market Sentry

Market Sentry is a personal-use low-float momentum scanner project with planned future voice alerts.

This repository currently includes the project scaffold, local development setup, scanner core, provider interface, mock-data command-line runner, and voice-ready alert event display.

## Safety Boundary

Market Sentry is not a trading bot. It does not place trades, does not execute orders, and does not connect to brokerage trading or order APIs.

The current runner uses local static mock data only. It displays voice-ready alert messages in the terminal, but it does not perform text-to-speech playback. It does not include real market-data integrations, dashboard UI, order execution, or any capability that can place trades.

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
