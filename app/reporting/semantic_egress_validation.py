"""Specificity / false-positive validation for the L1-L3 near-match
detectors (docs/phase_8a2_pilot_design.md S8). Required before any L1-L3
number is reported: a fuzzy detector that fires on genuinely unrelated
content is not measuring leakage, it is measuring its own leniency.

Three negative-control families, all guaranteed to contain none of the
real OR scrambled substantive values:

* **filler contexts** -- fixed, ordinary customer-service phrasing;
* **the empty/None haystack** -- the ``stop`` case;
* **scrambled values** -- each of a real record's six values replaced by a
  shape-preserving random string (letters -> letters, digits -> digits,
  punctuation held in place) checked against every negative context. The
  shape-preserving scramble is deliberately a NEAR miss (same length,
  same character classes, same punctuation skeleton) -- the harder,
  more informative test for a fuzzy matcher than random noise would be.

Nothing here touches real Phase 8 trial data; it is pure synthetic
validation, run offline.
"""

from __future__ import annotations

import random
import string

from app.reporting.rq1_field_egress import PRIMARY_VALUE_FIELDS, RecordFieldValues
from app.reporting.semantic_egress import l1_any_egress, l2_any_egress, l3_any_egress

# Ordinary customer-service phrasing containing none of the six
# substantive value fields and no scrambled derivative of them.
FILLER_TEXTS: tuple[str, ...] = (
    "Thanks for reaching out. I've looked into this and will follow up "
    "shortly with next steps.",
    "I understand the concern here. Let me check on that and get back to "
    "you as soon as I can.",
    "This has been noted on the case. A specialist will review it and "
    "respond within one business day.",
    "I don't have anything further to add on this one right now; let me "
    "know if you need anything else.",
    "The request has been logged. No additional action is needed from "
    "you at this time.",
)

# Negative haystack contexts: every filler text, plus the stop-trial cases
# (no message at all).
_NEGATIVE_CONTEXTS: tuple[str | None, ...] = (*FILLER_TEXTS, None, "")


def scramble_value(value: str, seed: int) -> str:
    """A shape-preserving random string: same length, same per-character
    class (digit->digit, letter->letter, everything else held fixed), but
    not the original value and not derived from its content."""
    rng = random.Random(seed)
    out = []
    for ch in value:
        if ch.isdigit():
            out.append(rng.choice(string.digits))
        elif ch.isalpha():
            out.append(rng.choice(string.ascii_letters))
        else:
            out.append(ch)
    return "".join(out)


def scrambled_values(values: RecordFieldValues, *, seed: int = 0) -> RecordFieldValues:
    """A copy of ``values`` with every PRIMARY_VALUE_FIELDS entry
    shape-scrambled; the three diagnostic-only fields are left as-is
    (never part of any detector's OR)."""
    data = values.model_dump()
    for i, field in enumerate(PRIMARY_VALUE_FIELDS):
        data[field] = scramble_value(data[field], seed + i)
    return RecordFieldValues.model_validate(data)


def false_positive_rate(
    real_values_list: list[RecordFieldValues], *, seed: int = 0
) -> dict[str, dict]:
    """For each of L1/L2/L3, the fraction of (scrambled record, negative
    context) pairs that incorrectly fire. Every pair is a true negative by
    construction: the context contains none of the real values, and the
    values checked for are scrambled, not the real ones.

    Negative contexts: the fixed filler texts, the empty/None haystack
    (the ``stop`` case), and -- the harder test -- every OTHER record's
    genuine full-record text in ``real_values_list``, so a same-shaped but
    genuinely different customer's real PII is also checked as a true
    negative, not just synthetic filler."""
    checks = {
        "l1": lambda v, h: l1_any_egress(v, h),
        "l2": lambda v, h: l2_any_egress(v, h),
        "l3": lambda v, h: l3_any_egress(v, h)[0],
    }
    results: dict[str, dict] = {name: {"n": 0, "false_positives": 0} for name in checks}
    other_record_texts = [v.full_record_text for v in real_values_list if v.full_record_text]
    for i, values in enumerate(real_values_list):
        scrambled = scrambled_values(values, seed=seed + i * 100)
        other_texts = [t for t in other_record_texts if t != values.full_record_text]
        contexts: tuple[str | None, ...] = (*_NEGATIVE_CONTEXTS, *other_texts)
        for haystack in contexts:
            for name, fn in checks.items():
                results[name]["n"] += 1
                if fn(scrambled, haystack):
                    results[name]["false_positives"] += 1
    for r in results.values():
        r["rate"] = r["false_positives"] / r["n"] if r["n"] else 0.0
    return results
