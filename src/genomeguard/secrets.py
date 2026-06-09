"""Encrypted local storage for OpenAI credentials outside the project tree."""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

CONFIG_DIR_NAME = ".genomeguard"
CREDENTIALS_FILE = "credentials.json"
FERNET_VERSION = "v1"


class SecretsError(RuntimeError):
    """Raised when encrypted credential storage cannot be read or written."""


def user_credentials_dir() -> Path:
    """Return the per-user GenomeGuard config directory under the home folder."""
    return Path.home() / CONFIG_DIR_NAME


def package_secrets_dir() -> Path:
    """Backward-compatible alias for :func:`user_credentials_dir`."""
    return user_credentials_dir()


def credentials_path() -> Path:
    return user_credentials_dir() / CREDENTIALS_FILE


def _derive_fernet_key() -> bytes:
    seed = f"{platform.node()}:{getpass.getuser()}:genomeguard:{FERNET_VERSION}"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise SecretsError(
            "The 'cryptography' package is not installed. Run: pip install -e ."
        ) from exc
    return Fernet(_derive_fernet_key())


def _encrypt_value(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt_value(token: str) -> str:
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")


def _read_store() -> dict[str, Any]:
    path = credentials_path()
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SecretsError(f"Could not read credentials file: {path}") from exc
    if not isinstance(payload, dict):
        return {}
    return payload


def _write_store(payload: dict[str, Any]) -> None:
    secrets_dir = user_credentials_dir()
    secrets_dir.mkdir(parents=True, exist_ok=True)
    path = credentials_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def has_stored_openai_api_key() -> bool:
    """Return True when an encrypted OpenAI API key is saved locally."""
    payload = _read_store()
    token = payload.get("openai_api_key_enc")
    return isinstance(token, str) and bool(token.strip())


def load_openai_api_key() -> str | None:
    """Decrypt and return the stored OpenAI API key, or None if unset."""
    payload = _read_store()
    token = payload.get("openai_api_key_enc")
    if not isinstance(token, str) or not token.strip():
        return None
    try:
        return _decrypt_value(token)
    except Exception as exc:
        raise SecretsError(
            "Stored OpenAI API key could not be decrypted on this machine."
        ) from exc


def save_openai_api_key(api_key: str) -> None:
    """Encrypt and persist the OpenAI API key in the user config directory."""
    cleaned = api_key.strip()
    if not cleaned:
        raise SecretsError("API key cannot be empty.")
    payload = _read_store()
    payload["openai_api_key_enc"] = _encrypt_value(cleaned)
    _write_store(payload)


def clear_openai_api_key() -> None:
    """Remove a stored OpenAI API key."""
    payload = _read_store()
    payload.pop("openai_api_key_enc", None)
    if payload:
        _write_store(payload)
    else:
        path = credentials_path()
        if path.is_file():
            path.unlink(missing_ok=True)


def mask_api_key(api_key: str) -> str:
    """Return a short masked preview suitable for display."""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:3]}...{api_key[-4:]}"
