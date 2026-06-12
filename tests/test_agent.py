"""Tests for intent classification and reply generation.

These tests mock the Anthropic client so they run without an API key or
credits (see CLAUDE.md: every external call needs try/except + fallback,
and that fallback path is what we verify here too).
"""

from types import SimpleNamespace
from unittest.mock import patch

from src.agent import FALLBACK_REPLY, generate_reply
from src.classifier import FALLBACK_INTENT, classify_intent


def _usage():
    return SimpleNamespace(input_tokens=10, output_tokens=5)


def test_classify_intent_returns_tool_result():
    mock_response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                name="classify_intent",
                input={"intent": "cita"},
            )
        ],
        usage=_usage(),
    )

    with patch("src.classifier.client.messages.create", return_value=mock_response):
        assert classify_intent("Quiero una cita el sabado") == "cita"


def test_classify_intent_falls_back_on_api_error():
    with patch("src.classifier.client.messages.create", side_effect=RuntimeError("boom")):
        assert classify_intent("hola") == FALLBACK_INTENT


def test_generate_reply_returns_text():
    mock_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Una limpieza dental cuesta S/ 120.")],
        usage=_usage(),
    )

    with patch("src.agent.client.messages.create", return_value=mock_response):
        reply = generate_reply("Cuanto cuesta una limpieza?", "info", [])

    assert "S/ 120" in reply


def test_generate_reply_falls_back_on_api_error():
    with patch("src.agent.client.messages.create", side_effect=RuntimeError("boom")):
        reply = generate_reply("hola", "otro", [])

    assert reply == FALLBACK_REPLY
