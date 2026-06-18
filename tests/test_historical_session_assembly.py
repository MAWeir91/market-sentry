import ast
import inspect
import math
from datetime import date, datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from market_sentry.data import historical_session_assembly
from market_sentry.data.alpaca_historical_bars_adapter import (
    AlpacaHistoricalBarsAdapterStatus,
    AlpacaHistoricalBarsIntradaySeriesResult,
)
from market_sentry.data.alpaca_historical_bars_fetcher import AlpacaHistoricalBarsPage
from market_sentry.data.historical_session_assembly import (
    HistoricalIntradaySessionMetadata,
    HistoricalSessionAssemblyStatus,
    assemble_historical_sessions_from_page,
)
from market_sentry.data.intraday_bucket_adapter import IntradayVolumeSeriesInput


UTC = timezone.utc
EASTERN = timezone(timedelta(hours=-5))


def ts(minute: int, tz=UTC) -> datetime:
    return datetime(2026, 1, 2, 14, minute, tzinfo=tz)


def raw_bar(timestamp: str = "2026-01-02T14:32:00Z", volume=1000) -> dict:
    return {"t": timestamp, "v": volume, "o": 1.0, "c": 1.1}


def page_for(symbol: str = "ABC", bars=(), *, next_page_token=None) -> AlpacaHistoricalBarsPage:
    return AlpacaHistoricalBarsPage(
        requested_symbols=(symbol,),
        bars_by_symbol={symbol.strip().upper(): tuple(bars)},
        next_page_token=next_page_token,
    )


def unsafe_page(symbol: str = "ABC", bars=()) -> AlpacaHistoricalBarsPage:
    page = object.__new__(AlpacaHistoricalBarsPage)
    object.__setattr__(page, "requested_symbols", (symbol,))
    object.__setattr__(page, "bars_by_symbol", MappingProxyType({symbol: tuple(bars)}))
    object.__setattr__(page, "next_page_token", None)
    return page


def metadata(
    symbol: str = "ABC",
    *,
    session_id: str = "hist-1",
    bucket: str = "09:32",
    start=ts(30),
    end=ts(35),
    cutoff=ts(32),
    is_complete=True,
) -> HistoricalIntradaySessionMetadata:
    return HistoricalIntradaySessionMetadata(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        session_start_timestamp=start,
        session_end_timestamp=end,
        cutoff_timestamp=cutoff,
        is_complete=is_complete,
    )


def assemble(page, records, *, current_session_id="current", complete=True):
    return assemble_historical_sessions_from_page(
        page,
        records,
        current_session_id=current_session_id,
        page_collection_complete=complete,
    )


def assert_failed(result, status: str) -> None:
    assert result.status == status
    assert result.reason == status
    assert result.intraday_series is None


def test_valid_session_assembly_calls_phase_14b_once(monkeypatch) -> None:
    calls = []

    def fake_adapter(page, request):
        calls.append((page, request))
        return AlpacaHistoricalBarsIntradaySeriesResult(
            symbol=request.symbol,
            session_id=request.session_id,
            bucket=request.bucket,
            cutoff_timestamp=request.cutoff_timestamp,
            intraday_series=IntradayVolumeSeriesInput(
                symbol=request.symbol,
                session_id=request.session_id,
                bucket=request.bucket,
                cutoff_timestamp=request.cutoff_timestamp,
                bars=(),
            ),
            status=AlpacaHistoricalBarsAdapterStatus.OK,
        )

    monkeypatch.setattr(
        historical_session_assembly,
        "build_intraday_series_from_historical_bars",
        fake_adapter,
    )
    page = page_for(bars=(raw_bar("2026-01-02T14:32:00Z", 1000),))

    result = assemble(page, [metadata()])[0]

    assert result.status == HistoricalSessionAssemblyStatus.OK
    assert result.adapter_result is not None
    assert result.intraday_series is result.adapter_result.intraday_series
    assert result.source_raw_bar_count == 1
    assert result.in_window_raw_bar_count == 1
    assert len(calls) == 1
    scoped_page, adapter_request = calls[0]
    assert scoped_page.requested_symbols == ("ABC",)
    assert scoped_page.next_page_token is None
    assert tuple(scoped_page.bars_by_symbol) == ("ABC",)
    assert adapter_request.symbol == "ABC"
    assert adapter_request.session_id == "hist-1"
    assert adapter_request.bucket == "09:32"


