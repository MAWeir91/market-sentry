from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from market_sentry.config import AppConfig
from market_sentry.data.alpaca import AlpacaMarketDataSettings
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsFetchError,
    AlpacaHistoricalBarsFetcher,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.explicit_alpaca_rvol_bundle_capture import (
    ExplicitAlpacaRvolBundleCaptureRequest,
)
from market_sentry.data.explicit_alpaca_rvol_capture_preflight import (
    ExplicitAlpacaRvolCapturePreflightRequest,
    ExplicitAlpacaRvolCapturePreflightResult,
    ExplicitAlpacaRvolCapturePreflightStatus,
    capture_and_preflight_explicit_alpaca_rvol_bundle,
    is_explicit_alpaca_rvol_capture_preflight_success,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
)
from market_sentry.data.http import HttpTransport, HttpTransportError
from market_sentry.data.http_stdlib import StdlibHttpTransport
from market_sentry.data.json_historical_session_metadata_source import (
    JsonHistoricalSessionMetadataFileSource,
    JsonHistoricalSessionMetadataFileSourceError,
)
from market_sentry.data.json_historical_session_metadata_writer import (
    JsonHistoricalSessionMetadataWriteError,
)


MANUAL_EXPLICIT_ALPACA_CAPTURE_EXPECTED_ERRORS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    JsonHistoricalSessionMetadataFileSourceError,
    JsonHistoricalSessionMetadataWriteError,
    AlpacaHistoricalBarsFetchError,
    HttpTransportError,
)

MANUAL_EXPLICIT_ALPACA_CAPTURE_COMMAND_NOTE = (
    "Note: This command is one-shot and does not activate providers, scan "
    "candidates, call FMP, or play voice alerts."
)

MANUAL_EXPLICIT_ALPACA_CAPTURE_OPERATIONAL_NOTE = (
    "Note: This command can use caller-configured Alpaca fetching only after "
    "explicit CLI confirmation and MARKET_SENTRY_ALLOW_LIVE_DATA are both "
    "enabled. It does not activate providers, scan candidates, call FMP, or "
    "play voice alerts."
)

MISSING_CAPTURE_FIELDS = (
    ("--manual-alpaca-rvol-capture-symbol", "symbol"),
    ("--manual-alpaca-rvol-capture-historical-start", "historical_start"),
    ("--manual-alpaca-rvol-capture-historical-end", "historical_end"),
    ("--manual-alpaca-rvol-capture-historical-max-pages", "historical_max_pages"),
    ("--manual-alpaca-rvol-capture-current-start", "current_start"),
    ("--manual-alpaca-rvol-capture-current-end", "current_end"),
    ("--manual-alpaca-rvol-capture-current-max-pages", "current_max_pages"),
    ("--manual-alpaca-rvol-capture-current-session-id", "current_session_id"),
    ("--manual-alpaca-rvol-capture-bucket", "bucket"),
    ("--manual-alpaca-rvol-capture-cutoff", "cutoff"),
    (
        "--manual-alpaca-rvol-capture-minimum-historical-sessions",
        "minimum_historical_sessions",
    ),
)


class ManualExplicitAlpacaRvolCaptureCommandError(ValueError):
    """Raised for invalid manual explicit Alpaca capture command inputs."""


@dataclass(frozen=True)
class ManualExplicitAlpacaRvolCaptureCommandRequest:
    """Fully explicit inputs for one manual Alpaca capture command."""

    metadata_input_path: Path
    metadata_output_path: Path
    bundle_output_path: Path
    report_output_path: Path | None
    confirm_live_data: bool
    symbol: str | None
    historical_start: str | None
    historical_end: str | None
    historical_max_pages: int | None
    current_start: str | None
    current_end: str | None
    current_max_pages: int | None
    current_session_id: str | None
    bucket: str | None
    cutoff: str | None
    minimum_historical_sessions: int | None
    timeframe: str = "1Min"
    page_limit: int = 1000
    sort: str = "asc"


def _command_error(message: str) -> ManualExplicitAlpacaRvolCaptureCommandError:
    return ManualExplicitAlpacaRvolCaptureCommandError(message)


