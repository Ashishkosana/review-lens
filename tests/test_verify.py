from typing import Any

from review_lens.models import Finding, Lens, Severity
from review_lens.verify import verify_findings
from tests.fakes import FakeLLM

SEC = Finding(
    file="a.py",
    line=5,
    lens=Lens.SECURITY,
    severity=Severity.BLOCKER,
    title="SQL injection",
    detail="d",
    confidence=0.9,
)
CORR = Finding(
    file="a.py",
    line=7,
    lens=Lens.CORRECTNESS,
    severity=Severity.HIGH,
    title="None crash",
    detail="d",
    confidence=0.9,
)


def test_drops_unconfirmed_and_recovers_lens_by_location() -> None:
    # Verify keeps only the security finding, and rewords its title — lens must
    # still be recovered via (file, line), not the fragile exact-title match.
    def responder(_system: str, _user: str) -> list[dict[str, Any]]:
        return [
            {
                "file": "a.py",
                "line": 5,
                "severity": "blocker",
                "title": "SQL injection vulnerability in get_user",  # reworded
                "detail": "d",
                "confidence": 0.9,
            }
        ]

    out = verify_findings(FakeLLM(responder), "diff", [SEC, CORR])
    assert len(out) == 1
    assert out[0].lens is Lens.SECURITY
    assert out[0].verified is True


def test_empty_candidates_skips_the_call() -> None:
    fake = FakeLLM(lambda _s, _u: [])
    assert verify_findings(fake, "diff", []) == []
    assert fake.calls == []
