"""Test the runner's no-key path — it must exit 0 with a clear message, no calls."""

from __future__ import annotations

import pytest

from review_lens.eval.__main__ import main


def test_main_without_key_exits_zero_and_explains(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Ensure no key leaks in from the real environment.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    rc = main()

    assert rc == 0
    out = capsys.readouterr().out
    assert "ANTHROPIC_API_KEY is not set" in out
    assert "labeled diffs" in out