def _display_path(path: Path | None) -> str:
    if path is None:
        return "N/A"
    return str(path)


def _validate_path_types(command: ManualExplicitAlpacaRvolCaptureCommandRequest) -> None:
    if not isinstance(command.metadata_input_path, Path):
        raise TypeError("metadata_input_path must be a pathlib.Path.")
    if not isinstance(command.metadata_output_path, Path):
        raise TypeError("metadata_output_path must be a pathlib.Path.")
    if not isinstance(command.bundle_output_path, Path):
        raise TypeError("bundle_output_path must be a pathlib.Path.")
    if (
        command.report_output_path is not None
        and not isinstance(command.report_output_path, Path)
    ):
        raise TypeError("report_output_path must be a pathlib.Path or None.")


def _missing_capture_arguments(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
) -> list[str]:
    missing: list[str] = []
    for flag, field_name in MISSING_CAPTURE_FIELDS:
        value = getattr(command, field_name)
        if isinstance(value, str):
            if value.strip() == "":
                missing.append(flag)
        elif value is None:
            missing.append(flag)
    return missing


def _require_command_fields(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
) -> None:
    missing = _missing_capture_arguments(command)
    if missing:
        raise _command_error(f"MISSING_CAPTURE_ARGUMENTS:{','.join(missing)}")


def _require_distinct_seed_paths(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
) -> None:
    if command.metadata_input_path == command.metadata_output_path:
        raise _command_error("METADATA_INPUT_EQUALS_METADATA_OUTPUT")
    if command.metadata_input_path == command.bundle_output_path:
        raise _command_error("METADATA_INPUT_EQUALS_BUNDLE_OUTPUT")
    if command.metadata_input_path == command.report_output_path:
        raise _command_error("METADATA_INPUT_EQUALS_REPORT_OUTPUT")


def _parse_cutoff(value: str) -> datetime:
    parse_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(parse_value)
    except ValueError as exc:
        raise _command_error("INVALID_CUTOFF_TIMESTAMP") from exc


def _build_query(
    *,
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
    start: str,
    end: str,
) -> AlpacaHistoricalBarsQuery:
    return AlpacaHistoricalBarsQuery(
        timeframe=command.timeframe,
        start=start,
        end=end,
        limit=command.page_limit,
        sort=command.sort,
    )


def _load_seed_records(command: ManualExplicitAlpacaRvolCaptureCommandRequest):
    seed_request = HistoricalSessionManifestRequest(
        symbol=command.symbol,
        bucket=command.bucket,
        current_session_id=command.current_session_id,
    )
    return JsonHistoricalSessionMetadataFileSource(
        command.metadata_input_path,
    ).load_raw_manifest_records(seed_request)


def validate_manual_explicit_alpaca_rvol_capture_command(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
) -> None:
    _validate_path_types(command)
    _require_command_fields(command)
    _require_distinct_seed_paths(command)

    if command.confirm_live_data is not True:
        raise _command_error("LIVE_DATA_CONFIRMATION_REQUIRED")


