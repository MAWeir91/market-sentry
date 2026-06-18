import ast
import inspect
import math
from datetime import date, datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from market_sentry.data import alpaca_historical_bars_adapter
from market_sentry.data.alpaca_historical_bars_adapter import (
    AlpacaHistoricalBarsAdapterStatus,
    AlpacaHistoricalBarsIntradaySeriesRequest,
    build_intraday_series_from_historical_bars,
    build_intraday_series_from_historical_bars_results,
)
from market_sentry.data.alpaca_historical_bars_fetcher import AlpacaHistoricalBarsPage
from market_sentry.data.intraday_bucket_adapter import (
    IntradayBucketStatus,
    calculate_cumulative_volume_at_bucket,
)


UTC = timezone.utc
EASTERN = timezone(timedelta(hours=-5))


def cutoff(tz=UTC) -> datetime:
    return datetime(2026, 1, 2, 14, 32, tzinfo=tz)


def request(
    symbol: str = "ABC",
    *,
    session_id: str = "session-1",
    bucket: str = "09:32",
    cutoff_timestamp=cutoff(),
) -> AlpacaHistoricalBarsIntradaySeriesRequest:
    return AlpacaHistoricalBarsIntradaySeriesRequest(
        symbol=symbol,
        session_id=session_id,
        bucket=bucket,
        cutoff_timestamp=cutoff_timestamp,
    )


def page_for(symbol: str = "ABC", bars=()) -> AlpacaHistoricalBarsPage:
    return AlpacaHistoricalBarsPage(
        requested_symbols=(symbol,),
        bars_by_symbol={symbol.strip().upper(): tuple(bars)},
        next_page_token=None,
    )


def unsafe_page(symbol: str = "ABC", bars=()) -> AlpacaHistoricalBarsPage:
    page = object.__new__(AlpacaHistoricalBarsPage)
    object.__setattr__(page, "requested_symbols", (symbol,))
    object.__setattr__(page, "bars_by_symbol", MappingProxyType({symbol: tuple(bars)}))
    object.__setattr__(page, "next_page_token", None)
    return page


def raw_bar(timestamp: str = "2026-01-02T14:31:00Z", volume=1000) -> dict:
    return {
        "t": timestamp,
        "o": 1.0,
        "h": 1.1,
        "l": 0.9,
        "c": 1.05,
        "v": volume,
    }


def assert_failed(result, status: str) -> None:
    assert result.status == status
    assert result.reason == status
    assert result.intraday_series is None
    assert result.converted_bar_count == 0


def test_z_suffixed_timestamp_parses_as_aware_datetime() -> None:
    result = build_intraday_series_from_historical_bars(
        page_for(bars=(raw_bar("2026-01-02T14:31:00Z", 1200),)),
        request(),
    )

    assert result.status == AlpacaHistoricalBarsAdapterStatus.OK
    assert result.intraday_series is not None
    assert result.intraday_series.bars[0].timestamp == datetime(
        2026, 1, 2, 14, 31, tzinfo=UTC
    )


def test_explicit_utc_offset_parses_without_conversion() -> None:
    result = build_intraday_series_from_historical_bars(
        page_for(bars=(raw_bar("2026-01-02T14:31:00+00:00", 1200),)),
        request(),
    )

    assert result.status == AlpacaHistoricalBarsAdapterStatus.OK
    assert result.intraday_series is not None
    assert result.intraday_series.bars[0].timestamp == datetime(
        2026, 1, 2, 14, 31, tzinfo=UTC
    )


def test_raw_order_preserved_without_sorting_filtering_or_cutoff_application() -> None:
    result = build_intraday_series_from_historical_bars(
        page_for(
            bars=(
                raw_bar("2026-01-02T14:33:00Z", 3000),
                raw_bar("2026-01-02T14:31:00Z", 1000),
                raw_bar("2026-01-02T14:32:00Z", 2000),
            )
        ),
        request(),
    )

    assert result.status == AlpacaHistoricalBarsAdapterStatus.OK
    assert result.intraday_series is not None
    assert [bar.timestamp.minute for bar in result.intraday_series.bars] == [
        33,
        31,
        32,
    ]
    assert [bar.volume for bar in result.intraday_series.bars] == [3000, 1000, 2000]


