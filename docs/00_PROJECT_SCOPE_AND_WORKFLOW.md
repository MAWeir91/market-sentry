# Market Sentry — Project Scope and Workflow

## 1. Project Summary

**Market Sentry** is a personal-use market scanner focused on identifying low-float momentum stocks and producing voice-ready alerts.

The first version of Market Sentry will focus on scanning for low-float stocks with strong daily gains, high volume, and high relative volume. Future versions may add voice alerts, news, SEC filings, trading halts, dashboard views, and live WebSocket data.

Market Sentry is designed to act as a market radar. It finds stocks worth paying attention to. It does not make trading decisions.

## 2. Project Identity

- **Project Name:** Market Sentry
- **Root Folder:** `market-sentry`
- **Python Package Name:** `market_sentry`
- **Owner:** Adam
- **Advisor / Project Manager:** ChatGPT
- **Builder:** Codex

## 3. Product Boundaries

Market Sentry is a scanner, alerting, and research tool only.

Market Sentry must not:

- Place trades.
- Connect to brokerage order APIs.
- Give buy or sell instructions.
- Automate trade execution.
- Risk real capital.
- Present scanner events as guaranteed trading signals.

Market Sentry may:

- Scan stocks based on configured filters.
- Rank stocks by momentum and attention score.
- Generate voice-ready alert messages.
- Log scan results and alert events.
- Display ranked scanner results.
- Monitor market data, news, filings, and halts in future phases.

The core philosophy is:

```text
Scanner finds attention.
Strategy decides action.
Risk rules protect the account.
```

## 4. Initial Scanner Focus

The first scanner module should focus on low-float U.S. stocks with strong momentum.

Default scan profile:

- **Price Range:** $0.25 to $20.00
- **Float Range:** 500,000 to 10,000,000 shares
- **Minimum Daily Gain:** 10%
- **Preferred Major Runner Gain:** 50%+
- **Minimum Relative Volume:** 2.0
- **Minimum Daily Volume:** 500,000 shares

The scanner should not only filter stocks. It should rank and classify them.

Initial alert tiers:

| Tier | Name | Default Criteria |
|---:|---|---|
| 1 | Early Heat | 10%+ daily gain, RVOL 2+, 500k+ volume |
| 2 | Active Momentum | 25%+ daily gain, RVOL 3+, 1M+ volume |
| 3 | Major Runner | 50%+ daily gain, RVOL 5+, 2M+ volume |
| 4 | Extreme Runner | 100%+ daily gain, RVOL 10+, 5M+ volume |

All criteria should eventually be configurable.

## 5. Technical Principles

Codex should follow these principles throughout the project:

1. **Build incrementally.** Each phase should be small, testable, and reviewable.
2. **Keep scanner logic separate from data providers.** The scanner engine should work with mock data before real APIs are added.
3. **Use interfaces and models.** Market data, scanner results, and alert events should be represented with clear Python models.
4. **Avoid premature UI complexity.** Build the scanner core before dashboards.
5. **Avoid premature API lock-in.** Add provider abstraction before real market-data integrations.
6. **Make behavior configurable.** Thresholds should not be hardcoded deep inside scanner logic.
7. **Write tests for core logic.** Filters, scoring, and tiers must be tested.
8. **No trading execution.** This project must remain a scanner and alerting system.
9. **Document decisions.** Major assumptions or architectural choices should be noted in relevant markdown files.
10. **Prefer clarity over cleverness.** The owner should be able to understand the code structure and behavior.

## 6. Roadmap

### Phase 0 — Project Scaffold

**Goal:** Create the basic repository structure and setup files.

Expected outputs:

```text
market-sentry/
  README.md
  pyproject.toml
  .env.example
  .gitignore
  docs/
    00_PROJECT_SCOPE_AND_WORKFLOW.md
    01_SCANNER_REQUIREMENTS.md
  src/
    market_sentry/
      __init__.py
      config.py
      main.py
      scanner/
        __init__.py
      data/
        __init__.py
      alerts/
        __init__.py
  tests/
    __init__.py
```

This phase should not implement the full scanner yet.

---

### Phase 1 — Scanner Core with Mock Data

**Goal:** Build the scanner decision engine using mock data.

The scanner should answer:

- Does this stock qualify?
- Why did it qualify or fail?
- What tier is it?
- What score does it receive?
- What voice-ready alert message would it produce later?

Expected files may include:

```text
src/market_sentry/scanner/models.py
src/market_sentry/scanner/filters.py
src/market_sentry/scanner/scoring.py
src/market_sentry/scanner/tiers.py
src/market_sentry/scanner/engine.py
src/market_sentry/data/mock_provider.py
tests/test_filters.py
tests/test_scoring.py
tests/test_tiers.py
tests/test_engine.py
```

---

### Phase 2 — Data Provider Interface

**Goal:** Create a clean abstraction for market-data providers before connecting to a real API.

