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


def _one(**kw: object) -> ReviewResult:
    base: dict[str, object] = {
        "file": "a.py",
        "line": 3,
        "lens": Lens.CORRECTNESS,
        "severity": Severity.HIGH,
        "title": "t",
        "detail": "d",
    }
    base.update(kw)
    return ReviewResult(findings=[Finding(**base)])  # type: ignore[arg-type]


def test_terminal_contains_location_and_title() -> None:
    out = render_terminal(_result(), color=False)
    assert "app/users.py:5" in out
    assert "SQL injection" in out
    assert "BLOCKER" in out
    assert "\033[" not in out


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


def test_github_comment_event_for_high_with_line() -> None:
    payload = render_github_json(_one(severity=Severity.HIGH, line=3))
    assert payload["event"] == "COMMENT"  # only BLOCKER requests changes
    assert len(payload["comments"]) == 1
    assert payload["comments"][0]["line"] == 3


def test_empty_result_reads_clean() -> None:
    empty = ReviewResult(findings=[], files_reviewed=["a.py"])
    assert "clean" in render_terminal(empty, color=False).lower()
    assert "Clean" in render_markdown(empty)


def test_github_skips_findings_without_a_line() -> None:
    r = _one(line=None, severity=Severity.LOW)
    assert render_github_json(r)["comments"] == []
    assert render_github_json(r)["event"] == "COMMENT"


def test_mentions_are_defanged_in_posted_output() -> None:
    r = _one(title="ping @org/team now", detail="cc @everyone", severity=Severity.LOW)
    md = render_markdown(r)
    gh = render_github_json(r)["comments"][0]["body"]
    for text in (md, gh):
        assert "@org" not in text
        assert "@everyone" not in text
        assert "\u200b" in text  # a zero-width space was inserted after '@'


def test_terminal_colorizes_when_color_true() -> None:
    out = render_terminal(_result(), color=True)
    assert "\033[41;97m BLOCKER \033[0m" in out  # severity tag wrapped in ANSI + reset
    assert "\033[2m" in out  # detail is dimmed


def test_github_blocker_without_line_still_states_a_reason() -> None:
    r = _one(line=None, severity=Severity.BLOCKER, title="latent blocker", detail="why it blocks")
    payload = render_github_json(r)
    assert payload["event"] == "REQUEST_CHANGES"
    assert payload["comments"] == []  # no diff line -> no inline comment
    assert "latent blocker" in payload["body"]  # ...but the reason is now in the body
