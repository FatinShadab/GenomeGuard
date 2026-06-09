"""GenomeGuard — Codegenome Immune System."""

from genomeguard.critic import (
    build_critic_prompt,
    evaluate_decay_metrics,
    parse_critic_response,
)
from genomeguard.graph import compact_graph_context, export_graph_context
from genomeguard.utils import load_config, read_changed_file, resolve_genome_db
from genomeguard.watcher import query_graph_delta

__version__ = "0.1.0"

__all__ = [
    "build_critic_prompt",
    "compact_graph_context",
    "evaluate_decay_metrics",
    "export_graph_context",
    "load_config",
    "parse_critic_response",
    "query_graph_delta",
    "read_changed_file",
    "resolve_genome_db",
]
