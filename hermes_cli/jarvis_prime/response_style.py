"""Per-mode response-style validator — a pure, opt-in post-hoc inspection.

MUSE classifies each turn into one of six :class:`~hermes_cli.jarvis_prime.modes.Mode`
values and injects a per-mode prompt style (see ``docs/jarvis-prime-operating-system.md``
§ Modes and constitution clauses C30–C32). The *input* side of that contract is
complete: :func:`~hermes_cli.jarvis_prime.communication_style.decide_pacing`
picks a cadence + ``max_sentences`` budget before a reply is composed, and the
persona prompt tells the model how each mode should sound.

What was missing (the vNext "adaptive-voice" residual, P3-3): nothing inspected
the *produced* response against its mode's style contract. This module closes
that gap as a **pure inspection function** — it measures an already-generated
reply and reports style violations. Examples:

* Mobile Voice that runs long (over the pacing ``max_sentences`` budget) →
  ``mobile_voice_too_long`` violation.
* Critic Mode with no objection / pushback → ``critic_no_objection`` violation.
* Builder Mode with no verification plan (no mention of tests / how it'll be
  checked) → ``builder_no_verification`` violation.
* Every other mode has no hard style rule here → always ``ok``.

Design constraints (all enforced here):

- **Pure & deterministic & offline.** :func:`validate_response_style` performs
  no model call, no I/O, and no randomness — it only reads the text it is
  handed and returns a structured result. Identical input ⇒ identical output.
- **Additive & default-inert.** This module changes no default behavior on its
  own. Any *enforcement* (rejecting or regenerating a reply based on a
  violation) is **opt-in and default OFF**, gated by
  :func:`style_validator_enabled` (config ``display.style_validator.enabled``
  or env ``MUSE_STYLE_VALIDATOR``). Mirrors the opt-in self-audit footer
  (``hermes_cli/jarvis_prime/self_audit/footer.py``).
- **Reuses existing thresholds.** The Mobile Voice length rule reuses the
  BRIEF-cadence ``max_sentences`` budget from
  :mod:`~hermes_cli.jarvis_prime.communication_style` rather than inventing a
  new number.

The validator is inspectable infra: it is wired *nowhere* on the hot response
path by default, so the default runtime output is byte-for-byte unchanged. A
caller that has opted in (via the gate helper) may consult it to decide whether
to regenerate; that decision is the caller's, not this module's.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.modes import Mode

# Environment override for the opt-in enforcement flag (mirrors MUSE_* flags).
_ENV_FLAG = "MUSE_STYLE_VALIDATOR"

# The Mobile Voice brevity budget. The BRIEF cadence in
# ``communication_style.decide_pacing`` caps a mobile/voice reply at 2
# sentences; a produced Mobile-Voice reply longer than that violates the
# contract. Sourced from the pacing logic so the two never drift.
DEFAULT_MOBILE_VOICE_MAX_SENTENCES = 2

# Word-count backstop for Mobile Voice (F3). Terminal-punctuation sentence
# counting alone is evadable: an unpunctuated run-on or a bullet list reads as a
# single "sentence" and slips past the cap. A reply over this many words is too
# long for Mobile Voice regardless of how it is punctuated. Sized so a genuinely
# brief 2-sentence reply comfortably passes but a padded run-on trips it.
DEFAULT_MOBILE_VOICE_MAX_WORDS = 40

# Objection / pushback markers for the Critic contract. Case-insensitive
# whole-word / whole-phrase signals (matched with word boundaries, see
# ``_compile_markers``) that the reply actually names a disagreement, risk, or
# counter-point rather than agreeing. Kept small and high-precision.
_OBJECTION_MARKERS: tuple[str, ...] = (
    "but ",
    "however",
    "risk",
    "disagree",
    "concern",
    "weakness",
    "flaw",
    "problem",
    "objection",
    "counter",
    "downside",
    "won't work",
    "wont work",
    "doesn't work",
    "doesnt work",
    "pushback",
    "the issue",
    "i'd push back",
    "id push back",
    "not convinced",
    "blind spot",
    "fails",
    "breaks",
    "caution",
    "watch out",
    "trade-off",
    "tradeoff",
    "on the other hand",
)

# Verification-plan markers for the Builder contract. Signals that the reply
# describes how the work will be checked (tests, validation, verification, CI).
_VERIFICATION_MARKERS: tuple[str, ...] = (
    "test",
    "tests",
    "verify",
    "verification",
    "validate",
    "validation",
    "assert",
    "pytest",
    "ci",
    "lint",
    "type check",
    "typecheck",
    "ty check",
    "ruff",
    "check that",
    "confirm that",
    "regression",
    "coverage",
    "smoke test",
    "sanity check",
    "how it'll be checked",
    "how it will be checked",
    "run the tests",
    "run tests",
)


@dataclass(frozen=True)
class StyleViolation:
    """A single per-mode style-contract violation.

    ``code`` is a stable machine identifier (e.g. ``mobile_voice_too_long``);
    ``message`` is a human-readable one-liner. ``observed``/``limit`` carry the
    measured value and threshold when the rule is quantitative (Mobile Voice
    length); they are ``None`` for presence rules (Critic / Builder).
    """

    code: str
    message: str
    observed: Any = None
    limit: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "observed": self.observed,
            "limit": self.limit,
        }


@dataclass(frozen=True)
class StyleValidationResult:
    """The structured result of inspecting a reply against its mode contract."""

    mode: str
    ok: bool
    violations: tuple[StyleViolation, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "violations": [v.to_dict() for v in self.violations],
        }


def _coerce_mode(mode: "Mode | str") -> Optional[Mode]:
    """Coerce a Mode or its string value to a Mode; ``None`` if unrecognized."""
    if isinstance(mode, Mode):
        return mode
    text = str(mode or "").strip().lower()
    for candidate in Mode:
        if candidate.value == text:
            return candidate
    return None


def _sentences(text: str) -> list[str]:
    """Split into sentences on terminal punctuation, keeping trailing fragments.

    Mirrors the sentence split used by ``output_validator._sentences`` so the
    Mobile-Voice length measurement matches the enforcement half's counting.
    """
    parts = re.findall(r"[^.!?]*[.!?]+|\S[^.!?]*$", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


# Apostrophe variants that must all fold to the straight ASCII apostrophe so a
# curly ``won't`` / ``it'll`` in polished output still matches an ASCII marker
# (F4). Covers U+2019 (right single quote), U+2018 (left), U+02BC (modifier
# letter apostrophe).
_APOSTROPHES = "’‘ʼ"
_APOSTROPHE_RE = re.compile("[" + _APOSTROPHES + "]")


def _normalize_apostrophes(text: str) -> str:
    """Fold curly / modifier apostrophes to a straight ASCII apostrophe."""
    return _APOSTROPHE_RE.sub("'", text or "")


def _compile_markers(markers: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    """Compile each marker into a word-boundary-aware, case-insensitive pattern.

    Plain substring matching false-positives short markers inside unrelated
    words (``ci`` in ``specificity``, ``test`` in ``protestation``, ``but`` in
    ``contribute``). Anchoring each marker with ``\\b`` on both sides makes a
    marker only count as a whole word / phrase. Multi-word markers still match
    across a normal space because ``re.escape`` preserves the literal space and
    the boundaries land on the outer edges of the phrase.
    """
    compiled: list[re.Pattern[str]] = []
    for marker in markers:
        stripped = _normalize_apostrophes(marker.strip())
        if not stripped:
            continue
        compiled.append(
            re.compile(r"\b" + re.escape(stripped) + r"\b", re.IGNORECASE)
        )
    return tuple(compiled)


_OBJECTION_PATTERNS: tuple[re.Pattern[str], ...] = _compile_markers(_OBJECTION_MARKERS)
_VERIFICATION_PATTERNS: tuple[re.Pattern[str], ...] = _compile_markers(
    _VERIFICATION_MARKERS
)


def _has_marker(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    low = _normalize_apostrophes(text or "")
    return any(pattern.search(low) for pattern in patterns)


def validate_response_style(
    mode: "Mode | str",
    text: str,
    *,
    effort_class: Any = None,  # accepted for parity / future rules; unused today
    mobile_voice_max_sentences: int = DEFAULT_MOBILE_VOICE_MAX_SENTENCES,
    mobile_voice_max_words: int = DEFAULT_MOBILE_VOICE_MAX_WORDS,
) -> StyleValidationResult:
    """Inspect an already-generated ``text`` against ``mode``'s style contract.

    Pure, deterministic, offline: no model call, no I/O. Returns a
    :class:`StyleValidationResult` listing any :class:`StyleViolation`. An empty
    / whitespace-only reply, an unrecognized mode, or a mode with no hard style
    rule all return ``ok=True`` with no violations.

    Rules (one per styled mode):

    - **Mobile Voice** — brevity. A reply exceeding ``mobile_voice_max_sentences``
      (default 2, the BRIEF-cadence budget) → ``mobile_voice_too_long``. A
      length backstop also flags a reply whose word count exceeds
      ``mobile_voice_max_words`` (default 40) or whose newline-delimited line
      count exceeds the sentence budget — so an unpunctuated run-on or a bullet
      list cannot evade the cap by reading as a single "sentence".
    - **Critic** — must push back. A reply with no objection marker →
      ``critic_no_objection``.
    - **Builder** — must ship a verification plan. A reply that never mentions
      tests / validation / verification → ``builder_no_verification``.
    - **Companion / Strategy / Operator** — no hard rule; always ``ok``.

    ``effort_class`` is accepted for signature parity with the other MUSE
    inspection helpers and to allow future effort-aware rules; it does not
    affect the current rules.
    """
    resolved = _coerce_mode(mode)
    mode_value = resolved.value if resolved is not None else str(mode or "")
    violations: list[StyleViolation] = []

    stripped = (text or "").strip()
    if resolved is None or not stripped:
        # Unknown mode or empty text: nothing to measure. Inspection only.
        return StyleValidationResult(mode=mode_value, ok=True, violations=())

    if resolved is Mode.MOBILE_VOICE:
        n = len(_sentences(stripped))
        limit = int(mobile_voice_max_sentences)
        # Backstop (F3): terminal-punctuation sentence counting is evadable —
        # an unpunctuated run-on or a bullet list reads as one "sentence". Also
        # measure raw word count and newline-delimited line count so neither
        # slips past the cap.
        word_count = len(stripped.split())
        word_limit = int(mobile_voice_max_words)
        line_count = len([ln for ln in stripped.splitlines() if ln.strip()])

        too_many_sentences = limit > 0 and n > limit
        too_many_words = word_limit > 0 and word_count > word_limit
        too_many_lines = limit > 0 and line_count > limit

        if too_many_sentences or too_many_words or too_many_lines:
            # Report the most representative measure/limit pair: prefer the
            # sentence overflow (the primary rule), else the word backstop, else
            # the line backstop.
            if too_many_sentences:
                observed, obs_limit, unit = n, limit, "sentences"
            elif too_many_words:
                observed, obs_limit, unit = word_count, word_limit, "words"
            else:
                observed, obs_limit, unit = line_count, limit, "lines"
            violations.append(
                StyleViolation(
                    code="mobile_voice_too_long",
                    message=(
                        f"Mobile Voice reply has {observed} {unit}; the brevity "
                        f"budget is {obs_limit}."
                    ),
                    observed=observed,
                    limit=obs_limit,
                )
            )
    elif resolved is Mode.CRITIC:
        if not _has_marker(stripped, _OBJECTION_PATTERNS):
            violations.append(
                StyleViolation(
                    code="critic_no_objection",
                    message=(
                        "Critic Mode reply names no objection, risk, or "
                        "pushback."
                    ),
                )
            )
    elif resolved is Mode.BUILDER:
        if not _has_marker(stripped, _VERIFICATION_PATTERNS):
            violations.append(
                StyleViolation(
                    code="builder_no_verification",
                    message=(
                        "Builder Mode reply describes no verification plan "
                        "(tests / validation / how it'll be checked)."
                    ),
                )
            )
    # COMPANION / STRATEGY / OPERATOR: no hard style rule -> always ok.

    return StyleValidationResult(
        mode=mode_value,
        ok=not violations,
        violations=tuple(violations),
    )


def style_validator_enabled(
    user_config: Mapping[str, Any] | None = None,
) -> bool:
    """Return whether style-validator ENFORCEMENT is enabled (default OFF).

    Resolution (later wins):

    1. Built-in default — ``False`` (enforcement off; validator stays pure infra).
    2. ``display.style_validator.enabled`` in the user config.
    3. The ``MUSE_STYLE_VALIDATOR`` environment variable, when set to a truthy
       value (``1``/``true``/``yes``/``on``) or a falsy one.

    The default is OFF, so with no config and no env var this returns ``False``
    and no enforcement runs — the default runtime output is unchanged. This gates
    *enforcement only*; :func:`validate_response_style` itself is always safe to
    call (it is a pure inspection function that changes nothing).
    """
    enabled = False

    display = (user_config or {}).get("display") if user_config else None
    if isinstance(display, Mapping):
        section = display.get("style_validator")
        if isinstance(section, Mapping) and "enabled" in section:
            enabled = bool(section.get("enabled"))

    raw = os.environ.get(_ENV_FLAG)
    if raw is not None:
        enabled = raw.strip().lower() in {"1", "true", "yes", "on"}

    return enabled


__all__ = [
    "StyleViolation",
    "StyleValidationResult",
    "validate_response_style",
    "style_validator_enabled",
    "DEFAULT_MOBILE_VOICE_MAX_SENTENCES",
    "DEFAULT_MOBILE_VOICE_MAX_WORDS",
]
