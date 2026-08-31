# Phase 7B — execution governance (frozen BEFORE any provider call)

**Status: FROZEN. NOT EXECUTED.** This document is the pre-registered
execution contract for the Phase 7 neutral-baseline study. The **rules**
(run IDs, panel, counts, terminal handling, infrastructure halt, resume
policy, invariant hard-stop, no-analysis-during-halt) are frozen together
with the executable source `EXECUTION_SOURCE_SHA`
(`2a892c0b9a8a636055cc0c4229aebfd788738b60`) and may not change. Only
non-normative operational clarifications are permitted afterward as
**metadata-only** commits that touch no executable / config / stimulus /
policy / schedule / fingerprint file — §5 (checkout state) was clarified
this way in Phase 7B.1. No outcome analysis is inspected while any
decision in this document is being made.

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

## 5. Operational checkout state and source / fingerprint pinning

Commits involved:

| role | commit | contents added |
|---|---|---|
| **`EXECUTION_SOURCE_SHA`** — the frozen executable source | `2a892c0b9a8a636055cc0c4229aebfd788738b60` | all code / config / stimuli / policy / schedule |
| **metadata commit** | `2201dda204021629548946f1f913fad026af4c28` | ONLY `benchmarks/composed/live_canary_phase7a_fingerprints.json` (FINAL) |
| **checkout-alignment commit (7B.1)** | `phase-6b-impl` tip `== origin/phase-6b-impl` | ONLY this doc + `phase_7a_neutral_baseline_design.md` (docs) |

Diffs from `EXECUTION_SOURCE_SHA`:

- `git diff 2a892c0..2201dda` — **exactly one file**,
  `benchmarks/composed/live_canary_phase7a_fingerprints.json`, and only
  its `artifact_role` / `final_execution_fingerprint` flag /
  `source_commit_sha` stamp / the four derived
  `execution_fingerprint_sha256` values.
- `git diff 2a892c0..<phase-6b-impl tip>` — that same fingerprints file
  plus `docs/phase_7b_execution_governance.md` and
  `docs/phase_7a_neutral_baseline_design.md`.

**No executable / config / stimulus / policy / schedule byte differs** in
either diff. Every *scientific input hash* in the fingerprints artifact
(`resolved_overlay_bundle_sha256`, `host_policy_sha256`,
`tool_schema_sha256`, `canonical_action_schema_sha256`, per-model
`schedule_sha256` / `provider_config_sha256` / `config_hash`,
`uv_lock_sha256`, `python_runtime_version`) is identical between the
reference and the FINAL artifact — only `source_commit_sha` (and its four
derived fingerprint hashes) changed.

**Operational execution state (preferred):**

- working tree / `HEAD` = the **branch tip** `phase-6b-impl`
  (`== origin/phase-6b-impl`) — any commit at or after the metadata commit
  `2201dda…` carries the FINAL fingerprints artifact
  (`final_execution_fingerprint: true`) on disk for the preflight to
  verify against; the branch tip is the simplest checkout
  (`git checkout phase-6b-impl && git pull --ff-only`);
- `HEAD == origin/phase-6b-impl`, clean working tree;
- environment: `A2AVALIDATOR_SOURCE_COMMIT=2a892c0b9a8a636055cc0c4229aebfd788738b60`
  (the `EXECUTION_SOURCE_SHA`, **not** the metadata or 7B.1 commit).

With that env set,
`app.runner.execution_fingerprint.resolve_source_commit_sha()` returns
`2a892c0b9a8a636055cc0c4229aebfd788738b60`, so the runner computes the
four already-frozen FINAL fingerprints, writes that fingerprint (with
`source_commit_sha = 2a892c0b…`) to `execution_fingerprint.json` in each
run directory, and embeds it in every
`TrialRecord.provenance.execution_fingerprint`. Every persisted trial
therefore pins `EXECUTION_SOURCE_SHA` `2a892c0b…`, never the metadata
commit `2201dda…`.

`app.cli.phase_7a_preflight` proves this offline: it runs the actual
runner code path
(`composed_live_pilot._execution_fingerprint_for`) with exactly that env
override and checks the result equals the frozen FINAL fingerprint
byte-for-byte, with `source_commit_sha == 2a892c0b…`, for all four models
(`runner_records_execution_source_sha = {all four: true}`).

## 6. Authorization

Execution is authorized only by an explicit human instruction naming this
study. Until then the exact commands in
`docs/phase_7a_neutral_baseline_design.md` §10 / the Phase 7B return are
**not** run.
