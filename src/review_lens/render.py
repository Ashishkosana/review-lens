"""Rendering. Pure — turns a ReviewResult into terminal / markdown / GitHub output."""

from __future__ import annotations

from typing import Any

from review_lens.models import Finding, ReviewResult, Severity

_LABEL: dict[Severity, str] = {
    Severity.BLOCKER: "BLOCKER",
    Severity.HIGH: "HIGH",
    Severity.MEDIUM: "MEDIUM",
    Severity.LOW: "LOW",
    Severity.NIT: "NIT",
}

_ANSI: dict[Severity, str] = {
    Severity.BLOCKER: "\033[41;97m",  # white on red
    Severity.HIGH: "\033[31m",
    Severity.MEDIUM: "\033[33m",
    Severity.LOW: "\033[36m",
    Severity.NIT: "\033[90m",
}
_RESET = "\033[0m"
_DIM = "\033[2m"


def _loc(f: Finding) -> str:
    return f"{f.file}:{f.line}" if f.line is not None else f.file


def _summary(result: ReviewResult) -> str:
    c = result.counts
    parts = [f"{c[s]} {s.value}" for s in Severity if c[s]]
    n = len(result.findings)
    head = f"{n} finding{'s' if n != 1 else ''}"
    files = f"{len(result.files_reviewed)} file{'s' if len(result.files_reviewed) != 1 else ''}"
    return f"{head} across {files}" + (f" ({', '.join(parts)})" if parts else "")


def render_terminal(result: ReviewResult, *, color: bool = True) -> str:
    if not result.findings:
        return f"review-lens: clean — no findings across {len(result.files_reviewed)} file(s)."
    out: list[str] = [f"review-lens: {_summary(result)}", ""]
    for f in result.findings:
        tag = f" {_LABEL[f.severity]} "
        if color:
            tag = f"{_ANSI[f.severity]}{tag}{_RESET}"
        check = " ✓verified" if f.verified else ""
        conf = f"{int(f.confidence * 100)}%"
        out.append(f"{tag} {_loc(f)}  [{f.lens.value} · {conf}{check}]")
        out.append(f"  {f.title}")
        out.append(f"  {_DIM if color else ''}{f.detail}{_RESET if color else ''}")
        if f.suggestion:
            out.append(f"  → {f.suggestion}")
        out.append("")
    return "\n".join(out).rstrip()


def render_markdown(result: ReviewResult) -> str:
    if not result.findings:
        n = len(result.files_reviewed)
        return f"### review-lens\n\n✅ Clean — no findings across {n} file(s)."
    lines = [f"### review-lens\n\n**{_summary(result)}**\n"]
    for f in result.findings:
        check = " · ✓ verified" if f.verified else ""
        lines.append(
            f"- **[{_LABEL[f.severity]}] {f.title}** — `{_loc(f)}` "
            f"_({f.lens.value} · {int(f.confidence * 100)}%{check})_\n"
            f"  {f.detail}"
            + (f"\n  _Suggestion:_ {f.suggestion}" if f.suggestion else "")
        )
    return "\n".join(lines)


def render_github_json(result: ReviewResult) -> dict[str, Any]:
    """A payload shaped for the GitHub 'create a review' API (line comments)."""
    comments: list[dict[str, Any]] = []
    for f in result.findings:
        if f.line is None:
            continue
        body = f"**[{_LABEL[f.severity]}] {f.title}** _({f.lens.value})_\n\n{f.detail}"
        if f.suggestion:
            body += f"\n\n_Suggestion:_ {f.suggestion}"
        comments.append({"path": f.file, "line": f.line, "body": body})
    event = "REQUEST_CHANGES" if result.has_blockers else "COMMENT"
    body = (
        f"🔎 **review-lens** — {_summary(result)}\n\n"
        "_Drafts for your review; nothing is auto-applied._"
    )
    return {"event": event, "body": body, "comments": comments}
