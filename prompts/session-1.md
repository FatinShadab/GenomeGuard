Deliverables this session
query_graph_delta() in genome_guard.py
export_graph_context() helper in genome_guard.py
read_changed_file() helper in genome_guard.py

You are implementing Session 1 (Sensor Agent) of GenomeGuard. Build ONLY the sensor layer — do not implement Critic, Surgeon, Verifier, CLI loop, or OpenAI calls.

CONTEXT:
- Session 0 created: guard_config.json, AGENTS.md, skills.md, .genome/patches/, requirements.txt, and an empty genome_guard.py header.
- GenomeGuard polls `.genome/watcher.db` (created by `codegenome analyze .`, updated by `codegenome evolve .`).
- When the DB changes, GenomeGuard must discover which source file changed and harvest graph context via `codegenome export --format json`.
- Poll interval comes from guard_config.json → `poll_interval_seconds` (default 2).

TASK:
Edit `genome_guard.py` and add the Sensor Agent module at the bottom. Use only stdlib + sqlite3 (no openai import yet).

1. Add constants/helpers:
   - `load_config(path="guard_config.json")` → returns parsed dict.
   - `resolve_genome_db(workspace_root: Path) -> Path` → returns `workspace_root / ".genome" / "watcher.db"`.

2. Implement `query_graph_delta(db_path: Path, last_seen_mtime: float | None) -> dict | None`:
   - Poll strategy (implement both, prefer DB signal when available):
     a) Compare `db_path.stat().st_mtime` against `last_seen_mtime`.
     b) If DB exists, open SQLite read-only and inspect tables to find the most recently updated file/resource (explore schema with `PRAGMA table_info` / `SELECT` — codegenome schema may vary; document what you find in a short module docstring).
   - Return `None` if no change detected.
   - On change, return:
     ```python
     {
       "changed_path": "<absolute path str>",
       "timestamp": <float unix mtime or row timestamp>,
       "db_mtime": <float>
     }
     ```

3. Implement `export_graph_context(workspace_root: Path) -> dict`:
   - Run subprocess: `codegenome export --format json` with `cwd=workspace_root`, capture stdout.
   - Parse JSON; on failure raise a clear RuntimeError with stderr attached.
   - Return parsed dict.

4. Implement `compact_graph_context(full_graph: dict, changed_path: str) -> dict`:
   - Extract ONLY the changed node plus immediate upstream/downstream neighbors (imports, dependencies, callers — whatever fields exist in the JSON).
   - If structure is unknown, return `{"target": changed_path, "raw_subset": <best-effort slice>}`.
   - Goal: small payload for later LLM calls (implemented in Session 2).

5. Implement `read_changed_file(changed_path: str) -> str`:
   - Read UTF-8 text; raise FileNotFoundError with clear message if missing.

6. Add `if __name__ == "__main__"` block for manual sensor smoke test ONLY:
   - Accept optional `--workspace` arg (default `.`).
   - Loop: call `query_graph_delta`, on hit print changed path + first 200 chars of file + keys of compacted graph; sleep per config.
   - Do NOT call OpenAI.

CONSTRAINTS:
- Do not modify guard_config.json, AGENTS.md, or skills.md unless you add one line cross-referencing implemented functions.
- No OpenAI, no patch writing, no py_compile yet.
- Handle missing `.genome/watcher.db` gracefully (log warning, keep polling).

OUTPUT: Confirm functions added and the manual test command, e.g. `python genome_guard.py --workspace .`