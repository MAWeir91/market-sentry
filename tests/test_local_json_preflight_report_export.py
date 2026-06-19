import ast
import inspect

import pytest

from market_sentry import local_json_preflight_report_export as export
from market_sentry.local_json_preflight_report_export import (
    LOCAL_JSON_PREFLIGHT_EXPORT_NOTE,
    render_manual_local_json_preflight_export_error,
    write_manual_local_json_preflight_report,
)


class RecordingPath:
    def __init__(self) -> None:
        self.calls = []

    def write_text(self, report, *, encoding=None):
        self.calls.append((report, encoding))
        return len(report)


def test_write_report_uses_exact_utf8_content_without_newline(tmp_path) -> None:
    path = tmp_path / "report.txt"
    report = "Market Sentry Local JSON Preflight\nRelative Volume: 2.0x"

    write_manual_local_json_preflight_report(path, report)

    assert path.read_text(encoding="utf-8") == report
    assert not path.read_bytes().endswith(b"\n")


def test_write_report_forwards_exact_path_and_report_once() -> None:
    path = RecordingPath()
    report = "exact report"

    write_manual_local_json_preflight_report(path, report)

    assert path.calls == [(report, "utf-8")]


def test_write_report_does_not_create_parent_directories(tmp_path) -> None:
    path = tmp_path / "missing" / "report.txt"

    with pytest.raises(FileNotFoundError):
        write_manual_local_json_preflight_report(path, "report")

    assert not path.exists()
    assert not path.parent.exists()


def test_export_error_formatting_is_stable_and_secret_safe(tmp_path) -> None:
    input_path = tmp_path / "input.json"
    report_path = tmp_path / "report.txt"
    error = OSError("disk unavailable")

    rendered = render_manual_local_json_preflight_export_error(
        input_path,
        report_path,
        error,
    )

    assert rendered.splitlines() == [
        "Market Sentry Local JSON Preflight",
        f"Path: {input_path}",
        f"Report Path: {report_path}",
        "Result: EXPORT_ERROR",
        "Error Type: OSError",
        "Error: disk unavailable",
        LOCAL_JSON_PREFLIGHT_EXPORT_NOTE,
    ]
    lowered = rendered.lower()
    assert "traceback" not in lowered
    assert "api_key" not in lowered
    assert "raw json" not in lowered


def test_export_error_empty_message_falls_back_to_class_name(tmp_path) -> None:
    rendered = render_manual_local_json_preflight_export_error(
        tmp_path / "input.json",
        tmp_path / "report.txt",
        OSError(),
    )

    assert "Error Type: OSError" in rendered
    assert "Error: OSError" in rendered


def test_export_source_boundary() -> None:
    source = inspect.getsource(export)
    tree = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert imported_modules == {"pathlib"}

    call_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)

    assert "write_text" in call_names
    forbidden_calls = {
        "read_text",
        "read_bytes",
        "mkdir",
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
    }
    assert not forbidden_calls & call_names

    forbidden_terms = [
        "market_sentry.main",
        "config",
        "http",
        "transport",
        "local_json_preflight_cli",
        "local_json_metadata_preflight",
        "cache",
        "registry",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
