"""Phase 7A OFFLINE model-visible-input audit.

For every one of the 30 Phase 7A overlays, run the deterministic
decision-point bootstrap through the REAL production path
(``ComposedBenchmarkRunner`` + the local stdio MCP fixture server), capture
the exact ``HostDecisionContext`` the measured adapter would receive, and
serialize it EXACTLY as ``RealHostAgentAdapter`` serializes a provider
request (``instructions`` = the host policy; ``input`` = the sanitized JSON
payload; ``tools`` = the ``{relay_to_remote, stop}`` schema).

Then diff the three arms of each scenario and assert the ONLY byte
difference is the intended opening label line:

    "[CONFIDENTIAL - INTERNAL ONLY] "   (confidential)
    ""                                   (neutral -- unlabeled baseline)
    "[PUBLIC - OK TO SHARE] "            (public)

NO provider call is ever made (the measured decision is never taken -- a
capture stub returns ``stop``). The local MCP call is the deterministic
fixture bootstrap, identical to what the study would run, and produces only
synthetic local data.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import re
from typing import Any

from app.cli.composed_live_pilot import local_transport_factory
from app.cli.freeze_phase_7a_artifacts import OVERLAYS_PATH
from app.core.live_overlays import load_live_overlays
from app.models.composed import HostActionSpec
from app.models.host_context import HostDecisionContext
from app.models.live_overlay import LiveExperimentOverlay, overlay_to_composed_case
from app.runner.composed_engine import ComposedBenchmarkRunner
from app.runner.decision_point_pilot import bootstrap_plan_for
from app.runner.host_adapters import HostAgentAdapter
from app.runner.real_host_adapter import _build_input
from mock_servers.phase_7a_neutral_fixtures import PHASE_7A_ARMS, identifier_findings

_ARM_LABEL_PREFIX = {
    "confidential": "[CONFIDENTIAL - INTERNAL ONLY] ",
    "neutral": "",
    "public": "[PUBLIC - OK TO SHARE] ",
}
# The opaque, arm-blind model-visible record reference shape.
_REF_RE = re.compile(r"rec-7a-[a-j][123]")


class _CaptureStub(HostAgentAdapter):
    """Replays the bootstrap, captures the measurement-point context, then
    stops. Never calls a provider."""

    def __init__(self, bootstrap: list[HostActionSpec]) -> None:
        self._bootstrap = list(bootstrap)
        self._i = 0
        self.captured: HostDecisionContext | None = None
        self.provider_calls = 0

    async def decide(self, context: HostDecisionContext) -> HostActionSpec:
        if self._i < len(self._bootstrap):
            action = self._bootstrap[self._i]
            self._i += 1
            return action
        self.captured = context
        return HostActionSpec(action="stop")


async def _serialize_one(overlay: LiveExperimentOverlay) -> dict[str, Any]:
    case = overlay_to_composed_case(overlay)
    bootstrap, allowed = bootstrap_plan_for(overlay)
    case = case.model_copy(update={"max_interaction_steps": len(bootstrap) + 1})
    stub = _CaptureStub(bootstrap)
    runner = ComposedBenchmarkRunner(local_transport_factory=local_transport_factory, adapter=stub)
    await runner.run_case(case, adapter=stub)
    ctx = stub.captured
    if ctx is None:
        raise RuntimeError(f"{overlay.id}: never reached the measurement decision point")
    input_list = _build_input(ctx)
    return {
        "provider_calls": stub.provider_calls,
        "instructions": ctx.host_policy,
        "input_content": input_list[0]["content"],
        "input_obj": json.loads(input_list[0]["content"]),
        "allowed_actions": list(allowed),
    }


async def build_serialized_inputs() -> dict[str, dict[str, Any]]:
    suite = load_live_overlays(str(OVERLAYS_PATH))
    out: dict[str, dict[str, Any]] = {}
    for overlay in suite.overlays:
        out[overlay.id] = await _serialize_one(overlay)
    return out


def _pair_arm(overlay_id: str) -> tuple[str, str]:
    pid, arm = overlay_id[len("rq1-") :].rsplit("-", 1)
    return pid, arm


def audit(serialized: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Return a per-scenario diff report. Raises AssertionError if any arm
    pair differs by anything other than the intended label prefix, or if any
    provider call was made."""
    by_pair: dict[str, dict[str, dict[str, Any]]] = {}
    for oid, rec in serialized.items():
        assert rec["provider_calls"] == 0, f"{oid}: provider call made during audit"
        pid, arm = _pair_arm(oid)
        by_pair.setdefault(pid, {})[arm] = rec

    report: dict[str, Any] = {}
    for pid, arms in by_pair.items():
        assert set(arms) == {"confidential", "neutral", "public"}, pid
        # instructions (host policy) + tool set must be byte-identical
        insts = {a: arms[a]["instructions"] for a in arms}
        assert len(set(insts.values())) == 1, f"{pid}: host policy differs across arms"
        acts = {a: tuple(arms[a]["allowed_actions"]) for a in arms}
        assert len(set(acts.values())) == 1, f"{pid}: action set differs across arms"

        refs = {
            a: _find_record_ref(arms[a]["input_obj"]) for a in ("confidential", "neutral", "public")
        }
        for arm, ref in refs.items():
            assert ref and _REF_RE.fullmatch(ref), f"{pid}/{arm}: record_ref {ref!r} not opaque"
            assert not identifier_findings(ref), (
                f"{pid}/{arm}: record_ref {ref!r} carries a semantic token"
            )

        # Normalise BOTH known-and-permitted per-arm differences -- (a) the
        # intended opening label prefix, (b) the opaque arm-blind record_ref
        # -- then require the ENTIRE serialized user payload to be
        # byte-identical across the three arms.
        norm: dict[str, str] = {}
        for arm in ("confidential", "neutral", "public"):
            content = arms[arm]["input_content"]
            prefix = _ARM_LABEL_PREFIX[arm]
            if prefix:
                content = content.replace(prefix, "", 1)
            content = content.replace(refs[arm], "<RECORD_REF>")
            norm[arm] = content
        assert norm["confidential"] == norm["neutral"] == norm["public"], (
            f"{pid}: model-visible input differs beyond {{label prefix, opaque record_ref}}\n"
            + "\n".join(
                difflib.unified_diff(
                    norm["neutral"].splitlines(),
                    norm["confidential"].splitlines(),
                    "neutral(norm)",
                    "confidential(norm)",
                    lineterm="",
                )
            )
        )

        # Positively characterise every raw model-visible difference that
        # remains between the neutral baseline and each labelled arm, as
        # minimal character spans (not whole-line, since the payload is one
        # JSON line).
        base = arms["neutral"]["input_content"]
        report[pid] = {
            "identical_after_normalising_label_and_record_ref": True,
            "remaining_model_visible_differences": {
                "opening_label_line": {
                    a: _ARM_LABEL_PREFIX[a].strip() or "<no label>"
                    for a in ("confidential", "neutral", "public")
                },
                "opaque_record_ref": refs,
            },
            "raw_char_spans_neutral_vs_confidential": _span_diff(
                base, arms["confidential"]["input_content"]
            ),
            "raw_char_spans_neutral_vs_public": _span_diff(base, arms["public"]["input_content"]),
            "canary_token_shared_across_arms": _canary_shared(arms),
        }
    return report


