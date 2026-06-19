from pathlib import Path


LOCAL_JSON_BUNDLE_PREFLIGHT_EXPORT_NOTE = (
    "Note: This command reads only the explicit local metadata JSON path and "
    "local historical RVOL bundle path. It does not activate providers, scan "
    "candidates, call APIs, or play voice alerts."
)


def write_manual_local_json_bundle_preflight_report(
    path: Path,
    report: str,
) -> None:
    path.write_text(report, encoding="utf-8")


def render_manual_local_json_bundle_preflight_export_error(
    metadata_path: Path,
    bundle_path: Path,
    report_path: Path,
    error: OSError,
) -> str:
    error_message = str(error) or error.__class__.__name__
    return "\n".join(
        [
            "Market Sentry Local JSON Bundle Preflight",
            f"Metadata Path: {metadata_path}",
            f"Bundle Path: {bundle_path}",
            f"Report Path: {report_path}",
            "Result: EXPORT_ERROR",
            f"Error Type: {error.__class__.__name__}",
            f"Error: {error_message}",
            LOCAL_JSON_BUNDLE_PREFLIGHT_EXPORT_NOTE,
        ]
    )
