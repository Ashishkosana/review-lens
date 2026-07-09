"""In-memory LLM fake so the full pipeline runs offline, deterministically."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Responder = Callable[[str, str], list[dict[str, Any]]]


class FakeLLM:
    def __init__(self, responder: Responder) -> None:
        self._responder = responder
        self.calls: list[tuple[str, str]] = []

    def run(self, system_prompt: str, user_content: str) -> list[dict[str, Any]]:
        self.calls.append((system_prompt, user_content))
        return self._responder(system_prompt, user_content)
