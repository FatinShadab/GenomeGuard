"""Tests for Sensor Agent graph compaction and path normalization."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from genomeguard.graph import compact_graph_context
from genomeguard.utils import load_config, normalize_path
from genomeguard.watcher import query_graph_delta

LARGE_GRAPH = {
    "nodes": [
        {
            "id": "file:src/routes/api.py",
            "absolute_path": "src/routes/api.py",
            "type": "file",
        },
        {"id": "sym:handle_request", "type": "function"},
        *[{"id": f"sym:extra_{i}", "type": "function"} for i in range(50)],
    ],
    "edges": [
        {"source": "file:src/routes/api.py", "target": "sym:handle_request"},
        *[
            {"source": f"sym:extra_{i}", "target": f"sym:extra_{i + 1}"}
            for i in range(49)
        ],
    ],
}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    target = tmp_path / "src" / "routes" / "api.py"
    target.parent.mkdir(parents=True)
    target.write_text("def handle_request():\n    pass\n", encoding="utf-8")
    return tmp_path


def test_normalize_path_uses_posix(workspace: Path) -> None:
    raw = str(workspace / "src" / "routes" / "api.py")
    normalized = normalize_path(raw)
    assert "\\" not in normalized
    assert normalized.endswith("src/routes/api.py")


def test_compact_graph_context_subset_smaller_than_full_graph(workspace: Path) -> None:
    changed = str((workspace / "src" / "routes" / "api.py").resolve())
    graph = {
        **LARGE_GRAPH,
        "nodes": [
            {
                "id": "file:src/routes/api.py",
                "absolute_path": changed,
                "type": "file",
            },
            *LARGE_GRAPH["nodes"][1:],
        ],
    }
    compact = compact_graph_context(graph, changed)

    full_size = len(json.dumps(graph))
    compact_size = len(json.dumps(compact))
    assert compact_size < full_size
    assert compact["target"] == normalize_path(changed)
    assert "node" in compact
    assert "upstream" in compact
    assert "downstream" in compact


def test_compact_graph_context_fallback_when_node_missing(workspace: Path) -> None:
    changed = str((workspace / "missing.py").resolve())
    compact = compact_graph_context(LARGE_GRAPH, changed)

    assert compact["target"] == normalize_path(changed)
    subset = compact.get("raw_subset", {})
    assert len(subset.get("nodes", [])) <= 10
    assert len(subset.get("edges", [])) <= 20


def test_query_graph_delta_returns_none_when_db_unchanged(tmp_path: Path) -> None:
    db_path = tmp_path / "watcher.db"
    db_path.write_bytes(b"sqlite-placeholder")
    mtime = db_path.stat().st_mtime

    assert query_graph_delta(db_path, mtime) is None


@patch("genomeguard.watcher._latest_changed_resource")
def test_query_graph_delta_detects_change(
    mock_resource: pytest.Mock,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "watcher.db"
    db_path.write_bytes(b"sqlite-placeholder")
    target = str((tmp_path / "sample.py").resolve())
    mock_resource.return_value = (target, 99.0)

    delta = query_graph_delta(db_path, None)

    assert delta is not None
    assert delta["changed_path"] == normalize_path(target)
    assert delta["timestamp"] == 99.0
    assert "db_mtime" in delta


def test_load_config_safe_fallbacks(tmp_path: Path) -> None:
    config = load_config(str(tmp_path / "nonexistent.json"))

    assert config["openai_model"] == "gpt-4o"
    assert config["mode"] == "patch"
    assert config["patches_dir"] == ".genome/patches"
    assert config["poll_interval_seconds"] == 2
