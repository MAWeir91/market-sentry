from __future__ import annotations

from dataclasses import dataclass

from market_sentry.data.alpaca_historical_bars_fetcher import AlpacaHistoricalBarsPage
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsPageCollectionResult,
    HistoricalBarsPageCollectionStatus,
)


class CollectedHistoricalPagesCompositionStatus:
    COMPOSED = "COMPOSED"
    INCOMPLETE_COLLECTION = "INCOMPLETE_COLLECTION"
    EMPTY_COMPLETE_COLLECTION = "EMPTY_COMPLETE_COLLECTION"
    MISMATCHED_PAGE_REQUESTED_SYMBOLS = "MISMATCHED_PAGE_REQUESTED_SYMBOLS"


@dataclass(frozen=True)
class CollectedHistoricalPagesCompositionResult:
    source_collection: HistoricalBarsPageCollectionResult
    composed_page: AlpacaHistoricalBarsPage | None
    status: str
    reason: str | None = None


def _not_composed(
    collection: HistoricalBarsPageCollectionResult,
    status: str,
    reason: str,
) -> CollectedHistoricalPagesCompositionResult:
    return CollectedHistoricalPagesCompositionResult(
        source_collection=collection,
        composed_page=None,
        status=status,
        reason=reason,
    )


def _collection_is_complete(collection: HistoricalBarsPageCollectionResult) -> bool:
    return (
        collection.status == HistoricalBarsPageCollectionStatus.COMPLETE
        and collection.page_collection_complete is True
        and collection.next_page_token is None
    )


def compose_collected_historical_pages(
    collection: HistoricalBarsPageCollectionResult,
) -> CollectedHistoricalPagesCompositionResult:
    if not _collection_is_complete(collection):
        return _not_composed(
            collection,
            CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION,
            (
                f"{CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION}:"
                f"{collection.status}"
            ),
        )

    if not collection.collected_pages:
        return _not_composed(
            collection,
            CollectedHistoricalPagesCompositionStatus.EMPTY_COMPLETE_COLLECTION,
            CollectedHistoricalPagesCompositionStatus.EMPTY_COMPLETE_COLLECTION,
        )

    requested_symbols = collection.collected_pages[0].page.requested_symbols
    for position, collected_page in enumerate(collection.collected_pages[1:], start=1):
        if collected_page.page.requested_symbols != requested_symbols:
            return _not_composed(
                collection,
                CollectedHistoricalPagesCompositionStatus.MISMATCHED_PAGE_REQUESTED_SYMBOLS,
                (
                    f"{CollectedHistoricalPagesCompositionStatus.MISMATCHED_PAGE_REQUESTED_SYMBOLS}:"
                    f"{position}"
                ),
            )

    composed_bars_by_symbol = {}
    for symbol in requested_symbols:
        composed_bars = []
        for collected_page in collection.collected_pages:
            composed_bars.extend(collected_page.page.bars_by_symbol.get(symbol, ()))
        composed_bars_by_symbol[symbol] = tuple(composed_bars)

    return CollectedHistoricalPagesCompositionResult(
        source_collection=collection,
        composed_page=AlpacaHistoricalBarsPage(
            requested_symbols=requested_symbols,
            bars_by_symbol=composed_bars_by_symbol,
            next_page_token=None,
        ),
        status=CollectedHistoricalPagesCompositionStatus.COMPOSED,
        reason=None,
    )
