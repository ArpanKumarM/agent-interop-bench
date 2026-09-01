"""Phase 8 neutral-language audit (docs/phase_8_design.md S6 rule 4).

The ``unlabeled`` / ``suppress`` / ``permit`` record bodies must introduce
no confidentiality / permission / sharing / sensitivity term that is not
already present, byte-identical, in the ``confidential`` and ``public``
bodies of the same scenario (i.e. it may only ride in on the shared
skeleton). The calibration instruction lives in the user prompt, not the
record, so it is out of scope here.
"""

from __future__ import annotations

from mock_servers.phase_8_fixtures import (
    PHASE_8_SCENARIOS,
    neutral_language_findings,
    phase_8_canary_token,
    phase_8_fields,
    phase_8_record_body,
)


def test_baseline_bodies_introduce_no_prohibited_language():
    for scenario in PHASE_8_SCENARIOS:
        f = phase_8_fields(scenario)
        canary = phase_8_canary_token(scenario)
        conf = phase_8_record_body("confidential", f, canary).splitlines()
        pub = phase_8_record_body("public", f, canary).splitlines()
        conf_lines, pub_lines = set(conf), set(pub)
        for arm in ("unlabeled", "suppress", "permit"):
            body = phase_8_record_body(arm, f, canary)
            for ln in body.splitlines():
                hits = neutral_language_findings(ln)
                if hits:
                    assert ln in conf_lines and ln in pub_lines, (
                        f"{scenario}/{arm}: introduces {hits} on new line: {ln!r}"
                    )
            # the first line (no header) must carry no prohibited stem at all
            assert neutral_language_findings(body.splitlines()[0]) == []


def test_wording_ablation_headers_are_the_only_new_first_line_tokens():
    for scenario in PHASE_8_SCENARIOS:
        f = phase_8_fields(scenario)
        canary = phase_8_canary_token(scenario)
        base_first = phase_8_record_body("unlabeled", f, canary).splitlines()[0]
        for arm, marker in (
            ("pub_only", "[PUBLIC] "),
            ("ok_only", "[OK TO SHARE] "),
        ):
            first = phase_8_record_body(arm, f, canary).splitlines()[0]
            assert first == marker + base_first
