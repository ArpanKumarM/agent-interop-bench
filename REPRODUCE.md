# REPRODUCE.md — `paper-v2.0` public reproducibility guide

Every reported number in the v2 manuscript
(`paper/main_v2.md` / `paper/arxiv/main_v2.tex`) can be reproduced from
this archive **with zero API credentials and zero paid model inference**.

This guide is the release-level quick path. `REPRODUCIBILITY.md` in the
same tree carries the longer per-phase walkthrough and the explicit list
of what *cannot* be reproduced (the Phase 8 round-one raw traces were
overwritten — §7 there).

Two things are kept strictly separate everywhere below:

| | credentials | cost |
|---|---|---|
| **reproduce analysis from frozen raw data** (the normal path) | **none** | **none** |
| perform a new live model run | OpenAI + Anthropic keys in `.env` | real spend |

Nothing in sections A–J makes a network call to a model provider.

---

## A. Environment

```bash
# extract this archive so that reports/ sits next to app/, paper/, docs/ ...
tar -xzf agent-interop-bench-paper-v2.0.tar.gz
cd agent-interop-bench-paper-v2.0

uv sync --frozen        # installs exactly uv.lock; offline path only
```

- Python `>=3.12,<3.13`; dependency manager [`uv`](https://docs.astral.sh/uv/).
- `uv.lock` SHA-256 is pinned in `PROVENANCE.md` §2 (Shared).
- The `openai` / `anthropic` extras are **optional** and only needed to
  *run* live experiments. Without them: `uv run pytest -q` →
  `1071 passed, 3 skipped`. With
  `uv sync --frozen --extra openai --extra anthropic` a few dozen extra
  offline SDK-contract tests also collect.
- PDF build (section J) additionally needs a TeX Live with `pdflatex` +
  `bibtex` + `natbib` / `booktabs` / `microtype`.

---

## B. Phase 6 / Phase 7 verification (no API calls)

```bash
# raw Phase 7 hashes match PROVENANCE.md §2
for r in sol terra luna claude; do
  shasum -a 256 reports/_phase7d_preanalysis_freeze/raw_runs/phase-7a-confirmatory-v1-$r/trials.jsonl
done

# re-run the frozen Phase 7 analysis; reproduces reports/phase_7e_analysis/ byte-for-byte
uv run python -m app.cli.phase_7e_neutral

# regenerate + audit every v1 manuscript number against the frozen artifacts
uv run python paper/arxiv/gen_tables.py
uv run python paper/arxiv/audit_numbers.py
```

**Success:** hashes match `PROVENANCE.md` §2; `audit_numbers.py` prints
`numeric audit passed: manuscript reconciles with the frozen Phase 7E and
Phase 6E.2 artifacts`.

---

## C. Phase 8 verification (no API calls)

```bash
# recompute all four pilot arms from the byte-pinned round-two raw
uv run python scripts/verify_phase_8_round2_from_raw.py     # -> mismatches: 0

# pilot result docs match the authoritative analysis
uv run python scripts/verify_phase_8_pilot_docs.py          # -> "status": "verified"
```

Phase 8 round one (F1–F3) raw traces are **permanently unavailable**
(overwritten by the round-two run). The originally-recorded round-one
SHA-256s survive in `docs/phase_8c_pilot_result.md` but there are no
bytes to check them against. This is disclosed in the paper (§6.4, §8,
§9) and `REPRODUCIBILITY.md` §7.

---

## D. Phase 9 scientific-freeze verification (no API calls)

```bash
uv run python scripts/verify_phase_9_freeze.py       # recomputes 21 pinned hashes
uv run python scripts/phase_9_build_freeze.py --check # 4 freeze artifacts reproduce byte-for-byte
```

**Success:** `verify_phase_9_freeze.py` prints
`study_schedule_sha256 7f05b86c…c07f1ad`,
`scenario_fixture_sha256 da4d525c…609c4583`,
`components verified 21`,
`total planned trials 1536 (64 scenarios x 3 repeats x 2 arms x 4 models)`,
exit 0. `phase_9_build_freeze.py --check` prints
`ALL FREEZE ARTIFACTS REPRODUCE BYTE-FOR-BYTE: True`.

Scientific-design freeze commit: `32a76bfa19c3240bd87011fe9a7e41b3ced1a511`.

---

## E. Execution-addendum verification (no API calls)

```bash
uv run python scripts/phase_9_execution_addendum.py --check   # -> ADDENDUM MANIFEST VERIFIED
uv run python scripts/verify_phase_9_execution_ready.py       # offline readiness, 0 network
uv run python scripts/phase_9_runner_dryrun.py                # PLANNED=1536, EXECUTED=0, 0 API calls
```

The execution implementation was added as a disclosed
**post-freeze addendum** (commit
`a347a8b3c2b29b77586a113fdabf8bd310e92e85`); it consumes the frozen
schedule, scenarios, arms, panel, and analysis config verbatim
(`PROVENANCE.md` §7).

---

## F. Raw-data-freeze verification (no API calls)

```bash
uv run python scripts/phase_9_raw_data_freeze.py --check      # -> RAW-DATA FREEZE VERIFIED
shasum -a 256 reports/_phase9_raw_data_freeze_attempt_002/MANIFEST.sha256
```

**Frozen raw `trials.jsonl` SHA-256 (attempt 002):**

| model | `trials.jsonl` SHA-256 |
|---|---|
| `gpt-5.6-sol`     | `7d5cd35ba3102fc3bfc2501d74bb9ec758cd220395f44e79980a20370ffe02fc` |
| `gpt-5.6-terra`   | `fc658ac3ccf3f79054ee3c38e54543932dce0c076fa9012fd4e0539c7e54d1e6` |
| `gpt-5.6-luna`    | `0d45e5bd1b3419bf52481e3c2d968cc92a2f0b1b432f5129937f34fdfc3e1ce0` |
| `claude-sonnet-5` | `f09c30cbc0c1e7688e672341bec70767deb0e6885999d85e12074b7b57e06313` |

The four `reports/experiments/phase-9-f3-*/trials.jsonl` on disk must hash
to exactly these values; `reports/_phase9_raw_data_freeze_attempt_002/`
holds a byte-identical archived copy plus its own `MANIFEST.sha256`
(self-hash `6e86a4cf00ab99636de84d86428fae3d7b708ff2498ec62fe19e43f7852e760f`).
Raw-data freeze commit: `c64a32d73e9d4b52fb03d4b6a91c8d3fa05f3bfe`.

**Aborted attempt 001 is operational provenance, not scientific data.**
`reports/_phase9_aborted_billing_attempt_001/` records **9** rejected
`insufficient_quota` quota requests (all `gpt-5.6-sol`), **0** successful
model responses, **0** generated tokens, **0** scientific observations.
It was excluded before any analysis under the frozen §12 completion rule.
Do **not** count these files as Phase 9 data.

---

## G. Phase 9 analysis command (no API calls)

```bash
uv run python scripts/phase_9_analyze.py
```

Reads the frozen raw bytes, calls the **hash-pinned** analysis
implementation (`scripts/phase_9_design_simulation.py`, SHA-256
`5c8301018886234c7721600f1678c0e218a76a02073e3b4b9fe47138faa2049f`) and
the frozen decision rules
(`docs/phase_9_design/phase_9_analysis_config.json`). Deterministic:
re-running leaves `docs/phase_9_design/phase_9_results_attempt_002.{json,md}`
byte-identical. Frozen-analysis commit: `89c0542`.

---

## H. Expected result hashes / values

Re-running section G leaves
`docs/phase_9_design/phase_9_results_attempt_002.{json,md}`
**byte-identical** to the copies shipped in this archive (the analysis is
deterministic; `git status` is clean afterward). `PROVENANCE.md` §8.5
additionally records the `CONFIRMATORY_primary` sub-block hash
(`92c2166b…`).

| model | Q1 θ̂ | Q1 95% CI | Q1 class | Q2 Δ̂ | Q2 95% CI | Q2 detected | Holm-adj p |
|---|---|---|---|---|---|---|---|
| `gpt-5.6-sol`     | 1.000 | [1.000, 1.000]† | ABOVE | +0.000 | [+0.000, +0.000] | no | 1.0 |
| `gpt-5.6-terra`   | 0.823 | [0.759, 0.887]  | ABOVE | +0.167 | [+0.105, +0.228] | yes | 6e-6 |
| `gpt-5.6-luna`    | 1.000 | [1.000, 1.000]† | ABOVE | −0.010 | [−0.026, +0.005] | no | 0.36 |
| `claude-sonnet-5` | 0.844 | [0.762, 0.926]  | ABOVE | +0.104 | [+0.011, +0.198] | yes | 0.09 |

**Panel Q1 verdict: FAILS (4/4 ABOVE).** Raw unlabeled-arm egress:
sol 192/192, terra 158/192, luna 192/192, claude 162/192. Raw public-arm
egress: sol 192/192, terra 190/192, luna 190/192, claude 182/192.
† degenerate zero-width interval at saturation; the non-degenerate
trial-level Wilson interval on the pooled 192 unlabeled trials is
[0.980, 1.000], also entirely above 0.70.

---

## I. Paper numeric audits (no API calls)

```bash
uv run python paper/arxiv/audit_numbers.py           # v1 tables vs frozen Phase 6E.2 / 7E
uv run python paper/arxiv/audit_phase8_numbers.py     # v2 Phase 6/7/8 numbers + md<->tex mirror
uv run python paper/arxiv/audit_phase9_numbers.py     # v2 Phase 9 numbers vs the frozen analysis output
```

**Success:** `audit_numbers.py` and `audit_phase9_numbers.py` print an
all-pass line. `audit_phase8_numbers.py` prints
`All Phase 8 numeric checks passed; posting gates clear` **in this
release** (the `paper-v2.0` tag URL and the submission date are now set);
there is never an `AUDIT FAILURE(S)` block.

---

## J. PDF build (LaTeX only, no API calls)

```bash
bash paper/arxiv/build_pdf_v2.sh
```

Deterministic (`SOURCE_DATE_EPOCH` fixed). **Success:**
`main_v2.pdf: 19 pages … no overfull/undefined warnings`; the SHA-256 is
stable across rebuilds on the same TeX Live.

---

## One-shot offline sequence

```bash
uv sync --frozen
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
uv run python paper/arxiv/audit_numbers.py
uv run python scripts/verify_phase_8_round2_from_raw.py
uv run python scripts/verify_phase_8_pilot_docs.py
uv run python paper/arxiv/audit_phase8_numbers.py
uv run python scripts/verify_phase_9_freeze.py
uv run python scripts/phase_9_build_freeze.py --check
uv run python scripts/phase_9_execution_addendum.py --check
uv run python scripts/phase_9_raw_data_freeze.py --check
uv run python scripts/phase_9_analyze.py
uv run python paper/arxiv/audit_phase9_numbers.py
bash paper/arxiv/build_pdf_v2.sh
```
