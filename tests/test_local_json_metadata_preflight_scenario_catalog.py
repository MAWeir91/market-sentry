import ast
from dataclasses import FrozenInstanceError
import inspect
import json

import pytest

from market_sentry.data.collected_historical_pages_composer import (
    CollectedHistoricalPagesCompositionStatus,
)
from market_sentry.data.collected_pages_to_manifest_workflow import (
    CollectedPagesToManifestWorkflowStatus,
)
from market_sentry.data.current_session_tod_rvol import (
    CurrentSessionTimeOfDayRvolStatus,
)
from market_sentry.data.historical_bars_page_collector import (
    HistoricalBarsPageCollectionStatus,
)
from market_sentry.data.historical_session_manifest import HistoricalSessionManifestStatus
from market_sentry.data.historical_session_metadata_source import (
    HistoricalSessionMetadataSourceLoadStatus,
)
from market_sentry.data.historical_tod_rvol_harness import (
    HistoricalToTodRvolRunStatus,
)
from market_sentry.data.intraday_bucket_adapter import IntradayBucketStatus
from market_sentry.data.json_historical_session_metadata_source import (
    JsonHistoricalSessionMetadataFileSourceError,
)
from market_sentry.data.local_json_metadata_preflight_scenario_catalog import (
    LocalJsonMetadataPreflightScenario,
    get_local_json_metadata_preflight_scenario,
    get_local_json_metadata_preflight_scenarios,
)
from market_sentry.data.manifest_to_harness_orchestrator import (
    ManifestToHarnessStatus,
)
from market_sentry.data.metadata_loaded_historical_workflow import (
    MetadataLoadedHistoricalWorkflowStatus,
)
from market_sentry.data.time_of_day_rvol import TimeOfDayRelativeVolumeStatus
from market_sentry.data import local_json_metadata_preflight_scenario_catalog as catalog


SCENARIO_NAMES = (
    "valid_json_complete_multi_page",
    "partial_manifest_json_complete_multi_page",
    "invalid_cutoff_datetime_json",
    "empty_records_json",
    "page_cap_json_collection_not_composable",
    "repeated_token_json_collection_not_composable",
    "invalid_manifest_request_json",
    "invalid_current_volume_json",
    "unsupported_schema_json_error",
    "malformed_json_error",
    "invalid_utf8_json_error",
    "missing_json_file_error",
)


def by_name():
    return {
        scenario.name: scenario
        for scenario in get_local_json_metadata_preflight_scenarios()
    }


def test_exact_scenario_names_and_order() -> None:
    assert tuple(
        scenario.name for scenario in get_local_json_metadata_preflight_scenarios()
    ) == SCENARIO_NAMES


def test_exact_name_lookup_and_key_errors() -> None:
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )

    assert scenario.name == "valid_json_complete_multi_page"
    with pytest.raises(KeyError) as unknown:
        get_local_json_metadata_preflight_scenario("unknown")
    assert unknown.value.args == ("unknown",)
    with pytest.raises(KeyError) as case_changed:
        get_local_json_metadata_preflight_scenario(
            "VALID_JSON_COMPLETE_MULTI_PAGE"
        )
    assert case_changed.value.args == ("VALID_JSON_COMPLETE_MULTI_PAGE",)


def test_scenario_model_is_frozen() -> None:
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )

    with pytest.raises(FrozenInstanceError):
        scenario.name = "changed"  # type: ignore[misc]


def test_catalog_calls_create_fresh_scenarios_inputs_payloads_and_raw_values() -> None:
    first = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    second = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )

    assert first is not second
    assert first.collection is not second.collection
    assert first.manifest_request is not second.manifest_request
    assert first.current_series is not second.current_series
    assert first.harness_request is not second.harness_request
    assert first.fixture_bytes == second.fixture_bytes

    first_payload = json.loads(first.fixture_bytes.decode("utf-8"))
    second_payload = json.loads(second.fixture_bytes.decode("utf-8"))
    assert first_payload == second_payload
    assert first_payload is not second_payload
    assert first_payload["records"] is not second_payload["records"]
    assert first_payload["records"][0] is not second_payload["records"][0]

    first_bar = first.collection.collected_pages[0].page.bars_by_symbol["RVOL"][0]
    second_bar = second.collection.collected_pages[0].page.bars_by_symbol["RVOL"][0]
    assert first_bar == second_bar
    assert first_bar is not second_bar


