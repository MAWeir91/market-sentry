import ast
import inspect
from dataclasses import FrozenInstanceError

import pytest

from market_sentry.data import historical_bars_page_collector
from market_sentry.data.alpaca import AlpacaMarketDataSettings
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsFetchError,
    AlpacaHistoricalBarsFetcher,
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsPageCollectionError,
    HistoricalBarsPageCollectionRequest,
    HistoricalBarsPageCollectionResult,
    HistoricalBarsPageCollectionStatus,
    collect_historical_bars_pages,
)
from market_sentry.data.http import FakeHttpTransport, HttpResponse, HttpTransportError


def query(**overrides) -> AlpacaHistoricalBarsQuery:
    values = {
        "timeframe": "1Min",
        "start": "2026-01-02T14:30:00Z",
        "end": "2026-01-02T15:00:00Z",
        "limit": 1000,
        "sort": "asc",
    }
    values.update(overrides)
    return AlpacaHistoricalBarsQuery(**values)


def page(next_page_token=None) -> AlpacaHistoricalBarsPage:
    return AlpacaHistoricalBarsPage(
        requested_symbols=("ABC",),
        bars_by_symbol={"ABC": ()},
        next_page_token=next_page_token,
    )


class RecordingFetcher:
    def __init__(self, items) -> None:
        self.items = list(items)
        self.calls = []

    def fetch_bars(self, symbols, current_query):
        self.calls.append((symbols, current_query))
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def make_request(
    *,
    symbols=("ABC",),
    initial_query=None,
    max_pages=5,
) -> HistoricalBarsPageCollectionRequest:
    return HistoricalBarsPageCollectionRequest(
        symbols=symbols,
        initial_query=initial_query or query(),
        max_pages=max_pages,
    )


@pytest.mark.parametrize("max_pages", [1, 1000])
def test_request_accepts_valid_page_limits(max_pages) -> None:
    request = make_request(max_pages=max_pages)

    assert request.max_pages == max_pages


@pytest.mark.parametrize("max_pages", [True, False, "1", 1.5, None, 0, -1, 1001])
def test_request_rejects_invalid_page_limits(max_pages) -> None:
    with pytest.raises(HistoricalBarsPageCollectionError):
        make_request(max_pages=max_pages)


def test_request_is_frozen_keeps_tuple_safe_and_retains_initial_query_identity() -> None:
    initial_query = query()
    symbols = (" abc ", "XYZ")
    request = make_request(symbols=symbols, initial_query=initial_query)

    assert request.symbols is symbols
    assert request.initial_query is initial_query

    with pytest.raises(FrozenInstanceError):
        request.max_pages = 10  # type: ignore[misc]


def test_request_converts_non_tuple_symbols_without_normalizing_values() -> None:
    request = make_request(symbols=[" abc ", "XYZ"])

    assert request.symbols == (" abc ", "XYZ")


def test_collects_one_terminal_page_as_complete() -> None:
    first_page = page(None)
    fetcher = RecordingFetcher([first_page])
    request = make_request()

    result = collect_historical_bars_pages(fetcher, request)

    assert result.request is request
    assert result.status == HistoricalBarsPageCollectionStatus.COMPLETE
    assert result.page_collection_complete is True
    assert result.next_page_token is None
    assert result.reason is None
    assert len(result.collected_pages) == 1
    assert result.collected_pages[0].index == 0
    assert result.collected_pages[0].query is request.initial_query
    assert result.collected_pages[0].page is first_page
    assert fetcher.calls == [(request.symbols, request.initial_query)]


def test_progresses_tokens_in_order_and_changes_only_page_token() -> None:
    pages = [page("A"), page("B"), page(None)]
    fetcher = RecordingFetcher(pages)
    initial_query = query(limit=250, sort="desc")
    request = make_request(initial_query=initial_query)

    result = collect_historical_bars_pages(fetcher, request)

    assert result.status == HistoricalBarsPageCollectionStatus.COMPLETE
    assert len(result.collected_pages) == 3
    assert [artifact.index for artifact in result.collected_pages] == [0, 1, 2]
    assert [artifact.page for artifact in result.collected_pages] == pages
    assert [call[1].page_token for call in fetcher.calls] == [None, "A", "B"]
    assert fetcher.calls[0][1] is initial_query
    assert fetcher.calls[1][1] is result.collected_pages[1].query
    assert fetcher.calls[2][1] is result.collected_pages[2].query

    for _, follow_up_query in fetcher.calls[1:]:
        assert follow_up_query.timeframe == initial_query.timeframe
        assert follow_up_query.start == initial_query.start
        assert follow_up_query.end == initial_query.end
        assert follow_up_query.limit == initial_query.limit
        assert follow_up_query.sort == initial_query.sort


