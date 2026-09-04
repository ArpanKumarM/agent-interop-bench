# Phase 8A.2 — pre-registered framing-selection rule (frozen BEFORE candidates)

**Status: FROZEN before any Phase 8A.2 framing candidate is written.** This
is the actual point of the exercise: the selection rule is stated and
committed first; candidates are written after, against this rule, not the
other way around. If this file is ever edited after a candidate exists,
that is a violation of the design and must be disclosed as one.

## Why this document exists

The Phase 8C pilot (`docs/phase_8c_pilot_result.md`) rejected all three
`F1`/`F2`/`F3` candidates: the calibration rule passed cleanly (the
instrument works), the headroom rule failed (the unlabeled baseline
saturates near ceiling for 3 of 4 models under every candidate).

A second review pass on that result identified a real risk in how the next
iteration was about to proceed: **designing new candidates by looking at
which model moved the most in the failed pilot, and building toward that
model's specific response curve, is selection on the outcome variable.**
Freezing the analysis plan afterward does not fix this — the fork already
happened at task-design time. This document exists to close that path
before it is taken.

## 1. The selection rule (unchanged from Phase 8C, restated exactly)

For each candidate framing, pooled over the pilot's scenarios and models:

- **Headroom**: unlabeled-arm (`N`) L0 rate ∈ `[0.25, 0.70]` for **≥ 3 of
  4 models**.
- **Sensitivity**: `permit − suppress ≥ 0.50` for **≥ 3 of 4 models**.
- Both required. Non-saturation (`permit < 1.0` for ≥ 2 models) remains
  advisory only.

**Among candidates that pass both rules, pick the one whose mean `N` rate
(averaged over the models with an in-band rate) is closest to the band
midpoint (0.475).** This is the entire selection procedure. There is no
discretionary step, no "looks most promising" judgment call, and no
per-model tie-break beyond this one arithmetic rule.

**If no candidate passes, do not select one anyway.** Loop back again.

## 2. What is explicitly forbidden in designing the candidates

- **No candidate may be written, revised, or discarded based on any
  individual model's numeric response in the Phase 8C pilot** (or any
  earlier pilot). `gpt-5.6-terra` showing more mid-range variation than
  `gpt-5.6-sol` in Phase 8C is a *reason to expect this study can find a
  working framing at all* — it is not a target to reverse-engineer a
  wording toward. A framing must be motivated by an independent,
  statable task-design argument (see §3), not by "this wording moves
  terra's number into the band."
- **No candidate may be selected, ranked, or discarded using Phase 8C's
  per-model rates**, full stop — Phase 8C's only permitted contribution to
  Phase 8A.2 is the *mechanism-level* lesson in §3, stated once, in
  general terms, before any candidate text is drafted.
- **No iterative fitting.** Candidates are written once as a batch,
  piloted once, evaluated against §1 mechanically. If none pass, this
  document is not touched; a **new**, separately-numbered document
  (Phase 8A.3) states any new task-design argument before new candidates
  are drafted, exactly as this one does for 8A.2.

## 3. The one permitted mechanism-level lesson from Phase 8C

Stated in general terms, with no reference to any specific model's rate:

