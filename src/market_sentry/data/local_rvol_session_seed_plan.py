"""Explicit local RVOL session-plan loader and metadata seed builder."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from types import MappingProxyType

from market_sentry.data.historical_session_assembly import (
    HistoricalIntradaySessionMetadata,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
    HistoricalSessionManifestResult,
    HistoricalSessionManifestStatus,
    adapt_historical_session_manifest,
)
from market_sentry.data.json_historical_session_metadata_writer import (
    write_local_historical_session_metadata,
)


ROOT_FIELDS = (
    "schema_version",
    "symbol",
    "bucket",
    "current_session_id",
    "sessions",
)
SESSION_FIELDS = (
    "session_id",
    "session_start_timestamp",
    "session_end_timestamp",
    "cutoff_timestamp",
    "is_complete",
)


class LocalRvolSessionSeedPlanError(ValueError):
    """Raised when an explicit local RVOL session plan cannot create metadata."""


@dataclass(frozen=True)
class LocalRvolSessionSeedPlan:
    path: Path
    request: HistoricalSessionManifestRequest
    raw_manifest_records: tuple[Mapping[str, object], ...]


@dataclass(frozen=True)
class LocalRvolSessionSeedBuildResult:
    plan: LocalRvolSessionSeedPlan
    manifest_result: HistoricalSessionManifestResult
    metadata_records: tuple[HistoricalIntradaySessionMetadata, ...]


def _plan_error(message: str) -> LocalRvolSessionSeedPlanError:
    return LocalRvolSessionSeedPlanError(message)


def _unknown_field(payload: Mapping[str, object], allowed: tuple[str, ...], path: str) -> None:
    allowed_fields = set(allowed)
    for key in payload:
        if key not in allowed_fields:
            field_path = key if path == "" else f"{path}.{key}"
            raise _plan_error(f"UNKNOWN_FIELD:{field_path}")


def _require_fields(payload: Mapping[str, object], fields: tuple[str, ...], path: str) -> None:
    for field_name in fields:
        if field_name not in payload:
            field_path = field_name if path == "" else f"{path}.{field_name}"
            raise _plan_error(f"MISSING_REQUIRED_FIELD:{field_path}")


def _string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise _plan_error(f"INVALID_STRING:{path}")
    if value.strip() == "":
        raise _plan_error(f"EMPTY_STRING:{path}")
    return value


def _timestamp(value: object, path: str) -> datetime:
    timestamp_text = _string(value, path)
    parse_value = (
        f"{timestamp_text[:-1]}+00:00"
        if timestamp_text.endswith("Z")
        else timestamp_text
    )
    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError as exc:
        raise _plan_error(f"INVALID_TIMESTAMP:{path}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _plan_error(f"NAIVE_TIMESTAMP:{path}")
    return parsed


def _boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise _plan_error(f"INVALID_BOOLEAN:{path}")
    return value


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _protected_record(record: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(record))


def _record_from_session(
    *,
    symbol: str,
    bucket: str,
    session: Mapping[str, object],
    index: int,
) -> Mapping[str, object]:
    path = f"sessions[{index}]"
    _unknown_field(session, SESSION_FIELDS, path)
    _require_fields(session, SESSION_FIELDS, path)

    return _protected_record(
        {
            "symbol": symbol,
            "session_id": _string(session["session_id"], f"{path}.session_id"),
            "bucket": bucket,
            "session_start_timestamp": _timestamp(
                session["session_start_timestamp"],
                f"{path}.session_start_timestamp",
            ),
            "session_end_timestamp": _timestamp(
                session["session_end_timestamp"],
                f"{path}.session_end_timestamp",
            ),
            "cutoff_timestamp": _timestamp(
                session["cutoff_timestamp"],
                f"{path}.cutoff_timestamp",
            ),
            "is_complete": _boolean(session["is_complete"], f"{path}.is_complete"),
        }
    )


def _first_manifest_failure(result: HistoricalSessionManifestResult) -> tuple[str, str]:
    for record_result in result.record_results:
        if record_result.status != "OK":
            return str(record_result.index), record_result.reason or record_result.status
    return "N/A", "N/A"


def _metadata_record_mapping(
    record: HistoricalIntradaySessionMetadata,
) -> Mapping[str, object]:
    return {
        "symbol": record.symbol,
        "session_id": record.session_id,
        "bucket": record.bucket,
        "session_start_timestamp": record.session_start_timestamp,
        "session_end_timestamp": record.session_end_timestamp,
        "cutoff_timestamp": record.cutoff_timestamp,
        "is_complete": record.is_complete,
    }


def load_local_rvol_session_seed_plan(path: Path) -> LocalRvolSessionSeedPlan:
    """Load one explicit JSON session plan without writing output."""

    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path.")

    payload = _load_json(path)
    if not isinstance(payload, Mapping):
        raise _plan_error("INVALID_ENVELOPE_ROOT")

    _unknown_field(payload, ROOT_FIELDS, "")
    _require_fields(payload, ROOT_FIELDS, "")

    schema_version = payload["schema_version"]
    if not (type(schema_version) is int and schema_version == 1):
        raise _plan_error("INVALID_SCHEMA_VERSION")

    symbol = _string(payload["symbol"], "symbol")
    bucket = _string(payload["bucket"], "bucket")
    current_session_id = _string(payload["current_session_id"], "current_session_id")
    sessions = payload["sessions"]
    if not isinstance(sessions, list):
        raise _plan_error("INVALID_SEQUENCE:sessions")
    if not sessions:
        raise _plan_error("EMPTY_SESSIONS")

    records: list[Mapping[str, object]] = []
    for index, item in enumerate(sessions):
        if not isinstance(item, Mapping):
            raise _plan_error(f"INVALID_MAPPING:sessions[{index}]")
        records.append(
            _record_from_session(
                symbol=symbol,
                bucket=bucket,
                session=item,
                index=index,
            )
        )

    return LocalRvolSessionSeedPlan(
        path=path,
        request=HistoricalSessionManifestRequest(
            symbol=symbol,
            bucket=bucket,
            current_session_id=current_session_id,
        ),
        raw_manifest_records=tuple(records),
    )


def build_local_rvol_session_seed(
    plan: LocalRvolSessionSeedPlan,
) -> LocalRvolSessionSeedBuildResult:
    """Validate one plan through the existing historical-session manifest."""

    if not isinstance(plan, LocalRvolSessionSeedPlan):
        raise TypeError("plan must be a LocalRvolSessionSeedPlan.")

    manifest_result = adapt_historical_session_manifest(
        plan.raw_manifest_records,
        plan.request,
    )
    if manifest_result.status != HistoricalSessionManifestStatus.OK:
        index, reason = _first_manifest_failure(manifest_result)
        raise _plan_error(
            "HISTORICAL_SESSION_MANIFEST_INVALID:"
            f"{manifest_result.status}:{index}:{reason}"
        )
    return LocalRvolSessionSeedBuildResult(
        plan=plan,
        manifest_result=manifest_result,
        metadata_records=manifest_result.metadata_records,
    )


def write_local_rvol_session_seed(
    output_path: Path,
    plan: LocalRvolSessionSeedPlan,
) -> LocalRvolSessionSeedBuildResult:
    """Build and write one canonical metadata seed using the existing writer."""

    if not isinstance(output_path, Path):
        raise TypeError("output_path must be a pathlib.Path.")

    result = build_local_rvol_session_seed(plan)
    write_local_historical_session_metadata(
        output_path,
        tuple(_metadata_record_mapping(record) for record in result.metadata_records),
    )
    return result
