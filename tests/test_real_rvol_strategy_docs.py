from pathlib import Path


PLAN_PATH = Path("docs/30_REAL_RVOL_SOURCE_STRATEGY.md")


def test_real_rvol_strategy_documents_phase_13b_boundaries() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "Phase 13B is a strategy/data-contract phase only.",
        "This phase does not implement an RVOL source",
        "calculate RVOL from watchlist-only historical volume data",
        "offline/testable RVOL calculation skeleton",
        "Static/local RVOL is not production live activation",
        "Provider-supplied RVOL remains deferred",
        "RVOL must not be fabricated",
        "RVOL must not be inferred from unrelated data",
        "Missing RVOL source blocks real live activation",
        "skip that symbol once a real source exists",
        "watchlist-only",
        "MARKET_SENTRY_WATCHLIST",
        "RelativeVolumeProvider",
        "get_relative_volumes",
        "secret-safe",
        "No provider factory activation",
        "No trading/order behavior",
    ]

    for phrase in required_phrases:
        assert phrase in plan


def test_real_rvol_strategy_documents_valid_invalid_and_failure_rules() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "Valid RVOL must be",
        "explicit",
        "numeric",
        "finite",
        "positive",
        "associated with a normalized symbol",
        "Invalid RVOL includes",
        "missing value",
        "zero",
        "negative value",
        "NaN",
        "infinity",
        "non-numeric value",
        "fabricated default",
        "no RVOL source configured",
        "missing symbol from RVOL source",
        "invalid current volume",
        "missing historical volume data",
        "invalid historical average volume",
        "insufficient lookback data",
        "provider timeout/status/network failure",
        "all RVOL results invalid",
        "partial RVOL results invalid",
    ]

    for phrase in required_phrases:
        assert phrase in plan
