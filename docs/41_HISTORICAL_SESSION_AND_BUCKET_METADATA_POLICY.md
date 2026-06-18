# Phase 14C — Historical Session and Bucket Metadata Policy

## Status

**Planned.** This document defines Phase 14C only.

Phase 14A fetches one raw historical Alpaca bars page through an injected transport. Phase 14B converts a raw page symbol plus explicit metadata into a Phase 13F-compatible `IntradayVolumeSeriesInput`.

Before a future phase can assemble real historical sessions into the completed time-of-day RVOL pipeline, Market Sentry must explicitly define the metadata policy for:

```text
session identity
session boundaries
bucket labels
cutoff timestamps
historical-session eligibility
partial pages and incomplete sessions
early closes and halts
```

Phase 14C is a **documentation and contract-test phase only**. It adds no runtime or data-processing implementation.

---

## Goal

Define a strict, caller-supplied metadata contract for turning raw timestamped bars into comparable historical sessions without silently inferring an exchange calendar or session behavior.

The intended future path is:

```text
raw historical pages
+ explicit session metadata manifest
→ future session-series assembly layer
→ Phase 14B raw bar adapter
→ Phase 13F cutoff and volume validation
→ Phase 13E same-bucket historical RVOL baseline
```

This document intentionally does **not** implement the future assembly layer.

---

## Core Policy

### 1. Session metadata is explicit

A future historical-session caller must explicitly provide each session’s metadata.

At minimum, each historical session record must provide:

```text
symbol
session_id
bucket
session_start_timestamp
session_end_timestamp
cutoff_timestamp
is_complete
```

Recommended future shape:

```python
@dataclass(frozen=True)
class HistoricalIntradaySessionMetadata:
    symbol: str
    session_id: str
    bucket: str
    session_start_timestamp: datetime
    session_end_timestamp: datetime
    cutoff_timestamp: datetime
    is_complete: bool
```

This is a future model example only. Phase 14C does not create it in code.

The session metadata manifest is the authority for session identity and boundaries. No code may derive a session ID from a raw timestamp by itself.

---

### 2. Metadata normalization rules

Future code must use the existing project conventions:

```text
symbol:
  trim surrounding whitespace
  uppercase
  blank symbol is invalid

session_id:
  non-empty string after trimming
  preserve resulting case/content exactly
  do not parse as date or timestamp

bucket:
  non-empty string after trimming
  preserve resulting label exactly
  do not parse as a time

timestamps:
  datetime only
  timezone-aware only
  no time-zone conversion or normalization
```

All timestamps within one session record must have exactly equal `tzinfo` values:

```text
session_start_timestamp.tzinfo
session_end_timestamp.tzinfo
cutoff_timestamp.tzinfo
```

This aligns with the strict exact-`tzinfo` compatibility already used by Phase 14B and Phase 13F.

---

### 3. Session window convention

A future session metadata record defines a half-open session window:

```text
[session_start_timestamp, session_end_timestamp)
```

A raw bar belongs to that session only when:

```text
session_start_timestamp <= bar.timestamp < session_end_timestamp
```

The cutoff must satisfy:

```text
session_start_timestamp <= cutoff_timestamp < session_end_timestamp
```

The existing Phase 13F code remains responsible for summing valid adapted bars where:

```text
bar.timestamp <= cutoff_timestamp
```

A future assembly layer must not alter, round, or infer a cutoff timestamp.

---

### 4. Bucket convention

The `bucket` is an **opaque caller-supplied label** attached to a specific cutoff timestamp.

Examples of possible caller labels:

```text
09:35
opening_5m
midday_checkpoint
```

Phase 14C does not choose a universal bucket string format. Future code must treat the trimmed label as exact text and must not parse it as a clock time.

To create a valid Phase 13E comparison:

```text
current and historical inputs must use the same exact trimmed bucket label
```

A similar-looking label is not a match:

```text
09:35 != 9:35
opening_5m != opening-5m
```

No nearest-bucket substitution, rounding, or fallback is allowed.

---

### 5. Historical session eligibility

A historical session may be used for a time-of-day RVOL baseline only when all of the following are true:

```text
- session metadata is valid;
- is_complete is True;
- the source response/page set is known to be complete for the requested query;
- the session has an explicit cutoff timestamp;
- the same exact bucket label is supplied as the current input;
- the session ID is distinct from the current session ID;
- the session data reaches the requested cutoff timestamp;
- the future adapter/Phase 13F validation succeeds.
```

The completed Phase 13E default baseline requires at least:

```text
20 eligible historical sessions
```

A future implementation must not lower this default internally to make a sparse dataset appear usable.

---

### 6. Partial-session policy

Partial or uncertain sessions are **not eligible by default**.

Examples:

```text
- request response has a non-null next_page_token;
- retrieved pages do not cover the intended query completely;
- metadata says is_complete is False;
- no raw bar reaches the caller-supplied cutoff;
- caller cannot establish session coverage confidently;
- source data is known to begin after session_start_timestamp;
- source data is known to end before cutoff_timestamp.
```

A future assembly layer must expose a stable, inspectable skip or failure diagnostic rather than fabricate a partial baseline.

No interpolation, volume extrapolation, prior-session substitution, or fallback to daily average is allowed.

---

### 7. Pagination-completion policy

Phase 14A fetches one page only and surfaces `next_page_token`. It does not establish that a query is complete.

Future page retrieval/assembly policy must follow these rules:

