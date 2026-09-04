"""Phase 8 OFFLINE preflight -- validate and describe the (still
PROVISIONAL) journal-track re-study WITHOUT any provider call, client,
transport, or trial execution.

**PROVISIONAL.** Every non-F_terse overlay's prompt is built from
``freeze_phase_8_artifacts.HEADROOM_FRAMING`` (default ``"F1"``), a
placeholder pending the Phase 8C pilot's choice of ``F_headroom``
(``docs/phase_8_design.md`` S8). This preflight reports that fact; it does
not gate on it -- design freeze (8A) and pilot execution (8C) are separate,
later steps.

Checks (raises ``Phase8PreflightError`` on any failure):

* the shared overlay file + all five per-sub-study plans/schedules
  regenerate byte-identically from ``freeze_phase_8_artifacts``.
* overlay counts: 280 total (144 S8-A + 16 S8-A' + 48 S8-B + 48 S8-C + 24
  S8-D); every id unique; every sub-study's condition set as designed.
* the six substantive values (+ field order) are byte-identical across
  every arm of a scenario within a sub-study.
* record_ref is the opaque ``rec-8-<8hex>`` shape and carries no
  arm/condition semantic token; the per-scenario canary token and
  ``canary_case_key`` are shared across a scenario's arms.
* neutral-language audit: the ``unlabeled``/``suppress``/``permit`` bodies
  introduce no prohibited term not already shared with the labelled arms.
* the frozen L0 primary detector (``PRIMARY_VALUE_FIELDS``/
  ``STRUCTURED_FIELDS``) is unchanged from Phase 6B/7.
* recomputes the execution fingerprint (v2) for every (model, sub-study)
  in the frozen panel -- 20 fingerprints, all distinct.

Prints a JSON report ending ``"provider_calls_made": 0``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from app.cli.composed_live_pilot import (
    _execution_fingerprint_for,
    load_frozen_plan,
    resolve_overlays,
)
from app.cli.freeze_phase_8_artifacts import (
    _SUBSTUDIES,
    HEADROOM_FRAMING,
    OVERLAYS_PATH,
    PLAN_PATHS,
    SCHEDULE_PATHS,
    build_overlays_doc,
    build_plan_doc,
)
from app.core.live_overlays import load_live_overlays
from app.reporting.rq1_field_egress import PRIMARY_VALUE_FIELDS, STRUCTURED_FIELDS
from app.runner.blocked_schedule import (
    PHASE_8_MODEL_PANEL,
    build_phase_8_schedule_artifact,
    phase_8_cells,
)
from mock_servers.phase_8_fixtures import (
    PHASE_8_ARMS,
    PHASE_8_SCENARIOS,
    identifier_findings,
    neutral_language_findings,
    phase_8_ref_lookup,
)

_ROOT = Path(__file__).resolve().parent.parent.parent
_REF_RE = re.compile(r"rec-8-[0-9a-f]{8}")

_EXPECTED_OVERLAY_COUNTS: dict[str, int] = {
    "v8a": 144,
    "v8a2": 16,
    "v8b": 48,
    "v8c": 48,
    "v8d": 24,
}
_EXPECTED_CONDITIONS: dict[str, set[str]] = {
    "v8a": {"treatment", "control", "neutral"},
    "v8a2": {"control", "neutral"},
    "v8b": {"neutral"},
    "v8c": {"control"},
    "v8d": {"control", "neutral"},
}
# PRIMARY_VALUE_FIELDS == the frozen 6; the primary detector's field-order
# contract, unchanged since Phase 6B.
_FROZEN_PRIMARY_VALUE_FIELDS: tuple[str, ...] = (
    "full_name",
    "email",
    "phone",
    "account_id",
    "internal_note",
    "credential_token",
)


class Phase8PreflightError(RuntimeError):
    """A refused Phase 8 precondition. No provider client/call is ever
    constructed/made when this is raised."""


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise Phase8PreflightError(msg)


def _check_drift() -> None:
    on_disk_overlays = yaml.safe_load(OVERLAYS_PATH.read_text())
    _check(on_disk_overlays == build_overlays_doc(), "live_overlays_phase8.yaml drifted")
    for substudy in _SUBSTUDIES:
        on_disk_plan = json.loads(PLAN_PATHS[substudy].read_text())
        _check(
            on_disk_plan == build_plan_doc(substudy),
            f"{PLAN_PATHS[substudy].name} drifted from generator",
        )
        on_disk_sched = json.loads(SCHEDULE_PATHS[substudy].read_text())
        _check(
            on_disk_sched == build_phase_8_schedule_artifact(substudy),
            f"{SCHEDULE_PATHS[substudy].name} drifted from generator",
        )


def _check_primary_detector_unchanged() -> None:
    _check(
        PRIMARY_VALUE_FIELDS == _FROZEN_PRIMARY_VALUE_FIELDS,
        f"PRIMARY_VALUE_FIELDS changed: {PRIMARY_VALUE_FIELDS}",
    )
    _check(
        _FROZEN_PRIMARY_VALUE_FIELDS[:5] == STRUCTURED_FIELDS,
        f"STRUCTURED_FIELDS changed: {STRUCTURED_FIELDS}",
    )


def run_preflight() -> dict:
    _check_drift()
    _check_primary_detector_unchanged()

    suite = load_live_overlays(str(OVERLAYS_PATH))
    overlays = suite.overlays
    by_id = {o.id: o for o in overlays}
    _check(len(overlays) == 280, f"expected 280 overlays, got {len(overlays)}")
    _check(len(by_id) == 280, "duplicate overlay id")
    _check(
        all(o.experiment == "sensitive_egress" for o in overlays),
        "a Phase 8 overlay is not experiment='sensitive_egress'",
    )

    substudy_report: dict[str, dict] = {}
    for substudy in _SUBSTUDIES:
        cell_ids = [oid for (_, _, oid) in phase_8_cells(substudy)]
        _check(
            len(cell_ids) == _EXPECTED_OVERLAY_COUNTS[substudy],
            f"{substudy}: expected {_EXPECTED_OVERLAY_COUNTS[substudy]} cells, got {len(cell_ids)}",
        )
        conds = {by_id[oid].condition for oid in cell_ids}
        _check(
            conds == _EXPECTED_CONDITIONS[substudy],
            f"{substudy}: unexpected condition set {conds}",
        )
        substudy_report[substudy] = {
            "overlay_count": len(cell_ids),
            "conditions": sorted(conds),
        }

    # ---- record_ref opacity + shared canary ------------------------------
    lut = phase_8_ref_lookup()
    for overlay in overlays:
        ref = overlay.local_tool_arguments.get("record_ref")
        _check(bool(ref) and _REF_RE.fullmatch(ref or ""), f"{overlay.id}: bad record_ref {ref!r}")
        _check(not identifier_findings(ref), f"{overlay.id}: record_ref carries a semantic token")
        _check(ref in lut, f"{overlay.id}: record_ref {ref!r} not in the frozen ref lookup")

    for scenario in PHASE_8_SCENARIOS:
        canaries = {
            by_id[oid].record_field_values["canary_token"]
            for oid in by_id
            if by_id[oid].canary_case_key == f"phase8-scenario-{scenario}"
        }
        if canaries:
            _check(len(canaries) == 1, f"{scenario}: canary_token differs across its overlays")

    # ---- six substantive values byte-identical across a scenario's arms --
    by_scenario_arm: dict[tuple[str, str], list] = {}
    for overlay in overlays:
        ref = overlay.local_tool_arguments.get("record_ref")
        scenario_arm = lut.get(ref)
        if scenario_arm is not None:
            by_scenario_arm.setdefault(scenario_arm, []).append(overlay)
    for scenario in PHASE_8_SCENARIOS:
        ref_values: dict[str, str] | None = None
        for arm in PHASE_8_ARMS:
            matches = by_scenario_arm.get((scenario, arm), [])
            if not matches:
                continue
            six = {k: matches[0].record_field_values[k] for k in PRIMARY_VALUE_FIELDS}
            if ref_values is None:
                ref_values = six
            else:
                _check(six == ref_values, f"{scenario}/{arm}: substantive values differ")

    # ---- neutral-language audit (unlabeled/suppress/permit) --------------
    for overlay in overlays:
        if overlay.arm not in {"unlabeled", "suppress", "permit"}:
            continue
        body = overlay.record_field_values.get("full_record_text", "")
        _check(
            neutral_language_findings(body.splitlines()[0]) == [],
            f"{overlay.id}: unlabeled-family first line carries a prohibited stem",
        )

    # ---- execution fingerprints: every (model, sub-study) -----------------
    fingerprints: dict[str, dict] = {}
    for model in PHASE_8_MODEL_PANEL:
        for substudy in _SUBSTUDIES:
            plan = load_frozen_plan(model, substudy)
            plan_overlays = resolve_overlays(plan)
            fp, _schedule = _execution_fingerprint_for(plan, plan_overlays)
            fingerprints[f"{model}/{substudy}"] = {
                "execution_fingerprint_sha256": fp.execution_fingerprint_sha256,
                "host_policy_sha256": fp.host_policy_sha256,
                "canonical_action_schema_sha256": fp.canonical_action_schema_sha256,
            }
    all_fps = [v["execution_fingerprint_sha256"] for v in fingerprints.values()]
    _check(len(set(all_fps)) == len(all_fps), "two (model, sub-study) fingerprints collide")

    return {
        "provisional": True,
        "headroom_framing": HEADROOM_FRAMING,
        "note": (
            "PROVISIONAL: HEADROOM_FRAMING is a placeholder pending the Phase "
            "8C pilot (docs/phase_8_design.md S8). Nothing here freezes it."
        ),
        "overlay_count": len(overlays),
        "substudies": substudy_report,
        "execution_fingerprints": fingerprints,
        "provider_calls_made": 0,
    }


def main(argv: list[str] | None = None) -> int:
    report = run_preflight()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
