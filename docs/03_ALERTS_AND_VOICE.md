# Market Sentry — Alerts and Voice Spec

## 1. Purpose

This document defines the alert and voice roadmap for Market Sentry.

Market Sentry is a personal-use low-float momentum scanner. The scanner core identifies qualified candidates, assigns tiers, calculates scores, and explains pass/fail reasons. The alert layer converts scanner results into voice-ready alert events.

Phase 4 does **not** make the computer speak yet. Phase 4 creates the alert event system that future voice output will use.

## 2. Current Project Status

Completed phases:

- Phase 0 — Project scaffold
- Phase 0.1 — Dev/test/GitHub setup
- Phase 1 — Scanner core with mock data
- Phase 2 — Data provider interface
- Phase 3 — Mock CLI runner

Current data source:

- `MockMarketDataProvider` only

Current command:

```bash
python -m market_sentry
```

## 3. Product Boundary

Market Sentry is not a trading bot.

Do not add:

- order execution
- brokerage trading/order API connections
- trade placement
- buy/sell recommendations
- automatic trading behavior

Phase 4 must also avoid:

- real market-data APIs
- API keys
- network calls
- WebSockets
- Alpaca
- Polygon/Massive
- Financial Modeling Prep
- SEC filings integrations
- news integrations
- halt integrations
- dashboard UI
- actual text-to-speech playback

## 4. Phase 4 Goal

Create a voice-ready alert event layer.

The alert layer should take existing scanner results and produce structured alert events that future voice and UI systems can consume.

The alert layer should answer:

- Which scanner results deserve alerts?
- What type of alert is this?
- How important is this alert?
- What should the alert message say?
- Should this alert be suppressed because of cooldown?

## 5. Phase 4 Non-Goal

Phase 4 should not create actual speech output.

Actual local text-to-speech should be a later phase.

Phase 4 output should be plain Python alert objects and formatted strings that are ready to be spoken later.

## 6. Alert Event Types

Initial alert types should be simple and based only on scanner results.

Recommended event types:

- `NEW_QUALIFIED` — a stock qualifies for the scanner
- `TIER_1_EARLY_HEAT` — qualified Tier 1 candidate
- `TIER_2_ACTIVE_MOMENTUM` — qualified Tier 2 candidate
- `TIER_3_MAJOR_RUNNER` — qualified Tier 3 candidate
- `TIER_4_EXTREME_RUNNER` — qualified Tier 4 candidate
- `HIGH_SCORE` — qualified candidate has an unusually strong scanner score

Future event types, not part of Phase 4:

- high-of-day break
- volume surge
- price acceleration
- halt detected
- resume detected
- news detected
- SEC filing detected

## 7. Alert Priority

Alerts should have clear priority levels.

Suggested priority scale:

- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

Suggested mapping:

| Event Type | Priority |
|---|---|
| `NEW_QUALIFIED` | `LOW` |
| `TIER_1_EARLY_HEAT` | `LOW` |
| `TIER_2_ACTIVE_MOMENTUM` | `MEDIUM` |
| `TIER_3_MAJOR_RUNNER` | `HIGH` |
| `TIER_4_EXTREME_RUNNER` | `CRITICAL` |
| `HIGH_SCORE` | `HIGH` |

## 8. Alert Event Model

Create a structured alert model.

Recommended fields:

- `symbol`
- `event_type`
- `priority`
- `message`
- `scanner_result`

Optional fields:

- `created_at`
- `metadata`

If `created_at` is added, tests should remain deterministic. Prefer allowing it to be passed in or defaulted safely.

## 9. Alert Message Style

Messages should be short, clear, and voice-friendly.

Good examples:

```text
XTRM extreme runner. Up 118.0 percent with 12.5 relative volume. Float 1.3 million.
```

```text
ABCD major runner. Up 58.0 percent. Score 87.4.
```

```text
WXYZ active momentum. Up 31.0 percent with 3.8 relative volume.
```

Avoid overly long messages.

Avoid language that implies trade advice, such as:

- buy now
- sell now
- enter here
- exit here
- guaranteed runner
- safe trade

The alert should identify market activity, not recommend actions.

## 10. Alert Formatting Rules

Use readable values:

- price: `$4.80`
- daily gain: `58.0 percent`
- relative volume: `6.2 relative volume`
- float: `4.5 million`
- score: `87.4`

For voice-ready text, prefer words over symbols:

- use `percent`, not `%`
- use `relative volume`, not `RVOL`
- use `million`, not `M`

Terminal display can still use compact formats later, but spoken messages should be natural.

## 11. Alert Generation Rules

For Phase 4, generate alerts only from qualified scanner results.

Rejected scanner results should not generate voice-ready alerts yet.

Suggested behavior:

- Every qualified result can produce a tier-based alert.
- Tier 1 produces `TIER_1_EARLY_HEAT`.
- Tier 2 produces `TIER_2_ACTIVE_MOMENTUM`.
- Tier 3 produces `TIER_3_MAJOR_RUNNER`.
- Tier 4 produces `TIER_4_EXTREME_RUNNER`.
- A high score can optionally produce `HIGH_SCORE` if score is at least 90.

To avoid too much noise, Phase 4 should keep alert generation simple and deterministic.

## 12. Cooldown Rules

Create a cooldown system, but keep it simple.

The cooldown system should decide whether an alert should be allowed or suppressed based on symbol and event type.

Suggested key:

```text
(symbol, event_type)
```

Suggested defaults:

| Event Type | Cooldown |
|---|---:|
| `NEW_QUALIFIED` | 10 minutes |
| `TIER_1_EARLY_HEAT` | 10 minutes |
| `TIER_2_ACTIVE_MOMENTUM` | 5 minutes |
| `TIER_3_MAJOR_RUNNER` | 3 minutes |
| `TIER_4_EXTREME_RUNNER` | 1 minute |
| `HIGH_SCORE` | 5 minutes |

The cooldown manager should be deterministic and testable.

Tests should be able to inject timestamps rather than depend on real time.

## 13. Recommended Phase 4 Files

Create:

```text
src/market_sentry/alerts/events.py
src/market_sentry/alerts/formatter.py
src/market_sentry/alerts/cooldowns.py
src/market_sentry/alerts/generator.py
tests/test_alert_events.py
tests/test_alert_formatter.py
tests/test_cooldowns.py
tests/test_alert_generator.py
```

Modify:

```text
src/market_sentry/alerts/__init__.py
```

Possible modifications only if necessary:

```text
src/market_sentry/main.py
tests/test_main.py
```

Do not modify scanner core unless there is a strong reason.

## 14. Phase 4 Testing Expectations

Tests should verify:

- alert event model can be created
- alert priorities are correct
- formatter produces voice-friendly messages
- formatter avoids trading advice language
- alert generator creates alerts from qualified scanner results
- alert generator ignores rejected scanner results
- Tier 1 through Tier 4 results map to correct event types
- high-score results can create `HIGH_SCORE` alerts if implemented
- cooldown manager allows first alert
- cooldown manager suppresses repeated alert within cooldown
- cooldown manager allows alert after cooldown expires
- cooldown logic can be tested with injected timestamps
- no real APIs, network calls, credentials, or trading behavior are required

## 15. Definition of Done

Phase 4 is complete when:

- Alert event models exist.
- Alert formatter exists.
- Alert generator exists.
- Cooldown manager exists.
- Alerts are generated from scanner results using mock data only.
- Tests pass.
- No real APIs, network calls, text-to-speech playback, dashboard, or trading/order behavior are added.
- Codex provides a build summary.
- Adam zips changed files.
- ChatGPT reviews and approves the phase.
