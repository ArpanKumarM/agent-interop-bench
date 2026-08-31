"""Anthropic Messages API seam (Phase 6C).

Provider-neutral helpers for the external-family robustness model
(`claude-sonnet-5`). This module never imports ``anthropic`` at module load;
the client is built lazily via ``build_anthropic_messages_client`` and is
never constructed for a deterministic run, a preflight, or any test.

Mirrors the discipline of ``app.runner.openai_adapter``:

* ``anthropic_sdk_available()`` -- a monkeypatchable "is the optional extra
  importable" seam.
* ``AnthropicMessagesClient`` -- the minimal ``.create(**kwargs)`` Protocol
  a fake can satisfy without importing the real package.
* error sanitisation is delegated to
  ``app.runner.openai_adapter._sanitize_provider_error`` (provider-neutral:
  it only reads ``type(exc).__name__`` / ``status_code`` / ``request_id``
  and a bounded, credential-redacted message excerpt).

No Anthropic-specific decision logic lives here or in the composed engine;
the canonical action semantics are compiled in
``app.runner.host_decision_client.AnthropicHostDecisionClient`` and parsed
back through the SAME post-parse path OpenAI uses
(``app.runner.real_host_adapter.build_host_action_spec``).
"""

from __future__ import annotations

import importlib.util
from typing import Any, Protocol

# Re-exported so callers have one sanitiser regardless of provider.
from app.runner.openai_adapter import _sanitize_provider_error

__all__ = [
    "AnthropicMessagesClient",
    "anthropic_sdk_available",
    "build_anthropic_messages_client",
    "_sanitize_provider_error",
]

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 0


def anthropic_sdk_available() -> bool:
    """Whether the optional ``anthropic`` package is importable. A
    monkeypatchable seam so offline tests never depend on whether the extra
    is installed in the environment the suite runs in."""
    return importlib.util.find_spec("anthropic") is not None


class AnthropicMessagesClient(Protocol):
    """The minimal surface of ``anthropic.AsyncAnthropic().messages`` the
    host-decision client needs, as a ``Protocol`` so a fake can be injected
    without importing the real ``anthropic`` package."""

    async def create(self, **kwargs: Any) -> Any: ...


def build_anthropic_messages_client(
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AnthropicMessagesClient:
    """Construct a real ``AsyncAnthropic().messages`` resource.

    Reads ``ANTHROPIC_API_KEY`` from the environment via the SDK's own
    standard behaviour only -- never from a request body, plan file, or
    fixture. Raises a clear error if the optional ``anthropic`` extra is not
    installed. NEVER called for a deterministic run, a preflight, or a test.
    """
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        raise RuntimeError(
            "The 'anthropic' package is not installed. Install the optional "
            "real-model extra to use provider=anthropic: `uv sync --extra anthropic`."
        ) from None

    client = AsyncAnthropic(timeout=timeout_seconds, max_retries=max_retries)
    return client.messages
