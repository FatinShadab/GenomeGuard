"""Live OpenAI integration tests (skipped without OPENAI_API_KEY)."""

from __future__ import annotations

import os

import pytest

from genomeguard.critic import evaluate_decay_metrics

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


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping live OpenAI integration test",
)
def test_live_openai_critic_parses_structured_response() -> None:
    """Single small SoC violation sample; asserts parseable critic JSON."""
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
