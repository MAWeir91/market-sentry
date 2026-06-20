"""Live-readiness diagnostics for future live-provider phases.

Diagnostics inspect local configuration only. They do not call APIs, build
transports, or activate the reserved live provider.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from market_sentry.config import LIVE_COMPOSED_PROVIDER, AppConfig


class LiveReadinessStatus(str, Enum):
    """Overall diagnostic status for future live-provider readiness."""

    READY = "READY"
    NOT_READY = "NOT_READY"


class LiveReadinessCheckName(str, Enum):
    """Stable live-readiness check names."""

    PROVIDER_SELECTED = "PROVIDER_SELECTED"
    LIVE_DATA_ALLOWED = "LIVE_DATA_ALLOWED"
    WATCHLIST_PRESENT = "WATCHLIST_PRESENT"
    ALPACA_API_KEY_PRESENT = "ALPACA_API_KEY_PRESENT"
    ALPACA_API_SECRET_PRESENT = "ALPACA_API_SECRET_PRESENT"
    FMP_API_KEY_PRESENT = "FMP_API_KEY_PRESENT"
    RVOL_ARTIFACT_MANIFEST_PATH_PRESENT = "RVOL_ARTIFACT_MANIFEST_PATH_PRESENT"
    RELATIVE_VOLUME_SOURCE_PRESENT = "RELATIVE_VOLUME_SOURCE_PRESENT"


@dataclass(frozen=True)
class LiveReadinessCheck:
    """One secret-safe readiness check result."""

    name: LiveReadinessCheckName
    passed: bool
    message: str


@dataclass(frozen=True)
class LiveReadinessReport:
    """Inspectable report for future live-provider readiness."""

    status: LiveReadinessStatus
    checks: tuple[LiveReadinessCheck, ...]

    @property
    def ready(self) -> bool:
        """Return whether all readiness checks passed."""

        return self.status == LiveReadinessStatus.READY

    @property
    def failed_checks(self) -> tuple[LiveReadinessCheck, ...]:
        """Return checks that did not pass."""

        return tuple(check for check in self.checks if not check.passed)

    @property
    def summary(self) -> str:
        """Return a secret-safe user-facing summary."""

        if self.ready:
            return "Live readiness checks passed."
        failed_names = ", ".join(check.name.value for check in self.failed_checks)
        return f"Live readiness checks failed: {failed_names}."


def _has_mapping_values(value: Mapping[str, Any] | None) -> bool:
    return value is not None and bool(value)


def _has_relative_volume_source(
    *,
    relative_volume_configured: bool,
    relative_volume_provider: Any | None,
    relative_volume_by_symbol: Mapping[str, Any] | None,
) -> bool:
    return (
        relative_volume_configured
        or relative_volume_provider is not None
        or _has_mapping_values(relative_volume_by_symbol)
    )


def _check(name: LiveReadinessCheckName, passed: bool, message: str) -> LiveReadinessCheck:
    return LiveReadinessCheck(name=name, passed=passed, message=message)


def evaluate_live_readiness(
    config: AppConfig,
    *,
    relative_volume_configured: bool = False,
    relative_volume_provider: Any | None = None,
    relative_volume_by_symbol: Mapping[str, Any] | None = None,
) -> LiveReadinessReport:
    """Evaluate local preconditions for future live composed data.

    The relative-volume inputs are explicit readiness signals only. This helper
    does not calculate or validate RVOL values.
    """

    provider_selected = config.provider == LIVE_COMPOSED_PROVIDER
    live_data_allowed = config.allow_live_data
    watchlist_present = bool(config.watchlist)
    alpaca_api_key_present = bool(config.alpaca_api_key)
    alpaca_api_secret_present = bool(config.alpaca_api_secret)
    fmp_api_key_present = bool(config.fmp_api_key)
    rvol_artifact_manifest_path_present = (
        config.rvol_artifact_manifest_path is not None
    )
    relative_volume_source_present = _has_relative_volume_source(
        relative_volume_configured=relative_volume_configured,
        relative_volume_provider=relative_volume_provider,
        relative_volume_by_symbol=relative_volume_by_symbol,
    )

    checks = (
        _check(
            LiveReadinessCheckName.PROVIDER_SELECTED,
            provider_selected,
            (
                "Provider is live_composed."
                if provider_selected
                else "Provider must be live_composed."
            ),
        ),
        _check(
            LiveReadinessCheckName.LIVE_DATA_ALLOWED,
            live_data_allowed,
            (
                "Live data allow flag is enabled."
                if live_data_allowed
                else "Live data allow flag is not enabled."
            ),
        ),
        _check(
            LiveReadinessCheckName.WATCHLIST_PRESENT,
            watchlist_present,
            "Watchlist is present." if watchlist_present else "Watchlist is missing.",
        ),
        _check(
            LiveReadinessCheckName.ALPACA_API_KEY_PRESENT,
            alpaca_api_key_present,
            (
                "Alpaca API key is present."
                if alpaca_api_key_present
                else "Alpaca API key is missing."
            ),
        ),
        _check(
            LiveReadinessCheckName.ALPACA_API_SECRET_PRESENT,
            alpaca_api_secret_present,
            (
                "Alpaca API secret is present."
                if alpaca_api_secret_present
                else "Alpaca API secret is missing."
            ),
        ),
        _check(
            LiveReadinessCheckName.FMP_API_KEY_PRESENT,
            fmp_api_key_present,
            "FMP API key is present." if fmp_api_key_present else "FMP API key is missing.",
        ),
        _check(
            LiveReadinessCheckName.RVOL_ARTIFACT_MANIFEST_PATH_PRESENT,
            rvol_artifact_manifest_path_present,
            (
                "RVOL artifact manifest path is configured."
                if rvol_artifact_manifest_path_present
                else "RVOL artifact manifest path is missing."
            ),
        ),
        _check(
            LiveReadinessCheckName.RELATIVE_VOLUME_SOURCE_PRESENT,
            relative_volume_source_present,
            (
                "Relative-volume source is explicitly configured."
                if relative_volume_source_present
                else "Relative-volume source is missing."
            ),
        ),
    )
    status = (
        LiveReadinessStatus.READY
        if all(check.passed for check in checks)
        else LiveReadinessStatus.NOT_READY
    )
    return LiveReadinessReport(status=status, checks=checks)
