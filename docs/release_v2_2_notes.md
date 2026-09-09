# `paper-v2.2` — wording-consistency patch of `paper-v2.1`

Three wording fixes only. `paper-v2.2` does **not** change any experiment,
raw trial, frozen analysis, numerical result, or pre-registered rule. The
canonical raw data and every frozen scientific output in this release are
byte-identical to `paper-v2.0` and `paper-v2.1`.

## What changed

1. **Anonymous-supplementary consistency (report only).** The anonymous
   TMLR supplementary ZIP does **not** retain any canonical repository
   commit SHA — `execution_fingerprint.source_commit_sha` in the anon
   `reports/**/trials.jsonl` derivative copies is
   `[redacted-for-double-blind]`, verified by extraction. The stale
   statement in an earlier packaging report that the anon traces are
   "byte-exact and retain `source_commit_sha`" was incorrect and is
   withdrawn; `ANON_README.md` (correct) already describes the traces as
   double-blind derivative copies.
2. **Phase 8 provider wording.** "executed at different times against
   different provider snapshots" → "executed in different windows against
   provider endpoints whose underlying snapshot identity was not pinned"
   (Section 5.3 and Limitations (iii-a)). Snapshot IDs were not pinned, so
   literal snapshot difference is not asserted. The existing limitation
   ("Without provider snapshot pinning, sampling variability,
   scenario-distribution differences, and possible provider-endpoint
   drift cannot be separated") is unchanged; no behavioural/provider
   drift is claimed.
3. **Sample-size / headroom wording.** "increasing the per-model sample
   more than tenfold (Phase 9) did not create headroom" / "Adding samples
   does not create headroom … Phase 9 increased the per-model sample more
   than tenfold" → "Additional samples can improve resolution around a
   baseline but cannot, by themselves, create directional headroom if the
   underlying operating regime is saturated" plus, for the empirical
   Phase 9 description, "the larger Phase 9 follow-up resolved F3 to a
   high-egress regime rather than revealing an intermediate one." The
   Phase 8 -> Phase 9 difference is no longer described as attributable to
   sample size alone.

## Archive

- file: `agent-interop-bench-paper-v2.2.tar.gz`
- built by `scripts/build_paper_v2_release.py`
  (`--check` re-derives the archive SHA-256).
- SHA-256, byte size, member count, and the exact release commit are in
  the **Verification** section of this release page.

`REPRODUCE.md`, the Phase 9 raw hashes, and the frozen analysis output are
unchanged from `paper-v2.0`.
