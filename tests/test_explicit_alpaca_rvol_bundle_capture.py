import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path

import pytest

from market_sentry.data import explicit_alpaca_rvol_bundle_capture as capture_module
from market_sentry.data.alpaca import AlpacaMarketDataSettings
from market_sentry.data.alpaca_historical_bars_adapter import (
    AlpacaHistoricalBarsAdapterStatus,
    AlpacaHistoricalBarsIntradaySeriesResult,
)
from market_sentry.data.alpaca_historical_bars_fetcher import (
    AlpacaHistoricalBarsFetcher,
    AlpacaHistoricalBarsPage,
    AlpacaHistoricalBarsQuery,
)
from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionResult,
    CollectedHistoricalPagesCompositionStatus,
)
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsCollectedPage,
    HistoricalBarsPageCollectionRequest,
    HistoricalBarsPageCollectionResult,
    HistoricalBarsPageCollectionStatus,
)
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSourceLoadStatus,
)
from market_sentry.data.historical_session_manifest import (
    HistoricalSessionManifestRequest,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunRequest,
)
from market_sentry.data.http import (
    FakeHttpTransport,
    HttpResponse,
    HttpTimeoutError,
)
from market_sentry.data.intraday_bucket_adapter import (
    IntradayBucketStatus,
    IntradayVolumeBar,
    IntradayVolumeSeriesInput,
)
from market_sentry.data.json_historical_rvol_bundle import (
    load_local_historical_rvol_bundle,
)
from market_sentry.data.json_historical_rvol_bundle_writer import (
    JsonHistoricalRvolBundleWriteError,
)
from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    get_local_json_metadata_preflight_scenario,
)
from market_sentry.data.local_json_metadata_workflow_preflight import (
    run_local_json_metadata_workflow_preflight,
)
from market_sentry.data.metadata_loaded_historical_workflow import (
    MetadataLoadedHistoricalWorkflowStatus,
)
from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionStatus,
)
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessStatus,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeStatus
from market_sentry.data.explicit_alpaca_rvol_bundle_capture import (
    ExplicitAlpacaRvolBundleCaptureRequest,
    ExplicitAlpacaRvolBundleCaptureStatus,
    capture_explicit_alpaca_rvol_bundle,
)


def query(**overrides) -> AlpacaHistoricalBarsQuery:
    values = {
        "timeframe": "1Min",
        "start": "2026-01-02T09:30:00Z",
        "end": "2026-01-21T10:00:00Z",
        "limit": 1000,
        "page_token": None,
        "sort": "asc",
    }
    values.update(overrides)
    return AlpacaHistoricalBarsQuery(**values)


def request(output_path, *, allow_live_data=True, historical_max_pages=5, current_max_pages=5):
    return ExplicitAlpacaRvolBundleCaptureRequest(
        symbol="RVOL",
        historical_initial_query=query(),
        historical_max_pages=historical_max_pages,
        current_initial_query=query(
            start="2026-01-31T09:30:00Z",
            end="2026-01-31T09:35:00Z",
        ),
        current_max_pages=current_max_pages,
        current_session_id="CURRENT-001",
        bucket="09:35",
        cutoff_timestamp=datetime(2026, 1, 31, 9, 35, tzinfo=timezone.utc),
        minimum_historical_sessions=20,
        output_path=output_path,
        allow_live_data=allow_live_data,
    )


def raw_bar(day: int, minute: int, volume: int) -> dict[str, object]:
    return {
        "t": f"2026-01-{day:02d}T09:{minute:02d}:00Z",
        "v": volume,
        "o": 1.0,
        "h": 1.0,
        "l": 1.0,
        "c": 1.0,
    }


def response(symbol: str, bars, *, next_page_token=None) -> HttpResponse:
    return HttpResponse(
        status_code=200,
        body=json.dumps(
            {
                "bars": {symbol: bars},
                "next_page_token": next_page_token,
            }
        ),
    )


def valid_historical_pages() -> list[HttpResponse]:
    first_page = [raw_bar(2, 31, 25), raw_bar(2, 35, 75)]
    for day in range(3, 12):
        first_page.append(raw_bar(day, 35, 100))
    second_page = [raw_bar(day, 35, 100) for day in range(12, 22)]
    return [
        response("RVOL", first_page, next_page_token="hist-2"),
        response("RVOL", second_page),
    ]