def test_window_membership_preserves_selected_order_and_excludes_end() -> None:
    page = page_for(
        bars=(
            raw_bar("2026-01-02T14:29:00Z", "before"),
            raw_bar("2026-01-02T14:30:00Z", "start"),
            raw_bar("2026-01-02T14:34:00Z", "after-cutoff"),
            raw_bar("2026-01-02T14:32:00Z", "cutoff"),
            raw_bar("2026-01-02T14:35:00Z", "end"),
        )
    )

    result = assemble(page, [metadata()])[0]

    assert result.status == HistoricalSessionAssemblyStatus.OK
    assert result.source_raw_bar_count == 5
    assert result.in_window_raw_bar_count == 3
    assert result.adapter_result is not None
    assert result.adapter_result.intraday_series is not None
    assert [bar.volume for bar in result.adapter_result.intraday_series.bars] == [
        "start",
        "after-cutoff",
        "cutoff",
    ]


@pytest.mark.parametrize(
    "bars",
    [
        (raw_bar("2026-01-02T14:32:00Z", 1000),),
        (raw_bar("2026-01-02T14:33:00Z", 1000),),
    ],
)
def test_bar_at_or_after_cutoff_satisfies_coverage(bars) -> None:
    result = assemble(page_for(bars=bars), [metadata()])[0]

    assert result.status == HistoricalSessionAssemblyStatus.OK


@pytest.mark.parametrize(
    "page, record",
    [
        (page_for(bars=(raw_bar("2026-01-02T14:31:00Z", 1000),)), metadata()),
        (page_for("OTHER", bars=(raw_bar("2026-01-02T14:32:00Z", 1000),)), metadata("ABC")),
    ],
)
def test_no_bar_at_or_after_cutoff_fails(page, record) -> None:
    result = assemble(page, [record])[0]

    assert_failed(result, HistoricalSessionAssemblyStatus.CUT_OFF_NOT_REACHED)


def test_symbol_isolation_and_metadata_trim_preservation() -> None:
    page = AlpacaHistoricalBarsPage(
        requested_symbols=("ABC", "XYZ"),
        bars_by_symbol={
            "ABC": (raw_bar("2026-01-02T14:32:00Z", "abc"),),
            "XYZ": (raw_bar("2026-01-02T14:32:00Z", "xyz"),),
        },
        next_page_token=None,
    )

    result = assemble(
        page,
        [metadata(" abc ", session_id=" Hist-A ", bucket=" custom bucket ")],
    )[0]

    assert result.status == HistoricalSessionAssemblyStatus.OK
    assert result.symbol == "ABC"
    assert result.session_id == "Hist-A"
    assert result.bucket == "custom bucket"
    assert result.adapter_result is not None
    assert result.adapter_result.intraday_series is not None
    assert [bar.volume for bar in result.adapter_result.intraday_series.bars] == ["abc"]


@pytest.mark.parametrize(
    ("record", "status"),
    [
        (metadata("   "), HistoricalSessionAssemblyStatus.EMPTY_SYMBOL),
        (metadata(session_id="   "), HistoricalSessionAssemblyStatus.INVALID_SESSION_ID),
        (metadata(session_id=None), HistoricalSessionAssemblyStatus.INVALID_SESSION_ID),
        (metadata(bucket="   "), HistoricalSessionAssemblyStatus.EMPTY_BUCKET),
        (metadata(bucket=None), HistoricalSessionAssemblyStatus.EMPTY_BUCKET),
        (metadata(start=date(2026, 1, 2)), HistoricalSessionAssemblyStatus.INVALID_SESSION_START_TIMESTAMP),
        (metadata(end="2026-01-02T14:35:00Z"), HistoricalSessionAssemblyStatus.INVALID_SESSION_END_TIMESTAMP),
        (metadata(cutoff=14.32), HistoricalSessionAssemblyStatus.INVALID_CUTOFF_TIMESTAMP),
        (metadata(cutoff=True), HistoricalSessionAssemblyStatus.INVALID_CUTOFF_TIMESTAMP),
        (metadata(start=datetime(2026, 1, 2, 14, 30)), HistoricalSessionAssemblyStatus.NAIVE_SESSION_TIMESTAMP),
        (metadata(end=ts(35, EASTERN)), HistoricalSessionAssemblyStatus.MISMATCHED_SESSION_TIMEZONE),
        (metadata(start=ts(35), end=ts(35)), HistoricalSessionAssemblyStatus.INVALID_SESSION_WINDOW),
        (metadata(cutoff=ts(35)), HistoricalSessionAssemblyStatus.INVALID_CUTOFF_OUTSIDE_SESSION),
        (metadata(cutoff=ts(29)), HistoricalSessionAssemblyStatus.INVALID_CUTOFF_OUTSIDE_SESSION),
        (metadata(is_complete="true"), HistoricalSessionAssemblyStatus.INVALID_IS_COMPLETE),
        (metadata(is_complete=False), HistoricalSessionAssemblyStatus.INCOMPLETE_SESSION),
    ],
)
def test_metadata_validation_failures(record, status) -> None:
    result = assemble(page_for(bars=(raw_bar(),)), [record])[0]

    assert_failed(result, status)