Expected files may include:

```text
src/market_sentry/data/provider.py
src/market_sentry/data/models.py
```

The scanner should depend on provider interfaces, not on one specific API vendor.

Possible future providers:

- Alpaca
- Polygon / Massive
- Financial Modeling Prep
- Finnhub
- Other market-data vendors

---

### Phase 3 — First Real Market Data Provider

**Goal:** Connect Market Sentry to one real market-data provider.

This phase should not begin until the owner and PM choose the provider.

Expected work may include:

- API client wrapper.
- Environment variable support.
- Error handling.
- Rate-limit awareness.
- Data normalization into internal models.
- Tests using mocked API responses.

No API key should ever be committed to the repository.

---

### Phase 4 — Voice Alert Engine

**Goal:** Convert scanner events into spoken or voice-ready alerts.

Expected files may include:

```text
src/market_sentry/alerts/events.py
src/market_sentry/alerts/cooldowns.py
src/market_sentry/alerts/voice_formatter.py
src/market_sentry/alerts/speaker.py
```

First build voice-ready strings. Local text-to-speech can be added after event formatting and cooldown logic work correctly.

Example messages:

```text
ABCD showing early heat. Up 18 percent with 2.8 relative volume.
XYZ active momentum. Up 36 percent. Relative volume 4.2.
LMNO major runner. Up 64 percent with strong volume.
```

---

### Phase 5 — Polling Runner

**Goal:** Run the scanner repeatedly on a configured interval.

Expected behavior:

- Load configuration.
- Pull market data from the selected provider.
- Run scanner engine.
- Print ranked scanner results.
- Emit alert events.
- Respect cooldowns.

Initial refresh interval:

```text
60 seconds
```

Later versions may reduce the interval or add WebSocket streaming.

---

### Phase 6 — Logging and Watch History

**Goal:** Persist scan results and alert events locally.

Potential outputs:

- CSV logs.
- JSONL event logs.
- Daily scanner history.
- Watchlist snapshots.

This phase should help the owner review what the scanner saw during a trading session.

---

### Phase 7 — Dashboard MVP

**Goal:** Add a simple dashboard after scanner logic is stable.

Possible dashboard options:

- Streamlit dashboard.
- Rich terminal table.
- Lightweight web UI.

Initial dashboard columns may include:

- Ticker
- Price
- Daily gain %
- RVOL
- Daily volume
- Float
- Tier
- Score
- High of day distance
- Last alert

---

### Phase 8 — Catalyst Layer

**Goal:** Add catalyst monitoring.

Potential catalyst modules:

- News headlines.
- SEC filings.
- Trading halts.
- Resumptions.
- Reverse splits.
- Forward splits.

The scanner should eventually be able to say not only that a stock is moving, but why it may be moving.

---

### Phase 9 — Live Stream Mode

**Goal:** Add faster real-time market monitoring using WebSockets or streaming APIs.

This phase should come after polling mode works reliably.

Expected considerations:

- Connection stability.
- Reconnect handling.
- Stream subscriptions.
- Rate limits.
- Event deduplication.
- Alert throttling.

---

### Phase 10 — Review, Hardening, and Documentation

**Goal:** Improve reliability and maintainability.

Expected work:

- Expand tests.
- Improve documentation.
- Validate configuration.
- Improve errors and logs.
- Add type hints.
- Add linting/formatting if not already present.
- Review architecture before adding more features.

## 7. Official Build Workflow

Every build phase must follow this workflow.

### Step 1 — PM Prompt

ChatGPT creates a build-phase prompt for Codex.

The prompt should include:

- Phase name.
- Goal.
- Files expected to be created or changed.
- Specific requirements.
- Out-of-scope items.
- Expected planning response from Codex.

### Step 2 — Codex Planning Response

Codex must confirm understanding before coding.

During this step, Codex must not write code, edit files, or run implementation commands.

Codex should respond with:

- Understanding of the phase.
- What it plans to build.
- Files it expects to create or change.
- Tests it expects to create or run.
- Assumptions.
- Risks.
- Suggested improvements, if any.

### Step 3 — PM Review and Approval

Adam gives Codex's planning response to ChatGPT.

ChatGPT reviews Codex's understanding and suggestions.

ChatGPT then provides an approval prompt that either:

- Confirms Codex's plan as written.
- Approves selected suggestions.
- Rejects selected suggestions.
- Clarifies scope.
- Gives permission to build.

### Step 4 — Codex Build

Codex may build only after receiving explicit approval from the PM prompt.

After building, Codex must report:

- Files created.
- Files changed.
- Tests created.
- Tests run.
- Test results.
- Summary of implemented behavior.
- Known issues or limitations.
- Any deviations from the approved plan.

### Step 5 — Zip and PM Code Review

After Codex builds, Adam gives Codex's summary to ChatGPT.

