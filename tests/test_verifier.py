"""Tests for the Verifier Agent compilation gate."""

from pathlib import Path

import pytest

from genomeguard.verifier import execute_compilation_check, verify_and_apply

VALID_PYTHON = "def greet():\n    return 'hello'\n"

INVALID_PYTHON = "def broken(\n"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def test_compile_check_valid_python(workspace: Path) -> None:
    ok, err = execute_compilation_check(VALID_PYTHON, "temp_genome_check.py", workspace)
    assert ok is True
    assert err == ""
    assert not (workspace / "temp_genome_check.py").exists()


def test_compile_check_invalid_python(workspace: Path) -> None:
    ok, err = execute_compilation_check(INVALID_PYTHON, "temp_genome_check.py", workspace)
    assert ok is False
    assert err
    assert not (workspace / "temp_genome_check.py").exists()


def test_verify_rejects_bad_refactor(workspace: Path) -> None:
    critic_result = {
        "decay_detected": True,
        "reason": "test violation",
        "refactored_code": INVALID_PYTHON,
    }
    config = {
        "mode": "patch",
        "patches_dir": str(workspace / "patches"),
        "temp_file": "temp_genome_check.py",
    }
    result = verify_and_apply(
        critic_result,
        "original = True\n",
        "tests/tmp/sample.py",
        config,
        workspace,
    )
    assert result["status"] == "rejected"
    assert result["reason"]
    patches_dir = workspace / "patches"
    assert not patches_dir.exists() or not list(patches_dir.glob("*.patch"))
