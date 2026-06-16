# Market Sentry

Market Sentry is a personal-use low-float momentum scanner project with planned future voice alerts.

This repository currently includes the project scaffold, local development setup, scanner core, provider interface, and a mock-data command-line runner.

## Safety Boundary

Market Sentry is not a trading bot. It does not place trades, does not execute orders, and does not connect to brokerage trading or order APIs.

The current runner uses local static mock data only. It does not include real market-data integrations, voice alerts, dashboard UI, order execution, or any capability that can place trades.

## Development

Install the local development dependencies with:

```powershell
python -m pip install -e ".[dev]"
```

Run the test suite with:

```powershell
python -m pytest
```

Run the mock scanner report with:

```powershell
python -m market_sentry
```
