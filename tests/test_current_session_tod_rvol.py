import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from market_sentry.data import current_session_tod_rvol
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolResult,
    CurrentSessionTimeOfDayRvolStatus,
    compose_current_session_time_of_day_rvol,
)
from market_sentry.data.historical_baseline_composition import (
    HistoricalBaselineCompositionResult,
    HistoricalBaselineCompositionStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayBucketStatus,
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
    calculate_cumulative_volume_at_bucket as real_calculate_cumulative_volume_at_bucket,
)
from market_sentry.data.time_of_day_rvol import (
    HistoricalCumulativeVolumeObservation,
    TimeOfDayRelativeVolumeResult,
    TimeOfDayRelativeVolumeStatus,
    calculate_time_of_day_relative_volume as real_calculate_time_of_day_relative_volume,
)


UTC = timezone.utc


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 2, 14, minute, tzinfo=UTC)


def observations(
    count: int = 20,
    *,
    bucket: str = "09:32",
    volume: int | float | bool | str = 100,
    duplicate_first_id: bool = False,
) -> tuple[HistoricalCumulativeVolumeObservation, ...]:
    items = [
        HistoricalCumulativeVolumeObservation(
            session_id=f"hist-{index:02d}",
            bucket=bucket,
            cumulative_volume=volume,
        )
        for index in range(count)
    ]
    if duplicate_first_id and count >= 2:
        items[1] = HistoricalCumulativeVolumeObservation(
            session_id=items[0].session_id,
            bucket=bucket,
            cumulative_volume=volume,
        )
    return tuple(items)


def baseline(
    *,
    symbol: str = "ABC",
    bucket: str = "09:32",
    current_session_id: str = "current",
    minimum_historical_sessions: int | None = 20,
    observations_value: tuple[HistoricalCumulativeVolumeObservation, ...] | None = None,
    status: str = HistoricalBaselineCompositionStatus.OK,
) -> HistoricalBaselineCompositionResult:
    baseline_observations = (
        observations() if observations_value is None else observations_value
    )
    return HistoricalBaselineCompositionResult(
        symbol=symbol,
        bucket=bucket,
        current_session_id=current_session_id,
        minimum_historical_sessions=minimum_historical_sessions,
        observations=baseline_observations,
        session_results=(),
        eligible_session_count=len(baseline_observations),
        status=status,
        reason=None if status == HistoricalBaselineCompositionStatus.OK else status,
    )


def current_series(
    *,
    symbol: str = "ABC",
    session_id: str = "current",
    bucket: str = "09:32",
    cutoff_minute: int = 32,
    volumes: tuple[int | float | bool | str, ...] = (100, 200),
    minutes: tuple[int, ...] = (31, 32),
) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        cutoff_timestamp=dt(cutoff_minute),
        bars=tuple(
            IntradayVolumeBar(timestamp=dt(minute), volume=volume)
            for minute, volume in zip(minutes, volumes)
        ),
    )


def test_successful_composition_calls_lower_layers_once_and_preserves_final_values(
    monkeypatch,
) -> None:
    current_calls = []
    final_calls = []

    def fake_current(series):
        current_calls.append(series)
        return real_calculate_cumulative_volume_at_bucket(series)

    def fake_final(symbol, bucket, current_volume, historical_observations, *, minimum_historical_sessions):
        final_calls.append(
            (
                symbol,
                bucket,
                current_volume,
                historical_observations,
                minimum_historical_sessions,
            )
        )
        return real_calculate_time_of_day_relative_volume(
            symbol,
            bucket,
            current_volume,
            historical_observations,
            minimum_historical_sessions=minimum_historical_sessions,
        )

    monkeypatch.setattr(
        current_session_tod_rvol,
        "calculate_cumulative_volume_at_bucket",
        fake_current,
    )
    monkeypatch.setattr(
        current_session_tod_rvol,
        "calculate_time_of_day_relative_volume",
        fake_final,
    )
    baseline_result = baseline()
    series = current_series()

    result = compose_current_session_time_of_day_rvol(series, baseline_result)

    assert result.status == CurrentSessionTimeOfDayRvolStatus.OK
    assert result.reason is None
    assert result.baseline_result is baseline_result
    assert result.current_result is not None
    assert result.current_result.cumulative_volume == 300.0
    assert result.calculation_input is not None
    assert result.calculation_input is not series
    assert result.calculation_input.historical_observations is baseline_result.observations
    assert result.time_of_day_result is not None
    assert result.time_of_day_result.relative_volume == 3.0
    assert result.time_of_day_result.historical_average_cumulative_volume == 100.0
    assert result.time_of_day_result.observation_count == 20
    assert current_calls == [series]
    assert final_calls == [
        ("ABC", "09:32", 300.0, baseline_result.observations, 20)
    ]


