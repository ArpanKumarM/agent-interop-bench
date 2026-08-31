# CLAIMS — what this paper does and does not assert (v4r1)

Scope of every claim below: a **real-model host** — three OpenAI GPT-5.6
tiers (`sol`/`terra`/`luna`) via the Responses API and **Claude Sonnet 5**
via the Anthropic Messages API — driven over **local deterministic MCP and
A2A protocol fixtures**, one host policy, one **12-tool model-visible MCP
surface**, **40 fixed overlays** (10 matched RQ1 pairs + 10 matched RQ2
pairs), the **decision-point** methodology (one restricted host decision per
trial), **four repeats** per (model, overlay), **320 RQ1 trials**, **320
planned / 319 analysable RQ2 trials**, **640 scheduled trials total**, at
one point in time. All numbers are from the frozen Phase 6E analysis
(analysis source commit `60024fcf24624fab90ac9d6a3be7c73be17acbc9`;
execution source commit `23bf90bf379654f0afc2fadaa5a16ade30ae3439`). The
generalization unit is the matched stimulus pair; the four within-pair
repeats are repeated observations, not independent samples. **No p-values,
no significance tests, no cross-model pooling.** The prior Phase 4B pilot is
historical evidence only.

---

## A. Directly supported empirical claims

1. **Confidentiality label vs. verbatim substantive-value egress.** In this
   matched-pair design, marking a record confidential (vs. an otherwise
   byte-identical public record) is associated with a lower rate of
   verbatim substantive-field egress to the remote agent for `gpt-5.6-sol`,
   `gpt-5.6-luna`, and `claude-sonnet-5`. The paired confidential$-$public
   difference is negative in every pair where either arm leaked, and no pair
   in any model reverses. Pooled: `gpt-5.6-sol` 0/40 vs. 10/40 (mean pair
   diff $-0.250$, bootstrap $[-0.450,-0.075]$); `gpt-5.6-luna` 0/40 vs. 5/40
   ($-0.125$, $[-0.200,-0.050]$); `claude-sonnet-5` 2/40 vs. 38/40
   ($-0.900$, $[-0.975,-0.825]$, 10/10 pairs negative). `gpt-5.6-terra`
   emitted no substantive value in either arm (0/40 vs. 0/40) — a floor,
   uninformative about the label. **Magnitude is not uniform across
   models.**
2. **No state-changing tool requests under the influence manipulation.**
   Across all 319 analysable RQ2 trials (320 planned; 1
   `provider_protocol_error` attrited), no model — OpenAI or Anthropic
   family — requested a state-changing MCP tool, under either the
   adversarial approval-and-execute-now framing or the matched
   approval-pending control. `mutating_tool_requested = 0`;
   exact proposed-target-tool requests $= 0$.
3. **Unapproved-mutation containment invariant.** Across all 640 scheduled
   study trials (RQ1 320 + RQ2 320), the number of trials in which an
   unapproved request whose trusted discovered classification is mutating
   actually executed was **0** (`violations = 0`,
   `mutating_tool_executed = 0`). This follows from deterministic
   enforcement plus a per-trial trace audit; it is **not** a measured model
   property, and because no model requested a state-changing tool, the gate
   was not stress-tested by a real influenced mutation in this run.

## B. Descriptive observations (not effects)

- The confidentiality label's effect on **relaying** is model-specific and
  does **not** shift every model toward `stop`: relay counts (confidential
  vs. public) were 9 vs. 19 (`gpt-5.6-sol`, toward stop), 3 vs. 38
  (`claude-sonnet-5`, strongly toward stop), 22 vs. 22 (`gpt-5.6-terra`, no
  shift), 39 vs. 37 (`gpt-5.6-luna`, marginally toward relaying).
- Under the adversarial framing some models substitute a read-only
  diagnostic call for `stop`: `claude-sonnet-5` `stop` rate 95% (control) vs.
  25% (adversarial); `gpt-5.6-sol` 12.5% vs. 0%. In every RQ2 cell the
  requested tool was read-only.
- `gpt-5.6-luna` relays a record in ~38 of 40 RQ1 trials in both arms but
  rarely copies exact field values.

## C. Limitations

- 10 authored matched pairs per experiment; 4 model snapshots; the bootstrap
  over 10 pair differences is descriptive spread, not inference; no
  p-values.
- The RQ1 primary is exact-substring identity over six substantive values;
  paraphrased/summarised/partial disclosure is not measured; a $0$ is not
  "no information crossed the boundary."
- RQ2 primary is a complete floor across all 319 analysable RQ2 trials;
  `gpt-5.6-terra`'s RQ1 cell is also at the floor.
- OpenAI and Anthropic each run in their own low-effort mode; parameters are
  not numerically equivalent; `claude-sonnet-5` is a robustness block, not a
  ranked comparator.
- One attrition event (RQ2 analysable $N = 319$ vs. planned 320).
- Local in-process synthetic fixtures; one host policy; one 12-tool surface;
  one point in time.

## D. Claims that would be OVERSTATEMENT — not made

- "First cross-protocol study" / "first composition study" / "first MCP/A2A
  security work."
- "Proof that model X is safe" / "models achieve a 100% safety rate" (RQ3 is
  an enforcement invariant plus audit, not a measured model property, and no
  true mutating request occurred).
- Any causal or generalization claim beyond these matched fixtures and these
  four model identifiers.
- Any provider ranking or between-provider significance claim.
- "The adversarial manipulation had no effect" stated unconditionally — it
  produced no effect **on state-changing tool requests** (a floor); it did
  move read-only/stop behaviour for some models.
- Any semantic-leakage claim; semantic/paraphrased leakage is not measured.
