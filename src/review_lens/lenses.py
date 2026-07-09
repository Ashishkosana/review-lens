"""The review lenses. Each lens is an independent, narrowly-scoped reviewer.

Running focused single-concern passes (instead of one "review this" prompt)
produces sharper, less generic findings and lets us parallelise the calls.
"""

from __future__ import annotations

from review_lens.models import Lens

_SHARED = """\
You are reviewing a unified diff. Review ONLY the changed lines (those the diff
adds or modifies); use the surrounding context only to understand them. Report
each concrete problem as a finding via the `report_findings` tool.

Rules:
- Cite the exact file path and the new-file line number from the diff.
- Every finding must be actionable: say what breaks and give a concrete fix.
- Prefer a few real, high-signal findings over many speculative ones. If the
  change is clean for your lens, return an empty list — do not invent issues.
- Set `confidence` (0-1) honestly: 1.0 only when you can point at the exact
  failing line and input. Lower it when you're reasoning about unseen code.
- `severity`: blocker (ships a bug/vuln), high, medium, low, nit.
"""

LENS_PROMPTS: dict[Lens, str] = {
    Lens.CORRECTNESS: _SHARED
    + """
Your lens is CORRECTNESS. Hunt logic bugs, wrong conditionals, off-by-one and
boundary errors, unhandled None/empty/error cases, incorrect async/await,
resource leaks, race conditions, and mismatches between a function's contract
and its behaviour. Ignore style, security, and performance — other lenses own
those.
""",
    Lens.SECURITY: _SHARED
    + """
Your lens is SECURITY. Hunt injection (SQL/command/template), missing
authz/authn checks, secrets or keys committed in code, unsafe deserialization,
SSRF, path traversal, weak crypto, and unvalidated user input crossing a trust
boundary. Map findings to the OWASP Top 10 category in the detail when it fits.
Ignore style and performance.
""",
    Lens.PERFORMANCE: _SHARED
    + """
Your lens is PERFORMANCE. Hunt N+1 queries, work inside hot loops that could be
hoisted, unbounded memory growth, blocking I/O on an async path, missing
pagination/limits, and needless O(n^2) scans. Only flag things that will
plausibly bite at real scale — not micro-optimisations. Ignore style/security.
""",
    Lens.TESTS: _SHARED
    + """
Your lens is TEST COVERAGE. Identify new or changed behaviour that ships without
a test: untested branches, error paths, and edge cases; assertions that don't
actually check the behaviour; and tests that would pass even if the code were
broken. Suggest the specific test to add. Ignore style/security/performance.
""",
}
