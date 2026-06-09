"""CLI entry point and sensor smoke-test loop."""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from genomeguard.graph import compact_graph_context, export_graph_context
from genomeguard.utils import load_config, read_changed_file, resolve_genome_db
from genomeguard.watcher import query_graph_delta

logger = logging.getLogger(__name__)


def run_sensor_smoke_test(workspace: Path) -> None:
    """Poll the watcher DB and print change previews (manual Session 1 test)."""
    config = load_config(str(workspace / "guard_config.json"))
    poll_interval = config.get("poll_interval_seconds", 2)
    db_path = resolve_genome_db(workspace)
    last_seen_mtime: float | None = None

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("Sensor smoke test polling %s every %ss", db_path, poll_interval)

    while True:
        delta = query_graph_delta(db_path, last_seen_mtime)
        if delta is None:
            time.sleep(poll_interval)
            continue

        last_seen_mtime = delta["db_mtime"]
        changed_path = delta["changed_path"]
        logger.info("Change detected: %s (ts=%s)", changed_path, delta["timestamp"])

        try:
            content = read_changed_file(changed_path)
            preview = content[:200].replace("\n", "\\n")
            print(f"changed_path={changed_path}")
            print(f"preview={preview!r}")

            full_graph = export_graph_context(workspace)
            compact = compact_graph_context(full_graph, changed_path)
            print(f"compact_graph_keys={list(compact.keys())}")
        except (OSError, RuntimeError, json.JSONDecodeError) as exc:
            logger.error("Sensor handling failed for %s: %s", changed_path, exc)

        time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="GenomeGuard sensor smoke test")
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root containing .genome/watcher.db (default: .)",
    )
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    run_sensor_smoke_test(workspace)
