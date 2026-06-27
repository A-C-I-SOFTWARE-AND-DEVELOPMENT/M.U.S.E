"""Deterministic post-generation OUTPUT-constraint validator for MUSE.

The task router (:mod:`hermes_cli.jarvis_prime.task_router`) DECIDES which model
runs a task class and DECLARES the per-class ``OutputConstraint``s. This module
is the enforcement half — commissioner recommendation #8 from the MUSE
verifiable arena: a single, deterministic, stdlib-only gate the surface layer
calls on a generated response *before* returning it.

Deterministic kinds (auto-checked; auto-fixed where it is safe to do so):

* ``max_words`` / ``max_sentences`` — over-limit output is trimmed to fit.
* ``min_words`` — under-limit output cannot be auto-grown, so it flags a
  *regenerate*.
* ``banned_phrases`` — a banned phrase cannot be safely rewritten without a
  model, so it flags a *regenerate*.

Advisory kinds (cannot be checked without another model call — reported back as
required actions for the caller to honor, never silently passed):

* ``verify_pass`` — run a verification pass with the target model.
* ``complexity_bar`` — escalate / verify a provable complexity bound.
* ``preserve_fidelity`` — preserve hedges / directions / calibration.

The validator NEVER raises on content; a host with no constraints for a task
class gets ``ok=True`` and the text unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from hermes_cli.jarvis_prime.task_router import (
    OutputConstraint,
    TaskClass,
    TASK_PROFILES,
)

# Banned-phrase class → case-insensitive patterns. Kept deliberately small and
# high-precision (low false-positive) — the goal is a floor, not a thesaurus.
_BANNED_PHRASE_CLASSES: dict[str, tuple[str, ...]] = {
    "therapy_speak": (
        r"\bi['’]?m here for you\b",
        r"\bi am here for you\b",
        r"\bhold(?:ing)? space\b",
        r"\bsit with (?:that|this|your|the)\b",
        r"\byour feelings are valid\b",
        r"\block in your feelings\b",
        r"\blean into (?:the|your|it|that)\b",
        r"\bshow up for yourself\b",
        r"\bdoing the work\b",
        r"\byou['’]?ve got this\b",
    ),
    "question_closer": (
        # Ends the whole reply on a question (emotional follow-up closer).
        r"\?\s*$",
    ),
}


def _words(text: str) -> list[str]:
    return text.split()


def _sentences(text: str) -> list[str]:
    """Split into sentences on terminal punctuation, keeping the punctuation."""
    parts = re.findall(r"[^.!?]*[.!?]+|\S[^.!?]*$", text.strip())
    return [p.strip() for p in parts if p.strip()]


@dataclass
class Violation:
    kind: str
    detail: str
    observed: Any
    limit: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "detail": self.detail,
                "observed": self.observed, "limit": self.limit}


@dataclass
class EnforcementResult:
    task_class: str
    ok: bool                       # final text passes all deterministic constraints
    text: str                      # possibly auto-fixed (trimmed) text
    original_text: str
    violations: list[Violation] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)            # auto-fixes applied
    required_actions: list[str] = field(default_factory=list)  # advisory kinds
    regenerate_recommended: bool = False  # a violation could not be safely fixed

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_class": self.task_class,
            "ok": self.ok,
            "text": self.text,
            "violations": [v.to_dict() for v in self.violations],
            "fixes": list(self.fixes),
            "required_actions": list(self.required_actions),
            "regenerate_recommended": self.regenerate_recommended,
            "changed": self.text != self.original_text,
        }


def constraints_for(task_class: "TaskClass | str") -> tuple[OutputConstraint, ...]:
    """The declared output constraints for ``task_class`` (empty if none/unknown)."""
    tc = task_class if isinstance(task_class, TaskClass) else TaskClass.from_value(task_class)
    profile = TASK_PROFILES.get(tc)
    return profile.output_constraints if profile else ()


def _truncate_words(text: str, limit: int) -> str:
    words = _words(text)
    if len(words) <= limit:
        return text
    return " ".join(words[:limit])


def _truncate_sentences(text: str, limit: int) -> str:
    sents = _sentences(text)
    if len(sents) <= limit:
        return text
    return " ".join(sents[:limit])


def enforce(
    task_class: "TaskClass | str",
    text: str,
    constraints: Optional[Sequence[OutputConstraint]] = None,
) -> EnforcementResult:
    """Validate (and where safe, auto-fix) ``text`` against a task class's constraints.

    ``constraints`` defaults to the task class's declared constraints; pass an
    explicit sequence (e.g. ``decision.output_constraints``) to avoid a second
    profile lookup. Returns an :class:`EnforcementResult`; never raises on
    content.
    """
    tc = task_class if isinstance(task_class, TaskClass) else TaskClass.from_value(task_class)
    cons = tuple(constraints) if constraints is not None else constraints_for(tc)

    result = EnforcementResult(task_class=tc.value, ok=True, text=text, original_text=text)
    if not cons:
        return result

    current = text
    for c in cons:
        if c.kind == "max_words":
            limit = int(c.param("limit", 0) or 0)
            n = len(_words(current))
            if limit and n > limit:
                result.violations.append(
                    Violation("max_words", c.detail, observed=n, limit=limit))
                current = _truncate_words(current, limit)
                result.fixes.append(f"max_words: trimmed {n}->{limit} words")
        elif c.kind == "max_sentences":
            limit = int(c.param("limit", 0) or 0)
            n = len(_sentences(current))
            if limit and n > limit:
                result.violations.append(
                    Violation("max_sentences", c.detail, observed=n, limit=limit))
                current = _truncate_sentences(current, limit)
                result.fixes.append(f"max_sentences: trimmed {n}->{limit} sentences")
        elif c.kind == "min_words":
            limit = int(c.param("limit", 0) or 0)
            n = len(_words(current))
            if limit and n < limit:
                result.violations.append(
                    Violation("min_words", c.detail, observed=n, limit=limit))
                result.regenerate_recommended = True  # cannot invent content
        elif c.kind == "banned_phrases":
            classes = c.param("classes", ()) or ()
            hits: list[str] = []
            for cls in classes:
                for pat in _BANNED_PHRASE_CLASSES.get(cls, ()):
                    if re.search(pat, current, flags=re.IGNORECASE | re.MULTILINE):
                        hits.append(cls)
                        break
            if hits:
                result.violations.append(
                    Violation("banned_phrases", c.detail, observed=sorted(set(hits)),
                              limit=list(classes)))
                result.regenerate_recommended = True  # cannot safely rewrite
        else:
            # Advisory kind (verify_pass / complexity_bar / preserve_fidelity).
            result.required_actions.append(f"[{c.kind}] {c.detail}")

    result.text = current
    # Final pass/fail: a deterministic violation that we could NOT auto-fix
    # (min_words / banned_phrases) means the text still fails.
    result.ok = not result.regenerate_recommended
    return result


__all__ = [
    "Violation",
    "EnforcementResult",
    "constraints_for",
    "enforce",
]
