from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from market_sentry.data.relative_volume import normalize_symbol


class LocalRvolArtifactManifestError(ValueError):
    """Raised for invalid explicit local RVOL artifact manifests."""


@dataclass(frozen=True)
class LocalRvolArtifact:
    symbol: str
    metadata_path: Path
    bundle_path: Path


@dataclass(frozen=True)
class LocalRvolArtifactManifest:
    path: Path
    artifacts: tuple[LocalRvolArtifact, ...]


def _manifest_error(message: str) -> LocalRvolArtifactManifestError:
    return LocalRvolArtifactManifestError(message)


def _required(mapping: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in mapping:
        field_path = key if not path else f"{path}.{key}"
        raise _manifest_error(f"MISSING_REQUIRED_FIELD:{field_path}")
    return mapping[key]


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise _manifest_error(f"INVALID_STRING:{path}")
    if value.strip() == "":
        raise _manifest_error(f"INVALID_STRING:{path}")
    return value


def _artifact(value: Any, index: int, seen_symbols: set[str]) -> LocalRvolArtifact:
    path = f"artifacts[{index}]"
    if not isinstance(value, Mapping):
        raise _manifest_error(f"INVALID_MAPPING:{path}")

    raw_symbol = _required(value, "symbol", path)
    if not isinstance(raw_symbol, str):
        raise _manifest_error(f"INVALID_STRING:{path}.symbol")
    symbol = normalize_symbol(raw_symbol)
    if not symbol:
        raise _manifest_error(f"EMPTY_SYMBOL:{path}.symbol")
    if symbol in seen_symbols:
        raise _manifest_error(f"DUPLICATE_SYMBOL:{symbol}")

    metadata_path = Path(_string(_required(value, "metadata_path", path), f"{path}.metadata_path"))
    bundle_path = Path(_string(_required(value, "bundle_path", path), f"{path}.bundle_path"))
    if metadata_path == bundle_path:
        raise _manifest_error(f"SAME_ARTIFACT_PATH:{symbol}")

    seen_symbols.add(symbol)
    return LocalRvolArtifact(
        symbol=symbol,
        metadata_path=metadata_path,
        bundle_path=bundle_path,
    )


def load_local_rvol_artifact_manifest(path: Path) -> LocalRvolArtifactManifest:
    """Load one explicit local RVOL artifact manifest."""

    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path.")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise _manifest_error("INVALID_ENVELOPE_ROOT")
    if "schema_version" not in payload:
        raise _manifest_error("MISSING_SCHEMA_VERSION")
    schema_version = payload["schema_version"]
    if type(schema_version) is not int or schema_version != 1:
        raise _manifest_error("UNSUPPORTED_SCHEMA_VERSION")

    artifacts_value = _required(payload, "artifacts", "")
    if not isinstance(artifacts_value, list):
        raise _manifest_error("INVALID_SEQUENCE:artifacts")

    seen_symbols: set[str] = set()
    artifacts = tuple(
        _artifact(item, index, seen_symbols)
        for index, item in enumerate(artifacts_value)
    )
    return LocalRvolArtifactManifest(path=path, artifacts=artifacts)
