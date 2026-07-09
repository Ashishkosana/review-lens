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
_DIFF_GIT = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def _strip_prefix(path: str) -> str:
    return path[2:] if path.startswith(("a/", "b/")) else path


@dataclass
class FileDiff:
    path: str
    patch: str = ""
    #: new-file line number -> the added line's text (without the leading "+")
    added_lines: dict[int, str] = field(default_factory=dict)


def parse_diff(text: str) -> list[FileDiff]:  # noqa: PLR0912, PLR0915 - line-by-line state machine
    files: list[FileDiff] = []
    current: FileDiff | None = None
    patch_lines: list[str] = []
    new_ln = 0
    old_path: str | None = None  # from "diff --git a/<x>" or "--- a/<x>"

    def flush() -> None:
        nonlocal current, patch_lines
        if current is not None:
            current.patch = "\n".join(patch_lines)
            files.append(current)
        current = None
        patch_lines = []

    # Split on real newlines only. str.splitlines() also breaks on form-feed,
    # vertical tab, NEL, LS/PS — which would corrupt line numbers if any of those
    # appear inside a changed line's content.
    for line in re.split(r"\r?\n", text):
        git_header = _DIFF_GIT.match(line)
        if git_header:
            # Start the file here so a pure rename (no hunk) still registers, and
            # so deletions can recover their real path from the "a/" side.
            flush()
            old_path = git_header.group(1)
            current = FileDiff(path=git_header.group(2))
            patch_lines = [line]
            new_ln = 0
            continue

        if current is None:
            # A plain unified diff with no "diff --git" header: start on "+++".
            if line.startswith("+++ "):
                path = _strip_prefix(line[4:].strip())
                current = FileDiff(path=path if path != "/dev/null" else (old_path or path))
                patch_lines = [line]
                new_ln = 0
            elif line.startswith("--- "):
                stripped = _strip_prefix(line[4:].strip())
                old_path = stripped if stripped != "/dev/null" else old_path
            continue

        patch_lines.append(line)

        if line.startswith("--- "):
            stripped = _strip_prefix(line[4:].strip())
            if stripped != "/dev/null":
                old_path = stripped
            continue
        if line.startswith("+++ "):
            path = _strip_prefix(line[4:].strip())
            # On deletion (+++ /dev/null) recover the real path from the old side.
            current.path = path if path != "/dev/null" else (old_path or current.path)
            continue
        header = _HUNK_HEADER.match(line)
        if header:
            new_ln = int(header.group(1))
            continue
        if line.startswith("\\ "):
            # "No newline at end of file" — never advances.
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
