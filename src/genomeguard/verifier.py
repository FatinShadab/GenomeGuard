"""Verifier Agent (Safety Gatekeeper) — compilation validation before writes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from genomeguard.surgeon import run_surgeon
from genomeguard.utils import copy_process_env


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


def verify_and_apply(
    critic_result: dict,
    original_code: str,
    target_path: str,
    config: dict,
    workspace_root: Path,
) -> dict[str, Any]:
    """Gatekeeper: verify compilation before delegating to the Surgeon."""
    if not critic_result.get("decay_detected"):
        return {"status": "healthy"}

    refactored_code = critic_result["refactored_code"]
    temp_filename = config.get("temp_file", "temp_genome_check.py")

    passed, error_message = execute_compilation_check(
        refactored_code, temp_filename, workspace_root
    )
    if not passed:
        return {"status": "rejected", "reason": error_message}

    surgeon_result = run_surgeon(critic_result, original_code, target_path, config)
    return {"status": "applied", **surgeon_result}


def run_verifier_smoke_test(workspace: str | None = None) -> None:
    """Smoke test valid and invalid samples through ``execute_compilation_check``."""
    from genomeguard.utils import load_config

    root = Path(workspace or ".").resolve()
    config = load_config(str(root / "guard_config.json"))
    temp_file = config.get("temp_file", "temp_genome_check.py")

    valid_ok, valid_err = execute_compilation_check("x = 1\n", temp_file, root)
    print(f"valid sample: ok={valid_ok} error={valid_err!r}")

    invalid_ok, invalid_err = execute_compilation_check("def broken(\n", temp_file, root)
    print(f"invalid sample: ok={invalid_ok} error={invalid_err!r}")
