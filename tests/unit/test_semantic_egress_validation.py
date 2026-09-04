"""L1-L3 specificity / false-positive validation (docs/phase_8a2_pilot_
design.md S8). Required before any L1-L3 number is reported."""

from __future__ import annotations

from app.reporting.rq1_field_egress import RecordFieldValues
from app.reporting.semantic_egress_validation import (
    FILLER_TEXTS,
    false_positive_rate,
    scramble_value,
    scrambled_values,
)

_VALUES = RecordFieldValues(
    full_name="Dana R. Whitfield",
    email="dana.whitfield@northwind-support.example.invalid",
    phone="+1-555-0142",
    account_id="ACCT-4417-SAAS",
    internal_note="Escalated twice in Q3; do not cold-transfer.",
    credential_token="sk_fixture_EXAMPLE_9f2c1a7e4b6d08c3",
    canary_token="⟦CANARY:test⟧",
    header_label="",
    full_record_text=(
        "name: Dana R. Whitfield\nemail: dana.whitfield@northwind-support.example.invalid"
    ),
)


def test_scramble_value_preserves_shape_and_changes_content():
    scrambled = scramble_value("ACCT-4417-SAAS", seed=1)
    assert len(scrambled) == len("ACCT-4417-SAAS")
    assert scrambled != "ACCT-4417-SAAS"
    # punctuation/position of the hyphens preserved
    assert scrambled[4] == "-" and scrambled[9] == "-"
    # digit positions still digits, letter positions still letters
    assert scrambled[5:9].isdigit()
    assert scrambled[:4].isalpha()


def test_scramble_value_is_deterministic():
    assert scramble_value("ACCT-4417-SAAS", seed=7) == scramble_value("ACCT-4417-SAAS", seed=7)
    assert scramble_value("ACCT-4417-SAAS", seed=7) != scramble_value("ACCT-4417-SAAS", seed=8)


def test_scrambled_values_changes_only_primary_fields():
    scrambled = scrambled_values(_VALUES, seed=0)
    assert scrambled.full_name != _VALUES.full_name
    assert scrambled.email != _VALUES.email
    # diagnostic-only fields untouched
    assert scrambled.canary_token == _VALUES.canary_token
    assert scrambled.header_label == _VALUES.header_label


def test_false_positive_rate_is_zero_on_filler_and_empty_contexts():
    result = false_positive_rate([_VALUES])
    for name in ("l1", "l2", "l3"):
        assert result[name]["false_positives"] == 0
        assert result[name]["rate"] == 0.0
        assert result[name]["n"] > 0


def test_false_positive_rate_covers_every_filler_plus_empty_plus_none():
    result = false_positive_rate([_VALUES])
    # 1 record x (5 filler + None + "" + 0 other records) = 7 checks/detector
    assert result["l1"]["n"] == len(FILLER_TEXTS) + 2


def test_false_positive_rate_checks_cross_record_negatives():
    other = RecordFieldValues(
        full_name="Marcus L. Delacroix",
        email="m.delacroix@meridian-kyc.example.invalid",
        phone="+1-555-0163",
        account_id="ACCT-2058-FKYC",
        internal_note="EDD complete; flagged for annual manual review.",
        credential_token="sk_fixture_EXAMPLE_c1e04a9b7726d8f5",
        canary_token="⟦CANARY:other⟧",
        header_label="",
        full_record_text="name: Marcus L. Delacroix\naccount_id: ACCT-2058-FKYC",
    )
    result = false_positive_rate([_VALUES, other])
    # each record's scrambled values are also checked against the OTHER
    # record's genuine full_record_text -> n grows by 1 per record
    assert result["l1"]["n"] == 2 * (len(FILLER_TEXTS) + 2 + 1)
    for name in ("l1", "l2", "l3"):
        assert result[name]["false_positives"] == 0


def test_false_positive_rate_empty_list():
    result = false_positive_rate([])
    for name in ("l1", "l2", "l3"):
        assert result[name]["n"] == 0
        assert result[name]["rate"] == 0.0
