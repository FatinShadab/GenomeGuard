"""Critic Agent (Architect) — prompt construction, mock LLM, and JSON parsing."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

from genomeguard.utils import create_openai_client, load_config

MOCK_CRITIC_FIXTURE = "critic_decay_detected.json"
MOCK_CRITIC_HEALTHY_FIXTURE = "critic_healthy.json"

_REQUIRED_RESPONSE_KEYS = ("decay_detected", "reason", "refactored_code")
_FENCE_PATTERN = re.compile(
    r"^\s*```(?:json|text)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)

CRITIC_SYSTEM_PROMPT = """\
You are GenomeGuard, an elite autonomous software architect.
You are analyzing a modified file alongside its codebase graph context.
Your task is to detect architectural decay:
1. Circular dependencies.
2. Deep nesting / High cyclomatic complexity.
3. Separation of Concerns violations (e.g., mixing business logic with infrastructure/UI).

CRITICAL: Your response must be in valid JSON format matching this schema:
{
  "decay_detected": true/false,
  "reason": "Clear, concise explanation of the design violation",
  "refactored_code": "The complete, fixed file content string here"
}
Do not wrap the JSON output in markdown blocks (like ```json). Return raw stringified JSON text only.\
"""


def _fixture_dir() -> Path:
    """Resolve tests/fixtures relative to the repository root."""
    package_dir = Path(__file__).resolve().parent
    return package_dir.parent.parent / "tests" / "fixtures"


def _load_fixture_text(name: str) -> str:
    path = _fixture_dir() / name
    if not path.is_file():
        raise FileNotFoundError(f"Mock critic fixture not found: {path}")
    return path.read_text(encoding="utf-8")


def build_critic_prompt(
    changed_code: str,
    graph_context: dict,
    rules: list[str],
) -> list[dict[str, str]]:
    """Build OpenAI chat messages for the Critic (Architect) persona."""
    numbered_rules = "\n".join(f"{index}. {rule}" for index, rule in enumerate(rules, start=1))
    graph_json = json.dumps(graph_context, indent=2, sort_keys=True)
    user_content = (
        "## Changed file source\n"
        f"```python\n{changed_code}\n```\n\n"
        "## Compact graph context (JSON)\n"
        f"{graph_json}\n\n"
        "## Architectural rules\n"
        f"{numbered_rules if numbered_rules else '(no rules configured)'}"
    )
    return [
        {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _strip_markdown_fences(raw: str) -> str:
    text = raw.strip()
    match = _FENCE_PATTERN.match(text)
    if match:
        return match.group(1).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def parse_critic_response(raw: str) -> dict[str, Any]:
    """Parse and validate the Critic LLM JSON response."""
    cleaned = _strip_markdown_fences(raw)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        snippet = cleaned[:200]
        raise ValueError(
            f"Invalid critic JSON response ({exc}); snippet: {snippet!r}"
        ) from exc

    if not isinstance(payload, dict):
        snippet = cleaned[:200]
        raise ValueError(
            f"Critic response must be a JSON object; snippet: {snippet!r}"
        )

    missing = [key for key in _REQUIRED_RESPONSE_KEYS if key not in payload]
    if missing:
        snippet = cleaned[:200]
        raise ValueError(
            f"Critic response missing required keys {missing}; snippet: {snippet!r}"
        )

    decay_detected = payload["decay_detected"]
    reason = payload["reason"]
    refactored_code = payload["refactored_code"]

    if not isinstance(decay_detected, bool):
        raise ValueError(
            f"'decay_detected' must be bool, got {type(decay_detected).__name__}"
        )
    if not isinstance(reason, str):
        raise ValueError(f"'reason' must be str, got {type(reason).__name__}")
    if not isinstance(refactored_code, str):
        raise ValueError(
            f"'refactored_code' must be str, got {type(refactored_code).__name__}"
        )

    return {
        "decay_detected": decay_detected,
        "reason": reason,
        "refactored_code": refactored_code,
    }


def _load_mock_critic_response(changed_code: str) -> str:
    """Load the default decay-detected mock fixture (no network)."""
    try:
        return _load_fixture_text(MOCK_CRITIC_FIXTURE)
    except FileNotFoundError:
        inline = {
            "decay_detected": True,
            "reason": "Mock inline fallback: separation of concerns violation detected.",
            "refactored_code": changed_code.replace(
                "# SOC VIOLATION", "# refactored: logic delegated to service layer"
            ),
        }
        return json.dumps(inline)


def _invoke_openai_chat(
    client: Any,
    messages: list[dict[str, str]],
    config: dict,
) -> str:
    """Call OpenAI chat completions and return assistant text content."""
    model = config.get("openai_model", "gpt-4o")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
        )
    except Exception as exc:
        raise RuntimeError(
            "OpenAI API request failed. Verify OPENAI_API_KEY, network access, "
            f"and that model {model!r} is available for your account. "
            f"Details: {type(exc).__name__}: {exc}"
        ) from exc

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise RuntimeError(
            "OpenAI API returned an unexpected response shape; no assistant content found."
        ) from exc

    if not content or not str(content).strip():
        raise RuntimeError("OpenAI API returned empty assistant content.")

    return str(content)


def evaluate_decay_metrics(
    changed_code: str,
    graph_context: dict,
    config: dict,
    *,
    llm_client: Callable[[list[dict[str, str]]], str] | Any | None = None,
    mock: bool = True,
) -> dict[str, Any]:
    """Run Critic analysis; uses mock fixtures when ``mock=True``."""
    rules = config.get("rules", [])
    messages = build_critic_prompt(changed_code, graph_context, rules)

    if mock:
        raw = _load_mock_critic_response(changed_code)
    elif llm_client is not None and hasattr(llm_client, "chat"):
        raw = _invoke_openai_chat(llm_client, messages, config)
    elif llm_client is not None:
        raw = llm_client(messages)
    else:
        client = create_openai_client()
        raw = _invoke_openai_chat(client, messages, config)

    return parse_critic_response(raw)


_SOC_VIOLATION_SAMPLE = """\
# SOC VIOLATION: business logic and DB access inside route handler
from infrastructure.database import query_users


def handle_request(request):
    users = query_users()
    return {"users": users}
"""


def run_critic_smoke_test(sample_path: str | None = None) -> None:
    """Local smoke test for the Critic Agent using mock fixtures."""
    if sample_path:
        changed_code = Path(sample_path).read_text(encoding="utf-8")
    else:
        changed_code = _SOC_VIOLATION_SAMPLE

    graph_context = {
        "file": sample_path or "sample_route.py",
        "upstream": [],
        "downstream": [{"id": "infrastructure.database.query_users", "relation": "imports"}],
    }
    config = load_config()
    result = evaluate_decay_metrics(changed_code, graph_context, config)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    run_critic_smoke_test(sys.argv[1] if len(sys.argv) > 1 else None)
