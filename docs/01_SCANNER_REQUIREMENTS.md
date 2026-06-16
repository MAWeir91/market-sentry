# 01 Scanner Requirements

## Project Role Definitions

**Owner:** Adam  
**Builder:** Codex  
**Project Manager / Architecture Advisor:** ChatGPT

## Purpose

Build the first version of a personal-use low-float momentum stock scanner.

The scanner should identify U.S. stocks showing unusual intraday momentum, with a focus on low-float runners, high relative volume, high daily percentage gain, strong liquidity, and real-time alert readiness.

This scanner is a market-awareness tool only. It does not place trades, recommend trades, or automate execution.

## MVP Goal

The first deliverable is a polling-based scanner engine that:

1. Pulls market data on a recurring interval.
2. Filters for low-float momentum candidates.
3. Calculates relative volume and daily percentage gain.
4. Assigns each candidate a momentum tier.
5. Scores and ranks candidates.
6. Emits voice-ready alert events.
7. Outputs a ranked table to the console.

Do not build a full dashboard yet.  
Do not build trade execution.  
Do not build broker order routing.  
Do not build social/community features.  

## Scanner Philosophy

The scanner should act as a radar, not a trading system.

The scanner finds attention.  
The trader decides whether a setup is actionable.  
Risk management remains outside the scanner.

The scanner should prioritize finding low-float stocks that are moving with unusual volume before they become too extended, while still highlighting extreme runners.

## Core Universe

The default universe should include U.S. common stocks only.

Exclude by default:

- ETFs
- ETNs
- Warrants
- Rights
- Units
- Preferred shares
- Closed-end funds
- OTC stocks
- Crypto
- Options
- Futures

If the chosen API cannot perfectly classify security type during MVP, document the limitation and filter as much as the data provider allows.

## Default Price Range

Include only stocks with current price between:

```text
$0.25 and $20.00
```

Configuration values:

```text
MIN_PRICE = 0.25
MAX_PRICE = 20.00
```

## Default Float Range

Include only stocks with float between:

```text
500,000 and 10,000,000 shares
```

Configuration values:

```text
MIN_FLOAT = 500_000
MAX_FLOAT = 10_000_000
```

Float classifications:

| Classification | Float Range |
|---|---:|
| Micro float | 500k to 2M |
| Low float | 2M to 10M |
| Borderline float | 10M to 20M |
| Ignore by default | Above 20M |

Float data should be cached because float does not need to be fetched continuously.

If float is unavailable for a ticker, the scanner should mark the ticker as `float_unknown` and exclude it from the main scanner by default.

Later versions may support an optional setting to include unknown-float tickers in a separate watch bucket.

## Core Scanner Eligibility

A stock is eligible for the main scanner if it meets all of the following requirements:

| Requirement | Default Value |
|---|---:|
| Current price | $0.25 to $20.00 |
| Float | 500k to 10M shares |
| Daily gain | At least 10% |
| Relative volume | At least 2.0 |
| Daily volume | At least 500,000 shares |

Configuration values:

```text
MIN_DAILY_GAIN_PCT = 10.0
MIN_RELATIVE_VOLUME = 2.0
MIN_DAILY_VOLUME = 500_000
```

## Why Daily Gain Starts at 10%, Not 50%

The owner originally requested stocks that are already up 50% or more.

That should remain an important alert threshold, but it should not be the minimum discovery threshold.

Reason:

A stock that is already up 50% may still continue running, but it may also be extended, halted, diluted, or near a reversal. The scanner should identify potential momentum earlier.

Therefore:

- 10%+ daily gain qualifies a stock for early scanner visibility.
- 25%+ daily gain qualifies as active momentum.
- 50%+ daily gain qualifies as a major runner.
- 100%+ daily gain qualifies as an extreme runner.

## Relative Volume Definition

Relative volume, or RVOL, should measure current daily volume compared with average daily volume.

Preferred MVP formula:

```text
RVOL = current_day_volume / average_daily_volume
```

Average daily volume should default to a 20-day lookback.

Configuration value:

```text
AVG_VOLUME_LOOKBACK_DAYS = 20
```

If the API provides a reliable average daily volume field, the scanner may use it. Otherwise, the scanner should calculate average daily volume from historical daily bars.

If average volume is zero or unavailable, RVOL should be marked as unavailable and the ticker should not pass the main scanner.

## Volume Requirements

The scanner should track two kinds of volume:

1. Cumulative daily volume.
2. Recent volume burst.

For MVP, cumulative daily volume is required.

Default requirement:

```text
Daily volume >= 500,000 shares
```

Recent volume burst detection may be implemented in v2.

Possible v2 definitions:

```text
1-minute volume burst = current 1-minute volume > 3x average 1-minute volume
5-minute volume burst = current 5-minute volume > 3x average 5-minute volume
```

## Momentum Tiers

The scanner should classify eligible stocks into tiers.

### Tier 1: Early Heat

