"""The composed live-canary pilot CLI (Phase 4A.3b).

Subcommands:
    preflight   Prints/validates the resolved plan. NEVER calls the
                provider -- constructs no client, no adapter.
    dry-run     Runs the exact same wiring end-to-end
                (run_pilot -> GlobalBudgetHostAdapter -> ComposedBenchmarkRunner
                -> local MCP/A2A mocks) with a built-in, no-network mocked
                decision source. Produces real plan.json/trials.jsonl/
                summary.json artifacts.
    run         The ONLY subcommand that can make a live provider call.
                Refuses unless ENABLE_REAL_MODEL_COMPOSED_RUNS=true,
                OPENAI_API_KEY is set, and --model/--run-id are both given.

No subcommand bypasses ComposedBenchmarkRunner's existing mutation gate:
every adapter (real or the dry-run stub) is wrapped in
``GlobalBudgetHostAdapter`` and driven by the unmodified
``app.runner.pilot_runner.run_pilot`` -- this module adds no new execution
path, only wiring around the existing one.

The only overridable CLI arguments are ``--run-id`` and ``--model``.
There is deliberately no flag to raise ``max_total_decisions`` (or any
other budget/plan field) above what the committed
``benchmarks/composed/live_canary_plan.json`` template declares.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.core.config import real_model_api_key_configured, settings
from app.core.live_overlays import load_live_overlays
from app.models.composed import HostActionSpec
from app.models.composed_provenance import ComposedModelRunProvenance
from app.models.host_context import HostDecisionContext
from app.models.live_overlay import LiveExperimentOverlay
from app.models.pilot_plan import PilotExperimentPlan
from app.runner.blocked_schedule import (
    PHASE_4B_SCHEDULE_SEED,
    PHASE_6B_SCHEDULE_SEED,
    ScheduledTrial,
    build_model_schedule,
    build_phase_6b_model_schedule,
    schedule_sha256,
)
from app.runner.decision_point_pilot import (
    DecisionPointAdapterFactory,
    run_decision_point_pilot,
)
from app.runner.execution_fingerprint import (
    compute_execution_fingerprint,
    compute_execution_fingerprint_v2,
)
from app.runner.host_adapters import HostAgentAdapter
from app.runner.pilot_ledger import (
    PilotResumeConfigMismatchError,
    PilotResumeFingerprintMismatchError,
    PilotResumeScheduleMismatchError,
    TrialLedger,
)
from app.runner.pilot_runner import AdapterFactory, finalize_summary, run_pilot
from app.runner.transport import MCPTransport, StdioMCPTransport

_BENCHMARKS_DIR = Path(__file__).resolve().parent.parent.parent / "benchmarks" / "composed"
FROZEN_PLAN_PATH = _BENCHMARKS_DIR / "live_canary_plan.json"
# Phase 4A.3d: the frozen decision-point (v2) plan. A separate committed
# file with its own experiment_id/version and its own config_hash -- the v1
# hash is never reused.
FROZEN_PLAN_PATHS: dict[str, Path] = {
    "v1": FROZEN_PLAN_PATH,
    "v2": _BENCHMARKS_DIR / "live_canary_plan_v2.json",
    # Phase 4B: the confirmatory decision-point plan (20 trials/condition,
    # blocked-randomised order -- see app.runner.blocked_schedule).
    "v3": _BENCHMARKS_DIR / "live_canary_plan_v3.json",
    # Phase 6B: 40 overlays (10 RQ1 + 10 RQ2 matched pairs), 4 repeats each,
    # call_tool action surface, execution fingerprint v2.
    "v4": _BENCHMARKS_DIR / "live_canary_plan_v4.json",
}
# Plan versions that dispatch trials in a frozen BLOCKED schedule.
_BLOCKED_SCHEDULE_PLAN_VERSIONS = frozenset({"v3", "v4"})
_PHASE_6B_PLAN_VERSIONS = frozenset({"v4"})
OVERLAYS_PATH = "benchmarks/composed/live_overlays.yaml"
_OVERLAYS_PATH_BY_VERSION: dict[str, str] = {
    "v4": "benchmarks/composed/live_overlays_v2.yaml",
}
# The canonical (provider-neutral) decision-point action surface fingerprinted
# for Phase 6B: relay (RQ1) + call_tool (RQ2) + stop.
_PHASE_6B_CANONICAL_ACTIONS: tuple[str, ...] = ("relay_to_remote", "call_tool", "stop")
MODEL_PLACEHOLDER = "REPLACE_WITH_MODEL_ID"
RUN_DIR_ROOT = Path("reports/experiments")


class ComposedLivePilotConfigError(RuntimeError):
    """A refused precondition. No provider client or call is ever
    constructed/made when this is raised."""


def local_transport_factory() -> MCPTransport:
    """The ONLY local MCP target this CLI ever connects to: a local stdio
    subprocess running the composed-suite fixture tool server. Never
    ``github_mock.py``, never any external command."""
    return StdioMCPTransport(command=sys.executable, args=["-m", "mock_servers.composed_tool_mock"])


def load_frozen_plan(model: str | None, plan_version: str = "v1") -> PilotExperimentPlan:
    """Loads a committed, credential-free plan template. Every field except
    ``model`` comes from the frozen file, unconditionally -- there is no CLI
    flag for any of them. ``model`` must be explicitly supplied (the
    template only contains a placeholder); this is never chosen
    automatically. ``plan_version`` selects which frozen file (v1 free-run
    or v2 decision-point); it never alters any field in the chosen file."""
    plan_path = FROZEN_PLAN_PATHS[plan_version]
    data = json.loads(plan_path.read_text())
    if model is not None:
        data["model"] = model
    plan = PilotExperimentPlan.model_validate(data)
    if plan.model == MODEL_PLACEHOLDER:
        raise ComposedLivePilotConfigError(
            "No model specified: the frozen plan template only contains a placeholder "
            f"({MODEL_PLACEHOLDER!r}). Pass --model explicitly."
        )
    return plan


def _overlays_path_for(plan: PilotExperimentPlan) -> str:
    return _OVERLAYS_PATH_BY_VERSION.get(plan.experiment_version, OVERLAYS_PATH)


def resolve_overlays(plan: PilotExperimentPlan) -> list[LiveExperimentOverlay]:
    """Validates every overlay id in the plan exists, and that the plan's
    own budget is internally consistent, BEFORE any provider/transport is
    ever touched."""
    suite = load_live_overlays(_overlays_path_for(plan))
    overlays_by_id = {overlay.id: overlay for overlay in suite.overlays}

    unknown = [oid for oid in plan.overlay_ids if oid not in overlays_by_id]
    if unknown:
        raise ComposedLivePilotConfigError(f"Unknown overlay id(s) in plan: {unknown}")

    if plan.max_total_decisions < plan.max_decisions_per_trial:
        raise ComposedLivePilotConfigError(
            "Invalid budget: max_total_decisions "
            f"({plan.max_total_decisions}) is less than max_decisions_per_trial "
            f"({plan.max_decisions_per_trial}); not even one trial could ever complete."
        )

    return [overlays_by_id[oid] for oid in plan.overlay_ids]


def _uses_blocked_schedule(plan: PilotExperimentPlan) -> bool:
    return plan.experiment_version in _BLOCKED_SCHEDULE_PLAN_VERSIONS


def _is_phase_6b(plan: PilotExperimentPlan) -> bool:
    return plan.experiment_version in _PHASE_6B_PLAN_VERSIONS


def _resolve_schedule(plan: PilotExperimentPlan) -> list[ScheduledTrial] | None:
    """The frozen per-model blocked schedule for a v3 (Phase 4B) or v4
    (Phase 6B) plan (None otherwise). Raises ``ComposedLivePilotConfigError``
    if the model is not in that study's frozen panel."""
    if not _uses_blocked_schedule(plan):
        return None
    try:
        if _is_phase_6b(plan):
            return build_phase_6b_model_schedule(plan.model)
        return build_model_schedule(plan.model, blocks_per_model=plan.trials_per_condition)
    except ValueError as exc:
        raise ComposedLivePilotConfigError(str(exc)) from None


