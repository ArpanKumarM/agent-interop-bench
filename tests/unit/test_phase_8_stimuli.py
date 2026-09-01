"""Phase 8 stimulus discipline (docs/phase_8_design.md S2, S6;
docs/phase_8_change_list.md S7).

Guards the byte-identity / example-safety / arm-blindness properties the
Phase 8 pre-registration depends on. No provider call, no network.
"""

from __future__ import annotations

import re

from mock_servers.composed_record_fixtures import CONFIDENTIAL_LABEL, PUBLIC_LABEL
from mock_servers.phase_7a_neutral_fixtures import PHASE7A_RECORD_REF_SALT
from mock_servers.phase_8_fixtures import (
    PHASE_8_ARMS,
    PHASE_8_INHERITED_SCENARIOS,
    PHASE_8_LABEL_ARMS,
    PHASE_8_NEW_RECORDS,
    PHASE_8_NEW_SCENARIOS,
    PHASE_8_PILOT_SCENARIOS,
    PHASE_8_RECORD_REF_SALT,
    PHASE_8_SCENARIOS,
    PHASE_8_SINKS,
    all_phase_8_field_values,
    identifier_findings,
    phase_8_canary_key,
    phase_8_canary_token,
    phase_8_fields,
    phase_8_record_body,
    phase_8_record_ref,
    phase_8_ref_lookup,
    phase_8_user_prompt,
    substantive_values,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.example\.invalid$")
_PHONE_RE = re.compile(r"^\+1-555-01\d\d$")
_ACCT_RE = re.compile(r"^ACCT-\d{4}-[A-Z]{4}$")
_TOKEN_RE = re.compile(r"^sk_fixture_EXAMPLE_[0-9a-f]{16}$")
_REF_RE = re.compile(r"^rec-8-[0-9a-f]{8}$")


def test_scenario_counts():
    assert len(PHASE_8_INHERITED_SCENARIOS) == 10
    assert len(PHASE_8_NEW_SCENARIOS) == 14
    assert len(PHASE_8_SCENARIOS) == 24
    assert len(set(PHASE_8_SCENARIOS)) == 24
    # inherited come first, in the frozen Phase 7 order
    assert PHASE_8_SCENARIOS[:10] == PHASE_8_INHERITED_SCENARIOS
    assert set(PHASE_8_PILOT_SCENARIOS) <= set(PHASE_8_SCENARIOS)


def test_arm_and_sink_sets():
    assert PHASE_8_ARMS == (
        "confidential",
        "unlabeled",
        "public",
        "pub_only",
        "ok_only",
        "suppress",
        "permit",
    )
    assert PHASE_8_SINKS == ("a2a_relay", "user_reply")


def test_new_records_are_example_safe_and_unique():
    seen: dict[str, set[str]] = {k: set() for k in ("name", "email", "phone", "acct", "token")}
    for scenario in PHASE_8_SCENARIOS:
        f = phase_8_fields(scenario)
        assert _EMAIL_RE.match(f.email), f"{scenario}: {f.email!r}"
        assert _PHONE_RE.match(f.phone), f"{scenario}: {f.phone!r}"
        assert _ACCT_RE.match(f.account_id), f"{scenario}: {f.account_id!r}"
        assert _TOKEN_RE.match(f.credential_token), f"{scenario}: {f.credential_token!r}"
        assert f.internal_note and not f.internal_note.endswith(" ")
        for key, val in (
            ("name", f.full_name),
            ("email", f.email),
            ("phone", f.phone),
            ("acct", f.account_id),
            ("token", f.credential_token),
        ):
            assert val not in seen[key], f"duplicate {key}: {val!r}"
            seen[key].add(val)


def test_new_records_do_not_collide_with_phase7_values():
    p7 = {
        v
        for s in PHASE_8_INHERITED_SCENARIOS
        for v in substantive_values(phase_8_fields(s)).values()
    }
    for scenario in PHASE_8_NEW_SCENARIOS:
        for v in substantive_values(phase_8_fields(scenario)).values():
            assert v not in p7, f"{scenario}: value reused from Phase 7: {v!r}"


def test_six_substantive_values_byte_identical_across_all_seven_arms():
    for scenario in PHASE_8_SCENARIOS:
        f = phase_8_fields(scenario)
        canary = phase_8_canary_token(scenario)
        want = substantive_values(f)
        for arm in PHASE_8_ARMS:
            body = phase_8_record_body(arm, f, canary)
            for name, value in want.items():
                assert value in body, f"{scenario}/{arm}: missing {name}"
            assert canary in body


def test_labelled_body_is_unlabeled_body_plus_prefix():
    for scenario in PHASE_8_SCENARIOS:
        f = phase_8_fields(scenario)
        canary = phase_8_canary_token(scenario)
        base = phase_8_record_body("unlabeled", f, canary)
        assert phase_8_record_body("suppress", f, canary) == base
        assert phase_8_record_body("permit", f, canary) == base
        cases = {
            "confidential": f"[{CONFIDENTIAL_LABEL}] ",
            "public": f"[{PUBLIC_LABEL}] ",
            "pub_only": "[PUBLIC] ",
            "ok_only": "[OK TO SHARE] ",
        }
        for arm, prefix in cases.items():
            assert phase_8_record_body(arm, f, canary) == prefix + base


def test_record_ref_is_opaque_fixed_shape_and_unique():
    refs = set()
    for scenario in PHASE_8_SCENARIOS:
        for arm in PHASE_8_ARMS:
            ref = phase_8_record_ref(scenario, arm)
            assert _REF_RE.match(ref), ref
            assert identifier_findings(ref) == []
            # opaque: no scenario name, no arm word. The 8-hex body is a
            # pure hash of (salt, scenario, arm) so it encodes no readable
            # ordinal arm position by construction.
            assert scenario not in ref and arm not in ref
            refs.add(ref)
    assert len(refs) == 24 * len(PHASE_8_ARMS)


def test_record_ref_salt_is_distinct_from_phase7():
    assert PHASE_8_RECORD_REF_SALT != PHASE7A_RECORD_REF_SALT
    assert not phase_8_record_ref("saas-support", "unlabeled").startswith("rec-7a-")


def test_ref_lookup_round_trips():
    lut = phase_8_ref_lookup()
    assert len(lut) == 24 * len(PHASE_8_ARMS)
    for scenario in PHASE_8_SCENARIOS:
        for arm in PHASE_8_ARMS:
            assert lut[phase_8_record_ref(scenario, arm)] == (scenario, arm)


def test_shared_canary_key_is_arm_blind():
    for scenario in PHASE_8_SCENARIOS:
        key = phase_8_canary_key(scenario)
        assert identifier_findings(key) == []
        assert phase_8_canary_token(scenario)  # derivable


def test_no_substantive_value_leaks_into_model_visible_prompt_text():
    values = set(all_phase_8_field_values())
    for framing in ("F1", "F2", "F3", "F_terse"):
        sinks = ("a2a_relay",) if framing == "F_terse" else PHASE_8_SINKS
        for sink in sinks:
            for arm in PHASE_8_ARMS:
                prompt = phase_8_user_prompt(framing, sink, arm)
                for v in values:
                    assert v not in prompt


def test_user_prompt_calibration_suffix_only_for_suppress_permit():
    for framing in ("F1", "F2", "F3"):
        for sink in PHASE_8_SINKS:
            bare = phase_8_user_prompt(framing, sink, "unlabeled")
            for arm in ("confidential", "public", "pub_only", "ok_only"):
                assert phase_8_user_prompt(framing, sink, arm) == bare
            assert phase_8_user_prompt(framing, sink, "suppress") != bare
            assert phase_8_user_prompt(framing, sink, "permit") != bare
            assert phase_8_user_prompt(framing, sink, "suppress").startswith(bare)
            assert phase_8_user_prompt(framing, sink, "permit").startswith(bare)


def test_f_terse_is_a2a_only_and_verbatim_phase7():
    from app.cli.freeze_v4_artifacts import _RQ1_USER_PROMPT

    assert phase_8_user_prompt("F_terse", "a2a_relay", "unlabeled") == _RQ1_USER_PROMPT
    for arm in PHASE_8_ARMS:
        try:
            phase_8_user_prompt("F_terse", "user_reply", arm)
        except ValueError:
            continue
        raise AssertionError("F_terse must not be defined for user_reply")


def test_arm_names_never_appear_in_any_prompt():
    for framing in ("F1", "F2", "F3", "F_terse"):
        sinks = ("a2a_relay",) if framing == "F_terse" else PHASE_8_SINKS
        for sink in sinks:
            for arm in PHASE_8_ARMS:
                low = phase_8_user_prompt(framing, sink, arm).lower()
                for word in ("confidential", "unlabeled", "public", "suppress", "permit"):
                    assert word not in low


def test_label_arm_table_shapes():
    for arm, (cond, header, kind) in PHASE_8_LABEL_ARMS.items():
        assert cond in {"treatment", "control", "neutral"}
        assert (header == "") == (arm in {"unlabeled", "suppress", "permit"})
        assert kind in {"none", "suppress", "permit"}
        assert (kind == "none") == (arm not in {"suppress", "permit"})


def test_new_record_dict_key_matches_scenario_list():
    assert tuple(PHASE_8_NEW_RECORDS) == PHASE_8_NEW_SCENARIOS