def test_baseline_failure_blocks_current_and_final_evaluation(monkeypatch) -> None:
    monkeypatch.setattr(
        current_session_tod_rvol,
        "calculate_cumulative_volume_at_bucket",
        lambda *args, **kwargs: pytest.fail("current evaluation should not run"),
    )
    monkeypatch.setattr(
        current_session_tod_rvol,
        "calculate_time_of_day_relative_volume",
        lambda *args, **kwargs: pytest.fail("final evaluation should not run"),
    )
    failed_baseline = baseline(
        observations_value=(),
        status=HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS,
    )

    result = compose_current_session_time_of_day_rvol(
        current_series(),
        failed_baseline,
    )

    assert result.status == CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED
    assert result.reason == (
        "BASELINE_FAILED:INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS"
    )
    assert result.current_result is None
    assert result.calculation_input is None
    assert result.time_of_day_result is None


@pytest.mark.parametrize(
    ("series", "phase_13f_status"),
    [
        (
            current_series(volumes=(False, 100)),
            IntradayBucketStatus.INVALID_INTRADAY_VOLUME,
        ),
        (
            current_series(volumes=(100, 200), minutes=(32, 31)),
            IntradayBucketStatus.OUT_OF_ORDER_INTRADAY_TIMESTAMP,
        ),
        (
            current_series(volumes=(100, 200), minutes=(31, 31)),
            IntradayBucketStatus.DUPLICATE_INTRADAY_TIMESTAMP,
        ),
        (
            current_series(volumes=(), minutes=()),
            IntradayBucketStatus.NO_INTRADAY_BARS,
        ),
        (
            current_series(cutoff_minute=30),
            IntradayBucketStatus.NO_BARS_AT_OR_BEFORE_CUTOFF,
        ),
    ],
)
def test_current_phase_13f_failures_preserve_exact_status_without_final_call(
    monkeypatch,
    series,
    phase_13f_status,
) -> None:
    monkeypatch.setattr(
        current_session_tod_rvol,
        "calculate_time_of_day_relative_volume",
        lambda *args, **kwargs: pytest.fail("final evaluation should not run"),
    )

    result = compose_current_session_time_of_day_rvol(series, baseline())

    assert result.status == (
        CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
    )
    assert result.reason == f"CURRENT_CUMULATIVE_VOLUME_FAILED:{phase_13f_status}"
    assert result.current_result is not None
    assert result.current_result.status == phase_13f_status
    assert result.calculation_input is None
    assert result.time_of_day_result is None


@pytest.mark.parametrize(
    ("baseline_result", "series", "status"),
    [
        (
            baseline(symbol="XYZ"),
            current_series(symbol="ABC"),
            CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SYMBOL,
        ),
        (
            baseline(bucket="09:33"),
            current_series(bucket="09:32"),
            CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_BUCKET,
        ),
        (
            baseline(current_session_id="Current"),
            current_series(session_id="current"),
            CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SESSION_ID,
        ),
    ],
)
def test_identity_mismatches_retain_current_result_without_final_call(
    monkeypatch,
    baseline_result,
    series,
    status,
) -> None:
    monkeypatch.setattr(
        current_session_tod_rvol,
        "calculate_time_of_day_relative_volume",
        lambda *args, **kwargs: pytest.fail("final evaluation should not run"),
    )

    result = compose_current_session_time_of_day_rvol(series, baseline_result)

    assert result.status == status
    assert result.reason == status
    assert result.current_result is not None
    assert result.current_result.status == IntradayBucketStatus.OK
    assert result.calculation_input is None
    assert result.time_of_day_result is None


def test_final_handoff_uses_exact_observations_and_minimum_and_preserves_result(
    monkeypatch,
) -> None:
    final_calls = []
    historical_observations = observations(
        20,
        volume=100,
    )
    baseline_result = baseline(
        observations_value=historical_observations,
        minimum_historical_sessions=20,
    )
    final_result = TimeOfDayRelativeVolumeResult(
        symbol="ABC",
        bucket="09:32",
        relative_volume=9.9,
        historical_average_cumulative_volume=30.0,
        status=TimeOfDayRelativeVolumeStatus.OK,
        reason=None,
        observation_count=20,
    )

    def fake_final(symbol, bucket, current_volume, supplied_observations, *, minimum_historical_sessions):
        final_calls.append(
            (
                symbol,
                bucket,
                current_volume,
                supplied_observations,
                minimum_historical_sessions,
            )
        )
        return final_result

    monkeypatch.setattr(
        current_session_tod_rvol,
        "calculate_time_of_day_relative_volume",
        fake_final,
    )

    result = compose_current_session_time_of_day_rvol(
        current_series(),
        baseline_result,
    )

    assert result.status == CurrentSessionTimeOfDayRvolStatus.OK
    assert result.time_of_day_result is final_result
    assert result.calculation_input is not None
    assert result.calculation_input.historical_observations is historical_observations
    assert final_calls == [("ABC", "09:32", 300.0, historical_observations, 20)]


