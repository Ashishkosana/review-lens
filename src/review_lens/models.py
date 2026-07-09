"""Typed domain models. Pure — no I/O, no LLM, no network. 100% unit-testable."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NIT = "nit"


class Lens(StrEnum):
    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    TESTS = "tests"


# Higher number == more severe. Used for ordering and threshold comparisons.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.NIT: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.BLOCKER: 4,
}


class Finding(BaseModel):
    """A single review comment produced by one lens. Immutable by design."""

    model_config = ConfigDict(frozen=True)

    file: str
    line: int | None = None
    lens: Lens
    severity: Severity
    title: str
    detail: str
    suggestion: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    verified: bool = False

    def at_least(self, minimum: Severity) -> bool:
        return _SEVERITY_RANK[self.severity] >= _SEVERITY_RANK[minimum]

    def key(self) -> tuple[str, int, str]:
        """Identity for de-duplication: same file+line+title is the same finding."""
        return (self.file, self.line or 0, self.title.strip().lower())


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Most severe, then most confident, then stable by location."""
    return sorted(
        findings,
        key=lambda f: (-_SEVERITY_RANK[f.severity], -f.confidence, f.file, f.line or 0),
    )


def dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, int, str]] = set()
    out: list[Finding] = []
    for f in findings:
        if f.key() in seen:
            continue
        seen.add(f.key())
        out.append(f)
    return out


class ReviewResult(BaseModel):
    findings: list[Finding]
    files_reviewed: list[str] = Field(default_factory=list)
    lenses: list[Lens] = Field(default_factory=list)

    def filtered(self, *, min_severity: Severity, min_confidence: float) -> ReviewResult:
        kept = [
            f
            for f in self.findings
            if f.at_least(min_severity) and f.confidence >= min_confidence
        ]
        return ReviewResult(
            findings=sort_findings(kept),
            files_reviewed=self.files_reviewed,
            lenses=self.lenses,
        )

    @property
    def counts(self) -> dict[Severity, int]:
        counts = dict.fromkeys(Severity, 0)
        for f in self.findings:
            counts[f.severity] += 1
        return counts

    @property
    def has_blockers(self) -> bool:
        return any(f.severity == Severity.BLOCKER for f in self.findings)
