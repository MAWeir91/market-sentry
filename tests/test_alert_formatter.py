from market_sentry.alerts import AlertEventType, format_alert_message
from market_sentry.scanner.engine import evaluate_candidate
from market_sentry.scanner.models import StockCandidate


def test_formatter_produces_voice_friendly_message() -> None:
    scanner_result = evaluate_candidate(
        StockCandidate(
            symbol="VOICE",
            price=5.50,
            float_shares=4_500_000,
            daily_gain_percent=58.0,
            relative_volume=6.2,
            daily_volume=2_600_000,
            high_of_day=5.60,
            change_15m_pct=7.4,
        )
    )

    message = format_alert_message(
        scanner_result,
        AlertEventType.TIER_3_MAJOR_RUNNER,
    )

    assert message == (
        "VOICE major runner. Up 58.0 percent with 6.2 relative volume. "
        "Float 4.5 million. Rotation 0.6 times float. "
        "Fifteen-minute change positive 7.4 percent. Score 52.1."
    )
    assert "%" not in message
    assert "RVOL" not in message


def test_formatter_creates_high_score_message() -> None:
    scanner_result = evaluate_candidate(
        StockCandidate(
            symbol="XTRM",
            price=11.40,
            float_shares=1_300_000,
            daily_gain_percent=118.0,
            relative_volume=12.5,
            daily_volume=6_400_000,
            high_of_day=11.55,
            change_15m_pct=14.8,
        )
    )

    message = format_alert_message(scanner_result, AlertEventType.HIGH_SCORE)

    assert "XTRM high scanner score." in message
    assert "Score 96.1." in message
    assert "118.0 percent" in message
    assert "12.5 relative volume" in message
    assert "Rotation 4.9 times float." in message
    assert "Fifteen-minute change positive 14.8 percent." in message


def test_formatter_avoids_trading_advice_language() -> None:
    scanner_result = evaluate_candidate(
        StockCandidate(
            symbol="SAFE",
            price=8.00,
            float_shares=1_200_000,
            daily_gain_percent=101.0,
            relative_volume=11.0,
            daily_volume=5_500_000,
        )
    )
    banned_terms = {"buy", "sell", "enter", "exit", "guaranteed", "safe trade"}

    for event_type in AlertEventType:
        message = format_alert_message(scanner_result, event_type).lower()
        assert not any(term in message for term in banned_terms)
