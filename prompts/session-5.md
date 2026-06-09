Deliverables this session
argparse CLI in genome_guard.py
run_daemon() main orchestration loop
Full pipeline wiring: Sensor → Critic (mock) → Verifier → Surgeon
Logging to stdout
You are implementing Session 5 (Orchestrator) of GenomeGuard. Wire all four agents into a headless polling daemon with CLI flags. Still use mock Critic (real OpenAI is Session 7).
CONTEXT:
- Sensor: query_graph_delta, export_graph_context, compact_graph_context, read_changed_file.
- Critic: evaluate_decay_metrics (mock by default).
- Verifier: verify_and_apply.
- Workflow per PRD:
  [DB change] → extract file + graph → critic → verify → patch OR enforce → log.
TASK:
Edit `genome_guard.py`:
1. Add argparse CLI (replace/extend existing `__main__`):
genome-guard / python genome_guard.py [options] --workspace PATH Project root (default: cwd) --config PATH guard_config.json path (default: workspace/guard_config.json) --mode {patch,enforce} Override config mode --once Process single poll cycle then exit (for debugging) --mock-critic Force mock LLM (default True until Session 7)

2. Implement `run_daemon(workspace, config, *, mock_critic=True)`:
- Validate `.genome/watcher.db` exists; if not, print:
  `Run: codegenome analyze . && codegenome evolve .`
  and exit code 1.
- Track `last_seen_mtime`.
- Loop every `poll_interval_seconds`:
  - delta = query_graph_delta(...)
  - if delta: read file, export + compact graph, evaluate_decay_metrics (mock), verify_and_apply, log outcome.
- On healthy: log `Architecture Healthy: <path>`.
- On patch: log patch path.
- On rejected: log compile failure reason.
3. Implement `process_single_change(workspace, config, changed_path, mock_critic=True)` for `--once` and testing.
4. Add structured logging (stdlib `logging`, INFO level).
5. Create `tests/test_orchestrator.py`:
- Use tmp_path fixture: fake watcher.db mtime bump simulation OR mock query_graph_delta.
- Mock evaluate_decay_metrics to return healthy fixture.
- Assert verify_and_apply not called for healthy path OR patch created for decay path.
- No API key.
CONSTRAINTS:
- Do not add OpenAI API key or real client yet.
- Do not refactor into src/ package yet (Session 6).
- Keep all logic in genome_guard.py for now.
OUTPUT: Confirm CLI flags + example:
`python genome_guard.py --workspace . --once --mock-critic`