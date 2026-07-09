"""review-lens: a multi-lens, self-verifying LLM code-review agent.

Public surface is intentionally small — the CLI (`review_lens.cli`) and the
orchestrator (`review_lens.reviewer.review`) are the two entry points.
"""

from review_lens.models import Finding, Lens, ReviewResult, Severity

__version__ = "0.1.0"

__all__ = ["Finding", "Lens", "ReviewResult", "Severity", "__version__"]