def test_non_null_initial_page_token_is_used_by_identity_then_continues() -> None:
    pages = [page("NEXT"), page(None)]
    fetcher = RecordingFetcher(pages)
    initial_query = query(page_token="SEED")
    request = make_request(initial_query=initial_query)

    result = collect_historical_bars_pages(fetcher, request)

    assert result.status == HistoricalBarsPageCollectionStatus.COMPLETE
    assert fetcher.calls[0][1] is initial_query
    assert [call[1].page_token for call in fetcher.calls] == ["SEED", "NEXT"]


def test_page_cap_stops_after_one_page_with_unresolved_token() -> None:
    fetcher = RecordingFetcher([page("NEXT"), page(None)])
    request = make_request(max_pages=1)

    result = collect_historical_bars_pages(fetcher, request)

    assert result.status == HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED
    assert result.page_collection_complete is False
    assert result.next_page_token == "NEXT"
    assert result.reason == "MAX_PAGE_LIMIT_REACHED:NEXT"
    assert len(fetcher.calls) == 1
    assert len(result.collected_pages) == 1


def test_page_cap_stops_after_multiple_pages_with_unresolved_token() -> None:
    fetcher = RecordingFetcher([page("A"), page("B"), page(None)])
    request = make_request(max_pages=2)

    result = collect_historical_bars_pages(fetcher, request)

    assert result.status == HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED
    assert result.page_collection_complete is False
    assert result.next_page_token == "B"
    assert result.reason == "MAX_PAGE_LIMIT_REACHED:B"
    assert [call[1].page_token for call in fetcher.calls] == [None, "A"]


def test_repeated_adjacent_token_stops_without_extra_fetch() -> None:
    fetcher = RecordingFetcher([page("A"), page("A"), page(None)])
    request = make_request()

    result = collect_historical_bars_pages(fetcher, request)

    assert result.status == HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN
    assert result.page_collection_complete is False
    assert result.next_page_token == "A"
    assert result.reason == "REPEATED_NEXT_PAGE_TOKEN:A"
    assert len(fetcher.calls) == 2
    assert len(result.collected_pages) == 2


def test_repeated_non_adjacent_token_stops_without_extra_fetch() -> None:
    fetcher = RecordingFetcher([page("A"), page("B"), page("A"), page(None)])
    request = make_request()

    result = collect_historical_bars_pages(fetcher, request)

    assert result.status == HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN
    assert result.next_page_token == "A"
    assert result.reason == "REPEATED_NEXT_PAGE_TOKEN:A"
    assert [call[1].page_token for call in fetcher.calls] == [None, "A", "B"]


def test_initial_token_loop_stops_after_first_fetch() -> None:
    fetcher = RecordingFetcher([page("SEED"), page(None)])
    request = make_request(initial_query=query(page_token="SEED"))

    result = collect_historical_bars_pages(fetcher, request)

    assert result.status == HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN
    assert result.next_page_token == "SEED"
    assert result.reason == "REPEATED_NEXT_PAGE_TOKEN:SEED"
    assert len(fetcher.calls) == 1


def test_repeated_token_wins_over_page_cap() -> None:
    fetcher = RecordingFetcher([page("A"), page("A"), page(None)])
    request = make_request(max_pages=2)

    result = collect_historical_bars_pages(fetcher, request)

    assert result.status == HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN
    assert result.next_page_token == "A"
    assert result.reason == "REPEATED_NEXT_PAGE_TOKEN:A"
    assert len(fetcher.calls) == 2


def test_identity_immutability_and_source_objects_remain_unchanged() -> None:
    first_page = page("A")
    second_page = page(None)
    symbols = ("abc",)
    initial_query = query(limit=777)
    request = make_request(symbols=symbols, initial_query=initial_query)
    fetcher = RecordingFetcher([first_page, second_page])

    result = collect_historical_bars_pages(fetcher, request)

    assert result.request is request
    assert fetcher.calls[0][0] is request.symbols
    assert fetcher.calls[0][0] is symbols
    assert fetcher.calls[0][1] is initial_query
    assert result.collected_pages[0].query is initial_query
    assert result.collected_pages[0].page is first_page
    assert result.collected_pages[1].query is fetcher.calls[1][1]
    assert result.collected_pages[1].page is second_page
    assert isinstance(result.collected_pages, tuple)
    assert request.symbols == symbols
    assert initial_query.page_token is None
    assert first_page.next_page_token == "A"

    with pytest.raises(FrozenInstanceError):
        result.status = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.collected_pages[0].index = 99  # type: ignore[misc]


