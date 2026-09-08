"""Phase 9 (F3 resolution study) -- execution-ATTEMPT freeze.

The Phase 9 SCIENTIFIC design is frozen at commit
``32a76bfa19c3240bd87011fe9a7e41b3ced1a511`` and the execution
IMPLEMENTATION at ``a347a8b3c2b29b77586a113fdabf8bd310e92e85``. Neither is
changed by this file.

Frozen design section 12 requires a **re-freeze before any re-run**. This
script records one such attempt-level freeze. It changes **no** scientific
or execution-implementation parameter -- it only pins:

* which attempt this is;
* that the prior attempt(s) were aborted for an external reason and
  contribute zero scientific observations;
* that the same frozen 1,536-row schedule / scenarios / overlays /
  provider configs / analysis / halt rule are reused verbatim;
* the archived aborted-attempt artifact hashes;
* that the real scientific output directories are pristine.

Attempt 001 was aborted 2026-09-08 after 9 ``gpt-5.6-sol`` calls, all
HTTP 429 ``insufficient_quota`` -- zero successful model responses, zero
tokens, $0, halted under section 12. It is archived (byte-identical) at
``reports/_phase9_aborted_billing_attempt_001/`` (git-ignored).

Writes ``docs/phase_9_execution_attempt_002_manifest.json``. Deterministic
/ byte-reproducible (``--check`` and a unit test enforce it). Makes NO
provider call. Executes NO trial.

Run:  uv run python scripts/phase_9_attempt_freeze.py           # write + verify
      uv run python scripts/phase_9_attempt_freeze.py --check   # verify only
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

SCIENTIFIC_FREEZE_COMMIT = "32a76bfa19c3240bd87011fe9a7e41b3ced1a511"
EXECUTION_IMPLEMENTATION_FREEZE_COMMIT = "a347a8b3c2b29b77586a113fdabf8bd310e92e85"

ATTEMPT_ID = "002"
# Pinned once; stable across rebuilds so the manifest stays byte-reproducible.
ATTEMPT_FREEZE_UTC = "2026-09-08T22:36:30Z"

MANIFEST_PATH = _ROOT / "docs" / "phase_9_execution_attempt_002_manifest.json"
_SCI_MANIFEST = _ROOT / "docs" / "phase_9_freeze_manifest.json"
_ADD_MANIFEST = _ROOT / "docs" / "phase_9_execution_addendum_manifest.json"
_ABORTED_001 = _ROOT / "reports" / "_phase9_aborted_billing_attempt_001"

PHASE_9_MODEL_PANEL = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5")
REAL_OUTPUT_DIRS = {
    m: f"reports/experiments/phase-9-f3-{s}/"
    for m, s in zip(PHASE_9_MODEL_PANEL, ("sol", "terra", "luna", "claude"), strict=True)
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canon(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _pretty(obj: object) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _aborted_001_hashes() -> dict:
    """SHA-256 of every file in the archived aborted attempt (empty dict if
    the archive is absent -- it is git-ignored, may not be present on a
    fresh checkout)."""
    out: dict[str, str] = {}
    if not _ABORTED_001.is_dir():
        return {"_note": "archive not present on this checkout (git-ignored)"}
    for p in sorted(_ABORTED_001.rglob("*")):
        if p.is_file():
            out[p.relative_to(_ABORTED_001).as_posix()] = _sha256(p.read_bytes())
    return out


def _fresh_output_state() -> dict:
    """Confirm each real per-model output dir holds zero trial observations."""
    state: dict[str, str] = {}
    for model, rel in REAL_OUTPUT_DIRS.items():
        trials = _ROOT / rel / "trials.jsonl"
        if not (_ROOT / rel).exists():
            state[model] = "pristine (directory absent)"
        elif not trials.exists() or not trials.read_text().strip():
            state[model] = "pristine (no trials.jsonl observations)"
        else:
            n = len([x for x in trials.read_text().splitlines() if x.strip()])
            state[model] = f"NOT PRISTINE ({n} trial rows present)"
    return state


def build_manifest() -> dict:
    sci = json.loads(_SCI_MANIFEST.read_text())
    add = json.loads(_ADD_MANIFEST.read_text())
    plan = next(
        r
        for r in add["components"]
        if r["path"] == "benchmarks/composed/live_canary_plan_phase9.json"
    )
    overlays = next(
        r for r in add["components"] if r["path"] == "benchmarks/composed/live_overlays_phase9.yaml"
    )
    body = {
        "phase": 9,
        "kind": "EXECUTION-ATTEMPT FREEZE",
        "attempt_id": ATTEMPT_ID,
        "attempt_freeze_utc": ATTEMPT_FREEZE_UTC,
        "reason_for_rerun": (
            "attempt 001 was aborted by an EXTERNAL provider-billing failure: 9 gpt-5.6-sol "
            "calls, every one HTTP 429 insufficient_quota, ZERO successful model responses, "
            "zero generated tokens, $0 cost, halted under frozen design section 12. Billing "
            "was subsequently replenished on both OpenAI and Anthropic."
        ),
        "not_outcome_based_rerun": (
            "no model output was ever observed in attempt 001 (0 successful responses, 0 "
            "tokens); the frozen section-12 halt rule prohibits analysing partial data; no "
            "confirmatory or sensitivity analysis was run. The rerun is triggered solely by "
            "an external account state, not by any observed scientific result."
        ),
        "scientific_freeze_unchanged": True,
        "execution_implementation_unchanged": True,
        "no_scientific_parameter_changed": True,
        "no_execution_parameter_changed": True,
        "scientific_freeze_commit": SCIENTIFIC_FREEZE_COMMIT,
        "scientific_freeze_manifest_sha256": sci["manifest_sha256"],
        "execution_implementation_freeze_commit": EXECUTION_IMPLEMENTATION_FREEZE_COMMIT,
        "execution_addendum_manifest_sha256": add["addendum_manifest_sha256"],
        "reused_verbatim": {
            "study_schedule_sha256": sci["derived_hashes"]["study_schedule_sha256"],
            "scenario_fixture_sha256": sci["derived_hashes"]["scenario_fixture_sha256"],
            "live_canary_plan_phase9_sha256": plan["sha256"],
            "live_overlays_phase9_sha256": overlays["sha256"],
            "total_planned_trials": 1536,
            "model_panel": list(PHASE_9_MODEL_PANEL),
            "model_execution_order": list(PHASE_9_MODEL_PANEL),
            "retry_behavior": "max_retries = 0; no replacement trials; no fallback model",
            "halt_rule": (
                "frozen design section 12: per (model, arm) cell 192 planned, >= 187 completed "
                "required; halt the moment a cell reaches 6 non-completions (187/192 "
                "unreachable) or on any indeterminate attempt -- operator-ratified"
            ),
            "analysis": "the hash-pinned scientific analysis implementation only; unchanged",
        },
        "aborted_attempt_001": {
            "archive_path": "reports/_phase9_aborted_billing_attempt_001/  (git-ignored)",
            "scientific_observations_contributed": 0,
            "successful_model_responses": 0,
            "generated_tokens": 0,
            "billed_cost_usd": 0.0,
            "provider_attempts": 9,
            "all_attempts_status": "HTTP 429 insufficient_quota",
            "halted_under": "frozen design section 12",
            "artifact_sha256": _aborted_001_hashes(),
        },
        "attempt_002_preconditions": {
            "starts_from_pristine_scientific_output_dirs": True,
            "real_output_dirs": REAL_OUTPUT_DIRS,
            "real_output_dir_state": _fresh_output_state(),
            "same_frozen_1536_row_schedule": True,
            "attempt_001_contributes_no_observations": True,
        },
        "execution_provenance_identity": (
            "the scientific trial IDs (p9-<model>-<scenario>-<arm>-r<repeat>, in "
            "phase_9_frozen_trial_map.json) are identical across attempts; the EXECUTION "
            "attempt is distinguished by (a) this manifest's attempt_id, (b) the archived "
            "attempt-001 directory, and (c) each fresh run's own execution_fingerprint.json "
            "+ started_at UTC. Attempt 002 does not overwrite attempt 001's journal."
        ),
        "authorization_state": (
            "attempt 002 PREPARED; a live run is a SEPARATE explicit authorization"
        ),
    }
    body["attempt_manifest_sha256"] = _sha256(_canon(body).encode())
    return body


def verify_attempt_manifest() -> list[str]:
    fails: list[str] = []
    if not MANIFEST_PATH.exists():
        return ["docs/phase_9_execution_attempt_002_manifest.json is missing"]
    on_disk = json.loads(MANIFEST_PATH.read_text())
    recorded = on_disk.get("attempt_manifest_sha256", "")
    body = {k: v for k, v in on_disk.items() if k != "attempt_manifest_sha256"}
    if _sha256(_canon(body).encode()) != recorded:
        fails.append("attempt manifest self-hash inconsistent with its body")
    rebuilt = build_manifest()
    if rebuilt["attempt_manifest_sha256"] != recorded:
        fails.append(
            "attempt manifest no longer reproduces -- a referenced frozen hash or the "
            "fresh-output state changed"
        )
    if on_disk.get("scientific_freeze_commit") != SCIENTIFIC_FREEZE_COMMIT:
        fails.append("scientific_freeze_commit drift")
    if (
        on_disk.get("execution_implementation_freeze_commit")
        != EXECUTION_IMPLEMENTATION_FREEZE_COMMIT
    ):
        fails.append("execution_implementation_freeze_commit drift")
    state = on_disk["attempt_002_preconditions"]["real_output_dir_state"]
    not_pristine = [m for m, s in state.items() if "NOT PRISTINE" in s]
    if not_pristine:
        fails.append(f"real output dir(s) not pristine: {not_pristine}")
    return fails


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in args
    text = _pretty(build_manifest())
    if check_only:
        on_disk = MANIFEST_PATH.read_text() if MANIFEST_PATH.exists() else "<absent>"
        ok = on_disk == text
        print(("OK   " if ok else "FAIL ") + str(MANIFEST_PATH.relative_to(_ROOT)))
        for p in verify_attempt_manifest():
            print(f"  - {p}")
        good = ok and not verify_attempt_manifest()
        print("ATTEMPT-002 FREEZE VERIFIED" if good else "ATTEMPT-002 FREEZE NOT OK")
        return 0 if good else 1
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(text)
    print(f"wrote {MANIFEST_PATH.relative_to(_ROOT)}  ({len(text.encode())} bytes)")
    return main(["--check"])


if __name__ == "__main__":
    raise SystemExit(main())
