"""Phase 6C: the multi-model robustness view analyses each model family as
its OWN block and never pools a headline rate across families.
"""

from __future__ import annotations

from app.models.composed_provenance import ComposedModelRunProvenance
from app.models.trial_ledger import TrialOutcomes, TrialRecord
from app.reporting.pilot_analysis import compute_multimodel_robustness_summary


def _prov(model: str) -> ComposedModelRunProvenance:
    return ComposedModelRunProvenance(
        adapter_type="x",
        provider="anthropic" if model.startswith("claude") else "openai",
        requested_model=model,
        host_policy_sha256="0" * 64,
        tool_schema_sha256="0" * 64,
        configured_timeout_seconds=1.0,
        configured_max_retries=0,
        configured_max_output_tokens=1,
    )


def _rec(model: str, overlay_id: str, condition: str, *, mut_req: bool | None, egress: bool | None):
    return TrialRecord(
        run_id="composed-live-canary-004",
        overlay_id=overlay_id,
        condition=condition,
        trial_index=0,
        trial_id=f"{model}:{overlay_id}:0",
        requested_model=model,
        returned_model=model,
        status="completed",
        decision_count=1,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tokens=0,
        latency_ms_total=0.0,
        provenance=_prov(model),
        events=[],
        termination_reason="completed_normally",
        outcomes=TrialOutcomes(
            mutating_tool_requested=mut_req,
            any_sensitive_field_egress=egress,
        ),
    )


def _records() -> list[TrialRecord]:
    out: list[TrialRecord] = []
    for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5"):
        for pair in ("rollback-orders", "purge-pricing"):
            for _ in range(4):
                out.append(
                    _rec(model, f"rq2-{pair}-adversarial", "treatment", mut_req=True, egress=None)
                )
                out.append(_rec(model, f"rq2-{pair}-benign", "control", mut_req=False, egress=None))
        for pair in ("saas-support",):
            for _ in range(4):
                out.append(
                    _rec(model, f"rq1-{pair}-confidential", "treatment", mut_req=None, egress=True)
                )
                out.append(_rec(model, f"rq1-{pair}-public", "control", mut_req=None, egress=False))
    return out


def test_per_model_blocks_with_no_cross_family_pooling():
    summary = compute_multimodel_robustness_summary(_records())
    assert summary is not None
    assert set(summary["per_model"]) == {
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "claude-sonnet-5",
    }
    assert summary["pooled_across_models"] is None
    assert summary["cross_model_difference"] is None
    assert summary["robustness_block_model"] == "claude-sonnet-5"
    assert summary["no_p_values"] is True
    # each model gets its own pairwise summary with RQ1 + RQ2 blocks
    claude = summary["per_model"]["claude-sonnet-5"]
    assert "adversarial_influence" in claude and "sensitive_egress" in claude
    assert claude["adversarial_influence"]["primary_outcome"] == "mutating_tool_requested"


def test_returns_none_without_phase_6b_overlays():
    plain = [
        _rec("gpt-5.6-sol", "live-influence-treatment", "treatment", mut_req=True, egress=None)
    ]
    assert compute_multimodel_robustness_summary(plain) is None
