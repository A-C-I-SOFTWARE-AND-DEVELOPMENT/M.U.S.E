"""``muse_eval`` — the additive, opt-in behavioral + adversarial eval harness.

This package is the *measurement front door* for MUSE Prime vNext. It stands
alongside (never replaces) the existing ``hermes_cli.jarvis_prime.self_audit``
harness and mirrors its patterns: stdlib-only, deterministic-by-default,
offline, with a pluggable judge so an LLM lane can be injected later without
touching the harness.

Design invariants (all enforced by ``tests/muse_eval``):

* **stdlib-only** — ``dataclasses``, ``enum``, ``json``, ``re``, ``hashlib``,
  ``pathlib``. No third-party imports, no network.
* **offline / CI-safe** — a reference compliant/noncompliant target stand-in
  lets the loop run end-to-end without a model.
* **pluggable judge** — anything satisfying the :class:`~.harness.Judge`
  protocol (``grade(case, target_text) -> CaseVerdict``) can be dropped in.
* **eight scoring dimensions** — the six carried over from the constitution
  plus the two the eval-harness gap analysis identified as missing
  (``agent_selection_quality`` and ``verification_honesty``). See ``rubric.md``.

Nothing here is imported by any default runtime path. Importing this package
has no side effects.

Public surface::

    from hermes_cli.jarvis_prime.muse_eval import (
        DIMENSIONS, Dimension, load_cases, HeuristicJudge, run, Report,
    )
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.muse_eval.harness import (
    DIMENSIONS,
    Case,
    CaseVerdict,
    Dimension,
    HeuristicJudge,
    Judge,
    Report,
    load_cases,
    run,
)

__all__ = [
    "DIMENSIONS",
    "Case",
    "CaseVerdict",
    "Dimension",
    "HeuristicJudge",
    "Judge",
    "Report",
    "load_cases",
    "run",
]
