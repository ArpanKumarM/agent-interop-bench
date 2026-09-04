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

**If no candidate passes, do not select one anyway.** Loop back again --
subject to the round limit in §1a.

### 1a. No partial credit, no per-model salvage, and a hard stop after round 2

Two ambiguities a bare pass/fail rule leaves open if not closed explicitly:

- **Partial pass is a fail, not a judgment call.** "≥ 3 of 4 models"
  means exactly that: 2 models in-band is REJECT, full stop, regardless
  of how close the pattern looks to passing. There is no "2 of 4 plus it
  looks promising" path.
- **Acceptance is all-or-nothing per framing across the FULL 4-model
  panel.** A framing that clears the bar in only some models is rejected
  in its entirety -- there is no per-model salvage (e.g. "run the main
  study under F5 for the two models where F5 worked, and a different
  framing for the other two"). A mixed-framing main study across models
  is not a design this project runs; it would make every cross-model
  comparison uninterpretable.

**Round limit.** This is pilot round 2 (round 1 = F1/F2/F3, rejected;
`docs/phase_8c_pilot_result.md`). **If round 2 (F4/F5/F6) also rejects
every candidate, the loop stops. Round 3 is not attempted, no new
framings are written, and the main study does not run.** In that case the
project's finding is reframed and reported as-is: **task-framing
sensitivity dominates any measurable label effect** in this decision
surface -- itself a real, reportable result (§5) -- rather than continuing
to search for a framing that produces the originally-hoped-for label
contrast. This limit exists for the same reason §2 exists: an unbounded
search for a passing framing is indistinguishable, after enough rounds,
from fitting the framing to the desired result.

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

### 3a. Candidate independence check (written after drafting F4/F5/F6, before piloting)

Three candidates are only worth three separate bets if they can fail or
pass for different reasons. Honest read of what was actually written:

- **F4** (status-only ask) and **F5** (recipient-TBD handoff) share a
  family resemblance: both reduce forwarding-obligation by making the
  *need* for the record's specifics ambiguous or not-yet-established,
  rather than by offering an explicit alternative action. If a model's
  disposition to forward is driven mainly by "does this request obviously
  require PII," F4 and F5 may move together rather than independently.
- **F6** (reference-or-detail choice) is the one candidate using a
  structurally different mechanism -- an explicit, named non-forwarding
  path presented as equally legitimate -- rather than ambiguity about
  need. It is the most likely of the three to behave differently from the
  other two.

**Consequence, stated in advance so it cannot be fitted after seeing
results:** if F4 and F5 pass or fail together while F6 diverges, that
pattern is consistent with the mechanism split above and will be reported
as such. It does not change the selection rule in §1/§1a -- acceptance is
still mechanical -- but the eventual manuscript's "framings piloted"
table (§5) will note this grouping so a reader can judge how many
genuinely independent bets three candidates actually represented, rather
than reading three passes/failures as three independent data points.

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

## 7. Repeats: R = 6 → R = 8 everywhere, R = 16 for S8-A specifically

Cost is not the constraint (measured Phase 8C rate: ~$0.005–0.01/trial).
`R = 8` (0.125 grid) applies to S8-A'/B/C; S8-D keeps its own separate
`R = 4` (a robustness check, not a headline result). **S8-A -- the
sub-study containing the one primary contrast and the one primary
interaction (§6) -- is raised further, to `R = 16` (a 0.0625 grid)**: fine
resolution where the manuscript's central claim is decided, the coarser
grid everywhere else. Extra cost for that one sub-study: roughly
2,300 additional trials/model (≈ $25 total across the panel) over the
R = 8 baseline -- still small next to the ≈ $45 whole-study estimate.
Recorded formally in `docs/phase_8a_parameters.md` O2;
`app.runner.blocked_schedule.PHASE_8_SUBSTUDY_BLOCKS_PER_MODEL["v8a"]`
overrides the shared `PHASE_8_BLOCKS_PER_MODEL` default accordingly.

## 7a. Pilot/main contamination check

Disjoint scenarios (§4) closes the stimulus-content path. The execution
path is closed structurally, not just by convention: the main-study
analysis CLI (`app/cli/phase_8.py`) only ever reads from run directories
named `phase-8-<substudy>-<model>` for `substudy` in
`{v8a, v8a2, v8b, v8c, v8d}` (its `RUN_DIRNAME` table) -- it has no code
path that can address a pilot run directory. Pilot runs are written to
`phase-8-pilot-<model>` (`v8pilot`'s own plan/run-id namespace), which
does not match any `RUN_DIRNAME` entry. This is asserted by
`test_pilot_run_directories_are_disjoint_from_main_study_run_directories`
in `tests/unit/test_phase_8_cli_analysis.py` -- a structural guarantee,
not a naming convention someone could accidentally violate.

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