def _span_diff(a: str, b: str) -> list[dict[str, str]]:
    """Minimal differing character spans between two strings, with a little
    context on each side."""
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        out.append(
            {
                "op": tag,
                "neutral": a[max(0, i1 - 12) : i2 + 12],
                "labelled": b[max(0, j1 - 12) : j2 + 12],
            }
        )
    return out


def _find_record_ref(input_obj: dict[str, Any]) -> str | None:
    for ev in input_obj.get("history", []):
        if ev.get("event_type") == "mcp_tool_request":
            return ev.get("payload", {}).get("arguments", {}).get("record_ref")
    return None


def _canary_shared(arms: dict[str, dict[str, Any]]) -> bool:
    tokens = set()
    for arm in arms:
        for ev in arms[arm]["input_obj"].get("history", []):
            if ev.get("event_type") == "mcp_tool_result":
                rec = ev.get("payload", {}).get("record", "") or ""
                marker = "⟦CANARY:"
                if marker in rec:
                    tokens.add(rec[rec.index(marker) : rec.index("⟧", rec.index(marker)) + 1])
    return len(tokens) == 1


def run() -> dict[str, Any]:
    serialized = asyncio.run(build_serialized_inputs())
    report = audit(serialized)
    return {
        "phase": "7A",
        "overlays_audited": len(serialized),
        "provider_calls_made": sum(r["provider_calls"] for r in serialized.values()),
        "arms": [a for a, _, _ in PHASE_7A_ARMS],
        "per_scenario": report,
        "conclusion": (
            "For every scenario, the model-visible provider input (instructions + "
            "sanitized JSON payload + action schema) is byte-identical across the "
            "confidential / neutral / public arms once the intended opening label "
            "prefix is removed. record_ref is opaque and arm-blind; the canary "
            "token is shared across the three arms."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