Requirements:

- Daily gain: 10%+
- RVOL: 2.0+
- Daily volume: 500k+
- Float: 500k to 10M

Voice-ready message example:

```text
{TICKER} showing early heat. Up {daily_gain_pct} percent with {relative_volume} relative volume.
```

### Tier 2: Active Momentum

Requirements:

- Daily gain: 25%+
- RVOL: 3.0+
- Daily volume: 1M+
- Float: 500k to 10M

Voice-ready message example:

```text
{TICKER} active momentum. Up {daily_gain_pct} percent. Relative volume {relative_volume}.
```

### Tier 3: Major Runner

Requirements:

- Daily gain: 50%+
- RVOL: 5.0+
- Daily volume: 2M+
- Float: 500k to 10M

Voice-ready message example:

```text
{TICKER} major runner. Up {daily_gain_pct} percent with strong volume.
```

### Tier 4: Extreme Runner

Requirements:

- Daily gain: 100%+
- RVOL: 10.0+
- Daily volume: 5M+

Voice-ready message example:

```text
{TICKER} extreme runner. Up over {daily_gain_pct} percent. Manage risk.
```

## Tier Assignment Rules

A stock should receive the highest tier it qualifies for.

Example:

If a stock qualifies for Tier 1, Tier 2, and Tier 3, it should be classified as Tier 3.

If a stock meets the daily gain threshold for a tier but not the RVOL or volume threshold, it should remain in the lower tier it fully qualifies for.

## Scoring Engine

The scanner should calculate a numeric score for each eligible stock.

The score should be used to rank stocks in the output table.

Initial scoring suggestion:

| Condition | Points |
|---|---:|
| Float between 500k and 10M | +30 |
| Float between 500k and 2M | +15 bonus |
| Daily gain 10%+ | +10 |
| Daily gain 25%+ | +20 additional |
| Daily gain 50%+ | +30 additional |
| Daily gain 100%+ | +30 additional |
| RVOL 2+ | +20 |
| RVOL 5+ | +30 additional |
| RVOL 10+ | +30 additional |
| Daily volume 500k+ | +10 |
| Daily volume 1M+ | +15 additional |
| Daily volume 5M+ | +25 additional |
| Near high of day | +20 |
| New high of day | +30 |
| Recent volume burst | +25 |
| Recent news catalyst | +25 |
| Recent SEC filing | +25 |
| Already up 150%+ | -20 risk penalty |
| Offering/dilution keyword detected | -40 risk penalty |

For MVP, if news, SEC filings, and recent volume burst are not implemented yet, their scoring fields should be omitted or set to zero.

The scoring engine should be easy to modify later.

## High-of-Day Tracking

MVP should include high-of-day values if the data provider makes them available.

Track:

- Current price
- High of day
- Distance from high of day as a percentage

Suggested formula:

```text
hod_distance_pct = ((high_of_day - current_price) / high_of_day) * 100
```

A stock is considered near high of day if:

```text
hod_distance_pct <= 2.0
```

A stock is considered at or making a new high of day if:

```text
current_price >= high_of_day
```

If the data provider does not provide reliable high-of-day data in MVP, document the limitation and skip HOD scoring.

## Alert Event Types

The scanner should emit structured events that can later be used by voice alerts, dashboards, logs, or notifications.

MVP event types:

- `new_match`
- `tier_upgrade`
- `near_hod`
- `new_hod`

Later event types:

- `volume_surge`
- `price_acceleration`
- `news_detected`
- `sec_filing_detected`
- `halt_detected`
- `resume_detected`

## Alert Object Shape

Use a structured event object similar to:

```python
{
    "ticker": "ABCD",
    "event_type": "tier_upgrade",
    "tier": "major_runner",
    "priority": 3,
    "message": "ABCD major runner. Up 54.2 percent with strong volume.",
    "timestamp": "2026-06-16T09:45:00-04:00",
    "data": {
        "price": 3.42,
        "daily_gain_pct": 54.2,
        "relative_volume": 6.4,
        "daily_volume": 4_200_000,
        "float": 3_800_000,
        "score": 145
    }
}
```

## Alert Cooldowns

The scanner should avoid repeating the same alert too often.

Default cooldowns:

| Event Type | Cooldown |
|---|---:|
| `new_match` | 10 minutes |
| `tier_upgrade` | No cooldown |
| `near_hod` | 5 minutes |
| `new_hod` | 3 minutes |
| `volume_surge` | 5 minutes |
| `news_detected` | 10 minutes after first headline |
| `sec_filing_detected` | No cooldown for first filing |
| `halt_detected` | No cooldown |
| `resume_detected` | No cooldown |

Cooldowns should be based on ticker plus event type.

Example key:

```text
ABCD:new_hod
```

## Polling Behavior

MVP should use polling rather than WebSockets.

Default polling interval:

```text
60 seconds
```

Configuration value:

