from pathlib import Path


PLAN_PATH = Path("docs/29_LIVE_COMPOSED_ACTIVATION_PLAN.md")


def test_live_activation_plan_covers_phase_13a_boundaries() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "Phase 13A is documentation/specification only.",
        "no runtime activation",
        "no provider factory activation",
        "`live_composed` remains a gated, reserved placeholder",
        "config gate",
        "local preflight guidance",
        "StdlibHttpTransport",
        "AlpacaSnapshotFetcher",
        "FMPFloatFetcher",
        "explicit RVOL source",
        "Real `live_composed` activation remains blocked until a real explicit RVOL source exists.",
        "Relative volume must not be fabricated",
        "watchlist-only",
        "MARKET_SENTRY_WATCHLIST",
        "GET/read-only market/reference data only",
        "no trading/order behavior",
        "no order endpoints",
        "secret-safe",
        "all-candidates-skipped",
        "Rollback And Safe Disable",
    ]

    for phrase in required_phrases:
        assert phrase in plan


def test_live_activation_plan_defines_future_failure_modes() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    failure_modes = [
        "Gate failure",
        "Missing watchlist",
        "Missing credentials",
        "Live provider still inactive",
        "Alpaca request construction failure",
        "Alpaca HTTP/status/timeout failure",
        "FMP HTTP/status/timeout failure",
        "Missing RVOL source",
        "Alpaca data missing",
        "FMP float missing",
        "Invalid price/volume/float",
        "Partial candidates skipped",
        "All candidates skipped",
    ]

    for failure_mode in failure_modes:
        assert failure_mode in plan
