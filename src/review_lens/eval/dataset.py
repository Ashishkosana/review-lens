"""The labeled eval dataset: unified-diff fixtures + ground-truth label files.

Each case is a pair of sibling files under `cases/`:
  * `<name>.diff`         — a unified diff to review
  * `<name>.labels.json`  — `{"description": ..., "labels": [Label, ...]}`

A case with an empty `labels` list is a *clean* diff: any finding it produces is
a false positive, which is how the harness measures precision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from review_lens.eval.metrics import Label

CASES_PACKAGE = "review_lens.eval.cases"
_DIFF_SUFFIX = ".diff"
_LABELS_SUFFIX = ".labels.json"


@dataclass(frozen=True)
class Case:
    name: str
    description: str
    diff: str
    labels: list[Label]

    @property
    def is_clean(self) -> bool:
        return not self.labels


def load_cases() -> list[Case]:
    """Load every labeled case, sorted by name for deterministic output."""
    root = files(CASES_PACKAGE)
    cases: list[Case] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        name = entry.name
        if not name.endswith(_DIFF_SUFFIX):
            continue
        stem = name[: -len(_DIFF_SUFFIX)]
        diff = entry.read_text(encoding="utf-8")
        payload: dict[str, Any] = json.loads(
            root.joinpath(f"{stem}{_LABELS_SUFFIX}").read_text(encoding="utf-8")
        )
        labels = [Label.model_validate(raw) for raw in payload.get("labels", [])]
        cases.append(
            Case(
                name=stem,
                description=str(payload.get("description", "")),
                diff=diff,
                labels=labels,
            )
        )
    return cases
