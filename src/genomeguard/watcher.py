"""Watcher database access — detects graph deltas from `.genome/watcher.db`.

Codegenome watcher schema (observed):
  - ``snapshots``: snapshot_id, created_at, label, node_count, edge_count
  - ``graph_nodes``: snapshot_id, node_id, attrs_json (file metadata incl. absolute_path, last_seen, mtime)
  - ``graph_edges``: snapshot_id, source_id, target_id, attrs_json

The most recently touched file node in the latest snapshot is selected via max ``last_seen``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from genomeguard.utils import normalize_path, open_db_readonly

logger = logging.getLogger(__name__)


def _latest_changed_resource(db_path: Path) -> tuple[str, float] | None:
    """Return (absolute_path, timestamp) for the newest file node in the latest snapshot."""
    conn = open_db_readonly(db_path)
    try:
        row = conn.execute(
            """
            SELECT snapshot_id, created_at
            FROM snapshots
            ORDER BY snapshot_id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None

        snapshot_id, snapshot_created_at = row
        rows = conn.execute(
            """
            SELECT node_id, attrs_json
            FROM graph_nodes
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchall()

        best_path: str | None = None
        best_ts = float("-inf")

        for node_id, attrs_json in rows:
            if not node_id.startswith("file:"):
                continue
            try:
                attrs = json.loads(attrs_json)
            except json.JSONDecodeError:
                continue

            ts = attrs.get("last_seen") or attrs.get("mtime") or snapshot_created_at
            try:
                ts_value = float(ts)
            except (TypeError, ValueError):
                continue

            if ts_value <= best_ts:
                continue

            raw_path = attrs.get("absolute_path") or attrs.get("file_path") or node_id.removeprefix("file:")
            if not raw_path:
                continue

            best_ts = ts_value
            best_path = normalize_path(raw_path)

        if best_path is None:
            return None
        return best_path, best_ts
    finally:
        conn.close()


def query_graph_delta(db_path: Path, last_seen_mtime: float | None) -> dict | None:
    """Detect watcher DB changes and return the most recently updated resource."""
    if not db_path.is_file():
        logger.warning("Watcher database not found at %s; continuing poll loop.", db_path)
        return None

    db_mtime = db_path.stat().st_mtime
    if last_seen_mtime is not None and db_mtime <= last_seen_mtime:
        return None

    resource = _latest_changed_resource(db_path)
    if resource is None:
        return None

    changed_path, timestamp = resource
    return {
        "changed_path": normalize_path(changed_path),
        "timestamp": timestamp,
        "db_mtime": db_mtime,
    }
