# Phase 8A.2 pilot result (round 2): NO CANDIDATE ACCEPTED — STOP RULE TRIGGERED

**Status: pilot round 2 executed and rejected. Per the pre-registered
failure branch (`docs/phase_8a2_pilot_design.md` §1a), the loop STOPS
here.** Round 3 is not attempted. No new framing candidates are written.
**The main study (S8-A…D) does not run.** This document is that outcome
record.

> ## Later correction & clarification (2026-09-07, v2 submission pass)
>
> The frozen per-model rates in this document are unchanged and were
> always correct (they are also independently recomputable from the
> byte-pinned round-two raw — this round, unlike round one, is not
> provenance-limited). Corrections below are to **derived / interpretive
> text only**, and **no accept/reject outcome changes** (headroom needs
> ≥3/4; the true count at every framing is ≤1/4):
>
> | location | field | as written | corrected | why |
> |---|---|---|---|---|
> | F4 row, acceptance table | headroom in-band count | `0/4` | **`1/4`** | `claude-sonnet-5` `N = 0.417` ∈ `[0.25, 0.70]` |
> | "Reading" section, `claude-sonnet-5` paragraph | position of `N = 0.417` relative to band | "just under" | **"inside the band"** | `0.25 ≤ 0.417 ≤ 0.70` |
>
> The corrected counts are recomputed from the byte-pinned raw by
> `scripts/verify_phase_8_pilot_docs.py` and checked by
> `paper/arxiv/audit_phase8_numbers.py`, so they cannot drift again.
>
> **Interpretive language.** The "Cross-round synthesis" and "Decision"
> sections were written at pilot time, before the v2 reframe. Phrases
> such as "its effect is small relative to — and swamped by — the task
> framing's effect" and "task-framing sensitivity … is large enough …
> to dominate any effect a … label could produce" state a **stronger
> label-vs-framing magnitude comparison than the study supports** and
> are superseded by the cautious v2 central claim: *under this fixed
> decision surface, task framing strongly changed the unlabeled
> operating regime and frequently pushed behavior to floor or ceiling,
> determining whether the sensitivity-label contrast could be measured;
> the study does not establish that task-framing effects are universally
> larger than label effects* (`paper/main_v2.md` §7). The body text
> below is left as the historical record; read it against that
> statement.
>
> **F3 remains unresolved.** Interval analysis added in the v2 pass
> (Wilson 95% CIs at n = 12) shows that at **F3** three of four models'
> CIs overlap `[0.25, 0.70]` — the acceptance threshold itself — so the
> point-estimate rejection of F3 is *not distinguishable* from an
> acceptance at this sample size. This does not reopen the Phase 8 stop
> (F3 was rejected under the frozen point-estimate rule and Phase 8 is
> stopped); it is the specific uncertainty a separate follow-up
> (`docs/phase_9_f3_resolution_design.md`, not yet run) is designed to
> resolve.

## Execution

- Executable source commit: `d06a88b0eebd6f4452ab09ccbc6fe5c2a4907631`
  (the pre-execution-hardening commit).
- Plan version `v8pilot`, candidates `F4`/`F5`/`F6`
  (`docs/phase_8a2_pilot_design.md` §3), pilot-only scenarios disjoint
  from the 24 main-study scenarios.
- 576 trials planned; **575/576 completed**, 1 attrition on
  `gpt-5.6-terra` (`provider_protocol_error`-shaped: `max_output_tokens`
  truncation, same failure mode as round 1; no retry, no replacement).
- Measured cost: **$3.02** (sol $1.32, terra $0.66, luna $0.07, claude
  $0.97).
- Raw `trials.jsonl` SHA-256 per model:

