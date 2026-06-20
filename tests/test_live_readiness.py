import ast
import inspect
from pathlib import Path

import pytest

from market_sentry.config import AppConfig
from market_sentry.data import factory
from market_sentry.data.composed_fixture_provider import OfflineComposedFixtureProvider
from market_sentry.data.factory import ProviderConfigurationError, create_market_data_provider
from market_sentry.data.fixture_provider import FixtureComposedMarketDataProvider
from market_sentry.data.mock_provider import MockMarketDataProvider
from market_sentry import live_readiness
from market_sentry.live_readiness import (
    LiveReadinessCheckName,
    LiveReadinessStatus,
    evaluate_live_readiness,
)


class FakeRelativeVolumeProvider:
    pass


def live_config(**overrides: object) -> AppConfig:
    values = {
        "provider": "live_composed",
        "allow_live_data": True,
        "watchlist": ("AAPL",),
        "alpaca_api_key": "placeholder-key",
        "alpaca_api_secret": "placeholder-secret",
        "fmp_api_key": "placeholder-fmp-key",
        "rvol_artifact_manifest_path": Path("rvol-artifacts.json"),
    }
    values.update(overrides)
    return AppConfig(**values)


def checks_by_name(report):
    return {check.name: check for check in report.checks}


def test_report_fails_when_provider_is_not_live_composed() -> None:
    report = evaluate_live_readiness(
        live_config(provider="mock"),
        relative_volume_configured=True,
    )

    check = checks_by_name(report)[LiveReadinessCheckName.PROVIDER_SELECTED]

    assert not report.ready
    assert report.status == LiveReadinessStatus.NOT_READY
    assert not check.passed
    assert check.message == "Provider must be live_composed."


def test_report_fails_when_allow_live_is_false() -> None:
    report = evaluate_live_readiness(
        live_config(allow_live_data=False),
        relative_volume_configured=True,
    )

    check = checks_by_name(report)[LiveReadinessCheckName.LIVE_DATA_ALLOWED]

    assert not report.ready
    assert not check.passed
    assert check.message == "Live data allow flag is not enabled."


def test_report_fails_when_watchlist_is_empty() -> None:
    report = evaluate_live_readiness(
        live_config(watchlist=()),
        relative_volume_configured=True,
    )

    check = checks_by_name(report)[LiveReadinessCheckName.WATCHLIST_PRESENT]

    assert not report.ready
    assert not check.passed
    assert check.message == "Watchlist is missing."


def test_report_fails_when_alpaca_api_key_is_missing() -> None:
    report = evaluate_live_readiness(
        live_config(alpaca_api_key=None),
        relative_volume_configured=True,
    )

    check = checks_by_name(report)[LiveReadinessCheckName.ALPACA_API_KEY_PRESENT]

    assert not report.ready
    assert not check.passed
    assert check.message == "Alpaca API key is missing."


def test_report_fails_when_alpaca_api_secret_is_missing() -> None:
    report = evaluate_live_readiness(
        live_config(alpaca_api_secret=None),
        relative_volume_configured=True,
    )

    check = checks_by_name(report)[LiveReadinessCheckName.ALPACA_API_SECRET_PRESENT]

    assert not report.ready
    assert not check.passed
    assert check.message == "Alpaca API secret is missing."


def test_report_fails_when_fmp_api_key_is_missing() -> None:
    report = evaluate_live_readiness(
        live_config(fmp_api_key=None),
        relative_volume_configured=True,
    )

    check = checks_by_name(report)[LiveReadinessCheckName.FMP_API_KEY_PRESENT]

    assert not report.ready
    assert not check.passed
    assert check.message == "FMP API key is missing."


def test_report_fails_when_relative_volume_source_is_missing() -> None:
    report = evaluate_live_readiness(live_config())

    check = checks_by_name(report)[
        LiveReadinessCheckName.RELATIVE_VOLUME_SOURCE_PRESENT
    ]

    assert not report.ready
    assert not check.passed
    assert check.message == "Relative-volume source is missing."


def test_report_fails_when_manifest_path_is_missing() -> None:
    report = evaluate_live_readiness(
        live_config(rvol_artifact_manifest_path=None),
        relative_volume_configured=True,
    )

    check = checks_by_name(report)[
        LiveReadinessCheckName.RVOL_ARTIFACT_MANIFEST_PATH_PRESENT
    ]

    assert not report.ready
    assert not check.passed
    assert check.message == "RVOL artifact manifest path is missing."