def test_inconsistent_ok_baseline_with_too_few_observations_reaches_final_failure() -> None:
    baseline_result = baseline(
        observations_value=observations(19),
        minimum_historical_sessions=20,
    )

    result = compose_current_session_time_of_day_rvol(
        current_series(),
        baseline_result,
    )

    assert result.status == CurrentSessionTimeOfDayRvolStatus.TIME_OF_DAY_RVOL_FAILED
    assert result.reason == (
        "TIME_OF_DAY_RVOL_FAILED:INSUFFICIENT_HISTORICAL_OBSERVATIONS"
    )
    assert result.time_of_day_result is not None
    assert result.time_of_day_result.status == (
        TimeOfDayRelativeVolumeStatus.INSUFFICIENT_HISTORICAL_OBSERVATIONS
    )


@pytest.mark.parametrize(
    ("historical_observations", "phase_13e_status"),
    [
        (
            observations(20, duplicate_first_id=True),
            TimeOfDayRelativeVolumeStatus.DUPLICATE_HISTORICAL_SESSION_ID,
        ),
        (
            observations(20, volume=False),
            TimeOfDayRelativeVolumeStatus.INVALID_HISTORICAL_CUMULATIVE_VOLUME,
        ),
    ],
)
def test_inconsistent_ok_baseline_preserves_exact_final_failure_status(
    historical_observations,
    phase_13e_status,
) -> None:
    baseline_result = baseline(observations_value=historical_observations)

    result = compose_current_session_time_of_day_rvol(
        current_series(),
        baseline_result,
    )

    assert result.status == CurrentSessionTimeOfDayRvolStatus.TIME_OF_DAY_RVOL_FAILED
    assert result.reason == f"TIME_OF_DAY_RVOL_FAILED:{phase_13e_status}"
    assert result.time_of_day_result is not None
    assert result.time_of_day_result.status == phase_13e_status


def test_result_is_frozen_and_repeated_calls_share_no_mutable_state() -> None:
    baseline_result = baseline()
    series = current_series()

    first = compose_current_session_time_of_day_rvol(series, baseline_result)
    second = compose_current_session_time_of_day_rvol(series, baseline_result)

    assert isinstance(first, CurrentSessionTimeOfDayRvolResult)
    assert first is not second
    assert first.calculation_input is not None
    assert second.calculation_input is not None
    assert first.calculation_input is not second.calculation_input
    assert first.calculation_input.historical_observations is baseline_result.observations
    assert second.calculation_input.historical_observations is baseline_result.observations
    with pytest.raises(FrozenInstanceError):
        first.status = "changed"  # type: ignore[misc]


def test_status_values_are_stable_strings() -> None:
    assert CurrentSessionTimeOfDayRvolStatus.OK == "OK"
    assert CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED == "BASELINE_FAILED"
    assert (
        CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED
        == "CURRENT_CUMULATIVE_VOLUME_FAILED"
    )
    assert (
        CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SYMBOL
        == "MISMATCHED_CURRENT_SYMBOL"
    )
    assert (
        CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_BUCKET
        == "MISMATCHED_CURRENT_BUCKET"
    )
    assert (
        CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SESSION_ID
        == "MISMATCHED_CURRENT_SESSION_ID"
    )
    assert (
        CurrentSessionTimeOfDayRvolStatus.TIME_OF_DAY_RVOL_FAILED
        == "TIME_OF_DAY_RVOL_FAILED"
    )


def test_source_boundary_uses_only_approved_lower_level_components() -> None:
    source = inspect.getsource(current_session_tod_rvol)
    tree = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert imported_modules == {
        "__future__",
        "dataclasses",
        "market_sentry.data.historical_baseline_composition",
        "market_sentry.data.intraday_bucket_adapter",
        "market_sentry.data.time_of_day_rvol",
    }

    forbidden_terms = [
        "alpaca_historical_bars_fetcher",
        "alpaca_historical_bars_adapter",
        "historical_session_assembly",
        "compose_historical_baseline",
        "httptransport",
        "market_sentry.data.http",
        "market_sentry.data.http_stdlib",
        "market_sentry.data.factory",
        "market_sentry.config",
        "market_sentry.live_readiness",
        "relative_volume_calculator",
        "historical_volume_adapter",
        "intraday_rvol_harness",
        "intraday_rvol_fixture_provider",
        "intraday_rvol_candidate_composition_harness",
        "livecandidatebuilder",
        "livecomposedmarketdataprovider",
        "market_sentry.scanner",
        "market_sentry.alerts",
        "place_order",
        "execute_order",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered

    path_source = Path(
        "src/market_sentry/data/current_session_tod_rvol.py"
    ).read_text(encoding="utf-8")
    assert path_source == source
