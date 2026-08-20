from app.core.baseline_policy import (
    BASELINE_POLICY_SHA256,
    BASELINE_POLICY_TEXT,
    BASELINE_POLICY_VERSION,
)


def test_policy_version_is_the_expected_frozen_tag():
    assert BASELINE_POLICY_VERSION == "real-model-baseline-v1"


def test_policy_text_is_nonempty_and_provider_neutral():
    assert len(BASELINE_POLICY_TEXT) > 0
    lowered = BASELINE_POLICY_TEXT.lower()
    for provider_name in ("openai", "gpt", "anthropic", "claude"):
        assert provider_name not in lowered


def test_policy_hash_matches_the_exact_text():
    import hashlib

    assert (
        hashlib.sha256(BASELINE_POLICY_TEXT.encode("utf-8")).hexdigest() == BASELINE_POLICY_SHA256
    )
    assert len(BASELINE_POLICY_SHA256) == 64
