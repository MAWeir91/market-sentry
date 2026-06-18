import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from market_sentry.data import historical_tod_rvol_harness
from market_sentry.data.alpaca_historical_bars_fetcher import AlpacaHistoricalBarsPage
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolResult,
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_baseline_composition import (
    HistoricalBaselineCompositionRequest,
    HistoricalBaselineCompositionResult,
    HistoricalBaselineCompositionStatus,
)
from market_sentry.data.historical_session_assembly import (
    HistoricalIntradaySessionMetadata,
    HistoricalSessionAssemblyResult,
    HistoricalSessionAssemblyStatus,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
    HistoricalToTodRvolRunResult,
    HistoricalToTodRvolRunStatus,
    run_historical_to_time_of_day_rvol,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.time_of_day_rvol import (
    DEFAULT_MINIMUM_HISTORICAL_SESSIONS,
    HistoricalCumulativeVolumeObservation,
    TimeOfDayRelativeVolumeResult,
    TimeOfDayRelativeVolumeStatus,
)


UTC = timezone.utc


def ts(day: int = 2, minute: int = 32) -> datetime:
    return datetime(2026, 1, day, 14, minute, tzinfo=UTC)


def raw_bar(day: int, minute: int, volume: int | float = 100) -> dict[str, object]:
    return {
        "t": f"2026-01-{day:02d}T14:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "c": 1.1,
    }


def page_for(*, symbol: str = "ABC", bars=()) -> AlpacaHistoricalBarsPage:
    normalized_symbol = symbol.strip().upper()
    return AlpacaHistoricalBarsPage(
        requested_symbols=(normalized_symbol,),
        bars_by_symbol={normalized_symbol: tuple(bars)},
        next_page_token=None,
    )


def metadata(
    session_id: str = "hist-01",
    *,
    symbol: str = "ABC",
    bucket: str = "09:32",
    day: int = 2,
    is_complete: bool = True,
) -> HistoricalIntradaySessionMetadata:
    return HistoricalIntradaySessionMetadata(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        session_start_timestamp=ts(day, 30),
        session_end_timestamp=ts(day, 35),
        cutoff_timestamp=ts(day, 32),
        is_complete=is_complete,
    )


def current_series(
    *,
    symbol: str = "ABC",
    session_id: str = "current",
    bucket: str = "09:32",
    volumes: tuple[int | float | bool | str, ...] = (300, 300),
) -> IntradayVolumeSeriesInput:
    return IntradayVolumeSeriesInput(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        cutoff_timestamp=ts(31, 32),
        bars=(
            IntradayVolumeBar(ts(31, 31), volumes[0]),
            IntradayVolumeBar(ts(31, 32), volumes[1]),
        ),
    )


def request(**overrides) -> HistoricalToTodRvolRunRequest:
    values = {
        "symbol": "ABC",
        "bucket": "09:32",
        "current_session_id": "current",
        "page_collection_complete": True,
    }
    values.update(overrides)
    return HistoricalToTodRvolRunRequest(**values)


def assembly_result(
    *,
    status: str = HistoricalSessionAssemblyStatus.OK,
    session_id: str = "hist-01",
) -> HistoricalSessionAssemblyResult:
    return HistoricalSessionAssemblyResult(
        symbol="ABC",
        session_id=session_id,
        bucket="09:32",
        session_start_timestamp=ts(2, 30),
        session_end_timestamp=ts(2, 35),
        cutoff_timestamp=ts(2, 32),
        intraday_series=current_series(session_id=session_id)
        if status == HistoricalSessionAssemblyStatus.OK
        else None,
        status=status,
        reason=None if status == HistoricalSessionAssemblyStatus.OK else status,
    )


def observations(count: int = 20) -> tuple[HistoricalCumulativeVolumeObservation, ...]:
    return tuple(
        HistoricalCumulativeVolumeObservation(
            session_id=f"hist-{index:02d}",
            bucket="09:32",
            cumulative_volume=300,
        )
        for index in range(count)
    )


def baseline_result(
    *,
    status: str = HistoricalBaselineCompositionStatus.OK,
    request_value: HistoricalBaselineCompositionRequest | None = None,
) -> HistoricalBaselineCompositionResult:
    request_value = request_value or HistoricalBaselineCompositionRequest(
        symbol="ABC",
        bucket="09:32",
        current_session_id="current",
    )
    baseline_observations = (
        observations()
        if status == HistoricalBaselineCompositionStatus.OK
        else ()
    )
    return HistoricalBaselineCompositionResult(
        symbol=request_value.symbol,
        bucket=request_value.bucket,
        current_session_id=request_value.current_session_id,
        minimum_historical_sessions=request_value.minimum_historical_sessions,
        observations=baseline_observations,
        session_results=(),
        eligible_session_count=len(baseline_observations),
        status=status,
        reason=None if status == HistoricalBaselineCompositionStatus.OK else status,
    )


def final_result(
    *,
    status: str = CurrentSessionTimeOfDayRvolStatus.OK,
    baseline_value: HistoricalBaselineCompositionResult | None = None,
) -> CurrentSessionTimeOfDayRvolResult:
    baseline_value = baseline_value or baseline_result()
    tod_result = (
        TimeOfDayRelativeVolumeResult(
            symbol="ABC",
            bucket="09:32",
            relative_volume=2.0,
            historical_average_cumulative_volume=300.0,
            status=TimeOfDayRelativeVolumeStatus.OK,
            reason=None,
            observation_count=20,
        )
        if status == CurrentSessionTimeOfDayRvolStatus.OK
        else None
    )
    return CurrentSessionTimeOfDayRvolResult(
        baseline_result=baseline_value,
        current_result=None,
        calculation_input=None,
        time_of_day_result=tod_result,
        status=status,
        reason=None if status == CurrentSessionTimeOfDayRvolStatus.OK else status,
    )


def test_successful_run_calls_each_stage_once_and_retains_exact_artifacts(
    monkeypatch,
) -> None:
    calls = {"assembly": [], "baseline": [], "final": []}
    page = page_for(bars=(raw_bar(2, 32),))
    duplicate_record = metadata("hist-dup", day=3)
    records = [metadata("hist-01", day=2), duplicate_record, duplicate_record]
    series = current_series()
    run_request = request(minimum_historical_sessions=21)
    assembly_artifacts = [assembly_result(session_id="hist-01")]
    baseline_artifact = baseline_result()
    final_artifact = final_result(baseline_value=baseline_artifact)

    def fake_assembly(page_arg, records_arg, *, current_session_id, page_collection_complete):
        calls["assembly"].append(
            (page_arg, records_arg, current_session_id, page_collection_complete)
        )
        return assembly_artifacts

    def fake_baseline(assembly_arg, baseline_request_arg):
        calls["baseline"].append((assembly_arg, baseline_request_arg))
        return baseline_artifact

    def fake_final(current_series_arg, baseline_arg):
        calls["final"].append((current_series_arg, baseline_arg))
        return final_artifact

    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "assemble_historical_sessions_from_page",
        fake_assembly,
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_historical_baseline",
        fake_baseline,
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_current_session_time_of_day_rvol",
        fake_final,
    )

    result = run_historical_to_time_of_day_rvol(
        page,
        records,
        series,
        run_request,
    )

    assert result.status == HistoricalToTodRvolRunStatus.OK
    assert result.reason is None
    assert result.request is run_request
    assert result.assembly_results == tuple(assembly_artifacts)
    assert result.baseline_result is baseline_artifact
    assert result.final_result is final_artifact
    assert calls["assembly"] == [(page, tuple(records), "current", True)]
    assert calls["baseline"] == [
        (tuple(assembly_artifacts), result.baseline_request)
    ]
    assert calls["final"] == [(series, baseline_artifact)]
    assert result.baseline_request == HistoricalBaselineCompositionRequest(
        symbol="ABC",
        bucket="09:32",
        current_session_id="current",
        minimum_historical_sessions=21,
    )


