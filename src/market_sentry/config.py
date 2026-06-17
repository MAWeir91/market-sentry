"""Configuration for Market Sentry runtime and provider planning."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
import os

LIVE_COMPOSED_PROVIDER = "live_composed"
LIVE_DATA_TRUTHY_VALUES = {"1", "true", "yes", "on"}


def parse_watchlist(value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated watchlist into normalized symbols."""

    if value is None:
        return ()
    return tuple(
        symbol
        for symbol in (part.strip().upper() for part in value.split(","))
        if symbol
    )


def parse_allow_live_data(value: str | None) -> bool:
    """Return whether live data was explicitly enabled."""

    if value is None:
        return False
    return value.strip().lower() in LIVE_DATA_TRUTHY_VALUES


class LiveProviderGateFailure(str, Enum):
    """Stable reasons the future live provider gate did not pass."""

    PROVIDER_NOT_LIVE_COMPOSED = "PROVIDER_NOT_LIVE_COMPOSED"
    LIVE_DATA_NOT_ALLOWED = "LIVE_DATA_NOT_ALLOWED"
    MISSING_WATCHLIST = "MISSING_WATCHLIST"
    MISSING_ALPACA_API_KEY = "MISSING_ALPACA_API_KEY"
    MISSING_ALPACA_API_SECRET = "MISSING_ALPACA_API_SECRET"
    MISSING_FMP_API_KEY = "MISSING_FMP_API_KEY"


@dataclass(frozen=True)
class LiveProviderGateResult:
    """Inspectable result for future live composed provider validation."""

    allowed: bool
    failure_reasons: tuple[LiveProviderGateFailure, ...]

    @property
    def message(self) -> str:
        """Return a secret-safe user-facing gate status message."""

        if self.allowed:
            return "Live composed provider gate passed."
        reasons = ", ".join(reason.value for reason in self.failure_reasons)
        return f"Live composed provider gate failed: {reasons}."


@dataclass(frozen=True)
class AppConfig:
    """Application configuration with future provider placeholders."""

    environment: str = "development"
    log_level: str = "INFO"
    provider: str = "mock"
    watchlist: tuple[str, ...] = ()
    allow_live_data: bool = False
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
        allow_live_data=parse_allow_live_data(env.get("MARKET_SENTRY_ALLOW_LIVE_DATA")),
        alpaca_api_key=_optional_env(env, "ALPACA_API_KEY"),
        alpaca_api_secret=_optional_env(env, "ALPACA_API_SECRET"),
        alpaca_data_feed=_optional_env(env, "ALPACA_DATA_FEED"),
        fmp_api_key=_optional_env(env, "FMP_API_KEY"),
    )


def validate_live_provider_gate(config: AppConfig) -> LiveProviderGateResult:
    """Validate future live composed provider safety requirements."""

    failures: list[LiveProviderGateFailure] = []

    if config.provider != LIVE_COMPOSED_PROVIDER:
        failures.append(LiveProviderGateFailure.PROVIDER_NOT_LIVE_COMPOSED)
    if not config.allow_live_data:
        failures.append(LiveProviderGateFailure.LIVE_DATA_NOT_ALLOWED)
    if not config.watchlist:
        failures.append(LiveProviderGateFailure.MISSING_WATCHLIST)
    if not config.alpaca_api_key:
        failures.append(LiveProviderGateFailure.MISSING_ALPACA_API_KEY)
    if not config.alpaca_api_secret:
        failures.append(LiveProviderGateFailure.MISSING_ALPACA_API_SECRET)
    if not config.fmp_api_key:
        failures.append(LiveProviderGateFailure.MISSING_FMP_API_KEY)

    return LiveProviderGateResult(
        allowed=not failures,
        failure_reasons=tuple(failures),
    )
