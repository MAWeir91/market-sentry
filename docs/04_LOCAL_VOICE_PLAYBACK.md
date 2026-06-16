# Market Sentry — Phase 6 Local Voice Playback

## 1. Purpose

Phase 6 adds local text-to-speech playback for Market Sentry's existing voice-ready alert events.

Market Sentry already creates structured `AlertEvent` objects and voice-ready messages. Phase 6 should make those messages speak locally while keeping the system safe, testable, and optional.

The goal is not to create live market scanning yet. The goal is to prove that generated alerts can be spoken through a local speaker layer using mock scanner data.

## 2. Product Boundary

Market Sentry is a personal-use low-float momentum scanner with future voice alerts.

Market Sentry is not a trading bot.

Phase 6 must not add:

- order execution
- brokerage trading/order API connections
- anything that can place trades
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
- polling/live loop behavior
- trading advice language

## 3. Phase 6 Goal

Create a local speaker layer that can consume existing `AlertEvent` objects and speak their `message` text.

The owner should be able to run Market Sentry in a mode that prints the mock scanner report, prints voice-ready alerts, and optionally speaks those alert messages locally.

Actual voice playback should be optional and easy to disable.

## 4. Voice Playback Philosophy

The speaker layer should be treated as an output adapter.

It should not know how scanner results are calculated.
It should not generate alerts.
It should not apply trading logic.
It should not decide whether a stock is good or bad.
It should only speak alert messages it is given.

Approved flow:

```text
MockMarketDataProvider
  -> ScannerEngine
  -> generate_alerts(results)
  -> Speaker speaks alert.message
```

## 5. Speaker Abstraction

Create a simple speaker abstraction so future voice backends can be swapped without changing scanner or alert logic.

Recommended structure:

```text
src/market_sentry/alerts/speaker.py
```

Recommended concepts:

```python
class AlertSpeaker:
    def speak(self, message: str) -> None:
        ...
```

Possible implementations:

```text
NullSpeaker       -> does nothing; safest default for tests
ConsoleSpeaker    -> prints what would be spoken; useful for dry runs
LocalTTSSpeaker   -> performs local text-to-speech playback if available
```

Phase 6 should prefer a safe default. Tests should never require audio hardware.

## 6. Suggested Playback Modes

The CLI should support simple optional modes.

Recommended behavior:

```text
python -m market_sentry
```

Default behavior remains safe and familiar:

- prints scanner report
- prints voice-ready alerts
- does not speak aloud unless explicitly enabled

Recommended optional command:

```text
python -m market_sentry --speak
```

Expected behavior:

- prints scanner report
- prints voice-ready alerts
- speaks alert messages locally

Optional dry-run command if implemented:

```text
python -m market_sentry --dry-run-voice
```

Expected behavior:

- prints scanner report
- prints voice-ready alerts
- prints which messages would be spoken
- does not play audio

If Codex suggests a simpler command design, it must explain the tradeoff before implementation.

## 7. Local TTS Backend

Phase 6 may use a local text-to-speech backend if it is simple and cross-platform enough for the project.

Recommended first backend:

```text
pyttsx3
```

Reason:

- local/offline style usage
- simple Python interface
- suitable for a personal desktop prototype

However, the code should be written so the speaker abstraction does not depend on one specific library forever.

If a TTS package is added, it should be added as an optional dependency, not a mandatory dependency for running tests.

Suggested optional dependency group:

```toml
[project.optional-dependencies]
voice = [
  "pyttsx3",
]
```

Then the owner can install voice support with:

```powershell
python -m pip install -e ".[dev,voice]"
```

If optional dependency syntax causes problems, Codex should explain and propose the safest alternative.

## 8. Error Handling

Voice playback must fail safely.

If the local TTS engine is unavailable, audio devices are unavailable, or the voice package is not installed, Market Sentry should not crash unexpectedly.

Preferred behavior:

- print the scanner report
- print the voice-ready alerts
- show a clear message that voice playback could not run
- continue safely

Example:

```text
Voice playback unavailable: install voice dependencies with python -m pip install -e ".[voice]"
```

Do not hide errors completely, but do not let missing audio support make the scanner unusable.

## 9. Trading Advice Restrictions

Spoken messages must continue to avoid trading advice language.

Do not speak or generate phrases such as:

- buy
- sell
- enter
- exit
- guaranteed
- safe trade
- sure thing
- can't lose
- should trade

Approved style:

```text
XTRM extreme runner. Up 118.0 percent with 12.5 relative volume. Float 1.3 million. Score 99.6.
```

Not approved:

```text
Buy XTRM now.
```

## 10. Cooldowns

Phase 6 may use the existing cooldown manager only if it remains simple and deterministic.

However, cooldown behavior is not required for the first local voice playback integration unless explicitly approved.

Preferred Phase 6 approach:

- speak the alerts generated during one CLI run when `--speak` is used
- do not add polling loops yet
- do not add persistent cooldown state yet
- do not add background processes yet

Cooldowns will matter more when Market Sentry gains a polling loop or live mode.

## 11. Expected Files

Expected files to create:

```text
src/market_sentry/alerts/speaker.py
tests/test_speaker.py
```

Expected files to modify:

```text
src/market_sentry/main.py
tests/test_main.py
README.md
pyproject.toml
src/market_sentry/alerts/__init__.py
```

Do not modify scanner core unless there is a strong reason.

## 12. Expected CLI Behavior

After Phase 6, these commands should be considered:

```powershell
python -m market_sentry
```

Expected:

- no audio playback by default
- scanner report printed
- voice-ready alerts printed

```powershell
python -m market_sentry --speak
```

Expected:

- scanner report printed
- voice-ready alerts printed
- alert messages spoken locally if voice support is available
- no real APIs or live market data

Optional:

```powershell
python -m market_sentry --dry-run-voice
```

Expected:

- scanner report printed
- voice-ready alerts printed
- messages listed as would-be-spoken
- no audio playback

## 13. Testing Requirements

Tests should verify:

- speaker model/abstraction can be created
- `NullSpeaker` does not speak or crash
- `ConsoleSpeaker` or dry-run speaker records/prints messages without real audio
- CLI default mode does not call real audio playback
- CLI `--speak` mode routes alert messages to a speaker
- tests do not require audio hardware
- tests do not require installed TTS dependencies unless mocked
- missing TTS dependency fails safely
- scanner report still includes qualified results
- scanner report still includes rejected results
- scanner report still includes voice-ready alerts
- no APIs, credentials, network calls, dashboard, or trading/order behavior are added
- spoken/voice messages avoid banned trading advice language

## 14. Acceptance Criteria

Phase 6 is complete when:

- local speaker abstraction exists
- voice playback is optional
- tests pass without requiring audio hardware
- `python -m market_sentry` still works without speaking by default
- an approved voice command can attempt local speech playback
- missing voice dependencies fail safely
- scanner and alert layers remain cleanly separated
- no real market data or trading behavior is introduced

## 15. Out of Scope For Phase 6

Do not add:

- polling loops
- repeated live scanning
- real market-data providers
- WebSockets
- news alerts
- SEC filing alerts
- halt alerts
- dashboard controls
- persistent alert history
- persistent cooldown storage
- background services
- brokerage integrations
- order execution

## 16. Future Phases

Possible future phases after Phase 6:

```text
Phase 7 — Mock polling loop with cooldowns
Phase 8 — First real market data provider
Phase 9 — Float/reference data provider
Phase 10 — News, SEC filings, and halt catalysts
Phase 11 — Dashboard MVP
```
