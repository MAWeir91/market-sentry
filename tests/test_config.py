import pytest

from market_sentry.config import (
    AppConfig,
    LiveProviderGateFailure,
    load_config,
    parse_allow_live_data,
    parse_watchlist,
    validate_live_provider_gate,
)


def test_default_provider_is_mock() -> None:
    config = load_config({})

    assert config.provider == "mock"


def test_mock_mode_requires_no_credentials() -> None:
    config = load_config({})

    assert config.provider == "mock"
    assert config.allow_live_data is False
    assert config.alpaca_api_key is None
    assert config.alpaca_api_secret is None
    assert config.fmp_api_key is None


def test_future_credential_fields_are_optional_placeholders() -> None:
    config = AppConfig()

    assert config.alpaca_api_key is None
    assert config.alpaca_api_secret is None
    assert config.alpaca_data_feed is None
    assert config.fmp_api_key is None


def test_provider_name_normalizes_cleanly() -> None:
    config = load_config({"MARKET_SENTRY_PROVIDER": " Alpaca "})

    assert config.provider == "alpaca"


def test_watchlist_parser_trims_uppercases_and_ignores_empty_values() -> None:
    assert parse_watchlist(" xtrm, CRVO, , atai ") == ("XTRM", "CRVO", "ATAI")


def test_empty_watchlist_is_empty_tuple() -> None:
    assert parse_watchlist(None) == ()
    assert parse_watchlist("") == ()
    assert load_config({"MARKET_SENTRY_WATCHLIST": " , , "}).watchlist == ()


def test_load_config_parses_future_placeholders_without_requiring_them() -> None:
    config = load_config(
        {
            "MARKET_SENTRY_PROVIDER": "mock",
            "MARKET_SENTRY_WATCHLIST": "xtrm, crvo",
            "MARKET_SENTRY_ALLOW_LIVE_DATA": "true",
            "ALPACA_API_KEY": "key",
            "ALPACA_API_SECRET": "secret",
            "ALPACA_DATA_FEED": "iex",
            "FMP_API_KEY": "fmp",
        }
    )

    assert config.watchlist == ("XTRM", "CRVO")
    assert config.allow_live_data is True
    assert config.alpaca_api_key == "key"
    assert config.alpaca_api_secret == "secret"
    assert config.alpaca_data_feed == "iex"
    assert config.fmp_api_key == "fmp"


def test_config_repr_does_not_include_secret_values() -> None:
    config = load_config(
        {
            "ALPACA_API_KEY": "visible-key-should-not-print",
            "ALPACA_API_SECRET": "visible-secret-should-not-print",
            "FMP_API_KEY": "visible-fmp-should-not-print",
        }
    )

    representation = repr(config)

    assert "visible-key-should-not-print" not in representation
    assert "visible-secret-should-not-print" not in representation
    assert "visible-fmp-should-not-print" not in representation


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", " TRUE ", " On "])
def test_allow_live_flag_truthy_parsing(value: str) -> None:
    assert parse_allow_live_data(value)


@pytest.mark.parametrize("value", [None, "", "0", "false", "no", "off", "anything"])
def test_allow_live_flag_false_or_missing_behavior(value: str | None) -> None:
    assert not parse_allow_live_data(value)


def live_config(**overrides: object) -> AppConfig:
    values = {
        "provider": "live_composed",
        "allow_live_data": True,
        "watchlist": ("XTRM",),
        "alpaca_api_key": "alpaca-key-secret",
        "alpaca_api_secret": "alpaca-secret-secret",
        "fmp_api_key": "fmp-key-secret",
    }
    values.update(overrides)
    return AppConfig(**values)


def assert_gate_fails_with(config: AppConfig, reason: LiveProviderGateFailure) -> None:
    result = validate_live_provider_gate(config)

    assert not result.allowed
    assert reason in result.failure_reasons


def test_live_gate_fails_if_provider_is_not_live_composed() -> None:
    assert_gate_fails_with(
        live_config(provider="mock"),
        LiveProviderGateFailure.PROVIDER_NOT_LIVE_COMPOSED,
    )


def test_live_gate_fails_if_allow_live_flag_is_false() -> None:
    assert_gate_fails_with(
        live_config(allow_live_data=False),
        LiveProviderGateFailure.LIVE_DATA_NOT_ALLOWED,
    )


def test_live_gate_fails_if_watchlist_is_empty() -> None:
    assert_gate_fails_with(
        live_config(watchlist=()),
        LiveProviderGateFailure.MISSING_WATCHLIST,
    )


def test_live_gate_fails_if_alpaca_api_key_is_missing() -> None:
    assert_gate_fails_with(
        live_config(alpaca_api_key=None),
        LiveProviderGateFailure.MISSING_ALPACA_API_KEY,
    )


def test_live_gate_fails_if_alpaca_api_secret_is_missing() -> None:
    assert_gate_fails_with(
        live_config(alpaca_api_secret=None),
        LiveProviderGateFailure.MISSING_ALPACA_API_SECRET,
    )


def test_live_gate_fails_if_fmp_api_key_is_missing() -> None:
    assert_gate_fails_with(
        live_config(fmp_api_key=None),
        LiveProviderGateFailure.MISSING_FMP_API_KEY,
    )


def test_live_gate_passes_only_when_all_required_fields_are_present() -> None:
    result = validate_live_provider_gate(live_config())

    assert result.allowed
    assert result.failure_reasons == ()
    assert result.message == "Live composed provider gate passed."


def test_live_gate_collects_stable_failure_reasons() -> None:
    result = validate_live_provider_gate(AppConfig())

    assert not result.allowed
    assert result.failure_reasons == (
        LiveProviderGateFailure.PROVIDER_NOT_LIVE_COMPOSED,
        LiveProviderGateFailure.LIVE_DATA_NOT_ALLOWED,
        LiveProviderGateFailure.MISSING_WATCHLIST,
        LiveProviderGateFailure.MISSING_ALPACA_API_KEY,
        LiveProviderGateFailure.MISSING_ALPACA_API_SECRET,
        LiveProviderGateFailure.MISSING_FMP_API_KEY,
    )


def test_live_gate_message_does_not_expose_secret_values() -> None:
    config = live_config(
        provider="mock",
        allow_live_data=False,
        alpaca_api_key="visible-key-should-not-print",
        alpaca_api_secret="visible-secret-should-not-print",
        fmp_api_key="visible-fmp-should-not-print",
    )

    message = validate_live_provider_gate(config).message

    assert "visible-key-should-not-print" not in message
    assert "visible-secret-should-not-print" not in message
    assert "visible-fmp-should-not-print" not in message
    assert "PROVIDER_NOT_LIVE_COMPOSED" in message
    assert "LIVE_DATA_NOT_ALLOWED" in message


def test_live_gate_can_be_validated_from_environment_mapping() -> None:
    config = load_config(
        {
            "MARKET_SENTRY_PROVIDER": " live_composed ",
            "MARKET_SENTRY_ALLOW_LIVE_DATA": " YES ",
            "MARKET_SENTRY_WATCHLIST": "xtrm",
            "ALPACA_API_KEY": "key",
            "ALPACA_API_SECRET": "secret",
            "FMP_API_KEY": "fmp",
        }
    )

    result = validate_live_provider_gate(config)

    assert config.provider == "live_composed"
    assert config.allow_live_data
    assert result.allowed
