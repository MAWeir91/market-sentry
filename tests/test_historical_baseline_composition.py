import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from market_sentry.data import historical_baseline_composition
from market_sentry.data.historical_baseline_composition import (
    HistoricalBaselineCompositionRequest,
    HistoricalBaselineCompositionStatus,
    HistoricalBaselineSessionStatus,
    compose_historical_baseline,
)
from market_sentry.data.historical_session_assembly import (
    HistoricalSessionAssemblyResult,
    HistoricalSessionAssemblyStatus,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
    calculate_cumulative_volume_at_bucket as real_calculate_cumulative_volume_at_bucket,
)
from market_sentry.data.time_of_day_rvol import DEFAULT_MINIMUM_HISTORICAL_SESSIONS


UTC = timezone.utc


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 2, 14, minute, tzinfo=UTC)


def series(
    session_id: str,
    *,
    symbol: str = "ABC",
    bucket: str = "09:32",
    volumes: tuple[int | float | bool | str, ...] = (100, 200),
    minutes: tuple[int, ...] = (31, 32),
) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        cutoff_timestamp=dt(32),
        bars=tuple(
            IntradayVolumeBar(timestamp=dt(minute), volume=volume)
            for minute, volume in zip(minutes, volumes)
        ),
    )


def assembly_result(
    session_id: str = "hist-1",
    *,
    status: str = HistoricalSessionAssemblyStatus.OK,
    intraday_series: IntradayVolumeSeriesInput | None = None,
    symbol: str = "ABC",
    bucket: str = "09:32",
) -> HistoricalSessionAssemblyResult:
    if intraday_series is None and status == HistoricalSessionAssemblyStatus.OK:
        intraday_series = series(session_id, symbol=symbol, bucket=bucket)
    return HistoricalSessionAssemblyResult(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        session_start_timestamp=dt(30),
        session_end_timestamp=dt(35),
        cutoff_timestamp=dt(32),
        intraday_series=intraday_series,
        status=status,
        reason=None if status == HistoricalSessionAssemblyStatus.OK else status,
        source_raw_bar_count=2,
        in_window_raw_bar_count=2,
        adapter_result=None,
    )


def request(**overrides) -> HistoricalBaselineCompositionRequest:
    values = {
        "symbol": "ABC",
        "bucket": "09:32",
        "current_session_id": "current",
    }
    values.update(overrides)
    return HistoricalBaselineCompositionRequest(**values)


def valid_assemblies(count: int, *, prefix: str = "hist") -> list[HistoricalSessionAssemblyResult]:
    return [
        assembly_result(
            f"{prefix}-{index:02d}",
            intraday_series=series(
                f"{prefix}-{index:02d}",
                volumes=(index + 1, (index + 1) * 10),
            ),
        )
        for index in range(count)
    ]


def test_twenty_valid_sessions_create_ordered_observations_and_ok_status() -> None:
    result = compose_historical_baseline(valid_assemblies(20), request())

    assert result.status == HistoricalBaselineCompositionStatus.OK
    assert result.eligible_session_count == 20
    assert len(result.observations) == 20
    assert [observation.session_id for observation in result.observations] == [
        f"hist-{index:02d}" for index in range(20)
    ]
    assert [session_result.status for session_result in result.session_results] == [
        HistoricalBaselineSessionStatus.OK
    ] * 20


def test_more_than_twenty_sessions_preserve_input_relative_order() -> None:
    result = compose_historical_baseline(valid_assemblies(22), request())

    assert result.status == HistoricalBaselineCompositionStatus.OK
    assert result.eligible_session_count == 22
    assert [observation.session_id for observation in result.observations] == [
        f"hist-{index:02d}" for index in range(22)
    ]


def test_nineteen_sessions_are_insufficient_but_partial_observations_remain() -> None:
    result = compose_historical_baseline(valid_assemblies(19), request())

    assert result.status == (
        HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
    )
    assert result.reason == (
        HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
    )
    assert result.eligible_session_count == 19
    assert len(result.observations) == 19
    assert len(result.session_results) == 19


def test_higher_minimum_controls_insufficient_and_success_behavior() -> None:
    insufficient = compose_historical_baseline(
        valid_assemblies(20),
        request(minimum_historical_sessions=21),
    )
    sufficient = compose_historical_baseline(
        valid_assemblies(21),
        request(minimum_historical_sessions=21),
    )

    assert insufficient.status == (
        HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
    )
    assert sufficient.status == HistoricalBaselineCompositionStatus.OK


