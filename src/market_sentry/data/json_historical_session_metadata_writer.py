from collections.abc import Mapping, Sequence
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any


class JsonHistoricalSessionMetadataWriteError(ValueError):
    """Raised when metadata records cannot be represented as canonical JSON."""


def _metadata_error(message: str) -> JsonHistoricalSessionMetadataWriteError:
    return JsonHistoricalSessionMetadataWriteError(message)


def _validate_records(records: Sequence[object]) -> None:
    if isinstance(records, str | bytes | bytearray | memoryview):
        raise _metadata_error("INVALID_RECORDS_SEQUENCE")
    if not isinstance(records, Sequence):
        raise _metadata_error("INVALID_RECORDS_SEQUENCE")


def _datetime_tag(value: datetime) -> dict[str, str]:
    rendered = value.isoformat()
    if rendered.endswith("+00:00"):
        rendered = f"{rendered[:-6]}Z"
    return {"$datetime": rendered}


def _encode_json_value(value: Any, path: str) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _metadata_error(f"NON_FINITE_FLOAT:{path}")
        return value
    if isinstance(value, datetime):
        return _datetime_tag(value)
    if isinstance(value, list | tuple):
        return [
            _encode_json_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        encoded: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise _metadata_error(f"INVALID_MAPPING_KEY:{path}")
            encoded[key] = _encode_json_value(item, f"{path}.{key}")
        return encoded
    raise _metadata_error(f"UNSUPPORTED_VALUE:{path}")


def render_local_historical_session_metadata(
    records: Sequence[object],
) -> str:
    """Return canonical schema-version-one metadata JSON text."""

    _validate_records(records)
    envelope = {
        "records": [
            _encode_json_value(record, f"records[{index}]")
            for index, record in enumerate(records)
        ],
        "schema_version": 1,
    }
    return (
        json.dumps(
            envelope,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def write_local_historical_session_metadata(
    path: Path,
    records: Sequence[object],
) -> None:
    """Write one canonical local metadata JSON file."""

    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path.")
    rendered = render_local_historical_session_metadata(records)
    path.write_text(rendered, encoding="utf-8")