def run_manual_explicit_alpaca_rvol_capture_preflight(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
    config: AppConfig,
    transport: HttpTransport | None = None,
) -> ExplicitAlpacaRvolCapturePreflightResult:
    """Run one explicitly confirmed, configuration-gated Alpaca capture."""

    validate_manual_explicit_alpaca_rvol_capture_command(command)
    if config.allow_live_data is not True:
        raise _command_error("ENV_LIVE_DATA_NOT_ALLOWED")
    if not config.alpaca_api_key:
        raise _command_error("MISSING_ALPACA_API_KEY")
    if not config.alpaca_api_secret:
        raise _command_error("MISSING_ALPACA_API_SECRET")

    cutoff_timestamp = _parse_cutoff(command.cutoff)
    historical_query = _build_query(
        command=command,
        start=command.historical_start,
        end=command.historical_end,
    )
    current_query = _build_query(
        command=command,
        start=command.current_start,
        end=command.current_end,
    )
    records = _load_seed_records(command)

    actual_transport = transport if transport is not None else StdlibHttpTransport()
    settings = AlpacaMarketDataSettings(
        api_key=config.alpaca_api_key,
        api_secret=config.alpaca_api_secret,
        feed=config.alpaca_data_feed or "iex",
    )
    fetcher = AlpacaHistoricalBarsFetcher(
        settings=settings,
        transport=actual_transport,
    )
    capture_request = ExplicitAlpacaRvolBundleCaptureRequest(
        symbol=command.symbol,
        historical_initial_query=historical_query,
        historical_max_pages=command.historical_max_pages,
        current_initial_query=current_query,
        current_max_pages=command.current_max_pages,
        current_session_id=command.current_session_id,
        bucket=command.bucket,
        cutoff_timestamp=cutoff_timestamp,
        minimum_historical_sessions=command.minimum_historical_sessions,
        output_path=command.bundle_output_path,
        allow_live_data=True,
    )
    preflight_request = ExplicitAlpacaRvolCapturePreflightRequest(
        capture_request=capture_request,
        metadata_records=records,
        metadata_output_path=command.metadata_output_path,
        report_output_path=command.report_output_path,
    )
    return capture_and_preflight_explicit_alpaca_rvol_bundle(
        fetcher,
        preflight_request,
    )


def render_manual_explicit_alpaca_rvol_capture_command_error(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
    error: BaseException,
) -> str:
    return "\n".join(
        [
            "Market Sentry Manual Alpaca RVOL Capture Preflight",
            f"Metadata Input Path: {_display_path(command.metadata_input_path)}",
            f"Metadata Path: {_display_path(command.metadata_output_path)}",
            f"Bundle Path: {_display_path(command.bundle_output_path)}",
            f"Report Path: {_display_path(command.report_output_path)}",
            "Result: COMMAND_ERROR",
            f"Error: {str(error) or error.__class__.__name__}",
            MANUAL_EXPLICIT_ALPACA_CAPTURE_COMMAND_NOTE,
        ]
    )


def render_manual_explicit_alpaca_rvol_capture_error(
    command: ManualExplicitAlpacaRvolCaptureCommandRequest,
    error: BaseException,
) -> str:
    return "\n".join(
        [
            "Market Sentry Manual Alpaca RVOL Capture Preflight",
            f"Metadata Input Path: {_display_path(command.metadata_input_path)}",
            f"Metadata Path: {_display_path(command.metadata_output_path)}",
            f"Bundle Path: {_display_path(command.bundle_output_path)}",
            f"Report Path: {_display_path(command.report_output_path)}",
            "Result: ERROR",
            f"Error Type: {error.__class__.__name__}",
            f"Error: {str(error) or error.__class__.__name__}",
            MANUAL_EXPLICIT_ALPACA_CAPTURE_OPERATIONAL_NOTE,
        ]
    )


def render_manual_explicit_alpaca_rvol_capture_stopped_report(
    result: ExplicitAlpacaRvolCapturePreflightResult,
    command: ManualExplicitAlpacaRvolCaptureCommandRequest | None = None,
) -> str:
    capture_status = (
        result.capture_result.status if result.capture_result is not None else "N/A"
    )
    metadata_input_path = command.metadata_input_path if command is not None else None
    return "\n".join(
        [
            "Market Sentry Manual Alpaca RVOL Capture Preflight",
            f"Metadata Input Path: {_display_path(metadata_input_path)}",
            f"Metadata Path: {_display_path(result.metadata_path)}",
            f"Bundle Path: {_display_path(result.bundle_path)}",
            f"Report Path: {_display_path(result.report_path)}",
            "Input Mode: EXPLICIT_ALPACA_CAPTURE",
            f"Capture: {capture_status}",
            f"Result: {result.status}",
            f"Reason: {result.reason or 'N/A'}",
            MANUAL_EXPLICIT_ALPACA_CAPTURE_OPERATIONAL_NOTE,
        ]
    )


def is_manual_explicit_alpaca_rvol_capture_success(
    result: ExplicitAlpacaRvolCapturePreflightResult,
) -> bool:
    return is_explicit_alpaca_rvol_capture_preflight_success(result)
