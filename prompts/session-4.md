Deliverables this session
execute_compilation_check() in genome_guard.py
verify_and_apply() gatekeeper wrapper in genome_guard.py
Integration of verifier into run_surgeon() flow

You are implementing Session 4 (Verifier Agent) of GenomeGuard. Add the safety gate that blocks bad LLM output before any patch or enforce write is finalized.

CONTEXT:
- PRD: write LLM output to temp shadow file, run `python -m py_compile <temp>`, abandon transformation on failure.
- guard_config.json key: `temp_file` (default `temp_genome_check.py` from Session 0).
- Surgeon (Session 3) currently writes patches/enforce without verification — you must wrap that.

TASK:
Edit `genome_guard.py`:

1. Implement `execute_compilation_check(code: str, temp_filename: str, workspace_root: Path) -> tuple[bool, str]`:
   - Write `code` to `workspace_root / temp_filename` (use guard_config temp_file name).
   - Subprocess: `[sys.executable, "-m", "py_compile", str(temp_path)]`.
   - Capture stderr on failure.
   - Always delete temp file in `finally` block.
   - Return `(True, "")` on success, `(False, error_message)` on failure.

2. Implement `verify_and_apply(critic_result, original_code, target_path, config, workspace_root) -> dict`:
   - If not decay_detected → `{"status": "healthy"}`.
   - If decay_detected:
     a) Run `execute_compilation_check` on `refactored_code`.
     b) On failure → `{"status": "rejected", "reason": "<compile error>"}` — do NOT patch or write.
     c) On success → delegate to `run_surgeon(...)` and return its result with `"status": "applied"`.

3. Update `run_surgeon` docstring to note it should only be called post-verification (or make it private `_run_surgeon`).

4. Create `tests/test_verifier.py` (pytest):
   - `test_compile_check_valid_python` → passes.
   - `test_compile_check_invalid_python` → fails with syntax error.
   - `test_verify_rejects_bad_refactor` → mock critic with `def broken(` code, assert status rejected.
   - No OpenAI, no API key.

5. Add `if __name__ == "__main__"` verifier smoke:
   - Run one valid and one invalid sample through execute_compilation_check, print results.

CONSTRAINTS:
- Use pytest for tests; add `pytest` to requirements.txt if missing.
- Still no OpenAI integration.
- Do not implement full daemon loop yet.

OUTPUT: Confirm functions + `pytest tests/test_verifier.py` command.