def _execution_fingerprint_for(plan: PilotExperimentPlan, overlays: list[LiveExperimentOverlay]):
    schedule = _resolve_schedule(plan)
    sched_sha = schedule_sha256(schedule) if schedule is not None else None
    if _is_phase_6b(plan):
        from app.runner.host_adapters import PHASE_6B_HOST_POLICY_TEXT
        from app.runner.model_panel import provider_config_sha256

        fp = compute_execution_fingerprint_v2(
            plan,
            overlays,
            canonical_actions=_PHASE_6B_CANONICAL_ACTIONS,
            host_policy_text=PHASE_6B_HOST_POLICY_TEXT,
            schedule_sha256=sched_sha,
            # Phase 6C: fold the exact provider inference interface for this
            # plan's model into the fingerprint (provider id, model id,
            # provider wire tool-schema hash, request-param hash, API mode).
            provider_config_sha256=provider_config_sha256(
                plan.model,
                canonical_actions=_PHASE_6B_CANONICAL_ACTIONS,
                timeout_seconds=plan.timeout_seconds,
            ),
        )
        return fp, schedule
    return compute_execution_fingerprint(plan, overlays, schedule_sha256=sched_sha), schedule


def _provider_for(model: str) -> str:
    from app.runner.model_panel import provider_for_model

    return provider_for_model(model)


