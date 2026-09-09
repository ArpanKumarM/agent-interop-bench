"""Load-bearing manuscript assertion (paper/main_v2.md S5.3, Appendix A):
the two Phase 8 pilot rounds used DISJOINT four-record sets, so the
round-one-to-round-two difference is confounded and only within-round
contrasts are matched.

This test mechanically proves, and will fail if future code makes them
overlap:

  * round one (F1-F3, record set A) and round two (F4-F6, record set B)
    are disjoint by scenario identifier;
  * their scored record bodies (the six substantive field values) are not
    accidentally identical between any set-A and set-B record;
  * the four identifiers in each set are exactly the four named in the
    manuscript and in the frozen design/result docs.
"""

from __future__ import annotations

from app.reporting import phase_8_frozen_grid as grid
from mock_servers.phase_8_fixtures import PHASE_8_PILOT_ONLY_RECORDS, phase_8_fields

# The four identifiers per round, exactly as written in paper/main_v2.md
# (S5.3 "The two rounds used disjoint record sets" + Table 1 caption +
# Appendix A) and in the frozen docs.
MANUSCRIPT_SET_A = {
    "healthcare-billing",
    "logistics-shipment",
    "insurance-claims",
    "ad-platform-advertiser",
}
MANUSCRIPT_SET_B = {
    "pilotonly-vehicle-service",
    "pilotonly-subscription-mgmt",
    "pilotonly-benefits-inquiry",
    "pilotonly-loyalty-rewards",
}

_SCORED_FIELDS = (
    "full_name",
    "email",
    "phone",
    "account_id",
    "internal_note",
    "credential_token",
)


def _value_tuple(scenario: str) -> tuple[str, ...]:
    f = phase_8_fields(scenario)
    return tuple(getattr(f, name) for name in _SCORED_FIELDS)


def test_frozen_grid_round_sets_match_the_manuscript_identifiers():
    assert set(grid.ROUND_ONE_PILOT_RECORDS) == MANUSCRIPT_SET_A
    assert set(grid.ROUND_TWO_PILOT_RECORDS) == MANUSCRIPT_SET_B
    assert len(grid.ROUND_ONE_PILOT_RECORDS) == 4
    assert len(grid.ROUND_TWO_PILOT_RECORDS) == 4
    # round two's set is exactly the pilot-only fixture record set
    assert set(grid.ROUND_TWO_PILOT_RECORDS) == set(PHASE_8_PILOT_ONLY_RECORDS)


def test_round_one_and_round_two_record_sets_are_disjoint_by_identifier():
    a = set(grid.ROUND_ONE_PILOT_RECORDS)
    b = set(grid.ROUND_TWO_PILOT_RECORDS)
    assert a.isdisjoint(b), f"round-one and round-two pilot records overlap: {a & b}"


def test_round_one_and_round_two_record_bodies_are_not_accidentally_identical():
    a_values = {s: _value_tuple(s) for s in grid.ROUND_ONE_PILOT_RECORDS}
    b_values = {s: _value_tuple(s) for s in grid.ROUND_TWO_PILOT_RECORDS}

    # every record has a full, non-empty six-value tuple
    for scenario, values in {**a_values, **b_values}.items():
        assert len(values) == 6 and all(values), f"{scenario}: incomplete scored fields"

    # no set-A record shares its scored field-value tuple with any set-B record
    for sa, va in a_values.items():
        for sb, vb in b_values.items():
            assert va != vb, f"set-A {sa} and set-B {sb} have identical scored record bodies"

    # and no single scored value is shared across the round boundary
    a_flat = {v for values in a_values.values() for v in values}
    b_flat = {v for values in b_values.values() for v in values}
    assert a_flat.isdisjoint(b_flat), (
        f"scored value(s) shared between round-one and round-two records: {a_flat & b_flat}"
    )
