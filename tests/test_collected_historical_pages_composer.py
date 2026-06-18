import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from market_sentry.data import collected_historical_pages_composer
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionStatus,
    compose_collected_historical_pages,
)
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsCollectedPage,
    HistoricalBarsPageCollectionRequest,
    HistoricalBarsPageCollectionResult,
    HistoricalBarsPageCollectionStatus,
)
from market_sentry.data.historical_session_assembly import (
    HistoricalIntradaySessionMetadata,
    HistoricalSessionAssemblyStatus,
    assemble_historical_sessions_from_page,
)


def query(**overrides) -> AlpacaHistoricalBarsQuery:
    values = {
        "timeframe": "1Min",
        "start": "2026-01-02T14:30:00Z",
        "end": "2026-01-02T15:00:00Z",
    }
    values.update(overrides)
    return AlpacaHistoricalBarsQuery(**values)


def raw_bar(timestamp: str, volume) -> dict:
    return {"t": timestamp, "v": volume, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.0}


def page_for(
    requested_symbols=("ABC",),
    bars_by_symbol=None,
    *,
    next_page_token=None,
) -> AlpacaHistoricalBarsPage:
    return AlpacaHistoricalBarsPage(
        requested_symbols=requested_symbols,
        bars_by_symbol=bars_by_symbol or {},
        next_page_token=next_page_token,
    )


def request_for(symbols=("ABC",)) -> HistoricalBarsPageCollectionRequest:
    return HistoricalBarsPageCollectionRequest(
        symbols=symbols,
        initial_query=query(),
        max_pages=5,
    )


def collected_page(index: int, page: AlpacaHistoricalBarsPage) -> HistoricalBarsCollectedPage:
    return HistoricalBarsCollectedPage(index=index, query=query(page_token=f"p{index}"), page=page)


def collection_for(
    pages,
    *,
    status=HistoricalBarsPageCollectionStatus.COMPLETE,
    complete=True,
    next_page_token=None,
) -> HistoricalBarsPageCollectionResult:
    return HistoricalBarsPageCollectionResult(
        request=request_for(),
        collected_pages=tuple(
            collected_page(index, page) for index, page in enumerate(pages)
        ),
        status=status,
        page_collection_complete=complete,
        next_page_token=next_page_token,
    )


def test_single_complete_page_composes_terminal_page() -> None:
    first = raw_bar("2026-01-02T14:31:00Z", 100)
    second = raw_bar("2026-01-02T14:32:00Z", 200)
    source_page = page_for(
        ("ABC",),
        {"ABC": (first, second)},
    )
    collection = collection_for([source_page])

    result = compose_collected_historical_pages(collection)

    assert result.source_collection is collection
    assert result.status == CollectedHistoricalPagesCompositionStatus.COMPOSED
    assert result.reason is None
    assert result.composed_page is not None
    assert result.composed_page is not source_page
    assert result.composed_page.requested_symbols == source_page.requested_symbols
    assert result.composed_page.next_page_token is None
    assert tuple(result.composed_page.bars_by_symbol["ABC"]) == tuple(
        source_page.bars_by_symbol["ABC"]
    )


def test_multi_page_multi_symbol_concatenates_without_sorting_or_duplicate_removal() -> None:
    abc_late = raw_bar("2026-01-02T14:34:00Z", "abc-late")
    abc_early = raw_bar("2026-01-02T14:31:00Z", "abc-early")
    duplicate = raw_bar("2026-01-02T14:32:00Z", "duplicate")
    xyz_first = raw_bar("2026-01-02T14:33:00Z", "xyz-first")
    xyz_second = raw_bar("2026-01-02T14:31:00Z", "xyz-second")
    first_page = page_for(
        ("ABC", "XYZ"),
        {
            "ABC": (abc_late, duplicate),
            "XYZ": (xyz_first,),
        },
    )
    second_page = page_for(
        ("ABC", "XYZ"),
        {
            "ABC": (abc_early, duplicate),
        },
    )
    third_page = page_for(
        ("ABC", "XYZ"),
        {
            "XYZ": (xyz_second,),
        },
    )
    collection = collection_for([first_page, second_page, third_page])

    result = compose_collected_historical_pages(collection)

    assert result.status == CollectedHistoricalPagesCompositionStatus.COMPOSED
    assert result.composed_page is not None
    assert result.composed_page.requested_symbols == ("ABC", "XYZ")
    assert [bar["v"] for bar in result.composed_page.bars_by_symbol["ABC"]] == [
        "abc-late",
        "duplicate",
        "abc-early",
        "duplicate",
    ]
    assert [bar["v"] for bar in result.composed_page.bars_by_symbol["XYZ"]] == [
        "xyz-first",
        "xyz-second",
    ]
    assert [bar["v"] for bar in first_page.bars_by_symbol["ABC"]] == [
        "abc-late",
        "duplicate",
    ]
    assert "XYZ" not in second_page.bars_by_symbol
    assert "ABC" not in third_page.bars_by_symbol


