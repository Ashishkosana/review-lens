# review-lens

**LLM code review you can actually put behind a PR — because it argues with itself before it comments.**

[![CI](https://github.com/Ashishkosana/review-lens/actions/workflows/ci.yml/badge.svg)](https://github.com/Ashishkosana/review-lens/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

`review-lens` reviews a git diff with an LLM across **four focused lenses** — correctness, security, performance, and test-coverage — then runs an **adversarial self-verification pass** that tries to *refute* every finding before you ever see it. You get a short list of high-signal, verified comments instead of the wall of confident-but-wrong noise a single "review this PR" prompt produces.

It suggests. **You decide.** Nothing is ever auto-applied.

---

## Try it in 30 seconds (no API key)

```bash
git clone https://github.com/Ashishkosana/review-lens && cd review-lens
pip install -e .
review-lens --demo
```

> PyPI release (`pipx install review-lens`) is on the roadmap.

```
review-lens: 4 findings across 1 file (1 blocker, 2 high, 1 medium)

 BLOCKER  app/users.py:5  [security · 98% ✓verified]
  SQL injection: username interpolated into the query string
  get_user() builds SQL with an f-string, so `' OR '1'='1` runs as SQL (OWASP A03).
  → Use a parameterized query: db.execute("... WHERE username = ?", (username,)).

 HIGH  app/users.py:7  [correctness · 95% ✓verified]
  Unhandled missing row raises TypeError
  fetchone() returns None for an unknown user; row[0] then raises instead of 404-ing.
  → Guard the None case before indexing.

 HIGH  app/users.py:12  [security · 90% ✓verified]
  Privilege escalation: admin derived from email domain
  → Check an explicit role flag set by a trusted process, not user-supplied email.

 MEDIUM  app/users.py:10  [tests · 80% ✓verified]
  No test covers the not-found or admin paths
  → Add tests for the missing-user and is_admin true/false branches.
```

## Real usage

```bash
export ANTHROPIC_API_KEY=sk-ant-...

git diff main | review-lens -            # review a branch against main
review-lens HEAD~1                        # review the last commit
review-lens                               # review your working tree vs HEAD
review-lens changes.diff                  # review a saved diff

review-lens HEAD~1 --format markdown      # PR-ready markdown
review-lens HEAD~1 --lenses security,correctness --fail-on high
```

Flags: `--format {terminal,markdown,github}` · `--lenses` · `--min-severity` · `--min-confidence` · `--no-verify` · `--fail-on <severity>` (CI gate) · `--model`.

## How it works

```
              ┌─ correctness ─┐
   git diff ──┼─ security ─────┤ (LLM, run in parallel)
              ├─ performance ──┤
              └─ tests ────────┘
                     │  candidate findings
                     ▼
             adversarial verify  ← a skeptic pass refutes each finding
                     │             against the actual diff; only survivors remain
                     ▼
        ranked, de-duped, verified findings → terminal / markdown / GitHub review
```

The verify pass is the whole point: it trades a little recall for a lot of **precision**, which is the difference between a reviewer people keep and one they mute. That claim isn't a vibe — there's an [evaluation harness](#evaluation) that measures it. Line references the model invents are also nulled out if they don't map to a line the diff actually changed.

## Use it as a GitHub Action

```yaml
# .github/workflows/review.yml
name: review-lens
on: pull_request
permissions:
  contents: read
  pull-requests: write
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: Ashishkosana/review-lens@main
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          fail-on: blocker
```

It posts the review as a PR comment and (optionally) fails the check on severe findings.

## Design

- **Ports & adapters.** Everything depends on a tiny `LLMClient` protocol, so the whole pipeline is unit-tested against an in-memory fake — no key, no network in CI. The Anthropic adapter is the only place that touches the API.
- **Structured output.** The model is forced through a single required tool call, and its output is coerced tolerantly (bad severities → LOW, confidence clamped, junk dropped) — it never crashes the run.
- **Pure core.** Diff parsing, ranking, filtering, and rendering are pure functions with their own tests.

```
src/review_lens/
  models.py     # typed domain models (pure)
  diff.py       # unified-diff → per-file added-line maps (pure)
  lenses.py     # the four focused reviewer prompts
  llm.py        # LLMClient protocol + Anthropic adapter
  coerce.py     # tolerant LLM-output → Finding coercion
  reviewer.py   # orchestration: fan out → verify → filter
  verify.py     # adversarial self-verification
  render.py     # terminal / markdown / GitHub renderers (pure)
  config.py     # env-driven settings
  cli.py        # entry point
  eval/         # labeled dataset + precision/recall/F1 harness (python -m review_lens.eval)
```

> **Note:** `--fail-on` is a convenience gate, not a trust boundary. An LLM
> reading attacker-authored diff text can be talked out of a finding (prompt
> injection), so keep a human in the loop — never merge solely on a green check.

## Evaluation

The headline claim — *the verify pass trades recall for precision* — is measured,
not asserted. There's a small **labeled dataset** under `src/review_lens/eval/cases/`:
each case is a unified diff plus a ground-truth labels file listing the findings it
*should* surface (`file`, `line`, `lens`, `severity`).

- **Seeded-bug diffs** — a SQL injection, an off-by-one slice, an N+1 query, and a
  branch-heavy function shipped without a test — one per lens.
- **Clean diffs** — a pure rename/retype and a correct parameterize-and-guard fix —
  carry *no* labels, so any finding on them is a false positive. This is how the
  harness measures precision, not just recall.

**Metrics** (`review_lens.eval.metrics`, pure and unit-tested) score predicted
findings against labels with **precision / recall / F1**. A prediction is a true
positive when it matches a label by `file` + `lens` and lands within a few lines of
the labelled line; matching is one-to-one, so duplicate comments on the same defect
count as false positives rather than inflating recall. Corpus metrics sum the
confusion-matrix counts across all diffs (so the clean diffs genuinely pull
precision down).

Run it:

```bash
# No key: prints the dataset and how to score it (exit 0).
python -m review_lens.eval

# With a key: runs review() over every diff twice — WITHOUT and WITH the verify
# pass — and prints a precision/recall/F1 table showing the precision lift.
export ANTHROPIC_API_KEY=sk-ant-...
python -m review_lens.eval
```

Both runs use identical severity/confidence gates, so the verify pass is the only
variable between them. **Every number is computed live from the model over the
dataset — nothing is hardcoded.** Expect the *with-verify* row to show higher
precision (fewer false positives on the clean diffs) at some cost to recall.

## Roadmap
- Inline GitHub review comments (not just a summary comment)
- Config file for per-repo lens weights and ignore rules
- Local/OSS model adapter (Ollama)

## License
MIT © Ashish Kosana
