## `prompts/session-7.md` — Real OpenAI API + E2E smoke (API key last)
```markdown
Deliverables this session
Real OpenAI client in evaluate_decay_metrics()
.env.example + README API key section
Optional guard_config openai_model override
tests/test_openai_integration.py (skipped without key)
Manual E2E checklist
You are implementing Session 7 (final) of GenomeGuard: wire the real OpenAI API and document end-to-end usage. This is the ONLY session that requires an API key.
CONTEXT:
- evaluate_decay_metrics() was built mock-first in Session 2; CLI has --mock-critic (default was True).
- guard_config.json: `"openai_model": "gpt-4o"`.
- PRD uses structured JSON response from gpt-4o.
TASK:
1. Implement `create_openai_client()` in genomeguard/core.py or utils.py:
   - Read `OPENAI_API_KEY` from environment (os.environ).
   - Use `openai.OpenAI()` SDK (openai>=1.0.0).
   - If key missing and mock_critic=False, raise clear error with setup instructions.
2. Update `evaluate_decay_metrics(..., llm_client=None, mock=False)`:
   - When `mock=False` and `llm_client` provided (or created from env):
     - Call `client.chat.completions.create(model=config["openai_model"], messages=prompt, temperature=0)`.
     - Pass `response.choices[0].message.content` to `parse_critic_response`.
   - When `mock=True`, keep fixture behavior from Session 2.
3. Update CLI:
   - `--mock-critic` default → **False** when `OPENAI_API_KEY` is set, else **True** with warning.
   - Add `--mock-critic` flag to force mock even with key (for cheap local runs).
4. Create `.env.example`:
OPENAI_API_KEY=sk-...

5. Update README.md — "OpenAI Setup" section:
- `export OPENAI_API_KEY=...` (never commit real keys)
- Cost note: only changed files trigger calls
6. Add `tests/test_openai_integration.py`:
- `@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="no key")`
- Single small prompt: obvious SoC violation sample (~20 lines).
- Assert response parses and has decay_detected bool.
- Mark as `@pytest.mark.integration` so default CI can exclude: `pytest -m "not integration"`
7. Manual E2E checklist (print in README or TESTING.md):
- [ ] `pip install -e .` in GenomeGuard repo
- [ ] Create sample project with intentional architecture violation
- [ ] `cd sample && codegenome analyze . && codegenome evolve .` (background terminal)
- [ ] `export OPENAI_API_KEY=...`
- [ ] `genome-guard --workspace . --mode patch`
- [ ] Edit sample file, save, confirm `.genome/patches/*.patch` generated
- [ ] Repeat with `--mode enforce` on throwaway branch only
CONSTRAINTS:
- Never hardcode API keys.
- Do not commit .env files.
- Keep mock path working for token-free development.
OUTPUT: Confirm CLI with real API + skip message for integration test without key.