"""`python -m review_lens.eval` — measure the harness against the labeled set.

With ANTHROPIC_API_KEY set, this runs `review()` over every labeled diff twice —
once WITHOUT the adversarial verify pass and once WITH it — and prints a
precision/recall/F1 table so you can see the precision the verify pass buys.
Without a key it explains how to run it and exits 0.

Every number printed here is computed from a live model run over the dataset;
nothing is hardcoded or fabricated.
"""

from __future__ import annotations

from review_lens.config import Settings
from review_lens.eval.dataset import Case, load_cases
from review_lens.eval.metrics import Metrics, aggregate, score
from review_lens.eval.report import format_comparison, format_per_case
from review_lens.llm import AnthropicClient, LLMClient
from review_lens.models import Severity
from review_lens.reviewer import review

# Score the *raw* lens output vs the verified output: drop the severity and
# confidence gates so the only variable between the two runs is the verify pass.
_EVAL_MIN_SEVERITY = Severity.NIT
_EVAL_MIN_CONFIDENCE = 0.0


def _evaluate(
    client: LLMClient, cases: list[Case], *, verify: bool
) -> tuple[list[tuple[str, Metrics]], Metrics]:
    per_case: list[tuple[str, Metrics]] = []
    for case in cases:
        result = review(
            case.diff,
            client,
            verify=verify,
            min_severity=_EVAL_MIN_SEVERITY,
            min_confidence=_EVAL_MIN_CONFIDENCE,
        )
        per_case.append((case.name, score(result.findings, case.labels)))
    return per_case, aggregate(m for _, m in per_case)


def _print_no_key_notice(cases: list[Case]) -> None:
    clean = sum(1 for c in cases if c.is_clean)
    labelled = len(cases) - clean
    print("review-lens eval: ANTHROPIC_API_KEY is not set — skipping the live run.")
    print(
        f"Dataset: {len(cases)} labeled diffs "
        f"({labelled} with seeded bugs, {clean} clean for false-positive measurement)."
    )
    for case in cases:
        kind = "clean" if case.is_clean else f"{len(case.labels)} label(s)"
        print(f"  - {case.name} [{kind}]: {case.description}")
    print("\nSet ANTHROPIC_API_KEY and re-run `python -m review_lens.eval` to score it.")


def main() -> int:
    settings = Settings()
    cases = load_cases()

    if not settings.anthropic_api_key:
        _print_no_key_notice(cases)
        return 0

    client = AnthropicClient(settings.anthropic_api_key, settings.model, settings.max_tokens)

    print(f"review-lens eval: scoring {len(cases)} labeled diffs with {settings.model}\n")

    _without_rows, without_total = _evaluate(client, cases, verify=False)
    with_rows, with_total = _evaluate(client, cases, verify=True)

    print("per-case (with verify):")
    print(format_per_case(with_rows))
    print("\ncorpus metrics:")
    print(format_comparison(without_total, with_total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