@pytest.mark.parametrize("current_session_id", ["", "   ", None])
def test_invalid_current_session_id_fails_every_record_before_adapter(
    monkeypatch,
    current_session_id,
) -> None:
    monkeypatch.setattr(
        historical_session_assembly,
        "build_intraday_series_from_historical_bars",
        lambda *args: pytest.fail("adapter should not be called"),
    )

    results = assemble(
        page_for(bars=(raw_bar(),)),
        [metadata("ABC"), metadata("XYZ")],
        current_session_id=current_session_id,
    )

    assert [result.status for result in results] == [
        HistoricalSessionAssemblyStatus.INVALID_CURRENT_SESSION_ID,
        HistoricalSessionAssemblyStatus.INVALID_CURRENT_SESSION_ID,
    ]


def test_current_session_reused_in_history_is_rejected_case_sensitive() -> None:
    records = [
        metadata("ABC", session_id="current"),
        metadata("XYZ", session_id="Current"),
    ]

    results = assemble(
        AlpacaHistoricalBarsPage(
            requested_symbols=("ABC", "XYZ"),
            bars_by_symbol={
                "ABC": (raw_bar(),),
                "XYZ": (raw_bar(),),
            },
            next_page_token=None,
        ),
        records,
        current_session_id=" current ",
    )

    assert results[0].status == HistoricalSessionAssemblyStatus.CURRENT_SESSION_IN_HISTORY
    assert results[1].status == HistoricalSessionAssemblyStatus.OK


def test_duplicate_historical_session_ids_reject_all_occurrences_per_symbol() -> None:
    records = [
        metadata(" abc ", session_id=" dup "),
        metadata("ABC", session_id="dup"),
        metadata("XYZ", session_id="dup"),
        metadata("ABC", session_id="Dup"),
    ]
    page = AlpacaHistoricalBarsPage(
        requested_symbols=("ABC", "XYZ"),
        bars_by_symbol={
            "ABC": (raw_bar(),),
            "XYZ": (raw_bar(),),
        },
        next_page_token=None,
    )

    results = assemble(page, records)

    assert [result.status for result in results] == [
        HistoricalSessionAssemblyStatus.DUPLICATE_HISTORICAL_SESSION_ID,
        HistoricalSessionAssemblyStatus.DUPLICATE_HISTORICAL_SESSION_ID,
        HistoricalSessionAssemblyStatus.OK,
        HistoricalSessionAssemblyStatus.OK,
    ]


@pytest.mark.parametrize("complete", [False, "true", 1])
def test_page_collection_incomplete_fails_every_record_before_adapter(monkeypatch, complete) -> None:
    monkeypatch.setattr(
        historical_session_assembly,
        "build_intraday_series_from_historical_bars",
        lambda *args: pytest.fail("adapter should not be called"),
    )

    results = assemble(
        page_for(bars=(raw_bar(),)),
        [metadata("ABC"), metadata("XYZ")],
        complete=complete,
    )

    assert [result.status for result in results] == [
        HistoricalSessionAssemblyStatus.INCOMPLETE_PAGE_COLLECTION,
        HistoricalSessionAssemblyStatus.INCOMPLETE_PAGE_COLLECTION,
    ]


def test_non_null_page_token_fails_every_record_before_adapter(monkeypatch) -> None:
    monkeypatch.setattr(
        historical_session_assembly,
        "build_intraday_series_from_historical_bars",
        lambda *args: pytest.fail("adapter should not be called"),
    )

    results = assemble(
        page_for(bars=(raw_bar(),), next_page_token="next"),
        [metadata("ABC")],
    )

    assert results[0].status == HistoricalSessionAssemblyStatus.INCOMPLETE_PAGE_COLLECTION


@pytest.mark.parametrize(
    ("bars", "status"),
    [
        (("not-a-mapping",), HistoricalSessionAssemblyStatus.INVALID_RAW_BAR),
        (({"v": 1000},), HistoricalSessionAssemblyStatus.MISSING_RAW_TIMESTAMP),
        ((raw_bar("bad", 1000),), HistoricalSessionAssemblyStatus.INVALID_RAW_TIMESTAMP),
        ((raw_bar("2026-01-02T14:32:00", 1000),), HistoricalSessionAssemblyStatus.NAIVE_RAW_TIMESTAMP),
        ((raw_bar("2026-01-02T14:32:00-05:00", 1000),), HistoricalSessionAssemblyStatus.MISMATCHED_RAW_TIMESTAMP_TIMEZONE),
    ],
)
def test_raw_timestamp_failures_invalidate_full_record(bars, status) -> None:
    result = assemble(unsafe_page(bars=bars), [metadata()])[0]

    assert_failed(result, status)
    assert result.source_raw_bar_count == 1
    assert result.in_window_raw_bar_count == 0


