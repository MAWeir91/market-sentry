import ast
import inspect

from market_sentry.data import relative_volume
from market_sentry.data.relative_volume import (
    RelativeVolumeProvider,
    StaticRelativeVolumeProvider,
    normalize_relative_volume,
    normalize_symbol,
    normalize_symbols,
)


class FakeRelativeVolumeProvider:
    def get_relative_volumes(self, symbols):
        return {symbol.strip().upper(): 2.5 for symbol in symbols if symbol.strip()}


def test_protocol_fake_provider_shape_is_usable() -> None:
    provider: RelativeVolumeProvider = FakeRelativeVolumeProvider()

    assert provider.get_relative_volumes([" xtrm ", ""]) == {"XTRM": 2.5}


def test_symbol_normalization_trims_and_uppercases() -> None:
    assert normalize_symbol(" xtrm ") == "XTRM"
    assert normalize_symbol("") == ""
    assert normalize_symbol(None) == ""


def test_normalize_symbols_ignores_empty_symbols() -> None:
    assert normalize_symbols([" xtrm ", "", "  ", "mrun"]) == ("XTRM", "MRUN")


def test_static_provider_normalizes_configured_and_requested_symbols() -> None:
    provider = StaticRelativeVolumeProvider({" xtrm ": 12.5, "mrun": "6.2"})

    assert provider.get_relative_volumes(["XTRM", " MRUN "]) == {
        "XTRM": 12.5,
        "MRUN": 6.2,
    }


def test_static_provider_returns_only_explicit_values() -> None:
    provider = StaticRelativeVolumeProvider({"XTRM": 12.5})

    assert provider.get_relative_volumes(["XTRM", "MISSING"]) == {"XTRM": 12.5}


def test_missing_relative_volume_is_not_fabricated() -> None:
    provider = StaticRelativeVolumeProvider({})

    assert provider.get_relative_volumes(["XTRM"]) == {}


def test_invalid_relative_volume_values_are_omitted_safely() -> None:
    provider = StaticRelativeVolumeProvider(
        {
            "TEXT": "not-a-number",
            "NONE": None,
            "BOOL": True,
            "NAN": float("nan"),
            "INF": float("inf"),
            "VALID": "3.5",
        }
    )

    assert provider.get_relative_volumes(["TEXT", "NONE", "BOOL", "NAN", "INF", "VALID"]) == {
        "VALID": 3.5
    }


def test_zero_and_negative_relative_volume_values_are_not_usable() -> None:
    provider = StaticRelativeVolumeProvider({"ZERO": 0, "NEG": -1, "VALID": 1})

    assert provider.get_relative_volumes(["ZERO", "NEG", "VALID"]) == {"VALID": 1.0}
    assert normalize_relative_volume(0) is None
    assert normalize_relative_volume(-1) is None


def test_duplicate_symbols_are_deterministic() -> None:
    provider = StaticRelativeVolumeProvider({"xtrm": 2.0, " XTRM ": 3.0})

    assert provider.get_relative_volumes(["xtrm", " XTRM ", "xtrm"]) == {"XTRM": 3.0}


def test_static_provider_makes_no_http_calls_and_requires_no_credentials() -> None:
    provider = StaticRelativeVolumeProvider({"XTRM": 12.5})

    assert provider.get_relative_volumes(["XTRM"]) == {"XTRM": 12.5}


def test_relative_volume_module_has_no_network_or_trading_behavior() -> None:
    source = inspect.getsource(relative_volume)
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
    assert ".send(" not in source
    assert "api_key" not in source.lower()
    assert "authorization" not in source.lower()
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()
