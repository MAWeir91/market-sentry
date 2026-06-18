from pathlib import Path


POLICY_DOC = Path("docs/41_HISTORICAL_SESSION_AND_BUCKET_METADATA_POLICY.md")


def read_policy_doc() -> str:
    return POLICY_DOC.read_text(encoding="utf-8")


def assert_contains_all(text: str, phrases: tuple[str, ...]) -> None:
    lowered = text.lower()
    for phrase in phrases:
        assert phrase.lower() in lowered


def test_historical_session_metadata_policy_document_exists() -> None:
    assert POLICY_DOC.exists()


def test_policy_locks_required_session_bucket_and_cutoff_clauses() -> None:
    text = read_policy_doc()

    assert_contains_all(
        text,
        (
            "caller-supplied metadata contract",
            "symbol/session ID/bucket normalization behavior",
            "timezone-aware timestamps with exact tzinfo compatibility",
            "half-open session window",
            "[session_start_timestamp, session_end_timestamp)",
            "session_start_timestamp <= cutoff_timestamp < session_end_timestamp",
            "opaque caller-supplied label",
            "same exact trimmed bucket label",
            "20 eligible historical sessions",
        ),
    )


def test_policy_locks_completeness_exception_and_current_session_rules() -> None:
    text = read_policy_doc()

    assert_contains_all(
        text,
        (
            "partial or uncertain sessions are **not eligible by default**",
            "next_page_token is non-null",
            "response collection is incomplete for baseline eligibility",
            "next_page_token is null",
            "this alone does not prove calendar/session completeness",
            "unknown or exceptional session",
            "not eligible for a historical RVOL baseline",
            "current session must be explicit and must not appear in its own historical baseline",
            "current session_id == any historical session_id",
        ),
    )


def test_policy_locks_watchlist_only_and_diagnostic_ownership_rules() -> None:
    text = read_policy_doc()

    assert_contains_all(
        text,
        (
            "Future live callers may supply only symbols explicitly listed in `MARKET_SENTRY_WATCHLIST`",
            "lower-level diagnostic ownership",
            "Phase 14A",
            "Phase 14B",
            "future session assembler",
            "Phase 13F",
            "Phase 13E",
            "must not replace lower-level diagnostics with generic errors",
        ),
    )


def test_policy_explicitly_does_not_infer_market_metadata() -> None:
    text = read_policy_doc()

    assert_contains_all(
        text,
        (
            "must not infer early closes, halts, or exceptional sessions",
            "does not infer calendars, sessions, regular hours, holidays, early closes, halts, time zones, cutoff metadata, or page completeness",
            "No code may derive a session ID from a raw timestamp by itself",
            "must not parse it as a clock time",
            "no time-zone conversion or normalization",
            "null next_page_token does not prove calendar/session completeness",
            "regular hours",
            "holidays",
            "bucket labels",
            "cutoff timestamps",
            "page completeness",
        ),
    )


def test_phase_14c_remains_documentation_only() -> None:
    text = read_policy_doc()

    assert_contains_all(
        text,
        (
            "documentation and contract-test phase only",
            "adds no runtime or data-processing implementation",
            "does **not** implement the future assembly layer",
            "This is a future model example only. Phase 14C does not create it in code.",
            "no code or enum is added in Phase 14C",
            "raw-bar parsing or adaptation code",
            "session-assembly code",
            "RVOL calculations",
            "candidate composition",
            "order APIs, order placement, trade execution, or trading recommendations",
            "`live_composed` remains gated and reserved/inactive",
        ),
    )