def test_opaque_malformed_raw_mappings_compose_without_field_validation() -> None:
    first = {"unexpected": object(), "t": None, "v": "not-normal"}
    second = {"nested": {"not": ["a", "standard", "bar"]}}
    collection = collection_for(
        [
            page_for(("ABC",), {"ABC": (first,)}),
            page_for(("ABC",), {"ABC": (second,)}),
        ]
    )

    result = compose_collected_historical_pages(collection)

    assert result.status == CollectedHistoricalPagesCompositionStatus.COMPOSED
    assert result.composed_page is not None
    assert result.composed_page.bars_by_symbol["ABC"][0]["unexpected"] is first["unexpected"]
    assert result.composed_page.bars_by_symbol["ABC"][0]["t"] is None
    assert result.composed_page.bars_by_symbol["ABC"][1]["nested"] == {
        "not": ["a", "standard", "bar"]
    }


@pytest.mark.parametrize(
    ("status", "complete", "next_page_token", "reason_status"),
    [
        (
            HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED,
            False,
            "NEXT",
            HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED,
        ),
        (
            HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN,
            False,
            "LOOP",
            HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN,
        ),
        (
            HistoricalBarsPageCollectionStatus.COMPLETE,
            False,
            None,
            HistoricalBarsPageCollectionStatus.COMPLETE,
        ),
        (
            HistoricalBarsPageCollectionStatus.COMPLETE,
            True,
            "NEXT",
            HistoricalBarsPageCollectionStatus.COMPLETE,
        ),
    ],
)
def test_incomplete_or_malformed_complete_collections_are_not_composed(
    status,
    complete,
    next_page_token,
    reason_status,
) -> None:
    collection = collection_for(
        [page_for(("ABC",), {"ABC": (raw_bar("2026-01-02T14:31:00Z", 100),)})],
        status=status,
        complete=complete,
        next_page_token=next_page_token,
    )

    result = compose_collected_historical_pages(collection)

    assert result.source_collection is collection
    assert result.status == CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION
    assert result.composed_page is None
    assert result.reason == f"INCOMPLETE_COLLECTION:{reason_status}"


def test_empty_complete_collection_is_not_composed() -> None:
    collection = collection_for([])

    result = compose_collected_historical_pages(collection)

    assert result.source_collection is collection
    assert result.status == CollectedHistoricalPagesCompositionStatus.EMPTY_COMPLETE_COLLECTION
    assert result.composed_page is None
    assert result.reason == CollectedHistoricalPagesCompositionStatus.EMPTY_COMPLETE_COLLECTION


def test_mismatched_symbol_tuple_order_reports_source_tuple_position_one() -> None:
    collection = collection_for(
        [
            page_for(("ABC", "XYZ"), {"ABC": (), "XYZ": ()}),
            page_for(("XYZ", "ABC"), {"ABC": (), "XYZ": ()}),
        ]
    )

    result = compose_collected_historical_pages(collection)

    assert result.status == CollectedHistoricalPagesCompositionStatus.MISMATCHED_PAGE_REQUESTED_SYMBOLS
    assert result.composed_page is None
    assert result.reason == "MISMATCHED_PAGE_REQUESTED_SYMBOLS:1"


def test_later_mismatched_symbol_tuple_reports_source_tuple_position_two() -> None:
    collection = collection_for(
        [
            page_for(("ABC", "XYZ"), {"ABC": (), "XYZ": ()}),
            page_for(("ABC", "XYZ"), {"ABC": (), "XYZ": ()}),
            page_for(("ABC",), {"ABC": ()}),
        ]
    )

    result = compose_collected_historical_pages(collection)

    assert result.status == CollectedHistoricalPagesCompositionStatus.MISMATCHED_PAGE_REQUESTED_SYMBOLS
    assert result.reason == "MISMATCHED_PAGE_REQUESTED_SYMBOLS:2"


def test_mismatch_position_uses_tuple_order_not_artifact_index() -> None:
    first = collected_page(99, page_for(("ABC", "XYZ"), {"ABC": (), "XYZ": ()}))
    second = collected_page(42, page_for(("XYZ", "ABC"), {"ABC": (), "XYZ": ()}))
    collection = HistoricalBarsPageCollectionResult(
        request=request_for(),
        collected_pages=(first, second),
        status=HistoricalBarsPageCollectionStatus.COMPLETE,
        page_collection_complete=True,
        next_page_token=None,
    )

    result = compose_collected_historical_pages(collection)

    assert result.status == CollectedHistoricalPagesCompositionStatus.MISMATCHED_PAGE_REQUESTED_SYMBOLS
    assert result.reason == "MISMATCHED_PAGE_REQUESTED_SYMBOLS:1"


