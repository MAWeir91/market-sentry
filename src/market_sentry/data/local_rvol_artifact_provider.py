from collections.abc import Sequence
from dataclasses import dataclass

from market_sentry.data.local_rvol_artifact_manifest import (
    LocalRvolArtifact,
    LocalRvolArtifactManifest,
)
from market_sentry.data.relative_volume import normalize_symbols
from market_sentry.local_json_bundle_preflight_cli import (
    ManualLocalJsonBundlePreflightResult,
    is_manual_local_json_bundle_preflight_success,
    run_manual_local_json_bundle_preflight,
)


class LocalRvolArtifactProviderError(ValueError):
    """Raised when an explicit local artifact cannot yield usable RVOL."""


@dataclass(frozen=True)
class LocalRvolArtifactPreflightResult:
    symbol: str
    artifact: LocalRvolArtifact
    preflight_result: ManualLocalJsonBundlePreflightResult


class LocalRvolArtifactProvider:
    """Read-only RVOL provider backed by explicit local artifact paths."""

    def __init__(self, manifest: LocalRvolArtifactManifest) -> None:
        self.manifest = manifest
        self._latest_results: tuple[LocalRvolArtifactPreflightResult, ...] = ()

    @property
    def latest_results(self) -> tuple[LocalRvolArtifactPreflightResult, ...]:
        return self._latest_results

    def get_relative_volumes(
        self,
        symbols: Sequence[str],
    ) -> dict[str, float]:
        requested_symbols = normalize_symbols(symbols)
        if not requested_symbols:
            self._latest_results = ()
            return {}

        artifacts_by_symbol = {
            artifact.symbol: artifact for artifact in self.manifest.artifacts
        }
        for symbol in requested_symbols:
            if symbol not in artifacts_by_symbol:
                raise LocalRvolArtifactProviderError(f"MISSING_ARTIFACT:{symbol}")

        results: list[LocalRvolArtifactPreflightResult] = []
        relative_volumes: dict[str, float] = {}

        for symbol in requested_symbols:
            artifact = artifacts_by_symbol[symbol]

            preflight_result = run_manual_local_json_bundle_preflight(
                artifact.metadata_path,
                artifact.bundle_path,
            )
            wrapped = LocalRvolArtifactPreflightResult(
                symbol=symbol,
                artifact=artifact,
                preflight_result=preflight_result,
            )
            results.append(wrapped)

            if not is_manual_local_json_bundle_preflight_success(preflight_result):
                self._latest_results = tuple(results)
                raise LocalRvolArtifactProviderError(
                    f"ARTIFACT_PREFLIGHT_FAILED:{symbol}"
                )

            workflow_result = preflight_result.preflight_result.workflow_result
            bridge = workflow_result.workflow_bridge_result
            coordinator = bridge.workflow_result if bridge is not None else None
            harness = coordinator.harness_result if coordinator is not None else None
            final = harness.final_result if harness is not None else None
            tod = final.time_of_day_result if final is not None else None
            relative_volume = tod.relative_volume if tod is not None else None
            if relative_volume is None:
                self._latest_results = tuple(results)
                raise LocalRvolArtifactProviderError(f"MISSING_RVOL:{symbol}")

            relative_volumes[symbol] = float(relative_volume)

        self._latest_results = tuple(results)
        return relative_volumes
