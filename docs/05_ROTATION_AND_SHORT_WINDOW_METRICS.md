# Market Sentry — Rotation and Short-Window Metrics

## Purpose

This document defines Phase 7 of Market Sentry: adding rotation and short-window momentum metrics to the scanner core.

Market Sentry currently evaluates low-float momentum candidates using price, float, daily gain, relative volume, and daily volume. Phase 7 expands the scanner's "ticker story" by adding metrics inspired by real-time momentum scanners such as Arcane Monitor:

- Float rotation
- High of day
- Distance from high of day
- 15-minute change
- Recent volume context, if available through mock data

These metrics should improve the scanner's ability to describe whether a ticker is merely up on the day or actively behaving like a low-float momentum runner.

## Project Boundary

Market Sentry is a personal-use low-float momentum scanner with local voice alerts.

Market Sentry is not a trading bot.

Do not add:

- Order execution
- Brokerage trading/order API connections
- Any functionality that places trades
- Real market-data APIs
- API keys
- Network calls
- WebSockets
- Dashboard UI
- News integrations
- SEC filing integrations
- Halt integrations

Phase 7 remains mock-data compatible and local-only.

## Phase 7 Goal

Add scanner-ready rotation and short-window metrics to the existing stock candidate, scanner result, scoring, report, and alert context.

The scanner should be able to describe not just:

> This stock is up 50%.

But also:

> This stock is up 50%, has traded 3.4 times its float, is near high of day, and is up 12% over the last 15 minutes.

## Key Concepts

### Float Rotation

Float rotation estimates how many times the float has traded during the day.

Formula:

```text
rotation = daily_volume / float_shares
```

Example:

```text
daily_volume = 6,400,000
float_shares = 1,300,000
rotation = 4.92
```

Display example:

```text
Rotation: 4.9x
```

Why it matters:

Low-float stocks can become especially active when daily volume greatly exceeds float. High rotation may indicate intense market attention, active churn, or mania-like behavior.

Important:

Rotation is not a buy/sell signal. It is an attention/context metric.

### High of Day

High of day is the highest price the stock has traded at during the current session.

Suggested field:

```python
high_of_day: float | None
```

### Distance From High of Day

Distance from high of day shows how close the current price is to the current session high.

Formula:

```text
distance_from_high_pct = ((current_price - high_of_day) / high_of_day) * 100
```

Examples:

```text
current_price = 9.50
high_of_day = 10.00
distance_from_high_pct = -5.0
```

Display example:

```text
HOD Dist: -5.0%
```

If current price equals high of day, distance is 0.0%.

If high_of_day is missing or invalid, distance should be None.

### 15-Minute Change

15-minute change captures recent momentum rather than only daily momentum.

Suggested field:

```python
change_15m_pct: float | None
```

Display example:

```text
15m: +12.4%
```

Why it matters:

A stock up 80% on the day may be fading, while another stock up 25% may be accelerating in the last 15 minutes. Short-window metrics help separate stale movers from active movers.

## Approved Data Model Changes

Update the stock candidate model to support optional fields:

```python
high_of_day: float | None = None
change_15m_pct: float | None = None
```

Rotation may be implemented as a calculated property or helper function, not necessarily a stored field.

Recommended approach:

```python
@property
def rotation(self) -> float | None:
    if self.float_shares <= 0:
        return None
    return self.daily_volume / self.float_shares
```

Recommended distance helper/property:

```python
@property
def distance_from_high_pct(self) -> float | None:
    if self.high_of_day is None or self.high_of_day <= 0:
        return None
    return ((self.price - self.high_of_day) / self.high_of_day) * 100
```

Do not make these new fields required for all future providers. They should be optional so early real providers can still work even if they cannot provide every value.

## Scanner Criteria

Phase 7 should not change the base qualification rules yet.

Base qualification remains:

- Price between 0.25 and 20.00
- Float between 500,000 and 10,000,000 shares
- Daily gain at least 10%
- Relative volume at least 2
- Daily volume at least 500,000 shares

Rotation and short-window metrics should improve context and scoring, but they should not become hard qualification requirements in Phase 7.

## Scoring Updates

Phase 7 may update the scoring formula while keeping the score range 0–100.

Current score components may be rebalanced to include:

- Daily gain
- Relative volume
- Daily volume
- Float quality
- Rotation
- 15-minute change
- Distance from high of day

Recommended scoring principles:

