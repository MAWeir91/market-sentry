import ast
import inspect

import market_sentry.__main__ as package_main
from market_sentry.data import MockMarketDataProvider
from market_sentry.main import format_share_count, main, render_report
from market_sentry.scanner import ScannerEngine


def test_format_share_count_uses_readable_units() -> None:
    assert format_share_count(750_000) == "750K"
    assert format_share_count(1_400_000) == "1.4M"
    assert format_share_count(10_000_000) == "10.0M"


def test_render_report_includes_meaningful_scanner_content() -> None:
    provider = MockMarketDataProvider()
    results = ScannerEngine().scan(provider.get_candidates())

    report = render_report(results)

    assert "Market Sentry" in report
    assert "Mock Scanner Report" in report
    assert "Qualified Results" in report
    assert "Rejected Results" in report
    assert "XTRM" in report
    assert "LOWP" in report
    assert "Tier 4: Extreme Runner" in report
    assert "Score:" in report
    assert "$11.40" in report
    assert "118.0%" in report
    assert "12.5x" in report
    assert "1.3M" in report
    assert "6.4M" in report
    assert "PRICE_BELOW_MIN" in report
    assert "[PASS]" in report
    assert "[FAIL]" in report


def test_render_report_shows_qualified_results_before_rejected_results() -> None:
    provider = MockMarketDataProvider()
    results = ScannerEngine().scan(provider.get_candidates())
    report = render_report(results)

    assert report.index("Qualified Results") < report.index("Rejected Results")
    assert report.index("XTRM") < report.index("LOWP")


def test_main_prints_mock_scanner_report(capsys) -> None:
    main()

    output = capsys.readouterr().out

    assert "Market Sentry" in output
    assert "Qualified Results" in output
    assert "Rejected Results" in output
    assert "Mock Scanner Report" in output


def test_package_main_delegates_to_main() -> None:
    source = inspect.getsource(package_main)

    assert "from market_sentry.main import main" in source
    assert "main()" in source


def test_cli_runner_has_no_external_api_or_trading_behavior() -> None:
    import market_sentry.main as runner

    source = inspect.getsource(runner)
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

    assert not {"http", "requests", "socket", "urllib", "os"} & imported_modules
    assert "api_key" not in source.lower()
    assert "broker" not in source.lower()
    assert "place_order" not in source.lower()
    assert "execute_order" not in source.lower()
