"""Deterministic offline workflow scenarios for manifest-to-harness runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
)
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_baseline_composition import (
    HistoricalBaselineCompositionStatus,
)
from market_sentry.data.historical_session_assembly import (
    HistoricalSessionAssemblyStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRecordStatus,
    HistoricalSessionManifestRequest,
    HistoricalSessionManifestStatus,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
    HistoricalToTodRvolRunStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessStatus,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeStatus


SYMBOL = "RVOL"
BUCKET = "09:35"
CURRENT_SESSION_ID = "CURRENT-001"
MINIMUM_HISTORICAL_SESSIONS = 20


@dataclass(frozen=True)
class ManifestToHarnessWorkflowScenario:
    """Deterministic complete workflow inputs and expected artifacts."""

    name: str
    raw_manifest_records: tuple[object, ...]
    manifest_request: HistoricalSessionManifestRequest
    page: AlpacaHistoricalBarsPage
    current_series: IntradayVolumeSeriesInput
    harness_request: HistoricalToTodRvolRunRequest
    expected_coordinator_status: str
    expected_coordinator_reason: str | None
    expected_manifest_status: str
    expected_manifest_record_statuses: tuple[str, ...]
    expected_harness_status: str
    expected_baseline_status: str
    expected_final_status: str
    expected_time_of_day_status: str | None
    expected_assembly_statuses: tuple[str, ...]
    expected_relative_volume: float | None


def _timestamp(day: int, minute: int) -> datetime:
    return datetime(2026, 1, day, 9, minute, tzinfo=timezone.utc)


def _timestamp_text(day: int, minute: int) -> str:
    return f"2026-01-{day:02d}T09:{minute:02d}:00Z"


def _historical_session_id(index: int) -> str:
    return f"HIST-{index:02d}"


def _protected_record(record: dict[str, object]) -> MappingProxyType:
    return MappingProxyType(dict(record))


def _raw_manifest_record(
    session_id: str,
    *,
    day: int,
    include_bucket: bool = True,
) -> MappingProxyType:
    record: dict[str, object] = {
        "symbol": SYMBOL,
        "session_id": session_id,
        "session_start_timestamp": _timestamp(day, 30),
        "session_end_timestamp": datetime(2026, 1, day, 10, 0, tzinfo=timezone.utc),
        "cutoff_timestamp": _timestamp(day, 35),
        "is_complete": True,
    }
    if include_bucket:
        record["bucket"] = BUCKET
    return _protected_record(record)


def _valid_manifest_records(count: int = 20) -> tuple[object, ...]:
    return tuple(
        _raw_manifest_record(_historical_session_id(index), day=index + 1)
        for index in range(1, count + 1)
    )


def _raw_bar(day: int, minute: int, volume: float | int) -> dict[str, object]:
    return {"t": _timestamp_text(day, minute), "v": volume}


def _valid_bars(
    count: int = 20,
    *,
    volume: float | int = 100,
) -> tuple[dict[str, object], ...]:
    return tuple(_raw_bar(index + 1, 35, volume) for index in range(1, count + 1))


def _page(
    bars: tuple[dict[str, object], ...],
    *,
    next_page_token: str | None = None,
) -> AlpacaHistoricalBarsPage:
    return AlpacaHistoricalBarsPage(
        requested_symbols=(SYMBOL,),
        bars_by_symbol={SYMBOL: bars},
        next_page_token=next_page_token,
    )


def _current_series(
    *,
    symbol: str = SYMBOL,
    volume: float | int | bool = 200,
) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol=symbol,
        session_id=CURRENT_SESSION_ID,
        bucket=BUCKET,
        cutoff_timestamp=_timestamp(31, 35),
        bars=(IntradayVolumeBar(timestamp=_timestamp(31, 35), volume=volume),),
    )


def _manifest_request(*, symbol: Any = SYMBOL) -> HistoricalSessionManifestRequest:
    return HistoricalSessionManifestRequest(
        symbol=symbol,
        bucket=BUCKET,
        current_session_id=CURRENT_SESSION_ID,
    )


def _harness_request() -> HistoricalToTodRvolRunRequest:
    return HistoricalToTodRvolRunRequest(
        symbol=SYMBOL,
        bucket=BUCKET,
        current_session_id=CURRENT_SESSION_ID,
        page_collection_complete=True,
        minimum_historical_sessions=MINIMUM_HISTORICAL_SESSIONS,
    )


def _scenario(
    *,
    name: str,
    raw_manifest_records: tuple[object, ...],
    page: AlpacaHistoricalBarsPage,
    current_series: IntradayVolumeSeriesInput,
    manifest_request: HistoricalSessionManifestRequest | None = None,
    expected_coordinator_status: str,
    expected_coordinator_reason: str | None,
    expected_manifest_status: str,
    expected_manifest_record_statuses: tuple[str, ...],
    expected_harness_status: str,
    expected_baseline_status: str,
    expected_final_status: str,
    expected_time_of_day_status: str | None,
    expected_assembly_statuses: tuple[str, ...],
    expected_relative_volume: float | None,
) -> ManifestToHarnessWorkflowScenario:
    return ManifestToHarnessWorkflowScenario(
        name=name,
        raw_manifest_records=raw_manifest_records,
        manifest_request=(
            _manifest_request() if manifest_request is None else manifest_request
        ),
        page=page,
        current_series=current_series,
        harness_request=_harness_request(),
        expected_coordinator_status=expected_coordinator_status,
        expected_coordinator_reason=expected_coordinator_reason,
        expected_manifest_status=expected_manifest_status,
        expected_manifest_record_statuses=expected_manifest_record_statuses,
        expected_harness_status=expected_harness_status,
        expected_baseline_status=expected_baseline_status,
        expected_final_status=expected_final_status,
        expected_time_of_day_status=expected_time_of_day_status,
        expected_assembly_statuses=expected_assembly_statuses,
        expected_relative_volume=expected_relative_volume,
    )


def _successful_expected(
    *,
    coordinator_status: str = ManifestToHarnessStatus.OK,
    coordinator_reason: str | None = None,
    manifest_status: str = HistoricalSessionManifestStatus.OK,
    manifest_record_statuses: tuple[str, ...] = (
        HistoricalSessionManifestRecordStatus.OK,
    )
    * 20,
) -> dict[str, object]:
    return {
        "expected_coordinator_status": coordinator_status,
        "expected_coordinator_reason": coordinator_reason,
        "expected_manifest_status": manifest_status,
        "expected_manifest_record_statuses": manifest_record_statuses,
        "expected_harness_status": HistoricalToTodRvolRunStatus.OK,
        "expected_baseline_status": HistoricalBaselineCompositionStatus.OK,
        "expected_final_status": CurrentSessionTimeOfDayRvolStatus.OK,
        "expected_time_of_day_status": TimeOfDayRelativeVolumeStatus.OK,
        "expected_assembly_statuses": (HistoricalSessionAssemblyStatus.OK,) * 20,
        "expected_relative_volume": 2.0,
    }


def _harness_failure_expected(
    *,
    manifest_status: str = HistoricalSessionManifestStatus.OK,
    manifest_record_statuses: tuple[str, ...] = (
        HistoricalSessionManifestRecordStatus.OK,
    )
    * 20,
    baseline_status: str,
    final_status: str,
    time_of_day_status: str | None,
    assembly_statuses: tuple[str, ...],
) -> dict[str, object]:
    return {
        "expected_coordinator_status": ManifestToHarnessStatus.HARNESS_FAILED,
        "expected_coordinator_reason": "HARNESS_FAILED:FINAL_COMPOSITION_FAILED",
        "expected_manifest_status": manifest_status,
        "expected_manifest_record_statuses": manifest_record_statuses,
        "expected_harness_status": HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
        "expected_baseline_status": baseline_status,
        "expected_final_status": final_status,
        "expected_time_of_day_status": time_of_day_status,
        "expected_assembly_statuses": assembly_statuses,
        "expected_relative_volume": None,
    }


def _valid_manifest_valid_rvol() -> ManifestToHarnessWorkflowScenario:
    return _scenario(
        name="valid_manifest_valid_rvol",
        raw_manifest_records=_valid_manifest_records(),
        page=_page(_valid_bars()),
        current_series=_current_series(),
        **_successful_expected(),
    )


def _partial_manifest_valid_rvol() -> ManifestToHarnessWorkflowScenario:
    records = _valid_manifest_records() + (
        _raw_manifest_record("MISSING-BUCKET", day=30, include_bucket=False),
    )
    return _scenario(
        name="partial_manifest_valid_rvol",
        raw_manifest_records=records,
        page=_page(_valid_bars()),
        current_series=_current_series(),
        **_successful_expected(
            coordinator_status=ManifestToHarnessStatus.MANIFEST_PARTIAL,
            coordinator_reason=ManifestToHarnessStatus.MANIFEST_PARTIAL,
            manifest_status=HistoricalSessionManifestStatus.PARTIAL,
            manifest_record_statuses=(
                (HistoricalSessionManifestRecordStatus.OK,) * 20
                + (HistoricalSessionManifestRecordStatus.MISSING_REQUIRED_FIELD,)
            ),
        ),
    )


def _invalid_manifest_empty_harness_input() -> ManifestToHarnessWorkflowScenario:
    return _scenario(
        name="invalid_manifest_empty_harness_input",
        raw_manifest_records=("not-a-mapping",),
        manifest_request=_manifest_request(symbol=" "),
        page=_page(_valid_bars()),
        current_series=_current_series(),
        expected_coordinator_status=ManifestToHarnessStatus.MANIFEST_FAILED,
        expected_coordinator_reason="MANIFEST_FAILED:INVALID_TARGET_SYMBOL",
        expected_manifest_status=HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL,
        expected_manifest_record_statuses=(),
        expected_harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
        expected_baseline_status=(
            HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
        ),
        expected_final_status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
        expected_time_of_day_status=None,
        expected_assembly_statuses=(),
        expected_relative_volume=None,
    )


def _duplicate_manifest_records() -> ManifestToHarnessWorkflowScenario:
    records = _valid_manifest_records() + (
        _raw_manifest_record("DUP-ONLY", day=30),
        _raw_manifest_record("DUP-ONLY", day=31),
    )
    return _scenario(
        name="duplicate_manifest_records",
        raw_manifest_records=records,
        page=_page(_valid_bars()),
        current_series=_current_series(),
        **_successful_expected(
            coordinator_status=ManifestToHarnessStatus.MANIFEST_PARTIAL,
            coordinator_reason=ManifestToHarnessStatus.MANIFEST_PARTIAL,
            manifest_status=HistoricalSessionManifestStatus.PARTIAL,
            manifest_record_statuses=(
                (HistoricalSessionManifestRecordStatus.OK,) * 20
                + (HistoricalSessionManifestRecordStatus.DUPLICATE_HISTORICAL_SESSION_ID,)
                * 2
            ),
        ),
    )


def _incomplete_historical_page() -> ManifestToHarnessWorkflowScenario:
    return _scenario(
        name="incomplete_historical_page",
        raw_manifest_records=_valid_manifest_records(),
        page=_page(_valid_bars(), next_page_token="next-page"),
        current_series=_current_series(),
        **_harness_failure_expected(
            baseline_status=(
                HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
            ),
            final_status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
            time_of_day_status=None,
            assembly_statuses=(
                HistoricalSessionAssemblyStatus.INCOMPLETE_PAGE_COLLECTION,
            )
            * 20,
        ),
    )


def _historical_cutoff_not_reached() -> ManifestToHarnessWorkflowScenario:
    bars = tuple(
        _raw_bar(index + 1, 34 if index == 20 else 35, 100)
        for index in range(1, 21)
    )
    return _scenario(
        name="historical_cutoff_not_reached",
        raw_manifest_records=_valid_manifest_records(),
        page=_page(bars),
        current_series=_current_series(),
        **_harness_failure_expected(
            baseline_status=(
                HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
            ),
            final_status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
            time_of_day_status=None,
            assembly_statuses=(
                (HistoricalSessionAssemblyStatus.OK,) * 19
                + (HistoricalSessionAssemblyStatus.CUT_OFF_NOT_REACHED,)
            ),
        ),
    )


def _current_invalid_volume() -> ManifestToHarnessWorkflowScenario:
    return _scenario(
        name="current_invalid_volume",
        raw_manifest_records=_valid_manifest_records(),
        page=_page(_valid_bars()),
        current_series=_current_series(volume=False),
        **_harness_failure_expected(
            baseline_status=HistoricalBaselineCompositionStatus.OK,
            final_status=(
                CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
            ),
            time_of_day_status=None,
            assembly_statuses=(HistoricalSessionAssemblyStatus.OK,) * 20,
        ),
    )


def _current_identity_mismatch() -> ManifestToHarnessWorkflowScenario:
    return _scenario(
        name="current_identity_mismatch",
        raw_manifest_records=_valid_manifest_records(),
        page=_page(_valid_bars()),
        current_series=_current_series(symbol="OTHER"),
        **_harness_failure_expected(
            baseline_status=HistoricalBaselineCompositionStatus.OK,
            final_status=CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SYMBOL,
            time_of_day_status=None,
            assembly_statuses=(HistoricalSessionAssemblyStatus.OK,) * 20,
        ),
    )


def _final_phase_13e_validation_failure() -> ManifestToHarnessWorkflowScenario:
    return _scenario(
        name="final_phase_13e_validation_failure",
        raw_manifest_records=_valid_manifest_records(),
        page=_page(_valid_bars(volume=1e308)),
        current_series=_current_series(volume=1e308),
        **_harness_failure_expected(
            baseline_status=HistoricalBaselineCompositionStatus.OK,
            final_status=CurrentSessionTimeOfDayRvolStatus.TIME_OF_DAY_RVOL_FAILED,
            time_of_day_status=(
                TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME
            ),
            assembly_statuses=(HistoricalSessionAssemblyStatus.OK,) * 20,
        ),
    )


def get_manifest_to_harness_workflow_scenarios() -> tuple[
    ManifestToHarnessWorkflowScenario,
    ...,
]:
    """Return fresh deterministic complete-workflow scenarios."""

    return (
        _valid_manifest_valid_rvol(),
        _partial_manifest_valid_rvol(),
        _invalid_manifest_empty_harness_input(),
        _duplicate_manifest_records(),
        _incomplete_historical_page(),
        _historical_cutoff_not_reached(),
        _current_invalid_volume(),
        _current_identity_mismatch(),
        _final_phase_13e_validation_failure(),
    )


def get_manifest_to_harness_workflow_scenario(
    name: str,
) -> ManifestToHarnessWorkflowScenario:
    """Return one workflow scenario by exact, case-sensitive name."""

    for scenario in get_manifest_to_harness_workflow_scenarios():
        if scenario.name == name:
            return scenario
    raise KeyError(name)
