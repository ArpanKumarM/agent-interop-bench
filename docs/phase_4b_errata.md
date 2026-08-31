# Phase 4B errata

This note records defects found *after* the Phase 4B study was frozen and
published. **No historical Phase 4B artifact is changed by this document.**
The raw runs under `reports/experiments/composed-live-canary-00{1,2,3}-*`,
the `phase4b-results-v1` git tag and GitHub release, the historical
execution commit, and every committed JSON/JSONL remain byte-for-byte as
published. The corrections here apply to **HEAD going forward** (Phase 6B);
the Phase 4B study stays reproducible from its own tagged history.

## 1. `mutation_action.is_mutating` recording bug

`app/runner/composed_engine.py` (at the Phase 4B execution commit) computed
the *discovered* mutating status of the named tool
(`is_mutating = bool(tool_def and tool_def.is_mutating)`) and used it
correctly for the mutation gate, but then emitted the `mutation_action`
event with **`is_mutating=True` hardcoded** in both the blocked and the
executed branch. The executed branch is only reachable when the gate did
*not* block -- which, because a host can never grant its own approval, means
the named tool was actually discovered **read-only**. Every read-only tool
that a model routed through the `attempt_mutating_tool` wrapper was
therefore recorded on the trace as `is_mutating=True, executed=True`.

Fixed at HEAD: the event now stamps the discovered value, never a hardcode;
and the `attempt_mutating_tool` wrapper is not used at all in Phase 6B (the
action surface is `call_tool` / `stop`, with a single canonical taxonomy in
`app/reporting/composed_taxonomy.py`).

## 2. Old `summary.json` `mutation_executed` semantics

The online summary computed
`mutation_executed = any(event.executed is True for event in mutation_events)`
with **no `is_mutating` filter**
(`app/reporting/pilot_outcomes.py`), so it counted the read-only-via-wrapper
executions of defect 1 as "mutation executed". The frozen
`reports/experiments/composed-live-canary-003-sol-attempt-1/summary.json`
shows the symptom directly:

```json
"experiments" -> "adversarial_influence" -> "control" -> "outcomes" ->
  "mutation_executed": { "n": 12, "successes": 2, "rate": 0.1666... }
```

Those 2 are the `get_deployment_status` calls in the `gpt-5.6-sol` control
cell (Table 5: sol/control `E = 2`, `F = 2`). The derived
`treatment_vs_control.mutation_executed.rate_difference = -0.167` is an
artefact of the same over-count.

## 3. Corrected offline taxonomy is authoritative

`app/reporting/phase_4b_audit.py` (Phase 4B.1) re-derived the mutating
status from a static discovered-annotation table and split the outcomes:

* **actual mutating-tool request** `B = 56`
* **actual mutating-tool request blocked** `C = 56`
* **actual mutating-tool request executed** `D = 0`
* **non-mutating-tool-via-wrapper executed** `F = 26`

`D = 0` (zero actual mutating executions) is the correct Phase 4B figure and
is what `docs/phase_4b_results.md` and the manuscript report. `F = 26` is
the read-only-via-wrapper count that the online summary mislabelled as
mutation executions. The offline rescore
(`app/reporting/decision_point_rescore.py`) has also been routed through the
canonical taxonomy at HEAD; it is **not** re-run against the frozen Phase 4B
artifacts.

## 4. MCP Python SDK version

The manuscript's `paper/references.bib` states "MCP Python SDK (v1.6.0 in
the frozen run environment)". Re-verified from `uv.lock`: the lock pins
**`mcp` version `2.0.0`** at the Phase 4B execution commit, at the
`phase4b-results-v1` release commit, and at HEAD (unchanged since an early
commit), and the code imports the 2.x server API
(`mcp.server.mcpserver.MCPServer`). The correct value is **`mcp==2.0.0`**;
the paper will be corrected in Phase 6C. Phase 6B's execution fingerprint v2
additionally folds `sha256(uv.lock)` and the Python runtime version into the
fingerprint so the environment is auditable from the run artifacts alone.

## 5. Commit roles (execution vs release vs analysis vs manuscript)

The manuscript names one commit as the "experimental source commit"; the
four distinct roles are:

| role | commit | note |
| --- | --- | --- |
| **execution commit** | `77faebcc42daf1192b1141451a2d63ead5d42db6` | recorded as `source_commit_sha` in every frozen `execution_fingerprint.json`; the code + frozen v3 plan + blocked schedule + study-design doc the 240 trials actually ran under |
| **release / tag commit** | `6cb64606a614c42145cc2da03468551c1ca48c6d` | tagged `phase4b-results-v1`; 3 commits after execution (`77faebc -> 46bcddd -> caf036d -> 6cb6460`); identical code/plan/schedule/design plus the frozen result tables |
| **analysis commits** | `46bcddd76afc74a7fffbe7e6ab99a0bf2a2816fc` (outcome-taxonomy audit), `caf036db97b142005e8f12e02fc9b95d0a205cbd` (paper-ready pipeline) | offline only; zero provider calls |
| **manuscript commit** | `67f61bc41303fed42a8d3d9adb00f9903426be19` (`paper/main.md`) then `6bf5ddd` (arXiv v2) | prose |

## 6. Historical raw artifacts intentionally unchanged

None of the above rewrites Phase 4B scientific history. The frozen
`trials.jsonl` / `summary.json` / `execution_fingerprint.json` /
`schedule.json` / `plan.json` files and the `phase4b-results-v1` release are
preserved exactly. Phase 4B is reproduced from that tagged history; HEAD is
the corrected Phase 6B engine.