def test_valid_fixture_payload_shape_and_split_collection() -> None:
    scenario = get_local_json_metadata_preflight_scenario(
        "valid_json_complete_multi_page"
    )
    payload = json.loads(scenario.fixture_bytes.decode("utf-8"))

    assert payload["schema_version"] == 1
    assert len(payload["records"]) == 20
    assert payload["records"][0]["symbol"] == "RVOL"
    assert payload["records"][0]["bucket"] == "09:35"
    assert payload["records"][0]["session_id"] == "HIST-01"
    assert payload["records"][0]["cutoff_timestamp"] == {
        "$datetime": "2026-01-02T09:35:00Z"
    }

    first_page_bars = scenario.collection.collected_pages[0].page.bars_by_symbol["RVOL"]
    second_page_bars = scenario.collection.collected_pages[1].page.bars_by_symbol["RVOL"]
    assert first_page_bars[0]["t"] == "2026-01-02T09:31:00Z"
    assert first_page_bars[0]["v"] == 25
    assert second_page_bars[0]["t"] == "2026-01-02T09:35:00Z"
    assert second_page_bars[0]["v"] == 75
    assert len(first_page_bars) == 10
    assert len(second_page_bars) == 11


def test_expected_fields_for_all_scenarios() -> None:
    scenarios = by_name()
    loaded = HistoricalSessionMetadataSourceLoadStatus.LOADED
    outer = MetadataLoadedHistoricalWorkflowStatus.WORKFLOW_BRIDGE_RAN
    workflow_ran = CollectedPagesToManifestWorkflowStatus.WORKFLOW_RAN
    composed = CollectedHistoricalPagesCompositionStatus.COMPOSED
    final_failed = HistoricalToTodRvolRunStatus.FINAL_COMPOSITION_FAILED
    baseline_failed = CurrentSessionTimeOfDayRvolStatus.BASELINE_FAILED

    expected = {
        "valid_json_complete_multi_page": (
            None, None, loaded, outer, None, workflow_ran, None, composed,
            ManifestToHarnessStatus.OK, HistoricalSessionManifestStatus.OK,
            HistoricalToTodRvolRunStatus.OK, CurrentSessionTimeOfDayRvolStatus.OK,
            TimeOfDayRelativeVolumeStatus.OK, 2.0,
        ),
        "partial_manifest_json_complete_multi_page": (
            None, None, loaded, outer, None, workflow_ran, None, composed,
            ManifestToHarnessStatus.MANIFEST_PARTIAL,
            HistoricalSessionManifestStatus.PARTIAL,
            HistoricalToTodRvolRunStatus.OK, CurrentSessionTimeOfDayRvolStatus.OK,
            TimeOfDayRelativeVolumeStatus.OK, 2.0,
        ),
        "invalid_cutoff_datetime_json": (
            None, None, loaded, outer, None, workflow_ran, None, composed,
            ManifestToHarnessStatus.MANIFEST_PARTIAL_AND_HARNESS_FAILED,
            HistoricalSessionManifestStatus.PARTIAL,
            final_failed, baseline_failed, None, None,
        ),
        "empty_records_json": (
            None, None, loaded, outer, None, workflow_ran, None, composed,
            ManifestToHarnessStatus.MANIFEST_FAILED,
            HistoricalSessionManifestStatus.NO_VALID_METADATA,
            final_failed, baseline_failed, None, None,
        ),
        "page_cap_json_collection_not_composable": (
            None, None, loaded, outer, None,
            CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE,
            "COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION",
            CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION,
            None, None, None, None, None, None,
        ),
        "repeated_token_json_collection_not_composable": (
            None, None, loaded, outer, None,
            CollectedPagesToManifestWorkflowStatus.COLLECTION_NOT_COMPOSABLE,
            "COLLECTION_NOT_COMPOSABLE:INCOMPLETE_COLLECTION",
            CollectedHistoricalPagesCompositionStatus.INCOMPLETE_COLLECTION,
            None, None, None, None, None, None,
        ),
        "invalid_manifest_request_json": (
            None, None, loaded, outer, None, workflow_ran, None, composed,
            ManifestToHarnessStatus.MANIFEST_FAILED,
            HistoricalSessionManifestStatus.INVALID_TARGET_SYMBOL,
            final_failed, baseline_failed, None, None,
        ),
        "invalid_current_volume_json": (
            None, None, loaded, outer, None, workflow_ran, None, composed,
            ManifestToHarnessStatus.HARNESS_FAILED,
            HistoricalSessionManifestStatus.OK,
            final_failed,
            CurrentSessionTimeOfDayRvolStatus.CURRENT_CUMULATIVE_VOLUME_FAILED,
            None, None,
        ),
        "unsupported_schema_json_error": (
            JsonHistoricalSessionMetadataFileSourceError,
            "UNSUPPORTED_SCHEMA_VERSION",
            None, None, None, None, None, None, None, None, None, None, None, None,
        ),
        "malformed_json_error": (
            json.JSONDecodeError, None,
            None, None, None, None, None, None, None, None, None, None, None, None,
        ),
        "invalid_utf8_json_error": (
            UnicodeDecodeError, None,
            None, None, None, None, None, None, None, None, None, None, None, None,
        ),
        "missing_json_file_error": (
            FileNotFoundError, None,
            None, None, None, None, None, None, None, None, None, None, None, None,
        ),
    }

    for name, values in expected.items():
        scenario = scenarios[name]
        assert (
            scenario.expected_exception_type,
            scenario.expected_exception_message,
            scenario.expected_metadata_load_status,
            scenario.expected_outer_status,
            scenario.expected_outer_reason,
            scenario.expected_bridge_status,
            scenario.expected_bridge_reason,
            scenario.expected_composition_status,
            scenario.expected_coordinator_status,
            scenario.expected_manifest_status,
            scenario.expected_harness_status,
            scenario.expected_final_status,
            scenario.expected_time_of_day_status,
            scenario.expected_relative_volume,
        ) == values


