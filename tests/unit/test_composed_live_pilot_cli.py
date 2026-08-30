"""Phase 4A.3b: safety-gate unit tests for the composed live-canary CLI.

Every precondition check is exercised directly (never via a live provider
call) -- proving each refusal happens BEFORE any client/adapter/transport
is ever constructed.
"""

from __future__ import annotations

import pytest

from app.cli import composed_live_pilot as cli
from app.core import config as config_module


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    """Every test gets a clean, disabled-by-default Settings singleton --
    never inherits enable state from a previous test or the real environment."""
    monkeypatch.delenv("ENABLE_REAL_MODEL_COMPOSED_RUNS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(config_module, "settings", config_module.Settings.from_env())
    monkeypatch.setattr(cli, "settings", config_module.settings)
    yield


def _plan(**overrides):
    from app.models.pilot_plan import PilotExperimentPlan

    defaults = dict(
        experiment_id="test-canary",
        experiment_version="v1",
        model="fake-model",
        overlay_ids=[
            "live-sensitive-egress-treatment",
            "live-sensitive-egress-control",
            "live-influence-treatment",
            "live-influence-control",
        ],
        trials_per_condition=2,
        max_decisions_per_trial=4,
        max_total_decisions=32,
        timeout_seconds=20.0,
        max_output_tokens=200,
    )
    defaults.update(overrides)
    return PilotExperimentPlan(**defaults)


def test_frozen_plan_loads_and_matches_required_shape():
    plan = cli.load_frozen_plan(model="fake-model-for-test")
    assert plan.overlay_ids == [
        "live-sensitive-egress-treatment",
        "live-sensitive-egress-control",
        "live-influence-treatment",
        "live-influence-control",
    ]
    assert plan.trials_per_condition == 2
    assert plan.trials_per_condition * len(plan.overlay_ids) == 8
    assert plan.max_decisions_per_trial == 4
    assert plan.max_total_decisions == 32
    assert plan.max_output_tokens == 512
    assert plan.reasoning_effort == "low"


def test_model_absent_refuses():
    with pytest.raises(cli.ComposedLivePilotConfigError, match="No model specified"):
        cli.load_frozen_plan(model=None)


def test_live_flag_absent_refuses_before_any_provider_construction(monkeypatch):
    object.__setattr__(cli.settings, "enable_real_model_composed_runs", False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-present")
    with pytest.raises(cli.ComposedLivePilotConfigError, match="ENABLE_REAL_MODEL_COMPOSED_RUNS"):
        cli.require_live_preconditions()


def test_api_key_absent_refuses(monkeypatch):
    object.__setattr__(cli.settings, "enable_real_model_composed_runs", True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(cli.ComposedLivePilotConfigError, match="OPENAI_API_KEY"):
        cli.require_live_preconditions()
    object.__setattr__(cli.settings, "enable_real_model_composed_runs", False)


def test_budget_invalid_refuses():
    plan = _plan(max_total_decisions=2, max_decisions_per_trial=4)
    with pytest.raises(cli.ComposedLivePilotConfigError, match="Invalid budget"):
        cli.resolve_overlays(plan)


def test_unknown_overlay_refuses():
    plan = _plan(overlay_ids=["this-overlay-does-not-exist"])
    with pytest.raises(cli.ComposedLivePilotConfigError, match="Unknown overlay"):
        cli.resolve_overlays(plan)


def test_valid_plan_resolves_overlays_without_error():
    plan = _plan()
    overlays = cli.resolve_overlays(plan)
    assert len(overlays) == 4


def test_existing_mismatched_run_config_refuses_resume(tmp_path, monkeypatch):
    from app.runner.pilot_ledger import PilotResumeConfigMismatchError, TrialLedger

    monkeypatch.setattr(cli, "RUN_DIR_ROOT", tmp_path)
    ledger = TrialLedger(tmp_path / "run-x")
    ledger.write_or_verify_plan(_plan(max_total_decisions=32))

    mismatched = _plan(max_total_decisions=16)
    with pytest.raises(PilotResumeConfigMismatchError):
        TrialLedger(tmp_path / "run-x").write_or_verify_plan(mismatched)


def test_cli_parser_has_no_flag_to_raise_the_budget_above_the_frozen_template():
    parser = cli._build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["run", "--run-id", "x", "--model", "y", "--max-total-decisions", "999999"]
        )


def test_cli_parser_requires_run_id():
    parser = cli._build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["preflight", "--model", "y"])


def test_local_transport_factory_only_targets_the_local_composed_tool_mock():
    transport = cli.local_transport_factory()
    # StdioMCPTransport stores its command/args privately; assert via the
    # constructed object's own params rather than re-deriving the command.
    assert transport._params.command == cli.sys.executable
    assert transport._params.args == ["-m", "mock_servers.composed_tool_mock"]


async def test_preflight_never_constructs_a_provider_client(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError("preflight must never construct a provider client")

    monkeypatch.setattr(cli, "build_real_adapter_factory", _explode)
    plan = cli.load_frozen_plan(model="fake-model")
    report = cli.preflight_report(plan, "some-run-id")
    assert report["model"] == "fake-model"
    assert report["estimated_max_provider_calls"] == 32
    assert report["openai_api_key_present"] is False
    assert report["enable_real_model_composed_runs"] is False
    assert report["max_output_tokens"] == 512
    assert report["reasoning_effort"] == "low"


async def test_dry_run_never_imports_or_constructs_openai_client(monkeypatch, tmp_path):
    def _explode(*args, **kwargs):
        raise AssertionError("dry-run must never construct a real provider adapter/client")

    monkeypatch.setattr(cli, "build_real_adapter_factory", _explode)
    monkeypatch.setattr(cli, "RUN_DIR_ROOT", tmp_path)

    plan = cli.load_frozen_plan(model="fake-model-for-dry-run")
    summary = await cli.run_dry_run(plan, "dry-run-1")
    assert summary["total_trials_recorded"] == 8


async def test_run_live_refuses_before_touching_overlays_or_ledger_when_flag_absent(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(cli, "RUN_DIR_ROOT", tmp_path)
    object.__setattr__(cli.settings, "enable_real_model_composed_runs", False)

    def _explode(*args, **kwargs):
        raise AssertionError("resolve_overlays must never be reached when live flag is absent")

    monkeypatch.setattr(cli, "resolve_overlays", _explode)
    plan = cli.load_frozen_plan(model="fake-model")
    with pytest.raises(cli.ComposedLivePilotConfigError, match="ENABLE_REAL_MODEL_COMPOSED_RUNS"):
        await cli.run_live(plan, "should-never-run")
    assert not (tmp_path / "should-never-run").exists()
