from dataclasses import dataclass
import json
from pathlib import Path

from market_sentry.data.local_rvol_artifact_manifest import LocalRvolArtifact
from market_sentry.data.relative_volume import normalize_symbol


class LocalRvolArtifactManifestWriteError(ValueError):
    """Raised when an explicit local RVOL artifact manifest cannot be written."""


@dataclass(frozen=True)
class LocalRvolArtifactManifestWriteRequest:
    output_path: Path
    artifacts: tuple[LocalRvolArtifact, ...]


def _write_error(message: str) -> LocalRvolArtifactManifestWriteError:
    return LocalRvolArtifactManifestWriteError(message)


def validate_local_rvol_artifact_manifest_write_request(
    request: LocalRvolArtifactManifestWriteRequest,
) -> tuple[LocalRvolArtifact, ...]:
    if not isinstance(request, LocalRvolArtifactManifestWriteRequest):
        raise TypeError("request must be a LocalRvolArtifactManifestWriteRequest.")
    if not isinstance(request.output_path, Path):
        raise TypeError("output_path must be a pathlib.Path.")
    if not isinstance(request.artifacts, tuple):
        raise TypeError("artifacts must be a tuple.")
    if not request.artifacts:
        raise _write_error("MISSING_ARTIFACTS")

    normalized_artifacts: list[LocalRvolArtifact] = []
    seen_symbols: set[str] = set()
    for index, artifact in enumerate(request.artifacts):
        if not isinstance(artifact, LocalRvolArtifact):
            raise TypeError(f"artifacts[{index}] must be a LocalRvolArtifact.")
        if not isinstance(artifact.metadata_path, Path):
            raise TypeError(
                f"artifacts[{index}].metadata_path must be a pathlib.Path."
            )
        if not isinstance(artifact.bundle_path, Path):
            raise TypeError(
                f"artifacts[{index}].bundle_path must be a pathlib.Path."
            )

        if not isinstance(artifact.symbol, str):
            raise _write_error(f"EMPTY_SYMBOL:artifacts[{index}].symbol")
        symbol = normalize_symbol(artifact.symbol)
        if not symbol:
            raise _write_error(f"EMPTY_SYMBOL:artifacts[{index}].symbol")
        if symbol in seen_symbols:
            raise _write_error(f"DUPLICATE_SYMBOL:{symbol}")
        if artifact.metadata_path == artifact.bundle_path:
            raise _write_error(f"SAME_ARTIFACT_PATH:{symbol}")
        if (
            request.output_path == artifact.metadata_path
            or request.output_path == artifact.bundle_path
        ):
            raise _write_error(f"OUTPUT_PATH_CONFLICT:{symbol}")

        seen_symbols.add(symbol)
        normalized_artifacts.append(
            LocalRvolArtifact(
                symbol=symbol,
                metadata_path=artifact.metadata_path,
                bundle_path=artifact.bundle_path,
            )
        )

    return tuple(normalized_artifacts)


def render_local_rvol_artifact_manifest(
    artifacts: tuple[LocalRvolArtifact, ...],
) -> str:
    if not isinstance(artifacts, tuple):
        raise TypeError("artifacts must be a tuple.")
    rendered_artifacts: list[dict[str, str]] = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, LocalRvolArtifact):
            raise TypeError(f"artifacts[{index}] must be a LocalRvolArtifact.")
        rendered_artifacts.append(
            {
                "symbol": artifact.symbol,
                "metadata_path": str(artifact.metadata_path),
                "bundle_path": str(artifact.bundle_path),
            }
        )

    return (
        json.dumps(
            {
                "schema_version": 1,
                "artifacts": rendered_artifacts,
            },
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    )


def write_local_rvol_artifact_manifest(
    request: LocalRvolArtifactManifestWriteRequest,
) -> tuple[LocalRvolArtifact, ...]:
    normalized_artifacts = validate_local_rvol_artifact_manifest_write_request(request)
    rendered = render_local_rvol_artifact_manifest(normalized_artifacts)
    request.output_path.write_text(rendered, encoding="utf-8")
    return normalized_artifacts