> All three Phase 8C candidates framed forwarding customer information as
> the point of the task ("give them what they need," "a summary," "respond
> to their request"). Under that framing, forwarding became close to an
> unconditional default: the wording was gentler across candidates, but
> the *task structure* still made withholding read as failing the task
> rather than as a reasonable, competent choice. A candidate with real
> headroom needs a task where a competent agent choosing to withhold or
> minimize is plausible on its own terms — not merely a softer version of
> "send it."

This is the only carryover from Phase 8C. Section 4 of the Phase 8A.2
candidate document (to be written next, informed only by this paragraph)
must not reference per-model Phase 8C numbers.

## 4. Disjoint scenarios (pilot vs. main study)

**The Phase 8C pilot scenario set overlapped the main study's 24
scenarios** (`healthcare-billing`, `logistics-shipment`,
`insurance-claims`, `ad-platform-advertiser` are all members of the main
24). This is fixed going forward:

- `PHASE_8_PILOT_SCENARIOS` is replaced with **4 new scenarios that are
  never members of `PHASE_8_SCENARIOS`** (the 24 main-study scenarios) --
  see `mock_servers/phase_8_fixtures.py` `PHASE_8_PILOT_ONLY_SCENARIOS`.
- Any future pilot (8A.2, 8A.3, ...) uses this same disjoint pilot-only
  set. The main study's 24 scenarios are never touched by any pilot, so
  no scenario that ever appears in the frozen manuscript numbers has had
  its response to any candidate framing observed beforehand.

## 5. Every framing piloted is reported, including failures

`docs/phase_8c_pilot_result.md` already reports F1/F2/F3 in full,
including the rejection. This is a standing commitment for every future
pilot iteration too: the eventual manuscript's reproducibility section
carries a **"framings piloted and discarded"** table (design id, one-line
task-design rationale, headroom/sensitivity pass-fail per model, decision),
not just the winning framing. A pilot failure is disclosed exactly like a
pilot success.

The pilot-vs-framing sensitivity itself (Phase 7 floored at 0, Phase 8C's
naive-headroom framings ceilinged near 1, all from wording changes alone)
is flagged as a candidate discussion point for the eventual manuscript,
independent of whether the main study ever executes: **the same behavior
swung from ~0% to ~100% on task phrasing alone, a larger swing than any
label effect measured anywhere in this project.** That observation stands
on its own and does not require the main study to be worth reporting.

## 6. One primary contrast, one primary channel comparison

To avoid an unstated multiplicity problem across `7 arms × 24 scenarios ×
2 sinks × 4 models`, the eventual main-study manuscript pre-specifies
**exactly one primary test**:

- **Primary contrast: `P − N` (public vs. unlabeled) under the
  `a2a_relay` sink**, the direct descendant of Phase 7's headline result.
- **Primary channel comparison: the `P − N` sink interaction** (`a2a_relay`
  vs. `user_reply`), since this is the single result that speaks to
  whether the effect is A2A-specific — the paper's most valuable new
  claim per the second-pass review.

Both are already implemented exactly this way in
`app/reporting/phase_8.py` (`contrast()` and `sink_interaction()`) and
already carry Holm correction within their own declared families
(`docs/phase_8a_parameters.md` §5). **Everything else — `C − N`, `C − P`,
the wording-ablation contrasts (S8-C), the policy-robustness contrast
(S8-D), any L1-L3 recomputation — is explicitly exploratory** and must be
labeled as such in every table it appears in. No new correction scheme is
introduced for the exploratory set; it is reported descriptively, exactly
as Phase 7 reported its non-primary numbers.

## 7. Repeats raised: R = 6 → R = 8

Cost is not the constraint (measured Phase 8C rate: ~$0.005–0.01/trial).
`R = 6` gives a 0.167 rate grid; `R = 8` gives 0.125, a real resolution
gain for a few additional dollars across the whole study. `R` is raised to
**8** for every main sub-study (S8-A/A'/B/C); S8-D keeps its own separate
`R = 4` per the original design (a robustness check, not a headline
result). Recorded formally in `docs/phase_8a_parameters.md` O2.

## 8. Near-match detector specificity check, required before any L1-L3 number is reported

L1/L2/L3 (`app/reporting/semantic_egress.py`) are not interpretable until
their false-positive rate against genuinely negative content is measured
and disclosed. Before Phase 8E (or any earlier reporting of an L1-L3
number), `app/reporting/semantic_egress_validation.py` computes and
publishes each detector's false-positive rate against:

- every trial's own `stop` outcome (empty/`None` outbound text);
- scrambled-value negative controls (the six substantive values replaced
  by matched-shape random strings, checked against the *original*,
  unscrambled outbound text);
- unrelated filler text (boilerplate customer-service phrasing containing
  none of the six values).

The false-positive rate table is a required part of any manuscript
section that reports an L1-L3 number.

## 9. The judge stays a cross-check, never an outcome

Unchanged from the original design and reaffirmed here: L4
(`app/reporting/llm_judge_crosscheck.py`) is reported only as trial-level
**agreement** with L0-L3 (Cohen's kappa, a confusion table), never as an
outcome in any contrast, primary or exploratory. The judge-free primary
scoring stays the paper's selling point.
