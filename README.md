# Market Sentry

Market Sentry is a personal-use low-float momentum scanner project with optional local voice alerts.

This repository currently includes the project scaffold, local development setup, scanner core, provider interface, mock-data command-line runner, voice-ready alert event display, optional local voice playback, and a mock polling loop.

## Safety Boundary

Market Sentry is not a trading bot. It does not place trades, does not execute orders, and does not connect to brokerage trading or order APIs.

The current runner uses local static mock data only. It displays voice-ready alert messages in the terminal and can optionally attempt local text-to-speech playback with `--speak`. It does not include real market-data integrations, dashboard UI, order execution, or any capability that can place trades.

## Roadmap Note

Real data provider implementation is not present yet. Phase 9A documents the planned provider strategy: Alpaca Market Data is the likely first price/volume/intraday provider, and Financial Modeling Prep is the likely first float/reference provider. The current runtime remains mock-data based until a future phase explicitly adds real-provider code.

Phase 9B adds a provider configuration skeleton for future phases. `mock` is still the default and only functional provider. Placeholder environment variables exist for future Alpaca/FMP configuration, but real provider implementation is not present yet and secrets should never be committed.

Runtime now uses the provider config/factory path internally. `MARKET_SENTRY_PROVIDER=mock` is supported and requires no credentials. `MARKET_SENTRY_PROVIDER=alpaca` is a placeholder and exits with a clear not-implemented message; real API implementation is still not present.

Phase 10A adds an offline Alpaca market-data skeleton for future request shaping and fixture parsing. Runtime still defaults to mock, real Alpaca integration is not active, and tests use fixtures only. Alpaca is not the planned source of float/reference data; future scanner-ready live candidates will likely require Alpaca market data plus FMP float/reference data. Do not commit credentials.

Phase 10B adds an offline FMP float/reference skeleton for future request shaping and fixture parsing. Runtime still defaults to mock, real FMP integration is not active, and tests use fixtures only. FMP is planned for float/reference data, not intraday market movement; future scanner-ready live candidates will likely compose Alpaca market data with FMP float/reference data. Do not commit credentials.

Phase 10C adds offline fixture-based candidate composition for future live-provider work. Runtime still defaults to mock, Alpaca and FMP are not active runtime providers, and composition currently uses offline fixtures/tests only. Future live scanner-ready candidates will likely require Alpaca market data plus FMP float/reference data. Do not commit credentials.

Phase 10D adds an offline fixture-composed provider for future-provider testing. The default runtime remains mock, but `MARKET_SENTRY_PROVIDER=fixture` can run static Alpaca/FMP-style fixtures through the composer without credentials or network calls. Phase 10E updates the report header so it reflects the selected provider, such as `Mock Scanner Report` or `Fixture Scanner Report`. Alpaca/FMP live providers are still not active. Trading/order functionality remains out of scope.

Phase 11A adds a generic HTTP transport skeleton for future live-provider phases. Current runtime modes still require no credentials: mock remains the default, fixture remains offline/static, and Alpaca/FMP live providers are not active. Do not commit secrets. Trading/order functionality remains out of scope.

Phase 11B adds an Alpaca snapshot fetcher skeleton behind the generic HTTP transport abstraction. Tests use fake transport responses only, runtime still defaults to mock, fixture remains offline/static, and Alpaca/FMP live providers are not active. Alpaca alone does not provide the float/reference data needed for scanner-ready low-float candidates. Do not commit credentials.

Phase 11C adds an FMP float/reference fetcher skeleton behind the generic HTTP transport abstraction. Tests use fake transport responses only, runtime still defaults to mock, fixture remains offline/static, and Alpaca/FMP live providers are not active. FMP provides float/reference data but is not a scanner-ready provider by itself. Do not commit credentials.