```text
next_page_token is non-null
→ response collection is incomplete for baseline eligibility
→ do not mark any affected session as complete

next_page_token is null
→ this response page is terminal for that request
→ this alone does not prove calendar/session completeness
→ caller metadata still controls session eligibility
```

A later explicitly approved pagination phase may retrieve additional pages. It must preserve raw page order and retain an inspectable request/page trail. It must not silently discard incomplete pages.

---

### 8. Early-close, halt, and exceptional-session policy

Market Sentry must not infer early closes, halts, or exceptional sessions from raw bars.

Default rule:

```text
unknown or exceptional session
→ not eligible for a historical RVOL baseline
```

A later caller may include an exceptional session only when it explicitly supplies:

```text
- valid session metadata;
- valid session_start/session_end/cutoff timestamps;
- is_complete=True;
- data coverage through the cutoff;
- the exact same bucket label as the current input.
```

If any of those conditions are absent, the session is excluded rather than approximated.

This prevents a halt, early close, or sparse data period from being treated as a normal baseline session.

---

### 9. Current-session policy

The current session must be explicit and must not appear in its own historical baseline.

Future code must reject:

```text
current session_id == any historical session_id
```

after session-ID trimming only. Session ID comparisons are case-sensitive after trimming, matching Phase 13E’s existing policy.

---

### 10. Multiple-symbol and watchlist policy

Future live callers may supply only symbols explicitly listed in `MARKET_SENTRY_WATCHLIST`.

This policy document does not add a watchlist lookup, a provider, a screener, or broad-market discovery.

Per-symbol historical data must remain isolated:

```text
bars from one symbol must never be assigned to another symbol’s session metadata
```

---

### 11. Data-quality and diagnostics policy

A future implementation must preserve diagnostic ownership:

```text
Phase 14A
  request/response/page parsing diagnostics

Phase 14B
  raw structural and timestamp-adaptation diagnostics

future session assembler
  metadata, page-completion, membership, and session-eligibility diagnostics

Phase 13F
  ordering, duplicate-timestamp, cutoff, and volume diagnostics

Phase 13E
  same-bucket historical baseline and final TOD RVOL diagnostics
```

A later layer must not replace lower-level diagnostics with generic errors or erase the reason a session was excluded.

Recommended future status families:

```text
INVALID_SESSION_METADATA
MISMATCHED_SESSION_TIMEZONE
INVALID_SESSION_WINDOW
INVALID_CUTOFF_OUTSIDE_SESSION
INCOMPLETE_PAGE_COLLECTION
INCOMPLETE_SESSION
CUT_OFF_NOT_REACHED
CURRENT_SESSION_IN_HISTORY
DUPLICATE_HISTORICAL_SESSION_ID
MISMATCHED_HISTORICAL_BUCKET
INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
```

These are documentation-level policy names only; no code or enum is added in Phase 14C.

---

## Out of Scope

Phase 14C must not add:

```text
runtime activation
provider-factory registration or provider-selection changes
new MARKET_SENTRY_PROVIDER values
CLI flags, reports, or polling changes
HTTP requests, fetchers, pagination, retries, backoff, caching, streaming, or WebSockets
raw-bar parsing or adaptation code
session-assembly code
calendar provider integration
holiday / early-close / halt provider integration
time-zone conversion
RVOL calculations
candidate composition
scanner scoring
alerts or voice changes
environment/config reads
persistent storage
order APIs, order placement, trade execution, or trading recommendations
```

`live_composed` remains gated and reserved/inactive.

---

## Expected Files

Create:

```text
docs/41_HISTORICAL_SESSION_AND_BUCKET_METADATA_POLICY.md
tests/test_historical_session_metadata_policy_docs.py
```

Modify only if useful:

```text
README.md
```

The test is a lightweight documentation contract test. It should verify the required policy clauses are present and that no executable runtime module is introduced.

---

## Documentation Contract Test Requirements

The test must verify that the policy document explicitly covers:

```text
- caller-supplied session metadata;
- symbol/session ID/bucket normalization behavior;
- timezone-aware timestamps with exact tzinfo compatibility;
- half-open session window;
- cutoff inside the session window;
- opaque exact bucket labels;
- at least 20 eligible historical sessions;
- partial/incomplete sessions excluded by default;
- non-null next_page_token means page collection is incomplete;
- null next_page_token does not prove calendar/session completeness;
- exceptional/early-close/halt sessions excluded by default unless explicitly complete;
- current session excluded from historical baseline;
- watchlist-only future caller boundary;
- lower-level diagnostic ownership;
- no runtime activation or implementation added in this phase.
```

The test must not read environment variables, use network access, instantiate providers/transports, or call scanner code.

---

## README Note

If updated, keep it brief:

```text
Phase 14C defines the explicit historical session and bucket metadata policy needed before real raw bars can form a time-of-day RVOL baseline.
It does not infer calendars, sessions, regular hours, holidays, early closes, halts, time zones, cutoff metadata, or page completeness.
It adds no runtime provider, network behavior, RVOL calculation, or live activation.
live_composed remains reserved/inactive.
Trading/order functionality remains out of scope.
```

---

## Acceptance Criteria

Phase 14C is complete when:

```text
- session/bucket/cutoff/completeness policy is documented;
- ambiguous calendar behavior is explicitly excluded rather than inferred;
- a documentation contract test locks the policy in place;
- no executable data-processing or runtime activation code is added;
- the full project suite remains green.
```
