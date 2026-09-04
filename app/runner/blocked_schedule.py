"""Deterministic BLOCKED execution schedule for the Phase 4B confirmatory
composed live study (Phase 4B kickoff).

Blocked randomization: for each model there are ``blocks_per_model`` blocks
(== ``trials_per_condition`` == 20). Every block contains each of the four
cells

    (sensitive_egress,      treatment)  -> live-sensitive-egress-treatment
    (sensitive_egress,      control)    -> live-sensitive-egress-control
    (adversarial_influence, treatment)  -> live-influence-treatment
    (adversarial_influence, control)    -> live-influence-control

exactly once; the ORDER within each block is shuffled with ONE frozen
scheduling seed. A single ``random.Random(seed)`` is advanced across the
model panel in its frozen order, so each model gets a distinct
block-permutation stream from the one seed.

The per-model 80-entry ordering is hashed (``model_schedule_sha256``) and
folded into that model's ``execution_fingerprint`` -- so changing the seed
(or the panel, or the cells) changes the fingerprint and a resume is
refused. The complete study schedule is frozen to
``benchmarks/composed/live_canary_v3_schedule.json`` before any execution;
resume re-derives the identical schedule from the same frozen inputs.

This module changes no prompt, overlay, policy, action surface, or outcome
logic -- it only fixes the order trials are dispatched in.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable

from pydantic import BaseModel

# The frozen Phase 4B model panel, in its frozen order (the rng is advanced
# model-by-model in exactly this order).
PHASE_4B_MODEL_PANEL: tuple[str, ...] = (
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
)

# The one frozen scheduling seed for Phase 4B. Arbitrary, fixed permanently
# at kickoff (canonical main 0578376...); changing it defines a different
# study, not a re-run of this one.
PHASE_4B_SCHEDULE_SEED: int = 20260401

PHASE_4B_BLOCKS_PER_MODEL: int = 20

# (experiment, condition, overlay_id) -- the four cells, in a fixed
# canonical order used only as the pre-shuffle list.
CELLS: tuple[tuple[str, str, str], ...] = (
    ("sensitive_egress", "treatment", "live-sensitive-egress-treatment"),
    ("sensitive_egress", "control", "live-sensitive-egress-control"),
    ("adversarial_influence", "treatment", "live-influence-treatment"),
    ("adversarial_influence", "control", "live-influence-control"),
)


class ScheduledTrial(BaseModel):
    model: str
    block_index: int
    position_in_block: int
    experiment: str
    condition: str
    overlay_id: str
    # per (model, cell) sequential index 0..blocks-1. Equals block_index
    # because each cell occurs exactly once per block. This is the value
    # that goes into the trial_id, so resume dedup is schedule-order
    # independent.
    trial_index: int


def _canonical(entries: list[ScheduledTrial]) -> str:
    return json.dumps([e.model_dump() for e in entries], sort_keys=True, separators=(",", ":"))


def schedule_sha256(entries: list[ScheduledTrial]) -> str:
    return hashlib.sha256(_canonical(entries).encode("utf-8")).hexdigest()


def build_study_schedule(
    *,
    models: tuple[str, ...] = PHASE_4B_MODEL_PANEL,
    seed: int = PHASE_4B_SCHEDULE_SEED,
    blocks_per_model: int = PHASE_4B_BLOCKS_PER_MODEL,
) -> dict[str, list[ScheduledTrial]]:
    """The full deterministic study schedule: {model -> ordered 80 trials}.
    One ``random.Random(seed)`` advanced model-by-model in ``models`` order,
    block-by-block, shuffling a copy of ``CELLS`` per block."""
    rng = random.Random(seed)
    study: dict[str, list[ScheduledTrial]] = {}
    for model in models:
        entries: list[ScheduledTrial] = []
        for block_index in range(blocks_per_model):
            order = list(CELLS)
            rng.shuffle(order)
            for position, (experiment, condition, overlay_id) in enumerate(order):
                entries.append(
                    ScheduledTrial(
                        model=model,
                        block_index=block_index,
                        position_in_block=position,
                        experiment=experiment,
                        condition=condition,
                        overlay_id=overlay_id,
                        trial_index=block_index,
                    )
                )
        study[model] = entries
    return study


def build_model_schedule(
    model: str,
    *,
    seed: int = PHASE_4B_SCHEDULE_SEED,
    blocks_per_model: int = PHASE_4B_BLOCKS_PER_MODEL,
    models: tuple[str, ...] = PHASE_4B_MODEL_PANEL,
) -> list[ScheduledTrial]:
    if model not in models:
        raise ValueError(f"model {model!r} is not in the frozen Phase 4B panel {list(models)}")
    return build_study_schedule(models=models, seed=seed, blocks_per_model=blocks_per_model)[model]


def model_schedule_sha256(
    model: str,
    *,
    seed: int = PHASE_4B_SCHEDULE_SEED,
    blocks_per_model: int = PHASE_4B_BLOCKS_PER_MODEL,
) -> str:
    return schedule_sha256(
        build_model_schedule(model, seed=seed, blocks_per_model=blocks_per_model)
    )


# ===========================================================================
# Phase 6B blocked schedule -- 40 overlays, 4 blocks/model, each block
# contains every overlay exactly once. Same one-frozen-seed mechanism as
# Phase 4B; a distinct seed. The Phase 4B constants/functions above are
# UNCHANGED.
# ===========================================================================

# Phase 6C: the external-family robustness model `claude-sonnet-5` is
# APPENDED after the three OpenAI models. Because one `random.Random(seed)`
# is advanced model-by-model in THIS order, the sol / terra / luna
# per-model schedules are byte-identical to the 3-model panel -- claude's
# blocks are the deterministic continuation of the same stream after luna.
# Only the overall study-schedule hash (a hash over the set of per-model
# hashes) changes, because the panel now has four entries.
PHASE_6B_MODEL_PANEL: tuple[str, ...] = (
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "claude-sonnet-5",
)
PHASE_6B_SCHEDULE_SEED: int = 20260615
PHASE_6B_BLOCKS_PER_MODEL: int = 4


def phase_6b_cells() -> tuple[tuple[str, str, str], ...]:
    """The 40 (experiment, condition, overlay_id) cells -- 20 RQ1 + 20 RQ2 --
    in a fixed canonical order used only as the per-block pre-shuffle list.
    Derived from the single stimulus source of truth
    (``mock_servers.composed_record_fixtures``)."""
    from mock_servers.composed_record_fixtures import RQ1_PAIRS, RQ2_PAIRS

    cells: list[tuple[str, str, str]] = []
    for pair in RQ1_PAIRS:
        cells.append(("sensitive_egress", "treatment", f"rq1-{pair.pair_id}-confidential"))
        cells.append(("sensitive_egress", "control", f"rq1-{pair.pair_id}-public"))
    for pair in RQ2_PAIRS:
        cells.append(("adversarial_influence", "treatment", f"rq2-{pair.pair_id}-adversarial"))
        cells.append(("adversarial_influence", "control", f"rq2-{pair.pair_id}-benign"))
    return tuple(cells)


PHASE_6B_OVERLAY_IDS: tuple[str, ...] = tuple(o for (_, _, o) in phase_6b_cells())


def build_phase_6b_study_schedule(
    *,
    models: tuple[str, ...] = PHASE_6B_MODEL_PANEL,
    seed: int = PHASE_6B_SCHEDULE_SEED,
    blocks_per_model: int = PHASE_6B_BLOCKS_PER_MODEL,
) -> dict[str, list[ScheduledTrial]]:
    """{model -> ordered blocks_per_model*40 trials}. One ``random.Random(seed)``
    advanced model-by-model in ``models`` order, block-by-block, shuffling a
    copy of the 40 cells per block. ``trial_index`` is the per-(model,cell)
    sequential index 0..blocks-1 (== block_index), so resume dedup is
    schedule-order independent."""
    cells = phase_6b_cells()
    rng = random.Random(seed)
    study: dict[str, list[ScheduledTrial]] = {}
    for model in models:
        entries: list[ScheduledTrial] = []
        for block_index in range(blocks_per_model):
            order = list(cells)
            rng.shuffle(order)
            for position, (experiment, condition, overlay_id) in enumerate(order):
                entries.append(
                    ScheduledTrial(
                        model=model,
                        block_index=block_index,
                        position_in_block=position,
                        experiment=experiment,
                        condition=condition,
                        overlay_id=overlay_id,
                        trial_index=block_index,
                    )
                )
        study[model] = entries
    return study


def build_phase_6b_model_schedule(
    model: str,
    *,
    seed: int = PHASE_6B_SCHEDULE_SEED,
    blocks_per_model: int = PHASE_6B_BLOCKS_PER_MODEL,
    models: tuple[str, ...] = PHASE_6B_MODEL_PANEL,
) -> list[ScheduledTrial]:
    if model not in models:
        raise ValueError(f"model {model!r} is not in the Phase 6B panel {list(models)}")
    return build_phase_6b_study_schedule(
        models=models, seed=seed, blocks_per_model=blocks_per_model
    )[model]


def build_phase_6b_schedule_artifact(
    *,
    models: tuple[str, ...] = PHASE_6B_MODEL_PANEL,
    seed: int = PHASE_6B_SCHEDULE_SEED,
    blocks_per_model: int = PHASE_6B_BLOCKS_PER_MODEL,
) -> dict:
    study = build_phase_6b_study_schedule(
        models=models, seed=seed, blocks_per_model=blocks_per_model
    )
    cells = phase_6b_cells()
    per_model = {model: [e.model_dump() for e in entries] for model, entries in study.items()}
    model_hashes = {model: schedule_sha256(entries) for model, entries in study.items()}
    study_hash = hashlib.sha256(
        json.dumps(model_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "study_id": "composed-live-canary-004",
        "study_version": "v4",
        "scheduling_seed": seed,
        "model_panel": list(models),
        "blocks_per_model": blocks_per_model,
        "overlays_per_block": len(cells),
        "trials_per_model": blocks_per_model * len(cells),
        "cells": [{"experiment": e, "condition": c, "overlay_id": o} for (e, c, o) in cells],
        "randomization": "blocked; within-block order shuffled by one random.Random(seed)",
        "per_model_schedule": per_model,
        "model_schedule_sha256": model_hashes,
        "study_schedule_sha256": study_hash,
    }


# ===========================================================================
# Phase 7A blocked schedule -- the RQ1-ONLY neutral-baseline extension.
#
# 10 record scenarios x 3 arms (confidential / neutral / public) = 30
# overlays; 4 blocks/model; each block contains every pair x arm exactly
# once => 120 trials/model; the frozen four-model panel => 480 trials.
#
# Same one-frozen-seed mechanism as Phase 4B/6B; a DISTINCT seed. All Phase
# 4B and Phase 6B constants/functions above are UNCHANGED, and Phase 6
# observations are never pooled into the Phase 7 primary analysis. Every
# Phase 7A cell is (experiment="sensitive_egress", condition in
# {treatment, neutral, control}). No RQ2 / adversarial_influence cell.
# ===========================================================================

PHASE_7A_MODEL_PANEL: tuple[str, ...] = PHASE_6B_MODEL_PANEL
# The one frozen Phase 7A scheduling seed. Arbitrary, fixed permanently at
# the Phase 7A design freeze; changing it defines a different study.
PHASE_7A_SCHEDULE_SEED: int = 20260831
PHASE_7A_BLOCKS_PER_MODEL: int = 4
# arm -> (overlay-id suffix, ledger condition)
PHASE_7A_ARM_CONDITION: tuple[tuple[str, str], ...] = (
    ("confidential", "treatment"),
    ("neutral", "neutral"),
    ("public", "control"),
)


def phase_7a_cells() -> tuple[tuple[str, str, str], ...]:
    """The 30 (experiment, condition, overlay_id) cells -- 10 RQ1 record
    pairs x 3 arms -- in a fixed canonical order used only as the per-block
    pre-shuffle list. Derived from the frozen Phase 6B stimulus source of
    truth; the neutral arm reuses the same pair ids."""
    from mock_servers.composed_record_fixtures import RQ1_PAIRS

    cells: list[tuple[str, str, str]] = []
    for pair in RQ1_PAIRS:
        for arm, condition in PHASE_7A_ARM_CONDITION:
            cells.append(("sensitive_egress", condition, f"rq1-{pair.pair_id}-{arm}"))
    return tuple(cells)


PHASE_7A_OVERLAY_IDS: tuple[str, ...] = tuple(o for (_, _, o) in phase_7a_cells())


def build_phase_7a_study_schedule(
    *,
    models: tuple[str, ...] = PHASE_7A_MODEL_PANEL,
    seed: int = PHASE_7A_SCHEDULE_SEED,
    blocks_per_model: int = PHASE_7A_BLOCKS_PER_MODEL,
) -> dict[str, list[ScheduledTrial]]:
    """{model -> ordered blocks_per_model*30 trials}. One ``random.Random(
    seed)`` advanced model-by-model in ``models`` order, block-by-block,
    shuffling a copy of the 30 cells per block. ``trial_index`` is the
    per-(model,cell) sequential index 0..blocks-1 (== block_index)."""
    cells = phase_7a_cells()
    rng = random.Random(seed)
    study: dict[str, list[ScheduledTrial]] = {}
    for model in models:
        entries: list[ScheduledTrial] = []
        for block_index in range(blocks_per_model):
            order = list(cells)
            rng.shuffle(order)
            for position, (experiment, condition, overlay_id) in enumerate(order):
                entries.append(
                    ScheduledTrial(
                        model=model,
                        block_index=block_index,
                        position_in_block=position,
                        experiment=experiment,
                        condition=condition,
                        overlay_id=overlay_id,
                        trial_index=block_index,
                    )
                )
        study[model] = entries
    return study


def build_phase_7a_model_schedule(
    model: str,
    *,
    seed: int = PHASE_7A_SCHEDULE_SEED,
    blocks_per_model: int = PHASE_7A_BLOCKS_PER_MODEL,
    models: tuple[str, ...] = PHASE_7A_MODEL_PANEL,
) -> list[ScheduledTrial]:
    if model not in models:
        raise ValueError(f"model {model!r} is not in the Phase 7A panel {list(models)}")
    return build_phase_7a_study_schedule(
        models=models, seed=seed, blocks_per_model=blocks_per_model
    )[model]


def build_phase_7a_schedule_artifact(
    *,
    models: tuple[str, ...] = PHASE_7A_MODEL_PANEL,
    seed: int = PHASE_7A_SCHEDULE_SEED,
    blocks_per_model: int = PHASE_7A_BLOCKS_PER_MODEL,
) -> dict:
    study = build_phase_7a_study_schedule(
        models=models, seed=seed, blocks_per_model=blocks_per_model
    )
    cells = phase_7a_cells()
    per_model = {model: [e.model_dump() for e in entries] for model, entries in study.items()}
    model_hashes = {model: schedule_sha256(entries) for model, entries in study.items()}
    study_hash = hashlib.sha256(
        json.dumps(model_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "study_id": "composed-live-canary-007a",
        "study_version": "v7a",
        "scheduling_seed": seed,
        "model_panel": list(models),
        "blocks_per_model": blocks_per_model,
        "overlays_per_block": len(cells),
        "trials_per_model": blocks_per_model * len(cells),
        "cells": [{"experiment": e, "condition": c, "overlay_id": o} for (e, c, o) in cells],
        "randomization": "blocked; within-block order shuffled by one random.Random(seed)",
        "per_model_schedule": per_model,
        "model_schedule_sha256": model_hashes,
        "study_schedule_sha256": study_hash,
    }


def build_schedule_artifact(
    *,
    models: tuple[str, ...] = PHASE_4B_MODEL_PANEL,
    seed: int = PHASE_4B_SCHEDULE_SEED,
    blocks_per_model: int = PHASE_4B_BLOCKS_PER_MODEL,
) -> dict:
    """The frozen, persistable study-schedule document."""
    study = build_study_schedule(models=models, seed=seed, blocks_per_model=blocks_per_model)
    per_model = {model: [e.model_dump() for e in entries] for model, entries in study.items()}
    model_hashes = {model: schedule_sha256(entries) for model, entries in study.items()}
    study_hash = hashlib.sha256(
        json.dumps(model_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "study_id": "composed-live-canary-003",
        "study_version": "v3",
        "scheduling_seed": seed,
        "model_panel": list(models),
        "blocks_per_model": blocks_per_model,
        "trials_per_model": blocks_per_model * len(CELLS),
        "cells": [{"experiment": e, "condition": c, "overlay_id": o} for (e, c, o) in CELLS],
        "randomization": "blocked; within-block order shuffled by one random.Random(seed)",
        "per_model_schedule": per_model,
        "model_schedule_sha256": model_hashes,
        "study_schedule_sha256": study_hash,
    }


# ===========================================================================
# Phase 8 blocked schedules -- the journal-track re-study
# (docs/phase_8_design.md, docs/phase_8a_parameters.md). FIVE independent
# sub-studies (S8-A / S8-A' / S8-B / S8-C / S8-D; S8-E was cut -- see
# docs/phase_8a_parameters.md O7), each with its own cell set and its own
# rng stream derived from ONE frozen seed family
# (PHASE_8_SCHEDULE_SEED + a small fixed per-sub-study offset), so a
# change to one sub-study's scenarios/blocks never perturbs another's
# draw order. Same one-frozen-seed blocked-randomization mechanism as
# Phase 4B/6B/7A; Phase 8 observations are never pooled with Phase 6/7.
# ===========================================================================

PHASE_8_MODEL_PANEL: tuple[str, ...] = PHASE_7A_MODEL_PANEL
# The Phase 8 scheduling seed family (docs/phase_8a_parameters.md S4).
# Arbitrary, fixed permanently at the Phase 8A design freeze; changing it
# defines a different study.
PHASE_8_SCHEDULE_SEED: int = 20261101
# R (docs/phase_8a_parameters.md O2). S8-D uses its own fixed R=4
# regardless of the O2 decision (design S5.6).
PHASE_8_BLOCKS_PER_MODEL: int = 6
PHASE_8_POLICY_ROBUSTNESS_BLOCKS_PER_MODEL: int = 4

# Per-sub-study rng-stream offset: rng = random.Random(seed + offset).
PHASE_8_SUBSTUDY_SEED_OFFSET: dict[str, int] = {
    "v8a": 0,
    "v8a2": 1,
    "v8b": 2,
    "v8c": 3,
    "v8d": 4,
}
PHASE_8_SUBSTUDY_BLOCKS_PER_MODEL: dict[str, int] = {
    "v8a": PHASE_8_BLOCKS_PER_MODEL,
    "v8a2": PHASE_8_BLOCKS_PER_MODEL,
    "v8b": PHASE_8_BLOCKS_PER_MODEL,
    "v8c": PHASE_8_BLOCKS_PER_MODEL,
    "v8d": PHASE_8_POLICY_ROBUSTNESS_BLOCKS_PER_MODEL,
}


def phase_8a_cells() -> tuple[tuple[str, str, str], ...]:
    """S8-A -- core label x sink study: 24 scenarios x 3 label arms
    (confidential/unlabeled/public) x 2 sinks (a2a_relay/user_reply) = 144
    cells, in a fixed canonical order used only as the per-block
    pre-shuffle list."""
    from mock_servers.phase_8_fixtures import PHASE_8_SCENARIOS, arm_condition

    cells: list[tuple[str, str, str]] = []
    for scenario in PHASE_8_SCENARIOS:
        for arm in ("confidential", "unlabeled", "public"):
            for sink in ("a2a_relay", "user_reply"):
                cells.append(
                    ("sensitive_egress", arm_condition(arm), f"p8a-{scenario}-{arm}-{sink}")
                )
    return tuple(cells)


def phase_8a_prime_cells() -> tuple[tuple[str, str, str], ...]:
    """S8-A' -- the F_terse robustness mini-cell: the fixed 8-scenario
    subset x {unlabeled, public}, a2a_relay only (F_terse is not defined
    for user_reply) = 16 cells."""
    from mock_servers.phase_8_fixtures import PHASE_8_TERSE_MINI_CELL_SCENARIOS, arm_condition

    cells: list[tuple[str, str, str]] = []
    for scenario in PHASE_8_TERSE_MINI_CELL_SCENARIOS:
        for arm in ("unlabeled", "public"):
            cells.append(("sensitive_egress", arm_condition(arm), f"p8a2-{scenario}-{arm}"))
    return tuple(cells)


def phase_8b_cells() -> tuple[tuple[str, str, str], ...]:
    """S8-B -- calibration: 24 scenarios x {suppress, permit}, a2a_relay
    only = 48 cells. Contrasts against S8-A's unlabeled cells for the same
    (model, scenario), joined in the analysis layer -- never re-run here."""
    from mock_servers.phase_8_fixtures import PHASE_8_SCENARIOS, arm_condition

    cells: list[tuple[str, str, str]] = []
    for scenario in PHASE_8_SCENARIOS:
        for arm in ("suppress", "permit"):
            cells.append(("sensitive_egress", arm_condition(arm), f"p8b-{scenario}-{arm}"))
    return tuple(cells)


def phase_8c_cells() -> tuple[tuple[str, str, str], ...]:
    """S8-C -- PUBLIC/OK-TO-SHARE wording ablation: 24 scenarios x
    {pub_only, ok_only}, a2a_relay only = 48 cells."""
    from mock_servers.phase_8_fixtures import PHASE_8_SCENARIOS, arm_condition

    cells: list[tuple[str, str, str]] = []
    for scenario in PHASE_8_SCENARIOS:
        for arm in ("pub_only", "ok_only"):
            cells.append(("sensitive_egress", arm_condition(arm), f"p8c-{scenario}-{arm}"))
    return tuple(cells)


def phase_8d_cells() -> tuple[tuple[str, str, str], ...]:
    """S8-D -- host-policy robustness: the fixed 12-scenario subset x
    {unlabeled, public}, a2a_relay only, under the `operational` policy
    (selected at overlay-generation time, not encoded in the cell) = 24
    cells."""
    from mock_servers.phase_8_fixtures import PHASE_8_POLICY_ROBUSTNESS_SCENARIOS, arm_condition

    cells: list[tuple[str, str, str]] = []
    for scenario in PHASE_8_POLICY_ROBUSTNESS_SCENARIOS:
        for arm in ("unlabeled", "public"):
            cells.append(("sensitive_egress", arm_condition(arm), f"p8d-{scenario}-{arm}"))
    return tuple(cells)


PHASE_8_SUBSTUDY_CELL_FNS: dict[str, Callable[[], tuple[tuple[str, str, str], ...]]] = {
    "v8a": phase_8a_cells,
    "v8a2": phase_8a_prime_cells,
    "v8b": phase_8b_cells,
    "v8c": phase_8c_cells,
    "v8d": phase_8d_cells,
}


def phase_8_cells(substudy: str) -> tuple[tuple[str, str, str], ...]:
    if substudy not in PHASE_8_SUBSTUDY_CELL_FNS:
        raise ValueError(
            f"unknown Phase 8 sub-study {substudy!r}; expected one of "
            f"{sorted(PHASE_8_SUBSTUDY_CELL_FNS)}"
        )
    return PHASE_8_SUBSTUDY_CELL_FNS[substudy]()


PHASE_8_OVERLAY_IDS: dict[str, tuple[str, ...]] = {
    substudy: tuple(o for (_, _, o) in fn()) for substudy, fn in PHASE_8_SUBSTUDY_CELL_FNS.items()
}


def build_phase_8_study_schedule(
    substudy: str,
    *,
    models: tuple[str, ...] = PHASE_8_MODEL_PANEL,
    seed: int = PHASE_8_SCHEDULE_SEED,
    blocks_per_model: int | None = None,
) -> dict[str, list[ScheduledTrial]]:
    """{model -> ordered blocks_per_model*len(cells) trials} for one Phase 8
    sub-study. One ``random.Random(seed + PHASE_8_SUBSTUDY_SEED_OFFSET[
    substudy])`` advanced model-by-model in ``models`` order, block-by-
    block, shuffling a copy of that sub-study's cells per block.
    ``trial_index`` is the per-(model,cell) sequential index
    0..blocks-1 (== block_index)."""
    cells = phase_8_cells(substudy)
    blocks = (
        blocks_per_model
        if blocks_per_model is not None
        else PHASE_8_SUBSTUDY_BLOCKS_PER_MODEL[substudy]
    )
    rng = random.Random(seed + PHASE_8_SUBSTUDY_SEED_OFFSET[substudy])
    study: dict[str, list[ScheduledTrial]] = {}
    for model in models:
        entries: list[ScheduledTrial] = []
        for block_index in range(blocks):
            order = list(cells)
            rng.shuffle(order)
            for position, (experiment, condition, overlay_id) in enumerate(order):
                entries.append(
                    ScheduledTrial(
                        model=model,
                        block_index=block_index,
                        position_in_block=position,
                        experiment=experiment,
                        condition=condition,
                        overlay_id=overlay_id,
                        trial_index=block_index,
                    )
                )
        study[model] = entries
    return study


def build_phase_8_model_schedule(
    substudy: str,
    model: str,
    *,
    seed: int = PHASE_8_SCHEDULE_SEED,
    blocks_per_model: int | None = None,
    models: tuple[str, ...] = PHASE_8_MODEL_PANEL,
) -> list[ScheduledTrial]:
    if model not in models:
        raise ValueError(f"model {model!r} is not in the Phase 8 panel {list(models)}")
    return build_phase_8_study_schedule(
        substudy, models=models, seed=seed, blocks_per_model=blocks_per_model
    )[model]


PHASE_8_STUDY_IDS: dict[str, str] = {
    "v8a": "composed-live-canary-008a",
    "v8a2": "composed-live-canary-008a2",
    "v8b": "composed-live-canary-008b",
    "v8c": "composed-live-canary-008c",
    "v8d": "composed-live-canary-008d",
}


def build_phase_8_schedule_artifact(
    substudy: str,
    *,
    models: tuple[str, ...] = PHASE_8_MODEL_PANEL,
    seed: int = PHASE_8_SCHEDULE_SEED,
    blocks_per_model: int | None = None,
) -> dict:
    blocks = (
        blocks_per_model
        if blocks_per_model is not None
        else PHASE_8_SUBSTUDY_BLOCKS_PER_MODEL[substudy]
    )
    study = build_phase_8_study_schedule(
        substudy, models=models, seed=seed, blocks_per_model=blocks
    )
    cells = phase_8_cells(substudy)
    per_model = {model: [e.model_dump() for e in entries] for model, entries in study.items()}
    model_hashes = {model: schedule_sha256(entries) for model, entries in study.items()}
    study_hash = hashlib.sha256(
        json.dumps(model_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "study_id": PHASE_8_STUDY_IDS[substudy],
        "study_version": substudy,
        "scheduling_seed": seed + PHASE_8_SUBSTUDY_SEED_OFFSET[substudy],
        "model_panel": list(models),
        "blocks_per_model": blocks,
        "overlays_per_block": len(cells),
        "trials_per_model": blocks * len(cells),
        "cells": [{"experiment": e, "condition": c, "overlay_id": o} for (e, c, o) in cells],
        "randomization": "blocked; within-block order shuffled by one random.Random(seed)",
        "per_model_schedule": per_model,
        "model_schedule_sha256": model_hashes,
        "study_schedule_sha256": study_hash,
    }


# ===========================================================================
# Phase 8C gating pilot (P8-0) -- docs/phase_8_design.md S8. NOT part of any
# S8-* sub-study's manuscript effect number: its only job is to pick
# F_headroom against the pre-stated acceptance rules and report the
# N/calibration rates that motivated the choice. Its own schedule/overlay/
# analysis are entirely separate from S8-A..D.
# ===========================================================================

PHASE_8_PILOT_FRAMINGS: tuple[str, ...] = ("F1", "F2", "F3")
PHASE_8_PILOT_ARMS: tuple[str, ...] = ("suppress", "unlabeled", "public", "permit")
PHASE_8_PILOT_BLOCKS_PER_MODEL: int = 3


def phase_8_pilot_cells() -> tuple[tuple[str, str, str], ...]:
    """3 framings x 4 arms x 4 pilot scenarios = 48 cells, a2a_relay only."""
    from mock_servers.phase_8_fixtures import PHASE_8_PILOT_SCENARIOS, arm_condition

    cells: list[tuple[str, str, str]] = []
    for framing in PHASE_8_PILOT_FRAMINGS:
        for scenario in PHASE_8_PILOT_SCENARIOS:
            for arm in PHASE_8_PILOT_ARMS:
                cells.append(
                    (
                        "sensitive_egress",
                        arm_condition(arm),
                        f"p8pilot-{framing}-{scenario}-{arm}",
                    )
                )
    return tuple(cells)


PHASE_8_SUBSTUDY_CELL_FNS["v8pilot"] = phase_8_pilot_cells
PHASE_8_SUBSTUDY_SEED_OFFSET["v8pilot"] = 5
PHASE_8_SUBSTUDY_BLOCKS_PER_MODEL["v8pilot"] = PHASE_8_PILOT_BLOCKS_PER_MODEL
PHASE_8_STUDY_IDS["v8pilot"] = "composed-live-canary-008pilot"
PHASE_8_OVERLAY_IDS["v8pilot"] = tuple(o for (_, _, o) in phase_8_pilot_cells())
