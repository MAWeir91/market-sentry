"""Configuration placeholders for Market Sentry Phase 0."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppConfig:
    """Minimal application configuration for scaffold validation."""

    environment: str = "development"
    log_level: str = "INFO"


def load_config() -> AppConfig:
    """Load safe local configuration values.

    This does not load market-data keys, brokerage credentials, or scanner settings.
    """

    return AppConfig(
        environment=os.getenv("MARKET_SENTRY_ENV", "development"),
        log_level=os.getenv("MARKET_SENTRY_LOG_LEVEL", "INFO"),
    )
