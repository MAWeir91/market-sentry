from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from market_sentry.data.relative_volume import normalize_symbol


class OneShotLiveComposedWorkflowPlanError(ValueError):
    """Raised when a one-shot live-composed workflow plan is invalid."""


@dataclass(frozen=True)
class OneShotLiveComposedWorkflowArtifact:
    symbol: str
    metadata_input_path: Path
    metadata_output_path: Path
    bundle_output_path: Path
    historical_start: str
    historical_end: str
    historical_max_pages: int
    current_start: str
    current_end: str
    current_max_pages: int
    current_session_id: str
    bucket: str
    cutoff: str
    minimum_historical_sessions: int
    timeframe: str
    page_limit: int
    sort: str


@dataclass(frozen=True)
class OneShotLiveComposedWorkflowPlan:
    path: Path
    manifest_output_path: Path
    artifacts: tuple[OneShotLiveComposedWorkflowArtifact, ...]


STRING_FIELDS = (
    "metadata_input_path",
    "metadata_output_path",
    "bundle_output_path",
    "historical_start",
    "historical_end",
    "current_start",
    "current_end",
    "current_session_id",
    "bucket",
    "cutoff",
    "timeframe",
    "sort",
)
INTEGER_FIELDS = (
    "historical_max_pages",
    "current_max_pages",
    "minimum_historical_sessions",
    "page_limit",
)


def _plan_error(message: str) -> OneShotLiveComposedWorkflowPlanError:
    return OneShotLiveComposedWorkflowPlanError(message)


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise _plan_error(f"INVALID_MAPPING:{path}")
    return value


def _string(value: Any, path: str) -> str:
    if type(value) is not str or value == "":
        raise _plan_error(f"INVALID_STRING:{path}")
    return value


def _integer(value: Any, path: str) -> int:
    if type(value) is not int:
        raise _plan_error(f"INVALID_INTEGER:{path}")
    return value


def _required(mapping: dict[str, Any], key: str, path: str) -> Any:
    if key not in mapping:
        raise _plan_error(f"MISSING_REQUIRED_FIELD:{path}")
    return mapping[key]


def _load_plan_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_one_shot_live_composed_workflow_plan(
    path: Path,
) -> OneShotLiveComposedWorkflowPlan:
    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path.")

    raw = _load_plan_json(path)
    if type(raw) is not dict:
        raise _plan_error("INVALID_ENVELOPE_ROOT")

    if "schema_version" not in raw:
        raise _plan_error("MISSING_SCHEMA_VERSION")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise _plan_error("UNSUPPORTED_SCHEMA_VERSION")

    manifest_output_path = Path(
        _string(
            _required(raw, "manifest_output_path", "manifest_output_path"),
            "manifest_output_path",
        )
    )

    artifacts_raw = _required(raw, "artifacts", "artifacts")
    if type(artifacts_raw) is not list:
        raise _plan_error("INVALID_SEQUENCE:artifacts")
    if not artifacts_raw:
        raise _plan_error("EMPTY_ARTIFACTS")

    artifacts: list[OneShotLiveComposedWorkflowArtifact] = []
    seen_symbols: set[str] = set()
    seen_metadata_inputs: dict[Path, str] = {}
    seen_outputs: dict[Path, str] = {}

    for index, raw_artifact in enumerate(artifacts_raw):
        artifact_path = f"artifacts[{index}]"
        artifact_mapping = _mapping(raw_artifact, artifact_path)
        raw_symbol = _required(artifact_mapping, "symbol", f"{artifact_path}.symbol")
        if type(raw_symbol) is not str:
            raise _plan_error(f"EMPTY_SYMBOL:{artifact_path}.symbol")
        strings = {
            field: _string(
                _required(artifact_mapping, field, f"{artifact_path}.{field}"),
                f"{artifact_path}.{field}",
            )
            for field in STRING_FIELDS
        }
        integers = {
            field: _integer(
                _required(artifact_mapping, field, f"{artifact_path}.{field}"),
                f"{artifact_path}.{field}",
            )
            for field in INTEGER_FIELDS
        }

        symbol = normalize_symbol(raw_symbol)
        if not symbol:
            raise _plan_error(f"EMPTY_SYMBOL:{artifact_path}.symbol")
        if symbol in seen_symbols:
            raise _plan_error(f"DUPLICATE_SYMBOL:{symbol}")
        if strings["sort"] not in {"asc", "desc"}:
            raise _plan_error(f"INVALID_SORT:{artifact_path}.sort")

        metadata_input_path = Path(strings["metadata_input_path"])
        metadata_output_path = Path(strings["metadata_output_path"])
        bundle_output_path = Path(strings["bundle_output_path"])

        capture_paths = (
            metadata_input_path,
            metadata_output_path,
            bundle_output_path,
        )
        if len(set(capture_paths)) != len(capture_paths):
            raise _plan_error(f"SAME_CAPTURE_PATH:{symbol}")
        if manifest_output_path in capture_paths:
            raise _plan_error(f"MANIFEST_OUTPUT_COLLISION:{symbol}")

        if metadata_input_path in seen_outputs:
            raise _plan_error(
                f"DUPLICATE_OUTPUT_PATH:{artifact_path}.metadata_input_path"
            )
        output_fields = (
            ("metadata_output_path", metadata_output_path),
            ("bundle_output_path", bundle_output_path),
        )
        for field_name, output_path in output_fields:
            field_path = f"{artifact_path}.{field_name}"
            if output_path in seen_outputs or output_path in seen_metadata_inputs:
                raise _plan_error(f"DUPLICATE_OUTPUT_PATH:{field_path}")

        seen_symbols.add(symbol)
        seen_metadata_inputs[metadata_input_path] = (
            f"{artifact_path}.metadata_input_path"
        )
        for field_name, output_path in output_fields:
            seen_outputs[output_path] = f"{artifact_path}.{field_name}"

        artifacts.append(
            OneShotLiveComposedWorkflowArtifact(
                symbol=symbol,
                metadata_input_path=metadata_input_path,
                metadata_output_path=metadata_output_path,
                bundle_output_path=bundle_output_path,
                historical_start=strings["historical_start"],
                historical_end=strings["historical_end"],
                historical_max_pages=integers["historical_max_pages"],
                current_start=strings["current_start"],
                current_end=strings["current_end"],
                current_max_pages=integers["current_max_pages"],
                current_session_id=strings["current_session_id"],
                bucket=strings["bucket"],
                cutoff=strings["cutoff"],
                minimum_historical_sessions=integers[
                    "minimum_historical_sessions"
                ],
                timeframe=strings["timeframe"],
                page_limit=integers["page_limit"],
                sort=strings["sort"],
            )
        )

    return OneShotLiveComposedWorkflowPlan(
        path=path,
        manifest_output_path=manifest_output_path,
        artifacts=tuple(artifacts),
    )
