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
