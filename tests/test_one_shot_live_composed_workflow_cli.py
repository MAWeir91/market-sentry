import ast
from dataclasses import FrozenInstanceError
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from market_sentry.config import AppConfig, LIVE_COMPOSED_PROVIDER
from market_sentry.data.local_rvol_artifact_manifest import LocalRvolArtifact
from market_sentry.data.one_shot_live_composed_workflow_plan import (
    OneShotLiveComposedWorkflowArtifact,
    OneShotLiveComposedWorkflowPlan,
    OneShotLiveComposedWorkflowPlanError,
)
from market_sentry.local_rvol_artifact_manifest_audit_cli import (
    LocalRvolArtifactAuditResult,
)
from market_sentry.local_rvol_artifact_manifest_writer_cli import (
    LocalRvolArtifactManifestWriterCommandResult,
)
from market_sentry.manual_explicit_alpaca_rvol_capture_preflight_cli import (
    ManualExplicitAlpacaRvolCaptureCommandError,
)
from market_sentry.one_shot_live_composed_workflow_cli import (
    OneShotLiveComposedWorkflowCommandError,
    OneShotLiveComposedWorkflowCommandRequest,
    render_one_shot_live_composed_workflow_command_error,
    render_one_shot_live_composed_workflow_report,
    run_one_shot_live_composed_workflow,
)
import market_sentry.one_shot_live_composed_workflow_cli as module


def artifact(symbol="AAPL", suffix="a") -> OneShotLiveComposedWorkflowArtifact:
    return OneShotLiveComposedWorkflowArtifact(
        symbol=symbol,
        metadata_input_path=Path(f"{suffix}-seed.json"),
        metadata_output_path=Path(f"{suffix}-metadata.json"),
        bundle_output_path=Path(f"{suffix}-bundle.json"),
        historical_start="2026-05-18T13:30:00Z",
        historical_end="2026-06-18T14:00:00Z",
        historical_max_pages=25,
        current_start="2026-06-18T13:30:00Z",
        current_end="2026-06-18T14:00:00Z",
        current_max_pages=2,
        current_session_id="2026-06-18",
        bucket="regular",
        cutoff="2026-06-18T14:00:00Z",
        minimum_historical_sessions=20,
        timeframe="1Min",
        page_limit=1000,
        sort="asc",
    )


def plan(*artifacts) -> OneShotLiveComposedWorkflowPlan:
    return OneShotLiveComposedWorkflowPlan(
        path=Path("workflow.json"),
        manifest_output_path=Path("manifest.json"),
        artifacts=tuple(artifacts or (artifact(),)),
    )


def live_config(**overrides) -> AppConfig:
    value = AppConfig(
        provider="mock",
        watchlist=("BAD",),
        allow_live_data=True,
        alpaca_api_key="alpaca-key",
        alpaca_api_secret="alpaca-secret",
        fmp_api_key="fmp-key",
        rvol_artifact_manifest_path=Path("bad-manifest.json"),
    )
    return AppConfig(**{**value.__dict__, **overrides})


def success_capture() -> SimpleNamespace:
    return SimpleNamespace(status="PREFLIGHT_SUCCEEDED", reason=None)


def success_manifest() -> LocalRvolArtifactManifestWriterCommandResult:
    return LocalRvolArtifactManifestWriterCommandResult(
        output_path=Path("manifest.json"),
        artifacts=(LocalRvolArtifact("AAPL", Path("a-metadata.json"), Path("a-bundle.json")),),
    )


def success_audit() -> LocalRvolArtifactAuditResult:
    return SimpleNamespace(entries=())


def test_command_request_is_frozen() -> None:
    request = OneShotLiveComposedWorkflowCommandRequest(
        plan_path=Path("workflow.json"),
        confirm_live_data=True,
    )

    with pytest.raises(FrozenInstanceError):
        request.confirm_live_data = False


def test_confirmation_absent_rejects_before_plan_or_config() -> None:
    calls = []

    with pytest.raises(OneShotLiveComposedWorkflowCommandError, match="LIVE_DATA_CONFIRMATION_REQUIRED"):
        run_one_shot_live_composed_workflow(
            OneShotLiveComposedWorkflowCommandRequest(Path("workflow.json"), False),
            load_config_fn=lambda: calls.append("config"),
            provider_factory=lambda _config: calls.append("provider"),
            scan_reporter=lambda _provider: "scan",
            plan_loader=lambda _path: calls.append("plan"),
        )

    assert calls == []


