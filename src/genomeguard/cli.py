"""CLI entry point and orchestrator daemon."""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from genomeguard.graph import compact_graph_context, export_graph_context
from genomeguard.orchestrator import configure_logging, run_daemon
from genomeguard.utils import load_config, read_changed_file, resolve_genome_db
from genomeguard.watcher import query_graph_delta

logger = logging.getLogger(__name__)


def run_sensor_smoke_test(workspace: Path) -> None:
    """Poll the watcher DB and print change previews (manual Session 1 test)."""
    configure_logging()
    config = load_config(str(workspace / "guard_config.json"))
    poll_interval = config.get("poll_interval_seconds", 2)
    db_path = resolve_genome_db(workspace)
    last_seen_mtime: float | None = None

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GenomeGuard — codegenome immune system orchestrator",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Project root containing .genome/watcher.db (default: current directory)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to guard_config.json (default: <workspace>/guard_config.json)",
    )
    parser.add_argument(
        "--mode",
        choices=("patch", "enforce"),
        default=None,
        help="Override config mode: patch (write .patch files) or enforce (direct rewrite)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll cycle then exit (debug / CI)",
    )
    parser.add_argument(
        "--mock-critic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use mock LLM critic fixtures (default: enabled until Session 7)",
    )
    parser.add_argument(
        "legacy_command",
        nargs="?",
        default=None,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.legacy_command == "sensor":
        workspace = Path(args.workspace).resolve()
        run_sensor_smoke_test(workspace)
        return

    workspace = Path(args.workspace).resolve()
    config_path = (
        Path(args.config).resolve()
        if args.config
        else workspace / "guard_config.json"
    )
    config = load_config(str(config_path))
    if args.mode is not None:
        config["mode"] = args.mode

    exit_code = run_daemon(
        workspace,
        config,
        mock_critic=args.mock_critic,
        once=args.once,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
