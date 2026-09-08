"""Write the Phase 8 artifacts -- the journal-track re-study
(``docs/phase_8_design.md``, ``docs/phase_8a_parameters.md``):

* ``benchmarks/composed/live_overlays_phase8.yaml`` -- one shared overlay
  file for all five sub-studies (S8-A / S8-A' / S8-B / S8-C / S8-D; S8-E
  was cut, see ``docs/phase_8a_parameters.md`` O7).
* ``benchmarks/composed/live_canary_plan_phase8{a,a2,b,c,d}.json`` -- one
  plan template per sub-study.
* ``benchmarks/composed/live_canary_phase8{a,a2,b,c,d}_schedule.json`` --
  the frozen blocked study schedule per sub-study.

Deterministic: re-running this reproduces every file byte-for-byte (a
regression test enforces it, mirroring ``freeze_phase_7a_artifacts``).
Makes NO provider call. Does NOT execute any trial. Does NOT touch any
Phase 6 or Phase 7 artifact.

**PROVISIONAL until the Phase 8C pilot picks ``F_headroom``.** Every
non-``F_terse`` overlay's prompt is built from ``HEADROOM_FRAMING``
(default ``"F1"``) -- design ``S8`` requires the pilot to choose F1/F2/F3
against pre-stated acceptance rules before the main study freezes. Calling
``main()`` with a different ``headroom_framing`` regenerates every affected
overlay/plan/schedule; nothing here freezes the choice on its own -- the
Phase 8A design freeze commit does, once the pilot result is in.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.cli.freeze_v4_artifacts import _AGENT_CARD, PHASE_6B_VISIBLE_TOOLS
from app.runner.blocked_schedule import (
    PHASE_8_SUBSTUDY_CELL_FNS,
    build_phase_8_schedule_artifact,
)
from app.runner.host_adapters import PHASE_6B_HOST_POLICY_TEXT
from mock_servers.phase_8_fixtures import (
    PHASE_8_LABEL_ARMS,
    PHASE_8_OPERATIONAL_POLICY_TEXT,
    arm_condition,
    phase_8_canary_key,
    phase_8_canary_token,
    phase_8_fields,
    phase_8_record_body,
    phase_8_record_ref,
    phase_8_user_prompt,
    substantive_values,
)

_BENCH = Path(__file__).resolve().parent.parent.parent / "benchmarks" / "composed"
OVERLAYS_PATH = _BENCH / "live_overlays_phase8.yaml"
PLAN_PATHS: dict[str, Path] = {
    "v8a": _BENCH / "live_canary_plan_phase8a.json",
    "v8a2": _BENCH / "live_canary_plan_phase8a2.json",
    "v8b": _BENCH / "live_canary_plan_phase8b.json",
    "v8c": _BENCH / "live_canary_plan_phase8c.json",
    "v8d": _BENCH / "live_canary_plan_phase8d.json",
}
SCHEDULE_PATHS: dict[str, Path] = {
    "v8a": _BENCH / "live_canary_phase8a_schedule.json",
    "v8a2": _BENCH / "live_canary_phase8a2_schedule.json",
    "v8b": _BENCH / "live_canary_phase8b_schedule.json",
    "v8c": _BENCH / "live_canary_phase8c_schedule.json",
    "v8d": _BENCH / "live_canary_phase8d_schedule.json",
}
# P8-0 gating pilot (design S8) -- a separate overlay file (never mixed
# into the main sub-studies' shared file, since it sweeps all 3 framing
# candidates, not HEADROOM_FRAMING).
PILOT_OVERLAYS_PATH = _BENCH / "live_overlays_phase8_pilot.yaml"
PILOT_PLAN_PATH = _BENCH / "live_canary_plan_phase8_pilot.json"
PILOT_SCHEDULE_PATH = _BENCH / "live_canary_phase8_pilot_schedule.json"

# PROVISIONAL default -- see module docstring. Re-pinned once the Phase 8C
# pilot (docs/phase_8_design.md S8) selects F_headroom.
HEADROOM_FRAMING = "F1"

# Phase 8 experiment ids, mirroring PHASE_8_STUDY_IDS in blocked_schedule.py.
_EXPERIMENT_IDS: dict[str, str] = {
    "v8a": "composed-live-canary-008a",
    "v8a2": "composed-live-canary-008a2",
    "v8b": "composed-live-canary-008b",
    "v8c": "composed-live-canary-008c",
    "v8d": "composed-live-canary-008d",
}

_SUBSTUDIES: tuple[str, ...] = ("v8a", "v8a2", "v8b", "v8c", "v8d")


def _record_field_values(scenario: str, arm: str) -> dict[str, str]:
    fields = phase_8_fields(scenario)
    canary = phase_8_canary_token(scenario)
    header = PHASE_8_LABEL_ARMS[arm][1]
    values = substantive_values(fields)
    values.update(
        canary_token=canary,
        header_label=header,
        full_record_text=phase_8_record_body(arm, fields, canary),
    )
    return values


def _allowed_sensitive_edges(arm: str, sink: str) -> list[dict[str, str]]:
    """Diagnostic-only axis (``decision_point_sensitive_egress`` in
    ``app.reporting.pilot_outcomes``); never consulted by the frozen L0
    primary detector. Mirrors the Phase 7A rule: the local_tool->host MCP
    edge is always declared; the host->remote A2A edge is additionally
    declared only for a "public-family" arm under the a2a_relay sink (a
    user_reply trial never exercises an A2A edge at all)."""
    edges = [{"source": "local_tool", "dest": "host", "protocol": "mcp"}]
    if sink == "a2a_relay" and arm in {"public", "pub_only", "ok_only", "permit"}:
        edges.append({"source": "host", "dest": "remote", "protocol": "a2a"})
    return edges


def _canary_sensitivity(arm: str) -> str:
    # Mirrors Phase 7A's _ARM_CANARY_SENSITIVITY: only the confidential
    # header itself is treated as declaring the canary "sensitive"; every
    # other arm (including the calibration arms, whose sensitivity comes
    # from the appended instruction, not the header) is "public". Also
    # diagnostic-only -- see _allowed_sensitive_edges.
    return "sensitive" if arm == "confidential" else "public"


def _overlay(
    *,
    overlay_id: str,
    scenario: str,
    arm: str,
    sink: str,
    framing: str,
    policy_text: str,
    researcher_note: str,
) -> dict:
    condition = arm_condition(arm)
    _kind = PHASE_8_LABEL_ARMS[arm][2]
    return {
        "id": overlay_id,
        "experiment": "sensitive_egress",
        "condition": condition,
        "user_prompt": phase_8_user_prompt(framing, sink, arm),
        "target_agent_card": _AGENT_CARD,
        "local_tool_name": "get_account_record",
        "local_tool_arguments": {"record_ref": phase_8_record_ref(scenario, arm)},
        "provenance_canaries": [{"name": "record-marker", "sensitivity": _canary_sensitivity(arm)}],
        "allowed_sensitive_edges": _allowed_sensitive_edges(arm, sink),
        "remote_artifact_text": "Understood, thank you.",
        "action_surface": "legacy_wrapper",
        "host_policy_text": policy_text,
        "visible_tool_names": list(PHASE_6B_VISIBLE_TOOLS),
        "canary_case_key": phase_8_canary_key(scenario),
        "sink": sink,
        "arm": arm,
        "task_framing_id": framing,
        "prompt_suffix_kind": _kind,
        "record_field_values": _record_field_values(scenario, arm),
        "researcher_notes": researcher_note,
    }


def _note(substudy: str, scenario: str, arm: str, sink: str, framing: str) -> str:
    return (
        f"Phase 8 {substudy} {scenario}/{arm}/{sink}/{framing}. Held "
        "byte-identical across every arm of this scenario: the six "
        "substantive values, field order, record skeleton, and the shared "
        "per-scenario canary token. The model-visible difference is exactly "
        "the record's opening label line (per PHASE_8_LABEL_ARMS) plus the "
        "opaque rec-8-<8hex> retrieval id, and -- across sinks -- the "
        "offered action set and the addressee wording already in "
        "user_prompt. See docs/phase_8_design.md."
    )


def _substudy_overlays(substudy: str) -> list[dict]:
    from app.runner.blocked_schedule import phase_8_cells

    cells = phase_8_cells(substudy)
    overlays: list[dict] = []
    for _experiment, _condition, overlay_id in cells:
        # overlay_id shapes (blocked_schedule.py, must match exactly):
        #   v8a  -> p8a-<scenario>-<arm>-<sink>
        #   v8a2 -> p8a2-<scenario>-<arm>              (sink=a2a_relay, F_terse)
        #   v8b  -> p8b-<scenario>-<arm>   (sink=a2a_relay, HEADROOM_FRAMING)
        #   v8c  -> p8c-<scenario>-<arm>   (sink=a2a_relay, HEADROOM_FRAMING)
        #   v8d  -> p8d-<scenario>-<arm>   (sink=a2a_relay, HEADROOM_FRAMING, operational policy)
        prefix = {"v8a": "p8a-", "v8a2": "p8a2-", "v8b": "p8b-", "v8c": "p8c-", "v8d": "p8d-"}[
            substudy
        ]
        body = overlay_id[len(prefix) :]
        if substudy == "v8a":
            scenario, arm, sink = body.rsplit("-", 2)
            framing = HEADROOM_FRAMING
        elif substudy == "v8a2":
            scenario, arm = body.rsplit("-", 1)
            sink, framing = "a2a_relay", "F_terse"
        else:
            scenario, arm = body.rsplit("-", 1)
            sink, framing = "a2a_relay", HEADROOM_FRAMING
        policy_text = (
            PHASE_8_OPERATIONAL_POLICY_TEXT if substudy == "v8d" else PHASE_6B_HOST_POLICY_TEXT
        )
        overlays.append(
            _overlay(
                overlay_id=overlay_id,
                scenario=scenario,
                arm=arm,
                sink=sink,
                framing=framing,
                policy_text=policy_text,
                researcher_note=_note(substudy, scenario, arm, sink, framing),
            )
        )
    return overlays


def _pilot_overlays() -> list[dict]:
    """P8-0 gating pilot (design S8): overlay id
    ``p8pilot-<framing>-<scenario>-<arm>``, a2a_relay only, strict policy.
    Unlike the main sub-studies, ``framing`` here is NOT
    ``HEADROOM_FRAMING`` -- the pilot is what DECIDES that value, so it
    sweeps all three candidates."""
    from app.runner.blocked_schedule import phase_8_pilot_cells

    overlays: list[dict] = []
    for _experiment, _condition, overlay_id in phase_8_pilot_cells():
        body = overlay_id[len("p8pilot-") :]
        framing, rest = body.split("-", 1)
        scenario, arm = rest.rsplit("-", 1)
        overlays.append(
            _overlay(
                overlay_id=overlay_id,
                scenario=scenario,
                arm=arm,
                sink="a2a_relay",
                framing=framing,
                policy_text=PHASE_6B_HOST_POLICY_TEXT,
                researcher_note=_note("v8pilot", scenario, arm, "a2a_relay", framing),
            )
        )
    return overlays


def build_pilot_overlays_doc() -> dict:
    return {
        "name": "agent-interop-composed-live-overlays-phase8-pilot",
        "version": "0.8.0-pilot",
        "overlays": _pilot_overlays(),
    }


def build_pilot_plan_doc() -> dict:
    from app.runner.blocked_schedule import build_phase_8_schedule_artifact, phase_8_pilot_cells

    schedule = build_phase_8_schedule_artifact("v8pilot")
    overlay_ids = [o for (_, _, o) in phase_8_pilot_cells()]
    n_conditions = len({c for (_, c, _) in phase_8_pilot_cells()})
    trials_per_model = schedule["trials_per_model"]
    return {
        "experiment_id": "composed-live-canary-008pilot",
        "experiment_version": "v8pilot",
        "model": "REPLACE_WITH_MODEL_ID",
        "overlay_ids": overlay_ids,
        "trials_per_condition": trials_per_model // n_conditions,
        "max_decisions_per_trial": 1,
        "max_total_decisions": trials_per_model,
        "timeout_seconds": 20.0,
        "max_output_tokens": 512,
        "reasoning_effort": "low",
        "execution_mode": "decision_point",
    }


def build_overlays_doc() -> dict:
    overlays: list[dict] = []
    for substudy in _SUBSTUDIES:
        overlays.extend(_substudy_overlays(substudy))
    return {
        "name": "agent-interop-composed-live-overlays-phase8",
        "version": "0.8.0",
        "overlays": overlays,
    }


def build_plan_doc(substudy: str) -> dict:
    schedule = build_phase_8_schedule_artifact(substudy)
    overlay_ids = [o for (_, _, o) in PHASE_8_SUBSTUDY_CELL_FNS[substudy]()]
    n_conditions = len({c for (_, c, _) in PHASE_8_SUBSTUDY_CELL_FNS[substudy]()})
    trials_per_model = schedule["trials_per_model"]
    return {
        "experiment_id": _EXPERIMENT_IDS[substudy],
        "experiment_version": substudy,
        "model": "REPLACE_WITH_MODEL_ID",
        "overlay_ids": overlay_ids,
        "trials_per_condition": trials_per_model // n_conditions,
        "max_decisions_per_trial": 1,
        "max_total_decisions": trials_per_model,
        "timeout_seconds": 20.0,
        "max_output_tokens": 512,
        "reasoning_effort": "low",
        "execution_mode": "decision_point",
    }


def main(argv: list[str] | None = None) -> int:
    OVERLAYS_PATH.write_text(
        yaml.safe_dump(build_overlays_doc(), sort_keys=False, width=100, allow_unicode=True)
    )
    written = [str(OVERLAYS_PATH)]
    summary: dict[str, dict] = {}
    for substudy in _SUBSTUDIES:
        plan = build_plan_doc(substudy)
        PLAN_PATHS[substudy].write_text(json.dumps(plan, indent=2) + "\n")
        written.append(str(PLAN_PATHS[substudy]))
        schedule = build_phase_8_schedule_artifact(substudy)
        SCHEDULE_PATHS[substudy].write_text(json.dumps(schedule, indent=2, sort_keys=True) + "\n")
        written.append(str(SCHEDULE_PATHS[substudy]))
        summary[substudy] = {
            "overlay_count": len(plan["overlay_ids"]),
            "trials_per_model": schedule["trials_per_model"],
            "study_schedule_sha256": schedule["study_schedule_sha256"],
        }
    print(
        json.dumps(
            {
                "headroom_framing": HEADROOM_FRAMING,
                "wrote": written,
                "substudies": summary,
            },
            indent=2,
        )
    )
    return 0


def main_pilot(argv: list[str] | None = None) -> int:
    """Writes the P8-0 pilot artifacts only (design S8) -- separate from
    ``main()``'s main-sub-study regeneration."""
    from app.runner.blocked_schedule import build_phase_8_schedule_artifact

    PILOT_OVERLAYS_PATH.write_text(
        yaml.safe_dump(build_pilot_overlays_doc(), sort_keys=False, width=100, allow_unicode=True)
    )
    plan = build_pilot_plan_doc()
    PILOT_PLAN_PATH.write_text(json.dumps(plan, indent=2) + "\n")
    schedule = build_phase_8_schedule_artifact("v8pilot")
    PILOT_SCHEDULE_PATH.write_text(json.dumps(schedule, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "wrote": [str(PILOT_OVERLAYS_PATH), str(PILOT_PLAN_PATH), str(PILOT_SCHEDULE_PATH)],
                "overlay_count": len(plan["overlay_ids"]),
                "trials_per_model": schedule["trials_per_model"],
                "study_schedule_sha256": schedule["study_schedule_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
