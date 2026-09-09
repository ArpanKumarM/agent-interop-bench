# `paper-v2.3` — wording-consistency patch of `paper-v2.2`

One wording fix only. `paper-v2.3` does **not** change any experiment,
raw trial, frozen analysis, numerical result, or pre-registered rule. The
canonical raw data and every frozen scientific output in this release are
byte-identical to `paper-v2.0`, `paper-v2.1`, and `paper-v2.2`.

## What changed

**Phase 6/7 cross-phase reproducibility-check caption.** In the
"Cross-phase reproducibility check" paragraph of Section 5.3, the
sentence

> "Different times, different provider snapshots, not pooled, no
> statistical test."

is replaced by

> "Different execution windows; provider snapshot identity was not
> pinned. The runs are not pooled and no cross-phase statistical test is
> performed."

Provider snapshot identifiers were never pinned, so literal snapshot
difference between the Phase 6 and Phase 7 runs cannot be asserted. The
Phase 6/7 numbers, the descriptive C − P comparison, and its
interpretation are unchanged. This mirrors the Phase 8 two-round wording
already corrected in `paper-v2.2`.

`paper/arxiv/audit_phase9_numbers.py` now fails the build if either
`different provider snapshots` or `different runs at different provider
snapshots` appears in `main_v2.md` / `main_v2.tex`.

## Anonymous TMLR review derivative (not part of this public release)

The anonymous supplementary builder
(`paper/tmlr/build_supplementary_zip.py`) additionally reword-sanitizes
three **legacy** occurrences of the same phrasing that live in
provenance-tracked Phase 7E history —
`reports/phase_7e_analysis/analysis_report.md`,
`app/reporting/phase_7e_neutral.py`, `app/cli/phase_7e_neutral.py` — in
the anonymous review copy only. Those canonical repository files are
**unchanged**; the transformation is documentation / report / docstring
string text only and does not affect any output, score, numerical
constant, model id, scenario record, raw trace, experiment
configuration, or analytical behaviour. `ANON_README.md` in the package
now records this.

## Archive

- file: `agent-interop-bench-paper-v2.3.tar.gz`
- built by `scripts/build_paper_v2_release.py`
  (`--check` re-derives the archive SHA-256).
- SHA-256, byte size, member count, and the exact release commit are in
  the **Verification** section of this release page.

`REPRODUCE.md`, the Phase 9 raw hashes, and the frozen analysis output
are unchanged from `paper-v2.0`.
