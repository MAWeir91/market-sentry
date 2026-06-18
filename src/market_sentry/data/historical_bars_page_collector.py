from __future__ import annotations

from dataclasses import dataclass, replace

from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsFetcher,
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
)


class HistoricalBarsPageCollectionError(ValueError):
    """Raised for invalid page-collection inputs."""


class HistoricalBarsPageCollectionStatus:
    COMPLETE = "COMPLETE"
    MAX_PAGE_LIMIT_REACHED = "MAX_PAGE_LIMIT_REACHED"
    REPEATED_NEXT_PAGE_TOKEN = "REPEATED_NEXT_PAGE_TOKEN"


@dataclass(frozen=True)
class HistoricalBarsPageCollectionRequest:
    symbols: tuple[str, ...]
    initial_query: AlpacaHistoricalBarsQuery
    max_pages: int

    def __post_init__(self) -> None:
        if not isinstance(self.symbols, tuple):
            object.__setattr__(self, "symbols", tuple(self.symbols))

        if isinstance(self.max_pages, bool) or not isinstance(self.max_pages, int):
            raise HistoricalBarsPageCollectionError(
                "max_pages must be an integer between 1 and 1000."
            )
        if not 1 <= self.max_pages <= 1000:
            raise HistoricalBarsPageCollectionError(
                "max_pages must be an integer between 1 and 1000."
            )


@dataclass(frozen=True)
class HistoricalBarsCollectedPage:
    index: int
    query: AlpacaHistoricalBarsQuery
    page: AlpacaHistoricalBarsPage


@dataclass(frozen=True)
class HistoricalBarsPageCollectionResult:
    request: HistoricalBarsPageCollectionRequest
    collected_pages: tuple[HistoricalBarsCollectedPage, ...]
    status: str
    page_collection_complete: bool
    next_page_token: str | None
    reason: str | None = None


def _result(
    *,
    request: HistoricalBarsPageCollectionRequest,
    collected_pages: list[HistoricalBarsCollectedPage],
    status: str,
    page_collection_complete: bool,
    next_page_token: str | None,
    reason: str | None = None,
) -> HistoricalBarsPageCollectionResult:
    return HistoricalBarsPageCollectionResult(
        request=request,
        collected_pages=tuple(collected_pages),
        status=status,
        page_collection_complete=page_collection_complete,
        next_page_token=next_page_token,
        reason=reason,
    )


def collect_historical_bars_pages(
    fetcher: AlpacaHistoricalBarsFetcher,
    request: HistoricalBarsPageCollectionRequest,
) -> HistoricalBarsPageCollectionResult:
    current_query = request.initial_query
    used_request_tokens: set[str] = set()
    if current_query.page_token is not None:
        used_request_tokens.add(current_query.page_token)

    collected_pages: list[HistoricalBarsCollectedPage] = []

    while True:
        page = fetcher.fetch_bars(request.symbols, current_query)
        collected_pages.append(
            HistoricalBarsCollectedPage(
                index=len(collected_pages),
                query=current_query,
                page=page,
            )
        )
        token = page.next_page_token

        if token is None:
            return _result(
                request=request,
                collected_pages=collected_pages,
                status=HistoricalBarsPageCollectionStatus.COMPLETE,
                page_collection_complete=True,
                next_page_token=None,
            )

        if token in used_request_tokens:
            return _result(
                request=request,
                collected_pages=collected_pages,
                status=HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN,
                page_collection_complete=False,
                next_page_token=token,
                reason=(
                    f"{HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN}:"
                    f"{token}"
                ),
            )

        if len(collected_pages) == request.max_pages:
            return _result(
                request=request,
                collected_pages=collected_pages,
                status=HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED,
                page_collection_complete=False,
                next_page_token=token,
                reason=(
                    f"{HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED}:"
                    f"{token}"
                ),
            )

        used_request_tokens.add(token)
        current_query = replace(current_query, page_token=token)
