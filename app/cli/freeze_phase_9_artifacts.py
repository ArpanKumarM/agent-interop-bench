"""Phase 9 (F3 resolution study) -- build the credential-free execution
plan + overlays the generic decision-point engine requires.

POST-FREEZE EXECUTION-IMPLEMENTATION ADDENDUM. Scientific freeze
``32a76bfa19c3240bd87011fe9a7e41b3ced1a511`` is unchanged: every value
below is derived **mechanically** from the frozen Phase 9 fixture /
scenario data (``mock_servers.phase_9_fixtures``) and the frozen execution
parameters (``docs/phase_9_design/phase_9_execution_params.json``). No
per-scenario wording is authored here.

Writes:
* ``benchmarks/composed/live_canary_plan_phase9.json``  (PilotExperimentPlan, v9)
* ``benchmarks/composed/live_overlays_phase9.yaml``     (128 LiveExperimentOverlay)

Deterministic: re-running reproduces both files byte-for-byte (a unit test
and ``--check`` enforce it). Makes NO provider call. Executes NO trial.

Run:  uv run python -m app.cli.freeze_phase_9_artifacts            # write + verify
      uv run python -m app.cli.freeze_phase_9_artifacts --check    # verify only
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from app.cli.freeze_v4_artifacts import _AGENT_CARD, PHASE_6B_VISIBLE_TOOLS
from app.runner.host_adapters import PHASE_6B_HOST_POLICY_TEXT
from mock_servers.composed_record_fixtures import PUBLIC_LABEL
from mock_servers.phase_7a_neutral_fixtures import substantive_values
from mock_servers.phase_9_fixtures import (
    PHASE_9_ARMS,
    PHASE_9_F3_TASK_TEXT,
    PHASE_9_SCENARIO_IDS,
    phase_9_canary_token,
    phase_9_domain_of,
    phase_9_fields,
    phase_9_record_body,
    phase_9_record_ref,
)

_BENCH = Path(__file__).resolve().parent.parent.parent / "benchmarks" / "composed"
PLAN_PATH = _BENCH / "live_canary_plan_phase9.json"
OVERLAYS_PATH = _BENCH / "live_overlays_phase9.yaml"

PHASE_9_EXPERIMENT_ID = "composed-live-canary-009"
PHASE_9_EXPERIMENT_VERSION = "v9"
MODEL_PLACEHOLDER = "REPLACE_WITH_MODEL_ID"

# Frozen execution parameters (phase_9_execution_params.json / design section 2).
_TIMEOUT_SECONDS = 20.0
_OPENAI_MAX_OUTPUT_TOKENS = 512  # Anthropic path overrides with ANTHROPIC_MAX_OUTPUT_TOKENS
_REASONING_EFFORT = "low"
_TRIALS_PER_CONDITION = 3
_MAX_DECISIONS_PER_TRIAL = 1
_MAX_TOTAL_DECISIONS = 384  # per model: 64 scenarios x 2 arms x 3 repeats

# arm -> (coarse condition tag, opening label line shown in the record).
_ARM_CONDITION: dict[str, str] = {"N": "neutral", "P": "control"}
_ARM_HEADER: dict[str, str] = {"N": "", "P": f"[{PUBLIC_LABEL}]"}


def overlay_id_for(scenario_id: str, arm: str) -> str:
    return f"{scenario_id}-{arm}"


def _record_field_values(scenario_id: str, arm: str) -> dict[str, str]:
    fields = phase_9_fields(scenario_id)
    values = substantive_values(fields)
    values.update(
        canary_token=phase_9_canary_token(scenario_id),
        header_label=_ARM_HEADER[arm],
        full_record_text=phase_9_record_body(arm, scenario_id),
    )
    return values


def _allowed_sensitive_edges(arm: str) -> list[dict[str, str]]:
    """Diagnostic-only axis (never consulted by the frozen L0 detector).
    Mirrors Phase 7A: the local_tool->host MCP edge is always declared; the
    host->remote A2A edge is additionally declared only for the sharing-
    permitted (public / P) arm."""
    edges = [{"source": "local_tool", "dest": "host", "protocol": "mcp"}]
    if arm == "P":
        edges.append({"source": "host", "dest": "remote", "protocol": "a2a"})
    return edges


def _overlay(scenario_id: str, arm: str) -> dict:
    domain = phase_9_domain_of(scenario_id)
    return {
        "id": overlay_id_for(scenario_id, arm),
        "experiment": "sensitive_egress",
        "condition": _ARM_CONDITION[arm],
        "user_prompt": PHASE_9_F3_TASK_TEXT,
        "target_agent_card": _AGENT_CARD,
        "local_tool_name": "get_account_record",
        "local_tool_arguments": {"record_ref": phase_9_record_ref(scenario_id, arm)},
        # Phase 9 has no confidential arm; both arms carry a "public"-sensitivity
        # canary (diagnostic-only, model-invisible).
        "provenance_canaries": [{"name": "record-marker", "sensitivity": "public"}],
        "allowed_sensitive_edges": _allowed_sensitive_edges(arm),
        "remote_artifact_text": "Understood, thank you.",
        "action_surface": "legacy_wrapper",
        "host_policy_text": PHASE_6B_HOST_POLICY_TEXT,
        "visible_tool_names": list(PHASE_6B_VISIBLE_TOOLS),
        "canary_case_key": f"phase9-scenario-{scenario_id}",
        "sink": "a2a_relay",
        "arm": arm,
        "task_framing_id": "F3",
        "prompt_suffix_kind": "none",
        "record_field_values": _record_field_values(scenario_id, arm),
        "researcher_notes": (
            f"Phase 9 F3 resolution study, {scenario_id}/{arm}/a2a_relay/F3 "
            f"(domain {domain}). Held byte-identical across the N and P arms of this "
            "scenario: the six substantive values, field order, record skeleton and the "
            "shared per-scenario canary token. The only model-visible difference is the "
            "record's opening label line -- P is byte-identical to N with a single leading "
            f"'[{PUBLIC_LABEL}] ' prefix. Derived mechanically from "
            "scripts/phase_9_build_scenarios.py (scientific freeze 32a76bf); no per-scenario "
            "wording authored in this file."
        ),
    }


def build_overlays_doc() -> dict:
    overlays = [_overlay(sid, arm) for sid in PHASE_9_SCENARIO_IDS for arm in PHASE_9_ARMS]
    return {
        "name": "agent-interop-composed-live-overlays-phase9",
        "version": "0.9.0",
        "overlays": overlays,
    }


def build_plan_doc() -> dict:
    overlay_ids = [overlay_id_for(sid, arm) for sid in PHASE_9_SCENARIO_IDS for arm in PHASE_9_ARMS]
    return {
        "experiment_id": PHASE_9_EXPERIMENT_ID,
        "experiment_version": PHASE_9_EXPERIMENT_VERSION,
        "model": MODEL_PLACEHOLDER,
        "overlay_ids": overlay_ids,
        "trials_per_condition": _TRIALS_PER_CONDITION,
        "max_decisions_per_trial": _MAX_DECISIONS_PER_TRIAL,
        "max_total_decisions": _MAX_TOTAL_DECISIONS,
        "timeout_seconds": _TIMEOUT_SECONDS,
        "max_output_tokens": _OPENAI_MAX_OUTPUT_TOKENS,
        "reasoning_effort": _REASONING_EFFORT,
        "execution_mode": "decision_point",
    }


def _plan_text() -> str:
    return json.dumps(build_plan_doc(), indent=2) + "\n"


def _overlays_text() -> str:
    return yaml.safe_dump(build_overlays_doc(), sort_keys=False, width=100, allow_unicode=True)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in args
    targets = ((PLAN_PATH, _plan_text()), (OVERLAYS_PATH, _overlays_text()))
    ok = True
    for path, text in targets:
        if check_only:
            on_disk = path.read_text() if path.exists() else "<absent>"
            row_ok = on_disk == text
            ok &= row_ok
            print(f"{'OK  ' if row_ok else 'FAIL'} {path.name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote {path.name}  ({len(text.encode())} bytes)")
    if check_only:
        print("PHASE 9 EXECUTION ARTIFACTS REPRODUCE BYTE-FOR-BYTE:" if ok else "MISMATCH:", ok)
        return 0 if ok else 1
    return main(["--check"])


if __name__ == "__main__":
    raise SystemExit(main())
