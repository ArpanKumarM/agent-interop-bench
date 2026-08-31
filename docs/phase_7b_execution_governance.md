# Phase 7B — execution governance (frozen BEFORE any provider call)

**Status: FROZEN. NOT EXECUTED.** This document is the pre-registered
execution contract for the Phase 7 neutral-baseline study. It is frozen
together with the executable source; nothing here may change after
`EXECUTION_SOURCE_SHA` is committed. No outcome analysis is inspected while
any decision in this document is being made.

Design / pre-registration: `docs/phase_7a_neutral_baseline_design.md`.

## 1. Run identifiers and panel

Panel order (one `random.Random(20260831)` advanced model-by-model in this
order): **`gpt-5.6-sol` → `gpt-5.6-terra` → `gpt-5.6-luna` →
`claude-sonnet-5`**.

| model | run ID | run directory |
|---|---|---|
| `gpt-5.6-sol` | `phase-7a-confirmatory-v1-sol` | `reports/experiments/phase-7a-confirmatory-v1-sol/` |
| `gpt-5.6-terra` | `phase-7a-confirmatory-v1-terra` | `reports/experiments/phase-7a-confirmatory-v1-terra/` |
| `gpt-5.6-luna` | `phase-7a-confirmatory-v1-luna` | `reports/experiments/phase-7a-confirmatory-v1-luna/` |
| `claude-sonnet-5` | `phase-7a-confirmatory-v1-claude` | `reports/experiments/phase-7a-confirmatory-v1-claude/` |

- **120 scheduled trials per model. 480 total.**
- Exactly **one** provider decision per trial. `max_retries = 0`.
  `max_decisions_per_trial = 1`. `max_total_decisions = 120` per run.
- **No replacement trials, ever.** A scheduled trial is attempted at most
  once; whatever terminal state it reaches is the recorded state.

## 2. Model-output terminal handling (recorded, no retry, continue)

Every trial ends `COMPLETED` or `FAILED`; the failure class is one of the
already-frozen pre-registered classes (`app.models` taxonomy). None is
coerced, retried, or replaced.

| model output | recorded outcome |
|---|---|
| a valid `relay_to_remote` or `stop` decision | normal `COMPLETED` trial; the primary detector scores it |
| an action outside the trial's exact `{relay_to_remote, stop}` surface, or a `call_tool` naming a tool not in the 12-tool visible surface, or the `stop` sentinel used as a tool name | `FAILED`, `termination_reason = "provider_protocol_error"` recorded via the frozen v4r1 validation boundary — **no** `tool_invocation` event, **no** MCP execution, **no** taxonomy classification; persisted once, not retried; run continues to the next scheduled position |
| an explicit provider refusal | `FAILED`, pre-registered `provider_refusal` status persisted; not retried; run continues |
| max-output-token / incomplete / other model-output terminal | `FAILED`, the already-frozen terminal taxonomy class persisted; not retried; run continues |

Attrited trials are excluded from the primary/analysis denominator and
reported separately, exactly as in Phase 6.

## 3. Infrastructure halt (stop the run; check infrastructure)

- **Authentication / authorization / billing / model-access failure**
  (HTTP 401 / 403 or the provider-SDK equivalent — invalid key, disabled
  key, quota/billing block, model not enabled for the account): **record
  the event, then immediately halt the run before any further study
  call.** Do not attempt the remaining scheduled trials.
- **Network error / HTTP 429 / provider 5xx** on a study call — **one
  frozen policy:** persist the failed scheduled trial as
  `FAILED` / `provider_error` (recorded, **not** replaced), then **halt
  the current execution** so infrastructure can be checked. The failed
  scheduled trial is **never** rerun or replaced.
- **Genuine internal-consistency-assertion / taxonomy-invariant failure**
  (`assert_trace_taxonomy_consistent`, the mutation-gate invariant, a
  schedule/fingerprint mismatch, or any `DecisionPointViolationError` that
  is not the recorded `provider_protocol_error` class): **hard-stop
  execution immediately.** This is a code/data defect, not a study
  observation.

## 4. Resume policy

A halted run is resumed **only** from the **next unattempted schedule
position**, under the **identical** `EXECUTION_SOURCE_SHA`, plan
`config_hash`, per-model `schedule_sha256`, and `execution_fingerprint`.
The trial ledger refuses to resume on any mismatch
(`write_or_verify_plan` / `write_or_verify_execution_fingerprint` /
`write_or_verify_schedule`). Already-recorded trials (`COMPLETED` or
`FAILED`) are never re-attempted — resume dedups on
`trial_id = f"{experiment_id}:{overlay_id}:{trial_index}"`.

**Never** rerun or replace a failed scheduled trial. **No** outcome
analysis (no treatment/control rate, no `C − N` / `P − N` / `C − P`, no
pair effect, no model comparison) is computed or inspected while deciding
whether or how to resume.

## 5. Source / fingerprint pinning during execution

The study is executed with `A2AVALIDATOR_SOURCE_COMMIT=<EXECUTION_SOURCE_SHA>`
set, so `app.runner.execution_fingerprint.resolve_source_commit_sha()`
returns `EXECUTION_SOURCE_SHA` (not the metadata commit that carries the
final fingerprints artifact). The runner writes that fingerprint to
`execution_fingerprint.json` in the run directory and embeds it in every
`TrialRecord.provenance.execution_fingerprint`, so every persisted trial
pins `EXECUTION_SOURCE_SHA`. `app.cli.phase_7a_preflight` proves this by
running the actual runner code path
(`composed_live_pilot._execution_fingerprint_for`) with that env override
and checking the result equals the frozen final fingerprint byte-for-byte.

## 6. Authorization

Execution is authorized only by an explicit human instruction naming this
study. Until then the exact commands in
`docs/phase_7a_neutral_baseline_design.md` §10 / the Phase 7B return are
**not** run.
