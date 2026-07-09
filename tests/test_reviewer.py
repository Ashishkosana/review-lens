from importlib.resources import files
from typing import Any

from review_lens.models import Lens, Severity
from review_lens.reviewer import review
from tests.fakes import FakeLLM

DIFF = files("review_lens.fixtures").joinpath("sample.diff").read_text(encoding="utf-8")

SEC: dict[str, Any] = {
    "file": "app/users.py",
    "line": 5,
    "severity": "blocker",
    "title": "SQL injection",
    "detail": "username is interpolated into the query string",
    "confidence": 0.95,
}
CORR: dict[str, Any] = {
    "file": "app/users.py",
    "line": 7,
    "severity": "high",
    "title": "Missing None check",
    "detail": "fetchone() may return None; row[0] then raises",
    "confidence": 0.9,
}


def _responder(system: str, _user: str) -> list[dict[str, Any]]:
    if "skeptical staff engineer" in system:  # the verify pass
        return [SEC, CORR]
    if "lens is SECURITY" in system:
        return [SEC]
    if "lens is CORRECTNESS" in system:
        return [CORR]
    return []


def test_review_collects_verifies_and_sorts() -> None:
    fake = FakeLLM(_responder)
    result = review(DIFF, fake)
    assert [f.title for f in result.findings] == ["SQL injection", "Missing None check"]
    assert result.findings[0].severity is Severity.BLOCKER
    assert result.findings[0].lens is Lens.SECURITY
    assert result.findings[1].lens is Lens.CORRECTNESS
    assert all(f.verified for f in result.findings)
    assert result.files_reviewed == ["app/users.py"]


def test_verify_can_be_skipped() -> None:
    fake = FakeLLM(_responder)
    result = review(DIFF, fake, verify=False)
    assert len(result.findings) == 2
    assert all(not f.verified for f in result.findings)
    assert not any("skeptical staff engineer" in s for s, _ in fake.calls)


def test_verify_drops_unconfirmed_findings() -> None:
    """The headline behavior: a candidate the verify pass omits is dropped."""

    def responder(system: str, _user: str) -> list[dict[str, Any]]:
        if "skeptical staff engineer" in system:
            return [SEC]  # verify confirms only the security finding
        if "lens is SECURITY" in system:
            return [SEC]
        if "lens is CORRECTNESS" in system:
            return [CORR]
        return []

    result = review(DIFF, FakeLLM(responder))
    assert [f.title for f in result.findings] == ["SQL injection"]


def test_one_failing_lens_is_isolated() -> None:
    def responder(system: str, _user: str) -> list[dict[str, Any]]:
        if "skeptical staff engineer" in system:
            return [CORR]
        if "lens is SECURITY" in system:
            raise RuntimeError("lens crashed")
        if "lens is CORRECTNESS" in system:
            return [CORR]
        return []

    result = review(DIFF, FakeLLM(responder))
    assert [f.title for f in result.findings] == ["Missing None check"]


def test_hallucinated_line_is_nulled() -> None:
    bogus = {**SEC, "line": 999}  # 999 is not a line the diff added

    def responder(system: str, _user: str) -> list[dict[str, Any]]:
        return [bogus] if "lens is SECURITY" in system else []

    result = review(DIFF, FakeLLM(responder), verify=False, lenses=[Lens.SECURITY])
    assert result.findings[0].line is None


def test_finding_on_file_not_in_diff_is_nulled() -> None:
    off_file = {**SEC, "file": "not/in/the.diff", "line": 3}

    def responder(system: str, _user: str) -> list[dict[str, Any]]:
        return [off_file] if "lens is SECURITY" in system else []

    result = review(DIFF, FakeLLM(responder), verify=False, lenses=[Lens.SECURITY])
    assert result.findings[0].line is None


def test_threshold_filters_out_low_confidence() -> None:
    fake = FakeLLM(_responder)
    result = review(DIFF, fake, min_confidence=0.92)
    assert [f.title for f in result.findings] == ["SQL injection"]


def test_empty_diff_short_circuits() -> None:
    fake = FakeLLM(_responder)
    result = review("", fake)
    assert result.findings == []
    assert fake.calls == []


def test_only_requested_lenses_run() -> None:
    fake = FakeLLM(_responder)
    review(DIFF, fake, lenses=[Lens.SECURITY], verify=False)
    lens_calls = [s for s, _ in fake.calls if "Your lens is" in s]
    assert len(lens_calls) == 1
    assert "lens is SECURITY" in lens_calls[0]
