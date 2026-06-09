"""End-to-end tests for patch, enforce, healthy, and rejected pipeline modes."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from genomeguard.core import process_single_change, run_daemon
from genomeguard.critic import evaluate_decay_metrics
from genomeguard.verifier import verify_and_apply

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

INVALID_REFACTOR = "def broken(\n"

DECAY_CRITIC = {
    "decay_detected": True,
    "reason": "SOC violation in route handler.",
    "refactored_code": REFACTORED,
}

HEALTHY_CRITIC = {
    "decay_detected": False,
    "reason": "No violations.",
    "refactored_code": "",
}

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
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return str(target.resolve())


def _load_config(workspace: Path) -> dict:
    return json.loads((workspace / "guard_config.json").read_text(encoding="utf-8"))


@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
class TestPatchMode:
    def test_full_pipeline_writes_patch(self, mock_export: MagicMock, workspace: Path) -> None:
        changed_path = _write_target(workspace)
        config = _load_config(workspace)

        outcome = process_single_change(workspace, config, changed_path, mock_critic=True)

        assert outcome["status"] == "applied"
        assert outcome["action"] == "patch"
        assert "patch_path" in outcome
        patch_path = Path(outcome["patch_path"])
        assert patch_path.is_file()
        assert patch_path.suffix == ".patch"
        assert SAMPLE_SOURCE == (workspace / "sample_route.py").read_text(encoding="utf-8")
        mock_export.assert_called_once()

    def test_verify_and_apply_patch_mode(self, mock_export: MagicMock, workspace: Path) -> None:
        target = workspace / "route.py"
        target.write_text(SAMPLE_SOURCE, encoding="utf-8")
        config = _load_config(workspace)

        outcome = verify_and_apply(
            DECAY_CRITIC,
            SAMPLE_SOURCE,
            str(target),
            config,
            workspace,
        )

        assert outcome["status"] == "applied"
        assert outcome["action"] == "patch"
        assert list((workspace / ".genome" / "patches").glob("*.patch"))
        assert target.read_text(encoding="utf-8") == SAMPLE_SOURCE


@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
class TestEnforceMode:
    def test_full_pipeline_overwrites_source(
        self, mock_export: MagicMock, workspace: Path
    ) -> None:
        changed_path = _write_target(workspace)
        config = _load_config(workspace)
        config["mode"] = "enforce"

        outcome = process_single_change(workspace, config, changed_path, mock_critic=True)

        assert outcome["status"] == "applied"
        assert outcome["action"] == "enforce"
        assert Path(changed_path).read_text(encoding="utf-8") == (
            json.loads(
                (Path(__file__).parent / "fixtures" / "critic_decay_detected.json").read_text(
                    encoding="utf-8"
                )
            )["refactored_code"]
        )
        assert not list((workspace / ".genome" / "patches").glob("*.patch"))

    def test_verify_and_apply_enforce_mode(self, mock_export: MagicMock, workspace: Path) -> None:
        target = workspace / "route.py"
        target.write_text(SAMPLE_SOURCE, encoding="utf-8")
        config = _load_config(workspace)
        config["mode"] = "enforce"

        outcome = verify_and_apply(
            DECAY_CRITIC,
            SAMPLE_SOURCE,
            str(target),
            config,
            workspace,
        )

        assert outcome["status"] == "applied"
        assert outcome["action"] == "enforce"
        assert target.read_text(encoding="utf-8") == REFACTORED
        assert not list((workspace / ".genome" / "patches").glob("*.patch"))


@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
class TestHealthyMode:
    @patch("genomeguard.core.evaluate_decay_metrics", return_value=HEALTHY_CRITIC)
    def test_skips_surgeon(
        self, mock_evaluate: MagicMock, mock_export: MagicMock, workspace: Path
    ) -> None:
        changed_path = _write_target(workspace)
        config = _load_config(workspace)

        outcome = process_single_change(workspace, config, changed_path, mock_critic=True)

        assert outcome["status"] == "healthy"
        assert not list((workspace / ".genome" / "patches").glob("*.patch"))
        mock_evaluate.assert_called_once()


@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
class TestRejectedMode:
    @patch(
        "genomeguard.core.evaluate_decay_metrics",
        return_value={
            "decay_detected": True,
            "reason": "Bad refactor from critic.",
            "refactored_code": INVALID_REFACTOR,
        },
    )
    def test_rejects_invalid_refactor(
        self, mock_evaluate: MagicMock, mock_export: MagicMock, workspace: Path
    ) -> None:
        changed_path = _write_target(workspace)
        config = _load_config(workspace)

        outcome = process_single_change(workspace, config, changed_path, mock_critic=True)

        assert outcome["status"] == "rejected"
        assert outcome["reason"]
        assert not list((workspace / ".genome" / "patches").glob("*.patch"))
        assert Path(changed_path).read_text(encoding="utf-8") == SAMPLE_SOURCE

    def test_verify_and_apply_rejects_invalid_syntax(
        self, mock_export: MagicMock, workspace: Path
    ) -> None:
        target = workspace / "route.py"
        target.write_text(SAMPLE_SOURCE, encoding="utf-8")
        config = _load_config(workspace)
        config["mode"] = "enforce"

        outcome = verify_and_apply(
            {
                "decay_detected": True,
                "reason": "test",
                "refactored_code": INVALID_REFACTOR,
            },
            SAMPLE_SOURCE,
            str(target),
            config,
            workspace,
        )

        assert outcome["status"] == "rejected"
        assert target.read_text(encoding="utf-8") == SAMPLE_SOURCE


@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
class TestCriticModes:
    def test_mock_critic_uses_fixture(self, mock_export: MagicMock, workspace: Path) -> None:
        changed_path = _write_target(workspace)
        config = _load_config(workspace)

        with patch(
            "genomeguard.critic._load_mock_critic_response",
            wraps=__import__(
                "genomeguard.critic", fromlist=["_load_mock_critic_response"]
            )._load_mock_critic_response,
        ) as mock_fixture:
            outcome = process_single_change(
                workspace, config, changed_path, mock_critic=True
            )

        assert outcome["status"] == "applied"
        mock_fixture.assert_called_once()

    @patch("genomeguard.core.evaluate_decay_metrics")
    def test_live_critic_flag_passed_through(
        self, mock_evaluate: MagicMock, mock_export: MagicMock, workspace: Path
    ) -> None:
        mock_evaluate.return_value = HEALTHY_CRITIC
        changed_path = _write_target(workspace)
        config = _load_config(workspace)

        process_single_change(workspace, config, changed_path, mock_critic=False)

        assert mock_evaluate.call_args.kwargs["mock"] is False


def test_evaluate_decay_metrics_mock_false_uses_client() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=(
                        '{"decay_detected": false, "reason": "ok", '
                        '"refactored_code": ""}'
                    )
                )
            )
        ]
    )
    config = {"openai_model": "gpt-4o", "rules": []}

    result = evaluate_decay_metrics(
        SAMPLE_SOURCE,
        {"file": "sample_route.py"},
        config,
        llm_client=mock_client,
        mock=False,
    )

    assert result["decay_detected"] is False
    assert result["reason"] == "ok"
    assert result["refactored_code"] == ""
    mock_client.chat.completions.create.assert_called_once()


@patch("genomeguard.core.time.sleep")
@patch("genomeguard.core.query_graph_delta")
@patch("genomeguard.core.export_graph_context", return_value=MINIMAL_GRAPH)
class TestDaemonModes:
    def test_daemon_patch_mode_once(
        self,
        mock_export: MagicMock,
        mock_delta: MagicMock,
        mock_sleep: MagicMock,
        workspace: Path,
    ) -> None:
        changed_path = _write_target(workspace)
        config = _load_config(workspace)
        config["mode"] = "patch"
        mock_delta.side_effect = [
            {"changed_path": changed_path, "timestamp": 1.0, "db_mtime": 10.0},
            None,
        ]

        exit_code = run_daemon(workspace, config, mock_critic=True, once=True)

        assert exit_code == 0
        assert len(list((workspace / ".genome" / "patches").glob("*.patch"))) == 1

    def test_daemon_enforce_mode_once(
        self,
        mock_export: MagicMock,
        mock_delta: MagicMock,
        mock_sleep: MagicMock,
        workspace: Path,
    ) -> None:
        changed_path = _write_target(workspace)
        config = _load_config(workspace)
        config["mode"] = "enforce"
        mock_delta.side_effect = [
            {"changed_path": changed_path, "timestamp": 1.0, "db_mtime": 10.0},
            None,
        ]

        exit_code = run_daemon(workspace, config, mock_critic=True, once=True)

        assert exit_code == 0
        assert Path(changed_path).read_text(encoding="utf-8") != SAMPLE_SOURCE
        assert not list((workspace / ".genome" / "patches").glob("*.patch"))