def test_raw_volume_values_pass_through_without_coercion_or_downstream_validation() -> None:
    values = (False, "1000", math.nan, 0, -5)
    bars = tuple(
        raw_bar(f"2026-01-02T14:3{index}:00Z", value)
        for index, value in enumerate(values)
    )

    result = build_intraday_series_from_historical_bars(page_for(bars=bars), request())

    assert result.status == AlpacaHistoricalBarsAdapterStatus.OK
    assert result.intraday_series is not None
    assert [bar.volume for bar in result.intraday_series.bars] == list(values)


def test_missing_page_symbol_returns_successful_empty_series() -> None:
    result = build_intraday_series_from_historical_bars(
        page_for("OTHER", bars=(raw_bar(),)),
        request("ABC"),
    )

    assert result.status == AlpacaHistoricalBarsAdapterStatus.OK
    assert result.raw_bar_count == 0
    assert result.converted_bar_count == 0
    assert result.intraday_series is not None
    assert result.intraday_series.symbol == "ABC"
    assert result.intraday_series.bars == ()


def test_symbol_normalization_and_metadata_preservation() -> None:
    result = build_intraday_series_from_historical_bars(
        page_for("ABC", bars=(raw_bar(),)),
        request(" abc ", session_id=" Session-A ", bucket=" 09:32 custom "),
    )

    assert result.status == AlpacaHistoricalBarsAdapterStatus.OK
    assert result.symbol == "ABC"
    assert result.session_id == "Session-A"
    assert result.bucket == "09:32 custom"
    assert result.intraday_series is not None
    assert result.intraday_series.session_id == "Session-A"
    assert result.intraday_series.bucket == "09:32 custom"


@pytest.mark.parametrize(
    ("bad_request", "status"),
    [
        (request("   "), AlpacaHistoricalBarsAdapterStatus.EMPTY_SYMBOL),
        (request(session_id="   "), AlpacaHistoricalBarsAdapterStatus.INVALID_SESSION_ID),
        (request(session_id=None), AlpacaHistoricalBarsAdapterStatus.INVALID_SESSION_ID),
        (request(bucket="   "), AlpacaHistoricalBarsAdapterStatus.EMPTY_BUCKET),
        (request(bucket=None), AlpacaHistoricalBarsAdapterStatus.EMPTY_BUCKET),
        (
            request(cutoff_timestamp=date(2026, 1, 2)),
            AlpacaHistoricalBarsAdapterStatus.INVALID_CUTOFF_TIMESTAMP,
        ),
        (
            request(cutoff_timestamp="2026-01-02T14:32:00Z"),
            AlpacaHistoricalBarsAdapterStatus.INVALID_CUTOFF_TIMESTAMP,
        ),
        (
            request(cutoff_timestamp=14.32),
            AlpacaHistoricalBarsAdapterStatus.INVALID_CUTOFF_TIMESTAMP,
        ),
        (
            request(cutoff_timestamp=True),
            AlpacaHistoricalBarsAdapterStatus.INVALID_CUTOFF_TIMESTAMP,
        ),
        (
            request(cutoff_timestamp=datetime(2026, 1, 2, 14, 32)),
            AlpacaHistoricalBarsAdapterStatus.NAIVE_CUTOFF_TIMESTAMP,
        ),
    ],
)
def test_metadata_validation_failures(bad_request, status) -> None:
    result = build_intraday_series_from_historical_bars(
        page_for(bars=(raw_bar(),)),
        bad_request,
    )

    assert_failed(result, status)


@pytest.mark.parametrize(
    ("bars", "status"),
    [
        (({"v": 1000},), AlpacaHistoricalBarsAdapterStatus.MISSING_RAW_TIMESTAMP),
        (({"t": "2026-01-02T14:31:00Z"},), AlpacaHistoricalBarsAdapterStatus.MISSING_RAW_VOLUME),
        (("not-a-mapping",), AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_BAR),
        ((raw_bar("", 1000),), AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP),
        ((raw_bar("   ", 1000),), AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP),
        ((raw_bar(" 2026-01-02T14:31:00Z", 1000),), AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP),
        ((raw_bar("2026-01-02 14:31:00+00:00", 1000),), AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP),
        ((raw_bar("not-a-timestamp", 1000),), AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP),
        ((raw_bar("2026-01-02T14:31:00", 1000),), AlpacaHistoricalBarsAdapterStatus.NAIVE_RAW_TIMESTAMP),
    ],
)
def test_raw_bar_validation_failures(bars, status) -> None:
    result = build_intraday_series_from_historical_bars(
        unsafe_page(bars=bars),
        request(),
    )

    assert_failed(result, status)
    assert result.raw_bar_count == 1