ChatGPT gives Adam a command to zip the files changed in the phase.

Adam uploads the zip file.

ChatGPT reviews the files and determines whether the phase is complete.

The phase is complete only when ChatGPT confirms completion.

## 8. Codex Planning Response Format

Codex should use this format during the planning step:

```md
# Phase Planning Response

## Phase

[Phase name]

## My Understanding

[Confirm what this phase is meant to accomplish.]

## Planned Work

[List what will be built.]

## Files I Expect to Create

[List files.]

## Files I Expect to Modify

[List files.]

## Tests I Expect to Add or Run

[List tests.]

## Assumptions

[List assumptions.]

## Risks / Questions

[List risks or questions.]

## Suggested Improvements

[List optional improvements. Do not implement them unless approved.]

## Confirmation

I will not code until I receive explicit approval to proceed.
```

## 9. Codex Build Response Format

Codex should use this format after a build step:

```md
# Phase Build Summary

## Phase

[Phase name]

## Files Created

[List files.]

## Files Modified

[List files.]

## Tests Created or Modified

[List tests.]

## Tests Run

[List commands and results.]

## Summary of Work Completed

[Explain what was implemented.]

## Behavior Now Supported

[List new behavior.]

## Known Issues / Limitations

[List anything incomplete or risky.]

## Deviations From Approved Plan

[List deviations, or say none.]

## Recommended Next Step

[Suggest next phase.]
```

## 10. File and Folder Standards

The project should use this general structure:

```text
market-sentry/
  README.md
  pyproject.toml
  .env.example
  .gitignore
  docs/
  src/
    market_sentry/
      __init__.py
      config.py
      main.py
      scanner/
      data/
      alerts/
  tests/
```

Python package imports should use:

```python
import market_sentry
```

Do not use spaces in file or folder names.

Use lowercase snake_case for Python files.

Use numbered markdown files in `docs/` when order matters.

## 11. Testing Standards

Codex should add or update tests for core behavior in each phase when practical.

Minimum testing expectations:

- Filter logic should be tested.
- Tier classification should be tested.
- Scoring behavior should be tested.
- Cooldown logic should be tested once alerts are added.
- Provider interfaces should be tested with mocks.
- Real API calls should not be required for normal unit tests.

Preferred test command:

```bash
pytest
```

If `pytest` is not yet configured, Codex should explain that and suggest the correct setup.

## 12. Configuration Standards

Scanner thresholds should eventually be configurable.

Examples:

```text
MIN_PRICE=0.25
MAX_PRICE=20.00
MIN_FLOAT=500000
MAX_FLOAT=10000000
MIN_DAILY_GAIN_PCT=10
MIN_RELATIVE_VOLUME=2
MIN_DAILY_VOLUME=500000
SCAN_INTERVAL_SECONDS=60
```

Secrets and API keys must be stored in environment variables and documented in `.env.example`.

No real secrets should ever be committed.

## 13. Review and Zip Process

After Codex completes a build phase, ChatGPT will provide a zip command for Adam.

The zip should include only files relevant to the completed phase unless ChatGPT says otherwise.

Example command format:

```bash
zip -r phase-0-market-sentry-scaffold.zip README.md pyproject.toml .env.example .gitignore docs src tests
```

The exact zip command will be generated after reviewing Codex's build summary.

Adam will upload the zip to ChatGPT.

ChatGPT will review the files and confirm whether the phase is complete.

## 14. Definition of Done

A phase is complete only when:

- Codex planned the work before coding.
- ChatGPT reviewed and approved the plan.
- Codex built only the approved scope.
- Codex summarized files changed and tests run.
- Adam zipped and uploaded changed files.
- ChatGPT reviewed the files.
- Tests pass, or any failures are understood and accepted.
- ChatGPT confirms the phase is complete.

## 15. Current Phase Tracker

| Phase | Name | Status |
|---:|---|---|
| 0 | Project Scaffold | Not Started |
| 1 | Scanner Core with Mock Data | Not Started |
| 2 | Data Provider Interface | Not Started |
| 3 | First Real Market Data Provider | Not Started |
| 4 | Voice Alert Engine | Not Started |
| 5 | Polling Runner | Not Started |
| 6 | Logging and Watch History | Not Started |
| 7 | Dashboard MVP | Not Started |
| 8 | Catalyst Layer | Not Started |
| 9 | Live Stream Mode | Not Started |
| 10 | Review, Hardening, and Documentation | Not Started |

## 16. Notes for Codex

Codex should remember that Adam is the owner and decision-maker.

Codex should treat ChatGPT as the project manager and architecture advisor.

Codex should not assume permission to expand scope.

Codex may suggest improvements, but must wait for approval before implementing them.

Codex should keep each phase small enough to review.

Codex should prioritize working, tested foundations before advanced features.

Codex should never add trade execution or brokerage order placement functionality to this project.
