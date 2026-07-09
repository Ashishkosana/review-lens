from review_lens.coerce import coerce_findings
from review_lens.models import Lens, Severity


def test_maps_fields_and_lens() -> None:
    raw = [
        {
            "file": "a.py",
            "line": 3,
            "severity": "high",
            "title": "Bug",
            "detail": "It breaks",
            "suggestion": "Fix it",
            "confidence": 0.7,
        }
    ]
    out = coerce_findings(raw, lens=Lens.SECURITY, verified=True)
    assert len(out) == 1
    f = out[0]
    assert f.lens is Lens.SECURITY
    assert f.severity is Severity.HIGH
    assert f.verified is True
    assert f.suggestion == "Fix it"


def test_unknown_severity_falls_back_to_low() -> None:
    out = coerce_findings(
        [{"severity": "catastrophic", "title": "t", "detail": "d", "confidence": 1}],
        lens=Lens.CORRECTNESS,
    )
    assert out[0].severity is Severity.LOW


def test_confidence_is_clamped_and_defaults() -> None:
    out = coerce_findings(
        [
            {"title": "a", "detail": "d", "confidence": 5},
            {"title": "b", "detail": "d", "confidence": "junk"},
        ],
        lens=Lens.CORRECTNESS,
    )
    assert out[0].confidence == 1.0
    assert out[1].confidence == 0.5


def test_drops_items_missing_title_or_detail() -> None:
    out = coerce_findings(
        [
            {"title": "", "detail": "d"},
            {"title": "t", "detail": ""},
            "not-a-dict",  # type: ignore[list-item]
            {"title": "ok", "detail": "d"},
        ],
        lens=Lens.CORRECTNESS,
    )
    assert [f.title for f in out] == ["ok"]
