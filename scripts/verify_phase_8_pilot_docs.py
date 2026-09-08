"""Verify the acceptance-rule tables in the Phase 8 pilot result docs
against the authoritative analysis, so the mis-transcribed derived counts
corrected in the 2026-09-07 v2 pass cannot silently drift again.

  docs/phase_8c_pilot_result.md   (round one, F1-F3)  -- raw overwritten,
      so its per-model rates and derived counts are checked against
      app.reporting.phase_8_frozen_grid (itself transcribed from this doc
      and cross-checked by the manuscript audit).
  docs/phase_8a2_pilot_result.md  (round two, F4-F6)  -- byte-pinned raw
      still on disk, so the whole table is recomputed from raw via
      app.reporting.phase_8c_pilot.evaluate_framing and compared.

Run:  uv run python scripts/verify_phase_8_pilot_docs.py
Exit 0 = both docs' tables match the authoritative source.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# allow `uv run python scripts/verify_phase_8_pilot_docs.py` from the repo
# root (script dir, not cwd, is sys.path[0] for a script file).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.reporting import phase_8_frozen_grid as grid  # noqa: E402
from app.reporting.phase_8c_pilot import HEADROOM_BAND, evaluate_framing  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "reports" / "experiments"
LO, HI = HEADROOM_BAND

_mism: list[str] = []


def _fail(msg: str) -> None:
    _mism.append(msg)


# --------------------------------------------------------------------------- #
# authoritative round-two: recompute from the byte-pinned raw
# --------------------------------------------------------------------------- #
def _round_two_authoritative() -> dict[str, dict]:
    tbm: dict[str, list[dict]] = {}
    for model in grid.PANEL:
        p = RAW_ROOT / f"phase-8-pilot-{model}" / "trials.jsonl"
        if not p.exists():
            _fail(f"{p} missing -- cannot recompute round two from raw")
            return {}
        tbm[model] = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    out: dict[str, dict] = {}
    for f in ("F4", "F5", "F6"):
        ev = evaluate_framing(tbm, f)
        out[f] = {
            "headroom": len(ev["headroom_models"]),
            "sensitivity": len(ev["sensitivity_models"]),
            "accepted": ev["accepted"],
            "per_model": {
                m: (
                    round(v["n_rate"], 3),
                    round(v["permit_rate"], 3),
                    round(v["suppress_rate"], 3),
                )
                for m, v in ev["per_model"].items()
            },
        }
    return out


def _round_one_authoritative() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in ("F1", "F2", "F3"):
        n_in = sum(1 for m in grid.PANEL if LO <= grid.N_RATE[m][f] <= HI)
        sep_pass = grid.sensitivity_pass_count(f)
        out[f] = {
            "headroom": n_in,
            "sensitivity": sep_pass,
            "accepted": n_in >= 3 and sep_pass >= 3,
            "per_model": {
                m: (
                    grid.N_RATE[m][f],
                    grid.PERMIT_RATE[m][f],
                    grid.SUPPRESS_RATE[m][f],
                )
                for m in grid.PANEL
            },
        }
    return out


# --------------------------------------------------------------------------- #
# parse the doc tables
# --------------------------------------------------------------------------- #
_ACC_ROW = re.compile(
    r"^\|\s*(F[1-6])[^|]*\|[^(]*\((\d)/4 in band\)[^|]*\|[^(]*\((\d)/4\)[^|]*\|",
    re.MULTILINE,
)
_PM_ROW = re.compile(
    r"^\|\s*(F[1-6])\s*\|\s*(gpt-5\.6-\w+|claude-sonnet-5)\s*\|\s*"
    r"([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|",
    re.MULTILINE,
)


def _parse_doc(path: Path) -> dict[str, dict]:
    # only the body table, not the correction block at the top -- the
    # correction block quotes "0/4" and "1/4" as prose and would confuse
    # the row regex, so start parsing at the real acceptance-rule heading.
    text = path.read_text()
    body = text[text.index("## Acceptance-rule table") :]
    out: dict[str, dict] = {}
    for framing, headroom, _nonsat in _ACC_ROW.findall(body):
        out.setdefault(framing, {})["headroom"] = int(headroom)
    for framing, model, n, permit, suppress in _PM_ROW.findall(body):
        out.setdefault(framing, {}).setdefault("per_model", {})[model] = (
            round(float(n), 3),
            round(float(permit), 3),
            round(float(suppress), 3),
        )
    return out


def _compare(label: str, doc: dict, auth: dict) -> None:
    for f, a in auth.items():
        d = doc.get(f)
        if not d:
            _fail(f"{label}: framing {f} not found in doc")
            continue
        if d.get("headroom") != a["headroom"]:
            _fail(
                f"{label} {f}: headroom in-band count doc={d.get('headroom')} "
                f"authoritative={a['headroom']}"
            )
        for m, vals in a["per_model"].items():
            dv = d.get("per_model", {}).get(m)
            if dv != vals:
                _fail(f"{label} {f} {m}: (N,permit,suppress) doc={dv} authoritative={vals}")


def main() -> int:
    r2 = _round_two_authoritative()
    r1 = _round_one_authoritative()
    if not _mism:
        _compare(
            "phase_8c_pilot_result.md",
            _parse_doc(ROOT / "docs" / "phase_8c_pilot_result.md"),
            r1,
        )
        _compare(
            "phase_8a2_pilot_result.md",
            _parse_doc(ROOT / "docs" / "phase_8a2_pilot_result.md"),
            r2,
        )
    if _mism:
        print("PILOT-DOC MISMATCHES:", file=sys.stderr)
        for m in _mism:
            print(f"  {m}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "verified",
                "round_one_source": "phase_8_frozen_grid (raw overwritten)",
                "round_two_source": "byte-pinned raw via phase_8c_pilot.evaluate_framing",
                "framings_checked": ["F1", "F2", "F3", "F4", "F5", "F6"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
