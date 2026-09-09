"""Phase 9 (F3 resolution study) -- RAW-DATA FREEZE for execution attempt 002.

Frozen design section 14 step 4: before ANY scientific computation, freeze
the raw ``trials.jsonl`` with SHA-256 manifests **and archive an immutable
copy outside the run directory** (the Phase 8 round-one overwrite lesson).

This script:

1. copies the four completed per-model run directories
   ``reports/experiments/phase-9-f3-{sol,terra,luna,claude}/`` byte-identically
   into ``reports/_phase9_raw_data_freeze_attempt_002/raw/<model>/`` and
   verifies SHA-256 identity before and after;
2. writes ``reports/_phase9_raw_data_freeze_attempt_002/MANIFEST.sha256``
   (git-ignored, travels with the bytes);
3. writes the COMMITTED manifest
   ``docs/phase_9_raw_data_freeze_attempt_002_manifest.json`` -- SHA-256 of
   every raw artifact + a full execution-integrity summary + a self-hash,
   so the raw-data freeze is in version control even though ``reports/`` is
   git-ignored.

Deterministic / byte-reproducible (``--check`` and a unit test enforce
it). Makes NO provider call. Reads only already-written raw run artifacts.

Run:  uv run python scripts/phase_9_raw_data_freeze.py           # freeze + verify
      uv run python scripts/phase_9_raw_data_freeze.py --check   # verify only
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.runner.phase_9_schedule_loader import engine_trial_id, frozen_rows  # noqa: E402

SCIENTIFIC_FREEZE_COMMIT = "32a76bfa19c3240bd87011fe9a7e41b3ced1a511"
EXECUTION_IMPLEMENTATION_FREEZE_COMMIT = "a347a8b3c2b29b77586a113fdabf8bd310e92e85"
ATTEMPT_002_FREEZE_COMMIT = "e8fd793940458a88f5fd122a7065737bf4a109c5"
ATTEMPT_ID = "002"
# Pinned once; stable across rebuilds so the manifest stays byte-reproducible.
RAW_DATA_FREEZE_UTC = "2026-09-09T00:54:27Z"

MODELS = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5")
_SHORT = {
    "gpt-5.6-sol": "sol",
    "gpt-5.6-terra": "terra",
    "gpt-5.6-luna": "luna",
    "claude-sonnet-5": "claude",
}
_RUN_DIR = {m: _ROOT / "reports" / "experiments" / f"phase-9-f3-{_SHORT[m]}" for m in MODELS}
_RAW_FILES = (
    "trials.jsonl",
    "attempts.jsonl",
    "summary.json",
    "execution_fingerprint.json",
    "schedule.json",
    "plan.json",
    "phase_9_frozen_trial_map.json",
)

ARCHIVE = _ROOT / "reports" / "_phase9_raw_data_freeze_attempt_002"
MANIFEST_PATH = _ROOT / "docs" / "phase_9_raw_data_freeze_attempt_002_manifest.json"


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canon(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _pretty(obj: object) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


class RawDataFreezeError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# integrity summary computed straight from the run dirs
# --------------------------------------------------------------------------- #
def _integrity_summary() -> dict:
    per_model: dict[str, dict] = {}
    tot = Counter()
    arm_tot = Counter()
    dom_tot = Counter()
    problems: list[str] = []

    for m in MODELS:
        d = _RUN_DIR[m]
        recs = [json.loads(x) for x in (d / "trials.jsonl").read_text().splitlines() if x.strip()]
        att = [json.loads(x) for x in (d / "attempts.jsonl").read_text().splitlines() if x.strip()]
        summ = json.loads((d / "summary.json").read_text())
        fp = json.loads((d / "execution_fingerprint.json").read_text())
        fmap = json.loads((d / "phase_9_frozen_trial_map.json").read_text())

        starts = [a for a in att if a["event"] == "ATTEMPT_STARTED"]
        terms = [a for a in att if a["event"] in ("COMPLETED", "PROVIDER_PROTOCOL_ERROR")]
        tids = [r["trial_id"] for r in recs]
        completed = sum(1 for r in recs if r["status"] == "completed")
        failed = sum(1 for r in recs if r["status"] == "failed")
        indet = len(starts) - len(terms)
        prov = sum(r["decision_count"] for r in recs)
        by_arm = Counter()
        by_dom = Counter()
        cells: dict = {}
        for r in recs:
            sid, arm = r["overlay_id"].rsplit("-", 1)
            by_arm[arm] += 1
            by_dom[sid.rsplit("-", 1)[0].replace("p9-", "", 1)] += 1
            cells.setdefault((sid, arm), []).append(r["trial_index"])
        exp = [
            engine_trial_id(f"{r['scenario_id']}-{r['arm']}", r["block_index"])
            for r in frozen_rows(m)
        ]
        reqs = sorted(set(r["requested_model"] for r in recs))
        rets = sorted({r.get("returned_model") for r in recs})
        ti = sum(r["total_input_tokens"] for r in recs)
        to = sum(r["total_output_tokens"] for r in recs)
        fp_ok = all(
            (r["provenance"].get("execution_fingerprint") or {}).get("execution_fingerprint_sha256")
            == fp["execution_fingerprint_sha256"]
            for r in recs
        )
        order_ok = tids == exp

        tot["attempted"] += len(recs)
        tot["completed"] += completed
        tot["protocol_error"] += failed
        tot["indeterminate"] += indet
        tot["provider_calls"] += prov
        tot["tok_in"] += ti
        tot["tok_out"] += to
        arm_tot.update(by_arm)
        dom_tot.update(by_dom)

        if len(recs) != 384 or completed != 384:
            problems.append(f"{m}: recorded {len(recs)}, completed {completed}")
        if failed or indet:
            problems.append(f"{m}: failed={failed} indeterminate={indet}")
        if len(tids) != len(set(tids)):
            problems.append(f"{m}: duplicate trial id")
        if any(t not in fmap for t in tids):
            problems.append(f"{m}: foreign trial id")
        if set(r["decision_count"] for r in recs) != {1}:
            problems.append(f"{m}: retry (decision_count != 1)")
        if set(by_arm.values()) != {192}:
            problems.append(f"{m}: arm balance {dict(by_arm)}")
        if set(by_dom.values()) != {48}:
            problems.append(f"{m}: domain balance {dict(by_dom)}")
        if len(cells) != 128 or any(sorted(v) != [0, 1, 2] for v in cells.values()):
            problems.append(f"{m}: cells/repeats")
        if reqs != [m] or rets != [m]:
            problems.append(f"{m}: requested {reqs} returned {rets}")
        if not order_ok:
            problems.append(f"{m}: recorded order != frozen schedule order")
        if not fp_ok:
            problems.append(f"{m}: trial fingerprint mismatch")
        if (
            not summ["run_complete"]
            or summ["partial"]
            or summ["halted"]
            or summ["model_substitution_detected"]
        ):
            problems.append(f"{m}: summary not clean-complete")

        per_model[m] = {
            "recorded": len(recs),
            "completed": completed,
            "protocol_error": failed,
            "indeterminate": indet,
            "provider_calls": prov,
            "by_arm": dict(by_arm),
            "domain_balance_ok": set(by_dom.values()) == {48},
            "cells": len(cells),
            "recorded_order_equals_frozen_schedule": order_ok,
            "requested_model": reqs,
            "returned_model": rets,
            "no_retry": set(r["decision_count"] for r in recs) == {1},
            "tokens_input": ti,
            "tokens_output": to,
            "started_at": summ["started_at"],
            "finished_at": summ["finished_at"],
            "execution_fingerprint_sha256": fp["execution_fingerprint_sha256"],
            "all_trials_carry_execution_fingerprint": fp_ok,
        }

    return {
        "expected_total_trials": 1536,
        "attempted": tot["attempted"],
        "completed": tot["completed"],
        "protocol_error": tot["protocol_error"],
        "indeterminate": tot["indeterminate"],
        "total_provider_calls": tot["provider_calls"],
        "per_arm_total": dict(arm_tot),
        "per_domain_total": dict(sorted(dom_tot.items())),
        "tokens_input_total": tot["tok_in"],
        "tokens_output_total": tot["tok_out"],
        "tokens_total": tot["tok_in"] + tot["tok_out"],
        "per_model": per_model,
        "problems": problems,
        "verdict": "PASS" if not problems else "FAIL",
    }


# --------------------------------------------------------------------------- #
# archive (byte-identical copy) + manifest
# --------------------------------------------------------------------------- #
def _copy_archive() -> None:
    for m in MODELS:
        src = _RUN_DIR[m]
        dst = ARCHIVE / "raw" / _SHORT[m]
        dst.mkdir(parents=True, exist_ok=True)
        for name in _RAW_FILES:
            s = src / name
            if not s.exists():
                raise RawDataFreezeError(f"missing raw file: {s}")
            data = s.read_bytes()
            (dst / name).write_bytes(data)
            if _sha256((dst / name).read_bytes()) != _sha256(data):
                raise RawDataFreezeError(f"copy not byte-identical: {name} ({m})")


def _archive_manifest_lines() -> list[str]:
    lines: list[str] = []
    for m in MODELS:
        for name in _RAW_FILES:
            p = ARCHIVE / "raw" / _SHORT[m] / name
            lines.append(f"{_sha256(p.read_bytes())}  raw/{_SHORT[m]}/{name}")
    return sorted(lines)


def _raw_hashes(root: Path) -> dict:
    out: dict[str, dict] = {}
    for m in MODELS:
        out[m] = {}
        base = root / _SHORT[m] if root.name == "raw" else root / "raw" / _SHORT[m]
        for name in _RAW_FILES:
            p = base / name
            b = p.read_bytes()
            out[m][name] = {"sha256": _sha256(b), "bytes": len(b)}
    return out


def build_manifest() -> dict:
    # hashes come from the LIVE run dirs (the archive is a verified copy)
    raw = {}
    for m in MODELS:
        raw[m] = {}
        for name in _RAW_FILES:
            b = (_RUN_DIR[m] / name).read_bytes()
            raw[m][name] = {"sha256": _sha256(b), "bytes": len(b)}
    body = {
        "phase": 9,
        "kind": "RAW-DATA FREEZE (pre-analysis)",
        "attempt_id": ATTEMPT_ID,
        "raw_data_freeze_utc": RAW_DATA_FREEZE_UTC,
        "scientific_freeze_commit": SCIENTIFIC_FREEZE_COMMIT,
        "execution_implementation_freeze_commit": EXECUTION_IMPLEMENTATION_FREEZE_COMMIT,
        "attempt_002_freeze_commit": ATTEMPT_002_FREEZE_COMMIT,
        "attempt_001_note": (
            "the aborted billing attempt 001 (9 gpt-5.6-sol calls, all HTTP 429, 0 successful "
            "responses, 0 tokens) is archived separately at "
            "reports/_phase9_aborted_billing_attempt_001/ and contributes NOTHING to this "
            "raw-data freeze or to any Phase 9 analysis."
        ),
        "live_run_dirs": {m: f"reports/experiments/phase-9-f3-{_SHORT[m]}/" for m in MODELS},
        "immutable_archive": (
            "reports/_phase9_raw_data_freeze_attempt_002/  "
            "(git-ignored; byte-identical copy, SHA-256 verified)"
        ),
        "raw_artifact_sha256": raw,
        "execution_integrity": _integrity_summary(),
        "analysis_not_yet_run": True,
    }
    body["raw_data_freeze_manifest_sha256"] = _sha256(_canon(body).encode())
    return body


def verify() -> list[str]:
    fails: list[str] = []
    if not MANIFEST_PATH.exists():
        return ["docs/phase_9_raw_data_freeze_attempt_002_manifest.json is missing"]
    on_disk = json.loads(MANIFEST_PATH.read_text())
    rec = on_disk.get("raw_data_freeze_manifest_sha256", "")
    body = {k: v for k, v in on_disk.items() if k != "raw_data_freeze_manifest_sha256"}
    if _sha256(_canon(body).encode()) != rec:
        fails.append("manifest self-hash inconsistent with its body")
    if build_manifest()["raw_data_freeze_manifest_sha256"] != rec:
        fails.append("manifest no longer reproduces from the run dirs -- raw data changed")
    if on_disk["execution_integrity"]["verdict"] != "PASS":
        fails.append(f"integrity verdict {on_disk['execution_integrity']['verdict']}")
    # archive present + byte-identical
    if ARCHIVE.is_dir():
        for m in MODELS:
            for name in _RAW_FILES:
                a = ARCHIVE / "raw" / _SHORT[m] / name
                if not a.exists():
                    fails.append(f"archive missing {name} ({m})")
                elif _sha256(a.read_bytes()) != on_disk["raw_artifact_sha256"][m][name]["sha256"]:
                    fails.append(f"archive drift {name} ({m})")
    else:
        fails.append("immutable archive directory is absent")
    return fails


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in args
    if not check_only:
        _copy_archive()
        (ARCHIVE / "MANIFEST.sha256").write_text("\n".join(_archive_manifest_lines()) + "\n")
    text = _pretty(build_manifest())
    if check_only:
        on_disk = MANIFEST_PATH.read_text() if MANIFEST_PATH.exists() else "<absent>"
        ok = on_disk == text
        print(("OK   " if ok else "FAIL ") + str(MANIFEST_PATH.relative_to(_ROOT)))
        for p in verify():
            print(f"  - {p}")
        good = ok and not verify()
        print("RAW-DATA FREEZE VERIFIED" if good else "RAW-DATA FREEZE NOT OK")
        return 0 if good else 1
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(text)
    print(f"wrote {MANIFEST_PATH.relative_to(_ROOT)}  ({len(text.encode())} bytes)")
    print(f"archived -> {ARCHIVE.relative_to(_ROOT)}/  (byte-identical, verified)")
    return main(["--check"])


if __name__ == "__main__":
    raise SystemExit(main())
