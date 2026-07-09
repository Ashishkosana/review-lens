from review_lens.models import Finding, Lens, ReviewResult, Severity
from review_lens.render import render_github_json, render_markdown, render_terminal


def _result() -> ReviewResult:
    return ReviewResult(
        findings=[
            Finding(
                file="app/users.py",
                line=5,
                lens=Lens.SECURITY,
                severity=Severity.BLOCKER,
                title="SQL injection",
                detail="username is interpolated into the query",
                suggestion="use a parameterized query",
                confidence=0.98,
                verified=True,
            )
        ],
        files_reviewed=["app/users.py"],
        lenses=[Lens.SECURITY],
    )


def test_terminal_contains_location_and_title() -> None:
    out = render_terminal(_result(), color=False)
    assert "app/users.py:5" in out
    assert "SQL injection" in out
    assert "BLOCKER" in out
    assert "\033[" not in out  # color disabled -> no ANSI


def test_markdown_has_heading_and_suggestion() -> None:
    out = render_markdown(_result())
    assert out.startswith("### review-lens")
    assert "SQL injection" in out
    assert "Suggestion" in out


def test_github_payload_requests_changes_on_blocker() -> None:
    payload = render_github_json(_result())
    assert payload["event"] == "REQUEST_CHANGES"
    assert payload["comments"][0]["path"] == "app/users.py"
    assert payload["comments"][0]["line"] == 5


def test_empty_result_reads_clean() -> None:
    empty = ReviewResult(findings=[], files_reviewed=["a.py"])
    assert "clean" in render_terminal(empty, color=False).lower()
    assert "Clean" in render_markdown(empty)


def test_github_skips_findings_without_a_line() -> None:
    r = ReviewResult(
        findings=[
            Finding(
                file="a.py",
                line=None,
                lens=Lens.CORRECTNESS,
                severity=Severity.LOW,
                title="t",
                detail="d",
            )
        ]
    )
    assert render_github_json(r)["comments"] == []
    assert render_github_json(r)["event"] == "COMMENT"
