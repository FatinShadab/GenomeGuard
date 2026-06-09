"""Session 5 orchestrator — wires Sensor → Critic → Verifier → Surgeon."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

from genomeguard.critic import evaluate_decay_metrics
from genomeguard.graph import compact_graph_context, export_graph_context
from genomeguard.utils import normalize_path, read_changed_file, resolve_genome_db
from genomeguard.verifier import verify_and_apply
from genomeguard.watcher import query_graph_delta

logger = logging.getLogger(__name__)

WATCHER_DB_MISSING_MSG = "Run: codegenome analyze . && codegenome evolve ."


def configure_logging() -> None:
    """Configure structured stdout logging at INFO level."""
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _log_pipeline_outcome(changed_path: str, outcome: dict[str, Any]) -> None:
    status = outcome.get("status")
    if status == "healthy":
        logger.info("Architecture Healthy: %s", changed_path)
    elif status == "applied":
        if outcome.get("action") == "patch":
            logger.info("Patch created: %s", outcome.get("patch_path"))
        elif outcome.get("action") == "enforce":
            logger.info("Enforced rewrite: %s", outcome.get("target_path"))
        else:
            logger.info("Applied change: %s", changed_path)
    elif status == "rejected":
        logger.info(
            "Rejected (compile failure): %s — %s",
            changed_path,
            outcome.get("reason", "unknown error"),
        )
    else:
        logger.info("Pipeline outcome for %s: %s", changed_path, outcome)


def _advance_last_seen_mtime(
    db_path: Path,
    delta: dict[str, Any],
    outcome: dict[str, Any],
    changed_path: str,
) -> float:
    """Bump ``last_seen_mtime`` after processing to avoid self-induced poll loops."""
    last_seen = float(delta["db_mtime"])

    if outcome.get("status") == "applied":
        file_path = Path(changed_path)
        if file_path.is_file():
            file_mtime = file_path.stat().st_mtime
            last_seen = max(last_seen, file_mtime)

        while True:
            current_db_mtime = db_path.stat().st_mtime
            last_seen = max(last_seen, current_db_mtime)
            drain = query_graph_delta(db_path, last_seen)
            if drain is None:
                break
            last_seen = float(drain["db_mtime"])

    return last_seen


def process_single_change(
    workspace: Path,
    config: dict,
    changed_path: str,
    *,
    mock_critic: bool = True,
) -> dict[str, Any]:
    """Run the full validation pipeline for a single changed file."""
    workspace = Path(workspace).resolve()
    normalized_path = normalize_path(changed_path)

    changed_code = read_changed_file(normalized_path)
    full_graph = export_graph_context(workspace)
    graph_context = compact_graph_context(full_graph, normalized_path)

    if not mock_critic:
        logger.warning(
            "Real OpenAI critic is not configured yet (Session 7); using mock fixtures."
        )

    critic_result = evaluate_decay_metrics(
        changed_code,
        graph_context,
        config,
        llm_client=None,
    )
    outcome = verify_and_apply(
        critic_result,
        changed_code,
        normalized_path,
        config,
        workspace,
    )
    _log_pipeline_outcome(normalized_path, outcome)
    return outcome


def run_daemon(
    workspace: Path,
    config: dict,
    *,
    mock_critic: bool = True,
    once: bool = False,
) -> int:
    """Poll ``.genome/watcher.db`` and run the agent pipeline on graph deltas."""
    configure_logging()
    workspace = Path(workspace).resolve()
    db_path = resolve_genome_db(workspace)

    if not db_path.is_file():
        print(WATCHER_DB_MISSING_MSG, file=sys.stderr)
        return 1

    poll_interval = config.get("poll_interval_seconds", 2)
    mode = config.get("mode", "patch")
    last_seen_mtime: float | None = None

    logger.info(
        "GenomeGuard daemon started (workspace=%s, mode=%s, poll=%ss)",
        workspace,
        mode,
        poll_interval,
    )

    while True:
        delta = query_graph_delta(db_path, last_seen_mtime)
        if delta is not None:
            changed_path = delta["changed_path"]
            logger.info("Change detected: %s (ts=%s)", changed_path, delta["timestamp"])
            try:
                outcome = process_single_change(
                    workspace,
                    config,
                    changed_path,
                    mock_critic=mock_critic,
                )
                last_seen_mtime = _advance_last_seen_mtime(
                    db_path, delta, outcome, changed_path
                )
            except (OSError, RuntimeError, ValueError) as exc:
                logger.error("Pipeline failed for %s: %s", changed_path, exc)
                last_seen_mtime = float(delta["db_mtime"])

        if once:
            break

        time.sleep(poll_interval)

    return 0
