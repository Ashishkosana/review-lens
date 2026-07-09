"""Unified-diff parsing. Pure — turns `git diff` text into per-file added-line maps.

The reviewer sends raw diff text to the model, but we parse it so we can:
  * know exactly which files changed (for the GitHub review renderer), and
  * validate/clamp the line numbers the model returns to lines that were
    actually added (a cheap guard against hallucinated line references).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class FileDiff:
    path: str
    patch: str = ""
    #: new-file line number -> the added line's text (without the leading "+")
    added_lines: dict[int, str] = field(default_factory=dict)


def parse_diff(text: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    current: FileDiff | None = None
    patch_lines: list[str] = []
    new_ln = 0

    def flush() -> None:
        nonlocal current, patch_lines
        if current is not None:
            current.patch = "\n".join(patch_lines)
            files.append(current)
        current = None
        patch_lines = []

    for line in text.splitlines():
        if line.startswith("diff --git"):
            flush()
            continue
        if line.startswith("+++ "):
            # Start of a new file's hunks. Path is "b/<path>" (or /dev/null on delete).
            flush()
            path = line[4:].strip()
            path = path[2:] if path.startswith(("a/", "b/")) else path
            current = FileDiff(path=path)
            patch_lines = [line]
            new_ln = 0
            continue
        if current is None:
            # Pre-amble before the first "+++" (e.g. "--- a/..", "index ..").
            continue

        patch_lines.append(line)

        header = _HUNK_HEADER.match(line)
        if header:
            new_ln = int(header.group(1))
            continue
        if line.startswith("--- ") or line.startswith("\\ "):
            # Old-file marker / "No newline at end of file" — never advance.
            continue
        if line.startswith("+"):
            current.added_lines[new_ln] = line[1:]
            new_ln += 1
        elif line.startswith("-"):
            # Removed line: exists only in the old file, so the new counter holds.
            continue
        else:
            # Context line (leading space, or an empty line inside a hunk).
            new_ln += 1

    flush()
    return files


def changed_files(text: str) -> list[str]:
    return [f.path for f in parse_diff(text)]
