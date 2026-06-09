Deliverables this session
pyproject.toml (PEP 621, package name genome-guard)
src/genomeguard/ package split from genome_guard.py
README.md update
tests/ full suite (mock LLM only)
.github/workflows or local pytest instructions in README
You are implementing Session 6 of GenomeGuard: production packaging and automated tests. Do NOT wire the real OpenAI API yet — all LLM calls remain mocked.
CONTEXT:
- PRD PyPI layout:
  src/genomeguard/{__init__.py, cli.py, core.py, utils.py}
  Entry point: genome-guard → genomeguard.cli:main
- Sessions 1–5 built logic in genome_guard.py — refactor without behavior change.
- Hackathon docs: AGENTS.md, skills.md already exist at repo root.
TASK:
1. Create `pyproject.toml`:
   - name: `genome-guard`
   - requires-python: `>=3.12`
   - dependencies: `openai>=1.0.0`, `codegenome`
   - [project.scripts] `genome-guard = "genomeguard.cli:main"`
   - build-backend: hatchling or setuptools
2. Split modules (move code, don't rewrite logic):
   - `utils.py`: load_config, subprocess helpers, execute_compilation_check, generate_unified_diff, sqlite helpers
   - `core.py`: Sensor/Critic/Surgeon/Verifier orchestration (query_graph_delta, evaluate_decay_metrics, verify_and_apply, run_daemon)
   - `cli.py`: argparse + main()
   - `__init__.py`: `__version__ = "0.1.0"`
3. Keep root `genome_guard.py` as thin shim:
   ```python
   from genomeguard.cli import main
   if __name__ == "__main__":
       main()
Expand tests (all mock, no network):

tests/test_sensor.py — compact_graph_context subset size
tests/test_critic_parser.py — parse_critic_response valid/invalid/m markdown fence
tests/test_surgeon.py — patch file created, enforce write
tests/test_verifier.py — (from Session 4, update imports)
tests/test_orchestrator.py — (from Session 5, update imports)
tests/test_pipeline_integration.py:
End-to-end with mocked query_graph_delta + mocked evaluate_decay_metrics
Assert .patch file appears in tmp .genome/patches/
Update README.md:

Install: pip install -e .
Prereq: codegenome analyze . then codegenome evolve .
Run: genome-guard --workspace .
Note: "OpenAI integration enabled in final setup step (Session 7)"
Update skills.md only if function signatures moved (add module paths).

CONSTRAINTS:

No OPENAI_API_KEY required for pytest.
Do not implement real OpenAI client yet.
Keep MIT LICENSE at root.
OUTPUT: Confirm package install command + pytest pass count.