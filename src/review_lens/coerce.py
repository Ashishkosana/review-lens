"""Tolerant coercion of raw LLM output dicts into typed `Finding` models.

The model is *asked* for a strict schema, but we never trust it blindly: bad
severities fall back to LOW, confidence is clamped, junk items are dropped
rather than crashing the run.
"""

from __future__ import annotations

from typing import Any

from review_lens.models import Finding, Lens, Severity


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_severity(value: Any) -> Severity:
    try:
        return Severity(str(value).strip().lower())
    except ValueError:
        return Severity.LOW


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def coerce_findings(
    raw: list[dict[str, Any]], *, lens: Lens, verified: bool = False
) -> list[Finding]:
    out: list[Finding] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        detail = str(item.get("detail", "")).strip()
        if not title or not detail:
            continue
        suggestion = item.get("suggestion")
        out.append(
            Finding(
                file=str(item.get("file", "")).strip() or "(unknown)",
                line=_as_int(item.get("line")),
                lens=lens,
                severity=_as_severity(item.get("severity")),
                title=title,
                detail=detail,
                suggestion=str(suggestion).strip() if suggestion else None,
                confidence=_clamp(item.get("confidence")),
                verified=verified,
            )
        )
    return out
