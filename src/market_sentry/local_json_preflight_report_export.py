from pathlib import Path


LOCAL_JSON_PREFLIGHT_EXPORT_NOTE = (
    "Note: This command reads only the explicit local JSON path. It does not "
    "activate providers, scan candidates, call APIs, or play voice alerts."
)


def write_manual_local_json_preflight_report(
    path: Path,
    report: str,
) -> None:
    path.write_text(report, encoding="utf-8")


def render_manual_local_json_preflight_export_error(
    input_path: Path,
    report_path: Path,
    error: OSError,
) -> str:
    error_message = str(error) or error.__class__.__name__
    return "\n".join(
        [
            "Market Sentry Local JSON Preflight",
            f"Path: {input_path}",
            f"Report Path: {report_path}",
            "Result: EXPORT_ERROR",
            f"Error Type: {error.__class__.__name__}",
            f"Error: {error_message}",
            LOCAL_JSON_PREFLIGHT_EXPORT_NOTE,
        ]
    )