def test_separate_calls_have_no_shared_state() -> None:
    first_fetcher = RecordingFetcher([page("A"), page(None)])
    second_fetcher = RecordingFetcher([page("A"), page(None)])
    request = make_request()

    first_result = collect_historical_bars_pages(first_fetcher, request)
    second_result = collect_historical_bars_pages(second_fetcher, request)

    assert first_result.status == HistoricalBarsPageCollectionStatus.COMPLETE
    assert second_result.status == HistoricalBarsPageCollectionStatus.COMPLETE
    assert [call[1].page_token for call in first_fetcher.calls] == [None, "A"]
    assert [call[1].page_token for call in second_fetcher.calls] == [None, "A"]


@pytest.mark.parametrize(
    "error",
    [
        AlpacaHistoricalBarsFetchError("bad page"),
        HttpTransportError("transport failed"),
    ],
)
def test_fetcher_errors_propagate_unchanged_without_retry(error) -> None:
    fetcher = RecordingFetcher([error, page(None)])
    request = make_request()

    with pytest.raises(type(error)) as exc_info:
        collect_historical_bars_pages(fetcher, request)

    assert exc_info.value is error
    assert len(fetcher.calls) == 1


def test_later_fetcher_error_propagates_unchanged_without_follow_up() -> None:
    error = HttpTransportError("second page failed")
    fetcher = RecordingFetcher([page("A"), error, page(None)])
    request = make_request()

    with pytest.raises(HttpTransportError) as exc_info:
        collect_historical_bars_pages(fetcher, request)

    assert exc_info.value is error
    assert [call[1].page_token for call in fetcher.calls] == [None, "A"]


def test_collects_pages_with_real_fetcher_and_fake_transport() -> None:
    transport = FakeHttpTransport(
        [
            HttpResponse(
                status_code=200,
                body='{"bars": {"ABC": [{"t": "one", "v": 100}]}, '
                '"next_page_token": "NEXT"}',
            ),
            HttpResponse(
                status_code=200,
                body='{"bars": {"ABC": [{"t": "two", "v": 200}]}, '
                '"next_page_token": null}',
            ),
        ]
    )
    fetcher = AlpacaHistoricalBarsFetcher(
        settings=AlpacaMarketDataSettings(api_key="test-key", api_secret="test-secret"),
        transport=transport,
        timeout_seconds=5.0,
    )
    request = make_request(symbols=("ABC",), max_pages=5)

    result = collect_historical_bars_pages(fetcher, request)

    assert result.status == HistoricalBarsPageCollectionStatus.COMPLETE
    assert len(result.collected_pages) == 2
    assert len(transport.requests) == 2
    assert "page_token" not in transport.requests[0].params
    assert transport.requests[1].params["page_token"] == "NEXT"
    assert result.collected_pages[0].page.next_page_token == "NEXT"
    assert result.collected_pages[1].page.next_page_token is None


def test_collector_source_boundary() -> None:
    source = inspect.getsource(historical_bars_page_collector)
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
        "market_sentry.data.alpaca_historical_bars_fetcher",
    }
    assert "bars_by_symbol" not in source

    forbidden_terms = [
        "build_historical_bars_http_request",
        "parse_historical_bars_http_response",
        "market_sentry.data.http",
        "market_sentry.data.http_stdlib",
        "alpaca_historical_bars_adapter",
        "historical_session_manifest",
        "manifest_to_harness_orchestrator",
        "historical_tod_rvol_harness",
        "historical_session_assembly",
        "historical_baseline_composition",
        "current_session_tod_rvol",
        "intraday_bucket_adapter",
        "time_of_day_rvol",
        "relative_volume",
        "factory",
        "config",
        "readiness",
        "provider",
        "scanner",
        "alerts",
        "voice",
        "StockCandidate",
        "LiveCandidateBuilder",
        "LiveComposedMarketDataProvider",
        "place_order",
        "execute_order",
        "broker",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term.lower() not in lowered


def test_public_result_model_can_be_created() -> None:
    request = make_request()
    result = HistoricalBarsPageCollectionResult(
        request=request,
        collected_pages=(),
        status=HistoricalBarsPageCollectionStatus.COMPLETE,
        page_collection_complete=True,
        next_page_token=None,
    )

    assert result.request is request
