"""Phase 9 (F3 resolution study) -- FROZEN stimulus fixtures for the runner.

Phase 9 is a NEW single-framing follow-up study. It never mutates,
re-pools, or reinterprets Phase 6 / 7 / 8; it imports the frozen stimulus
builders as sources of truth and adds only new symbols. Data only, no
network, no model call.

Every scenario in this module is derived **mechanically** from the
approved deterministic generator ``scripts/phase_9_build_scenarios.py``
(``build_scenarios()``); no field value is hand-authored here. Re-running
that generator and re-importing this module reproduces every byte.

What Phase 9 fixes (see ``docs/phase_9_f3_resolution_design.md``):

* **framing** -- ``F3`` verbatim (the frozen Phase 8 F3 ``a2a_relay``
  prompt), invariant across all 64 scenarios and both arms.
* **arms** -- ``N`` (unlabeled) and ``P`` (public). The ``P`` record body
  is byte-identical to ``N`` except a single leading
  ``"[PUBLIC - OK TO SHARE] "`` prefix.
* **scenarios** -- 64, in 8 fixed domains x 8, from the generator seed
  ``phase9-f3-resolution-scenarios-v1``.
* **model panel** -- the frozen four-model panel
  (``blocked_schedule.PHASE_6B_MODEL_PANEL``), analysed separately.
* **decision surface** -- ``{relay_to_remote, stop}`` under ``a2a_relay``,
  strict host policy, canonical action schema (unchanged from Phase 6/7/8).
* **primary outcome** -- ``any_sensitive_field_egress`` (L0 exact-substring
  over the six substantive values; canary excluded), frozen since Phase 6.

The model-visible retrieval id is an opaque ``rec-9-<8 hex>`` token
(hash-derived under a frozen salt DISTINCT from the Phase 7/8 salts); it
carries no scenario name, no arm word, no ordinal arm coding.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from scripts.phase_9_build_scenarios import (
    DOMAINS,
    F3_TASK_TEXT,
    SCEN_SEED,
    SCENARIOS_PER_DOMAIN,
    build_scenarios,
)

from app.runner.blocked_schedule import PHASE_6B_MODEL_PANEL
from mock_servers.composed_record_fixtures import PUBLIC_LABEL, RecordFields, record_body
from mock_servers.phase_7a_neutral_fixtures import neutral_record_body

__all__ = [
    "PHASE_9_ARMS",
    "PHASE_9_ARM_HEADER",
    "PHASE_9_DOMAINS",
    "PHASE_9_DOMAIN_CODES",
    "PHASE_9_FRAMING_ID",
    "PHASE_9_F3_TASK_TEXT",
    "PHASE_9_MODEL_PANEL",
    "PHASE_9_PUBLIC_PREFIX",
    "PHASE_9_RECORD_REF_SALT",
    "PHASE_9_SCENARIOS_PER_DOMAIN",
    "PHASE_9_SCENARIO_IDS",
    "PHASE_9_SCEN_SEED",
    "PHASE_9_SINK",
    "all_phase_9_field_values",
    "phase_9_canary_token",
    "phase_9_domain_of",
    "phase_9_fields",
    "phase_9_fixture_sha256",
    "phase_9_record_body",
    "phase_9_record_ref",
    "phase_9_ref_lookup",
    "phase_9_scenario_row",
    "phase_9_scenario_table",
]

# --------------------------------------------------------------------------- #
# frozen top-level constants
# --------------------------------------------------------------------------- #
PHASE_9_FRAMING_ID = "F3"
PHASE_9_SINK = "a2a_relay"
PHASE_9_F3_TASK_TEXT = F3_TASK_TEXT
PHASE_9_ARMS: tuple[str, str] = ("N", "P")
PHASE_9_PUBLIC_PREFIX = f"[{PUBLIC_LABEL}] "
# arm -> the opening label line the model sees (empty for N).
PHASE_9_ARM_HEADER: dict[str, str] = {"N": "", "P": f"[{PUBLIC_LABEL}]"}
PHASE_9_MODEL_PANEL: tuple[str, ...] = PHASE_6B_MODEL_PANEL
PHASE_9_DOMAINS: tuple[str, ...] = tuple(d for d, _ in DOMAINS)
PHASE_9_DOMAIN_CODES: dict[str, str] = {d: code for d, code in DOMAINS}
PHASE_9_SCENARIOS_PER_DOMAIN = SCENARIOS_PER_DOMAIN
PHASE_9_SCEN_SEED = SCEN_SEED

# Opaque model-visible record-ref salt. DISTINCT from the Phase 7/8 salts
# -- changing it defines a different study.
PHASE_9_RECORD_REF_SALT = "phase9-record-ref-salt-v1"


@lru_cache(maxsize=1)
def _scenarios() -> tuple[dict, ...]:
    """The frozen 64-scenario panel, straight from the approved generator."""
    return tuple(build_scenarios())


@lru_cache(maxsize=1)
def _by_id() -> dict[str, dict]:
    return {s["id"]: s for s in _scenarios()}


PHASE_9_SCENARIO_IDS: tuple[str, ...] = tuple(s["id"] for s in _scenarios())


def phase_9_scenario_row(scenario_id: str) -> dict:
    """The raw generator row for one scenario id (fields, canary, bodies)."""
    return _by_id()[scenario_id]


def phase_9_fields(scenario_id: str) -> RecordFields:
    """The synthetic record for one scenario (mechanically from the generator)."""
    return _by_id()[scenario_id]["fields"]


def phase_9_domain_of(scenario_id: str) -> str:
    return _by_id()[scenario_id]["domain"]


def phase_9_canary_token(scenario_id: str) -> str:
    """The one shared provenance canary for the scenario (identical N and P)."""
    return _by_id()[scenario_id]["canary"]


def phase_9_record_body(arm: str, scenario_id: str) -> str:
    """The exact record string the mock ``get_account_record`` tool returns.

    ``N`` -> the Phase 7 unlabeled body (no opening label line).
    ``P`` -> ``record_body("PUBLIC - OK TO SHARE", ...)`` == byte-identical
    to ``N`` with a single ``"[PUBLIC - OK TO SHARE] "`` prefix.
    """
    if arm not in PHASE_9_ARMS:
        raise ValueError(f"unknown Phase 9 arm {arm!r} (expected one of {PHASE_9_ARMS})")
    row = _by_id()[scenario_id]
    fields, canary = row["fields"], row["canary"]
    if arm == "N":
        return neutral_record_body(fields, canary)
    return record_body(PUBLIC_LABEL, fields, canary)


def phase_9_record_ref(scenario_id: str, arm: str) -> str:
    """``rec-9-`` + first 8 hex of
    ``sha256(f"{PHASE_9_RECORD_REF_SALT}:{scenario_id}:{arm}")`` -- 13
    chars, no scenario name / arm word / ordinal coding."""
    if arm not in PHASE_9_ARMS:
        raise ValueError(f"unknown Phase 9 arm {arm!r}")
    raw = f"{PHASE_9_RECORD_REF_SALT}:{scenario_id}:{arm}".encode()
    return f"rec-9-{hashlib.sha256(raw).hexdigest()[:8]}"


def phase_9_ref_lookup() -> dict[str, tuple[str, str]]:
    """Frozen server-side map: opaque record ref -> (scenario_id, arm).
    Raises on any collision (there are none for the frozen salt)."""
    out: dict[str, tuple[str, str]] = {}
    for sid in PHASE_9_SCENARIO_IDS:
        for arm in PHASE_9_ARMS:
            ref = phase_9_record_ref(sid, arm)
            if ref in out:
                raise RuntimeError(f"opaque record-ref collision on {ref!r}")
            out[ref] = (sid, arm)
    return out


def all_phase_9_field_values() -> list[str]:
    """Every synthetic value that must NOT appear in any model-visible
    prompt / policy / tool description / Agent Card (guarded by a test)."""
    out: list[str] = []
    for sid in PHASE_9_SCENARIO_IDS:
        f = phase_9_fields(sid)
        out.extend(
            [f.full_name, f.email, f.phone, f.account_id, f.internal_note, f.credential_token]
        )
    return out


def phase_9_scenario_table() -> list[dict]:
    """A JSON-serialisable, order-stable description of all 64 scenarios --
    the canonical fixture representation the runner and the freeze manifest
    key on. Pure derivation from the generator; no hand-authored value."""
    rows: list[dict] = []
    for sid in PHASE_9_SCENARIO_IDS:
        row = _by_id()[sid]
        f = row["fields"]
        n_body = phase_9_record_body("N", sid)
        p_body = phase_9_record_body("P", sid)
        rows.append(
            {
                "scenario_id": sid,
                "domain": row["domain"],
                "domain_code": row["code"],
                "framing_id": PHASE_9_FRAMING_ID,
                "sink": PHASE_9_SINK,
                "task_text": PHASE_9_F3_TASK_TEXT,
                "canary_token": row["canary"],
                "fields": {
                    "full_name": f.full_name,
                    "email": f.email,
                    "phone": f.phone,
                    "account_id": f.account_id,
                    "internal_note": f.internal_note,
                    "credential_token": f.credential_token,
                },
                "arms": {
                    "N": {
                        "header_label": PHASE_9_ARM_HEADER["N"],
                        "record_ref": phase_9_record_ref(sid, "N"),
                        "record_body_sha256": hashlib.sha256(n_body.encode()).hexdigest(),
                    },
                    "P": {
                        "header_label": PHASE_9_ARM_HEADER["P"],
                        "record_ref": phase_9_record_ref(sid, "P"),
                        "record_body_sha256": hashlib.sha256(p_body.encode()).hexdigest(),
                    },
                },
                "p_is_n_plus_prefix": p_body == PHASE_9_PUBLIC_PREFIX + n_body,
            }
        )
    return rows


def phase_9_fixture_sha256() -> str:
    """SHA-256 of the canonical fixture representation (``phase_9_scenario_table``,
    compact-canonical JSON). The freeze manifest pins this value."""
    payload = json.dumps(phase_9_scenario_table(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
