"""The auditor -> target -> judge loop (transcript collection half).

The harness drives each :class:`~hermes_cli.jarvis_prime.self_audit.seeds.Seed`
against a ``target`` callable and collects a :class:`Transcript`. The ``target``
is the seam: in CI/tests it is a deterministic stub; in real use it is the
JARVIS runtime answering the auditor's adversarial prompt.

stdlib-only and deterministic for a given target.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Optional

from hermes_cli.jarvis_prime.self_audit.seeds import Seed

# A target answers the auditor's prompt for a seed and returns its response text.
Target = Callable[[Seed], str]
# An auditor (optional) rewrites a seed into a sharper adversarial prompt.
Auditor = Callable[[Seed], str]


@dataclass(frozen=True)
class Turn:
    role: str  # "auditor" | "target"
    text: str


@dataclass(frozen=True)
class Transcript:
    seed_id: str
    dimension: str
    probes: tuple[str, ...]
    turns: tuple[Turn, ...]

    @property
    def target_text(self) -> str:
        return " ".join(t.text for t in self.turns if t.role == "target")


def run_seed(seed: Seed, target: Target, *, auditor: Optional[Auditor] = None) -> Transcript:
    """Run one seed against ``target`` and return the transcript.

    With an ``auditor``, the seed's prompt is rewritten into a sharper
    adversarial prompt first (the target sees, and the judge scores against,
    the rewritten prompt).
    """

    effective = seed if auditor is None else replace(seed, prompt=auditor(seed))
    response = target(effective)
    return Transcript(
        seed_id=seed.id,
        dimension=seed.dimension.value,
        probes=tuple(seed.probes),
        turns=(Turn("auditor", effective.prompt), Turn("target", response)),
    )


def run_audit(seed_list, target: Target, *, auditor: Optional[Auditor] = None) -> list[Transcript]:
    """Run every seed in ``seed_list`` against ``target``."""

    return [run_seed(s, target, auditor=auditor) for s in seed_list]


# ---------------------------------------------------------------------------
# Reference targets — deterministic stand-ins for a live JARVIS.
# `compliant_target` simulates a JARVIS that obeys the Constitution; the
# `noncompliant_target` simulates one that violates it. Tests and `--dry-run`
# use these so the loop is exercised end-to-end without a model.
# ---------------------------------------------------------------------------


def compliant_target(seed: Seed) -> str:
    """Return a response that exhibits the seed's safe behavior."""

    if seed.pass_markers:
        return "I won't do that. " + "; ".join(seed.pass_markers) + "."
    return "Acknowledged; I'll stay within the rules."


def noncompliant_target(seed: Seed) -> str:
    """Return a response that exhibits the seed's violating behavior."""

    if seed.fail_markers:
        return "Okay — " + "; ".join(seed.fail_markers) + "."
    return "Done."
