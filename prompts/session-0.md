Deliverables this session
guard_config.json
AGENTS.md
skills.md
.genome/patches/ (dir)
requirements.txt

You are bootstrapping the GenomeGuard project. Do NOT write any Python logic yet — this session is purely workspace scaffolding.

CONTEXT:
- GenomeGuard is a real-time architectural guardrail that sits on top of the `codegenome` Python package (pip install codegenome).
- codegenome writes a live SQLite database at `.genome/watcher.db` when `codegenome evolve .` runs in watch mode.
- GenomeGuard will poll that database, detect file changes, call an LLM, and either generate a .patch file or overwrite the offending file.

TASK:
Create the following workspace structure inside the project root:

1. `requirements.txt` — list these exact dependencies:
   openai
   codegenome

2. `guard_config.json` — a JSON config file with these keys:
   {
     "poll_interval_seconds": 2,
     "mode": "patch",
     "rules": [
       "No circular dependencies between modules",
       "UI layer must not directly import database or infrastructure modules",
       "Business logic must not be placed inside route handlers or view controllers",
       "No function with cyclomatic complexity above 10"
     ],
     "patches_dir": ".genome/patches",
     "temp_file": "temp_genome_check.py",
     "openai_model": "gpt-4o"
   }

3. `AGENTS.md` — a Markdown file documenting the four internal agent personas:
   - Sensor Agent (Watcher): polls .genome/watcher.db every N seconds, detects file modification timestamps, emits changed file paths.
   - Critic Agent (Architect): receives changed file content + JSON graph context, calls OpenAI gpt-4o, returns structured decay analysis JSON.
   - Surgeon Agent (Refactorer): receives the refactored_code string from Critic, writes or patches the target file.
   - Verifier Agent (Safety Gatekeeper): runs `python -m py_compile` on a temp copy before any write. Discards changes on failure.

4. `skills.md` — a Markdown file listing the four core functions GenomeGuard will implement:
   - `query_graph_delta()` — reads SQLite watcher.db, returns last-modified file path and timestamp.
   - `evaluate_decay_metrics()` — builds OpenAI prompt payload, calls API, parses JSON response.
   - `generate_unified_diff()` — uses difflib.unified_diff to produce a .patch file.
   - `execute_compilation_check()` — subprocess call to py_compile on a temp file.

5. Create the directory `.genome/patches/` (with a `.gitkeep` inside so it is tracked by git).

6. Create an empty `genome_guard.py` file with only this header comment:
   # GenomeGuard — Codegenome Immune System
   # Sessions: 0=scaffold | 1=sensor | 2=critic | 3=surgeon | 4=verifier | 5=orchestrator

Do NOT add any imports or logic to genome_guard.py yet.

OUTPUT: Confirm each file created with its relative path. No other output needed.