def test_phase_14d_failures_still_call_later_stages_without_early_exit(
    monkeypatch,
) -> None:
    assembly_artifacts = [
        assembly_result(status=HistoricalSessionAssemblyStatus.INCOMPLETE_SESSION)
    ]
    baseline_artifact = baseline_result(
        status=HistoricalBaselineCompositionStatus.INSUFFICIENT_ELIGIBLE_HISTORICAL_SESSIONS
    )
    final_artifact = final_result(
        status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
        baseline_value=baseline_artifact,
    )
    baseline_calls = []
    final_calls = []

    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "assemble_historical_sessions_from_page",
        lambda *args, **kwargs: assembly_artifacts,
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_historical_baseline",
        lambda assembly_arg, baseline_request_arg: (
            baseline_calls.append((assembly_arg, baseline_request_arg))
            or baseline_artifact
        ),
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_current_session_time_of_day_rvol",
        lambda current_series_arg, baseline_arg: (
            final_calls.append((current_series_arg, baseline_arg)) or final_artifact
        ),
    )

    result = run_historical_to_time_of_day_rvol(
        page_for(),
        [metadata()],
        current_series(),
        request(),
    )

    assert len(baseline_calls) == 1
    assert baseline_calls[0][0] == tuple(assembly_artifacts)
    assert len(final_calls) == 1
    assert final_calls[0][1] is baseline_artifact
    assert result.final_result is final_artifact
    assert result.status == HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
    assert result.reason == "FINAL_COMPOSITION_FAILED:BASELINE_FAILED"