def test_confirmation_only_dependency_error() -> None:
    with pytest.raises(
        OneShotLiveComposedWorkflowCommandError,
        match="requires --one-shot-live-composed-workflow",
    ):
        run_one_shot_live_composed_workflow(
            OneShotLiveComposedWorkflowCommandRequest(None, True),
            load_config_fn=lambda: pytest.fail("config should not load"),
            provider_factory=lambda _config: pytest.fail("provider should not build"),
            scan_reporter=lambda _provider: "scan",
        )


def test_bad_plan_structure_blocks_config_and_network() -> None:
    with pytest.raises(OneShotLiveComposedWorkflowPlanError, match="BAD_PLAN"):
        run_one_shot_live_composed_workflow(
            OneShotLiveComposedWorkflowCommandRequest(Path("workflow.json"), True),
            load_config_fn=lambda: pytest.fail("config should not load"),
            provider_factory=lambda _config: pytest.fail("provider should not build"),
            scan_reporter=lambda _provider: "scan",
            plan_loader=lambda _path: (_ for _ in ()).throw(
                OneShotLiveComposedWorkflowPlanError("BAD_PLAN")
            ),
        )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (live_config(allow_live_data=False), "ENV_LIVE_DATA_NOT_ALLOWED"),
        (live_config(alpaca_api_key=None), "MISSING_ALPACA_API_KEY"),
        (live_config(alpaca_api_secret=None), "MISSING_ALPACA_API_SECRET"),
        (live_config(fmp_api_key=None), "MISSING_FMP_API_KEY"),
    ],
)
def test_live_config_gates_block_capture_and_network(config, expected) -> None:
    with pytest.raises(OneShotLiveComposedWorkflowCommandError, match=expected):
        run_one_shot_live_composed_workflow(
            OneShotLiveComposedWorkflowCommandRequest(Path("workflow.json"), True),
            load_config_fn=lambda: config,
            provider_factory=lambda _config: pytest.fail("provider should not build"),
            scan_reporter=lambda _provider: "scan",
            plan_loader=lambda _path: plan(),
            capture_runner=lambda *_args, **_kwargs: pytest.fail("capture should not run"),
        )


def test_successful_workflow_runs_stages_in_order_and_overrides_config(monkeypatch) -> None:
    monkeypatch.setattr(module, "is_manual_explicit_alpaca_rvol_capture_success", lambda _result: True)
    monkeypatch.setattr(module, "is_local_rvol_artifact_audit_success", lambda _result: True)
    calls = []
    workflow_plan = plan(artifact("AAPL", "a"), artifact("MSFT", "m"))
    transport = object()
    provider = object()

    def capture_runner(command, config, transport=None):
        calls.append(("capture", command.symbol, transport))
        assert command.report_output_path is None
        assert command.confirm_live_data is True
        return success_capture()

    def manifest_writer(command):
        calls.append(("manifest", command.output_path, command.artifact_declarations))
        return success_manifest()

    def audit_runner(command):
        calls.append(("audit", command.manifest_path))
        return success_audit()

    def provider_factory(config):
        calls.append(("provider", config.provider, config.watchlist, config.rvol_artifact_manifest_path))
        assert config.provider == LIVE_COMPOSED_PROVIDER
        assert config.watchlist == ("AAPL", "MSFT")
        assert config.rvol_artifact_manifest_path == Path("manifest.json")
        return provider

    def scan_reporter(actual_provider):
        calls.append(("scan", actual_provider))
        return "scanner report"

    result = run_one_shot_live_composed_workflow(
        OneShotLiveComposedWorkflowCommandRequest(Path("workflow.json"), True),
        load_config_fn=live_config,
        provider_factory=provider_factory,
        scan_reporter=scan_reporter,
        transport=transport,
        plan_loader=lambda _path: workflow_plan,
        capture_runner=capture_runner,
        manifest_writer=manifest_writer,
        audit_runner=audit_runner,
    )

    assert result.status == "OK"
    assert result.scan_report == "scanner report"
    assert calls == [
        ("capture", "AAPL", transport),
        ("capture", "MSFT", transport),
        (
            "manifest",
            Path("manifest.json"),
            (
                ("AAPL", "a-metadata.json", "a-bundle.json"),
                ("MSFT", "m-metadata.json", "m-bundle.json"),
            ),
        ),
        ("audit", Path("manifest.json")),
        ("provider", LIVE_COMPOSED_PROVIDER, ("AAPL", "MSFT"), Path("manifest.json")),
        ("scan", provider),
    ]