def test_missing_v_reaches_phase_14b_as_adapter_failure() -> None:
    result = assemble(page_for(bars=({"t": "2026-01-02T14:32:00Z"},)), [metadata()])[0]

    assert result.status == HistoricalSessionAssemblyStatus.ADAPTER_FAILED
    assert result.reason == "ADAPTER_FAILED:MISSING_RAW_VOLUME"
    assert result.adapter_result is not None
    assert result.adapter_result.status == AlpacaHistoricalBarsAdapterStatus.MISSING_RAW_VOLUME


def test_invalid_raw_v_is_not_revalidated_by_assembler() -> None:
    values = (False, "1000", math.nan, 0, -5)
    bars = tuple(raw_bar(f"2026-01-02T14:3{index}:00Z", value) for index, value in enumerate(values))

    result = assemble(page_for(bars=bars), [metadata(cutoff=ts(30))])[0]

    assert result.status == HistoricalSessionAssemblyStatus.OK
    assert result.adapter_result is not None
    assert result.adapter_result.intraday_series is not None
    assert [bar.volume for bar in result.adapter_result.intraday_series.bars] == list(values)


def test_adapter_failure_preserves_exact_lower_level_status(monkeypatch) -> None:
    failed_adapter_result = AlpacaHistoricalBarsIntradaySeriesResult(
        symbol="ABC",
        session_id="hist-1",
        bucket="09:32",
        cutoff_timestamp=ts(32),
        intraday_series=None,
        status=AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP,
        reason=AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP,
    )
    monkeypatch.setattr(
        historical_session_assembly,
        "build_intraday_series_from_historical_bars",
        lambda *args: failed_adapter_result,
    )

    result = assemble(page_for(bars=(raw_bar(),)), [metadata()])[0]

    assert result.status == HistoricalSessionAssemblyStatus.ADAPTER_FAILED
    assert result.reason == "ADAPTER_FAILED:INVALID_RAW_TIMESTAMP"
    assert result.adapter_result is failed_adapter_result


def test_batch_order_duplicate_records_counts_and_page_immutability() -> None:
    first_bar = raw_bar("2026-01-02T14:31:00Z", "first")
    second_bar = raw_bar("2026-01-02T14:32:00Z", "second")
    page = page_for(bars=(first_bar, second_bar))
    original_page_bars = page.bars_by_symbol["ABC"]
    records = [
        metadata("ABC", session_id="a"),
        metadata("ABC", session_id="b", cutoff=ts(34)),
        metadata("ABC", session_id="c"),
    ]

    results = assemble(page, records)

    assert [result.session_id for result in results] == ["a", "b", "c"]
    assert [result.status for result in results] == [
        "OK",
        "CUT_OFF_NOT_REACHED",
        "OK",
    ]
    assert [result.source_raw_bar_count for result in results] == [2, 2, 2]
    assert [result.in_window_raw_bar_count for result in results] == [2, 2, 2]
    assert page.bars_by_symbol["ABC"] == original_page_bars
    assert first_bar["v"] == "first"
    assert second_bar["v"] == "second"


def test_source_boundary_allows_only_approved_lower_boundary() -> None:
    source = inspect.getsource(historical_session_assembly)
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
        "http",
        "requests",
        "socket",
        "urllib",
        "httpx",
        "aiohttp",
        "market_sentry.data.http",
        "market_sentry.data.http_stdlib",
        "market_sentry.data.factory",
        "market_sentry.data.live_provider_builder",
        "market_sentry.data.live_composed_provider",
        "market_sentry.data.intraday_rvol_harness",
        "market_sentry.data.intraday_rvol_fixture_provider",
        "market_sentry.data.intraday_rvol_candidate_composition_harness",
        "market_sentry.data.time_of_day_rvol",
        "market_sentry.scanner.engine",
        "market_sentry.alerts.generator",
    } & imported_modules
    forbidden_terms = [
        "AlpacaHistoricalBarsFetcher",
        "HttpTransport",
        "StdlibHttpTransport",
        "create_market_data_provider",
        "LiveCandidateBuilder",
        "StockCandidate",
        "calculate_cumulative_volume_at_bucket",
        "calculate_time_of_day_relative_volume",
        "place_order",
        "execute_order",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
