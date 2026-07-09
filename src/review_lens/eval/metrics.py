"""Precision / recall / F1 for predicted findings vs ground-truth labels.

Pure and deterministic — no I/O, no network, no API key needed. A predicted
`Finding` is counted as a true positive when it matches a label by **file** and
**lens** and lands **near** the labelled line (within a small window, since an
LLM and a human rarely agree on the exact line of a multi-line defect).

Matching is one-to-one and greedy: each label can be claimed by at most one
prediction and vice versa, so duplicate predictions on the same defect show up
as false positives rather than inflating recall.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from review_lens.models import Lens, Severity

if TYPE_CHECKING:
    from collections.abc import Iterable

    from review_lens.models import Finding

#: How far a predicted line may drift from the labelled line and still match.
DEFAULT_LINE_WINDOW = 3


class Label(BaseModel):
    """A ground-truth finding a diff *should* surface. Immutable."""

    model_config = ConfigDict(frozen=True)

    file: str
    line: int | None = None
    lens: Lens
    severity: Severity


def _lines_match(pred_line: int | None, label_line: int | None, window: int) -> bool:
    if label_line is None:
        # Label pins no specific line: file + lens is enough to match.
        return True
    if pred_line is None:
        return False
    return abs(pred_line - label_line) <= window


def _is_match(pred: Finding, label: Label, window: int) -> bool:
    return (
        pred.file == label.file
        and pred.lens == label.lens
        and _lines_match(pred.line, label.line, window)
    )


@dataclass(frozen=True)
class Metrics:
    """Confusion-matrix counts plus derived precision/recall/F1."""

    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        # No predictions at all => nothing wrong was claimed => perfect precision.
        return 1.0 if denom == 0 else self.tp / denom

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        # No labels to find => trivially perfect recall.
        return 1.0 if denom == 0 else self.tp / denom

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 0.0 if p + r == 0 else 2 * p * r / (p + r)

    def __add__(self, other: Metrics) -> Metrics:
        return Metrics(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)


def score(
    predicted: Iterable[Finding],
    labels: Iterable[Label],
    *,
    window: int = DEFAULT_LINE_WINDOW,
) -> Metrics:
    """Score one diff's predicted findings against its labels."""
    remaining = list(labels)
    tp = 0
    fp = 0
    for pred in predicted:
        for i, label in enumerate(remaining):
            if _is_match(pred, label, window):
                tp += 1
                remaining.pop(i)
                break
        else:
            fp += 1
    return Metrics(tp=tp, fp=fp, fn=len(remaining))


def aggregate(per_case: Iterable[Metrics]) -> Metrics:
    """Sum per-case counts, then derive corpus-level precision/recall/F1.

    Summing counts (not averaging ratios) is what makes clean diffs pull the
    corpus precision down when they produce false positives.
    """
    return reduce(lambda a, b: a + b, per_case, Metrics())
