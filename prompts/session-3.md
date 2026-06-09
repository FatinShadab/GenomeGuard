
---

## `prompts/session-3.md` — Surgeon Agent

```markdown
Deliverables this session
generate_unified_diff() in genome_guard.py
write_patch_file() in genome_guard.py
apply_enforce_write() in genome_guard.py
run_surgeon() orchestration helper in genome_guard.py

You are implementing Session 3 (Surgeon Agent) of GenomeGuard. Handle patch generation and enforce-mode writes only — no verifier yet (Session 4), no daemon loop (Session 5).

CONTEXT:
- Critic returns `refactored_code` when decay_detected is true.
- `--mode patch` (default): write reviewable `.patch` to guard_config `patches_dir` (`.genome/patches`).
- `--mode enforce`: overwrite the target source file directly (Verifier will gate this in Session 4).
- Use `difflib.unified_diff` per PRD.

TASK:
Edit `genome_guard.py`:

1. Implement `generate_unified_diff(original: str, refactored: str, filepath: str) -> str`:
   - Split lines with `splitlines(keepends=True)`.
   - Use `difflib.unified_diff` with fromfile/tofile = filepath.
   - Return unified diff as a single string (may be empty if identical).

2. Implement `write_patch_file(patch_text: str, target_path: str, patches_dir: str) -> Path`:
   - Ensure patches_dir exists.
   - Filename: `<stem>_<unix_timestamp>.patch` derived from target_path.
   - Write UTF-8; return Path to patch file.

3. Implement `apply_enforce_write(target_path: str, refactored_code: str) -> None`:
   - Overwrite file with refactored_code (UTF-8).
   - No backup yet (Verifier session adds safety gate).

4. Implement `run_surgeon(critic_result: dict, original_code: str, target_path: str, config: dict) -> dict`:
   - If `not critic_result["decay_detected"]`: return `{"action": "none", "message": "Architecture Healthy"}`.
   - If decay detected:
     - patch mode → generate diff, write patch, return `{"action": "patch", "patch_path": "..."}`.
     - enforce mode → apply_enforce_write, return `{"action": "enforce", "target_path": "..."}`.
   - Read mode from `config["mode"]`.

5. Add `if __name__ == "__main__"` surgeon smoke test:
   - Use mock critic result + sample original/refactored strings.
   - Run both modes to temp paths under `.genome/patches/` and `/tmp` or `tests/tmp/` (create tests/tmp/.gitkeep).

CONSTRAINTS:
- Do not call py_compile yet.
- Do not start polling loop.
- Do not add OpenAI.

OUTPUT: Confirm functions + example patch file path from smoke test.