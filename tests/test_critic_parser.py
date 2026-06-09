"""Tests for Critic Agent JSON parsing and markdown fence stripping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from genomeguard.critic import parse_critic_response

VALID_PAYLOAD = {
    "decay_detected": True,
    "reason": "Circular dependency between modules.",
    "refactored_code": "def fixed():\n    return 1\n",
}


def test_parse_critic_response_valid_json() -> None:
    raw = json.dumps(VALID_PAYLOAD)
    result = parse_critic_response(raw)

    assert result == VALID_PAYLOAD


def test_parse_critic_response_markdown_json_fence() -> None:
    raw = (
        "```json\n"
        + json.dumps(VALID_PAYLOAD, indent=2)
        + "\n```"
    )
    result = parse_critic_response(raw)

    assert result["decay_detected"] is True
    assert result["reason"] == VALID_PAYLOAD["reason"]
    assert result["refactored_code"] == VALID_PAYLOAD["refactored_code"]


def test_parse_critic_response_markdown_plain_fence() -> None:
    raw = "```\n" + json.dumps(VALID_PAYLOAD) + "\n```"
    result = parse_critic_response(raw)

    assert result["decay_detected"] is True


def test_parse_critic_response_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="Invalid critic JSON"):
        parse_critic_response("{not valid json")


def test_parse_critic_response_missing_keys_raises() -> None:
    incomplete = json.dumps({"decay_detected": True})
    with pytest.raises(ValueError, match="missing required keys"):
        parse_critic_response(incomplete)


def test_parse_critic_response_wrong_types_raises() -> None:
    bad_types = json.dumps(
        {
            "decay_detected": "yes",
            "reason": "ok",
            "refactored_code": "x = 1",
        }
    )
    with pytest.raises(ValueError, match="decay_detected"):
        parse_critic_response(bad_types)


def test_parse_critic_response_fixture_file() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "critic_decay_detected.json"
    raw = fixture_path.read_text(encoding="utf-8")
    result = parse_critic_response(raw)

    assert result["decay_detected"] is True
    assert result["refactored_code"]
