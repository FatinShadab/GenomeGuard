# GenomeGuard — Codegenome Immune System
# Sessions: 0=scaffold | 1=sensor | 2=critic | 3=surgeon | 4=verifier | 5=orchestrator

"""Backward-compatible facade — delegates to focused modules (SRP split).

Module layout:
  - ``utils``    — configuration, paths, filesystem, subprocess env
  - ``watcher``  — SQLite delta polling (Sensor DB layer)
  - ``graph``    — codegenome export and graph compaction
  - ``cli``      — argparse entry and smoke-test loop
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
from genomeguard.utils import load_config, read_changed_file, resolve_genome_db
from genomeguard.watcher import query_graph_delta

__all__ = [
    "MOCK_CRITIC_FIXTURE",
    "build_critic_prompt",
    "compact_graph_context",
    "evaluate_decay_metrics",
    "export_graph_context",
    "load_config",
    "main",
    "parse_critic_response",
    "query_graph_delta",
    "read_changed_file",
    "resolve_genome_db",
    "run_critic_smoke_test",
    "run_sensor_smoke_test",
]

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "sensor":
        main()
    else:
        path = sys.argv[1] if len(sys.argv) > 1 else None
        run_critic_smoke_test(path)
