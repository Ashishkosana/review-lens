"""LLM port + Anthropic adapter.

The rest of the package depends only on the `LLMClient` protocol, so the
orchestration is fully testable with an in-memory fake (see tests/) and the
network adapter can be swapped without touching business logic.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# Input schema for the `report_findings` tool: an object wrapping a findings[] array.
TOOL_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": ["integer", "null"]},
                    "severity": {
                        "type": "string",
                        "enum": ["blocker", "high", "medium", "low", "nit"],
                    },
                    "title": {"type": "string", "description": "one-line summary"},
                    "detail": {"type": "string", "description": "what breaks and why"},
                    "suggestion": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["file", "severity", "title", "detail", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

_TOOL = {
    "name": "report_findings",
    "description": "Report code-review findings found in the diff.",
    "input_schema": TOOL_INPUT_SCHEMA,
}


@runtime_checkable
class LLMClient(Protocol):
    def run(self, system_prompt: str, user_content: str) -> list[dict[str, Any]]:
        """Return the `findings` array the model reports via the tool (may be empty)."""
        ...


class AnthropicClient:
    """Real adapter. Forces structured output via a single required tool call."""

    def __init__(self, api_key: str, model: str, max_tokens: int = 4096) -> None:
        # Imported lazily so importing the package never pulls the heavy SDK
        # unless you actually construct the real client.
        from anthropic import Anthropic  # noqa: PLC0415

        if not api_key:
            raise ValueError(
                "No Anthropic API key. Set ANTHROPIC_API_KEY, or use `review-lens --demo`."
            )
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def run(self, system_prompt: str, user_content: str) -> list[dict[str, Any]]:
        message = self._client.messages.create(  # type: ignore[call-overload]
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_prompt,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "report_findings"},
            messages=[{"role": "user", "content": user_content}],
        )
        for block in message.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "report_findings":
                data = block.input
                if isinstance(data, dict):
                    findings = data.get("findings", [])
                    return findings if isinstance(findings, list) else []
        return []
