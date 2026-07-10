from types import SimpleNamespace
from typing import Any

import pytest

from review_lens.llm import AnthropicClient


def _client(blocks: list[Any]) -> AnthropicClient:
    """Build the real adapter, then swap the SDK client for a duck-typed fake."""
    client = AnthropicClient(api_key="test-key", model="test-model")
    message = SimpleNamespace(content=blocks)
    client._client = SimpleNamespace(messages=SimpleNamespace(create=lambda **_: message))
    return client


def test_extracts_findings_from_tool_use_block() -> None:
    findings = [
        {"file": "a.py", "severity": "high", "title": "t", "detail": "d", "confidence": 0.9}
    ]
    block = SimpleNamespace(type="tool_use", name="report_findings", input={"findings": findings})
    assert _client([block]).run("sys", "user") == findings


def test_returns_empty_when_no_tool_use_block() -> None:
    text = SimpleNamespace(type="text", text="no tool call")
    assert _client([text]).run("sys", "user") == []


def test_returns_empty_when_findings_not_a_list() -> None:
    block = SimpleNamespace(type="tool_use", name="report_findings", input={"findings": "oops"})
    assert _client([block]).run("sys", "user") == []


def test_missing_key_is_a_friendly_error() -> None:
    with pytest.raises(ValueError, match="review-lens --demo"):
        AnthropicClient(api_key="", model="m")
