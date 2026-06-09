"""GenomeGuard — Codegenome Immune System."""

from genomeguard.critic import (
    build_critic_prompt,
    evaluate_decay_metrics,
    parse_critic_response,
)
from genomeguard.graph import compact_graph_context, export_graph_context
from genomeguard.surgeon import (
    apply_enforce_write,
    generate_unified_diff,
    run_surgeon,
    write_patch_file,
)
from genomeguard.verifier import execute_compilation_check, verify_and_apply
from genomeguard.orchestrator import configure_logging, process_single_change, run_daemon
from genomeguard.utils import load_config, read_changed_file, resolve_genome_db
from genomeguard.watcher import query_graph_delta

__version__ = "0.1.0"

__all__ = [
    "apply_enforce_write",
    "build_critic_prompt",
    "compact_graph_context",
    "configure_logging",
    "evaluate_decay_metrics",
    "execute_compilation_check",
    "export_graph_context",
    "generate_unified_diff",
    "load_config",
    "parse_critic_response",
    "process_single_change",
    "query_graph_delta",
    "read_changed_file",
    "resolve_genome_db",
    "run_daemon",
    "run_surgeon",
    "verify_and_apply",
    "write_patch_file",
]