Phase 11D adds a live-data candidate builder skeleton for future provider phases. It combines Alpaca movement data, FMP float data, and explicit relative-volume input through offline/fake tests only. Runtime still defaults to mock, fixture remains offline/static, Alpaca/FMP live providers are not active, and relative volume must not be fabricated. Do not commit credentials.

Phase 11E adds an offline composed provider harness named `composed_fixture`. It combines static Alpaca-style movement data, static FMP-style float data, and explicit relative-volume data through the live candidate builder path. It is not a live provider, requires no credentials, and does not activate Alpaca or FMP runtime providers. Trading/order functionality remains out of scope.

Phase 11F adds a standard-library HTTP transport for future live-provider phases. It is not active at runtime, tests mock standard-library networking and make no real network calls, and current runtime modes still require no API credentials. Secrets should not be committed.

Phase 12A adds a strict config gate for a future live composed provider named `live_composed`. Live data is not active yet; the gate only validates that `MARKET_SENTRY_ALLOW_LIVE_DATA=true` or equivalent, a non-empty watchlist, Alpaca credentials, and an FMP key are present before future live mode could be considered. Runtime still defaults to mock, fixture and composed_fixture remain offline, Alpaca remains a placeholder, FMP remains inactive, and secrets should not be committed.

Phase 12B reserves `MARKET_SENTRY_PROVIDER=live_composed` with a clean placeholder/config-gate error path. The Phase 12A gate checks the allow-live flag, watchlist, Alpaca credentials, and FMP key, but even a passing gate still exits because live data remains disabled until a future phase. Current working runtime modes require no credentials, and trading/order functionality remains out of scope.

Phase 12C adds a dependency-injected live composed provider skeleton for future live-data phases. It is tested with fake components only, is not active at runtime, does not fabricate relative volume, and leaves `live_composed` on the reserved/gated placeholder path. Runtime still defaults to mock, fixture and composed_fixture remain offline, Alpaca remains a placeholder, FMP remains inactive as a standalone runtime provider, credentials should not be committed, and trading/order functionality remains out of scope.

Phase 12D adds a dry live-provider builder skeleton for future phases. It can assemble a `LiveComposedMarketDataProvider` from validated config and injected components, but it is not connected to runtime and `MARKET_SENTRY_PROVIDER=live_composed` remains the gated placeholder path. Runtime still defaults to mock, fixture and composed_fixture remain offline, Alpaca remains a placeholder, FMP remains inactive, relative volume must not be fabricated, secrets should not be committed, and trading/order functionality remains out of scope.

Phase 12E adds a relative-volume provider interface for future live-provider phases. The static/offline RVOL provider returns only explicit positive values, never fabricates missing RVOL, and can feed the dry live-provider builder without activating runtime. Runtime remains mock by default, fixture and composed_fixture remain offline, Alpaca remains a placeholder, `live_composed` remains gated, current working modes require no credentials, secrets should not be committed, and trading/order functionality remains out of scope.

Phase 12F adds live-readiness diagnostics for future live-provider phases. Diagnostics validate local preconditions only, do not call Alpaca, FMP, or any network API, and do not activate `live_composed`. Runtime remains mock by default, fixture and composed_fixture remain offline, Alpaca remains a placeholder, `live_composed` remains gated, RVOL source configuration must be explicit and is not fabricated, secrets should not be committed, and trading/order functionality remains out of scope.

Phase 12G exposes those diagnostics through `python -m market_sentry --live-readiness`. Add `--relative-volume-configured` only as an explicit local signal that RVOL source configuration exists; the command does not calculate RVOL, call Alpaca/FMP or any network API, activate `live_composed`, build providers, or render the scanner report.

Phase 13A documents the future `live_composed` activation plan only. Real activation remains blocked until a later approved phase adds provider factory wiring, read-only HTTP wiring, and an explicit real relative-volume source; runtime still defaults to mock, `live_composed` remains a gated placeholder, and no live provider or network behavior is active.

