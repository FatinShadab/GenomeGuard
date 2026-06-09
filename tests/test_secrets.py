"""Tests for encrypted OpenAI credential storage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from genomeguard import secrets
from genomeguard.utils import ensure_openai_api_key_in_env, has_openai_api_key, save_config


@pytest.fixture
def secrets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / ".secrets"
    monkeypatch.setattr(secrets, "package_secrets_dir", lambda: target)
    return target


def test_save_and_load_openai_api_key_roundtrip(secrets_dir: Path) -> None:
    secrets.save_openai_api_key("sk-test-roundtrip-key")
    assert secrets.has_stored_openai_api_key() is True
    assert secrets.load_openai_api_key() == "sk-test-roundtrip-key"

    raw = json.loads((secrets_dir / "credentials.json").read_text(encoding="utf-8"))
    assert raw["openai_api_key_enc"] != "sk-test-roundtrip-key"


def test_clear_openai_api_key(secrets_dir: Path) -> None:
    secrets.save_openai_api_key("sk-clear-me")
    secrets.clear_openai_api_key()
    assert secrets.has_stored_openai_api_key() is False
    assert secrets.load_openai_api_key() is None


def test_ensure_openai_api_key_in_env_loads_stored_key(
    secrets_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    secrets.save_openai_api_key("sk-from-store")
    assert ensure_openai_api_key_in_env() is True
    import os

    assert os.environ["OPENAI_API_KEY"] == "sk-from-store"
    assert has_openai_api_key() is True


def test_save_config_persists_model(tmp_path: Path) -> None:
    config_path = tmp_path / "guard_config.json"
    config_path.write_text('{"openai_model": "gpt-4o"}\n', encoding="utf-8")
    updated = save_config(str(config_path), {"openai_model": "gpt-4o-mini"})
    assert updated["openai_model"] == "gpt-4o-mini"
    reloaded = json.loads(config_path.read_text(encoding="utf-8"))
    assert reloaded["openai_model"] == "gpt-4o-mini"
