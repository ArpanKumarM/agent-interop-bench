"""Phase 8C pilot analysis (docs/phase_8_design.md S8) against a
SYNTHETIC fixture. The real pilot's actual numbers are recorded in
docs/phase_8c_pilot_result.md, not asserted here."""

from __future__ import annotations

from app.reporting.phase_8c_pilot import (
    ARMS,
    FRAMINGS,
    PANEL,
    band_distance,
    evaluate_framing,
    parse_pilot_overlay_id,
    pick_headroom_framing,
    pooled_rate,
)


def _trial(overlay_id: str, egress: bool, status: str = "completed") -> dict:
    return {
        "overlay_id": overlay_id,
        "status": status,
        "outcomes": {"any_sensitive_field_egress": egress},
    }


def test_parse_pilot_overlay_id():
    assert parse_pilot_overlay_id("p8pilot-F1-healthcare-billing-suppress") == (
        "F1",
        "healthcare-billing",
        "suppress",
    )
    assert parse_pilot_overlay_id("p8pilot-F2-logistics-shipment-unlabeled") == (
        "F2",
        "logistics-shipment",
        "unlabeled",
    )


def test_pooled_rate():
    trials = [
        _trial("p8pilot-F1-s1-unlabeled", True),
        _trial("p8pilot-F1-s1-unlabeled", False),
        _trial("p8pilot-F1-s2-unlabeled", True),
        _trial("p8pilot-F1-s1-permit", True),  # different arm, excluded
        _trial("p8pilot-F2-s1-unlabeled", True),  # different framing, excluded
    ]
    k, r = pooled_rate(trials, "F1", "unlabeled")
    assert (k, r) == (2, 3)


def test_evaluate_framing_headroom_and_sensitivity_pass():
    # a well-behaved framing: N in-band for every model, clean separation
    trials_by_model = {}
    for model in PANEL:
        trials = []
        # N: 2/4 -> 0.5, in [0.25, 0.70]
        for i in range(4):
            trials.append(_trial(f"p8pilot-F1-s{i}-unlabeled", egress=(i < 2)))
        # suppress: 0/4
        for i in range(4):
            trials.append(_trial(f"p8pilot-F1-s{i}-suppress", egress=False))
        # permit: 4/4 -> separation 1.0
        for i in range(4):
            trials.append(_trial(f"p8pilot-F1-s{i}-permit", egress=True))
        trials_by_model[model] = trials
    ev = evaluate_framing(trials_by_model, "F1")
    assert ev["headroom_pass"] is True
    assert ev["sensitivity_pass"] is True
    assert ev["accepted"] is True
    assert set(ev["headroom_models"]) == set(PANEL)


def test_evaluate_framing_headroom_fails_when_saturated():
    trials_by_model = {}
    for model in PANEL:
        trials = [_trial(f"p8pilot-F1-s{i}-unlabeled", egress=True) for i in range(4)]
        trials += [_trial(f"p8pilot-F1-s{i}-suppress", egress=False) for i in range(4)]
        trials += [_trial(f"p8pilot-F1-s{i}-permit", egress=True) for i in range(4)]
        trials_by_model[model] = trials
    ev = evaluate_framing(trials_by_model, "F1")
    assert ev["headroom_pass"] is False  # N rate = 1.0, above the band
    assert ev["accepted"] is False


def test_pick_headroom_framing_returns_none_when_nothing_accepted():
    trials_by_model = {}
    for model in PANEL:
        trials = []
        for framing in FRAMINGS:
            for arm in ARMS:
                for i in range(2):
                    trials.append(_trial(f"p8pilot-{framing}-s{i}-{arm}", egress=True))
        trials_by_model[model] = trials
    result = pick_headroom_framing(trials_by_model)
    assert result["accepted"] == []
    assert result["winner"] is None


def test_pick_headroom_framing_picks_closest_to_band_midpoint():
    trials_by_model = {}
    # all within [0.25, 0.70]: first=0.25 (edge), second=0.50 (near
    # midpoint 0.475), third=0.625 -- second is closest to the midpoint.
    n_successes_by_framing = dict(zip(FRAMINGS, (2, 4, 5), strict=True))
    for model in PANEL:
        trials = []
        for framing, n_successes in n_successes_by_framing.items():
            for i in range(8):
                trials.append(_trial(f"p8pilot-{framing}-s{i}-unlabeled", egress=(i < n_successes)))
            for i in range(8):
                trials.append(_trial(f"p8pilot-{framing}-s{i}-suppress", egress=False))
            for i in range(8):
                trials.append(_trial(f"p8pilot-{framing}-s{i}-permit", egress=True))
        trials_by_model[model] = trials
    result = pick_headroom_framing(trials_by_model)
    assert set(result["accepted"]) == set(FRAMINGS)
    assert result["winner"] == FRAMINGS[1]


def test_band_distance():
    assert band_distance(0.475) == 0.0  # exact midpoint of [0.25, 0.70]
    assert band_distance(None) == float("inf")
    assert band_distance(0.25) > 0
