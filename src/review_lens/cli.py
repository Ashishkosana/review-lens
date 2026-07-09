"""Command-line entry point.

Usage shapes:
    review-lens --demo                 # bundled sample, no API key needed
    git diff main | review-lens -      # review a piped diff
    review-lens HEAD~1                  # review a git ref/range
    review-lens changes.diff            # review a saved diff file
    review-lens                         # review the working tree vs HEAD
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

from review_lens import __version__
from review_lens.config import Settings
from review_lens.llm import AnthropicClient
from review_lens.models import Lens, ReviewResult, Severity, sort_findings
from review_lens.render import render_github_json, render_markdown, render_terminal
from review_lens.reviewer import review


def _fixture(name: str) -> str:
    return files("review_lens.fixtures").joinpath(name).read_text(encoding="utf-8")


def _git_diff(args: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["git", "diff", "--no-color", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit("review-lens: `git` was not found on PATH.")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"review-lens: `git diff {' '.join(args)}` failed:\n{exc.stderr.strip()}")
    return proc.stdout


def _acquire_diff(source: str | None) -> str:
    if source == "-":
        return sys.stdin.read()
    if source and Path(source).is_file():
        return Path(source).read_text(encoding="utf-8")
    if source:
        return _git_diff([source])
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return _git_diff(["HEAD"])


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="review-lens",
        description="Multi-lens, self-verifying LLM code review for diffs and PRs.",
    )
    p.add_argument("source", nargs="?", help="diff file, '-' for stdin, or a git ref/range")
    p.add_argument("--demo", action="store_true", help="run on a bundled sample (no API key)")
    p.add_argument(
        "--format", choices=["terminal", "markdown", "github"], default="terminal"
    )
    p.add_argument("--lenses", help="comma-separated subset of lenses to run")
    p.add_argument("--min-severity", choices=[s.value for s in Severity])
    p.add_argument("--min-confidence", type=float)
    p.add_argument("--no-verify", action="store_true", help="skip the adversarial verify pass")
    p.add_argument("--model", help="Anthropic model id")
    p.add_argument("--no-color", action="store_true")
    p.add_argument(
        "--fail-on",
        choices=[s.value for s in Severity],
        help="exit non-zero if any finding is at least this severe (CI gate)",
    )
    p.add_argument("--version", action="version", version=f"review-lens {__version__}")
    return p


def _run(args: argparse.Namespace) -> ReviewResult:
    if args.demo:
        demo = ReviewResult.model_validate_json(_fixture("demo_result.json"))
        return ReviewResult(
            findings=sort_findings(demo.findings),
            files_reviewed=demo.files_reviewed,
            lenses=demo.lenses,
        )

    settings = Settings()
    if args.model:
        settings.model = args.model
    if args.no_verify:
        settings.verify = False
    if args.lenses:
        settings.lenses = [Lens(name.strip()) for name in args.lenses.split(",") if name.strip()]
    if args.min_severity:
        settings.min_severity = Severity(args.min_severity)
    if args.min_confidence is not None:
        settings.min_confidence = args.min_confidence

    diff_text = _acquire_diff(args.source if args.source != "--demo" else None)
    if not diff_text.strip():
        return ReviewResult(findings=[], files_reviewed=[], lenses=settings.lenses)

    try:
        client = AnthropicClient(settings.anthropic_api_key, settings.model, settings.max_tokens)
    except ValueError as exc:
        sys.exit(f"review-lens: {exc}")

    return review(
        diff_text,
        client,
        lenses=settings.lenses,
        verify=settings.verify,
        min_severity=settings.min_severity,
        min_confidence=settings.min_confidence,
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = _run(args)

    if args.format == "markdown":
        print(render_markdown(result))
    elif args.format == "github":
        print(json.dumps(render_github_json(result), indent=2))
    else:
        print(render_terminal(result, color=not args.no_color))

    if args.fail_on:
        threshold = Severity(args.fail_on)
        if any(f.at_least(threshold) for f in result.findings):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
