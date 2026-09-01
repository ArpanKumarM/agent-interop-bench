# Phase 7E.1 — conservative interpretation clarification (provenance record)

**Interpretive clarification only.** No provider call, no trial re-run, no
raw-data change, no change to any C/N/P rate, scenario contrast, mean,
median or sign count, no change to the pre-registered statistical
analysis, no manuscript edit. The original Phase 7E artifacts are
preserved byte-for-byte. The frozen Phase 7 analysis plan was **not**
modified retroactively.

The clarification package lives at `reports/phase_7e1_interpretation/`
(`reports/` is gitignored, matching the Phase 6D / 7D / 7E convention).
This document is the committed provenance record.

## What changed

Only prose and the floor/headroom **classification labels**. Every
numeric Phase 7E result is unchanged.

| item | value |
|---|---|
| Phase 7E analysis implementation commit | `dc5d0767ce4bec946373bf720a37aae538ef258c` |
| Phase 7E `MANIFEST.sha256` self-hash (unchanged) | `dbeb7068f1fe318862ba706a788fcc7a46107168f162e0021a04437958603b19` |
| Phase 7E.1 `MANIFEST.sha256` self-hash | `f63d30c525926ef0d4ae54ccdfbeb425143d7e2e420280881ced637876d4b6d2` |
| Frozen Phase 7 analysis-plan SHA-256 (not modified) | `87fec92f4b71a80e10a9f6fd5dd06fade13bec11d72d41725d34a660b1e7f68d` |

Phase 7E.1 package files:

| file | SHA-256 |
|---|---|
| `interpretation_clarification.json` | `e72d774856ee48b166a2e4ac64930ec515b362978486e9cde55d28a2860f4ae6` |
| `interpretation_clarification.md` | `c370f304e915151890f1124c6106e49e9513f774138d88a530a56357dc9304c1` |
| `MANIFEST.sha256` (self-hash) | `f63d30c525926ef0d4ae54ccdfbeb425143d7e2e420280881ced637876d4b6d2` |

## Issue

`docs/phase_7a_neutral_baseline_design.md` §6.3 uses the qualitative
phrase *"neutral baseline at or near zero"* and did **not** pre-register a
numeric threshold. The Phase 7E implementation
(`app/reporting/phase_7e_neutral.py::floor_headroom`) supplied
`pooled N <= 0.05` as an operational classifier. That threshold was not
pre-registered; applied literally it would place claude-sonnet-5
(pooled `N` = 5/40 = 0.125) in `neutral_provides_headroom` and permit
describing its `C − N` as consistent-with-suppression.

## Human conservative decision

claude-sonnet-5 `C` = 1/40 = 0.025, `N` = 5/40 = 0.125, `P` = 37/40 =
0.925 is treated as **LOW-BASELINE / FLOOR-BOUNDED** for interpretation of
`C − N`. The numeric `C − N` is unchanged: mean −0.100, median 0, signs
0 positive / 7 zero / 3 negative. It is **not** described as evidence for
confidentiality suppression.

Adopted wording:

> Claude's confidential arm was numerically below the unlabeled arm, but
> the unlabeled baseline itself was low (5/40) and seven of ten
> scenario-level `C − N` differences were zero. Under the study's
> conservative floor/headroom rule, this contrast is treated as
> floor-bounded and is not interpreted as evidence that the confidential
> header suppresses egress.

## Revised floor / headroom classification (all four models)

| model | pooled C / N / P | `C − N` | `P − N` |
|---|---|---|---|
| gpt-5.6-sol | 0.000 / 0.000 / 0.125 | floor-bounded | interpretable descriptive, floor-limited |
| gpt-5.6-terra | 0.000 / 0.000 / 0.000 | complete floor | complete floor / uninformative |
| gpt-5.6-luna | 0.000 / 0.000 / 0.250 | floor-bounded | interpretable descriptive, floor-limited |
| claude-sonnet-5 | 0.025 / 0.125 / 0.925 | low-baseline / floor-bounded — not suppression evidence | fully interpretable descriptive |

No model enters a confidentiality-suppression sentence.

## Final interpretation

- **`C − N`** — the Phase 7 neutral baseline does **not** provide
  convincing evidence for confidential-header suppression in any of the
  four models. Sol/Luna/Terra: floored, `C − N` identically 0. Claude:
  numerically negative but floor-bounded (baseline 5/40; 7/10 scenarios
  zero); not read as suppression.
- **`P − N`** — adding `PUBLIC - OK TO SHARE` is associated with increased
  verbatim egress relative to the unlabeled baseline: Claude very large
  and consistent (mean +0.800, 10/10 positive); Luna moderate/floor-limited
  (mean +0.250, 7/10); Sol smaller/floor-limited (mean +0.125, 4/10);
  Terra uninformative floor. Descriptive **public-sharing-label
  association**, not a causal permission mechanism.

Prohibited language: "public label causes disclosure", "permission
mechanism proved", "confidential label protects data", "confidentiality
suppresses disclosure". Preferred: "public-sharing-label association",
"higher egress under the added public/OK-TO-SHARE header relative to the
unlabeled baseline", "consistent with".

## Verification at Phase 7E.1

- Phase 7E `MANIFEST.sha256` self-hash `dbeb7068…12a3c` — **unchanged**.
- All 11 Phase 7E artifact SHA-256 — **unchanged** (re-hashed on disk;
  listed in `interpretation_clarification.json`).
- Four raw `trials.jsonl` SHA-256 — **unchanged**
  (`5227c8b1…`, `874e364f…`, `e1b6736b…`, `68e0fc5a…`).
- Phase 7D `MANIFEST.sha256` self-hash `dad290f5…1dd22` — **unchanged**.
- Phase 6 manifests
  `8310a1f9…a542695` (raw) and `db34e1ba…540593` (analysis) — **unchanged**.
- Provider calls in Phase 7E.1: **0**. Trials rerun: **0**. Raw data
  mutated: **no**.
- `uv run pytest -q`, `ruff check`, `ruff format --check`,
  `git diff --check`, `gitleaks git --log-opts=--all` — all clean
  (see the Phase 7E.1 commit message / return).

## Recommendation for Phase 7F manuscript revision

Lead with the `P − N` public-sharing-label association; state that the
neutral baseline shows no convincing confidential-suppression effect in
any model; present Claude's `C − N` explicitly as floor-bounded (keep the
numbers, drop the suppression characterization); note that the `N <= 0.05`
classifier was implementation-supplied and not pre-registered and that
Phase 7E.1 adopts the conservative reading; keep Phase 6 ↔ Phase 7
comparison descriptive; no pooling, no inferential statistics.
