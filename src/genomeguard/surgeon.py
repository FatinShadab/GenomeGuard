"""Surgeon Agent (Refactorer) — patch generation and enforce-mode writes."""

from __future__ import annotations

import difflib
import json
import sys
import time
from pathlib import Path
from typing import Any

from genomeguard.critic import MOCK_CRITIC_FIXTURE
from genomeguard.utils import load_config

_SOC_VIOLATION_SAMPLE = """\
# SOC VIOLATION: business logic and DB access inside route handler
from infrastructure.database import query_users


def handle_request(request):
    users = query_users()
    return {"users": users}
"""


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


def write_patch_file(patch_text: str, target_path: str, patches_dir: str) -> Path:
    """Persist a unified diff patch under ``patches_dir`` with a timestamped name."""
    patches_root = Path(patches_dir)
    patches_root.mkdir(parents=True, exist_ok=True)

    stem = Path(target_path).stem
    timestamp = int(time.time())
    patch_name = f"{stem}_{timestamp}.patch"
    patch_path = patches_root / patch_name
    patch_path.write_text(patch_text, encoding="utf-8")
    return patch_path


def apply_enforce_write(target_path: str, refactored_code: str) -> None:
    """Overwrite the destination source file with refactored content (UTF-8).

    Kept as a standalone hook so the orchestrator loop can intercept file
    modification events before the next sensor poll (Session 5 race guard).
    """
    Path(target_path).write_text(refactored_code, encoding="utf-8")


def run_surgeon(
    critic_result: dict,
    original_code: str,
    target_path: str,
    config: dict,
) -> dict[str, Any]:
    """Route Surgeon actions based on critic decay signal and config mode.

  Safety: call only after ``verify_and_apply`` / ``execute_compilation_check``
  confirms ``refactored_code`` is syntactically valid. Invoking this on
  unverified LLM output risks patch or enforce loops on invalid syntax.
    """
    if not critic_result.get("decay_detected"):
        return {"action": "none", "message": "Architecture Healthy"}

    refactored_code = critic_result["refactored_code"]
    posix_target = Path(target_path).as_posix()
    mode = config.get("mode", "patch")

    if mode == "enforce":
        apply_enforce_write(target_path, refactored_code)
        return {"action": "enforce", "target_path": posix_target}

    patch_text = generate_unified_diff(original_code, refactored_code, posix_target)
    patches_dir = config.get("patches_dir", ".genome/patches")
    patch_path = write_patch_file(patch_text, posix_target, patches_dir)
    return {
        "action": "patch",
        "patch_path": patch_path.resolve().as_posix(),
    }


def run_surgeon_smoke_test(workspace: str | None = None) -> None:
    """Smoke test patch and enforce modes using mock critic output."""
    root = Path(workspace or ".").resolve()
    fixtures_dir = root / "tests" / "fixtures"
    tmp_dir = root / "tests" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    fixture_path = fixtures_dir / MOCK_CRITIC_FIXTURE
    if not fixture_path.is_file():
        package_dir = Path(__file__).resolve().parent
        fixture_path = package_dir.parent.parent / "tests" / "fixtures" / MOCK_CRITIC_FIXTURE
    critic_result = json.loads(fixture_path.read_text(encoding="utf-8"))

    original_code = _SOC_VIOLATION_SAMPLE
    target_rel = "tests/tmp/sample_route.py"
    target_path = root / target_rel
    target_path.write_text(original_code, encoding="utf-8")

    patch_config = load_config(str(root / "guard_config.json"))
    patch_config["mode"] = "patch"
    patch_config["patches_dir"] = str(root / ".genome" / "patches")

    patch_result = run_surgeon(critic_result, original_code, target_rel, patch_config)
    print("patch mode:", json.dumps(patch_result, indent=2))

    target_path.write_text(original_code, encoding="utf-8")
    enforce_config = dict(patch_config)
    enforce_config["mode"] = "enforce"
    enforce_target = root / "tests" / "tmp" / "enforce_sample_route.py"
    enforce_target.write_text(original_code, encoding="utf-8")
    enforce_rel = enforce_target.relative_to(root).as_posix()

    enforce_result = run_surgeon(
        critic_result, original_code, enforce_rel, enforce_config
    )
    print("enforce mode:", json.dumps(enforce_result, indent=2))

    healthy_result = run_surgeon(
        {"decay_detected": False, "reason": "", "refactored_code": ""},
        original_code,
        target_rel,
        patch_config,
    )
    print("healthy skip:", json.dumps(healthy_result, indent=2))


if __name__ == "__main__":
    run_surgeon_smoke_test(sys.argv[1] if len(sys.argv) > 1 else None)
