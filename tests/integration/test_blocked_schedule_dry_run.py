"""Phase 4B kickoff: one end-to-end (offline, no provider) proof that a v3
dry-run persists the complete 80-trial blocked schedule before execution,
dispatches trials in that exact order, and folds the schedule hash into the
execution fingerprint. Uses the built-in dry-run stub adapter -- zero
sockets, zero provider calls.
"""

from __future__ import annotations

import json
import socket
from collections import Counter

import pytest

from app.cli import composed_live_pilot as cli
from app.runner.blocked_schedule import build_model_schedule, schedule_sha256


@pytest.fixture(autouse=True)
def _no_sockets():
    def boom(self, address):
        raise AssertionError(f"v3 dry-run test attempted a real socket to {address}")

    orig = socket.socket.connect
    socket.socket.connect = boom
    try:
        yield
    finally:
        socket.socket.connect = orig


def test_v3_dry_run_persists_and_follows_the_frozen_80_trial_schedule(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RUN_DIR_ROOT", tmp_path)
    rc = cli.main(["dry-run", "--run-id", "v3-sched", "--model", "gpt-5.6-sol", "--plan", "v3"])
    assert rc == 0
    run_dir = tmp_path / "v3-sched"

    sched = build_model_schedule("gpt-5.6-sol")
    expected_sha = schedule_sha256(sched)

    # schedule.json was persisted (before/independent of results)
    persisted = json.loads((run_dir / "schedule.json").read_text())
    assert persisted["schedule_sha256"] == expected_sha
    assert len(persisted["entries"]) == 80

    # execution_fingerprint.json carries the schedule hash
    fp = json.loads((run_dir / "execution_fingerprint.json").read_text())
    assert fp["schedule_sha256"] == expected_sha

    trials = [
        json.loads(line)
        for line in (run_dir / "trials.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(trials) == 80
    assert all(t["status"] == "completed" for t in trials)

    # dispatched in exactly the frozen schedule order
    assert [(t["overlay_id"], t["trial_index"]) for t in trials] == [
        (e.overlay_id, e.trial_index) for e in sched
    ]
    # every 4-trial block holds all four cells exactly once
    for block_start in range(0, 80, 4):
        block = trials[block_start : block_start + 4]
        assert {t["overlay_id"] for t in block} == {
            "live-sensitive-egress-treatment",
            "live-sensitive-egress-control",
            "live-influence-treatment",
            "live-influence-control",
        }
    # exactly 20 observations per cell
    assert Counter(t["overlay_id"] for t in trials) == {
        "live-sensitive-egress-treatment": 20,
        "live-sensitive-egress-control": 20,
        "live-influence-treatment": 20,
        "live-influence-control": 20,
    }
    # every trial's provenance carries the same execution fingerprint
    fp_sha = fp["execution_fingerprint_sha256"]
    assert all(
        t["provenance"]["execution_fingerprint"]["execution_fingerprint_sha256"] == fp_sha
        for t in trials
    )
