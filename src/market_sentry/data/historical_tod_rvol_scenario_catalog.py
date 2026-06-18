"""Deterministic offline scenario inputs for historical-to-TOD RVOL runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

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
    HistoricalIntradaySessionMetadata,
    HistoricalSessionAssemblyStatus,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
    HistoricalToTodRvolRunStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeStatus


SYMBOL = "RVOL"
BUCKET = "09:35"
CURRENT_SESSION_ID = "CURRENT-001"
MINIMUM_HISTORICAL_SESSIONS = 20


@dataclass(frozen=True)
class HistoricalTodRvolScenario:
    """Deterministic raw inputs and expected stage statuses for one run."""

    name: str
    page: AlpacaHistoricalBarsPage
    historical_metadata_records: tuple[HistoricalIntradaySessionMetadata, ...]
    current_series: IntradayVolumeSeriesInput
    request: HistoricalToTodRvolRunRequest
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


def _raw_bar(day: int, minute: int, volume: float | int) -> dict[str, object]:
    return {"t": _timestamp_text(day, minute), "v": volume}


def _raw_bar_without_volume(day: int, minute: int) -> dict[str, object]:
    return {"t": _timestamp_text(day, minute)}


def _historical_session_id(index: int) -> str:
    return f"HIST-{index:02d}"


def _metadata_record(index: int) -> HistoricalIntradaySessionMetadata:
    day = index
    return HistoricalIntradaySessionMetadata(
        symbol=SYMBOL,
        session_id=_historical_session_id(index),
        bucket=BUCKET,
        session_start_timestamp=_timestamp(day, 30),
        session_end_timestamp=datetime(2026, 1, day, 10, 0, tzinfo=timezone.utc),
        cutoff_timestamp=_timestamp(day, 35),
        is_complete=True,
    )


def _metadata_records(count: int) -> tuple[HistoricalIntradaySessionMetadata, ...]:
    return tuple(_metadata_record(index) for index in range(1, count + 1))


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


def _request() -> HistoricalToTodRvolRunRequest:
    return HistoricalToTodRvolRunRequest(
        symbol=SYMBOL,
        bucket=BUCKET,
        current_session_id=CURRENT_SESSION_ID,
        page_collection_complete=True,
        minimum_historical_sessions=MINIMUM_HISTORICAL_SESSIONS,
    )


def _valid_bars(count: int, *, volume: float | int = 100) -> tuple[dict[str, object], ...]:
    return tuple(_raw_bar(index, 35, volume) for index in range(1, count + 1))


def _scenario(
    *,
    name: str,
    historical_count: int = 20,
    bars: tuple[dict[str, object], ...] | None = None,
    current: IntradayVolumeSeriesInput | None = None,
    next_page_token: str | None = None,
    expected_harness_status: str,
    expected_baseline_status: str,
    expected_final_status: str,
    expected_time_of_day_status: str | None,
    expected_assembly_statuses: tuple[str, ...],
    expected_relative_volume: float | None,
) -> HistoricalTodRvolScenario:
    page_bars = _valid_bars(historical_count) if bars is None else bars
    return HistoricalTodRvolScenario(
        name=name,
        page=_page(page_bars, next_page_token=next_page_token),
        historical_metadata_records=_metadata_records(historical_count),
        current_series=_current_series() if current is None else current,
        request=_request(),
        expected_harness_status=expected_harness_status,
        expected_baseline_status=expected_baseline_status,
        expected_final_status=expected_final_status,
        expected_time_of_day_status=expected_time_of_day_status,
        expected_assembly_statuses=expected_assembly_statuses,
        expected_relative_volume=expected_relative_volume,
    )


def _valid_20_session_baseline() -> HistoricalTodRvolScenario:
    return _scenario(
        name="valid_20_session_baseline",
        expected_harness_status=HistoricalToTodRvolRunStatus.OK,
        expected_baseline_status=HistoricalBaselineCompositionStatus.OK,
        expected_final_status=CurrentSessionTimeOfDayRvolStatus.OK,
        expected_time_of_day_status=TimeOfDayRelativeVolumeStatus.OK,
        expected_assembly_statuses=(HistoricalSessionAssemblyStatus.OK,) * 20,
        expected_relative_volume=2.0,
    )


def _insufficient_history() -> HistoricalTodRvolScenario:
    return _scenario(
        name="insufficient_history",
        historical_count=19,
        expected_harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
        expected_baseline_status=(
            HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
        ),
        expected_final_status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
        expected_time_of_day_status=None,
        expected_assembly_statuses=(HistoricalSessionAssemblyStatus.OK,) * 19,
        expected_relative_volume=None,
    )


def _incomplete_page_collection() -> HistoricalTodRvolScenario:
    return _scenario(
        name="incomplete_page_collection",
        next_page_token="next-page",
        expected_harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
        expected_baseline_status=(
            HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
        ),
        expected_final_status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
        expected_time_of_day_status=None,
        expected_assembly_statuses=(
            HistoricalSessionAssemblyStatus.INCOMPLETE_PAGE_COLLECTION,
        )
        * 20,
        expected_relative_volume=None,
    )


def _historical_session_cutoff_not_reached() -> HistoricalTodRvolScenario:
    bars = tuple(
        _raw_bar(index, 34 if index == 20 else 35, 100)
        for index in range(1, 21)
    )
    return _scenario(
        name="historical_session_cutoff_not_reached",
        bars=bars,
        expected_harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
        expected_baseline_status=(
            HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
        ),
        expected_final_status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
        expected_time_of_day_status=None,
        expected_assembly_statuses=(
            (HistoricalSessionAssemblyStatus.OK,) * 19
            + (HistoricalSessionAssemblyStatus.CUT_OFF_NOT_REACHED,)
        ),
        expected_relative_volume=None,
    )


def _historical_invalid_volume() -> HistoricalTodRvolScenario:
    bars = tuple(
        _raw_bar_without_volume(index, 35)
        if index == 20
        else _raw_bar(index, 35, 100)
        for index in range(1, 21)
    )
    return _scenario(
        name="historical_invalid_volume",
        bars=bars,
        expected_harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
        expected_baseline_status=(
            HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
        ),
        expected_final_status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
        expected_time_of_day_status=None,
        expected_assembly_statuses=(
            (HistoricalSessionAssemblyStatus.OK,) * 19
            + (HistoricalSessionAssemblyStatus.ADAPTER_FAILED,)
        ),
        expected_relative_volume=None,
    )


def _current_invalid_volume() -> HistoricalTodRvolScenario:
    return _scenario(
        name="current_invalid_volume",
        current=_current_series(volume=False),
        expected_harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
        expected_baseline_status=HistoricalBaselineCompositionStatus.OK,
        expected_final_status=(
            CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
        ),
        expected_time_of_day_status=None,
        expected_assembly_statuses=(HistoricalSessionAssemblyStatus.OK,) * 20,
        expected_relative_volume=None,
    )


def _current_identity_mismatch() -> HistoricalTodRvolScenario:
    return _scenario(
        name="current_identity_mismatch",
        current=_current_series(symbol="OTHER"),
        expected_harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
        expected_baseline_status=HistoricalBaselineCompositionStatus.OK,
        expected_final_status=CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SYMBOL,
        expected_time_of_day_status=None,
        expected_assembly_statuses=(HistoricalSessionAssemblyStatus.OK,) * 20,
        expected_relative_volume=None,
    )


def _final_phase_13e_validation_failure() -> HistoricalTodRvolScenario:
    return _scenario(
        name="final_phase_13e_validation_failure",
        bars=_valid_bars(20, volume=1e308),
        current=_current_series(volume=1e308),
        expected_harness_status=HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED,
        expected_baseline_status=HistoricalBaselineCompositionStatus.OK,
        expected_final_status=CurrentSessionTimeOfDayRvolStatus.TIME_OF_DAY_RVOL_FAILED,
        expected_time_of_day_status=(
            TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_AVERAGE_CUMULATIVE_VOLUME
        ),
        expected_assembly_statuses=(HistoricalSessionAssemblyStatus.OK,) * 20,
        expected_relative_volume=None,
    )


def get_historical_tod_rvol_scenarios() -> tuple[HistoricalTodRvolScenario, ...]:
    """Return fresh deterministic scenario inputs in stable order."""

    return (
        _valid_20_session_baseline(),
        _insufficient_history(),
        _incomplete_page_collection(),
        _historical_session_cutoff_not_reached(),
        _historical_invalid_volume(),
        _current_invalid_volume(),
        _current_identity_mismatch(),
        _final_phase_13e_validation_failure(),
    )


def get_historical_tod_rvol_scenario(name: str) -> HistoricalTodRvolScenario:
    """Return one scenario by exact, case-sensitive name."""

    for scenario in get_historical_tod_rvol_scenarios():
        if scenario.name == name:
            return scenario
    raise KeyError(name)
