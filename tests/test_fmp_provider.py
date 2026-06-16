import ast
import inspect

import pytest

from market_sentry.config import AppConfig
from market_sentry.data import fmp
from market_sentry.data.factory import ProviderConfigurationError, create_market_data_provider
from market_sentry.data.fmp import (
    FMPFloatData,
    FMPReferenceSettings,
    build_auth_params,
    build_shares_float_request,
    is_valid_low_float_reference,
    normalize_float_shares,
    parse_shares_float_response,
)


def shares_float_fixture() -> list[dict]:
    return [
        {
            "symbol": "XTRM",
            "floatShares": 1_300_000,
            "outstandingShares": 6_000_000,
            "date": "2026-06-16",
        }
    ]


def test_fmp_settings_repr_does_not_expose_api_key() -> None:
    settings = FMPReferenceSettings(api_key="test-fmp-key")

    assert "test-fmp-key" not in repr(settings)


def test_fmp_request_repr_does_not_expose_api_key_but_params_remain_accessible() -> None:
    request = build_shares_float_request(
        "XTRM",
        FMPReferenceSettings(api_key="test-fmp-key"),
    )

    assert request.params["apikey"] == "test-fmp-key"
    assert "test-fmp-key" not in repr(request)


def test_auth_params_only_include_api_key_when_present() -> None:
    assert build_auth_params(FMPReferenceSettings()) == {}
    assert build_auth_params(FMPReferenceSettings(api_key="key")) == {"apikey": "key"}


def test_shares_float_request_path_and_symbol_are_normalized() -> None:
    request = build_shares_float_request(" xtrm ", FMPReferenceSettings())

    assert request.path == "/stable/shares-float"
    assert request.params == {"symbol": "XTRM"}


def test_empty_symbol_is_handled_safely() -> None:
    request = build_shares_float_request("  ", FMPReferenceSettings())

    assert request.params["symbol"] == ""


def test_list_style_fixture_parses_float_reference_fields() -> None:
    parsed = parse_shares_float_response(shares_float_fixture(), "xtrm")

    assert parsed == FMPFloatData(
        symbol="XTRM",
        float_shares=1_300_000,
        outstanding_shares=6_000_000,
        date="2026-06-16",
    )


def test_dict_style_fixture_parses_float_reference_fields() -> None:
    parsed = parse_shares_float_response(
        {
            "symbol": "CRVO",
            "freeFloat": "2,500,000".replace(",", ""),
            "sharesOutstanding": "9000000",
            "date": "2026-06-16",
        },
        "crvo",
    )

    assert parsed == FMPFloatData(
        symbol="CRVO",
        float_shares=2_500_000,
        outstanding_shares=9_000_000,
        date="2026-06-16",
    )


def test_nested_data_fixture_is_supported() -> None:
    parsed = parse_shares_float_response(
        {
            "data": [
                {
                    "symbol": "ATAI",
                    "float": 7_500_000,
                    "outstandingShares": 30_000_000,
                }
            ]
        },
        "atai",
    )

    assert parsed == FMPFloatData(
        symbol="ATAI",
        float_shares=7_500_000,
        outstanding_shares=30_000_000,
        date=None,
    )


def test_parser_handles_missing_symbol_data_safely() -> None:
    assert parse_shares_float_response(shares_float_fixture(), "MISSING") is None
    assert parse_shares_float_response(shares_float_fixture(), "") is None


def test_parser_handles_missing_or_invalid_float_safely() -> None:
    assert parse_shares_float_response({"symbol": "XTRM"}, "XTRM") is None
    assert parse_shares_float_response({"symbol": "XTRM", "floatShares": 0}, "XTRM") is None
    assert parse_shares_float_response({"symbol": "XTRM", "floatShares": -1}, "XTRM") is None
    assert parse_shares_float_response({"symbol": "XTRM", "floatShares": "bad"}, "XTRM") is None


def test_normalize_float_shares_preserves_valid_integers_without_fabricating() -> None:
    assert normalize_float_shares(1_300_000) == 1_300_000
    assert normalize_float_shares("1300000") == 1_300_000
    assert normalize_float_shares(None) is None
    assert normalize_float_shares("bad") is None


def test_low_float_reference_helper_uses_current_float_band() -> None:
    assert is_valid_low_float_reference(FMPFloatData("XTRM", 1_300_000))
    assert not is_valid_low_float_reference(FMPFloatData("BIG", 50_000_000))


def test_runtime_provider_factory_remains_unchanged_for_alpaca_placeholder() -> None:
    with pytest.raises(ProviderConfigurationError, match="future placeholder"):
        create_market_data_provider(AppConfig(provider="alpaca"))


def test_fmp_skeleton_has_no_network_dependencies() -> None:
    source = inspect.getsource(fmp)
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

    assert not {"http", "requests", "socket", "urllib", "httpx", "aiohttp"} & imported_modules
    assert "websocket" not in source.lower()
    assert "order" not in source.lower()
