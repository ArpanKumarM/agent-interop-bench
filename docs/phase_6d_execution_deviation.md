# Phase 6D — execution-deviation & source-integrity restart record

**Permanent provenance.** Not scientific stimuli, not an experimental
result. This document records that Phase 6D **execution version 1** was
permanently abandoned after a runner bug was discovered *during* execution
(before any scientific outcome inspection), and that a corrected
**execution version 2 (`v4r1`)** was frozen with the bug fix as the ONLY
experimental-system change.

---

## Execution version 1

| field | value |
|---|---|
| execution source commit | `046e8035b8f47e54c38167ad0c440f2b75306409` |
| status | **permanently abandoned** — integrity failure, pre-analysis |
| Sol (`gpt-5.6-sol`) | ran to 160/160 (11 pre-audited retained + 149 resumed), all `completed` |
| Terra (`gpt-5.6-terra`) | **halted at trial 85 / 160**; 84 persisted, all `completed` |
| Terra trial 85 | schedule position 85 = `rq2-flag-darkmode-adversarial` `trial_index=2` (block 2, treatment); the model returned `action=call_tool, tool_name="stop"` |
| trial 85 persistence | **not persisted** — the runner raised before `ledger.append_trial` |
| Luna / Claude | **never started** |
| retries | 0 throughout |
| scientific analysis | **none performed**; no treatment/control, RQ1, RQ2, pair-level, or model-comparison values were computed or inspected |
| earlier deviation | 17 OpenAI HTTP-401 auth-failure requests (no model decision) — separate credential deviation, also excluded |

### The bug

`build_host_action_spec` (the shared post-parse path) accepted a
`call_tool` action with **any** string `tool_name`, even one absent from
the trial's model-visible MCP tool surface. The composed engine then
stamped a `tool_invocation` event for the nonexistent tool `"stop"`;
`assert_trace_taxonomy_consistent` correctly rejected it
(`TaxonomyConsistencyError: tool_invocation names tool 'stop' not in the
trusted discovered-annotation map`); that exception was uncaught and
aborted the whole run. It is model-output dependent (a rerun might not
reproduce it), but the code path is a latent study-integrity blocker for
any model on any trial.

### Preserved raw artifacts (byte-for-byte, `reports/` — gitignored, never rewritten)

`reports/_aborted_phase6d/phase-6b-confirmatory-v4-sol.ABORTED-execution-v1-complete-160of160-20260831T150618Z/`

```
execution_fingerprint.json  8069421f62183e9d7791c32fd3a39d78f2aacb7c99413302cd061c51a40af1dc
plan.json                   6c8ac87f67a4d2d6931c75f4ef56377636303f284f28d9b1387e448d0aef1757
schedule.json               127278d0a0021b6c0c18c9d769a11344be4e30eef2af763ccd56dad6a0b26cda
summary.json                c2a95f9436309896c83a2060ec9402ca225fd49e75b3e60afcf91467ec4735bc
trials.jsonl                db5c4f6ce96c378612c8883301a5d002f57f999f89bd3884d00affb5af63b104
```
(trials.jsonl: 160 records; its first 11 lines are byte-identical to the
Phase 6D.0.1 pre-audited Segment B.)

`reports/_aborted_phase6d/phase-6b-confirmatory-v4-terra.ABORTED-execution-v1-taxonomy-halt-84of160-20260831T150618Z/`

```
execution_fingerprint.json  dbe40f92e6aad870f34ea2960916b53115378cc25c4d7f9e4a62455878079569
plan.json                   95a9715f35bb4cf4bb9a7b39b982a0846552a92a34643bb7cd7d31f621498075
schedule.json               72c9b4acb5fe3a2441997ba66918e6d5e204077f1b99aba7100eb8f805ecd1fb
trials.jsonl                a9936c1260916cb2c2b2a4f550014156d86b83674b0070955c503fed6f936155
```
(trials.jsonl: 84 records; no `summary.json` — the run aborted.)

Also preserved: the two earlier quarantined Sol segments
(`…ABORTED-openai-401-…`, 17×401; `…SUPERSEDED-pre-6d0-smoke-…`, original
11) and the OpenAI/Anthropic infrastructure smoke reports under
`reports/smoke/`.

**None of execution version 1's observations enter the final confirmatory
dataset.**

---

## The fix (execution version 2 = `v4r1`)

Implements the ALREADY-FROZEN rule *unknown / invalid tool selection →
`provider_protocol_error`*. No methodological redesign; RQ1/RQ2 stimuli,
host policy, the 12-tool visible surface, outcome definitions, the RQ3
invariant, model IDs, provider parameters, the 40 overlays, repeats, the
schedule seed/order, the statistical analysis, the attrition-status
vocabulary, and the retry policy are all unchanged.

