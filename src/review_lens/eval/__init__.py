"""Evaluation harness: a labeled diff dataset + precision/recall/F1 metrics.

This subpackage is purely additive. It does not change any reviewer behaviour;
it measures it. The metrics and dataset layers are pure and unit-tested with no
API key; the live runner (`python -m review_lens.eval`) needs a key to call the
real model and never fabricates numbers.
"""

from review_lens.eval.dataset import Case, load_cases
from review_lens.eval.metrics import Label, Metrics, aggregate, score

__all__ = ["Case", "Label", "Metrics", "aggregate", "load_cases", "score"]
