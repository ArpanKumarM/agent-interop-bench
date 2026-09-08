# `paper-v2.0` release — preparation checklist and manifest (NOT YET CUT)

This document prepares the `paper-v2.0` public artifact release. **No GitHub
release or tag has been created.** The `audit_phase8_numbers.py` posting
gate stays red until the tag exists and its URL is substituted into
`paper/main_v2.md` / `main_v2.tex` §9.

## 1. What the release adds over `paper-v1.0`

`paper-v1.0` already contains: the frozen Phase 6 (`v4r1`) and Phase 7
(`v7a`) raw runs, integrity/pre-analysis manifests, and analysis artifacts
(`PROVENANCE.md` §2). `paper-v2.0` **supersedes and includes** all of that,
plus:

| addition | path(s) | purpose |
|---|---|---|
| **Phase 8 round-two pilot run** (four arms, full) | `reports/experiments/phase-8-pilot-{sol,terra,luna,claude}/` | the byte-pinned raw that `scripts/verify_phase_8_round2_from_raw.py` recomputes; the source of the §6.4 `public`-arm result |
| Phase 8 pilot design + result docs | `docs/phase_8_design.md`, `docs/phase_8a_parameters.md`, `docs/phase_8a2_pilot_design.md`, `docs/phase_8c_pilot_result.md`, `docs/phase_8a2_pilot_result.md` | already in-repo; included for a self-contained release |
| v2 manuscript | `paper/main_v2.md`, `paper/arxiv/main_v2.tex`, `paper/arxiv/references_v2.bib`, `paper/arxiv/main_v2.bbl`, and (optionally) a built `main_v2.pdf` | |
| v2 verification scripts | `scripts/verify_phase_8_round2_from_raw.py`, `scripts/verify_phase_8_pilot_docs.py`, `paper/arxiv/audit_phase8_numbers.py`, `app/reporting/phase_8_frozen_grid.py`, `app/reporting/phase_8c_pilot.py` | already in-repo |
| this manifest | `docs/release_v2_checklist.md` | |
| environment pin | `uv.lock` (SHA-256 `6b0d8279010a57be250d134ca291403061b4a8f7937fd2c93563ef9f6243fb56`), `pyproject.toml`, `python >=3.12,<3.13` | |

## 2. Manifest — Phase 8 round-two pilot artifacts (SHA-256)

The four `trials.jsonl` hashes also appear in
`docs/phase_8a2_pilot_result.md` and `scripts/verify_phase_8_round2_from_raw.py`
(`EXPECTED_SHA256`). The other four files per model are pinned here for the
first time.

| file | SHA-256 |
|---|---|
| `phase-8-pilot-gpt-5.6-sol/trials.jsonl` | `db9d3c5ca540c0e19730e9f4e80ed5f6cbd4cae57af933af8fd5d3aee5af6899` |
| `phase-8-pilot-gpt-5.6-sol/execution_fingerprint.json` | `aa14d855ba8f453120f9ba336dfb34dd2be8e4fd50fcec1a8bb34d6b62d50e93` |
| `phase-8-pilot-gpt-5.6-sol/plan.json` | `594b9e506062856bc4aca7006a05ec77d9dc173fce2eea48259c90dbb2e1778c` |
| `phase-8-pilot-gpt-5.6-sol/schedule.json` | `d9ca26cd47a4f5892272bb3d873069ae8932d09bd673149c0304db6814ca0700` |
| `phase-8-pilot-gpt-5.6-sol/summary.json` | `950754ccc9b0b73fb055ea06fbc4eb4404e51b9c7ef3ccbe369bb1c9b9750408` |
| `phase-8-pilot-gpt-5.6-terra/trials.jsonl` | `55144203978551a8abd694c7885dee1abc7f01566f82d4218376b05dbd5184f4` |
| `phase-8-pilot-gpt-5.6-terra/execution_fingerprint.json` | `bccfe2a95550237df277dab401f63c468f0ee9e875bbe3f92c179340d0d4ba69` |
| `phase-8-pilot-gpt-5.6-terra/plan.json` | `5dc5250b99942667a06ddbb516f16eb1eb0ec61755b2c430df53f965288f6d88` |
| `phase-8-pilot-gpt-5.6-terra/schedule.json` | `538e661b56772d203746b8b7e4503b6de9e84f76c99da841ed1741e51453eb1e` |
| `phase-8-pilot-gpt-5.6-terra/summary.json` | `f7ec2d5d4d0ec2817dbb3bcdde4ae77163196ebf6b0ad05d14915ae46b1c3cea` |
| `phase-8-pilot-gpt-5.6-luna/trials.jsonl` | `6a2512282b4dbcf5c412219034deca38acaf5bd50a0815bddc38568ff79940da` |
| `phase-8-pilot-gpt-5.6-luna/execution_fingerprint.json` | `3cd64238114d77575c819b52698e8d5fea16338949ac1641aa9e9c1d6de47d96` |
| `phase-8-pilot-gpt-5.6-luna/plan.json` | `2a6ff1d5a38064ecdf25686f7178ee55274b29136e8e60f1b956b1658e75eee4` |
| `phase-8-pilot-gpt-5.6-luna/schedule.json` | `fcdecf98130d928627fe5a2b3fa005a9b4e885b137989a1a039b542cf630bdd2` |
| `phase-8-pilot-gpt-5.6-luna/summary.json` | `a0c9ec9396d04a8368d0ecb1cd84619554b88e6ecdfdbab5fde43ca527e0a3b5` |
| `phase-8-pilot-claude-sonnet-5/trials.jsonl` | `8f916fa3cf3315e2fd89a1fec0fe74bd2e3c7ee7d3936d590db9fd15dff42c73` |
| `phase-8-pilot-claude-sonnet-5/execution_fingerprint.json` | `2bb87f6e8656db3f4a4bdaac53ef1ecf71ef381a78e98fc2b2c81fd2f6dfead5` |
| `phase-8-pilot-claude-sonnet-5/plan.json` | `181ae4ab6fca2348374947edd67536e8b0c12ae04b23042280ec9284cf3b2e51` |
| `phase-8-pilot-claude-sonnet-5/schedule.json` | `4836b306444888020f288d07870d7ffcce9e3f5300eb76420b2b1ea41ce29b43` |
| `phase-8-pilot-claude-sonnet-5/summary.json` | `dd4424ee65f1018ec0f3a14d98b315191d93bc6e2d4b4c37eafacf2d38be7906` |

