# Market Sentry — Data Provider Interface

## Document

- File: `docs/02_DATA_PROVIDER_INTERFACE.md`
- Project: Market Sentry
- Phase: Phase 2
- Owner: Adam
- Advisor / PM: ChatGPT
- Builder: Codex

## Purpose

Phase 2 defines the data provider interface for Market Sentry.

The goal is to make the scanner engine consume candidates from an interchangeable provider contract instead of being tied directly to the mock provider.

This phase prepares the project for future data sources while keeping the current implementation local, safe, deterministic, and testable.

## Product Boundary

Market Sentry is a personal-use low-float momentum scanner with future voice alerts.

Market Sentry is not a trading bot.

Phase 2 must not add:

- Real market-data APIs
- API keys
- Network calls
- WebSockets
- Brokerage trading/order APIs
- Order execution
- Trade placement
- Voice alerts
- Dashboard UI
- SEC filing integrations
- News integrations
- Halt integrations

Phase 2 is an architecture/interface phase only.

## Phase 2 Goal

Create a clean provider contract that allows the scanner engine to receive `StockCandidate` objects from interchangeable data sources.

The first official provider should remain the local static mock provider.

Future providers can include:

- CSV provider
- Alpaca market data provider
- Polygon/Massive market data provider
- Financial Modeling Prep float/reference provider
- SEC EDGAR filings provider
- Nasdaq/NYSE halt provider

Those future providers are out of scope for Phase 2.

## Core Design Principle

The scanner engine should not care where candidate data comes from.

It should only care that a provider returns scanner-ready `StockCandidate` objects.

Conceptually:

```text
Data Provider -> list[StockCandidate] -> Scanner Engine -> list[ScannerResult]
```

## Provider Contract

Create a provider interface or protocol named `MarketDataProvider`.

The required provider method should be:

```python
def get_candidates(self) -> list[StockCandidate]:
    ...
```

The provider contract should be simple, typed, and easy to implement.

Recommended file:

```text
src/market_sentry/data/provider.py
```

Recommended structure:

```python
from typing import Protocol

from market_sentry.scanner.models import StockCandidate


class MarketDataProvider(Protocol):
    """Contract for scanner candidate providers."""

    def get_candidates(self) -> list[StockCandidate]:
        """Return scanner-ready stock candidates."""
        ...
```

## Mock Provider

The current mock provider should be updated to follow the provider contract.

Recommended class name:

```text
MockMarketDataProvider
```

The mock provider should:

- Use local static data only
- Return `list[StockCandidate]`
- Include realistic examples that cover passing, failing, and multiple tier cases
- Avoid network calls
- Avoid API-like behavior
- Avoid credentials or environment variables
- Remain deterministic for tests

The mock provider is the only provider that should exist in Phase 2.

## Scanner Engine Relationship

Phase 2 may update the scanner engine only if needed so it can consume provider output cleanly.

The engine should be able to evaluate candidates from any object that follows the `MarketDataProvider` contract.

Acceptable patterns include:

```python
provider = MockMarketDataProvider()
candidates = provider.get_candidates()
results = scanner.evaluate(candidates)
```

or:

```python
results = scanner.scan(provider.get_candidates())
```

Do not overbuild lifecycle management, polling, streaming, async behavior, or provider registries in Phase 2.

## Data Model Boundary

Providers should return `StockCandidate` objects.

Do not create separate raw API response models in Phase 2.

Future real providers can later normalize raw provider-specific responses into `StockCandidate`.

For Phase 2, the data flow should stay simple:

```text
Static mock data -> StockCandidate -> Scanner Engine
```

## Expected Files

Phase 2 should create or modify:

```text
src/market_sentry/data/provider.py
src/market_sentry/data/mock_provider.py
src/market_sentry/data/__init__.py
tests/test_provider_contract.py
```

Phase 2 may modify if needed:

```text
src/market_sentry/scanner/engine.py
tests/test_engine.py
```

Phase 2 should not modify unless explicitly approved:

```text
src/market_sentry/scanner/filters.py
src/market_sentry/scanner/scoring.py
src/market_sentry/scanner/tiers.py
src/market_sentry/scanner/models.py
src/market_sentry/config.py
src/market_sentry/main.py
```

## Testing Requirements

Add tests confirming:

1. `MockMarketDataProvider` has a `get_candidates()` method.
2. `get_candidates()` returns a list.
3. Every returned item is a `StockCandidate`.
4. The mock provider returns at least one candidate.
5. The scanner engine can evaluate candidates returned by the provider.
6. No real API calls or network behavior are required.
7. Provider output remains deterministic between calls.

Recommended test file:

```text
tests/test_provider_contract.py
```

## Acceptance Criteria

Phase 2 is complete only when:

- A provider interface or protocol exists.
- The mock provider implements or conforms to the provider contract.
- The scanner engine can consume candidates from the mock provider.
- Tests pass.
- No real API integration exists.
- No credentials or active provider API keys are introduced.
- No trading/order behavior exists.
- Codex summarizes files changed, tests run, and design decisions.
- Adam zips and uploads changed files.
- ChatGPT reviews the code and signs off.

## Future Provider Roadmap

The likely future provider roadmap is:

```text
Phase 2: MockMarketDataProvider only
Phase 3: Runnable polling/CLI workflow using mock provider
Phase 4: Voice-ready alert events
Phase 5: Local voice alerts
Phase 6: First real market-data provider
Later: Float/reference provider
Later: SEC filing provider
Later: Halt provider
Later: News provider
Later: WebSocket provider
```

Potential future provider responsibilities:

| Future Provider | Possible Role |
|---|---|
| Alpaca | Price, volume, bars, snapshots, possible news |
| Polygon/Massive | Price, volume, bars, snapshots, possible deeper market data |
| Financial Modeling Prep | Float/reference data |
| SEC EDGAR | Filings |
| Nasdaq/NYSE | Halts |
| CSV/local file | Offline testing and replay data |

Do not implement these future providers in Phase 2.

## Codex Workflow Reminder

Codex must follow the Market Sentry workflow:

1. Receive a phase prompt from ChatGPT.
2. Confirm understanding and planned changes without coding.
3. Wait for approval.
4. Build only after approval.
5. Run tests.
6. Summarize changes and results.
7. Wait for zip/review before commit/push.

Codex must not expand scope without approval.
