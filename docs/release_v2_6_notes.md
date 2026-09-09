# `paper-v2.6` — three-line wording patch of `paper-v2.5`

Two manuscript sentences reworded plus a verified non-issue. `paper-v2.6`
changes **no** experiment, raw trial, frozen analysis, numerical result,
pre-registered rule, or table value. Canonical raw data and every frozen
Phase 6/7/8/9 output are byte-identical to `paper-v2.0`–`paper-v2.5`. No
model/API calls.

## What changed

1. **Contribution (3) no longer overstated.** "near a bound, an effect in
   the saturated direction cannot be observed regardless of sample size"
   → "as a baseline approaches a bound, available headroom in that
   direction shrinks; once the bound is reached, additional movement
   toward it is structurally unobservable regardless of sample size." The
   following sentence scoping this to the fixed decision surface with no
   prevalence claim is unchanged. ("near a bound" is not "at the bound" —
   Phase 9 Terra/Claude are above the band but below saturation and show
   detectable effects.)
2. **Abstract necessity claim scoped.** "showing that lying inside the
   pre-specified panel band is not a necessary condition …" → "showing
   that, **in this setting**, lying inside the pre-specified panel band
   is not a necessary condition …". The numerical Phase 9 result is
   unchanged.
3. **Table 1 Panel B label — verified, no fix needed.** The Markdown,
   LaTeX, public PDF, and anonymous TMLR PDF all read "Panel B — round
   two, record set B (disjoint from A)" and "Panel B is round two on
   record set B". The string "round one two" appears in **no** submission
   artifact (it was a typo in a status report only).

## Archive

- file: `agent-interop-bench-paper-v2.6.tar.gz`
- built by `scripts/build_paper_v2_release.py` (`--check` re-derives the
  archive SHA-256).
- SHA-256, byte size, member count, and the release commit are in the
  **Verification** section of this release page.
