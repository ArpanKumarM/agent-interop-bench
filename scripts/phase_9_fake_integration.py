"""Phase 9 (F3 resolution study) -- full offline integration exercise of the
REAL execution path with a deterministic fake provider at the network
boundary.

POST-FREEZE EXECUTION-IMPLEMENTATION ADDENDUM (scientific freeze
``32a76bf`` unchanged). Makes ZERO network calls and constructs NO provider
SDK client -- only the same ``app.cli.phase_9_execute.execute_phase_9``
loop the live run uses, with ``build_fake_phase_9_adapter_factory`` swapped
in at the final boundary and the real local MCP mock (subprocess
``mock_servers.composed_tool_mock``) serving the frozen Phase 9 records.

Runs all 1,536 frozen scheduled trials (4 models x 384) into a temporary
directory and asserts:

* 1,536 schedule entries consumed, in exact frozen order, each engine
  trial id exactly once (no skip, no duplicate);
* exactly 1,536 fake provider-boundary calls (one per trial, no retry);
* 384 calls / model; 192 / 192 N vs P per model; 48 / domain / model;
  three repeats / (scenario, arm) cell;
* the provider-bound ``HostDecisionContext`` for every N/P pair differs
  only by the frozen ``"[PUBLIC - OK TO SHARE] "`` prefix;
* action-schema parsing, L0 scoring, provider-metadata capture
  (returned_model + system_fingerprint) and raw-ledger serialization all
  work;
* the journal shows 1,536 COMPLETED, 0 indeterminate.

The temp directory is deleted afterward. Nothing is written under a real
Phase 9 output path.

Run:  uv run python scripts/phase_9_fake_integration.py
      uv run python scripts/phase_9_fake_integration.py --model gpt-5.6-sol   # one model
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.cli.phase_9_execute import (  # noqa: E402
    PHASE_9_MODEL_PANEL,
    build_fake_phase_9_adapter_factory,
    execute_phase_9,
    load_phase_9_plan,
    phase_9_execution_fingerprint,
    resolve_phase_9_overlays,
)
from app.runner.phase_9_schedule_loader import (  # noqa: E402
    engine_trial_id,
    frozen_rows,
    load_phase_9_schedule,
)
from mock_servers.phase_9_fixtures import phase_9_record_body  # noqa: E402


def _run_one_model(model: str, out_root: Path) -> dict:
    run_dir = out_root / f"fakeint-{model}"
    schedule = load_phase_9_schedule(model)
    plan = load_phase_9_plan(model)
    overlays = resolve_phase_9_overlays(plan)
    fp = phase_9_execution_fingerprint(plan, overlays, schedule)

    seen_contexts: list = []
    call_counter = [0]
    factory = build_fake_phase_9_adapter_factory(
        action="stop",
        returned_model=model,  # exact requested id -> no substitution flagged
        system_fingerprint=f"fp_fake_{model}",
        seen_contexts=seen_contexts,
        call_counter=call_counter,
    )
    t0 = time.time()
    summary = asyncio.run(
        execute_phase_9(model, run_dir, adapter_factory=factory, execution_fingerprint=fp)
    )
    dt = time.time() - t0

    records = [
        json.loads(x) for x in (run_dir / "trials.jsonl").read_text().splitlines() if x.strip()
    ]
    attempts = [
        json.loads(x) for x in (run_dir / "attempts.jsonl").read_text().splitlines() if x.strip()
    ]

    problems: list[str] = []
    if len(records) != 384:
        problems.append(f"{model}: {len(records)} records != 384")
    if call_counter[0] != 384:
        problems.append(f"{model}: {call_counter[0]} fake provider calls != 384")
    if summary["trial_status_counts"].get("completed") != 384:
        problems.append(f"{model}: completed != 384: {summary['trial_status_counts']}")
    if summary["journal_state_counts"].get("COMPLETED") != 384:
        problems.append(f"{model}: journal COMPLETED != 384")
    if any(a["event"] == "ATTEMPT_STARTED" for a in attempts) is False:
        problems.append(f"{model}: no ATTEMPT_STARTED lines")

    # frozen order + one-each + no dup
    got_order = [r["trial_id"] for r in records]
    exp_order = [
        engine_trial_id(f"{row['scenario_id']}-{row['arm']}", row["block_index"])
        for row in frozen_rows(model)
    ]
    if got_order != exp_order:
        problems.append(f"{model}: recorded order != frozen schedule order")
    if len(set(got_order)) != 384:
        problems.append(f"{model}: duplicate engine trial id in ledger")
    if [r["decision_count"] for r in records] != [1] * 384:
        problems.append(f"{model}: some trial made != 1 provider decision")

    # per-arm / per-domain / repeats balance from the frozen rows
    rows = frozen_rows(model)
    by_arm: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    cells: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        by_arm[row["arm"]] = by_arm.get(row["arm"], 0) + 1
        by_domain[row["domain"]] = by_domain.get(row["domain"], 0) + 1
        cells.setdefault((row["scenario_id"], row["arm"]), []).append(row["repeat"])
    if set(by_arm.values()) != {192}:
        problems.append(f"{model}: N/P not 192/192: {by_arm}")
    # per model: 8 scenarios/domain x 2 arms x 3 repeats = 48
    if set(by_domain.values()) != {48}:
        problems.append(f"{model}: per-domain != 48: {by_domain}")
    if any(sorted(v) != [1, 2, 3] for v in cells.values()):
        problems.append(f"{model}: a cell lacks repeats {{1,2,3}}")

    # provider metadata captured
    sf = {
        c.get("provider_system_fingerprint")
        for r in records
        for c in r["provenance"]["provider_calls"]
    }
    rm = {r["returned_model"] for r in records}
    if sf != {f"fp_fake_{model}"}:
        problems.append(f"{model}: system_fingerprint not captured: {sf}")
    if rm != {model}:
        problems.append(f"{model}: returned_model not captured: {rm}")

    # N/P provider-bound invariance: the record text in the captured context
    context_records: dict[tuple[str, str], str] = {}
    for entry, ctx in zip(schedule, seen_contexts, strict=True):
        sid = entry.overlay_id.rsplit("-", 1)[0]
        arm = entry.overlay_id.rsplit("-", 1)[1]
        text = _extract_record_text(ctx)
        if text is None:
            problems.append(
                f"{model}: no record text in provider-bound context for {entry.overlay_id}"
            )
            continue
        context_records[(sid, arm)] = text
    prefix = "[PUBLIC - OK TO SHARE] "
    checked = 0
    for (sid, arm), text in context_records.items():
        if arm != "N":
            continue
        p_text = context_records.get((sid, "P"))
        if p_text is None:
            continue
        checked += 1
        if p_text != prefix + text:
            problems.append(f"{model}: N/P provider-bound invariant broken for {sid}")
        # and it matches the frozen fixture bytes
        if text != phase_9_record_body("N", sid) or p_text != phase_9_record_body("P", sid):
            problems.append(f"{model}: provider-bound record != frozen fixture bytes for {sid}")
    if checked != 64:
        problems.append(f"{model}: only checked {checked}/64 N/P pairs through the path")

    return {
        "model": model,
        "seconds": round(dt, 1),
        "trials": len(records),
        "fake_provider_calls": call_counter[0],
        "np_pairs_checked": checked,
        "problems": problems,
    }


def _extract_record_text(ctx: object) -> str | None:
    """Pull the MCP tool-result record text out of the provider-bound
    HostDecisionContext -- the exact bytes the model would see."""
    for ev in getattr(ctx, "history", None) or []:
        if getattr(ev, "event_type", None) != "mcp_tool_result":
            continue
        payload = getattr(ev, "payload", None)
        if isinstance(payload, dict):
            structured = payload.get("structured_output")
            if isinstance(structured, dict) and isinstance(structured.get("record"), str):
                return structured["record"]
            if isinstance(payload.get("text_output"), str):
                try:
                    return json.loads(payload["text_output"])["record"]
                except (ValueError, KeyError, TypeError):
                    return payload["text_output"]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase_9_fake_integration")
    parser.add_argument("--model", choices=sorted(PHASE_9_MODEL_PANEL), default=None)
    args = parser.parse_args(argv)
    models = [args.model] if args.model else list(PHASE_9_MODEL_PANEL)

    out_root = Path(tempfile.mkdtemp(prefix="phase9-fakeint-"))
    all_problems: list[str] = []
    results = []
    try:
        for model in models:
            r = _run_one_model(model, out_root)
            results.append(r)
            all_problems.extend(r["problems"])
            print(
                f"{model:16s} {r['trials']} trials, {r['fake_provider_calls']} fake calls, "
                f"{r['np_pairs_checked']}/64 N/P pairs OK, {r['seconds']}s"
                + ("" if not r["problems"] else f"  <-- {len(r['problems'])} PROBLEM(S)")
            )
    finally:
        shutil.rmtree(out_root, ignore_errors=True)

    total_calls = sum(r["fake_provider_calls"] for r in results)
    total_trials = sum(r["trials"] for r in results)
    print()
    print(f"total scheduled/consumed : {total_trials}")
    print(f"total fake provider calls: {total_calls}")
    print("real provider calls      : 0")
    if all_problems:
        print(f"\nFAILED ({len(all_problems)} problem(s)):")
        for p in all_problems:
            print(f"  - {p}")
        return 1
    print("\nPHASE 9 FAKE-PROVIDER INTEGRATION: PASS  (no network, temp dir removed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
