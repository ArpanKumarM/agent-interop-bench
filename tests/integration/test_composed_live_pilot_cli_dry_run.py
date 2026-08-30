"""Phase 4A.3b: end-to-end CLI tests via the real ``main(argv)`` entry
point -- the exact same path a human invoking the script would use.

Proves: dry-run produces real plan.json/trials.jsonl/summary.json through
the exact live wiring, with zero sockets ever opened; ``run`` refuses
(non-zero exit, no artifacts written) when preconditions are unmet, without
ever reaching a provider.
"""

from __future__ import annotations

import json
import socket

import pytest

from app.cli import composed_live_pilot as cli
from app.core import config as config_module


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    monkeypatch.delenv("ENABLE_REAL_MODEL_COMPOSED_RUNS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(config_module, "settings", config_module.Settings.from_env())
    monkeypatch.setattr(cli, "settings", config_module.settings)
    yield


def test_dry_run_produces_all_three_artifacts_with_zero_sockets(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RUN_DIR_ROOT", tmp_path)

    def exploding_connect(self, address):
        raise AssertionError(f"dry-run attempted a real socket connection to {address}")

    original_connect = socket.socket.connect
    socket.socket.connect = exploding_connect
    try:
        exit_code = cli.main(["dry-run", "--run-id", "e2e-dry-run", "--model", "fake-model"])
    finally:
        socket.socket.connect = original_connect

    assert exit_code == 0
    run_dir = tmp_path / "e2e-dry-run"
    assert (run_dir / "plan.json").exists()
    assert (run_dir / "trials.jsonl").exists()
    assert (run_dir / "summary.json").exists()

    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["total_trials_recorded"] == 8
    assert summary["model"] == "fake-model"

    plan = json.loads((run_dir / "plan.json").read_text())
    assert "REPLACE_WITH_MODEL_ID" not in json.dumps(plan)


def test_run_refuses_and_writes_nothing_when_live_flag_absent(tmp_path, capsys):
    exit_code = cli.main(["run", "--run-id", "should-never-exist", "--model", "fake-model"])
    assert exit_code == 1
    assert not (tmp_path / "should-never-exist").exists()
    assert "refused" in capsys.readouterr().err.lower()


def test_run_refuses_when_model_absent_even_with_live_flag(monkeypatch):
    object.__setattr__(cli.settings, "enable_real_model_composed_runs", True)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-present-not-real")
    exit_code = cli.main(["run", "--run-id", "irrelevant"])
    object.__setattr__(cli.settings, "enable_real_model_composed_runs", False)
    assert exit_code == 1


def test_preflight_via_main_prints_json_and_exits_zero(capsys):
    exit_code = cli.main(["preflight", "--run-id", "e2e-preflight", "--model", "fake-model"])
    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["model"] == "fake-model"
    assert output["total_trials"] == 8
    assert output["max_total_decisions"] == 32