def test_raw_timestamp_timezone_mismatch_fails_without_conversion() -> None:
    result = build_intraday_series_from_historical_bars(
        page_for(bars=(raw_bar("2026-01-02T14:31:00Z", 1000),)),
        request(cutoff_timestamp=cutoff(EASTERN)),
    )

    assert_failed(result, AlpacaHistoricalBarsAdapterStatus.MISMATCHED_TIMESTAMP_TIMEZONE)


def test_one_bad_raw_bar_invalidates_full_series() -> None:
    result = build_intraday_series_from_historical_bars(
        page_for(
            bars=(
                raw_bar("2026-01-02T14:31:00Z", 1000),
                raw_bar("bad", 2000),
                raw_bar("2026-01-02T14:32:00Z", 3000),
            )
        ),
        request(),
    )

    assert_failed(result, AlpacaHistoricalBarsAdapterStatus.INVALID_RAW_TIMESTAMP)
    assert result.raw_bar_count == 3
    assert result.converted_bar_count == 0


def test_batch_preserves_order_duplicate_symbols_and_failures() -> None:
    page = page_for("ABC", bars=(raw_bar(),))
    requests = [
        request("abc", session_id="first"),
        request("abc", session_id="second"),
        request("   ", session_id="bad"),
        request("missing", session_id="missing"),
    ]

    results = build_intraday_series_from_historical_bars_results(page, requests)

    assert [result.symbol for result in results] == ["ABC", "ABC", "", "MISSING"]
    assert [result.session_id for result in results] == [
        "first",
        "second",
        "bad",
        "missing",
    ]
    assert [result.status for result in results] == [
        "OK",
        "OK",
        "EMPTY_SYMBOL",
        "OK",
    ]
    assert results[3].intraday_series is not None
    assert results[3].intraday_series.bars == ()


def test_successful_series_owns_tuple_bar_data_independently() -> None:
    raw_bars = [raw_bar("2026-01-02T14:31:00Z", 1000)]
    page = page_for(bars=raw_bars)

    result = build_intraday_series_from_historical_bars(page, request())
    raw_bars.append(raw_bar("2026-01-02T14:32:00Z", 2000))

    assert result.status == AlpacaHistoricalBarsAdapterStatus.OK
    assert result.raw_bar_count == 1
    assert result.converted_bar_count == 1
    assert result.intraday_series is not None
    assert isinstance(result.intraday_series.bars, tuple)
    assert len(result.intraday_series.bars) == 1


def test_phase_13f_rejects_invalid_raw_volume_preserved_by_adapter() -> None:
    result = build_intraday_series_from_historical_bars(
        page_for(bars=(raw_bar("2026-01-02T14:31:00Z", False),)),
        request(),
    )

    assert result.status == AlpacaHistoricalBarsAdapterStatus.OK
    assert result.intraday_series is not None
    assert result.intraday_series.bars[0].volume is False

    phase_13f_result = calculate_cumulative_volume_at_bucket(result.intraday_series)

    assert phase_13f_result.status == IntradayBucketStatus.INVALID_INTRADAY_VOLUME


def test_adapter_module_has_no_fetcher_transport_runtime_or_trading_hooks() -> None:
    source = inspect.getsource(alpaca_historical_bars_adapter)
    tree = ast.parse(source)
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert not {"http", "requests", "socket", "urllib", "httpx", "aiohttp"} & imported_modules
    forbidden_terms = [
        "AlpacaHistoricalBarsFetcher",
        "HttpTransport",
        "StdlibHttpTransport",
        "MARKET_SENTRY_PROVIDER",
        "create_market_data_provider",
        "time_of_day_rvol",
        "intraday_rvol_harness",
        "intraday_rvol_fixture_provider",
        "intraday_rvol_candidate_composition_harness",
        "LiveCandidateBuilder",
        "StockCandidate",
        "place_order",
        "execute_order",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered
