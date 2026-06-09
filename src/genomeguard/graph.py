"""Graph export and compaction — codegenome export and neighbor extraction."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from genomeguard.utils import (
    copy_process_env,
    normalize_path,
    resolve_codegenome_executable,
)


def export_graph_context(workspace_root: Path) -> dict:
    """Run ``codegenome export --format json`` and return the exported graph dict."""
    result = subprocess.run(
        [resolve_codegenome_executable(), "export", "--format", "json"],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        env=copy_process_env(),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"codegenome export failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    export_candidates = (
        workspace_root / ".genome" / "graph.json",
        workspace_root / ".genome" / "exports" / "graph.json",
    )
    for export_path in export_candidates:
        if export_path.is_file():
            with export_path.open(encoding="utf-8") as handle:
                return json.load(handle)

    raise RuntimeError(
        "codegenome export succeeded but no graph JSON was found under .genome/ "
        f"(stdout: {result.stdout.strip()})"
    )


def _node_matches_path(node: dict[str, Any], changed_path: str) -> bool:
    normalized = normalize_path(changed_path)
    candidates: list[str] = []
    for key in ("absolute_path", "file_path", "path", "id"):
        value = node.get(key)
        if isinstance(value, str) and value:
            candidates.append(value)
            if value.startswith("file:"):
                candidates.append(value.removeprefix("file:"))

    for candidate in candidates:
        try:
            if normalize_path(candidate) == normalized:
                return True
        except (OSError, RuntimeError, ValueError):
            if Path(candidate).as_posix() == Path(changed_path).as_posix():
                return True
    return False


def _resolve_target_id(target_node: dict[str, Any], changed_path: str) -> str:
    target_id = target_node.get("id")
    if isinstance(target_id, str):
        return target_id
    return f"file:{target_node.get('file_path', changed_path)}"


def _partition_neighbors(
    edges: list[Any],
    target_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str], set[str]]:
    upstream_edges: list[dict[str, Any]] = []
    downstream_edges: list[dict[str, Any]] = []
    upstream_ids: set[str] = set()
    downstream_ids: set[str] = set()

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source") or edge.get("source_id")
        target = edge.get("target") or edge.get("target_id")
        if target == target_id:
            upstream_edges.append(edge)
            if isinstance(source, str):
                upstream_ids.add(source)
        if source == target_id:
            downstream_edges.append(edge)
            if isinstance(target, str):
                downstream_ids.add(target)

    return upstream_edges, downstream_edges, upstream_ids, downstream_ids


def compact_graph_context(full_graph: dict, changed_path: str) -> dict:
    """Extract the changed node and its immediate upstream/downstream neighbors."""
    nodes = full_graph.get("nodes")
    edges = full_graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {
            "target": normalize_path(changed_path),
            "raw_subset": full_graph,
        }

    target_node: dict[str, Any] | None = None
    for node in nodes:
        if isinstance(node, dict) and _node_matches_path(node, changed_path):
            target_node = node
            break

    if target_node is None:
        return {
            "target": normalize_path(changed_path),
            "raw_subset": {
                "nodes": nodes[:10],
                "edges": edges[:20],
            },
        }

    target_id = _resolve_target_id(target_node, changed_path)
    upstream_edges, downstream_edges, upstream_ids, downstream_ids = _partition_neighbors(
        edges, target_id
    )

    node_by_id = {
        node.get("id"): node
        for node in nodes
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }

    return {
        "target": normalize_path(changed_path),
        "node": target_node,
        "upstream": {
            "edges": upstream_edges,
            "nodes": [node_by_id[node_id] for node_id in upstream_ids if node_id in node_by_id],
        },
        "downstream": {
            "edges": downstream_edges,
            "nodes": [node_by_id[node_id] for node_id in downstream_ids if node_id in node_by_id],
        },
    }