| model | trials.jsonl SHA-256 |
|---|---|
| gpt-5.6-sol | `db9d3c5ca540c0e19730e9f4e80ed5f6cbd4cae57af933af8fd5d3aee5af6899` |
| gpt-5.6-terra | `55144203978551a8abd694c7885dee1abc7f01566f82d4218376b05dbd5184f4` |
| gpt-5.6-luna | `6a2512282b4dbcf5c412219034deca38acaf5bd50a0815bddc38568ff79940da` |
| claude-sonnet-5 | `8f916fa3cf3315e2fd89a1fec0fe74bd2e3c7ee7d3936d590db9fd15dff42c73` |

Raw runs at `reports/experiments/phase-8-pilot-<model>/` (gitignored; the
hashes above are the pin). Analysis: `app/reporting/phase_8c_pilot.py`,
`FRAMINGS = ("F4", "F5", "F6")`.

## Acceptance-rule table

| framing | headroom pass | sensitivity pass | non-saturation (advisory) | **accepted** |
|---|---|---|---|---|
| F4 (status-only ask) | **NO** (1/4 in band) `[corrected]` | yes (3/4) | yes (4/4) | **NO** |
| F5 (recipient-TBD handoff) | **NO** (0/4 in band) | **NO** (2/4) | yes (4/4) | **NO** |
| F6 (reference-or-detail choice) | **NO** (0/4 in band) | yes (3/4) | yes (4/4) | **NO** |

### Per-model detail

| framing | model | N | permit | suppress | sep |
|---|---|---|---|---|---|
| F4 | gpt-5.6-sol | 0.000 | 0.667 | 0.000 | 0.667 |
| F4 | gpt-5.6-terra | 0.000 | 0.167 | 0.000 | 0.167 |
| F4 | gpt-5.6-luna | 0.000 | 1.000 | 0.000 | 1.000 |
| F4 | claude-sonnet-5 | 0.417 | 0.583 | 0.000 | 0.583 |
| F5 | gpt-5.6-sol | 0.000 | 1.000 | 0.000 | 1.000 |
| F5 | gpt-5.6-terra | 0.000 | 0.333 | 0.000 | 0.333 |
| F5 | gpt-5.6-luna | 0.000 | 1.000 | 0.000 | 1.000 |
| F5 | claude-sonnet-5 | 0.917 | 0.083 | 0.000 | 0.083 |
| F6 | gpt-5.6-sol | 0.000 | 0.917 | 0.000 | 0.917 |
| F6 | gpt-5.6-terra | 0.000 | 0.167 | 0.000 | 0.167 |
| F6 | gpt-5.6-luna | 0.000 | 1.000 | 0.000 | 1.000 |
| F6 | claude-sonnet-5 | 0.833 | 0.833 | 0.000 | 0.833 |

## Reading

