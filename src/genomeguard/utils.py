"""Shared utilities: configuration, paths, filesystem, subprocess, and diff helpers."""

from __future__ import annotations

import difflib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "poll_interval_seconds": 2,
    "mode": "patch",
    "rules": [],
    "patches_dir": ".genome/patches",
    "temp_file": "temp_genome_check.py",
    "openai_model": "gpt-4o",
}


def load_config(path: str = "guard_config.json") -> dict:
    """Read and parse guard configuration with structural fallbacks."""
    config = dict(DEFAULT_CONFIG)
    config_path = Path(path)
    if not config_path.is_file():
        return config

    with config_path.open(encoding="utf-8") as handle:
        user_config = json.load(handle)

    if not isinstance(user_config, dict):
        return config

    config.update(user_config)
    config["poll_interval_seconds"] = config.get("poll_interval_seconds", 2)
    config["mode"] = config.get("mode", "patch")
    config["rules"] = config.get("rules", [])
    config["patches_dir"] = config.get("patches_dir", ".genome/patches")
    config["temp_file"] = config.get("temp_file", "temp_genome_check.py")
    config["openai_model"] = config.get("openai_model", "gpt-4o")
    return config


def normalize_path(path: str) -> str:
    """Normalize a filesystem path to a resolved POSIX string."""
    return Path(path).resolve().as_posix()


def resolve_genome_db(workspace_root: Path) -> Path:
    """Return the path to the codegenome watcher database."""
    return workspace_root / ".genome" / "watcher.db"


def open_db_readonly(db_path: Path) -> sqlite3.Connection:
    """Open the watcher database in read-only mode."""
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def resolve_codegenome_executable() -> str:
    """Locate the codegenome CLI next to the active interpreter or on PATH."""
    bin_dir = Path(sys.executable).parent
    for name in ("codegenome.exe", "codegenome"):
        candidate = bin_dir / name
        if candidate.is_file():
            return str(candidate)

    discovered = shutil.which("codegenome")
    if discovered:
        return discovered
    return "codegenome"


def copy_process_env() -> dict[str, str]:
    """Return a copy of the current process environment for subprocess calls."""
    return os.environ.copy()


def read_changed_file(changed_path: str) -> str:
    """Read changed file contents as UTF-8 text."""
    path = Path(changed_path)
    if not path.is_file():
        raise FileNotFoundError(f"Changed file not found: {normalize_path(changed_path)}")
    return path.read_text(encoding="utf-8")


def generate_unified_diff(original: str, refactored: str, filepath: str) -> str:
    """Build a unified diff between original and refactored source."""
    relative_path = Path(filepath).as_posix()
    original_lines = original.splitlines(keepends=True)
    refactored_lines = refactored.splitlines(keepends=True)
    diff_lines = difflib.unified_diff(
        original_lines,
        refactored_lines,
        fromfile=relative_path,
        tofile=relative_path,
    )
    return "".join(diff_lines)


def execute_compilation_check(
    code: str,
    temp_filename: str,
    workspace_root: Path,
) -> tuple[bool, str]:
    """Write ``code`` to a temp shadow file and run ``py_compile`` against it.

    The shadow file is always removed in a ``finally`` block, even when
    compilation fails or raises.
    """
    temp_path = workspace_root / temp_filename
    try:
        temp_path.write_text(code, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(temp_path)],
            capture_output=True,
            text=True,
            env=copy_process_env(),
        )
        if result.returncode == 0:
            return True, ""
        error_message = (result.stderr or result.stdout or "").strip()
        return False, error_message or "py_compile failed with no error output"
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
