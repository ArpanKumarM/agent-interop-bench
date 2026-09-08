"""Phase 9 (F3 resolution study) -- frozen execution-schedule loader / bridge.

POST-FREEZE EXECUTION-IMPLEMENTATION ADDENDUM. The scientific freeze is
commit ``32a76bfa19c3240bd87011fe9a7e41b3ced1a511``; nothing here changes a
scientific parameter.

The ONLY schedule authority for Phase 9 is the frozen JSON
``docs/phase_9_design/phase_9_execution_schedule.json`` (pinned in
``docs/phase_9_freeze_manifest.json``). This module does NOT regenerate the
Phase 9 ordering and does NOT contain a randomization algorithm -- it reads
the frozen rows in their exact stored order and converts each into the
generic execution engine's ``ScheduledTrial`` representation, then verifies
a strict 1:1 correspondence between the frozen ``trial_id`` and the engine
``trial_id`` (``f"{experiment_id}:{overlay_id}:{trial_index}"``).

No provider call. No network. Pure stdlib + the frozen inputs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.runner.blocked_schedule import ScheduledTrial

_ROOT = Path(__file__).resolve().parents[2]
FROZEN_SCHEDULE_PATH = _ROOT / "docs" / "phase_9_design" / "phase_9_execution_schedule.json"
FREEZE_MANIFEST_PATH = _ROOT / "docs" / "phase_9_freeze_manifest.json"

PHASE_9_EXPERIMENT_ID = "composed-live-canary-009"
PHASE_9_EXPERIMENT_VERSION = "v9"
PHASE_9_MODEL_PANEL: tuple[str, ...] = (
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "claude-sonnet-5",
)
# arm -> the coarse {treatment, control, neutral} condition tag the generic
# ledger/record model expects. Mirrors mock_servers.phase_8_fixtures:
# unlabeled/N -> "neutral", public/P -> "control".
_ARM_CONDITION: dict[str, str] = {"N": "neutral", "P": "control"}
_PHASE_9_EXPERIMENT = "sensitive_egress"


class Phase9ScheduleError(RuntimeError):
    """The frozen schedule failed a structural / integrity / bijection check.
    Raised before any provider client is constructed."""


def overlay_id_for(scenario_id: str, arm: str) -> str:
    """The Phase 9 overlay id for one (scenario, arm) cell -- the key used in
    ``benchmarks/composed/live_overlays_phase9.yaml``."""
    if arm not in _ARM_CONDITION:
        raise Phase9ScheduleError(f"unknown Phase 9 arm {arm!r}")
    return f"{scenario_id}-{arm}"


def engine_trial_id(overlay_id: str, trial_index: int) -> str:
    return f"{PHASE_9_EXPERIMENT_ID}:{overlay_id}:{trial_index}"


def _load_frozen_document() -> dict:
    if not FROZEN_SCHEDULE_PATH.exists():
        raise Phase9ScheduleError(f"missing frozen schedule: {FROZEN_SCHEDULE_PATH}")
    doc = json.loads(FROZEN_SCHEDULE_PATH.read_text())

    # integrity: the frozen schedule file bytes must match the scientific
    # freeze manifest's recorded hash for it, and its own content hash must
    # match the manifest's derived study_schedule_sha256.
    if FREEZE_MANIFEST_PATH.exists():
        manifest = json.loads(FREEZE_MANIFEST_PATH.read_text())
        rel = "docs/phase_9_design/phase_9_execution_schedule.json"
        recorded = next((r for r in manifest["components"] if r["path"] == rel), None)
        on_disk = hashlib.sha256(FROZEN_SCHEDULE_PATH.read_bytes()).hexdigest()
        if recorded is None or recorded["sha256"] != on_disk:
            raise Phase9ScheduleError(
                "frozen schedule file bytes do not match docs/phase_9_freeze_manifest.json"
            )
        if doc["study_schedule_sha256"] != manifest["derived_hashes"]["study_schedule_sha256"]:
            raise Phase9ScheduleError(
                "frozen schedule study_schedule_sha256 disagrees with the freeze manifest"
            )
    else:
        raise Phase9ScheduleError(f"missing freeze manifest: {FREEZE_MANIFEST_PATH}")

    if doc.get("study_id") != PHASE_9_EXPERIMENT_ID or doc.get("total_trials") != 1536:
        raise Phase9ScheduleError(
            "frozen schedule study_id / total_trials are not the Phase 9 values"
        )
    if list(doc.get("model_panel", [])) != list(PHASE_9_MODEL_PANEL):
        raise Phase9ScheduleError(f"frozen schedule model panel drift: {doc.get('model_panel')}")
    return doc


def frozen_rows(model: str | None = None) -> list[dict]:
    """The frozen schedule rows in their exact stored order. ``model`` filters
    to that model's 384-row slice (order preserved); ``None`` returns all
    1,536 rows in panel order."""
    doc = _load_frozen_document()
    per_model = doc["per_model_schedule"]
    if model is not None:
        if model not in per_model:
            raise Phase9ScheduleError(f"model {model!r} not in the frozen schedule")
        return list(per_model[model])
    rows: list[dict] = []
    for m in PHASE_9_MODEL_PANEL:
        rows.extend(per_model[m])
    return rows


def _row_to_scheduled_trial(row: dict) -> ScheduledTrial:
    arm = row["arm"]
    return ScheduledTrial(
        model=row["model"],
        block_index=row["block_index"],
        position_in_block=row["position_in_block"],
        experiment=_PHASE_9_EXPERIMENT,
        condition=_ARM_CONDITION[arm],
        overlay_id=overlay_id_for(row["scenario_id"], arm),
        # each (scenario, arm) cell appears once per block; block_index is the
        # 0..2 repeat index, unique per overlay_id -> the ledger dedup key
        # f"{experiment_id}:{overlay_id}:{trial_index}" is 1:1 with a frozen row.
        trial_index=row["block_index"],
    )


def load_phase_9_schedule(model: str) -> list[ScheduledTrial]:
    """That model's frozen 384-trial schedule as ``ScheduledTrial`` objects,
    in the exact frozen order. Raises ``Phase9ScheduleError`` on any
    structural or bijection failure -- before any provider client exists."""
    if model not in PHASE_9_MODEL_PANEL:
        raise Phase9ScheduleError(f"model {model!r} is not in the frozen Phase 9 panel")
    rows = frozen_rows(model)
    if len(rows) != 384:
        raise Phase9ScheduleError(f"expected 384 frozen rows for {model!r}, got {len(rows)}")

    entries = [_row_to_scheduled_trial(r) for r in rows]

    # ---- structural checks on this model's slice ----
    seen_engine: dict[str, dict] = {}
    seen_frozen: set[str] = set()
    cells: dict[tuple[str, str], list[int]] = {}
    for row, entry in zip(rows, entries, strict=True):
        if row["model"] != model:
            raise Phase9ScheduleError(f"row model {row['model']!r} != requested {model!r}")
        eid = engine_trial_id(entry.overlay_id, entry.trial_index)
        fid = row["trial_id"]
        if eid in seen_engine:
            raise Phase9ScheduleError(f"duplicate engine trial id {eid!r}")
        if fid in seen_frozen:
            raise Phase9ScheduleError(f"duplicate frozen trial id {fid!r}")
        # bijection: the frozen id must be exactly the model + overlay + repeat
        expected_fid = f"p9-{model}-{row['scenario_id']}-{row['arm']}-r{row['repeat']}"
        if fid != expected_fid:
            raise Phase9ScheduleError(f"frozen trial id {fid!r} != reconstruction {expected_fid!r}")
        if row["repeat"] != entry.trial_index + 1:
            raise Phase9ScheduleError(
                f"repeat/{row['repeat']} != trial_index+1/{entry.trial_index + 1}"
            )
        seen_engine[eid] = {"frozen_trial_id": fid, "row": row}
        seen_frozen.add(fid)
        cells.setdefault((row["scenario_id"], row["arm"]), []).append(row["repeat"])

    if len(seen_engine) != 384 or len(seen_frozen) != 384:
        raise Phase9ScheduleError("model slice does not contain 384 distinct trials")
    if len(cells) != 128:
        raise Phase9ScheduleError(f"expected 128 (scenario, arm) cells, got {len(cells)}")
    for key, reps in cells.items():
        if sorted(reps) != [1, 2, 3]:
            raise Phase9ScheduleError(f"cell {key} has repeats {sorted(reps)}, expected [1, 2, 3]")

    n = sum(1 for r in rows if r["arm"] == "N")
    p = sum(1 for r in rows if r["arm"] == "P")
    if (n, p) != (192, 192):
        raise Phase9ScheduleError(f"N/P not 192/192 for {model!r}: {(n, p)}")
    return entries


def frozen_trial_id_map(model: str) -> dict[str, str]:
    """{engine_trial_id -> frozen_trial_id} for one model -- recorded in each
    trial's provenance so the frozen id travels with the observation."""
    rows = frozen_rows(model)
    out: dict[str, str] = {}
    for row in rows:
        eid = engine_trial_id(overlay_id_for(row["scenario_id"], row["arm"]), row["block_index"])
        out[eid] = row["trial_id"]
    return out


def scenario_arm_for_engine_trial(model: str, engine_id: str) -> tuple[str, str, int]:
    """(scenario_id, arm, repeat) for an engine trial id -- used by the halt
    monitor to attribute a terminal record to its (model, arm) cell."""
    for row in frozen_rows(model):
        eid = engine_trial_id(overlay_id_for(row["scenario_id"], row["arm"]), row["block_index"])
        if eid == engine_id:
            return row["scenario_id"], row["arm"], row["repeat"]
    raise Phase9ScheduleError(f"engine trial id {engine_id!r} not in {model!r}'s frozen schedule")