@pytest.mark.parametrize(
    ("bad_request", "status"),
    [
        (request(symbol="   "), HistoricalBaselineCompositionStatus.INVALID_TARGET_SYMBOL),
        (request(bucket="   "), HistoricalBaselineCompositionStatus.INVALID_TARGET_BUCKET),
        (request(current_session_id="   "), HistoricalBaselineCompositionStatus.INVALID_CURRENT_SESSION_ID),
        (request(current_session_id=None), HistoricalBaselineCompositionStatus.INVALID_CURRENT_SESSION_ID),
        (request(minimum_historical_sessions=19), HistoricalBaselineCompositionStatus.INVALID_MINIMUM_HISTORICAL_SESSIONS),
        (request(minimum_historical_sessions=True), HistoricalBaselineCompositionStatus.INVALID_MINIMUM_HISTORICAL_SESSIONS),
        (request(minimum_historical_sessions="20"), HistoricalBaselineCompositionStatus.INVALID_MINIMUM_HISTORICAL_SESSIONS),
    ],
)
def test_invalid_request_inputs_do_not_evaluate_phase_13f(monkeypatch, bad_request, status) -> None:
    monkeypatch.setattr(
        historical_baseline_composition,
        "calculate_cumulative_volume_at_bucket",
        lambda *args: pytest.fail("Phase 13F should not be evaluated"),
    )

    result = compose_historical_baseline(valid_assemblies(1), bad_request)

    assert result.status == status
    assert result.reason == status
    assert result.observations == ()
    assert result.session_results == ()
    assert result.eligible_session_count == 0


def test_failed_phase_14d_result_preserves_assembly_status_without_phase_13f(monkeypatch) -> None:
    monkeypatch.setattr(
        historical_baseline_composition,
        "calculate_cumulative_volume_at_bucket",
        lambda *args: pytest.fail("Phase 13F should not be evaluated"),
    )
    failed = assembly_result(
        status=HistoricalSessionAssemblyStatus.CUT_OFF_NOT_REACHED,
        intraday_series=None,
    )

    result = compose_historical_baseline([failed], request())

    assert result.session_results[0].status == HistoricalBaselineSessionStatus.ASSEMBLY_FAILED
    assert result.session_results[0].reason == "ASSEMBLY_FAILED:CUT_OFF_NOT_REACHED"
    assert result.session_results[0].assembly_result is failed


def test_ok_assembly_with_no_series_is_missing_intraday_series() -> None:
    missing = HistoricalSessionAssemblyResult(
        symbol="ABC",
        session_id="hist-1",
        bucket="09:32",
        session_start_timestamp=dt(30),
        session_end_timestamp=dt(35),
        cutoff_timestamp=dt(32),
        intraday_series=None,
        status=HistoricalSessionAssemblyStatus.OK,
        reason=None,
    )

    result = compose_historical_baseline([missing], request())

    assert result.session_results[0].status == HistoricalBaselineSessionStatus.MISSING_INTRADAY_SERIES
    assert result.session_results[0].cumulative_result is None


@pytest.mark.parametrize(
    ("item", "status"),
    [
        (
            assembly_result("hist-1", intraday_series=series("hist-1", symbol="XYZ")),
            HistoricalBaselineSessionStatus.MISMATCHED_HISTORICAL_SYMBOL,
        ),
        (
            assembly_result("hist-1", intraday_series=series("hist-1", bucket="other")),
            HistoricalBaselineSessionStatus.MISMATCHED_HISTORICAL_BUCKET,
        ),
        (
            assembly_result("current", intraday_series=series(" current ")),
            HistoricalBaselineSessionStatus.CURRENT_SESSION_IN_HISTORY,
        ),
    ],
)
def test_target_mismatches_do_not_evaluate_phase_13f(monkeypatch, item, status) -> None:
    monkeypatch.setattr(
        historical_baseline_composition,
        "calculate_cumulative_volume_at_bucket",
        lambda *args: pytest.fail("Phase 13F should not be evaluated"),
    )

    result = compose_historical_baseline([item], request(current_session_id="current"))

    assert result.session_results[0].status == status


