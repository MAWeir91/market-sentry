"""Configuration for Market Sentry runtime and provider planning."""

from dataclasses import dataclass, field
from typing import Mapping
import os


def parse_watchlist(value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated watchlist into normalized symbols."""

    if value is None:
        return ()
    return tuple(
        symbol
        for symbol in (part.strip().upper() for part in value.split(","))
        if symbol
    )


@dataclass(frozen=True)
class AppConfig:
    """Application configuration with future provider placeholders."""

    environment: str = "development"
    log_level: str = "INFO"
    provider: str = "mock"
    watchlist: tuple[str, ...] = ()
    alpaca_api_key: str | None = field(default=None, repr=False)
    alpaca_api_secret: str | None = field(default=None, repr=False)
    alpaca_data_feed: str | None = None
    fmp_api_key: str | None = field(default=None, repr=False)


def _optional_env(environ: Mapping[str, str], name: str) -> str | None:
    value = environ.get(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def load_config(environ: Mapping[str, str] | None = None) -> AppConfig:
    """Load local configuration values without external validation."""

    env = environ if environ is not None else os.environ
    return AppConfig(
        environment=env.get("MARKET_SENTRY_ENV", "development").strip()
        or "development",
        log_level=env.get("MARKET_SENTRY_LOG_LEVEL", "INFO").strip() or "INFO",
        provider=env.get("MARKET_SENTRY_PROVIDER", "mock").strip().lower() or "mock",
        watchlist=parse_watchlist(env.get("MARKET_SENTRY_WATCHLIST")),
        alpaca_api_key=_optional_env(env, "ALPACA_API_KEY"),
        alpaca_api_secret=_optional_env(env, "ALPACA_API_SECRET"),
        alpaca_data_feed=_optional_env(env, "ALPACA_DATA_FEED"),
        fmp_api_key=_optional_env(env, "FMP_API_KEY"),
    )
