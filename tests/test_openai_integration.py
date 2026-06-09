"""Live OpenAI integration tests (skipped without credentials)."""

from __future__ import annotations

import pytest

from genomeguard.critic import evaluate_decay_metrics
from genomeguard.utils import ensure_openai_api_key_in_env, has_openai_api_key

pytestmark = pytest.mark.integration

_SOC_VIOLATION_SAMPLE = """\
# SOC VIOLATION: business logic and DB access inside route handler
from infrastructure.database import query_users


def handle_request(request):
    users = query_users()
    return {"users": users}
"""

_GRAPH_CONTEXT = {
    "file": "sample_route.py",
    "upstream": [],
    "downstream": [{"id": "infrastructure.database.query_users", "relation": "imports"}],
}

_CONFIG = {
    "openai_model": "gpt-4o",
    "rules": [
        "Route handlers must not call database layers directly.",
        "Separate business logic from infrastructure concerns.",
    ],
}


def _live_openai_credentials_available() -> bool:
    """True when env or TUI encrypted storage provides an API key."""
    ensure_openai_api_key_in_env()
    return has_openai_api_key()


@pytest.mark.skipif(
    not _live_openai_credentials_available(),
    reason=(
        "No OpenAI credentials — set OPENAI_API_KEY or save a key via "
        "genome-guard tui (API Key tab)."
    ),
)
def test_live_openai_critic_parses_structured_response() -> None:
    """Single small SoC violation sample; asserts parseable critic JSON."""
    ensure_openai_api_key_in_env()
    result = evaluate_decay_metrics(
        _SOC_VIOLATION_SAMPLE,
        _GRAPH_CONTEXT,
        _CONFIG,
        mock=False,
    )

    assert isinstance(result["decay_detected"], bool)
    assert isinstance(result["reason"], str)
    assert result["reason"].strip()
    assert isinstance(result["refactored_code"], str)
