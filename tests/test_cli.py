"""CLI flag and entry-point tests for GenomeGuard modes."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from genomeguard.cli import build_parser, main
from genomeguard.utils import OpenAIConfigurationError

MINIMAL_GRAPH = {"nodes": [], "edges": []}


@pytest.fixture(autouse=True)
def mock_no_stored_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from genomeguard import secrets

    monkeypatch.setattr(secrets, "has_stored_openai_api_key", lambda: False)
    monkeypatch.setattr(secrets, "load_openai_api_key", lambda: None)


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


class TestBuildParser:
    def test_mode_choices(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--mode", "enforce", "--workspace", "."])
        assert args.mode == "enforce"

    def test_mock_critic_default_without_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        parser = build_parser()
        args = parser.parse_args(["--workspace", "."])
        assert args.mock_critic is True

    def test_mock_critic_default_with_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        parser = build_parser()
        args = parser.parse_args(["--workspace", "."])
        assert args.mock_critic is False

    def test_no_mock_critic_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--no-mock-critic", "--workspace", "."])
        assert args.mock_critic is False


@patch("genomeguard.cli.run_daemon", return_value=0)
@patch("genomeguard.cli.create_openai_client")
class TestMainDaemonLaunch:
    def test_mock_critic_without_api_key_warns_and_runs(
        self,
        mock_create_client: MagicMock,
        mock_run_daemon: MagicMock,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            main(["--workspace", str(workspace), "--mock-critic", "--once"])

        assert exc_info.value.code == 0
        mock_create_client.assert_not_called()
        mock_run_daemon.assert_called_once()
        assert mock_run_daemon.call_args.kwargs["mock_critic"] is True
        assert mock_run_daemon.call_args.kwargs["once"] is True
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "mock critic" in captured.err.lower()

    def test_no_mock_critic_without_api_key_exits(
        self,
        mock_create_client: MagicMock,
        mock_run_daemon: MagicMock,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        mock_create_client.side_effect = OpenAIConfigurationError(
            "OPENAI_API_KEY is not set."
        )

        with pytest.raises(SystemExit) as exc_info:
            main(["--workspace", str(workspace), "--no-mock-critic", "--once"])

        assert exc_info.value.code == 1
        mock_run_daemon.assert_not_called()
        mock_create_client.assert_called_once()
        captured = capsys.readouterr()
        assert "OPENAI_API_KEY" in captured.err

    def test_no_mock_critic_with_api_key_runs_live(
        self,
        mock_create_client: MagicMock,
        mock_run_daemon: MagicMock,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        with pytest.raises(SystemExit) as exc_info:
            main(["--workspace", str(workspace), "--no-mock-critic", "--once"])

        assert exc_info.value.code == 0
        mock_create_client.assert_called_once()
        mock_run_daemon.assert_called_once()
        assert mock_run_daemon.call_args.kwargs["mock_critic"] is False

    def test_mode_enforce_override(
        self,
        mock_create_client: MagicMock,
        mock_run_daemon: MagicMock,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        with pytest.raises(SystemExit):
            main(
                [
                    "--workspace",
                    str(workspace),
                    "--mode",
                    "enforce",
                    "--mock-critic",
                    "--once",
                ]
            )

        config_passed = mock_run_daemon.call_args.args[1]
        assert config_passed["mode"] == "enforce"

    def test_mode_patch_override(
        self,
        mock_create_client: MagicMock,
        mock_run_daemon: MagicMock,
        workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_path = workspace / "guard_config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["mode"] = "enforce"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        with pytest.raises(SystemExit):
            main(
                [
                    "--workspace",
                    str(workspace),
                    "--mode",
                    "patch",
                    "--mock-critic",
                    "--once",
                ]
            )

        config_passed = mock_run_daemon.call_args.args[1]
        assert config_passed["mode"] == "patch"


@patch("genomeguard.cli.run_daemon", return_value=1)
class TestMainErrors:
    def test_missing_watcher_db_propagates_exit_code(
        self,
        mock_run_daemon: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workspace = tmp_path / "empty"
        workspace.mkdir()
        (workspace / "guard_config.json").write_text("{}", encoding="utf-8")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            main(["--workspace", str(workspace), "--mock-critic", "--once"])

        assert exc_info.value.code == 1
        mock_run_daemon.assert_called_once()
