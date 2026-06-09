"""Tests for Surgeon Agent patch generation and enforce-mode writes."""

from __future__ import annotations

import json
from pathlib import Path

from genomeguard.surgeon import apply_enforce_write, run_surgeon

ORIGINAL = (
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

CRITIC_RESULT = {
    "decay_detected": True,
    "reason": "SOC violation.",
    "refactored_code": REFACTORED,
}


def test_run_surgeon_creates_patch_file(tmp_path: Path) -> None:
    target = tmp_path / "sample_route.py"
    target.write_text(ORIGINAL, encoding="utf-8")
    patches_dir = tmp_path / ".genome" / "patches"
    config = {
        "mode": "patch",
        "patches_dir": str(patches_dir),
    }

    result = run_surgeon(
        CRITIC_RESULT,
        ORIGINAL,
        str(target),
        config,
    )

    assert result["action"] == "patch"
    patch_path = Path(result["patch_path"])
    assert patch_path.is_file()
    assert patch_path.parent == patches_dir.resolve()
    assert patch_path.suffix == ".patch"
    content = patch_path.read_text(encoding="utf-8")
    assert "---" in content
    assert "+++" in content


def test_run_surgeon_enforce_overwrites_target(tmp_path: Path) -> None:
    target = tmp_path / "enforce_sample.py"
    target.write_text(ORIGINAL, encoding="utf-8")
    config = {"mode": "enforce", "patches_dir": str(tmp_path / "patches")}

    result = run_surgeon(
        CRITIC_RESULT,
        ORIGINAL,
        str(target),
        config,
    )

    assert result["action"] == "enforce"
    assert target.read_text(encoding="utf-8") == REFACTORED


def test_apply_enforce_write_direct(tmp_path: Path) -> None:
    target = tmp_path / "direct.py"
    target.write_text("old\n", encoding="utf-8")

    apply_enforce_write(str(target), "new\n")

    assert target.read_text(encoding="utf-8") == "new\n"


def test_run_surgeon_skips_when_healthy(tmp_path: Path) -> None:
    target = tmp_path / "healthy.py"
    target.write_text(ORIGINAL, encoding="utf-8")
    config = {"mode": "patch", "patches_dir": str(tmp_path / "patches")}

    result = run_surgeon(
        {"decay_detected": False, "reason": "", "refactored_code": ""},
        ORIGINAL,
        str(target),
        config,
    )

    assert result["action"] == "none"
    assert not (tmp_path / "patches").exists()


def test_run_surgeon_uses_fixture_refactor(tmp_path: Path) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "critic_decay_detected.json"
    critic_result = json.loads(fixture_path.read_text(encoding="utf-8"))
    target = tmp_path / "from_fixture.py"
    target.write_text(ORIGINAL, encoding="utf-8")
    patches_dir = tmp_path / ".genome" / "patches"
    config = {"mode": "patch", "patches_dir": str(patches_dir)}

    result = run_surgeon(critic_result, ORIGINAL, str(target), config)

    assert result["action"] == "patch"
    assert list(patches_dir.glob("*.patch"))