Phase 13B documents the future real relative-volume strategy only. The recommended path is watchlist-only historical-volume calculation through an offline/testable skeleton before any live activation; static RVOL remains testing-only, provider-supplied RVOL is deferred, and RVOL must never be fabricated.

Phase 13C adds an offline relative-volume calculation skeleton. It calculates RVOL only from supplied current-volume and historical-average-volume inputs, does not fetch data, does not activate live mode, and does not fabricate missing or invalid RVOL. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 13D adds an offline historical-volume input adapter. It calculates historical averages only from supplied completed daily bars, does not fetch data, is not time-of-day normalized, does not unblock production live activation, and does not fabricate missing or invalid history. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 13E adds an offline time-of-day-normalized RVOL calculation skeleton. It uses caller-supplied current cumulative volume and historical cumulative observations at the same bucket, does not fetch market data, does not activate live mode, and does not handle market-calendar/session normalization. Missing or invalid input is not fabricated; `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 13F adds an offline intraday bucket-construction adapter. It sums caller-supplied validated intraday bars through a caller-supplied cutoff, builds Phase 13E inputs without calculating final RVOL, does not fetch data or infer calendar/session/time-zone rules, and does not activate live mode. Missing or invalid inputs are never fabricated; `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 13G adds an offline end-to-end intraday RVOL harness. It composes caller-supplied fixture series through the existing Phase 13F and 13E modules, does not fetch market data, infer calendar/session behavior, or activate live mode, and does not fabricate missing RVOL data. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 13H adds an offline intraday RVOL fixture provider. It exposes Phase 13G fixture-harness results through the existing relative-volume provider contract, returns only successful requested RVOL values, never fabricates missing values, and does not fetch data, register a runtime provider, or activate live mode. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 13I adds an offline intraday RVOL candidate-composition harness. It feeds explicit Phase 13H RVOL mappings into the existing candidate builder with local fixture sources, exposes candidates and skipped-symbol diagnostics without fetching data or activating live mode, and does not fabricate RVOL, snapshot, float, or candidate data. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 13J adds a deterministic offline intraday RVOL scenario fixture catalog. It supplies explicit reusable test scenarios for the existing offline RVOL-to-candidate path, does not fetch data, register a runtime provider, infer market sessions, or activate live mode. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 14A adds an injected Alpaca historical intraday-bars fetcher skeleton. It returns one raw, inspectable response page for explicitly supplied symbols, surfaces pagination tokens without following them automatically, and does not build RVOL inputs, fetch a watchlist, register a runtime provider, or activate live mode. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 14B adds a strict offline adapter from raw Alpaca historical-bar mappings to Phase 13F intraday input models. Caller-supplied metadata determines symbol, session ID, bucket, and cutoff; the adapter parses timestamps but does not fetch data, infer sessions, convert time zones, validate downstream volume, calculate RVOL, register a runtime provider, or activate live mode. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 14C defines the explicit historical session and bucket metadata policy required before real raw bars can form a time-of-day RVOL baseline. It does not infer calendars, sessions, early closes, halts, time zones, cutoff metadata, or page completeness, and adds no runtime provider, network behavior, RVOL calculation, or live activation. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 14D adds an offline historical-session assembler that applies explicit caller session metadata to a raw historical-bars page before delegating eligible session bars to the Phase 14B adapter. It excludes incomplete page collections and incomplete or invalid sessions, does not infer calendars, and adds no runtime provider, network behavior, pagination, candidate composition, or live activation. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 14E adds an offline historical baseline composer. It evaluates eligible Phase 14D session series through the existing Phase 13F cumulative-volume validator and produces ordered historical cumulative-volume observations for a later Phase 13E TOD RVOL calculation. It does not build a current-series input, calculate final RVOL, fetch data, infer calendars, register a runtime provider, or activate live mode. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 14F adds an offline current-session TOD RVOL composer. It combines a successful Phase 14E baseline artifact with one explicit current intraday series, reuses Phase 13F for current cumulative volume, and reuses Phase 13E for the final time-of-day RVOL calculation. It does not fetch data, infer sessions or calendars, register a runtime provider, or activate live mode. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 14G adds a thin offline end-to-end historical-to-TOD RVOL harness. It orchestrates the existing Phase 14D historical-session assembly, Phase 14E baseline composition, and Phase 14F final TOD RVOL composition layers while retaining all stage artifacts and diagnostics for one explicit input run. It does not fetch data, paginate, infer calendars, register a runtime provider, or activate live mode. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 14H adds a deterministic offline scenario fixture catalog for the existing Phase 14G historical-to-TOD RVOL harness. Named raw-input scenarios exercise valid history, insufficient or incomplete history, historical and current validation failures, identity mismatch, and a final Phase 13E validation failure. It does not fetch data, register a runtime provider, or activate live mode. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 14I adds an offline session-metadata manifest adapter. It validates explicit caller-supplied historical session records and emits ordered Phase 14G-compatible metadata objects with per-record diagnostics. It does not inspect raw bars, infer calendars or sessions, fetch data, register a runtime provider, or activate live mode. `live_composed` remains reserved/inactive, and trading/order functionality remains out of scope.