Round-two pilot artifacts total: **4,566,404 bytes** across 20 files.
Full `reports/` tree (Phase 6 + 7 + 8): **~31 MB**.

## 3. Missing historical material (state in the release notes)

- **Phase 8 round-one (F1–F3) raw traces are permanently unavailable.** They
  were overwritten by the round-two run into the same directories before the
  `public` arm was identified as worth analyzing. The originally-recorded
  round-one `trials.jsonl` SHA-256 hashes are preserved in
  `docs/phase_8c_pilot_result.md` (§ raw hashes table:
  `8056732c…bdb498`, `b9e2956d…53100e5`, `8093abce…f979c460`,
  `64b432ce…dba21eba`) but there are **no bytes to check them against**.
- Round-one `unlabeled`/`permit`/`suppress` rates survive only as a
  transcription in `app/reporting/phase_8_frozen_grid.py`. Round-one
  `public`-arm values **cannot be recovered**.
- The release notes must not imply round one is byte-verifiable. It is not.

## 3a. Trees that must NOT be in the release (security)

`reports/` on disk contains non-published trees that must be **excluded**
from the tarball — the §5 command enumerates published subtrees only, it
does **not** ship `reports/` wholesale:

| tree | why excluded |
|---|---|
| `reports/_aborted_phase6d/` (1.8 MB) | aborted / superseded Phase 6 runs — "preserved on disk, permanently excluded, never merged" (`PROVENANCE.md` §1). One file, `phase-6b-confirmatory-v4-sol.ABORTED-openai-401-*/trials.jsonl`, contains 17 OpenAI `AuthenticationError` records whose message echoes `Incorrect API key provided: sk-proj-` **followed by a fully asterisk-masked key body (0 unmasked characters beyond the public `sk-proj-` prefix)** plus OpenAI `request_id`s. No usable credential, but no reason to ship it. |
| `reports/_aborted_*` (any) | same class |
| `reports/experiments/composed-live-canary-*` | pre-study smoke/canary runs, not a published number |
| `reports/smoke/`, `reports/canaries/` | smoke tests |
| `reports/_phase7c_execution_integrity/`, `reports/phase_7e1_interpretation/` | intermediate integrity/interpretation working dirs; the frozen artifacts they summarise are shipped separately |

Published trees that **are** in the release: `reports/experiments/phase-6b-confirmatory-v4r1-*`, `reports/experiments/phase-7a-confirmatory-v1-*`, `reports/experiments/phase-8-pilot-*`, `reports/phase_6e_v4r1/`, `reports/phase_7e_analysis/`, `reports/_phase6d_v4r1_integrity/`, `reports/_phase7d_preanalysis_freeze/`.

## 4. Pre-release checklist

