import json

import pytest

from review_lens.cli import main


def test_demo_terminal_runs_without_a_key(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--demo", "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "SQL injection" in out
    assert "app/users.py:5" in out


def test_demo_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--demo", "--format", "markdown"])
    assert capsys.readouterr().out.startswith("### review-lens")


def test_demo_github_is_valid_json(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--demo", "--format", "github"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["event"] == "REQUEST_CHANGES"
    assert any(c["path"] == "app/users.py" for c in payload["comments"])


def test_fail_on_returns_nonzero_when_severe(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--demo", "--fail-on", "high"]) == 1
    capsys.readouterr()


def test_no_gate_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--demo"]) == 0
    capsys.readouterr()