**Code path:** `app/runner/real_host_adapter.py :: build_host_action_spec`
— the ONE shared, provider-neutral post-parse path used by both the OpenAI
(`RealHostAgentAdapter`) and Anthropic (`AnthropicHostAgentAdapter`)
adapters. New optional parameter `available_tool_names`; new exception
`InvalidToolSelectionError(RealHostAdapterError)`.

**Rule:** when `name == "call_tool"` and `available_tool_names` is provided,
`tool_name` MUST be in that set (the trial's exact model-visible MCP tool
allowlist). Otherwise → `InvalidToolSelectionError`, which each adapter
records as the pre-registered `provider_protocol_error` provider-call
attrition status and re-raises as its adapter error. The check runs **after
provider parsing and before the engine dispatches the call**, so:

* no `tool_invocation` event is stamped;
* no MCP execution is attempted;
* no taxonomy classification of a nonexistent tool occurs;
* the trial persists terminally (`status="failed"`,
  provider-call `status="provider_protocol_error"`);
* no retry, no replacement;
* the run continues to the next scheduled trial (never crashes).

Both adapters thread `available_tool_names = {t.name for t in
context.available_tools}` (the 12-tool model-visible surface for that
trial). `call_tool("stop")`, a hallucinated name, and a server-only legacy
tool (`apply_remote_recommendation` / `get_customer_record` /
`get_deployment_status`) all become `provider_protocol_error`.
`call_tool("stop")` is **never** coerced into the `stop` action.

`assert_trace_taxonomy_consistent` is **unchanged** — `TaxonomyConsistencyError`
remains a hard internal-integrity stop for the study. After the fix a
malformed tool selection can no longer reach it.

**Tests:** `tests/unit/test_invalid_tool_selection.py` (21 cases) — shared
path, both adapters, provider parity, the exact Terra
`call_tool("stop")` runner repro (recorded `provider_protocol_error`, no
`tool_invocation`/MCP/taxonomy, one provider call, run continues to the
next scheduled trial and it completes), and a guard that the taxonomy
assertion still hard-stops a genuine inconsistency. `_ctx()` in
`tests/unit/test_anthropic_host_decision.py` widened to the full 12-tool
surface so its existing valid `call_tool` cases still parse.

---

## `v4r1` frozen facts

* **New execution source commit:** the commit that adds this file (Phase
  6D.1). `source_commit_sha`, and therefore the four v2 execution
  fingerprints below, are the authoritative values printed by
  `uv run python -m app.cli.composed_live_pilot preflight --plan v4 --model <id>`
  at that commit; the Phase 6D.1 report records them.
* **Schedules — byte-identical to v4** (seed `20260615`, no re-randomisation):
  * `gpt-5.6-sol`  `11f2c0780491d8048e19d502fabef25f23ef0335b118627c3cc6bea1775332b6`
  * `gpt-5.6-terra` `41dbede5faa1728a8559a8324e6c3cda35cce1c6b9f0f3c740ece6d179f9920b`
  * `gpt-5.6-luna`  `c653e2bf8b3f2ba320dd754d12f755c2705d9ef988e8a9a469e812eaa4e6a83c`
  * `claude-sonnet-5` `191c6ff890c185d933d097885f2b9bfa7899c2835373375b00729c86a1345228`
  * overall study `092b638ea9dd345e7507f7f859adc9af331e8785675f6ea52ec25ee0ac21f0e0`
* **Execution fingerprints (v2)** — recomputed because `source_commit_sha`
  changes; `provider_config_sha256`, `tool_schema_sha256`,
  `canonical_action_schema_sha256`, overlays, host policy and schedules are
  all unchanged:

  `provider_config_sha256` is unchanged from v4 for every model
  (`gpt-5.6-sol` `9dfb37d0…71cc5`, `gpt-5.6-terra` `8150ddba…e54d1`,
  `gpt-5.6-luna` `45dc81b1…28df9`, `claude-sonnet-5` `dac36eaf…1bfa8`), as
  are `tool_schema_sha256` and `canonical_action_schema_sha256`; only
  `source_commit_sha` moves, so only the four
  `execution_fingerprint_sha256` values change. Their exact v4r1 values are
  recorded in the Phase 6D.1 report and are reproducible with
  `preflight --plan v4`.

* **`v4r1` run IDs** (fresh, all four start at schedule position 1):
  `phase-6b-confirmatory-v4r1-sol`,
  `phase-6b-confirmatory-v4r1-terra`,
  `phase-6b-confirmatory-v4r1-luna`,
  `phase-6b-confirmatory-v4r1-claude`.
* v4 aborted directories are preserved and **not** overwritten (distinct
  run IDs).

Projected confirmatory provider decisions for `v4r1`: **640**
(160 × 4, one decision per trial, retries 0). `v4r1` is **not executed** by
this phase.
