"""Phase 9 (F3 resolution study) -- RUNNER DRY RUN (no network, no model call).

Proves the Phase 9 runner inputs load and assemble into exactly 1,536
executable trial requests WITHOUT invoking any provider:

* loads the frozen execution schedule;
* loads the 64-scenario fixture panel (records, arms, opaque refs);
* loads the frozen execution parameters (model panel, provider request
  config, policy hash, action schema, task text);
* builds the per-trial request context for every scheduled row;
* asserts it WOULD dispatch 1,536 provider decisions and makes 0.

Constructs NO provider client and imports NO adapter module, so there is
no code path to a network call. Writes nothing. Produces nothing that
resembles a Phase 9 result.

Run:  uv run python scripts/phase_9_runner_dryrun.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from mock_servers.phase_9_fixtures import (  # noqa: E402
    PHASE_9_F3_TASK_TEXT,
    phase_9_canary_token,
    phase_9_fields,
    phase_9_record_body,
    phase_9_record_ref,
)

_SCHEDULE_PATH = _ROOT / "docs" / "phase_9_design" / "phase_9_execution_schedule.json"
_PARAMS_PATH = _ROOT / "docs" / "phase_9_design" / "phase_9_execution_params.json"


def _provider_for(model: str) -> str:
    return "anthropic" if model.startswith("claude-") else "openai"


def build_trial_requests() -> list[dict]:
    """One request context per scheduled row -- exactly what the runner
    would hand its provider adapter. No adapter is constructed."""
    schedule = json.loads(_SCHEDULE_PATH.read_text())
    params = json.loads(_PARAMS_PATH.read_text())
    allowed_actions = tuple(params["allowed_actions"])
    host_policy_sha = params["host_policy"]["host_policy_sha256"]
    per_model_cfg_sha = params["provider_config_sha256"]

    requests: list[dict] = []
    for model, rows in schedule["per_model_schedule"].items():
        for r in rows:
            sid, arm = r["scenario_id"], r["arm"]
            fields = phase_9_fields(sid)
            record_body = phase_9_record_body(arm, sid)
            # sanity: the opaque ref in the schedule matches the fixture
            if r["record_ref"] != phase_9_record_ref(sid, arm):
                raise RuntimeError(f"record_ref mismatch for {r['trial_id']}")
            requests.append(
                {
                    "trial_id": r["trial_id"],
                    "model": model,
                    "provider": _provider_for(model),
                    "provider_config_sha256": per_model_cfg_sha[model],
                    "framing_id": r["framing_id"],
                    "sink": r["sink"],
                    "task_text": PHASE_9_F3_TASK_TEXT,
                    "allowed_actions": list(allowed_actions),
                    "host_policy_sha256": host_policy_sha,
                    "local_tool_name": "get_account_record",
                    "local_tool_arguments": {"record_ref": r["record_ref"]},
                    "served_record_len": len(record_body),
                    "canary_token": phase_9_canary_token(sid),
                    "scored_values": [
                        fields.full_name,
                        fields.email,
                        fields.phone,
                        fields.account_id,
                        fields.internal_note,
                        fields.credential_token,
                    ],
                    "would_dispatch_provider_decisions": 1,
                }
            )
    return requests


def main() -> int:
    requests = build_trial_requests()

    planned = sum(r["would_dispatch_provider_decisions"] for r in requests)
    executed = 0  # this script constructs no client and makes no call

    problems: list[str] = []
    if len(requests) != 1536:
        problems.append(f"assembled {len(requests)} trial requests, expected 1536")
    if planned != 1536:
        problems.append(f"planned provider decisions = {planned}, expected 1536")
    if len({r["trial_id"] for r in requests}) != len(requests):
        problems.append("duplicate trial_id in assembled requests")
    if {r["provider"] for r in requests} != {"openai", "anthropic"}:
        problems.append("unexpected provider set")
    for r in requests:
        if not r["served_record_len"] or not all(r["scored_values"]):
            problems.append(f"empty served record / scored value for {r['trial_id']}")
            break

    if problems:
        print("PHASE 9 DRY RUN FAILED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    by_model: dict[str, int] = {}
    for r in requests:
        by_model[r["model"]] = by_model.get(r["model"], 0) + 1

    print("PHASE 9 RUNNER DRY RUN -- no provider client constructed, no network call")
    print(f"  trial requests assembled : {len(requests)}")
    for model in sorted(by_model):
        print(f"    {model:16s} {by_model[model]}")
    print(f"  PLANNED provider decisions : {planned}")
    print(f"  EXECUTED provider calls    : {executed}")
    print("  RESULT: would execute exactly 1,536 trials; made 0 API calls; wrote nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
