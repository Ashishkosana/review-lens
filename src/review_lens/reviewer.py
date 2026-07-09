"""Orchestration: fan the diff out across lenses, verify, filter. The spine.

Depends only on the `LLMClient` protocol, so it runs identically against the
real Anthropic adapter and the in-memory fake used in tests.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from review_lens.coerce import coerce_findings
from review_lens.diff import FileDiff, parse_diff
from review_lens.lenses import LENS_PROMPTS
from review_lens.llm import LLMClient
from review_lens.models import (
    Finding,
    Lens,
    ReviewResult,
    Severity,
    dedupe,
)
from review_lens.verify import verify_findings

log = logging.getLogger("review_lens")


def _run_lens(client: LLMClient, lens: Lens, diff_text: str) -> list[Finding]:
    try:
        raw = client.run(LENS_PROMPTS[lens], f"```diff\n{diff_text}\n```")
    except Exception:
        log.exception("lens %s failed", lens.value)
        return []
    return coerce_findings(raw, lens=lens)


def _validate_lines(findings: list[Finding], files: list[FileDiff]) -> list[Finding]:
    """Null out line numbers that don't point at a line the diff actually added."""
    added = {f.path: set(f.added_lines) for f in files}
    out: list[Finding] = []
    for f in findings:
        # Null any line that doesn't point at a line the diff added — including
        # findings on a file that isn't in the diff at all (hallucinated file).
        if f.line is not None and (f.file not in added or f.line not in added[f.file]):
            out.append(f.model_copy(update={"line": None}))
        else:
            out.append(f)
    return out


def review(
    diff_text: str,
    client: LLMClient,
    *,
    lenses: list[Lens] | None = None,
    verify: bool = True,
    min_severity: Severity = Severity.LOW,
    min_confidence: float = 0.5,
) -> ReviewResult:
    active = lenses if lenses else list(Lens)
    files = parse_diff(diff_text)
    if not files or not diff_text.strip():
        return ReviewResult(findings=[], files_reviewed=[], lenses=active)

    with ThreadPoolExecutor(max_workers=min(len(active), 4)) as pool:
        groups = pool.map(lambda lens: _run_lens(client, lens, diff_text), active)
    findings = [f for group in groups for f in group]

    findings = dedupe(_validate_lines(findings, files))
    if verify and findings:
        # The verify model is no more trusted than the lens models: re-clamp its
        # line numbers and de-dupe again before anything reaches the renderers.
        survivors = verify_findings(client, diff_text, findings)
        findings = dedupe(_validate_lines(survivors, files))

    result = ReviewResult(
        findings=findings,  # filtered() sorts the survivors, so no sort here
        files_reviewed=[f.path for f in files],
        lenses=active,
    )
    return result.filtered(min_severity=min_severity, min_confidence=min_confidence)
