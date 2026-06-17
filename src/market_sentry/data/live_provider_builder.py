"""Dry builder for a future live composed market-data provider.

This module assembles injected components only. It is not connected to the
runtime provider factory and does not instantiate a real HTTP transport.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from market_sentry.config import (
    AppConfig,
    LiveProviderGateResult,
    validate_live_provider_gate,
)
from market_sentry.data.alpaca import AlpacaMarketDataSettings
from market_sentry.data.fmp import FMPReferenceSettings
from market_sentry.data.live_candidate_builder import LiveCandidateBuilder
from market_sentry.data.live_composed_provider import LiveComposedMarketDataProvider
from market_sentry.data.relative_volume import RelativeVolumeProvider


class LiveProviderBuildError(ValueError):
    """Raised when the future live provider cannot be safely assembled."""


def _gate_failure_message(gate_result: LiveProviderGateResult) -> str:
    reasons = ", ".join(reason.value for reason in gate_result.failure_reasons)
    return f"Live provider gate failed: {reasons}."


def _require_factory(factory: Callable[..., Any] | None, name: str) -> Callable[..., Any]:
    if factory is None:
        raise LiveProviderBuildError(f"{name} is required for dry live provider wiring.")
    return factory


def _require_live_config_fields(config: AppConfig) -> None:
    missing_fields: list[str] = []
    if not config.watchlist:
        missing_fields.append("WATCHLIST")
    if not config.alpaca_api_key:
        missing_fields.append("ALPACA_API_KEY")
    if not config.alpaca_api_secret:
        missing_fields.append("ALPACA_API_SECRET")
    if not config.fmp_api_key:
        missing_fields.append("FMP_API_KEY")

    if missing_fields:
        fields = ", ".join(missing_fields)
        raise LiveProviderBuildError(f"Missing live provider config fields: {fields}.")


def build_live_composed_provider(
    config: AppConfig,
    *,
    relative_volume_by_symbol: Mapping[str, float | int | str] | None = None,
    relative_volume_provider: RelativeVolumeProvider | None = None,
    transport_factory: Callable[[], Any] | None,
    alpaca_fetcher_factory: Callable[..., Any] | None,
    fmp_fetcher_factory: Callable[..., Any] | None,
    provider_class: type[LiveComposedMarketDataProvider] = LiveComposedMarketDataProvider,
    builder_class: type[LiveCandidateBuilder] = LiveCandidateBuilder,
    gate_result: LiveProviderGateResult | None = None,
) -> LiveComposedMarketDataProvider:
    """Assemble a future live composed provider from injected factories.

    Construction is dry wiring only. The injected factories must not perform
    network work during construction, and this helper does not call provider
    methods that would fetch market data.
    """

    resolved_gate_result = gate_result or validate_live_provider_gate(config)
    if not resolved_gate_result.allowed:
        raise LiveProviderBuildError(_gate_failure_message(resolved_gate_result))

    _require_live_config_fields(config)

    if relative_volume_by_symbol is None:
        if relative_volume_provider is None:
            raise LiveProviderBuildError(
                "Explicit relative_volume_by_symbol or relative_volume_provider "
                "is required for live provider wiring."
            )
        relative_volume_by_symbol = relative_volume_provider.get_relative_volumes(
            config.watchlist
        )

    required_transport_factory = _require_factory(
        transport_factory,
        "transport_factory",
    )
    required_alpaca_fetcher_factory = _require_factory(
        alpaca_fetcher_factory,
        "alpaca_fetcher_factory",
    )
    required_fmp_fetcher_factory = _require_factory(
        fmp_fetcher_factory,
        "fmp_fetcher_factory",
    )

    transport = required_transport_factory()
    alpaca_settings = AlpacaMarketDataSettings(
        api_key=config.alpaca_api_key,
        api_secret=config.alpaca_api_secret,
        feed=config.alpaca_data_feed or "iex",
    )
    fmp_settings = FMPReferenceSettings(api_key=config.fmp_api_key)

    snapshot_source = required_alpaca_fetcher_factory(
        settings=alpaca_settings,
        transport=transport,
    )
    float_source = required_fmp_fetcher_factory(
        settings=fmp_settings,
        transport=transport,
    )
    builder = builder_class(
        snapshot_source=snapshot_source,
        float_source=float_source,
    )

    return provider_class(
        watchlist=config.watchlist,
        snapshot_source=snapshot_source,
        float_source=float_source,
        relative_volume_by_symbol=relative_volume_by_symbol,
        builder=builder,
    )