- Keep scoring deterministic.
- Keep score range 0–100.
- Keep scoring simple and documented.
- Do not let one metric dominate everything.
- Missing optional metrics should not crash scoring.
- Missing optional metrics should contribute 0 to that metric's component.
- Existing strong candidates should still score reasonably.

Suggested Phase 7 scoring allocation:

```text
Daily gain: 25 points
Relative volume: 20 points
Daily volume: 15 points
Float quality: 10 points
Rotation: 15 points
15-minute change: 10 points
Near high of day: 5 points
Total: 100 points
```

This allocation can be adjusted if Codex identifies a cleaner implementation, but any changes should be explained before implementation.

## Report Output Updates

Update the CLI report to include the new metrics when available.

Qualified and rejected rows/details should include:

- Rotation
- 15-minute change
- High of day
- Distance from high of day

Suggested display:

```text
Price: $11.40 | Gain: 118.0% | 15m: +12.5% | RelVol: 12.5x | Float: 1.3M | Volume: 6.4M | Rotation: 4.9x | HOD: $11.80 | HOD Dist: -3.4%
```

If a value is missing, display a clean placeholder such as:

```text
15m: N/A
Rotation: N/A
HOD: N/A
HOD Dist: N/A
```

## Alert Message Updates

Voice-ready alert messages may include rotation and 15-minute change when available.

Examples:

```text
XTRM extreme runner. Up 118.0 percent with 12.5 relative volume. Rotation 4.9 times float. Fifteen-minute change positive 12.5 percent. Score 99.6.
```

Keep the language descriptive and avoid trading advice.

Do not use:

- buy
- sell
- enter
- exit
- guaranteed
- safe trade

## Mock Provider Updates

Update the mock provider so sample candidates include realistic optional values for:

- high_of_day
- change_15m_pct

Mock data should include cases such as:

- Strong high-rotation runner
- Runner near high of day
- Runner far from high of day
- Recent 15-minute acceleration
- Missing optional metrics
- Rejected candidate with optional metrics

## Testing Requirements

Add or update tests for:

### Model Metrics

- Rotation is calculated correctly.
- Rotation returns None or safe value when float is invalid.
- Distance from high of day is calculated correctly.
- Distance from high of day returns None when high_of_day is missing or invalid.
- Optional metrics do not break candidate creation.

### Scoring

- Score remains within 0–100.
- Rotation improves score when all else is equal.
- 15-minute strength improves score when all else is equal.
- Near-HOD candidate scores higher than far-from-HOD candidate when all else is equal.
- Missing optional metrics do not crash scoring.

### Mock Provider

- Mock candidates include optional Phase 7 metrics.
- At least one candidate has high rotation.
- At least one candidate has 15-minute change.
- At least one candidate has high_of_day.

### CLI Report

- Report includes Rotation.
- Report includes 15m change.
- Report includes HOD.
- Report includes HOD distance.
- Missing optional values display cleanly.

### Alert Formatting

- Alert messages can include rotation or 15-minute change when available.
- Alert messages still avoid trading advice language.

## Expected Files To Modify

Likely files:

```text
src/market_sentry/scanner/models.py
src/market_sentry/scanner/scoring.py
src/market_sentry/data/mock_provider.py
src/market_sentry/main.py
src/market_sentry/alerts/formatter.py
tests/test_scoring.py
tests/test_engine.py
tests/test_provider_contract.py
tests/test_main.py
tests/test_alert_formatter.py
```

Possible new test file:

```text
tests/test_candidate_metrics.py
```

Modify only if needed:

```text
src/market_sentry/scanner/engine.py
src/market_sentry/scanner/filters.py
src/market_sentry/scanner/tiers.py
src/market_sentry/alerts/generator.py
```

## Out of Scope

Phase 7 does not include:

- Real market data
- Live polling
- WebSockets
- Dashboard
- News
- SEC filings
- Halts
- Splits
- Voice customization
- Trading/order execution

## Definition of Done

Phase 7 is complete when:

- Candidate model supports optional high_of_day and 15-minute change.
- Rotation can be calculated.
- Distance from high of day can be calculated.
- Scoring includes the new context metrics while remaining 0–100.
- Mock provider includes realistic Phase 7 sample values.
- CLI report displays the new metrics cleanly.
- Alert messages can include useful new context.
- All tests pass.
- No APIs, network calls, dashboard, polling loop, or trading functionality are added.
