"""scripts/phase_9_build_scenarios.py -- the proposed Phase 9 stimulus
panel must stay deterministic and keep passing every invariance / dedup /
disjointness check before it can be frozen.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "phase_9_build_scenarios.py"
_spec = importlib.util.spec_from_file_location("phase_9_build_scenarios", _PATH)
mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = mod
_spec.loader.exec_module(mod)


def test_builds_exactly_64_scenarios_8x8():
    scen = mod.build_scenarios()
    assert len(scen) == 64
    assert mod.DOMAINS_COUNT == 8
    assert mod.SCENARIOS_PER_DOMAIN == 8
    per_domain: dict[str, int] = {}
    for s in scen:
        per_domain[s["domain"]] = per_domain.get(s["domain"], 0) + 1
    assert sorted(per_domain) == sorted(d for d, _ in mod.DOMAINS)
    assert set(per_domain.values()) == {8}


def test_all_checks_pass():
    scen = mod.build_scenarios()
    assert mod.run_checks(scen) == []


def test_deterministic_across_calls():
    a = mod.build_scenarios()
    b = mod.build_scenarios()
    assert [(s["id"], s["n_body"], s["p_body"]) for s in a] == [
        (s["id"], s["n_body"], s["p_body"]) for s in b
    ]


def test_n_and_p_differ_only_by_the_public_label_prefix():
    prefix = f"[{mod.PUBLIC_LABEL}] "
    for s in mod.build_scenarios():
        assert s["p_body"] == prefix + s["n_body"]
        # and nothing else: the two bodies are otherwise byte-identical
        assert s["p_body"][len(prefix) :] == s["n_body"]


def test_f3_task_text_is_the_frozen_phase_8_f3_relay_prompt():
    from mock_servers.phase_8_fixtures import _FRAMING_PROMPTS

    frozen_f3 = _FRAMING_PROMPTS["F3"]["a2a_relay"]
    assert frozen_f3 == mod.F3_TASK_TEXT


def test_disjoint_from_phase_8_scenarios():
    from mock_servers.phase_8_fixtures import (
        PHASE_8_PILOT_SCENARIOS,
        PHASE_8_SCENARIOS,
        phase_8_fields,
    )

    p8: set[str] = set()
    for name in (*PHASE_8_SCENARIOS, *PHASE_8_PILOT_SCENARIOS):
        f = phase_8_fields(name)
        p8.update(
            [f.full_name, f.email, f.phone, f.account_id, f.internal_note, f.credential_token]
        )
    for s in mod.build_scenarios():
        f = s["fields"]
        for v in (
            f.full_name,
            f.email,
            f.phone,
            f.account_id,
            f.internal_note,
            f.credential_token,
        ):
            assert v not in p8
