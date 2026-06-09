# GenomeGuard — Codegenome Immune System
# Sessions: 0=scaffold | 1=sensor | 2=critic | 3=surgeon | 4=verifier | 5=orchestrator

"""Backward-compatible facade — delegates to focused modules (SRP split).

Module layout:
  - ``utils``        — configuration, paths, filesystem, subprocess env
  - ``watcher``      — SQLite delta polling (Sensor DB layer)
  - ``graph``        — codegenome export and graph compaction
  - ``critic``       — LLM decay analysis (mock by default)
  - ``surgeon``      — patch generation and enforce-mode writes
  - ``verifier``     — compilation gate before writes
  - ``orchestrator`` — Session 5 daemon loop wiring all agents
  - ``cli``          — argparse entry and smoke-test helpers
"""

from genomeguard.cli import main, run_sensor_smoke_test
from genomeguard.critic import (
    MOCK_CRITIC_FIXTURE,
    build_critic_prompt,
    evaluate_decay_metrics,
    parse_critic_response,
    run_critic_smoke_test,
)
from genomeguard.graph import compact_graph_context, export_graph_context
from genomeguard.orchestrator import (
    configure_logging,
    process_single_change,
    run_daemon,
)
from genomeguard.surgeon import (
    apply_enforce_write,
    generate_unified_diff,
    run_surgeon,
    run_surgeon_smoke_test,
    write_patch_file,
)
from genomeguard.utils import load_config, read_changed_file, resolve_genome_db
from genomeguard.verifier import (
    execute_compilation_check,
    run_verifier_smoke_test,
    verify_and_apply,
)
from genomeguard.watcher import query_graph_delta

__all__ = [
    "MOCK_CRITIC_FIXTURE",
    "apply_enforce_write",
    "build_critic_prompt",
    "compact_graph_context",
    "configure_logging",
    "evaluate_decay_metrics",
    "execute_compilation_check",
    "export_graph_context",
    "generate_unified_diff",
    "load_config",
    "main",
    "parse_critic_response",
    "process_single_change",
    "query_graph_delta",
    "read_changed_file",
    "resolve_genome_db",
    "run_critic_smoke_test",
    "run_daemon",
    "run_sensor_smoke_test",
    "run_surgeon",
    "run_surgeon_smoke_test",
    "run_verifier_smoke_test",
    "verify_and_apply",
    "write_patch_file",
]

if __name__ == "__main__":
    main()
