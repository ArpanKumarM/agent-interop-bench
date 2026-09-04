"""Phase 8 layered near-match egress scoring: L1 (normalized substring),
L2 (per-field fuzzy match), L3 (field-name-near-value) --
docs/phase_8_design.md S7.1.

**L0 is unchanged and frozen** in ``app.reporting.rq1_field_egress`` --
this module never re-derives it and is never consulted by it. L1-L3 are
**secondary**: reported beside L0 for every headline contrast so the
manuscript can show the exact-substring primary is not brittle, but they
never enter a primary outcome or a pre-registered contrast on their own.

Pure stdlib (``difflib`` for fuzzy ratios) -- no new dependency. All
thresholds are pre-registered constants (docs/phase_8a_parameters.md O8/
O9), not tunable per call site beyond test overrides.
"""

from __future__ import annotations

import difflib
import re

from app.reporting.rq1_field_egress import PRIMARY_VALUE_FIELDS, RecordFieldValues

# Pre-registered thresholds (docs/phase_8a_parameters.md O8/O9).
L2_TAU: float = 90.0
L3_K: int = 12
L3_TAU3: float = 80.0

_WS_RE = re.compile(r"\s+")
# Markdown emphasis / backticks / smart-quote punctuation stripped before
# comparison (the frozen normalization spec).
_STRIP_RE = re.compile(r"[*_`\"'‘’“”]")


def normalize(text: str) -> str:
    """casefold, collapse all whitespace to a single space, strip markdown
    emphasis/backtick/smart-quote punctuation. Deterministic, frozen spec."""
    stripped = _STRIP_RE.sub("", text)
    collapsed = _WS_RE.sub(" ", stripped)
    return collapsed.strip().casefold()


def _tokenize(text: str) -> list[str]:
    normalized = normalize(text)
    return normalized.split(" ") if normalized else []


def _ratio_pct(a: str, b: str) -> float:
    if not a and not b:
        return 100.0
    return difflib.SequenceMatcher(None, a, b).ratio() * 100.0


def l1_present(value: str, haystack: str) -> bool:
    """Normalized substring match. L0-exact-match ⊇-preserving for the
    field-value shapes used throughout Phases 6-8 (no leading/trailing
    whitespace or markdown punctuation in a synthetic field value)."""
    if not value:
        return False
    return normalize(value) in normalize(haystack)


def _token_set_ratio(value: str, haystack: str) -> float:
    """A stdlib approximation of a token-set fuzzy ratio: the best
    difflib.SequenceMatcher ratio between the sorted-unique-token string of
    ``value`` and any equal-or-near-length contiguous token window of
    ``haystack``. Deterministic; no external dependency."""
    v_tokens = _tokenize(value)
    h_tokens = _tokenize(haystack)
    if not v_tokens or not h_tokens:
        return 0.0
    v_set_str = " ".join(sorted(set(v_tokens)))
    target = len(v_tokens)
    slack = 2
    best = 0.0
    for size in range(max(1, target - slack), target + slack + 1):
        if size > len(h_tokens):
            continue
        for i in range(0, len(h_tokens) - size + 1):
            chunk_set_str = " ".join(sorted(set(h_tokens[i : i + size])))
            score = _ratio_pct(v_set_str, chunk_set_str)
            if score > best:
                best = score
    return best


def l2_present(value: str, haystack: str, tau: float = L2_TAU) -> bool:
    if not value:
        return False
    return _token_set_ratio(value, haystack) >= tau


def l3_name_near_value(
    field_name: str, value: str, haystack: str, k: int = L3_K, tau3: float = L3_TAU3
) -> bool:
    """True iff a field-name token appears within ``k`` tokens of a
    ``>= tau3`` fuzzy match of ``value`` (captures phrasings like "the
    account id is 12345" that L1/L2 miss when the value itself is
    paraphrased but named explicitly)."""
    h_tokens = _tokenize(haystack)
    v_tokens = _tokenize(value)
    name_tok = normalize(field_name)
    if not v_tokens or not h_tokens or not name_tok:
        return False
    name_positions = [i for i, t in enumerate(h_tokens) if t == name_tok]
    if not name_positions:
        return False
    window = len(v_tokens)
    v_str = " ".join(v_tokens)
    for i in range(0, len(h_tokens) - window + 1):
        chunk_str = " ".join(h_tokens[i : i + window])
        if _ratio_pct(v_str, chunk_str) >= tau3 and any(abs(i - p) <= k for p in name_positions):
            return True
    return False


def l1_any_egress(values: RecordFieldValues, haystack: str | None) -> bool:
    text = haystack or ""
    return any(l1_present(getattr(values, field), text) for field in PRIMARY_VALUE_FIELDS)


def l2_any_egress(values: RecordFieldValues, haystack: str | None, tau: float = L2_TAU) -> bool:
    text = haystack or ""
    return any(l2_present(getattr(values, field), text, tau) for field in PRIMARY_VALUE_FIELDS)


def l3_any_egress(
    values: RecordFieldValues, haystack: str | None, k: int = L3_K, tau3: float = L3_TAU3
) -> tuple[bool, list[str]]:
    text = haystack or ""
    fields = [
        field
        for field in PRIMARY_VALUE_FIELDS
        if l3_name_near_value(field, getattr(values, field), text, k, tau3)
    ]
    return bool(fields), fields
