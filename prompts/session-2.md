Deliverables this session
evaluate_decay_metrics() in genome_guard.py
build_critic_prompt() in genome_guard.py
parse_critic_response() in genome_guard.py
MOCK_CRITIC_FIXTURE path or inline fixture for tests

You are implementing Session 2 (Critic Agent) of GenomeGuard. Build prompt construction and JSON parsing ONLY — use a mock LLM, NOT the real OpenAI API.

CONTEXT:
- Session 1 implemented Sensor helpers: query_graph_delta, export_graph_context, compact_graph_context, read_changed_file.
- The Critic evaluates changed code + compact graph against rules in guard_config.json → `rules` list.
- PRD response schema (strict JSON, no markdown fences):
  ```json
  {
    "decay_detected": true,
    "reason": "...",
    "refactored_code": "..."
  }

TASK: Edit genome_guard.py:

Implement build_critic_prompt(changed_code: str, graph_context: dict, rules: list[str]) -> list[dict]:

Return OpenAI chat messages format: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}].
System prompt must match PRD blueprint (GenomeGuard architect, detect circular deps, deep nesting, SoC violations).
User content: include changed file source, compact graph JSON, and numbered rules.
Enforce "raw JSON only, no markdown" in system prompt.
Implement parse_critic_response(raw: str) -> dict:

json.loads the string.
Validate required keys: decay_detected (bool), reason (str), refactored_code (str).
Strip accidental ```json fences if present.
Raise ValueError with snippet on invalid output.
Implement evaluate_decay_metrics(changed_code, graph_context, config, *, llm_client=None) -> dict:

Build prompt via build_critic_prompt.
Default behavior (no API key): if llm_client is None, load fixture from tests/fixtures/critic_decay_detected.json OR inline mock returning decay_detected=true with a minimally refactored copy of input.
Structure code so Session 7 can inject real OpenAI client without rewriting this function.
Return parsed dict from parse_critic_response.
Create tests/fixtures/critic_decay_detected.json — valid mock API response matching schema (decay_detected: true).

Create tests/fixtures/critic_healthy.json — decay_detected: false, refactored_code: "".

Add if __name__ == "__main__" critic smoke test:

Read a sample .py file path from argv or use a tiny embedded sample string with an obvious SoC violation comment.
Call evaluate_decay_metrics with mock client.
Print parsed JSON.
CONSTRAINTS:

Do NOT import or call openai yet.
Do NOT write patches or modify source files.
Keep evaluate_decay_metrics mock-first; real API is Session 7.
OUTPUT: Confirm new functions + fixture paths + smoke command.