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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import OpenAI

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

OPENAI_KEY_MISSING_MSG = (
    "OPENAI_API_KEY is not set. Live critic mode (--no-mock-critic) requires an API key.\n"
    "Setup:\n"
    "  1. Copy .env.example to .env (or export the variable in your shell).\n"
    "  2. Set OPENAI_API_KEY to a valid OpenAI secret (never commit real keys).\n"
    "  3. Re-run: genome-guard --workspace . --no-mock-critic\n"
    "For offline development without a key, omit --no-mock-critic (mock fixtures are used)."
)


class OpenAIConfigurationError(RuntimeError):
    """Raised when live OpenAI processing is requested without valid credentials."""


DEFAULT_CONFIG: dict[str, Any] = {
    "poll_interval_seconds": 2,
    "mode": "patch",
    "rules": [],
    "patches_dir": ".genome/patches",
    "temp_file": ".temp_genome_check.py",
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
    config["temp_file"] = config.get("temp_file", ".temp_genome_check.py")
    config["openai_model"] = config.get("openai_model", "gpt-4o")
    return config


def save_config(path: str, updates: dict[str, Any]) -> dict:
    """Merge ``updates`` into the config file and persist JSON to disk."""
    config_path = Path(path)
    config = load_config(str(config_path))
    config.update(updates)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")
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


def has_openai_api_key() -> bool:
    """Return True when an OpenAI API key is available from env or encrypted storage."""
    if os.environ.get(OPENAI_API_KEY_ENV, "").strip():
        return True
    from genomeguard.secrets import has_stored_openai_api_key

    return has_stored_openai_api_key()


def ensure_openai_api_key_in_env(*, force_reload: bool = False) -> bool:
    """Load the encrypted API key into ``OPENAI_API_KEY`` when env is unset."""
    if not force_reload and os.environ.get(OPENAI_API_KEY_ENV, "").strip():
        return True

    from genomeguard.secrets import load_openai_api_key

    stored_key = load_openai_api_key()
    if stored_key:
        os.environ[OPENAI_API_KEY_ENV] = stored_key
        return True
    return bool(os.environ.get(OPENAI_API_KEY_ENV, "").strip())


def create_openai_client() -> OpenAI:
    """Create an OpenAI SDK client using env or encrypted local credentials."""
    ensure_openai_api_key_in_env()
    api_key = os.environ.get(OPENAI_API_KEY_ENV, "").strip()
    if not api_key:
        raise OpenAIConfigurationError(OPENAI_KEY_MISSING_MSG)

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OpenAIConfigurationError(
            "The 'openai' package is not installed. Run: pip install -e \".[dev]\""
        ) from exc

    return OpenAI(api_key=api_key)


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
