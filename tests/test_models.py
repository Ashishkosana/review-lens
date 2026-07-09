import pydantic
import pytest

from review_lens.models import (
    Finding,
    Lens,
    ReviewResult,
    Severity,
    dedupe,
    sort_findings,
)


def _f(**kw: object) -> Finding:
    base: dict[str, object] = {
        "file": "a.py",
        "line": 1,
        "lens": Lens.CORRECTNESS,
        "severity": Severity.LOW,
        "title": "t",
        "detail": "d",
    }
    base.update(kw)
    return Finding(**base)  # type: ignore[arg-type]


def test_at_least_orders_severity() -> None:
    assert _f(severity=Severity.HIGH).at_least(Severity.MEDIUM)
    assert not _f(severity=Severity.LOW).at_least(Severity.HIGH)
    assert _f(severity=Severity.BLOCKER).at_least(Severity.BLOCKER)


def test_sort_puts_most_severe_and_confident_first() -> None:
    findings = [
        _f(title="a", severity=Severity.LOW, confidence=0.9),
        _f(title="b", severity=Severity.BLOCKER, confidence=0.5),
        _f(title="c", severity=Severity.BLOCKER, confidence=0.95),
    ]
    ordered = sort_findings(findings)
    assert [f.title for f in ordered] == ["c", "b", "a"]


def test_dedupe_by_file_line_title() -> None:
    a = _f(title="Same", line=3)
    b = _f(title="same", line=3, detail="different detail")  # case-insensitive dup
    c = _f(title="Same", line=4)
    out = dedupe([a, b, c])
    assert len(out) == 2


def test_filtered_applies_severity_and_confidence() -> None:
    result = ReviewResult(
        findings=[
            _f(title="keep", severity=Severity.HIGH, confidence=0.8),
            _f(title="low-sev", severity=Severity.NIT, confidence=0.9),
            _f(title="low-conf", severity=Severity.HIGH, confidence=0.2),
        ]
    )
    kept = result.filtered(min_severity=Severity.MEDIUM, min_confidence=0.5)
    assert [f.title for f in kept.findings] == ["keep"]


def test_counts_and_blockers() -> None:
    result = ReviewResult(
        findings=[_f(severity=Severity.BLOCKER), _f(severity=Severity.LOW)]
    )
    assert result.counts[Severity.BLOCKER] == 1
    assert result.has_blockers


def test_finding_is_frozen() -> None:
    f = _f()
    with pytest.raises(pydantic.ValidationError):
        f.severity = Severity.HIGH  # type: ignore[misc]
