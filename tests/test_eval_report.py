"""Unit tests for the pure report formatters — no API key needed."""

from __future__ import annotations

from review_lens.eval.metrics import Metrics
from review_lens.eval.report import format_comparison, format_per_case


def test_per_case_lists_every_case() -> None:
    rows = [("sqli", Metrics(tp=1, fp=0, fn=0)), ("clean", Metrics(tp=0, fp=1, fn=0))]
    out = format_per_case(rows)
    assert "sqli" in out
    assert "clean" in out
    assert "tp=1" in out
    assert "fp=1" in out


def test_per_case_empty() -> None:
    assert format_per_case([]) == "(no cases)"


def test_comparison_reports_both_modes_and_lift() -> None:
    without = Metrics(tp=8, fp=8, fn=0)  # precision 0.50
    with_ = Metrics(tp=6, fp=1, fn=2)  # precision ~0.857
    out = format_comparison(without, with_)
    assert "without verify" in out
    assert "with verify" in out
    # lift = 0.857 - 0.50 = +0.36 (rounded to 2dp)
    assert "verify precision lift: +0.36" in out


def test_comparison_handles_negative_lift() -> None:
    without = Metrics(tp=6, fp=1, fn=0)  # precision ~0.857
    with_ = Metrics(tp=3, fp=3, fn=3)  # precision 0.50
    out = format_comparison(without, with_)
    assert "verify precision lift: -0.36" in out
