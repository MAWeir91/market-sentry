from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
)


class JsonHistoricalSessionMetadataFileSourceError(ValueError):
    pass


INVALID_ENVELOPE_ROOT = "INVALID_ENVELOPE_ROOT"
MISSING_SCHEMA_VERSION = "MISSING_SCHEMA_VERSION"
UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
MISSING_RECORDS_FIELD = "MISSING_RECORDS_FIELD"
INVALID_RECORDS_CONTAINER = "INVALID_RECORDS_CONTAINER"


def _decode_datetime_tag(value: dict[str, Any]) -> object:
    if len(value) != 1 or "$datetime" not in value:
        return value

    raw_value = value["$datetime"]
    if not isinstance(raw_value, str):
        return value

    parse_value = raw_value[:-1] + "+00:00" if raw_value.endswith("Z") else raw_value
    try:
        return datetime.fromisoformat(parse_value)
    except ValueError:
        return value


@dataclass(frozen=True)
class JsonHistoricalSessionMetadataFileSource:
    path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise TypeError("path must be a pathlib.Path instance.")

    def load_raw_manifest_records(
        self,
        request: HistoricalSessionManifestRequest,
    ) -> Sequence[object]:
        payload = json.loads(
            self.path.read_text(encoding="utf-8"),
            object_hook=_decode_datetime_tag,
        )

        if not isinstance(payload, Mapping):
            raise JsonHistoricalSessionMetadataFileSourceError(INVALID_ENVELOPE_ROOT)
        if "schema_version" not in payload:
            raise JsonHistoricalSessionMetadataFileSourceError(MISSING_SCHEMA_VERSION)
        schema_version = payload["schema_version"]
        if type(schema_version) is not int or schema_version != 1:
            raise JsonHistoricalSessionMetadataFileSourceError(
                UNSUPPORTED_SCHEMA_VERSION
            )
        if "records" not in payload:
            raise JsonHistoricalSessionMetadataFileSourceError(MISSING_RECORDS_FIELD)
        records = payload["records"]
        if not isinstance(records, list):
            raise JsonHistoricalSessionMetadataFileSourceError(
                INVALID_RECORDS_CONTAINER
            )
        return records