def test_identity_immutability_and_protected_output_mappings() -> None:
    first_bar = raw_bar("2026-01-02T14:31:00Z", "first")
    source_page = page_for(("ABC",), {"ABC": (first_bar,)})
    collection = collection_for([source_page])
    source_artifact = collection.collected_pages[0]

    result = compose_collected_historical_pages(collection)

    assert result.source_collection is collection
    assert source_artifact.page is source_page
    assert source_page.requested_symbols == ("ABC",)
    assert source_page.bars_by_symbol["ABC"][0]["v"] == "first"
    assert result.composed_page is not None
    assert result.composed_page is not source_page
    assert isinstance(result.composed_page.bars_by_symbol, MappingProxyType)
    assert isinstance(result.composed_page.bars_by_symbol["ABC"][0], MappingProxyType)
    with pytest.raises(FrozenInstanceError):
        result.status = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.composed_page.bars_by_symbol["ABC"] = ()  # type: ignore[index]
    with pytest.raises(TypeError):
        result.composed_page.bars_by_symbol["ABC"][0]["v"] = "changed"  # type: ignore[index]


def test_repeated_composition_calls_return_independent_result_and_page_objects() -> None:
    collection = collection_for(
        [page_for(("ABC",), {"ABC": (raw_bar("2026-01-02T14:31:00Z", 100),)})]
    )

    first_result = compose_collected_historical_pages(collection)
    second_result = compose_collected_historical_pages(collection)

    assert first_result is not second_result
    assert first_result.source_collection is collection
    assert second_result.source_collection is collection
    assert first_result.composed_page is not None
    assert second_result.composed_page is not None
    assert first_result.composed_page is not second_result.composed_page
    assert tuple(first_result.composed_page.bars_by_symbol["ABC"]) == tuple(
        second_result.composed_page.bars_by_symbol["ABC"]
    )


def test_composed_page_can_feed_phase_14d_session_assembly() -> None:
    first_bar = raw_bar("2026-01-02T14:31:00Z", 100)
    second_bar = raw_bar("2026-01-02T14:32:00Z", 200)
    collection = collection_for(
        [
            page_for(("ABC",), {"ABC": (first_bar,)}),
            page_for(("ABC",), {"ABC": (second_bar,)}),
        ]
    )

    composition = compose_collected_historical_pages(collection)

    assert composition.status == CollectedHistoricalPagesCompositionStatus.COMPOSED
    assert composition.composed_page is not None
    assert [bar["v"] for bar in composition.composed_page.bars_by_symbol["ABC"]] == [
        100,
        200,
    ]

    assembly_results = assemble_historical_sessions_from_page(
        composition.composed_page,
        [
            HistoricalIntradaySessionMetadata(
                symbol="ABC",
                session_id="hist-1",
                bucket="09:32",
                session_start_timestamp=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
                session_end_timestamp=datetime(2026, 1, 2, 14, 35, tzinfo=timezone.utc),
                cutoff_timestamp=datetime(2026, 1, 2, 14, 32, tzinfo=timezone.utc),
                is_complete=True,
            )
        ],
        current_session_id="current",
        page_collection_complete=True,
    )

    assert len(assembly_results) == 1
    assert assembly_results[0].status == HistoricalSessionAssemblyStatus.OK
    assert assembly_results[0].source_raw_bar_count == 2
    assert assembly_results[0].in_window_raw_bar_count == 2


def test_composer_source_boundary() -> None:
    source = inspect.getsource(collected_historical_pages_composer)
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
        "market_sentry.data.historical_bars_page_collector",
    }

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert imported_names == {
        "annotations",
        "dataclass",
        "AlpacaHistoricalBarsPage",
        "HistoricalBarsPageCollectionResult",
        "HistoricalBarsPageCollectionStatus",
    }

    forbidden_import_names = [
        "Fetcher",
        "Query",
        "Http",
        "Adapter",
        "Manifest",
        "Harness",
        "Assembly",
        "Baseline",
        "Rvol",
        "Volume",
        "Provider",
        "Factory",
        "Config",
        "Readiness",
        "Scanner",
        "Alert",
        "Voice",
        "Candidate",
        "Broker",
    ]
    for name in imported_names:
        for fragment in forbidden_import_names:
            assert fragment not in name

    attribute_names = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "requested_symbols" in attribute_names
    assert "bars_by_symbol" in attribute_names
    assert "keys" not in attribute_names
    assert "values" not in attribute_names
    assert "items" not in attribute_names
    assert "sort" not in attribute_names
    assert "deduplicate" not in attribute_names

    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)

    assert "sorted" not in called_names
    assert "parse" not in called_names
    assert "repair" not in called_names
    assert "fetch_bars" not in called_names
    assert "get" in called_names