```text
POLL_INTERVAL_SECONDS = 60
```

The app should run continuously until stopped by the user.

At each polling interval:

1. Load or refresh the stock universe.
2. Pull market data.
3. Pull or reference cached float data.
4. Calculate daily gain.
5. Calculate RVOL.
6. Apply eligibility filters.
7. Calculate score.
8. Assign tier.
9. Detect alert events.
10. Apply cooldowns.
11. Print ranked output.
12. Emit voice-ready messages.

## Console Output

The MVP should print a ranked table to the console.

Suggested columns:

| Column | Description |
|---|---|
| Rank | Rank by score |
| Ticker | Stock symbol |
| Tier | Momentum tier |
| Score | Numeric scanner score |
| Price | Current price |
| Daily % | Daily percentage gain |
| RVOL | Relative volume |
| Volume | Daily volume |
| Float | Stock float |
| HOD Dist % | Distance from high of day |
| Last Event | Most recent event type |

Example:

```text
Rank  Ticker  Tier            Score  Price  Daily%  RVOL  Volume     Float     HOD Dist  Last Event
1     ABCD    Major Runner    145    3.42   54.2    6.4   4.2M       3.8M      0.5%      new_hod
2     LMNO    Active Momentum 112    1.18   31.7    4.1   1.6M       6.2M      1.8%      new_match
```

## Voice-Ready Messages

The scanner should generate messages but does not need to play audio in the first scanner-only file unless voice has already been implemented.

Messages should be short and useful.

Good examples:

```text
ABCD showing early heat. Up 14 percent with 2.8 relative volume.
ABCD active momentum. Up 28 percent. Relative volume 4.2.
ABCD major runner. Up 56 percent with strong volume.
ABCD new high of day. Up 61 percent.
ABCD extreme runner. Up 118 percent. Manage risk.
```

Avoid overly long messages.

Avoid financial advice language such as:

```text
Buy ABCD.
ABCD is a good trade.
Enter now.
This will keep running.
```

## Configuration Requirements

All major scanner thresholds should live in a config file.

Required config values:

```python
MIN_PRICE = 0.25
MAX_PRICE = 20.00
MIN_FLOAT = 500_000
MAX_FLOAT = 10_000_000
MIN_DAILY_GAIN_PCT = 10.0
MIN_RELATIVE_VOLUME = 2.0
MIN_DAILY_VOLUME = 500_000
AVG_VOLUME_LOOKBACK_DAYS = 20
POLL_INTERVAL_SECONDS = 60
NEAR_HOD_DISTANCE_PCT = 2.0
MAX_RESULTS_DISPLAYED = 25
```

## Data Fields Needed Per Ticker

Each ticker should have, at minimum:

```python
{
    "ticker": str,
    "price": float,
    "previous_close": float,
    "daily_gain_pct": float,
    "daily_volume": int,
    "average_daily_volume": int,
    "relative_volume": float,
    "float": int | None,
    "high_of_day": float | None,
    "hod_distance_pct": float | None,
    "score": int,
    "tier": str,
    "last_event": str | None,
}
```

## Error Handling

The scanner should handle missing or bad data gracefully.

Rules:

- If price is missing, skip ticker.
- If previous close is missing or zero, skip ticker.
- If average volume is missing or zero, skip ticker.
- If float is missing, exclude from main scanner by default.
- If high of day is missing, continue without HOD scoring.
- If API request fails, log the error and continue on the next polling cycle.
- If one ticker fails, the entire scanner should not crash.

## Logging

The MVP should log:

- Scanner start time.
- Polling cycle start and end.
- API errors.
- Number of symbols scanned.
- Number of eligible matches.
- Alert events emitted.

A simple console log is acceptable for MVP.

Later versions may write structured JSON logs or CSV logs.

## Non-Goals for Scanner MVP

Do not build the following in this file's scope:

- Trade execution
- Broker order placement
- Account connection
- Profit/loss tracking
- Backtesting engine
- Full GUI dashboard
- Mobile app
- Discord bot
- Community features
- AI trade recommendations
- Automatic buy/sell signals

## Acceptance Criteria

The scanner MVP is complete when:

1. It can run from the command line.
2. It scans a universe of U.S. stocks using configurable thresholds.
3. It filters for low-float momentum candidates.
4. It calculates daily gain and RVOL.
5. It excludes stocks outside the price, float, gain, volume, and RVOL requirements.
6. It assigns a tier to each eligible stock.
7. It calculates a score for each eligible stock.
8. It prints a ranked table of candidates.
9. It emits structured alert events.
10. It applies cooldowns to repeated alerts.
11. It handles missing data without crashing.
12. It does not place trades or provide buy/sell instructions.

## Suggested First Codex Task

Build the scanner engine first.

Do not build the UI yet.
Do not build trading execution.
Do not place trades.

The first deliverable is a polling-based scanner that returns a ranked list of low-float momentum stocks and emits voice-ready alert events.

