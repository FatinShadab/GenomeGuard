"""Tests for Session 5 orchestrator pipeline handoffs."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from genomeguard.core import (
    WATCHER_DB_MISSING_MSG,
    process_single_change,
    run_daemon,
)
from genomeguard.utils import normalize_path

HEALTHY_CRITIC = {
    "decay_detected": False,
    "reason": "No architectural violations detected.",
    "refactored_code": "",
}

DECAY_CRITIC = {
    "decay_detected": True,
    "reason": "SOC violation in route handler.",
    "refactored_code": (
        "from services.user_service import list_users\n\n\n"
        "def handle_request(request):\n"
        "    return {'users': list_users()}\n"
    ),
}

SAMPLE_SOURCE = (
    "from infrastructure.database import query_users\n\n\n"
    "def handle_request(request):\n"
    "    users = query_users()\n"
    "    return {'users': users}\n"
)

MINIMAL_GRAPH = {"nodes": [], "edges": []}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    genome_dir = tmp_path / ".genome"
    genome_dir.mkdir()
    (genome_dir / "watcher.db").write_bytes(b"")
    (genome_dir / "graph.json").write_text(
        json.dumps(MINIMAL_GRAPH), encoding="utf-8"
    )
    (tmp_path / "guard_config.json").write_text(
        json.dumps(
            {
                "mode": "patch",
                "patches_dir": str(tmp_path / "patches"),
                "temp_file": "temp_genome_check.py",
                "poll_interval_seconds": 0.01,
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def _write_target(workspace: Path, rel_path: str = "sample.py") -> str:
    target = workspace / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return str(target.resolve())


@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
@patch("genomeguard.core.evaluate_decay_metrics", return_value=HEALTHY_CRITIC)
@patch("genomeguard.core.verify_and_apply")
def test_healthy_path_skips_surgeon(
    mock_verify: MagicMock,
    mock_evaluate: MagicMock,
    mock_export: MagicMock,
    workspace: Path,
) -> None:
    mock_verify.return_value = {"status": "healthy"}
    config = json.loads((workspace / "guard_config.json").read_text(encoding="utf-8"))
    changed_path = _write_target(workspace)

    outcome = process_single_change(workspace, config, changed_path, mock_critic=True)

    assert outcome["status"] == "healthy"
    mock_evaluate.assert_called_once()
    mock_verify.assert_called_once()
    mock_verify.assert_called_with(
        HEALTHY_CRITIC,
        SAMPLE_SOURCE,
        normalize_path(changed_path),
        config,
        workspace,
    )


@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
@patch("genomeguard.core.evaluate_decay_metrics", return_value=DECAY_CRITIC)
@patch("genomeguard.core.verify_and_apply")
def test_decay_path_creates_patch(
    mock_verify: MagicMock,
    mock_evaluate: MagicMock,
    mock_export: MagicMock,
    workspace: Path,
) -> None:
    patch_path = workspace / "patches" / "sample_1.patch"
    mock_verify.return_value = {
        "status": "applied",
        "action": "patch",
        "patch_path": str(patch_path),
    }
    config = json.loads((workspace / "guard_config.json").read_text(encoding="utf-8"))
    changed_path = _write_target(workspace)

    outcome = process_single_change(workspace, config, changed_path, mock_critic=True)

    assert outcome["status"] == "applied"
    assert outcome["action"] == "patch"
    mock_evaluate.assert_called_once()
    mock_verify.assert_called_once()


@patch("genomeguard.core.time.sleep")
@patch("genomeguard.core.query_graph_delta")
def test_run_daemon_once_with_delta(
    mock_delta: MagicMock,
    mock_sleep: MagicMock,
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    changed_path = _write_target(workspace)
    config = json.loads((workspace / "guard_config.json").read_text(encoding="utf-8"))
    mock_delta.side_effect = [
        {"changed_path": changed_path, "timestamp": 1.0, "db_mtime": 10.0},
        None,
    ]

    with patch(
        "genomeguard.core.process_single_change",
        return_value={"status": "healthy"},
    ) as mock_process:
        exit_code = run_daemon(workspace, config, mock_critic=True, once=True)

    assert exit_code == 0
    mock_process.assert_called_once_with(
        workspace, config, changed_path, mock_critic=True
    )
    mock_sleep.assert_not_called()


@patch("genomeguard.core.time.sleep")
@patch("genomeguard.core.query_graph_delta", return_value=None)
def test_run_daemon_once_no_delta(
    mock_delta: MagicMock,
    mock_sleep: MagicMock,
    workspace: Path,
) -> None:
    config = json.loads((workspace / "guard_config.json").read_text(encoding="utf-8"))

    with patch("genomeguard.core.process_single_change") as mock_process:
        exit_code = run_daemon(workspace, config, mock_critic=True, once=True)

    assert exit_code == 0
    mock_process.assert_not_called()
    mock_sleep.assert_not_called()


def test_run_daemon_missing_watcher_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "empty"
    workspace.mkdir()
    config = {"poll_interval_seconds": 1, "mode": "patch"}

    exit_code = run_daemon(workspace, config, mock_critic=True, once=True)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert WATCHER_DB_MISSING_MSG in captured.err


@patch("genomeguard.core.query_graph_delta")
def test_advance_last_seen_drains_self_induced_delta(
    mock_delta: MagicMock,
    workspace: Path,
) -> None:
    """Landmine 2: after apply, drain DB bumps so enforce mode does not loop."""
    changed_path = _write_target(workspace)
    config = json.loads((workspace / "guard_config.json").read_text(encoding="utf-8"))
    config["mode"] = "enforce"

    mock_delta.side_effect = [
        {"changed_path": changed_path, "timestamp": 1.0, "db_mtime": 10.0},
        {"changed_path": changed_path, "timestamp": 2.0, "db_mtime": 11.0},
        None,
        None,
    ]

    with patch(
        "genomeguard.core.process_single_change",
        return_value={"status": "applied", "action": "enforce", "target_path": changed_path},
    ):
        exit_code = run_daemon(workspace, config, mock_critic=True, once=True)

    assert exit_code == 0
    assert mock_delta.call_count >= 2