def current_page(*, bars=None, next_page_token=None, symbol="RVOL") -> HttpResponse:
    return response(
        symbol,
        [raw_bar(31, 35, 200)] if bars is None else bars,
        next_page_token=next_page_token,
    )


def fetcher_with_responses(items) -> AlpacaHistoricalBarsFetcher:
    return AlpacaHistoricalBarsFetcher(
        settings=AlpacaMarketDataSettings(
            api_key="test-key",
            api_secret="test-secret",
        ),
        transport=FakeHttpTransport(items),
    )


def successful_fetcher() -> AlpacaHistoricalBarsFetcher:
    return fetcher_with_responses(valid_historical_pages() + [current_page()])


def minimal_collection(*, complete=True, status=HistoricalBarsPageCollectionStatus.COMPLETE):
    page = AlpacaHistoricalBarsPage(
        requested_symbols=("RVOL",),
        bars_by_symbol={"RVOL": (raw_bar(2, 35, 100),)},
        next_page_token=None if complete else "NEXT",
    )
    return HistoricalBarsPageCollectionResult(
        request=HistoricalBarsPageCollectionRequest(
            symbols=("RVOL",),
            initial_query=query(),
            max_pages=1,
        ),
        collected_pages=(
            HistoricalBarsCollectedPage(index=0, query=query(), page=page),
        ),
        status=status,
        page_collection_complete=complete,
        next_page_token=None if complete else "NEXT",
        reason=None if complete else f"{status}:NEXT",
    )


def test_allow_live_data_true_succeeds_and_models_are_frozen(tmp_path) -> None:
    output_path = tmp_path / "bundle.json"
    capture_request = request(output_path, allow_live_data=True)

    result = capture_explicit_alpaca_rvol_bundle(
        successful_fetcher(),
        capture_request,
    )

    assert result.request is capture_request
    assert result.output_path is output_path
    assert result.status == ExplicitAlpacaRvolBundleCaptureStatus.BUNDLE_WRITTEN
    assert result.reason is None
    assert result.output_written is True
    assert output_path.exists()
    assert result.manifest_request == HistoricalSessionManifestRequest(
        symbol="RVOL",
        bucket="09:35",
        current_session_id="CURRENT-001",
    )
    assert result.harness_request == HistoricalToTodRvolRunRequest(
        symbol="RVOL",
        bucket="09:35",
        current_session_id="CURRENT-001",
        page_collection_complete=True,
        minimum_historical_sessions=20,
    )
    with pytest.raises(FrozenInstanceError):
        result.status = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        capture_request.symbol = "ALT"  # type: ignore[misc]


@pytest.mark.parametrize("gate", [False, 1, "true", None])
def test_live_data_gate_denies_before_fetch_or_write(tmp_path, gate) -> None:
    output_path = tmp_path / "bundle.json"
    output_path.write_bytes(b"keep me")
    transport = FakeHttpTransport(valid_historical_pages() + [current_page()])
    fetcher = AlpacaHistoricalBarsFetcher(
        settings=AlpacaMarketDataSettings(api_key="key", api_secret="secret"),
        transport=transport,
    )

    result = capture_explicit_alpaca_rvol_bundle(
        fetcher,
        request(output_path, allow_live_data=gate),
    )

    assert result.status == ExplicitAlpacaRvolBundleCaptureStatus.LIVE_DATA_NOT_ALLOWED
    assert result.reason == ExplicitAlpacaRvolBundleCaptureStatus.LIVE_DATA_NOT_ALLOWED
    assert result.output_written is False
    assert result.historical_collection is None
    assert result.current_collection is None
    assert transport.requests == []
    assert output_path.read_bytes() == b"keep me"


def test_non_path_output_denies_before_fetch_or_write() -> None:
    transport = FakeHttpTransport(valid_historical_pages() + [current_page()])
    fetcher = AlpacaHistoricalBarsFetcher(
        settings=AlpacaMarketDataSettings(api_key="key", api_secret="secret"),
        transport=transport,
    )

    with pytest.raises(TypeError) as exc_info:
        capture_explicit_alpaca_rvol_bundle(fetcher, request("bundle.json"))

    assert str(exc_info.value) == "output_path must be a pathlib.Path."
    assert transport.requests == []


