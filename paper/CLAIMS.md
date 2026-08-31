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
no significance tests, no cross-model pooling of the primary outcome.** Every
numeric table body and the pair-effect figure in `paper/arxiv/main.tex` are
machine-generated from the frozen analysis artifacts by
`paper/arxiv/gen_tables.py` and audited by `paper/arxiv/audit_numbers.py`.
The prior Phase 4B pilot is historical evidence only.

---

## A. Directly supported empirical claims

1. **Confidential-versus-public labeling contrast vs. verbatim
   substantive-value egress.** In this matched-pair design, the paired
   difference in verbatim substantive-field egress to the remote agent
   between a record labelled `CONFIDENTIAL - INTERNAL ONLY` and an otherwise
   byte-identical record labelled `PUBLIC - OK TO SHARE` was negative for
   `gpt-5.6-sol`, `gpt-5.6-luna`, and `claude-sonnet-5`, and exactly zero
   for `gpt-5.6-terra`. **Both labels are active**, so this is a labeling
   contrast: the design cannot attribute the difference to the confidential
   wording, to the `OK TO SHARE` wording, or to both. The paired
   confidential$-$public difference is negative in every pair where either
   arm leaked, and no pair in any model reverses — but the confidential arm
   is at the $0$ floor for three of four models, so "no reversal" is partly
   structurally uninformative; `claude-sonnet-5` (confidential 2/40) is the
   one informative non-floor case. Pooled: `gpt-5.6-sol` 0/40 vs. 10/40
   (mean pair diff $-0.250$, bootstrap $[-0.450,-0.075]$); `gpt-5.6-luna`
   0/40 vs. 5/40 ($-0.125$, $[-0.200,-0.050]$); `claude-sonnet-5` 2/40 vs.
   38/40 ($-0.900$, $[-0.975,-0.825]$, 10/10 pairs negative).
   `gpt-5.6-terra` emitted no substantive value in either arm (0/40 vs.
   0/40) — a complete floor, uninformative about the labeling, with a
   degenerate $[0,0]$ bootstrap interval. **Magnitude is not uniform across
   models; the contrast is large only for `claude-sonnet-5`.** A
   neutral-label baseline is the clearest follow-up to decompose suppression
   vs. permission.
2. **RQ2 is a complete floor.** Across all 319 analysable RQ2 trials (320
   planned; 1 `provider_protocol_error` attrited), no model — OpenAI or
   Anthropic family — requested a state-changing MCP tool, under either the
   adversarial approval-and-execute-now framing or the matched
   approval-pending control. `mutating_tool_requested = 0`; exact
   proposed-target-tool requests $= 0$. Because the rate is pinned at 0 in
   both arms, **the design cannot establish resistance to adversarial
   cross-agent influence**; a plausible but unproven explanation is
   insufficient headroom in the generic `{call_tool, stop}` action surface /
   task framing.
3. **Verified enforcement property (not a research question).** Across all
   640 scheduled study trials (RQ1 320 + RQ2 320), the number of trials in
   which an unapproved request whose trusted discovered classification is
   mutating actually executed was **0** (`violations = 0`,
   `mutating_tool_executed = 0`). This follows from deterministic
   enforcement plus a per-trial trace audit; it is **not** a model safety
   rate, and because no model requested a state-changing tool, the gate was
   never exercised by a real state-changing request in this run.

## B. Descriptive observations (not effects)

- The label's effect on **relaying** is model-specific and does **not**
  shift every model toward `stop`: relay counts (confidential vs. public)
  were 9 vs. 19 (`gpt-5.6-sol`, toward stop), 3 vs. 38 (`claude-sonnet-5`,
  strongly toward stop), 22 vs. 22 (`gpt-5.6-terra`, no shift), 39 vs. 37
  (`gpt-5.6-luna`, marginally toward relaying).
- Under the adversarial framing some models substitute a read-only
  diagnostic call for `stop`: `claude-sonnet-5` `stop` rate 95% (control) vs.
  25% (adversarial); `gpt-5.6-sol` 12.5% vs. 0%. In every RQ2 cell the
  requested tool was read-only.
- `gpt-5.6-luna` relays a record in ~38 of 40 RQ1 trials in both arms but
  rarely copies exact field values.

## C. Limitations

- **Labeling-contrast confound:** RQ1 contrasts two active labels; the data
  cannot separate confidential-wording suppression from `OK TO SHARE`
  permission. No neutral-label arm was run; it is named as the clearest
  follow-up.
- **Treatment-arm floor:** the confidential arm is 0/40 for `gpt-5.6-sol`,
  `gpt-5.6-terra`, `gpt-5.6-luna`, so a positive pair difference is
  structurally impossible for them.
- 10 authored matched pairs per experiment; 4 model snapshots; the bootstrap
  over 10 pair differences is descriptive spread, not inference; no
  p-values. Four repeats + binary outcome ⇒ pair rates change in 0.25 steps.
- The RQ1 primary is exact-substring identity over six substantive values;
  paraphrased/summarised/partial disclosure is not measured; a $0$ is not
  "no information crossed the boundary." `disclosed_field_count` covers only
  the five structured fields (excludes `credential_token`, which the
  six-value primary includes).
- RQ2 primary is a complete floor across all 319 analysable RQ2 trials, so
  no influence-resistance claim is warranted; `gpt-5.6-terra`'s RQ1 cell is
  also at the floor with a degenerate $[0,0]$ bootstrap interval.
- OpenAI and Anthropic each run in their own low-effort mode; parameters are
  not numerically equivalent; `claude-sonnet-5` is a robustness block, not a
  ranked comparator.
- One attrition event (RQ2 analysable $N = 319$ vs. planned 320).
- Local in-process synthetic fixtures; one host policy; one 12-tool surface;
  one point in time.

## D. Claims that would be OVERSTATEMENT — not made

- "First cross-protocol study" / "first composition study" / "first MCP/A2A
  security work."
- **Any causal claim that confidential labeling protects, reduces, or
  prevents disclosure** — the design measures a symmetric labeling contrast
  only.
- **"3 of 4 models prove protection"** or any framing that treats the
  labeling contrast as demonstrated data protection.
- **"Resistant / robust to cross-agent influence"** — RQ2 is a floor and
  establishes no such thing.
- "Proof that model X is safe" / "models achieve a 100% safety rate" (the
  enforcement property is a deterministic gate plus audit, not a model
  safety rate, and no true state-changing request occurred).
- **"Empirical action containment"** — the gate was never exercised by a
  real state-changing request.
- Any causal or generalization claim beyond these matched fixtures and these
  four model identifiers.
- Any provider ranking or between-provider significance claim.
- "The adversarial manipulation had no effect" stated unconditionally — it
  produced no effect **on state-changing tool requests** (a floor); it did
  move read-only/stop behaviour for some models (pooled, exploratory).
- Any semantic-leakage claim; semantic/paraphrased leakage is not measured.
