import io
import json
import subprocess

import pytest

from review_lens import cli
from review_lens.cli import _acquire_diff, main
from review_lens.models import Finding, Lens, ReviewResult, Severity

VALID_DIFF = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+x = 1\n"


# --- demo path -------------------------------------------------------------
def test_demo_terminal_runs_without_a_key(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--demo", "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "SQL injection" in out
    assert "app/users.py:5" in out


def test_demo_github_is_valid_json(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--demo", "--format", "github"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["event"] == "REQUEST_CHANGES"


def test_demo_honors_min_severity(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--demo", "--min-severity", "blocker", "--no-color"])
    out = capsys.readouterr().out
    assert "SQL injection" in out  # the sole blocker
    assert "Privilege escalation" not in out  # a HIGH — filtered out


def test_demo_honors_lens_subset(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--demo", "--lenses", "tests", "--no-color"])
    out = capsys.readouterr().out
    assert "No test covers" in out
    assert "SQL injection" not in out


# --- gates & errors --------------------------------------------------------
def test_fail_on_returns_nonzero_when_severe(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--demo", "--fail-on", "high"]) == 1
    capsys.readouterr()


def test_fail_on_below_threshold_returns_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    low = ReviewResult(
        findings=[
            Finding(
                file="a.py", line=1, lens=Lens.CORRECTNESS,
                severity=Severity.LOW, title="t", detail="d",
            )
        ]
    )
    monkeypatch.setattr(cli, "_run", lambda _args: low)
    assert main(["--demo", "--fail-on", "high"]) == 0
    assert main(["--demo", "--fail-on", "low"]) == 1
    capsys.readouterr()


def test_invalid_lenses_exits_cleanly() -> None:
    with pytest.raises(SystemExit):
        main(["--demo", "--lenses", "bogus"])


# --- diff acquisition ------------------------------------------------------
def test_acquire_from_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("PIPED"))
    assert _acquire_diff("-") == "PIPED"


def test_acquire_from_file(tmp_path: object) -> None:
    p = tmp_path / "c.diff"  # type: ignore[operator]
    p.write_text("FROMFILE")
    assert _acquire_diff(str(p)) == "FROMFILE"


def test_acquire_from_git_ref_uses_end_of_options(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **_kw: object) -> object:
        seen["cmd"] = cmd
        return type("R", (), {"stdout": "REFDIFF"})()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _acquire_diff("HEAD~1") == "REFDIFF"
    assert "--end-of-options" in seen["cmd"]
    assert seen["cmd"][-1] == "HEAD~1"


def test_source_starting_with_dash_is_rejected() -> None:
    with pytest.raises(SystemExit):
        _acquire_diff("--output=/tmp/pwn")


def test_empty_diff_is_clean_without_a_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main(["-", "--no-color"]) == 0
    assert "clean" in capsys.readouterr().out.lower()


def test_missing_key_exits_with_helpful_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(VALID_DIFF))
    with pytest.raises(SystemExit) as exc:
        main(["-"])
    assert "ANTHROPIC_API_KEY" in str(exc.value)