- [ ] `uv run pytest -q` green (990 / 951+5-skip).
- [ ] `uv run ruff check .` and `uv run ruff format --check .` clean.
- [ ] `uv run python scripts/verify_phase_8_round2_from_raw.py` → 0 mismatches.
- [ ] `uv run python scripts/verify_phase_8_pilot_docs.py` → verified.
- [ ] `uv run python paper/arxiv/audit_numbers.py` (v1) → passes.
- [ ] `uv run python paper/arxiv/audit_phase8_numbers.py` (v2) → **no
      `AUDIT FAILURE(S)`**; only posting gates open.
- [ ] `bash paper/arxiv/build_pdf_v2.sh` → 15 pages, no overfull/undefined.
- [ ] `git diff` contains **no** change under `reports/`, no change to a
      **frozen** preregistration (`docs/phase_8_design.md`,
      `docs/phase_8a2_pilot_design.md`,
      `docs/phase_7a_neutral_baseline_design.md`), no change to a recorded
      hash. (The 2026-09-07/08 pass *did* strike superseded interpretive
      wording in the non-frozen `docs/phase_8a_parameters.md` "Round 2
      update" addendum and in the two pilot *result* docs — visible
      strikethrough + dated supersession notes, no number rewritten.)
- [ ] Round-one-unavailability wording present in README §"Where it lands",
      `REPRODUCIBILITY.md` §7, and this file §3.
- [ ] Decide whether the built `main_v2.pdf` ships in the release (it is
      deterministic; shipping it removes a TeX-Live dependency for
      reviewers).
- [ ] Set the real submission date in `paper/arxiv/main_v2.tex` `\date{}`
      and remove the TODO comment (clears one posting gate).

## 5. Exact commands to run when authorized to publish

**Not run yet. Requires explicit authorization.**

```bash
# from a clean working tree at the release commit:
git tag -a paper-v2.0 -m "v2 (arXiv:2609.01693 v2): pre-registered framing sweep + Phase 8 pilot traces"
git push origin paper-v2.0

# enumerate ONLY published report subtrees (NOT reports/ wholesale -- see §3a):
tar --sort=name --mtime='2016-01-01 00:00:00Z' --owner=0 --group=0 --numeric-owner \
    -czf agent-interop-bench-paper-v2.0.tar.gz \
    reports/experiments/phase-6b-confirmatory-v4r1-sol \
    reports/experiments/phase-6b-confirmatory-v4r1-terra \
    reports/experiments/phase-6b-confirmatory-v4r1-luna \
    reports/experiments/phase-6b-confirmatory-v4r1-claude \
    reports/experiments/phase-7a-confirmatory-v1-sol \
    reports/experiments/phase-7a-confirmatory-v1-terra \
    reports/experiments/phase-7a-confirmatory-v1-luna \
    reports/experiments/phase-7a-confirmatory-v1-claude \
    reports/experiments/phase-8-pilot-gpt-5.6-sol \
    reports/experiments/phase-8-pilot-gpt-5.6-terra \
    reports/experiments/phase-8-pilot-gpt-5.6-luna \
    reports/experiments/phase-8-pilot-claude-sonnet-5 \
    reports/phase_6e_v4r1 reports/phase_7e_analysis \
    reports/_phase6d_v4r1_integrity reports/_phase7d_preanalysis_freeze \
    docs/ paper/main_v2.md paper/arxiv/main_v2.tex paper/arxiv/references_v2.bib \
    paper/arxiv/main_v2.bbl paper/arxiv/audit_phase8_numbers.py \
    scripts/verify_phase_8_round2_from_raw.py scripts/verify_phase_8_pilot_docs.py \
    app/reporting/phase_8_frozen_grid.py app/reporting/phase_8c_pilot.py \
    uv.lock pyproject.toml PROVENANCE.md REPRODUCIBILITY.md CITATION.cff

# final secret scan on the staged tarball before publishing:
tar -xzOf agent-interop-bench-paper-v2.0.tar.gz | grep -aE 'sk-[A-Za-z0-9]{16}|sk-ant-|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|/Users/|/home/[a-z]' && echo "SECRET/PATH FOUND -- do not publish" || echo "scan clean"

shasum -a 256 agent-interop-bench-paper-v2.0.tar.gz   # record in the release notes

gh release create paper-v2.0 agent-interop-bench-paper-v2.0.tar.gz \
   --title "paper-v2.0" --notes-file docs/release_v2_notes.md   # notes to be written

# then substitute the release URL into paper/main_v2.md and paper/arxiv/main_v2.tex §9,
# rebuild the PDF, and re-run audit_phase8_numbers.py (posting gates should clear).
```
