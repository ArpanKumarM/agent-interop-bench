# `paper-v2.5` — evidence-alignment revision of `paper-v2.4`

Manuscript wording, one table's presentation, one front-matter note, and
three new tests. `paper-v2.5` does **not** change any experiment, raw
trial, frozen analysis, numerical result, or pre-registered rule. The
canonical raw data and every frozen Phase 6/7/8/9 scientific output are
byte-identical to `paper-v2.0`–`paper-v2.4`. No model/API calls were
made.

## What changed (manuscript)

Motivated by a valid reviewer observation: Phase 9 classified all four
models `ABOVE` the `[0.25, 0.70]` Q1 headroom band, yet positive `P − N`
effects were still detected for Terra and Claude, the two models that
were above the band but **not** saturated.

- **Band reconciliation (§5.4, new paragraph).** The `[0.25, 0.70]` band
  was a conservative *panel-level* screen for bidirectional headroom, not
  a necessary condition for every model-specific label effect to be
  detectable. Terra and Claude classify `ABOVE` but their unlabeled point
  estimates leave `1 − 0.823 = 0.177` and `1 − 0.844 = 0.156` of upward
  point-estimate gap (descriptive, not thresholds); a positive `P − N`
  contrast was still detected for both. Sol and Luna had `N = 1.000` and
  no upward room. `ABOVE` and `SATURATED` are empirically distinct
  regimes; the frozen panel verdict remains `FAILS` exactly as
  pre-registered.
- **Methodological reading / Discussion (§7).** Separates the panel
  search criterion from model-specific directional detectability, and
  adds the general design lesson: relevant headroom is the distance to
  the corresponding outcome bound, read with the target effect size and
  estimator uncertainty; a fixed interior band is a useful conservative
  operating criterion, not a universal detectability threshold.
- **Contributions reordered.** The separately pre-registered 1,536-trial
  F3 study is now contribution 2 and carries the panel-vs-directional
  distinction explicitly; the general saturation point is contribution 3,
  stated without a prevalence claim over deployed agent tasks.
- **Claude wording.** Every summary now says Terra and Claude met the
  pre-registered *primary* model-specific CI criterion, and Terra also
  stayed below 0.05 under the supplementary Holm familywise adjustment
  while Claude (Holm ≈ 0.09) did not — never "non-significant" or "merely
  borderline", and the frozen primary criterion is not demoted.
- **Abstract.** One added clause: band membership is not a necessary
  condition for detecting a model-specific directional effect. The Holm
  qualification is retained.
- **§5.3.** One sentence on the frozen Phase 8A.2 round-two design
  guardrail (`docs/phase_8a2_pilot_design.md` §2–§3): no candidate could
  be written/revised/discarded using any per-model Phase 8C rate; the
  only carryover was one general model-agnostic mechanism lesson;
  candidates written as one batch, evaluated mechanically, hard stop
  after round two.
- **Phase 8 not re-litigated.** New explicit sentence: Phase 9 does not
  alter the frozen Phase 8 stopping decision; it only informs future
  interpretation of the operating criterion.
- **Limitations.** New `(xix)`: the `[0.25, 0.70]` interval was chosen a
  priori, not estimated from Phase 9 and not validated as optimal or
  minimal; the `0.177` / `0.156` gaps are descriptive, not a required
  headroom. Future-work note on choosing operating criteria from a target
  effect size and precision.
- **Table 1 (Phase 8 unlabeled-arm grid)** is now rendered as **two
  clearly separated panels** — Panel A (F1–F3, record set A) and Panel B
  (F4–F6, record set B) — so the disjoint-record-set, different-window
  rounds do not read as a matched six-condition matrix. No numerical
  value changed. `audit_phase8_numbers.py` was updated to verify the
  two-panel layout against the frozen grid.
- **Numeric integrity note** shortened to two ideas: (1) numbers/tables
  are reconciled against the frozen Phase 6–9 analysis artifacts
  (including recomputation from byte-pinned raw data) and the build fails
  on numerical drift; (2) separate manuscript-lint checks exist as
  documentation safeguards, not statistical verification. The full lint
  list stays in the audit code and reproducibility notes.

## What changed (code / tests)

- `app/reporting/phase_8_frozen_grid.py`: **additive only** — two new
  constants `ROUND_ONE_PILOT_RECORDS` / `ROUND_TWO_PILOT_RECORDS`,
  transcribed from the frozen design/result docs. No existing frozen
  value touched.
- `tests/unit/test_phase_8_round_set_disjointness.py` (new): mechanically
  proves round-one set A and round-two set B are disjoint by identifier,
  that their scored record bodies and field values are not accidentally
  identical, and that each set's four ids match the manuscript.
- `tests/unit/test_decision_context_provider_seam.py` (new): at the real
  provider-bound seam (`real_host_adapter._build_input`, shared by both
  host adapters), feeds an `mcp_tool_result` event stuffed with arm /
  condition / formulation-id / sink / expected-outcome / sensitivity /
  canary / evaluator metadata plus `is_mutating`/`approved`/`executed`,
  and asserts none of those keys or distinctive identifier values reach
  the model-visible payload while the record's scored values do.
- `tests/unit/test_phase_9_analyze.py`: two added tests — Q2 `Delta_hat`
  is exactly the equal-domain-weight mean over the 8 domain means
  (3 repeats are the per-scenario denominator, not 192 independent
  scenarios), and the S1f all-successes degeneracy is recorded in the
  frozen result artifact (`Q1.pathological` + `BOUNDARY_DEGENERACY_NOTE`)
  for exactly Sol and Luna.
- `paper/arxiv/audit_phase8_numbers.py`: Table 1 parser updated for the
  two-panel layout, numeric verification preserved.

## Code-audit findings (all clean — no implementation/manuscript mismatch)

- **Q2 implementation** (`scripts/phase_9_analyze.py` →
  `phase_9_design_simulation._q2_s1f` / `_ws_var_df_pd` /
  `_binom_floors_diff`): computes `Δ̂ = (1/8) Σ_d mean_s(π̂(s|P) −
  π̂(s|N))` with the fixed-stratum Welch–Satterthwaite `t` and per-domain
  binomial variance floor at `R = 3`. Matches the written estimand.
- **S1f boundary flag**: `phase_9_results_attempt_002.json` records
  `CONFIRMATORY_primary.per_model.{gpt-5.6-sol,gpt-5.6-luna}.Q1.pathological
  = true` plus the top-level `BOUNDARY_DEGENERACY_NOTE`. The manuscript's
  "(flagged `pathological`)" wording is artifact-backed.
- **Model-visible context**: `HostDecisionContext` structurally cannot
  carry the banned fields; `_build_input` serializes only
  `user_prompt` / `current_step` / `target_agent_card` /
  `available_mcp_tools` (via `model_visible_dump`) / `history` (via
  `_canonical_history_event`, which drops `is_mutating`/`approved`/
  `executed`).
- **Phase 8A.2 round-two guardrail**: `docs/phase_8a2_pilot_design.md`
  §2–§3 fix it exactly; the manuscript sentence is drawn from that text.
- **L0 / L1–L3**: §4.1 and limitation `(xviii)` already frame L1–L3 as
  near-match specificity cross-checks (0.0% FP), descriptive only, not a
  validation of L0 as a semantic-leak detector. No change; no new L0-vs-L1/L2/L3
  characterization added to the paper.

## Archive

- file: `agent-interop-bench-paper-v2.5.tar.gz`
- built by `scripts/build_paper_v2_release.py` (`--check` re-derives the
  archive SHA-256).
- SHA-256, byte size, member count, and the exact release commit are in
  the **Verification** section of this release page.