def test_real_collector_uses_historical_pages_before_current_pages(tmp_path) -> None:
    transport = FakeHttpTransport(valid_historical_pages() + [current_page()])
    fetcher = AlpacaHistoricalBarsFetcher(
        settings=AlpacaMarketDataSettings(api_key="key", api_secret="secret"),
        transport=transport,
    )

    result = capture_explicit_alpaca_rvol_bundle(
        fetcher,
        request(tmp_path / "bundle.json"),
    )

    assert result.status == ExplicitAlpacaRvolBundleCaptureStatus.BUNDLE_WRITTEN
    assert len(transport.requests) == 3
    assert transport.requests[0].params["page_token"] == "hist-2" if "page_token" in transport.requests[0].params else True
    assert "page_token" not in transport.requests[0].params
    assert transport.requests[1].params["page_token"] == "hist-2"
    assert "page_token" not in transport.requests[2].params
    assert result.historical_collection.collected_pages[0].page.bars_by_symbol["RVOL"][0]["t"] == (
        "2026-01-02T09:31:00Z"
    )
    assert result.current_series_result.intraday_series.bars[0].timestamp == (
        datetime(2026, 1, 31, 9, 35, tzinfo=timezone.utc)
    )


def test_unit_sequencing_uses_collector_composer_adapter_and_writer_once(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []
    historical_collection = minimal_collection()
    current_collection = minimal_collection()
    current_page = AlpacaHistoricalBarsPage(
        requested_symbols=("RVOL",),
        bars_by_symbol={"RVOL": (raw_bar(31, 35, 200),)},
        next_page_token=None,
    )
    composition = CollectedHistoricalPagesCompositionResult(
        source_collection=current_collection,
        composed_page=current_page,
        status=CollectedHistoricalPagesCompositionStatus.COMPOSED,
        reason=None,
    )
    current_series = IntradayVolumeSeriesInput(
        symbol="RVOL",
        session_id="CURRENT-001",
        bucket="09:35",
        cutoff_timestamp=datetime(2026, 1, 31, 9, 35, tzinfo=timezone.utc),
        bars=(
            IntradayVolumeBar(
                timestamp=datetime(2026, 1, 31, 9, 35, tzinfo=timezone.utc),
                volume=200,
            ),
        ),
    )
    adapter_result = AlpacaHistoricalBarsIntradaySeriesResult(
        symbol="RVOL",
        session_id="CURRENT-001",
        bucket="09:35",
        cutoff_timestamp=current_series.cutoff_timestamp,
        intraday_series=current_series,
        status=AlpacaHistoricalBarsAdapterStatus.OK,
    )

    def fake_collect(fetcher, collection_request):
        calls.append(("collect", collection_request))
        return historical_collection if len(calls) == 1 else current_collection

    def fake_compose(collection):
        calls.append(("compose", collection))
        return composition

    def fake_adapter(page, adapter_request):
        calls.append(("adapter", page, adapter_request))
        return adapter_result

    def fake_writer(path, collection, manifest, current, harness):
        calls.append(("writer", path, collection, manifest, current, harness))

    monkeypatch.setattr(capture_module, "collect_historical_bars_pages", fake_collect)
    monkeypatch.setattr(capture_module, "compose_collected_historical_pages", fake_compose)
    monkeypatch.setattr(
        capture_module,
        "build_intraday_series_from_historical_bars",
        fake_adapter,
    )
    monkeypatch.setattr(capture_module, "write_local_historical_rvol_bundle", fake_writer)

    output_path = tmp_path / "bundle.json"
    capture_request = request(output_path)
    result = capture_explicit_alpaca_rvol_bundle(object(), capture_request)

    assert result.status == ExplicitAlpacaRvolBundleCaptureStatus.BUNDLE_WRITTEN
    assert [call[0] for call in calls] == [
        "collect",
        "collect",
        "compose",
        "adapter",
        "writer",
    ]
    first_request = calls[0][1]
    second_request = calls[1][1]
    assert first_request.symbols == ("RVOL",)
    assert first_request.initial_query is capture_request.historical_initial_query
    assert first_request.max_pages == capture_request.historical_max_pages
    assert second_request.symbols == ("RVOL",)
    assert second_request.initial_query is capture_request.current_initial_query
    assert second_request.max_pages == capture_request.current_max_pages
    assert calls[2][1] is current_collection
    assert calls[3][1] is current_page
    assert calls[3][2].symbol == "RVOL"
    assert calls[3][2].session_id == "CURRENT-001"
    assert calls[3][2].bucket == "09:35"
    assert calls[4][1] is output_path
    assert calls[4][2] is historical_collection
    assert calls[4][4] is current_series
    assert calls[4][3] == result.manifest_request
    assert calls[4][5] == result.harness_request


def test_historical_incomplete_collection_still_writes(tmp_path) -> None:
    historical_page = response("RVOL", [raw_bar(2, 35, 100)], next_page_token="NEXT")
    fetcher = fetcher_with_responses([historical_page, current_page()])

    result = capture_explicit_alpaca_rvol_bundle(
        fetcher,
        request(tmp_path / "bundle.json", historical_max_pages=1),
    )

    assert result.status == ExplicitAlpacaRvolBundleCaptureStatus.BUNDLE_WRITTEN
    assert result.historical_collection.status == (
        HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED
    )
    assert result.historical_collection.page_collection_complete is False
    assert result.harness_request.page_collection_complete is False
    assert result.output_written is True


def test_current_incomplete_collection_does_not_adapt_or_write(monkeypatch, tmp_path) -> None:
    fetcher = fetcher_with_responses(
        valid_historical_pages()
        + [current_page(next_page_token="NEXT")]
    )
    adapter_calls = []
    writer_calls = []
    monkeypatch.setattr(
        capture_module,
        "build_intraday_series_from_historical_bars",
        lambda *_args: adapter_calls.append("adapter"),
    )
    monkeypatch.setattr(
        capture_module,
        "write_local_historical_rvol_bundle",
        lambda *_args: writer_calls.append("writer"),
    )

    result = capture_explicit_alpaca_rvol_bundle(
        fetcher,
        request(tmp_path / "bundle.json", current_max_pages=1),
    )

    assert result.status == (
        ExplicitAlpacaRvolBundleCaptureStatus.CURRENT_COLLECTION_NOT_COMPOSABLE
    )
    assert result.reason == (
        "CURRENT_COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION"
    )
    assert result.output_written is False
    assert result.current_composition.status == (
        CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION
    )
    assert adapter_calls == []
    assert writer_calls == []


def test_current_empty_complete_collection_does_not_adapt_or_write(
    monkeypatch,
    tmp_path,
) -> None:
    historical_collection = minimal_collection()
    current_collection = HistoricalBarsPageCollectionResult(
        request=HistoricalBarsPageCollectionRequest(
            symbols=("RVOL",),
            initial_query=query(),
            max_pages=1,
        ),
        collected_pages=(),
        status=HistoricalBarsPageCollectionStatus.COMPLETE,
        page_collection_complete=True,
        next_page_token=None,
    )
    collections = [historical_collection, current_collection]

    monkeypatch.setattr(
        capture_module,
        "collect_historical_bars_pages",
        lambda *_args: collections.pop(0),
    )
    monkeypatch.setattr(
        capture_module,
        "build_intraday_series_from_historical_bars",
        lambda *_args: pytest.fail("adapter should not run"),
    )
    monkeypatch.setattr(
        capture_module,
        "write_local_historical_rvol_bundle",
        lambda *_args: pytest.fail("writer should not run"),
    )

    result = capture_explicit_alpaca_rvol_bundle(
        object(),
        request(tmp_path / "bundle.json"),
    )

    assert result.status == (
        ExplicitAlpacaRvolBundleCaptureStatus.CURRENT_COLLECTION_NOT_COMPOSABLE
    )
    assert result.current_composition.status == (
        CollectedHistoricalPagesCompositionStatus.EMPTY_COMPLETE_COLLECTION
    )


def test_current_requested_symbol_mismatch_does_not_adapt_or_write(
    monkeypatch,
    tmp_path,
) -> None:
    historical_collection = minimal_collection()
    first_page = AlpacaHistoricalBarsPage(
        requested_symbols=("RVOL",),
        bars_by_symbol={"RVOL": (raw_bar(31, 34, 50),)},
        next_page_token=None,
    )
    second_page = AlpacaHistoricalBarsPage(
        requested_symbols=("ALT",),
        bars_by_symbol={"ALT": (raw_bar(31, 35, 150),)},
        next_page_token=None,
    )
    current_collection = HistoricalBarsPageCollectionResult(
        request=HistoricalBarsPageCollectionRequest(
            symbols=("RVOL",),
            initial_query=query(),
            max_pages=2,
        ),
        collected_pages=(
            HistoricalBarsCollectedPage(index=0, query=query(), page=first_page),
            HistoricalBarsCollectedPage(index=1, query=query(), page=second_page),
        ),
        status=HistoricalBarsPageCollectionStatus.COMPLETE,
        page_collection_complete=True,
        next_page_token=None,
    )
    collections = [historical_collection, current_collection]
    monkeypatch.setattr(
        capture_module,
        "collect_historical_bars_pages",
        lambda *_args: collections.pop(0),
    )
    monkeypatch.setattr(
        capture_module,
        "build_intraday_series_from_historical_bars",
        lambda *_args: pytest.fail("adapter should not run"),
    )
    monkeypatch.setattr(
        capture_module,
        "write_local_historical_rvol_bundle",
        lambda *_args: pytest.fail("writer should not run"),
    )

    result = capture_explicit_alpaca_rvol_bundle(
        object(),
        request(tmp_path / "bundle.json"),
    )

    assert result.status == (
        ExplicitAlpacaRvolBundleCaptureStatus.CURRENT_COLLECTION_NOT_COMPOSABLE
    )
    assert result.current_composition.status == (
        CollectedHistoricalPagesCompositionStatus.MISMATCHED_PAGE_REQUESTED_SYMBOLS
    )


def test_adapter_failure_does_not_write(monkeypatch, tmp_path) -> None:
    writer_calls = []
    monkeypatch.setattr(
        capture_module,
        "write_local_historical_rvol_bundle",
        lambda *_args: writer_calls.append("writer"),
    )
    fetcher = fetcher_with_responses(
        valid_historical_pages()
        + [current_page(bars=[{"t": "2026-01-31T09:35:00Z"}])]
    )

    result = capture_explicit_alpaca_rvol_bundle(
        fetcher,
        request(tmp_path / "bundle.json"),
    )

    assert result.status == (
        ExplicitAlpacaRvolBundleCaptureStatus.CURRENT_SERIES_ADAPTATION_FAILED
    )
    assert result.reason == "CURRENT_SERIES_ADAPTATION_FAILED:MISSING_RAW_VOLUME"
    assert result.current_series_result.status == (
        AlpacaHistoricalBarsAdapterStatus.MISSING_RAW_VOLUME
    )
    assert result.output_written is False
    assert writer_calls == []


@pytest.mark.parametrize(
    "target",
    [
        "collect_historical_bars_pages",
        "compose_collected_historical_pages",
        "build_intraday_series_from_historical_bars",
        "write_local_historical_rvol_bundle",
    ],
)
def test_direct_dependency_exceptions_propagate(monkeypatch, tmp_path, target) -> None:
    error = RuntimeError(target)
    if target == "collect_historical_bars_pages":
        monkeypatch.setattr(capture_module, target, lambda *_args: (_ for _ in ()).throw(error))
    else:
        monkeypatch.setattr(capture_module, "collect_historical_bars_pages", lambda *_args: minimal_collection())
        if target == "compose_collected_historical_pages":
            monkeypatch.setattr(capture_module, target, lambda *_args: (_ for _ in ()).throw(error))
        else:
            composition = CollectedHistoricalPagesCompositionResult(
                source_collection=minimal_collection(),
                composed_page=AlpacaHistoricalBarsPage(
                    requested_symbols=("RVOL",),
                    bars_by_symbol={"RVOL": (raw_bar(31, 35, 200),)},
                    next_page_token=None,
                ),
                status=CollectedHistoricalPagesCompositionStatus.COMPOSED,
            )
            monkeypatch.setattr(
                capture_module,
                "compose_collected_historical_pages",
                lambda *_args: composition,
            )
            if target == "build_intraday_series_from_historical_bars":
                monkeypatch.setattr(capture_module, target, lambda *_args: (_ for _ in ()).throw(error))
            else:
                series = IntradayVolumeSeriesInput(
                    symbol="RVOL",
                    session_id="CURRENT-001",
                    bucket="09:35",
                    cutoff_timestamp=datetime(2026, 1, 31, 9, 35, tzinfo=timezone.utc),
                    bars=(
                        IntradayVolumeBar(
                            timestamp=datetime(2026, 1, 31, 9, 35, tzinfo=timezone.utc),
                            volume=200,
                        ),
                    ),
                )
                monkeypatch.setattr(
                    capture_module,
                    "build_intraday_series_from_historical_bars",
                    lambda *_args: AlpacaHistoricalBarsIntradaySeriesResult(
                        symbol="RVOL",
                        session_id="CURRENT-001",
                        bucket="09:35",
                        cutoff_timestamp=series.cutoff_timestamp,
                        intraday_series=series,
                        status=AlpacaHistoricalBarsAdapterStatus.OK,
                    ),
                )
                monkeypatch.setattr(capture_module, target, lambda *_args: (_ for _ in ()).throw(error))

    with pytest.raises(RuntimeError) as exc_info:
        capture_explicit_alpaca_rvol_bundle(object(), request(tmp_path / "bundle.json"))

    assert exc_info.value is error


def test_transport_error_propagates(tmp_path) -> None:
    error = HttpTimeoutError("timeout")
    fetcher = fetcher_with_responses([error])

    with pytest.raises(HttpTimeoutError) as exc_info:
        capture_explicit_alpaca_rvol_bundle(
            fetcher,
            request(tmp_path / "bundle.json"),
        )

    assert exc_info.value is error


def test_writer_errors_propagate(monkeypatch, tmp_path) -> None:
    error = JsonHistoricalRvolBundleWriteError("UNSUPPORTED_VALUE:test")
    monkeypatch.setattr(
        capture_module,
        "write_local_historical_rvol_bundle",
        lambda *_args: (_ for _ in ()).throw(error),
    )

    with pytest.raises(JsonHistoricalRvolBundleWriteError) as exc_info:
        capture_explicit_alpaca_rvol_bundle(
            successful_fetcher(),
            request(tmp_path / "bundle.json"),
        )

    assert exc_info.value is error


def test_actual_writer_loader_and_phase_15h_compatibility(tmp_path) -> None:
    output_path = tmp_path / "bundle.json"
    result = capture_explicit_alpaca_rvol_bundle(
        successful_fetcher(),
        request(output_path),
    )

    loaded = load_local_historical_rvol_bundle(output_path)
    assert loaded.collection == result.historical_collection
    assert loaded.manifest_request == result.manifest_request
    assert loaded.current_series == result.current_series_result.intraday_series
    assert loaded.harness_request == result.harness_request

    metadata = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_bytes(metadata.fixture_bytes)
    workflow_result = run_local_json_metadata_workflow_preflight(
        metadata_path,
        loaded.collection,
        loaded.manifest_request,
        loaded.current_series,
        loaded.harness_request,
    )

    assert workflow_result.workflow_result.metadata_load_result.status == (
        HistoricalSessionMetadataSourceLoadStatus.LOADED
    )
    assert workflow_result.workflow_result.status == (
        MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    )
    bridge = workflow_result.workflow_result.workflow_bridge_result
    assert bridge.composition_result.status == (
        CollectedHistoricalPagesCompositionStatus.COMPOSED
    )
    coordinator = bridge.workflow_result
    assert coordinator.status == ManifestToHarnessStatus.OK
    final = coordinator.harness_result.final_result
    assert final.status == CurrentSessionTimeOfDayRvolStatus.OK
    assert final.time_of_day_result.status == TimeOfDayRelativeVolumeStatus.OK
    assert final.time_of_day_result.relative_volume == 2.0


def test_source_boundary() -> None:
    source = inspect.getsource(capture_module)
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
        "dataclasses",
        "datetime",
        "pathlib",
        "market_sentry.data.alpaca_historical_bars_adapter",
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.collected_historical_pages_composer",
        "market_sentry.data.historical_bars_page_collector",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.historical_tod_rvol_harness",
        "market_sentry.data.json_historical_rvol_bundle_writer",
    }

    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)

    assert "collect_historical_bars_pages" in call_names
    assert "compose_collected_historical_pages" in call_names
    assert "build_intraday_series_from_historical_bars" in call_names
    assert "write_local_historical_rvol_bundle" in call_names
    forbidden_calls = {
        "fetch_bars",
        "render_local_historical_rvol_bundle",
        "load_local_historical_rvol_bundle",
        "run_local_json_metadata_workflow_preflight",
        "resolve",
        "absolute",
        "expanduser",
        "glob",
        "rglob",
        "mkdir",
        "getenv",
        "send",
        "write_text",
    }
    assert not forbidden_calls & set(call_names)

    forbidden_terms = [
        "main",
        "config",
        "readiness",
        "alpacasettings",
        "alpacamarketdatasettings",
        "stdlibhttptransport",
        "httptransport",
        "metadata_source",
        "workflow",
        "local_json_metadata_workflow_preflight",
        "provider",
        "factory",
        "scanner",
        "alert",
        "voice",
        "fmp",
        "scenario",
        "catalog",
        "trading",
        "order",
    ]
    lowered = source.lower()
    for term in forbidden_terms:
        assert term not in lowered