**The three OpenAI tiers floored again** (`N = 0.000` for sol/terra/luna
in all three framings) — the opposite of Phase 8C's ceiling, and a return
to Phase 7's original floor pattern. `gpt-5.6-terra`'s calibration
separation also collapsed this round (0.167–0.333, below the 0.50
sensitivity bar in all three, the only model to fail sensitivity anywhere
in this project's Phase 8 pilots) — worth noting for its own sake:
`terra`'s instrument sensitivity is not stable across framings, so its
promising mid-range Phase 8C numbers should not be read as a durable
model property.

**`claude-sonnet-5` is the only model that varied continuously across all
six piloted framings to date** (Phase 8C: 0.750–1.000; this round:
0.417–0.917), never fully floored or ceilinged, and it is the only model
for which `N` landed inside or near the target band this round (F4:
0.417, **inside the band** `[corrected — see top; 0.25 ≤ 0.417 ≤ 0.70]`;
F6: 0.833, over). No model, in either pilot round, satisfied the
headroom rule (which requires ≥3/4 models in band on one framing; the
most any framing reached is 1/4).

## Cross-round synthesis (the actual empirical result of the Phase 8A/8C exercise)

Across two independently piloted, pre-registered framing families:

| study | framing style | pooled OpenAI-tier `N` behavior | Claude `N` behavior |
|---|---|---|---|
| Phase 7 (original paper) | terse, ambiguous | floor (0) | low (0.125) |
| Phase 8C (round 1) | forwarding-as-task | ceiling (0.50–1.00) | ceiling (1.00) |
| Phase 8A.2 (round 2) | withholding-legitimized | floor (0) | mid, variable (0.42–0.92) |

**The unlabeled-arm relay rate for the three GPT-5.6 tiers swings between
a complete floor and a near-complete ceiling based on task phrasing
alone, with no reliable middle ground found across six attempted
framings.** ~~Whatever a confidential/public/unlabeled header does to
these models' behavior, its effect is small relative to — and swamped by
— the task framing's effect on baseline behavior.~~

> *[Superseded — see the correction block at the top of this document.
> The current defensible claim: **task framing strongly changed the
> unlabeled operating regime, frequently pushing behavior to floor or
> ceiling and therefore determining whether the sensitivity-label
> contrast could be measured. The study does not establish that
> task-framing effects are universally larger than label effects.**
> (`paper/main_v2.md` §7.)]*

The N-regime swing itself is a property of six actually-piloted,
pre-registered framings, not a hypothesis, and holds independent of
whether the main study ever runs.

`claude-sonnet-5` is the exception worth a sentence of its own: it is the
only model, across every framing in every phase of this project, that
never fully floors or ceilings, and it is the only model whose behavior
looks continuously graded rather than switch-like. That asymmetry between
providers/families is itself a finding independent of the original
label-effect question.

## Decision (per the pre-registered rule, `docs/phase_8a2_pilot_design.md` §1a)

**STOP. No round 3.** The main study (S8-A…D, ~13,000 trials under the
harness built in Phase 8B) does not run under any framing piloted so far.
Total spend across both pilot rounds: **$6.34** (round 1 $3.32 + round 2
$3.02); the ~$45–65 main-study cost was never at risk.

**This project's honest reportable finding, as of this pilot exercise, is
a re-scoping, not a null result:** ~~task-framing sensitivity in this
MCP-to-A2A decision surface is large enough, for three of four models, to
dominate any effect a confidentiality/public-sharing label could produce
on top of it.~~

> *[Superseded — see the correction block at the top. The current
> defensible claim: **task framing strongly changed the unlabeled
> operating regime, frequently pushing behavior to floor or ceiling and
> therefore determining whether the sensitivity-label contrast could be
> measured. The study does not establish that task-framing effects are
> universally larger than label effects.** (`paper/main_v2.md` §7.)]*

Whatever paper this becomes, it is a paper about *that* — illustrated by
Phase 6/7's original label contrasts and this project's two failed
attempts to find a task framing with real headroom — not a paper
reporting a validated, sink-differentiated label effect, because the
instrument was never able to measure one under stable mid-range
conditions.

## What happens now

No further pilot round is authorized by the pre-registered rule. Next
steps available, none of them "try more framings":

1. **Write up the honest result** — the manuscript restructure
   (`docs/phase_8_design.md` §10) still applies, but the headline
   changes: the calibration instrument works, the sink comparison and
   near-match scoring are validated (0% false-positive rate,
   `docs/phase_8a2_pilot_design.md` §8), and the label-vs-framing-magnitude
   comparison across six piloted framings is itself the result, reported
   with the full "framings piloted and discarded" table
   (`docs/phase_8c_pilot_result.md` + this document) as the pre-registered
   discipline requires.
2. **A structurally different decision surface** (flagged, not attempted,
   in `docs/phase_8c_pilot_result.md`'s point 3) — e.g. a third action
   (partial-forward / summarize-without-verbatim) — is future work, not a
   Phase 8A.3 pilot round under the current rule.
3. **Report `gpt-5.6-terra`'s calibration instability** as a secondary
   methodological note: an instrument-sensitivity gate can itself depend
   on task framing, which the original design (`docs/phase_8_design.md`
   S7.4) did not anticipate.
