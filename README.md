# Market Sentry

Market Sentry is a personal-use low-float momentum scanner project with planned future voice alerts.

This repository is currently in Phase 0. Phase 0 establishes the project scaffold, documentation placement, Python package layout, and testing foundation only.

## Safety Boundary

Market Sentry is not a trading bot. It does not place trades, does not execute orders, and does not connect to brokerage trading or order APIs.

Phase 0 does not include scanner logic, market-data integrations, voice alerts, dashboard UI, order execution, or any capability that can place trades.

## Development

Install the local development dependencies with:

```powershell
python -m pip install -e ".[dev]"
```

Run the test suite with:

```powershell
python -m pytest
```