def require_live_preconditions(model: str | None = None) -> None:
    """Checked before anything else in ``run_live`` -- no client, no
    adapter, no ledger write happens if any check fails. The API-key check
    is per-provider (OpenAI models need ``OPENAI_API_KEY``; the Anthropic
    robustness model needs ``ANTHROPIC_API_KEY``)."""
    if not settings.enable_real_model_composed_runs:
        raise ComposedLivePilotConfigError(
            "ENABLE_REAL_MODEL_COMPOSED_RUNS is not true; refusing to run a live composed pilot."
        )
    provider = _provider_for(model) if model is not None else "openai"
    if provider == "anthropic":
        import os

        if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
            raise ComposedLivePilotConfigError(
                "ANTHROPIC_API_KEY is not set; refusing to run the Anthropic robustness model."
            )
        return
    if not real_model_api_key_configured():
        raise ComposedLivePilotConfigError(
            "OPENAI_API_KEY is not set; refusing to run a live composed pilot."
        )


def preflight_report(plan: PilotExperimentPlan, run_id: str) -> dict:
    """Validates and describes the resolved plan, including the full
    execution fingerprint. Constructs no client, no adapter, no transport --
    makes no provider call."""
    overlays = resolve_overlays(plan)
    fingerprint, schedule = _execution_fingerprint_for(plan, overlays)
    # The frozen blocked schedule (v3/v4) is the authoritative trial count;
    # for an unscheduled plan it is trials_per_condition x #overlays.
    total_trials = (
        len(schedule) if schedule is not None else plan.trials_per_condition * len(plan.overlay_ids)
    )
    estimated_max_provider_calls = min(
        total_trials * plan.max_decisions_per_trial,
        plan.max_total_decisions,
    )
    report = {
        "model": plan.model,
        "overlays": list(plan.overlay_ids),
        "trials_per_condition": plan.trials_per_condition,
        "total_trials": total_trials,
        "max_decisions_per_trial": plan.max_decisions_per_trial,
        "max_total_decisions": plan.max_total_decisions,
        "max_output_tokens": plan.max_output_tokens,
        "reasoning_effort": plan.reasoning_effort,
        "execution_mode": plan.execution_mode,
        "estimated_max_provider_calls": estimated_max_provider_calls,
        "local_only_targets": {
            "mcp": "mock_servers.composed_tool_mock (local stdio subprocess only)",
            "a2a": "mock_servers.a2a_mock (in-process TestClient only, no sockets)",
        },
        "config_hash": plan.config_hash,
        "source_commit_sha": fingerprint.source_commit_sha,
        "resolved_overlay_bundle_sha256": fingerprint.resolved_overlay_bundle_sha256,
        "host_policy_sha256": fingerprint.host_policy_sha256,
        "tool_schema_sha256": fingerprint.tool_schema_sha256,
        "schedule_sha256": fingerprint.schedule_sha256,
        "fingerprint_version": fingerprint.fingerprint_version,
        "canonical_action_schema_sha256": fingerprint.canonical_action_schema_sha256,
        "uv_lock_sha256": fingerprint.uv_lock_sha256,
        "python_runtime_version": fingerprint.python_runtime_version,
        "provider_config_sha256": fingerprint.provider_config_sha256,
        "execution_fingerprint_sha256": fingerprint.execution_fingerprint_sha256,
        "run_directory": str(RUN_DIR_ROOT / run_id),
        "enable_real_model_composed_runs": settings.enable_real_model_composed_runs,
        "openai_api_key_present": real_model_api_key_configured(),
        "provider_calls_made": 0,
    }
    if _is_phase_6b(plan):
        import os

        from app.runner.model_panel import (
            provider_api_surface_for_model,
            provider_for_model,
            provider_request_config,
        )

        report["provider"] = provider_for_model(plan.model)
        report["provider_api_surface"] = provider_api_surface_for_model(plan.model)
        report["provider_request_config"] = provider_request_config(
            plan.model, timeout_seconds=plan.timeout_seconds
        )
        report["anthropic_api_key_present"] = bool(
            (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        )
    if schedule is not None:
        report["blocked_schedule"] = {
            "scheduling_seed": (
                PHASE_6B_SCHEDULE_SEED if _is_phase_6b(plan) else PHASE_4B_SCHEDULE_SEED
            ),
            "blocks": plan.trials_per_condition
            if not _is_phase_6b(plan)
            else max(e.block_index for e in schedule) + 1,
            "overlays_per_block": len({e.overlay_id for e in schedule if e.block_index == 0}),
            "trials_in_schedule": len(schedule),
            "first_block_overlay_order": [
                entry.overlay_id
                for entry in sorted(
                    (e for e in schedule if e.block_index == 0),
                    key=lambda e: e.position_in_block,
                )
            ],
        }
    return report


class _DryRunAdapter(HostAgentAdapter):
    """A minimal, built-in, no-network mocked decision source: always stops
    immediately. Exercises the exact ``GlobalBudgetHostAdapter``/
    ``ComposedBenchmarkRunner`` wiring ``run`` uses, without importing
    ``openai`` or constructing any client."""

    def __init__(self) -> None:
        self.provenance = ComposedModelRunProvenance(
            adapter_type="dry_run_stub",
            provider="none",
            requested_model="dry-run-stub",
            host_policy_sha256="0" * 64,
            tool_schema_sha256="0" * 64,
            configured_timeout_seconds=0.0,
            configured_max_retries=0,
            configured_max_output_tokens=0,
        )

    async def decide(self, context: HostDecisionContext) -> HostActionSpec:
        return HostActionSpec(action="stop")


def build_dry_run_adapter_factory() -> AdapterFactory:
    def factory(case_id: str, max_decisions: int) -> HostAgentAdapter:
        return _DryRunAdapter()

    return factory


def build_real_adapter_factory(plan: PilotExperimentPlan) -> AdapterFactory:
    """Only reached from ``run_live``, only after ``require_live_preconditions``
    has already passed."""
    from app.runner.real_host_adapter import RealHostAgentAdapter, build_openai_responses_client

    # build_openai_responses_client already returns the AsyncOpenAI().responses
    # resource (a ResponsesClient) -- pass it straight through; do NOT
    # dereference .responses again.
    responses_client = build_openai_responses_client(
        timeout_seconds=plan.timeout_seconds, max_retries=0
    )

    def factory(case_id: str, max_decisions: int) -> HostAgentAdapter:
        return RealHostAgentAdapter(
            responses_client,
            model=plan.model,
            max_output_tokens=plan.max_output_tokens,
            timeout_seconds=plan.timeout_seconds,
            max_retries=0,
            reasoning_effort=plan.reasoning_effort,
            max_decisions=max_decisions,
            case_id=case_id,
        )

    return factory


def build_dry_run_decision_point_adapter_factory() -> DecisionPointAdapterFactory:
    def factory(
        case_id: str, max_decisions: int, allowed_actions: tuple[str, ...]
    ) -> HostAgentAdapter:
        return _DryRunAdapter()

    return factory


def build_real_decision_point_adapter_factory(
    plan: PilotExperimentPlan,
) -> DecisionPointAdapterFactory:
    """Only reached from ``run_live`` for a decision_point plan, only after
    ``require_live_preconditions`` has already passed. Dispatches on the
    plan's model's provider: OpenAI models -> ``RealHostAgentAdapter``
    (unchanged, byte-for-byte); ``claude-sonnet-5`` -> the Phase 6C
    ``AnthropicHostAgentAdapter`` (its own low-effort request config, its
    own max_tokens). Each trial's adapter is restricted on the wire to
    exactly the ``allowed_actions`` its experiment's decision point
    permits."""
    provider = _provider_for(plan.model)

    if provider == "anthropic":
        from app.runner.anthropic_host_adapter import AnthropicHostAgentAdapter
        from app.runner.host_decision_client import build_anthropic_host_decision_client
        from app.runner.model_panel import ANTHROPIC_MAX_OUTPUT_TOKENS, LOW_EFFORT

        anthropic_client = build_anthropic_host_decision_client(
            timeout_seconds=plan.timeout_seconds, max_retries=0
        )

        def anthropic_factory(
            case_id: str, max_decisions: int, allowed_actions: tuple[str, ...]
        ) -> HostAgentAdapter:
            return AnthropicHostAgentAdapter(
                anthropic_client,
                model=plan.model,
                max_output_tokens=ANTHROPIC_MAX_OUTPUT_TOKENS,
                timeout_seconds=plan.timeout_seconds,
                reasoning_effort=LOW_EFFORT,
                max_decisions=max_decisions,
                case_id=case_id,
                allowed_actions=allowed_actions,
                canonical_actions=_PHASE_6B_CANONICAL_ACTIONS,
            )

        return anthropic_factory

    from app.runner.real_host_adapter import RealHostAgentAdapter, build_openai_responses_client

    responses_client = build_openai_responses_client(
        timeout_seconds=plan.timeout_seconds, max_retries=0
    )

    def factory(
        case_id: str, max_decisions: int, allowed_actions: tuple[str, ...]
    ) -> HostAgentAdapter:
        return RealHostAgentAdapter(
            responses_client,
            model=plan.model,
            max_output_tokens=plan.max_output_tokens,
            timeout_seconds=plan.timeout_seconds,
            max_retries=0,
            reasoning_effort=plan.reasoning_effort,
            max_decisions=max_decisions,
            case_id=case_id,
            allowed_actions=allowed_actions,
        )

    return factory


async def run_dry_run(plan: PilotExperimentPlan, run_id: str) -> dict:
    overlays = resolve_overlays(plan)
    fingerprint, schedule = _execution_fingerprint_for(plan, overlays)
    ledger = TrialLedger(RUN_DIR_ROOT / run_id)
    if plan.execution_mode == "decision_point":
        await run_decision_point_pilot(
            plan,
            overlays,
            ledger,
            build_dry_run_decision_point_adapter_factory(),
            local_transport_factory,
            fingerprint,
            schedule,
        )
    else:
        await run_pilot(
            plan,
            overlays,
            ledger,
            build_dry_run_adapter_factory(),
            local_transport_factory,
            fingerprint,
        )
    return finalize_summary(plan, overlays, ledger)


async def run_live(plan: PilotExperimentPlan, run_id: str) -> dict:
    require_live_preconditions(plan.model)
    overlays = resolve_overlays(plan)
    fingerprint, schedule = _execution_fingerprint_for(plan, overlays)
    ledger = TrialLedger(RUN_DIR_ROOT / run_id)
    if plan.execution_mode == "decision_point":
        await run_decision_point_pilot(
            plan,
            overlays,
            ledger,
            build_real_decision_point_adapter_factory(plan),
            local_transport_factory,
            fingerprint,
            schedule,
        )
    else:
        await run_pilot(
            plan,
            overlays,
            ledger,
            build_real_adapter_factory(plan),
            local_transport_factory,
            fingerprint,
        )
    return finalize_summary(plan, overlays, ledger)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="composed_live_pilot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "dry-run", "run"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--run-id", required=True)
        subparser.add_argument("--model", default=None)
        subparser.add_argument(
            "--plan",
            choices=sorted(FROZEN_PLAN_PATHS),
            default="v1",
            help="which frozen plan template: v1 (free-run) or v2 (decision-point).",
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    try:
        plan = load_frozen_plan(args.model, args.plan)

        if args.command == "preflight":
            report = preflight_report(plan, args.run_id)
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0

        if args.command == "dry-run":
            summary = asyncio.run(run_dry_run(plan, args.run_id))
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0

        summary = asyncio.run(run_live(plan, args.run_id))
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except (
        ComposedLivePilotConfigError,
        PilotResumeConfigMismatchError,
        PilotResumeFingerprintMismatchError,
        PilotResumeScheduleMismatchError,
    ) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
