# Reproducibility guide (for reviewers)

Every non-live claim in the v2 paper can be verified from this repository
plus the public artifact release, with **no API calls and no paid model
inference**. This document lists the exact commands, expected outputs, and
success conditions, and states plainly what **cannot** be reproduced.

---

## 0. Environment

| item | value |
|---|---|
| branch | `phase-6b-impl` |
| commit (this guide written against) | `0d680ec` (`git rev-parse HEAD` for the exact SHA once these changes are committed) |
| Python | `>=3.12,<3.13` (developed on 3.12.2) |
| dependency manager | [`uv`](https://docs.astral.sh/uv/); resolved lock is `uv.lock`, SHA-256 `6b0d8279010a57be250d134ca291403061b4a8f7937fd2c93563ef9f6243fb56` (also pinned in `PROVENANCE.md`) |
| LaTeX (PDF build only) | any TeX Live with `pdflatex` + `bibtex` + `natbib`/`booktabs` |

```bash
git clone https://github.com/ArpanKumarM/agent-interop-bench
cd agent-interop-bench
git checkout phase-6b-impl
uv sync --frozen
```

`uv sync --frozen` installs exactly the locked versions and runs the default
(offline) path. The `openai` / `anthropic` extras are **optional** and only
needed to *run* live experiments — they are **not** required for any
verification below. Installing them additionally lets ~35 offline
SDK-contract integration tests collect (`uv sync --frozen --extra openai
--extra anthropic`). The suite is **1071 passed, 3 skipped** (the skips
are "no prior attempt artifacts on this machine").

---

## 1. Unit + integration tests (no API calls)

```bash
uv run pytest -q
```

**Success:** `1071 passed, 3 skipped`.

```bash
uv run ruff check .          # lint  -> "All checks passed!"
uv run ruff format --check . # format -> no diff
```

---

## 2. Phase 6 / Phase 7 frozen tables (no API calls)

Requires the **public artifact release** extracted so that `reports/` sits at
the repository root (the `paper-v1.0` release carries the Phase 6/7
artifacts).

```bash
# raw Phase 7 hashes match PROVENANCE.md
for r in sol terra luna claude; do
  shasum -a 256 reports/_phase7d_preanalysis_freeze/raw_runs/phase-7a-confirmatory-v1-$r/trials.jsonl
done

# re-run the frozen Phase 7 analysis; must reproduce reports/phase_7e_analysis/ byte-for-byte
uv run python -m app.cli.phase_7e_neutral

# regenerate + audit every v1 manuscript number against the frozen artifacts
uv run python paper/arxiv/gen_tables.py
uv run python paper/arxiv/audit_numbers.py
```

**Success:** hashes match `PROVENANCE.md` §2; `audit_numbers.py` prints
`numeric audit passed: manuscript reconciles with the frozen Phase 7E and
Phase 6E.2 artifacts`.

The v2 paper reproduces the same Phase 6/7 tables (restored in
`paper/main_v2.md` §5.2 and Appendix C); `paper/arxiv/audit_phase8_numbers.py`
(check 8) compares them **row-for-row** against v1.

---

## 3. Phase 8 round two — recompute all four arms from byte-pinned raw (no API calls)

Requires the round-two raw traces
(`reports/experiments/phase-8-pilot-<model>/trials.jsonl`; in the
`paper-v2.0` release once cut — see `docs/release_v2_checklist.md`).

```bash
uv run python scripts/verify_phase_8_round2_from_raw.py
```

**Success:**
```json
{ "status": "verified", "total_trials": 576, "total_completed": 575,
  "cells_checked": 48, "mismatches": 0 }
```
This verifies each file's SHA-256 against the pins in
`docs/phase_8a2_pilot_result.md`, then recomputes `unlabeled` / `permit` /
`suppress` / `public` rates for every (model × F4/F5/F6) cell and asserts
byte-exact agreement with `app/reporting/phase_8_frozen_grid.py`.

---

## 4. Phase 8 pilot **result documents** match the authoritative analysis

```bash
uv run python scripts/verify_phase_8_pilot_docs.py
```

**Success:** `"status": "verified"`. Round one
(`docs/phase_8c_pilot_result.md`) is checked against
`app.reporting.phase_8_frozen_grid`; round two
(`docs/phase_8a2_pilot_result.md`) is recomputed from the byte-pinned raw.
This guards the 2026-09-07 correction of three mis-transcribed in-band
counts (F2/F3 round one, F4 round two: written `0/4`, actually `1/4`; the
`≥3/4` accept/reject outcome is unchanged — see the correction block at the
top of each doc).

---

## 5. v2 manuscript numeric audit (no API calls)

```bash
uv run python paper/arxiv/audit_phase8_numbers.py
```

**16 checks.** Verifies: the frozen grid's derived quantities; the round-two
raw recomputation (§3 above, as a subprocess); the pilot result docs (§4);
`paper/main_v2.md` Table 1 and the acceptance table; every trial count and
cost; the ~13,200 main-study total by **live schedule recomputation**
(= 13,184); every Phase 6/7 number against the frozen analysis artifacts and
against v1's text; the restored v1 tables row-for-row; the §6.1 calibration
separations; the §6.4 `P − N` values and the mandatory post-hoc disclosure;
the §5.3 Wilson-interval / F3 caveat; every Appendix B hash; every cited
arXiv id against a hand-verified set (`VERIFIED_ARXIV_IDS`); the `.tex`
mirror of all of the above; `references_v2.bib` + `\cite` resolution; two
non-fatal qualifier lints.

In the `paper-v2.0` release the `\date{}` and the tag URL are set, so this
prints `All Phase 8 numeric checks passed; posting gates clear`. **No
numeric-integrity check fails** (there is no `AUDIT FAILURE(S)` block) at
any point.

---

## 5a. Phase 9 F3 resolution study (no API calls)

The Phase 9 offline path — scientific-freeze / execution-addendum /
raw-data-freeze verification, the deterministic frozen analysis, its
expected result hashes, and `paper/arxiv/audit_phase9_numbers.py` — is
written out step by step in **`REPRODUCE.md` §D–I**. Summary: all four
verifiers exit 0, `scripts/phase_9_analyze.py` reproduces
`docs/phase_9_design/phase_9_results_attempt_002.{json,md}` byte-for-byte,
and the panel Q1 verdict is `FAILS` (4/4 ABOVE). The aborted attempt-001
archive (`reports/_phase9_aborted_billing_attempt_001/`) is operational
provenance only: 9 rejected quota requests, 0 successful responses, 0
tokens, 0 scientific observations.

---

## 6. Rebuild the v2 PDF (LaTeX only, no API calls)

```bash
bash paper/arxiv/build_pdf_v2.sh
```

Deterministic (`SOURCE_DATE_EPOCH` fixed). **Success:** `main_v2.pdf: 19
pages … no overfull/undefined warnings`, and the SHA-256 is stable across
rebuilds on the same TeX Live.

---

## 7. What **cannot** be reproduced

**Phase 8 round one (F1–F3) raw traces were overwritten** by the round-two
run before the `public` arm was identified as worth analyzing. Consequences:

- The originally-recorded round-one raw SHA-256 hashes **survive** in
  `docs/phase_8c_pilot_result.md` and are the pin, but there are **no bytes
  left to check them against** on any machine.
- Round-one `unlabeled` / `permit` / `suppress` rates are preserved as a
  **transcription** in `app/reporting/phase_8_frozen_grid.py` (from the
  frozen result doc's own table) and are cross-checked for internal
  consistency, but they **cannot be newly recomputed from raw**.
- The round-one **`public` arm cannot be recovered at all** — hence the
  within-study `P − N` label contrast in `paper/main_v2.md` §6.4 exists only
  for F4–F6, and for one model.

This is disclosed in the paper (§6.4, §8, §9), the README, and the frozen
result doc. A corrective lesson (`archive raw copies before rerunning`) is
recorded in `app/reporting/phase_8_frozen_grid.py`'s docstring.

---

## 8. Commands that would require **live, paid API calls** — do NOT run to verify

These are listed for completeness. **None is needed to check any published
number.** They require `uv sync --frozen --extra openai --extra anthropic`,
API keys in `.env`, and real spend.

| command | what it would do | cost |
|---|---|---|
| `uv run python -m app.cli.composed_live_pilot ...` | run a Phase 8 pilot round against live models | ~$3 per round (measured) |
| any `app.cli.*` entry point that constructs a real provider adapter | live model inference | varies |
| the (never-run) Phase 8 main study S8-A…D | 13,184 live trials | ~$45–65 (projected; never at risk) |
| the held-out L4 judge (`app/reporting/llm_judge_crosscheck.py`) | one live `claude-haiku` call per trial | quarantined; not run |
| a **new** Phase 9 live run (`app/cli/phase_9_execute.py … run`) | re-collect the F3 resolution study from scratch | ~$25–30 (measured; **not needed** — the frozen raw is in the release and the analysis in §D–G of `REPRODUCE.md` is fully offline) |

---

## Quick "all green" sequence (offline)

```bash
uv sync --frozen
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
uv run python scripts/verify_phase_8_round2_from_raw.py
uv run python scripts/verify_phase_8_pilot_docs.py
uv run python paper/arxiv/audit_numbers.py            # v1
uv run python paper/arxiv/audit_phase8_numbers.py     # v2
uv run python scripts/verify_phase_9_freeze.py
uv run python scripts/phase_9_build_freeze.py --check
uv run python scripts/phase_9_execution_addendum.py --check
uv run python scripts/phase_9_raw_data_freeze.py --check
uv run python scripts/phase_9_analyze.py
uv run python paper/arxiv/audit_phase9_numbers.py
```
