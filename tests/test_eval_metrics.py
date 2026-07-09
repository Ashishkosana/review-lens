"""Unit tests for the eval metrics — pure, synthetic, no API key."""

from __future__ import annotations

from review_lens.eval.metrics import DEFAULT_LINE_WINDOW, Label, Metrics, aggregate, score
from review_lens.models import Finding, Lens, Severity


def _finding(
    *,
    file: str = "a.py",
    line: int | None = 10,
    lens: Lens = Lens.SECURITY,
    title: str = "t",
) -> Finding:
    return Finding(
        file=file,
        line=line,
        lens=lens,
        severity=Severity.HIGH,
        title=title,
        detail="d",
    )


def _label(
    *, file: str = "a.py", line: int | None = 10, lens: Lens = Lens.SECURITY
) -> Label:
    return Label(file=file, line=line, lens=lens, severity=Severity.HIGH)


def test_exact_match_is_true_positive() -> None:
    m = score([_finding(line=10)], [_label(line=10)])
    assert m == Metrics(tp=1, fp=0, fn=0)


def test_near_line_within_window_matches() -> None:
    pred_line = 10 + DEFAULT_LINE_WINDOW
    m = score([_finding(line=pred_line)], [_label(line=10)])
    assert m.tp == 1


def test_line_outside_window_is_fp_and_fn() -> None:
    pred_line = 10 + DEFAULT_LINE_WINDOW + 1
    m = score([_finding(line=pred_line)], [_label(line=10)])
    assert m == Metrics(tp=0, fp=1, fn=1)


def test_wrong_lens_does_not_match() -> None:
    m = score([_finding(lens=Lens.PERFORMANCE)], [_label(lens=Lens.SECURITY)])
    assert m == Metrics(tp=0, fp=1, fn=1)


def test_wrong_file_does_not_match() -> None:
    m = score([_finding(file="a.py")], [_label(file="b.py")])
    assert m == Metrics(tp=0, fp=1, fn=1)


def test_label_with_no_line_matches_on_file_and_lens() -> None:
    m = score([_finding(line=999)], [_label(line=None)])
    assert m.tp == 1


def test_missing_finding_is_false_negative() -> None:
    m = score([], [_label(), _label(line=50, lens=Lens.CORRECTNESS)])
    assert m == Metrics(tp=0, fp=0, fn=2)


def test_matching_is_one_to_one() -> None:
    # Two predictions on the same single defect: one TP, one FP (not two TPs).
    preds = [_finding(line=10), _finding(line=11, title="dup")]
    m = score(preds, [_label(line=10)])
    assert m == Metrics(tp=1, fp=1, fn=0)


def test_clean_diff_no_predictions_is_perfect_precision() -> None:
    m = score([], [])
    assert m == Metrics(tp=0, fp=0, fn=0)
    assert m.precision == 1.0
    assert m.recall == 1.0


def test_clean_diff_with_a_prediction_is_a_false_positive() -> None:
    m = score([_finding()], [])
    assert m == Metrics(tp=0, fp=1, fn=0)
    assert m.precision == 0.0


def test_precision_recall_f1_values() -> None:
    m = Metrics(tp=6, fp=2, fn=4)
    assert m.precision == 0.75
    assert m.recall == 0.6
    assert round(m.f1, 4) == round(2 * 0.75 * 0.6 / (0.75 + 0.6), 4)


def test_f1_is_zero_when_precision_and_recall_zero() -> None:
    assert Metrics(tp=0, fp=1, fn=1).f1 == 0.0


def test_aggregate_sums_counts_then_derives() -> None:
    total = aggregate([Metrics(tp=1, fp=0, fn=1), Metrics(tp=2, fp=3, fn=0)])
    assert total == Metrics(tp=3, fp=3, fn=1)
    assert total.precision == 0.5


def test_aggregate_of_empty_is_zero_metrics() -> None:
    assert aggregate([]) == Metrics()
