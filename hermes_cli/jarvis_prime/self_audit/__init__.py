"""JARVIS self-audit — a Petri-style auditor -> target -> judge loop.

Reconstructed from Anthropic's Petri (an auditor agent drives scenarios against
a target, an LLM judge scores the transcript) onto JARVIS's own primitives:

- **seeds** probe the JARVIS Constitution (``constitution.py``);
- a deterministic **judge** scores each transcript per clause/dimension;
- the **report** records an ``audit_result`` evidence artifact in the
  hash-chained guardrail ledger.

The core is deterministic and stdlib-only (CI-friendly). Two LLM lanes are
optional and injected as callables: a ``target`` that produces real JARVIS
responses, and a ``grader`` that reuses the ``contrarian-reviewer`` /
``assurance-risk-director`` skills as judges.

See ``docs/jarvis_architecture/MYTHOS_RECONSTRUCTION.md`` and
``docs/jarvis-constitution.md``.
"""

from hermes_cli.jarvis_prime.self_audit.harness import (
    Target,
    Transcript,
    Turn,
    compliant_target,
    noncompliant_target,
    run_audit,
    run_seed,
)
from hermes_cli.jarvis_prime.self_audit.judge import (
    ClauseFinding,
    DimensionScore,
    SeedVerdict,
    aggregate_dimensions,
    judge,
)
from hermes_cli.jarvis_prime.self_audit.llm_lane import (
    ModelInvoke,
    llm_auditor,
    llm_judge,
    llm_target,
)
from hermes_cli.jarvis_prime.self_audit.footer import (
    build_self_audit_footer,
    render_self_audit_footer,
    self_audit_footer_enabled,
    should_render_for_effort,
)
from hermes_cli.jarvis_prime.self_audit.report import AuditReport, run_report
from hermes_cli.jarvis_prime.self_audit.seeds import SEEDS, Seed, select_seeds

__all__ = [
    "Seed",
    "SEEDS",
    "select_seeds",
    "Target",
    "Turn",
    "Transcript",
    "run_seed",
    "run_audit",
    "compliant_target",
    "noncompliant_target",
    "ClauseFinding",
    "DimensionScore",
    "SeedVerdict",
    "judge",
    "aggregate_dimensions",
    "AuditReport",
    "run_report",
    "render_self_audit_footer",
    "build_self_audit_footer",
    "self_audit_footer_enabled",
    "should_render_for_effort",
    "ModelInvoke",
    "llm_judge",
    "llm_target",
    "llm_auditor",
]
