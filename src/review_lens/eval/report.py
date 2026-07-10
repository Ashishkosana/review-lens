"""Pure text formatting for the eval report. No I/O — takes Metrics, returns str."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from review_lens.eval.metrics import Metrics


def _ratio(value: float) -> str:
    return f"{value:.2f}"


def format_per_case(rows: Sequence[tuple[str, Metrics]]) -> str:
    """One line per diff: its precision/recall/F1 and raw tp/fp/fn counts."""
    if not rows:
        return "(no cases)"
    width = max(len(name) for name, _ in rows)
    lines = []
    for name, m in rows:
        lines.append(
            f"  {name:<{width}}  P={_ratio(m.precision)} R={_ratio(m.recall)} "
            f"F1={_ratio(m.f1)}  (tp={m.tp} fp={m.fp} fn={m.fn})"
        )
    return "\n".join(lines)


def format_comparison(without_verify: Metrics, with_verify: Metrics) -> str:
    """The headline table: corpus metrics with the verify pass on vs off."""
    header = f"  {'mode':<16}{'precision':>11}{'recall':>9}{'F1':>7}   {'tp/fp/fn':>10}"
    rows = [
        ("without verify", without_verify),
        ("with verify", with_verify),
    ]
    lines = [header]
    for name, m in rows:
        counts = f"{m.tp}/{m.fp}/{m.fn}"
        lines.append(
            f"  {name:<16}{_ratio(m.precision):>11}{_ratio(m.recall):>9}"
            f"{_ratio(m.f1):>7}   {counts:>10}"
        )
    delta = with_verify.precision - without_verify.precision
    sign = "+" if delta >= 0 else ""
    lines.append("")
    lines.append(f"  verify precision lift: {sign}{delta:.2f}")
    return "\n".join(lines)
