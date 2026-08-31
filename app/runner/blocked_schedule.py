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
