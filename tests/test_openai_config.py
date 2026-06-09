"""Offline unit tests for OpenAI client configuration (no network)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from genomeguard.critic import evaluate_decay_metrics
from genomeguard.utils import OpenAIConfigurationError, create_openai_client, has_openai_api_key


def test_has_openai_api_key_false_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert has_openai_api_key() is False


def test_has_openai_api_key_true_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert has_openai_api_key() is True


def test_create_openai_client_missing_key_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(OpenAIConfigurationError, match="OPENAI_API_KEY is not set"):
        create_openai_client()


def test_evaluate_decay_metrics_live_path_uses_client() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"decay_detected": false, "reason": "ok", "refactored_code": ""}'
                )
            )
        ]
    )
    config = {"openai_model": "gpt-4o", "rules": []}

    result = evaluate_decay_metrics(
        "x = 1",
        {"file": "sample.py"},
        config,
        llm_client=mock_client,
        mock=False,
    )

    assert result["decay_detected"] is False
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o"
    assert call_kwargs["temperature"] == 0
    assert isinstance(call_kwargs["messages"], list)


def test_evaluate_decay_metrics_api_failure_raises_runtime_error() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("network down")
    config = {"openai_model": "gpt-4o", "rules": []}

    with pytest.raises(RuntimeError, match="OpenAI API request failed"):
        evaluate_decay_metrics(
            "x = 1",
            {"file": "sample.py"},
            config,
            llm_client=mock_client,
            mock=False,
        )
