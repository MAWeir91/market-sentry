from market_sentry.config import AppConfig, load_config, parse_watchlist


def test_default_provider_is_mock() -> None:
    config = load_config({})

    assert config.provider == "mock"


def test_mock_mode_requires_no_credentials() -> None:
    config = load_config({})

    assert config.provider == "mock"
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
            "ALPACA_API_KEY": "key",
            "ALPACA_API_SECRET": "secret",
            "ALPACA_DATA_FEED": "iex",
            "FMP_API_KEY": "fmp",
        }
    )

    assert config.watchlist == ("XTRM", "CRVO")
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