def test_failed_capture_stops_later_work(monkeypatch) -> None:
    monkeypatch.setattr(module, "is_manual_explicit_alpaca_rvol_capture_success", lambda _result: False)
    calls = []

    result = run_one_shot_live_composed_workflow(
        OneShotLiveComposedWorkflowCommandRequest(Path("workflow.json"), True),
        load_config_fn=live_config,
        provider_factory=lambda _config: pytest.fail("provider should not build"),
        scan_reporter=lambda _provider: "scan",
        plan_loader=lambda _path: plan(artifact("AAPL", "a"), artifact("MSFT", "m")),
        capture_runner=lambda *_args, **_kwargs: calls.append("capture") or SimpleNamespace(
            status="PREFLIGHT_FAILED",
            reason="PREFLIGHT_FAILED",
        ),
        manifest_writer=lambda _command: pytest.fail("manifest should not write"),
        audit_runner=lambda _command: pytest.fail("audit should not run"),
    )

    assert result.status == "FAILED"
    assert result.reason == "CAPTURE_FAILED"
    assert calls == ["capture"]


def test_capture_command_error_stops_later_work() -> None:
    with pytest.raises(
        ManualExplicitAlpacaRvolCaptureCommandError,
        match="INVALID_CUTOFF_TIMESTAMP",
    ):
        run_one_shot_live_composed_workflow(
            OneShotLiveComposedWorkflowCommandRequest(Path("workflow.json"), True),
            load_config_fn=live_config,
            provider_factory=lambda _config: pytest.fail("provider should not build"),
            scan_reporter=lambda _provider: pytest.fail("scanner should not run"),
            plan_loader=lambda _path: plan(),
            capture_runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                ManualExplicitAlpacaRvolCaptureCommandError(
                    "INVALID_CUTOFF_TIMESTAMP"
                )
            ),
            manifest_writer=lambda _command: pytest.fail("manifest should not write"),
            audit_runner=lambda _command: pytest.fail("audit should not run"),
        )


def test_audit_failure_blocks_provider_and_scan(monkeypatch) -> None:
    monkeypatch.setattr(module, "is_manual_explicit_alpaca_rvol_capture_success", lambda _result: True)
    monkeypatch.setattr(module, "is_local_rvol_artifact_audit_success", lambda _result: False)

    result = run_one_shot_live_composed_workflow(
        OneShotLiveComposedWorkflowCommandRequest(Path("workflow.json"), True),
        load_config_fn=live_config,
        provider_factory=lambda _config: pytest.fail("provider should not build"),
        scan_reporter=lambda _provider: "scan",
        plan_loader=lambda _path: plan(),
        capture_runner=lambda *_args, **_kwargs: success_capture(),
        manifest_writer=lambda _command: success_manifest(),
        audit_runner=lambda _command: success_audit(),
    )

    assert result.status == "FAILED"
    assert result.reason == "ARTIFACT_AUDIT_FAILED"
    assert result.scan_report is None


def test_reports_include_stage_summary(monkeypatch) -> None:
    monkeypatch.setattr(module, "is_manual_explicit_alpaca_rvol_capture_success", lambda _result: True)
    monkeypatch.setattr(module, "is_local_rvol_artifact_audit_success", lambda _result: True)
    monkeypatch.setattr(module, "render_local_rvol_artifact_audit_report", lambda *_args: "audit report")
    command = OneShotLiveComposedWorkflowCommandRequest(Path("workflow.json"), True)
    result = run_one_shot_live_composed_workflow(
        command,
        load_config_fn=live_config,
        provider_factory=lambda _config: object(),
        scan_reporter=lambda _provider: "scanner report",
        plan_loader=lambda _path: plan(),
        capture_runner=lambda *_args, **_kwargs: success_capture(),
        manifest_writer=lambda _command: success_manifest(),
        audit_runner=lambda _command: success_audit(),
    )

    report = render_one_shot_live_composed_workflow_report(command, result)

    assert "Market Sentry Explicit One-Shot Live-Composed Workflow" in report
    assert "Capture 1 Status: PREFLIGHT_SUCCEEDED" in report
    assert "Manifest Write: OK" in report
    assert "Artifact Audit: OK" in report
    assert "Live Scan: OK" in report
    assert "scanner report" in report
    assert "Result: OK" in report


def test_command_error_report_is_stable() -> None:
    report = render_one_shot_live_composed_workflow_command_error(
        OneShotLiveComposedWorkflowCommandRequest(None, True),
        OneShotLiveComposedWorkflowCommandError("MISSING_WORKFLOW_PLAN_PATH"),
    )

    assert "Plan Path: N/A" in report
    assert "Result: COMMAND_ERROR" in report
    assert "MISSING_WORKFLOW_PLAN_PATH" in report
    assert "place trades" in report


def test_source_boundaries_are_strict() -> None:
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert "market_sentry.main" not in imported_modules
    assert "market_sentry.scanner" not in imported_modules
    assert "market_sentry.alerts" not in imported_modules
    assert "market_sentry.data.http_stdlib" not in imported_modules
    assert "run_loop" not in source
    assert "write_text" not in source
    assert "read_text" not in source