def test_phase_14e_failure_is_preserved_through_final_status(monkeypatch) -> None:
    baseline_artifact = baseline_result(
        status=HistoricalBaselineCompositionStatus.INVALID_TARGET_SYMBOL
    )
    final_artifact = final_result(
        status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
        baseline_value=baseline_artifact,
    )
    final_calls = []

    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "assemble_historical_sessions_from_page",
        lambda *args, **kwargs: [assembly_result()],
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_historical_baseline",
        lambda *args, **kwargs: baseline_artifact,
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_current_session_time_of_day_rvol",
        lambda current_series_arg, baseline_arg: (
            final_calls.append((current_series_arg, baseline_arg)) or final_artifact
        ),
    )

    result = run_historical_to_time_of_day_rvol(
        page_for(),
        [metadata()],
        current_series(),
        request(),
    )

    assert final_calls[0][1] is baseline_artifact
    assert result.status == HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
    assert result.reason == "FINAL_COMPOSITION_FAILED:BASELINE_FAILED"
    assert result.final_result is final_artifact


@pytest.mark.parametrize(
    "final_status",
    [
        CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED,
        CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SYMBOL,
        CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_BUCKET,
        CurrentSessionTimeOfDayRvolStatus.MISMATCHED_CURRENT_SESSION_ID,
        CurrentSessionTimeOfDayRvolStatus.TIME_OF_DAY_RVOL_FAILED,
    ],
)
def test_phase_14f_failures_determine_harness_failure_status(
    monkeypatch,
    final_status,
) -> None:
    final_artifact = final_result(status=final_status)
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "assemble_historical_sessions_from_page",
        lambda *args, **kwargs: [assembly_result()],
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_historical_baseline",
        lambda *args, **kwargs: baseline_result(),
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_current_session_time_of_day_rvol",
        lambda *args, **kwargs: final_artifact,
    )

    result = run_historical_to_time_of_day_rvol(
        page_for(),
        [metadata()],
        current_series(),
        request(),
    )

    assert result.status == HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
    assert result.reason == f"FINAL_COMPOSITION_FAILED:{final_status}"
    assert result.final_result is final_artifact


def test_request_boundary_values_are_forwarded_without_harness_validation(
    monkeypatch,
) -> None:
    calls = {}
    run_request = request(
        symbol="   ",
        bucket="",
        current_session_id=None,
        page_collection_complete="true",
        minimum_historical_sessions="twenty",
    )

    def fake_assembly(page_arg, records_arg, *, current_session_id, page_collection_complete):
        calls["assembly"] = (current_session_id, page_collection_complete)
        return []

    def fake_baseline(assembly_arg, baseline_request_arg):
        calls["baseline_request"] = baseline_request_arg
        return baseline_result(
            status=HistoricalBaselineCompositionStatus.INVALID_TARGET_SYMBOL,
            request_value=baseline_request_arg,
        )

    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "assemble_historical_sessions_from_page",
        fake_assembly,
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_historical_baseline",
        fake_baseline,
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_current_session_time_of_day_rvol",
        lambda current_series_arg, baseline_arg: final_result(
            status=CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED,
            baseline_value=baseline_arg,
        ),
    )

    result = run_historical_to_time_of_day_rvol(
        page_for(),
        [metadata()],
        current_series(),
        run_request,
    )

    assert calls["assembly"] == (None, "true")
    baseline_request_arg = calls["baseline_request"]
    assert baseline_request_arg.symbol == "   "
    assert baseline_request_arg.bucket == ""
    assert baseline_request_arg.current_session_id is None
    assert baseline_request_arg.minimum_historical_sessions == "twenty"
    assert result.status == HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED


def test_default_and_higher_minimum_values_are_forwarded(monkeypatch) -> None:
    captured_minimums = []

    def fake_baseline(assembly_arg, baseline_request_arg):
        captured_minimums.append(baseline_request_arg.minimum_historical_sessions)
        return baseline_result(request_value=baseline_request_arg)

    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "assemble_historical_sessions_from_page",
        lambda *args, **kwargs: [assembly_result()],
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_historical_baseline",
        fake_baseline,
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_current_session_time_of_day_rvol",
        lambda *args, **kwargs: final_result(),
    )

    run_historical_to_time_of_day_rvol(
        page_for(),
        [metadata()],
        current_series(),
        request(),
    )
    run_historical_to_time_of_day_rvol(
        page_for(),
        [metadata()],
        current_series(),
        request(minimum_historical_sessions=25),
    )

    assert captured_minimums == [DEFAULT_MINIMUM_HISTORICAL_SESSIONS, 25]


def test_models_are_frozen_and_repeated_calls_share_no_mutable_state(monkeypatch) -> None:
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "assemble_historical_sessions_from_page",
        lambda *args, **kwargs: [assembly_result()],
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_historical_baseline",
        lambda *args, **kwargs: baseline_result(),
    )
    monkeypatch.setattr(
        historical_tod_rvol_harness,
        "compose_current_session_time_of_day_rvol",
        lambda *args, **kwargs: final_result(),
    )
    page = page_for()
    records = [metadata()]
    series = current_series()
    run_request = request()

    first = run_historical_to_time_of_day_rvol(page, records, series, run_request)
    second = run_historical_to_time_of_day_rvol(page, records, series, run_request)

    assert isinstance(first, HistoricalToTodRvolRunResult)
    assert first is not second
    assert first.baseline_request is not second.baseline_request
    assert isinstance(first.assembly_results, tuple)
    assert first.assembly_results is not second.assembly_results
    assert records[0].session_id == "hist-01"
    assert page.next_page_token is None
    with pytest.raises(FrozenInstanceError):
        first.status = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        run_request.symbol = "changed"  # type: ignore[misc]


def test_actual_offline_integration_produces_successful_final_tod_rvol() -> None:
    historical_bars = []
    historical_metadata = []
    for index in range(20):
        day = index + 2
        historical_bars.extend(
            [
                raw_bar(day, 31, 100),
                raw_bar(day, 32, 200),
            ]
        )
        historical_metadata.append(metadata(f"hist-{index:02d}", day=day))

    result = run_historical_to_time_of_day_rvol(
        page_for(bars=historical_bars),
        historical_metadata,
        current_series(volumes=(300, 300)),
        request(),
    )

    assert result.status == HistoricalToTodRvolRunStatus.OK
    assert result.reason is None
    assert len(result.assembly_results) == 20
    assert [item.status for item in result.assembly_results] == [
        HistoricalSessionAssemblyStatus.OK
    ] * 20
    assert result.baseline_result.status == HistoricalBaselineCompositionStatus.OK
    assert result.final_result.status == CurrentSessionTimeOfDayRvolStatus.OK
    assert result.final_result.time_of_day_result is not None
    assert result.final_result.time_of_day_result.relative_volume == 2.0
    assert result.final_result.time_of_day_result.observation_count == 20


def test_status_values_are_stable_strings() -> None:
    assert HistoricalToTodRvolRunStatus.OK == "OK"
    assert (
        HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
        == "FINAL_COMPOSITION_FAILED"
    )


def test_source_boundary_uses_only_approved_public_stage_boundaries() -> None:
    source = inspect.getsource(historical_tod_rvol_harness)
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
        "collections.abc",
        "dataclasses",
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.current_session_tod_rvol",
        "market_sentry.data.historical_baseline_composition",
        "market_sentry.data.historical_session_assembly",
        "market_sentry.data.intraday_bucket_adapter",
        "market_sentry.data.time_of_day_rvol",
    }

    forbidden_terms = [
        "alpaca_historical_bars_adapter",
        "calculate_cumulative_volume_at_bucket",
        "calculate_time_of_day_relative_volume",
        "AlpacaHistoricalBarsFetcher",
        "HttpTransport",
        "StdlibHttpTransport",
        "market_sentry.data.http",
        "market_sentry.data.http_stdlib",
        "market_sentry.data.factory",
        "market_sentry.config",
        "market_sentry.live_readiness",
        "relative_volume_calculator",
        "LiveCandidateBuilder",
        "LiveComposedMarketDataProvider",
        "market_sentry.scanner",
        "market_sentry.alerts",
        "voice",
        "StockCandidate",
        "place_order",
        "execute_order",
        "broker",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered

    path_source = Path(
        "src/market_sentry/data/historical_tod_rvol_harness.py"
    ).read_text(encoding="utf-8")
    assert path_source == source