Phase 14J adds an offline coordinator that runs the Phase 14I session-manifest adapter and Phase 14G historical-to-TOD RVOL harness in sequence. It preserves both artifacts and distinguishes complete, partial-manifest, manifest-failure, and harness-failure outcomes. It does not fetch data, register a runtime provider, activate live mode, or add trading/order functionality. `live_composed` remains reserved/inactive.

Phase 14K adds a deterministic offline workflow scenario catalog for the existing Phase 14I to Phase 14J to Phase 14G path. Named raw-input scenarios exercise complete, partial, invalid-manifest, duplicate-manifest, historical-page, historical-cutoff, current-session, identity-mismatch, and final TOD-RVOL validation outcomes. It does not fetch data, register a runtime provider, activate live mode, or add trading/order behavior. `live_composed` remains reserved/inactive.

Phase 18A activates `live_composed` for one-shot scanner runs only. A run requires a configured watchlist, Alpaca credentials, an FMP key, `MARKET_SENTRY_ALLOW_LIVE_DATA=true`, and an explicit local RVOL artifact manifest whose metadata/bundle pair preflights successfully for every watchlist symbol before any live transport is constructed. The scanner may then request live Alpaca snapshots and live FMP float data, while RVOL comes from explicit local artifacts and is not refreshed by the scanner command. Loop mode remains unavailable for `live_composed`, and trading/order functionality remains out of scope.

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

Run the offline fixture provider with:

```powershell
$env:MARKET_SENTRY_PROVIDER="fixture"
python -m market_sentry
Remove-Item Env:MARKET_SENTRY_PROVIDER
```

Run the offline composed provider harness with:

```powershell
$env:MARKET_SENTRY_PROVIDER="composed_fixture"
python -m market_sentry
Remove-Item Env:MARKET_SENTRY_PROVIDER
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

Run a manual local JSON preflight with:

```powershell
python -m market_sentry --local-json-preflight <PATH>
```

This reads only the explicit local JSON file path and runs it through a fixed offline RVOL diagnostic profile. It does not discover files, activate providers, scan candidates, call APIs, or play voice alerts. It returns 0 only for a complete end-to-end OK result; returned nested diagnostics or expected source errors return nonzero. The command is not live market analysis and does not execute trades.

Optional local report export:

```powershell
python -m market_sentry --local-json-preflight <INPUT_PATH> --local-json-preflight-report <OUTPUT_PATH>
```

The optional output path receives the exact same UTF-8 report shown in the terminal. The command reads only `INPUT_PATH` and writes only `OUTPUT_PATH`. It does not create parent directories, discover files, activate providers, scan candidates, call APIs, or play voice alerts. Use distinct input and output paths.

Run a manual two-path local bundle preflight with:

```powershell
python -m market_sentry --local-json-bundle-preflight <METADATA_PATH> <BUNDLE_PATH>
```

Optional two-path report export:

```powershell
python -m market_sentry --local-json-bundle-preflight <METADATA_PATH> <BUNDLE_PATH> --local-json-bundle-preflight-report <REPORT_PATH>
```

The metadata path is first and the historical RVOL bundle path is second. This command reads only those explicit local input paths and optionally writes only the explicit report path. It does not create parent directories, discover files, activate providers, scan candidates, call APIs, or play voice alerts. Use a report path distinct from both input paths. This is offline diagnostics only, not live analysis or trading behavior.

Run a manual one-shot Alpaca RVOL capture preflight with:

```powershell
python -m market_sentry --manual-alpaca-rvol-capture <METADATA_INPUT_PATH> <METADATA_OUTPUT_PATH> <BUNDLE_OUTPUT_PATH> --manual-alpaca-rvol-capture-confirm-live-data --manual-alpaca-rvol-capture-symbol <SYMBOL> --manual-alpaca-rvol-capture-historical-start <ISO_TIMESTAMP> --manual-alpaca-rvol-capture-historical-end <ISO_TIMESTAMP> --manual-alpaca-rvol-capture-historical-max-pages <INTEGER> --manual-alpaca-rvol-capture-current-start <ISO_TIMESTAMP> --manual-alpaca-rvol-capture-current-end <ISO_TIMESTAMP> --manual-alpaca-rvol-capture-current-max-pages <INTEGER> --manual-alpaca-rvol-capture-current-session-id <SESSION_ID> --manual-alpaca-rvol-capture-bucket <BUCKET> --manual-alpaca-rvol-capture-cutoff <ISO_TIMESTAMP> --manual-alpaca-rvol-capture-minimum-historical-sessions <INTEGER>
```

This command may call Alpaca only when both `--manual-alpaca-rvol-capture-confirm-live-data` and `MARKET_SENTRY_ALLOW_LIVE_DATA` are enabled. It requires Alpaca credentials, but it does not require FMP, `live_composed`, or a watchlist. It requires a caller-supplied metadata seed file and writes only the explicit metadata, bundle, and optional report artifact paths. It is not scanner activation and does not trade.

Run the live-readiness preflight without activating live data:

```powershell
python -m market_sentry --live-readiness
```

`--live-readiness` performs local checks only. It does not call Alpaca, FMP, or any network API, does not read or preflight RVOL artifacts, does not activate `live_composed`, and does not render the scanner report. `live_composed` is available only for one-shot scanner runs with explicit local RVOL artifacts; Alpaca remains a placeholder for standalone provider selection, and trading/order functionality is out of scope.

Run a local preflight with placeholder values:

```powershell
$env:MARKET_SENTRY_PROVIDER="live_composed"
$env:MARKET_SENTRY_ALLOW_LIVE_DATA="true"
$env:MARKET_SENTRY_WATCHLIST="AAPL"
$env:MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH="C:\market-sentry\artifacts\rvol-artifacts.json"
$env:ALPACA_API_KEY="placeholder-key"
$env:ALPACA_API_SECRET="placeholder-secret"
$env:FMP_API_KEY="placeholder-fmp-key"
python -m market_sentry --live-readiness --relative-volume-configured
Remove-Item Env:MARKET_SENTRY_PROVIDER
Remove-Item Env:MARKET_SENTRY_ALLOW_LIVE_DATA
Remove-Item Env:MARKET_SENTRY_WATCHLIST
Remove-Item Env:MARKET_SENTRY_RVOL_ARTIFACT_MANIFEST_PATH
Remove-Item Env:ALPACA_API_KEY
Remove-Item Env:ALPACA_API_SECRET
Remove-Item Env:FMP_API_KEY
```

`--relative-volume-configured` is only an explicit local signal that an RVOL source has been configured outside the CLI. RVOL is not calculated, fetched, inferred, or fabricated.
