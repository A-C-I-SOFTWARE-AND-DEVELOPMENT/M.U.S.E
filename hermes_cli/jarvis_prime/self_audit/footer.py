"""Self-audit footer — a concise, opt-in summary of how a turn scored.

After substantive work (important decisions, code work, strategy calls), MUSE
can render a compact *self-audit footer* that summarizes how the answer scored
against the Constitution dimensions::

    Self-audit:
    - Passed: evidence, scope, owner gate
    - Watch: verification not run locally
    - Improvement: route to Product Experience earlier next time

Design constraints (all enforced here):

- **Additive & opt-in.** Off by default. The default runtime output is
  byte-for-byte unchanged unless the owner enables the footer
  (``display.self_audit_footer.enabled`` or ``MUSE_SELF_AUDIT_FOOTER=1``).
- **Deterministic & offline.** No model call on the hot path. The renderer
  consumes *already-available* dimension scores (from
  :func:`~hermes_cli.jarvis_prime.self_audit.judge.aggregate_dimensions` or an
  :class:`~hermes_cli.jarvis_prime.self_audit.report.AuditReport`). If the
  caller has no scores, it supplies them; this module never scores by calling
  a model.
- **Major turns only.** The gate helper only fires for substantive turns
  (effort class ``E3`` and up, i.e. full council / implementation / swarm),
  reusing the existing effort-class signal rather than inventing a new one.

This module mirrors the existing opt-in gateway runtime footer
(``gateway/runtime_footer.py``): a deterministic renderer plus a small
config/env resolver, gated so the default path is unchanged.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from hermes_cli.jarvis_prime.self_audit.judge import DimensionScore

# Environment override for the opt-in flag (mirrors MUSE_* runtime flags).
_ENV_FLAG = "MUSE_SELF_AUDIT_FOOTER"

# A dimension whose pass-rate is at or above this is reported as "Passed";
# anything below it (any failure) is a "Watch" line. This is a display
# threshold only; it never changes any gate or verdict.
_PASS_THRESHOLD = 1.0

# Human-readable labels for the Constitution's machine dimension names. Falls
# back to a de-underscored form for any dimension not listed (so a new
# dimension never breaks rendering).
_DIMENSION_LABELS: dict[str, str] = {
    "loyalty_and_honesty": "loyalty",
    "owner_gate_respect": "owner gate",
    "memory_integrity": "memory integrity",
    "safe_execution": "safe execution",
    "scope_discipline": "scope",
    "anti_reward_hacking": "anti-reward-hacking",
    "self_improvement_restraint": "self-improvement restraint",
    "communication_fit": "communication fit",
    # Common evidence/verification dimensions from the wider audit vocabulary,
    # included so those scores render with friendly labels when present.
    "evidence_grounding": "evidence",
    "verification_honesty": "verification",
    "agent_selection_quality": "agent selection",
}


def _label(dimension: str) -> str:
    """Human-readable label for a machine dimension name."""
    return _DIMENSION_LABELS.get(dimension, dimension.replace("_", " "))


def self_audit_footer_enabled(
    user_config: Mapping[str, Any] | None = None,
) -> bool:
    """Return whether the self-audit footer is enabled.

    Resolution (later wins):

    1. Built-in default — ``False``.
    2. ``display.self_audit_footer.enabled`` in the user config.
    3. The ``MUSE_SELF_AUDIT_FOOTER`` environment variable, when set to a
       truthy value (``1``/``true``/``yes``/``on``) or a falsy one.

    The default is OFF, so with no config and no env var this returns
    ``False`` and the runtime output is unchanged.
    """
    enabled = False

    display = (user_config or {}).get("display") if user_config else None
    if isinstance(display, Mapping):
        section = display.get("self_audit_footer")
        if isinstance(section, Mapping) and "enabled" in section:
            enabled = bool(section.get("enabled"))

    raw = os.environ.get(_ENV_FLAG)
    if raw is not None:
        enabled = raw.strip().lower() in {"1", "true", "yes", "on"}

    return enabled


def should_render_for_effort(effort: Any) -> bool:
    """Return whether a turn is "major" enough to carry a self-audit footer.

    Reuses the existing effort-class signal: only effort class ``E3`` and up
    (full council, deep-research/implementation runs, and owner-approved
    swarms) are substantive enough. Anything smaller (a direct answer or a
    single-lens turn) is trivial and gets no footer.

    Accepts an :class:`~hermes_cli.jarvis_prime.effort_class.EffortClass`, its
    string value (``"E3"``), or ``None`` (which is treated as trivial).
    """
    if effort is None:
        return False
    rank = getattr(effort, "rank", None)
    if rank is None:
        # Accept a bare string like "E3"/"e4".
        text = str(effort).strip().upper()
        if text.startswith("E") and text[1:].isdigit():
            rank = int(text[1:])
        else:
            return False
    return int(rank) >= 3


def _scores_from(source: Any) -> dict[str, "DimensionScore"]:
    """Coerce the accepted score inputs into a ``{dimension: DimensionScore}``.

    Accepts:

    - a mapping of ``dimension -> DimensionScore`` (already aggregated);
    - an :class:`AuditReport` (uses its ``dimension_scores()``);
    - anything exposing ``dimension_scores()``.
    """
    if source is None:
        return {}
    if isinstance(source, Mapping):
        return dict(source)
    getter = getattr(source, "dimension_scores", None)
    if callable(getter):
        return dict(getter())
    return {}


def render_self_audit_footer(
    scores: Any,
    *,
    improvement: Optional[str] = None,
    max_items: int = 4,
) -> str:
    """Render the concise 3-line self-audit footer, or ``""`` if there's nothing.

    ``scores`` is an already-available score object — a mapping of
    ``dimension -> DimensionScore`` (from
    :func:`~hermes_cli.jarvis_prime.self_audit.judge.aggregate_dimensions`) or
    an :class:`~hermes_cli.jarvis_prime.self_audit.report.AuditReport`. This is
    deterministic and performs **no model call**: it only reads scores the
    caller already has.

    Output shape (lines are omitted when empty)::

        Self-audit:
        - Passed: <dims that scored a full pass>
        - Watch: <dims with any failure>
        - Improvement: <caller-supplied one-liner>

    ``improvement`` is an optional caller-supplied one-line suggestion (e.g.
    "route to Product Experience earlier next time"). It is never derived from
    a model here.
    """
    resolved = _scores_from(scores)
    if not resolved and not improvement:
        return ""

    passed: list[str] = []
    watch: list[str] = []
    for dimension in sorted(resolved):
        score = resolved[dimension]
        value = getattr(score, "score", None)
        if value is None:
            continue
        if value >= _PASS_THRESHOLD:
            passed.append(_label(dimension))
        else:
            watch.append(_label(dimension))

    lines: list[str] = ["Self-audit:"]
    body: list[str] = []
    if passed:
        body.append(f"- Passed: {', '.join(passed[:max_items])}")
    if watch:
        body.append(f"- Watch: {', '.join(watch[:max_items])}")
    if improvement:
        body.append(f"- Improvement: {improvement.strip()}")

    if not body:
        return ""
    return "\n".join(lines + body)


def build_self_audit_footer(
    scores: Any,
    *,
    user_config: Mapping[str, Any] | None = None,
    effort: Any = None,
    improvement: Optional[str] = None,
    fields: Iterable[str] | None = None,  # reserved; accepted for parity
) -> str:
    """Top-level gated entry point for callers on the final-message seam.

    Returns the footer text, or ``""`` when:

    - the feature is disabled (the default), or
    - the turn is not major (``effort`` below ``E3`` when supplied), or
    - there are no scores and no improvement note to show.

    When ``effort`` is ``None`` the major-turn check is skipped (the caller has
    already decided the turn is substantive). Deterministic and offline.
    """
    if not self_audit_footer_enabled(user_config):
        return ""
    if effort is not None and not should_render_for_effort(effort):
        return ""
    return render_self_audit_footer(scores, improvement=improvement)
