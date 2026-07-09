"""Integrity tests for the labeled dataset — no API key needed.

These guard the fixtures themselves: every label must point at a line the diff
actually adds (so the metrics compare like with like), and the corpus must keep
its shape (real bugs + clean diffs) for the harness to mean anything.
"""

from __future__ import annotations

from review_lens.diff import parse_diff
from review_lens.eval.dataset import load_cases
from review_lens.eval.metrics import DEFAULT_LINE_WINDOW
from review_lens.models import Lens


def test_dataset_loads_expected_shape() -> None:
    cases = load_cases()
    assert len(cases) >= 6
    assert any(not c.is_clean for c in cases), "need diffs with seeded bugs"
    assert any(c.is_clean for c in cases), "need a clean diff to measure precision"


def test_every_diff_parses_and_has_changed_files() -> None:
    for case in load_cases():
        files = parse_diff(case.diff)
        assert files, f"{case.name}: diff parsed to no files"


def test_labels_point_at_added_lines() -> None:
    for case in load_cases():
        added = {f.path: set(f.added_lines) for f in parse_diff(case.diff)}
        for label in case.labels:
            assert label.file in added, f"{case.name}: label file {label.file} not in diff"
            if label.line is None:
                continue
            near = any(
                abs(label.line - added_line) <= DEFAULT_LINE_WINDOW
                for added_line in added[label.file]
            )
            assert near, f"{case.name}: label line {label.line} is not near an added line"


def test_dataset_covers_the_advertised_bug_classes() -> None:
    lenses = {label.lens for case in load_cases() for label in case.labels}
    assert {Lens.SECURITY, Lens.CORRECTNESS, Lens.PERFORMANCE, Lens.TESTS} <= lenses


def test_clean_cases_have_descriptions() -> None:
    for case in load_cases():
        assert case.description.strip(), f"{case.name}: missing description"
