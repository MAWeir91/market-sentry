# Market Sentry — Phase 8: Polling Loop with Mock Data

## Purpose

Phase 8 adds a safe, mock-only polling loop so Market Sentry can behave more like a live scanner without using real market data yet.

The goal is to move from a single scanner run to an optional repeated scanner loop:

```powershell
python -m market_sentry --loop --interval 30
```

This phase should remain local, deterministic, and test-safe.

## Current State Before Phase 8

Market Sentry already has:

- Project scaffold and GitHub setup
- Scanner core with mock data
- Data provider interface
- Mock market data provider
- CLI report
- Voice-ready alert event layer
- Optional local voice playback
- Rotation, 15-minute momentum, HOD, and HOD distance metrics

## Phase 8 Goal

Add an optional polling loop that repeatedly runs the existing mock scanner flow.

Each loop iteration should:

1. Pull candidates from `MockMarketDataProvider`
2. Run `ScannerEngine`
3. Generate alert events
4. Render the scanner report
5. Print the report
6. Optionally speak eligible alerts if `--speak` is enabled
7. Wait for the configured interval
8. Repeat until stopped

## Important Product Boundary

Market Sentry is a personal-use scanner and alerting tool.

It is not a trading bot.

Do not add:

- Order execution
- Brokerage trading/order API connections
- Trade placement
- Buy/sell recommendations
- Real market data APIs
- API keys
- Network calls
- WebSockets
- Dashboard UI
- News integrations
- SEC filing integrations
- Halt integrations
- Split integrations

## CLI Behavior

### Default Single Run

The default command should continue to run once:

```powershell
python -m market_sentry
```

Default behavior:

- Print one mock scanner report
- Print voice-ready alerts section
- Do not speak unless `--speak` is provided
- Do not loop

### Loop Mode

Loop mode should be enabled explicitly:

```powershell
python -m market_sentry --loop --interval 30
```

Loop behavior:

- Run the scanner repeatedly
- Wait `interval` seconds between runs
- Use mock data only
- Continue until the user presses `Ctrl+C`

### Voice Loop Mode

Voice loop mode should work when `--speak` is also provided:

```powershell
python -m market_sentry --loop --interval 30 --speak
```

Behavior:

- Print scanner reports each iteration
- Generate alerts each iteration
- Speak only alerts that pass cooldown checks
- Do not repeat the same alert every interval

### No-Speech Mode

`--no-speak` should explicitly disable speech and remain the default behavior:

```powershell
python -m market_sentry --loop --interval 30 --no-speak
```

## Approved CLI Flags

Phase 8 may use these flags:

- `--loop`
- `--interval SECONDS`
- `--speak`
- `--no-speak`

Do not add additional CLI flags in this phase.

## Interval Rules

The interval should be configurable in seconds.

Recommended rules:

- Default interval: `30` seconds
- Minimum interval: `5` seconds
- If the user provides an interval below `5`, clamp to `5` or show a clear validation message
- Tests should not actually sleep for long periods

## Cooldown Behavior

Cooldowns should be wired into loop mode so voice alerts do not repeat constantly.

Cooldowns are especially important when using static mock data because the same mock alerts will appear every loop iteration.

### Cooldown Scope

Cooldown state should be:

- In-memory only
- Runtime-only
- Reset when the program exits
- Keyed by symbol and alert event type

Do not add persistent cooldown storage in Phase 8.

### Single-Run Mode

Cooldowns are optional in single-run mode and should not change the default report behavior.

### Loop Mode

In loop mode:

- First eligible alert should be allowed
- Repeated alert within cooldown should be suppressed for voice playback
- Repeated alert after cooldown expires should be allowed again

The printed scanner report may still show all current scanner data each iteration.

## Voice Behavior

Voice playback should remain optional.

- Default: no speech
- `--speak`: speak eligible alerts
- `--no-speak`: do not speak

Tests must not require actual audio hardware, system voices, or `pyttsx3`.

Use fake or no-op speakers in tests.

## Output Behavior

The report should remain readable in loop mode.

Each iteration should clearly indicate that a new scan occurred.

Recommended output header:

```text
Market Sentry
Mock Scanner Report
Scan Time: 2026-06-16 14:30:00
```

A simple timestamp or iteration number is acceptable.

Avoid overbuilding terminal UI behavior in Phase 8.

Do not add curses, rich, Textual, Streamlit, or dashboard libraries.

## Suggested Implementation Shape

Codex may add helper functions such as:

```python
def run_once(...):
    ...


def run_loop(...):
    ...
```

Recommended separation:

- `main.py` handles CLI args and orchestration
- Scanner engine remains unchanged
- Alert generator remains unchanged unless cooldown integration requires a small adapter
- Speaker remains unchanged unless loop integration reveals a bug

## Testing Expectations

Tests should verify:

- Default CLI still runs once
- `--loop` triggers loop behavior
- Loop mode can be tested without sleeping in real time
- Interval validation works
- `Ctrl+C` / `KeyboardInterrupt` exits cleanly
- Cooldowns suppress repeated voice alerts in loop mode
- Cooldowns allow first alert
- Cooldowns allow repeated alert after cooldown expires
- `--speak` uses the speaker path in loop mode
- `--no-speak` does not use the speaker path
- Tests do not require real audio playback
- Tests do not require real APIs, credentials, network calls, WebSockets, dashboard, or trading behavior

## Definition of Done

Phase 8 is complete when:

- `python -m market_sentry` still runs once by default
- `python -m market_sentry --loop --interval 30` runs repeatedly with mock data
- Loop mode exits cleanly on `Ctrl+C`
- `--speak` works with loop mode using cooldowns
- Tests pass
- No real data integrations or trading behavior are added

## Future Phases

Potential future phases after Phase 8:

- Voice configuration
- First real market data provider
- CSV provider
- News/catalyst layer
- SEC filing layer
- Halt module
- Dashboard
