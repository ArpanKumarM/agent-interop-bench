# `paper-v2.1` — claim-scope revision of `paper-v2.0`

Same study, same numbers. `paper-v2.1` revises the **manuscript claims and
scope** of `paper-v2.0`; it does **not** change any raw trial, any frozen
analysis, any numerical result, any pre-registered rule, or any Phase
6/7/8/9 scientific artifact. The canonical raw data and every frozen
scientific output in this release are byte-identical to `paper-v2.0`.

## What changed (manuscript / audits only)

- **Title** → *"Measuring Sensitivity-Label Effects at an MCP-to-A2A
  Handoff: Baseline Saturation and Directional Headroom."*
- **Phase 8 is presented as a two-round pilot search, not a matched
  six-condition experiment.** The two rounds used **disjoint** four-record
  pilot sets (round one: `healthcare-billing`, `logistics-shipment`,
  `insurance-claims`, `ad-platform-advertiser`; round two: four
  purpose-built `pilotonly-*` records) and ran at different times.
  Within-round formulation contrasts are matched; the
  round-one-to-round-two ceiling-vs-floor difference confounds task
  formulation, record set, and execution window and is **not** attributed
  to task formulation.
- **Central claim** reframed around baseline saturation as a measurement
  constraint on directional headroom, with no causal task-wording claim.
- **F3** is described as having *failed the pre-registered Phase 8
  point-estimate gate* while remaining *interval-wise unresolved at
  n = 12*; Phase 9 resolves it under its own interval-containment rule.
- New **L0 construct-validity** paragraph: `L0 = 1` is verbatim
  sensitive-field propagation, not a privacy-violation classifier.
- New **Future Work** sentence naming the controlled
  meaning-preserving-wording study that would be needed to isolate a pure
  wording effect.
- `paper/arxiv/audit_phase9_numbers.py` extended with build-time traps for
  the above (causal / cross-round / shared-scenario-set / `L0 =
  privacy-violation` wording) and required-disclosure checks.

Full rationale: `PROVENANCE.md`; the frozen Phase 8 design docs
`docs/phase_8a_parameters.md` §6 and `docs/phase_8a2_pilot_design.md` §4
record the round-one and round-two pilot record sets.

## Archive

- file: `agent-interop-bench-paper-v2.1.tar.gz`
- built by: `scripts/build_paper_v2_release.py`
  (`uv run python scripts/build_paper_v2_release.py --check` re-derives
  the archive SHA-256).
- The archive SHA-256, byte size, member count, and the exact release
  commit are in the **Verification** section of this release page.

`REPRODUCE.md` in the archive is the offline reproduction guide (sections
A–J); the Phase 9 raw hashes and analysis output are unchanged from
`paper-v2.0`.