def test_duplicate_eligible_session_ids_reject_every_duplicate_without_phase_13f(monkeypatch) -> None:
    calls = []

    def fake_phase_13f(series_input):
        calls.append(series_input.session_id)
        return real_calculate_cumulative_volume_at_bucket(series_input)

    monkeypatch.setattr(
        historical_baseline_composition,
        "calculate_cumulative_volume_at_bucket",
        fake_phase_13f,
    )
    items = [
        assembly_result("dup", intraday_series=series("dup")),
        assembly_result(" dup ", intraday_series=series(" dup ")),
        assembly_result("Dup", intraday_series=series("Dup")),
    ]

    result = compose_historical_baseline(items, request())

    assert [session_result.status for session_result in result.session_results] == [
        HistoricalBaselineSessionStatus.DUPLICATE_HISTORICAL_SESSION_ID,
        HistoricalBaselineSessionStatus.DUPLICATE_HISTORICAL_SESSION_ID,
        HistoricalBaselineSessionStatus.OK,
    ]
    assert calls == ["Dup"]


def test_phase_13f_success_creates_exact_observation_from_cumulative_result() -> None:
    result = compose_historical_baseline([assembly_result("hist-A")], request())

    session_result = result.session_results[0]
    assert session_result.status == HistoricalBaselineSessionStatus.OK
    assert session_result.cumulative_result is not None
    assert session_result.observation is not None
    assert session_result.observation.session_id == session_result.cumulative_result.session_id
    assert session_result.observation.bucket == session_result.cumulative_result.bucket
    assert session_result.observation.cumulative_volume == (
        session_result.cumulative_result.cumulative_volume
    )


@pytest.mark.parametrize(
    ("bad_series", "phase_13f_status"),
    [
        (
            series("bad-volume", volumes=(False, 100)),
            "INVALID_INTRADAY_VOLUME",
        ),
        (
            series("out-of-order", volumes=(100, 200), minutes=(32, 31)),
            "OUT_OF_ORDER_INTRADAY_TIMESTAMP",
        ),
    ],
)
def test_phase_13f_failures_preserve_exact_lower_level_status(bad_series, phase_13f_status) -> None:
    result = compose_historical_baseline(
        [assembly_result(bad_series.session_id, intraday_series=bad_series)],
        request(),
    )

    session_result = result.session_results[0]
    assert session_result.status == HistoricalBaselineSessionStatus.CUMULATIVE_VOLUME_FAILED
    assert session_result.reason == f"CUMULATIVE_VOLUME_FAILED:{phase_13f_status}"
    assert session_result.cumulative_result is not None
    assert session_result.cumulative_result.status == phase_13f_status
    assert session_result.observation is None


def test_observations_include_only_successful_phase_13f_results_in_input_order() -> None:
    items = [
        assembly_result("hist-a", intraday_series=series("hist-a", volumes=(1, 2))),
        assembly_result("bad", intraday_series=series("bad", volumes=(False, 2))),
        assembly_result("hist-b", intraday_series=series("hist-b", volumes=(3, 4))),
    ]

    result = compose_historical_baseline(items, request())

    assert [observation.session_id for observation in result.observations] == [
        "hist-a",
        "hist-b",
    ]
    assert [observation.cumulative_volume for observation in result.observations] == [
        3.0,
        7.0,
    ]
    assert result.eligible_session_count == 2


def test_result_models_are_frozen_and_collections_are_tuples() -> None:
    result = compose_historical_baseline(valid_assemblies(1), request())

    assert isinstance(result.observations, tuple)
    assert isinstance(result.session_results, tuple)
    with pytest.raises(FrozenInstanceError):
        result.eligible_session_count = 99  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.session_results[0].status = "changed"  # type: ignore[misc]


def test_repeated_calls_share_no_mutable_state_and_inputs_remain_unchanged() -> None:
    items = valid_assemblies(1)
    original_series = items[0].intraday_series

    first = compose_historical_baseline(items, request())
    second = compose_historical_baseline(items, request())

    assert first is not second
    assert first.observations is not second.observations
    assert first.session_results is not second.session_results
    assert items[0].intraday_series is original_series


def test_source_boundary_uses_only_allowed_lower_level_components() -> None:
    source = inspect.getsource(historical_baseline_composition)
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

    assert not {
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.alpaca_historical_bars_adapter",
        "market_sentry.data.http",
        "market_sentry.data.http_stdlib",
        "market_sentry.data.factory",
        "market_sentry.config",
        "market_sentry.live_readiness",
        "market_sentry.data.live_provider_builder",
        "market_sentry.data.live_composed_provider",
        "market_sentry.scanner.engine",
        "market_sentry.alerts.generator",
    } & imported_modules
    forbidden_terms = [
        "assemble_historical_sessions_from_page",
        "calculate_time_of_day_relative_volume",
        "TimeOfDayRelativeVolumeInput",
        "AlpacaHistoricalBarsFetcher",
        "HttpTransport",
        "LiveCandidateBuilder",
        "StockCandidate",
        "place_order",
        "execute_order",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
