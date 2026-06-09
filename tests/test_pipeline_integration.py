"""End-to-end pipeline integration tests (fully mocked, offline)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from genomeguard.core import process_single_change, run_daemon

SAMPLE_SOURCE = (
    "from infrastructure.database import query_users\n\n\n"
    "def handle_request(request):\n"
    "    users = query_users()\n"
    "    return {'users': users}\n"
)

REFACTORED = (
    "from services.user_service import list_users\n\n\n"
    "def handle_request(request):\n"
    "    return {'users': list_users()}\n"
)

MINIMAL_GRAPH = {"nodes": [], "edges": []}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    genome_dir = tmp_path / ".genome"
    patches_dir = genome_dir / "patches"
    patches_dir.mkdir(parents=True)
    (genome_dir / "watcher.db").write_bytes(b"")
    (genome_dir / "graph.json").write_text(
        json.dumps(MINIMAL_GRAPH), encoding="utf-8"
    )
    (tmp_path / "guard_config.json").write_text(
        json.dumps(
            {
                "mode": "patch",
                "patches_dir": str(patches_dir),
                "temp_file": "temp_genome_check.py",
                "poll_interval_seconds": 0.01,
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def _write_target(workspace: Path, rel_path: str = "sample_route.py") -> str:
    target = workspace / rel_path
    target.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return str(target.resolve())


@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
def test_pipeline_integration_writes_patch_file(
    mock_export: pytest.Mock,
    workspace: Path,
) -> None:
    changed_path = _write_target(workspace)
    config = json.loads((workspace / "guard_config.json").read_text(encoding="utf-8"))

    outcome = process_single_change(workspace, config, changed_path, mock_critic=True)

    assert outcome["status"] == "applied"
    assert outcome["action"] == "patch"
    patches_dir = workspace / ".genome" / "patches"
    patch_files = list(patches_dir.glob("*.patch"))
    assert len(patch_files) == 1
    patch_text = patch_files[0].read_text(encoding="utf-8")
    assert "list_users" in patch_text or "user_service" in patch_text
    mock_export.assert_called_once()


@patch("genomeguard.core.time.sleep")
@patch("genomeguard.core.query_graph_delta")
@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
def test_daemon_integration_end_to_end(
    mock_export: pytest.Mock,
    mock_delta: pytest.Mock,
    mock_sleep: pytest.Mock,
    workspace: Path,
) -> None:
    changed_path = _write_target(workspace)
    config = json.loads((workspace / "guard_config.json").read_text(encoding="utf-8"))
    mock_delta.side_effect = [
        {"changed_path": changed_path, "timestamp": 1.0, "db_mtime": 10.0},
        None,
    ]

    exit_code = run_daemon(workspace, config, mock_critic=True, once=True)

    assert exit_code == 0
    patch_files = list((workspace / ".genome" / "patches").glob("*.patch"))
    assert len(patch_files) == 1


@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
@patch("genomeguard.core.evaluate_decay_metrics")
def test_pipeline_healthy_skips_patch(
    mock_evaluate: pytest.Mock,
    mock_export: pytest.Mock,
    workspace: Path,
) -> None:
    mock_evaluate.return_value = {
        "decay_detected": False,
        "reason": "No violations.",
        "refactored_code": "",
    }
    changed_path = _write_target(workspace)
    config = json.loads((workspace / "guard_config.json").read_text(encoding="utf-8"))

    outcome = process_single_change(workspace, config, changed_path, mock_critic=True)

    assert outcome["status"] == "healthy"
    assert not list((workspace / ".genome" / "patches").glob("*.patch"))