def test_report_accepts_explicit_relative_volume_provider() -> None:
    report = evaluate_live_readiness(
        live_config(),
        relative_volume_provider=FakeRelativeVolumeProvider(),
    )

    check = checks_by_name(report)[
        LiveReadinessCheckName.RELATIVE_VOLUME_SOURCE_PRESENT
    ]

    assert report.ready
    assert check.passed


def test_report_accepts_explicit_relative_volume_mapping() -> None:
    report = evaluate_live_readiness(
        live_config(),
        relative_volume_by_symbol={"AAPL": 2.5},
    )

    assert report.ready


def test_report_does_not_treat_empty_relative_volume_mapping_as_configured() -> None:
    report = evaluate_live_readiness(
        live_config(),
        relative_volume_by_symbol={},
    )

    assert not report.ready


def test_report_passes_when_all_preconditions_are_present() -> None:
    report = evaluate_live_readiness(
        live_config(),
        relative_volume_configured=True,
    )

    assert report.ready
    assert report.status == LiveReadinessStatus.READY
    assert report.failed_checks == ()
    assert report.summary == "Live readiness checks passed."


def test_report_exposes_stable_check_names_and_results() -> None:
    report = evaluate_live_readiness(AppConfig())

    assert tuple(check.name for check in report.checks) == (
        LiveReadinessCheckName.PROVIDER_SELECTED,
        LiveReadinessCheckName.LIVE_DATA_ALLOWED,
        LiveReadinessCheckName.WATCHLIST_PRESENT,
        LiveReadinessCheckName.ALPACA_API_KEY_PRESENT,
        LiveReadinessCheckName.ALPACA_API_SECRET_PRESENT,
        LiveReadinessCheckName.FMP_API_KEY_PRESENT,
        LiveReadinessCheckName.RVOL_ARTIFACT_MANIFEST_PATH_PRESENT,
        LiveReadinessCheckName.RELATIVE_VOLUME_SOURCE_PRESENT,
    )
    assert all(isinstance(check.passed, bool) for check in report.checks)
    assert report.summary == (
        "Live readiness checks failed: PROVIDER_SELECTED, LIVE_DATA_ALLOWED, "
        "WATCHLIST_PRESENT, ALPACA_API_KEY_PRESENT, ALPACA_API_SECRET_PRESENT, "
        "FMP_API_KEY_PRESENT, RVOL_ARTIFACT_MANIFEST_PATH_PRESENT, "
        "RELATIVE_VOLUME_SOURCE_PRESENT."
    )


def test_report_messages_do_not_expose_secret_values() -> None:
    report = evaluate_live_readiness(
        live_config(
            provider="mock",
            allow_live_data=False,
            alpaca_api_key="visible-key-should-not-print",
            alpaca_api_secret="visible-secret-should-not-print",
            fmp_api_key="visible-fmp-should-not-print",
        )
    )
    output = " ".join([report.summary, *(check.message for check in report.checks)])

    assert "visible-key-should-not-print" not in output
    assert "visible-secret-should-not-print" not in output
    assert "visible-fmp-should-not-print" not in output


def test_live_readiness_module_has_no_network_or_trading_behavior() -> None:
    source = inspect.getsource(live_readiness)
    tree = ast.parse(source)
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert not {"http", "requests", "socket", "urllib", "httpx", "aiohttp", "os"} & imported_modules
    assert "StdlibHttpTransport" not in source
    assert "AlpacaSnapshotFetcher" not in source
    assert "FMPFloatFetcher" not in source
    assert ".send(" not in source
    assert "load_config" not in source
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()


def test_runtime_provider_factory_remains_unchanged() -> None:
    source = inspect.getsource(factory)

    assert "evaluate_live_readiness" not in source
    assert isinstance(create_market_data_provider(AppConfig()), MockMarketDataProvider)
    assert isinstance(
        create_market_data_provider(AppConfig(provider="fixture")),
        FixtureComposedMarketDataProvider,
    )
    assert isinstance(
        create_market_data_provider(AppConfig(provider="composed_fixture")),
        OfflineComposedFixtureProvider,
    )
    with pytest.raises(ProviderConfigurationError, match="future placeholder"):
        create_market_data_provider(AppConfig(provider="alpaca"))


def test_live_composed_requires_local_artifact_manifest() -> None:
    with pytest.raises(ProviderConfigurationError, match="MISSING_RVOL_ARTIFACT"):
        create_market_data_provider(
            live_config(
                provider="live_composed",
                allow_live_data=True,
                watchlist=("AAPL",),
                alpaca_api_key="placeholder-key",
                alpaca_api_secret="placeholder-secret",
                fmp_api_key="placeholder-fmp-key",
                rvol_artifact_manifest_path=None,
            )
        )