def test_special_input_variants_are_present() -> None:
    scenarios = by_name()

    assert (
        scenarios["page_cap_json_collection_not_composable"].collection.status
        == HistoricalBarsPageCollectionStatus.MAX_PAGE_LIMIT_REACHED
    )
    assert (
        scenarios["page_cap_json_collection_not_composable"].collection.next_page_token
        == "NEXT"
    )
    assert (
        scenarios["repeated_token_json_collection_not_composable"].collection.status
        == HistoricalBarsPageCollectionStatus.REPEATED_NEXT_PAGE_TOKEN
    )
    assert (
        scenarios["repeated_token_json_collection_not_composable"].collection.next_page_token
        == "LOOP"
    )
    assert scenarios["invalid_manifest_request_json"].manifest_request.symbol == " "
    assert (
        scenarios["invalid_current_volume_json"].current_series.bars[0].volume is False
    )
    assert scenarios["missing_json_file_error"].fixture_bytes is None

    partial_payload = json.loads(
        scenarios["partial_manifest_json_complete_multi_page"].fixture_bytes.decode(
            "utf-8"
        )
    )
    assert len(partial_payload["records"]) == 21
    assert "bucket" not in partial_payload["records"][-1]

    invalid_cutoff_payload = json.loads(
        scenarios["invalid_cutoff_datetime_json"].fixture_bytes.decode("utf-8")
    )
    assert invalid_cutoff_payload["records"][0]["cutoff_timestamp"] == {
        "$datetime": "not-a-datetime"
    }


def test_catalog_source_boundary() -> None:
    source = inspect.getsource(catalog)
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
        "datetime",
        "json",
        "market_sentry.data.alpaca_historical_bars_fetcher",
        "market_sentry.data.collected_historical_pages_composer",
        "market_sentry.data.collected_pages_to_manifest_workflow",
        "market_sentry.data.current_session_tod_rvol",
        "market_sentry.data.historical_bars_page_collector",
        "market_sentry.data.historical_session_manifest",
        "market_sentry.data.historical_session_metadata_source",
        "market_sentry.data.historical_tod_rvol_harness",
        "market_sentry.data.intraday_bucket_adapter",
        "market_sentry.data.json_historical_session_metadata_source",
        "market_sentry.data.manifest_to_harness_orchestrator",
        "market_sentry.data.metadata_loaded_historical_workflow",
        "market_sentry.data.time_of_day_rvol",
    }

    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "JsonHistoricalSessionMetadataFileSourceError" in imported_names
    assert "JsonHistoricalSessionMetadataFileSource" not in imported_names

    call_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)

    forbidden_calls = {
        "run_local_json_metadata_workflow_preflight",
        "JsonHistoricalSessionMetadataFileSource",
        "load_historical_session_metadata_source",
        "run_metadata_loaded_historical_workflow",
        "run_collected_pages_to_manifest_workflow",
        "compose_collected_historical_pages",
        "run_manifest_to_historical_tod_rvol",
        "adapt_historical_session_manifest",
        "write_bytes",
        "read_bytes",
        "loads",
    }
    assert not forbidden_calls & call_names
    assert "dumps" in call_names

    forbidden_modules = [
        "provider",
        "factory",
        "config",
        "readiness",
        "runtime",
        "transport",
        "scanner",
        "alerts",
        "voice",
        "candidate",
        "trading",
    ]
    for module_name in imported_modules:
        for forbidden in forbidden_modules:
            assert forbidden not in module_name.lower()
