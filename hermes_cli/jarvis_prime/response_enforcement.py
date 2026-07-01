"""Response-style enforcement — an OPT-IN, default-OFF, fail-open gate.

MUSE already *scores* a produced reply against two per-mode contracts:

- :mod:`hermes_cli.jarvis_prime.response_style` — the per-mode style validator
  (Mobile Voice brevity, Critic must object, Builder must ship a verification
  plan).
- :mod:`hermes_cli.jarvis_prime.challenge_contract` — the contrarian-duty
  detector (a non-trivial request must draw at least one challenge element).

Both are **pure inspection** and are wired *nowhere* on the hot path by default;
nothing rejects or regenerates a violating response. This module lands the
missing *enforcement* half as **additive, opt-in, default-OFF** infrastructure,
mirroring the merged gate pattern of
:func:`hermes_cli.jarvis_prime.tool_broker.tool_broker_enabled` and
:func:`hermes_cli.jarvis_prime.self_audit.footer.self_audit_footer_enabled`
exactly (built-in default ``False`` → config → env, env-non-empty wins, a
present-but-empty env defers to config).

It adds **no new detection logic**. :func:`evaluate_enforcement` only *composes*
the two existing detectors into one :class:`EnforcementCheck` and gates on it;
:func:`_corrective_nudge` turns a failing check into a short, deterministic
system-message string the caller may feed back into a bounded regenerate loop.

Design constraints (all enforced here):

- **Pure & deterministic & offline.** :func:`evaluate_enforcement` and
  :func:`_corrective_nudge` perform no model call, no I/O, and no randomness.
- **Fail-open by contract.** The gate defaults OFF; when off, the caller does
  ZERO new work. The evaluator itself never raises (malformed input →
  ``ok=True``, "nothing to enforce"), so a caller wrapping it can always keep
  the original response.
- **No new numbers / no new markers.** Every threshold and marker is reused from
  the two source modules; this file adds neither.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.challenge_contract import (
    ChallengeContractResult,
    classify_request_triviality,
    evaluate_challenge_contract,
)
from hermes_cli.jarvis_prime.modes import Mode
from hermes_cli.jarvis_prime.response_style import (
    StyleViolation,
    validate_response_style,
)

# Environment override for the opt-in gate (mirrors the MUSE_* flags on the
# other merged opt-in features: MUSE_TOOL_BROKER, MUSE_SELF_AUDIT_FOOTER).
_ENV_FLAG = "MUSE_STYLE_ENFORCEMENT"

# The regenerate loop is config-capped. The built-in default is a single
# regenerate attempt (one corrective retry); the hard ceiling is two, so an
# enabled deployment can never spin more than twice on a single turn.
DEFAULT_MAX_ATTEMPTS = 1
MAX_ATTEMPTS_CEILING = 2


@dataclass(frozen=True)
class EnforcementCheck:
    """The composed result of the two existing detectors.

    - ``ok`` — True when there is nothing to enforce (empty text, unknown mode
      with no bindable request) or when every consulted contract is satisfied.
    - ``mode`` — the mode value string the style check ran under (``""`` when
      style was skipped).
    - ``style_violations`` — the tuple of :class:`StyleViolation` from
      :func:`validate_response_style` (empty when style was skipped or clean).
    - ``challenge_violation`` — the :class:`ChallengeContractResult` when the
      challenge contract was consulted *and* failed, else ``None``.
    """

    ok: bool
    mode: str = ""
    style_violations: tuple[StyleViolation, ...] = field(default_factory=tuple)
    challenge_violation: Optional[ChallengeContractResult] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "mode": self.mode,
            "style_violations": [v.to_dict() for v in self.style_violations],
            "challenge_violation": (
                self.challenge_violation.to_dict()
                if self.challenge_violation is not None
                else None
            ),
        }


def style_enforcement_enabled(user_config: Mapping[str, Any] | None = None) -> bool:
    """Return whether the response-style enforcement loop is enabled (default OFF).

    Resolution (later wins), mirroring
    :func:`hermes_cli.jarvis_prime.tool_broker.tool_broker_enabled` verbatim
    (including the post-P1-11 present-but-empty-env guard):

    1. Built-in default — ``False`` (no enforcement; the default response path is
       byte-for-byte unchanged).
    2. ``response.style_enforcement.enabled`` in the user config.
    3. The ``MUSE_STYLE_ENFORCEMENT`` environment variable, when set to a
       *non-empty* truthy (``1``/``true``/``yes``/``on``) or falsy value. A
       present-but-empty (or whitespace-only) value means "not specified" and
       defers to config.

    With no config and no env var this returns ``False`` and no enforcement
    runs. Consulting this gate is the *only* thing a caller should do before
    doing any enforcement work, so the default path pays zero cost.
    """
    enabled = False

    response = (user_config or {}).get("response") if user_config else None
    if isinstance(response, Mapping):
        section = response.get("style_enforcement")
        if isinstance(section, Mapping) and "enabled" in section:
            enabled = bool(section.get("enabled"))

    raw = os.environ.get(_ENV_FLAG)
    if raw is not None and raw.strip():  # present-but-empty defers to config
        enabled = raw.strip().lower() in {"1", "true", "yes", "on"}

    return enabled


def resolve_max_attempts(user_config: Mapping[str, Any] | None = None) -> int:
    """Return the regenerate-attempt cap (default 1, hard-capped at 2).

    Reads ``response.style_enforcement.max_attempts`` from config when present,
    clamps it into ``[1, MAX_ATTEMPTS_CEILING]``, and otherwise returns
    :data:`DEFAULT_MAX_ATTEMPTS`. Malformed values fall back to the default. A
    single regenerate loop therefore never invokes the model more than
    ``max_attempts`` extra times.
    """
    value: Any = None
    response = (user_config or {}).get("response") if user_config else None
    if isinstance(response, Mapping):
        section = response.get("style_enforcement")
        if isinstance(section, Mapping):
            value = section.get("max_attempts")
    if value is None:
        return DEFAULT_MAX_ATTEMPTS
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MAX_ATTEMPTS
    if n < 1:
        return DEFAULT_MAX_ATTEMPTS
    return min(n, MAX_ATTEMPTS_CEILING)


def _coerce_mode(mode: Any) -> Optional[Mode]:
    """Coerce a Mode / its string value to a Mode; ``None`` if unrecognized."""
    if mode is None:
        return None
    if isinstance(mode, Mode):
        return mode
    text = str(mode).strip().lower()
    if not text:
        return None
    for candidate in Mode:
        if candidate.value == text:
            return candidate
    return None


def evaluate_enforcement(
    mode: Any,
    response_text: str,
    request_text: str = "",
    effort_class: Any = None,
) -> EnforcementCheck:
    """Compose the existing style + challenge detectors into one gated result.

    Pure, deterministic, offline: no model call, no I/O, no new detection logic.
    It only calls :func:`validate_response_style` and
    :func:`evaluate_challenge_contract` (with
    :func:`classify_request_triviality`) and folds the two into an
    :class:`EnforcementCheck`.

    Semantics:

    - Empty / whitespace-only ``response_text`` → ``ok=True`` (nothing to
      enforce). This is the fail-open floor.
    - A recognized ``mode`` → run the per-mode style validator on the reply.
    - An **unknown / ``None`` mode** → skip the style check entirely (stay
      conservative). The challenge contract may still run when a
      ``request_text`` is present, so a genuine yes-man reply to a non-trivial
      request is still caught even without a mode.
    - When ``request_text`` is present, classify its triviality and run the
      challenge contract on the reply; a non-trivial request answered with no
      challenge element is a violation. With no ``request_text`` the challenge
      contract is skipped (nothing to bind against).

    ``ok`` is True only when neither consulted contract produced a violation.
    """
    stripped_response = (response_text or "").strip()
    if not stripped_response:
        # Nothing produced to enforce — fail open.
        return EnforcementCheck(ok=True)

    resolved_mode = _coerce_mode(mode)
    mode_value = resolved_mode.value if resolved_mode is not None else ""

    # -- style (per-mode) — only when the mode is recognized ----------------
    style_violations: tuple[StyleViolation, ...] = ()
    if resolved_mode is not None:
        style_result = validate_response_style(
            resolved_mode,
            stripped_response,
            effort_class=effort_class,
        )
        style_violations = tuple(style_result.violations)

    # -- challenge (contrarian duty) — only when a request is present -------
    challenge_violation: Optional[ChallengeContractResult] = None
    stripped_request = (request_text or "").strip()
    if stripped_request:
        triviality = classify_request_triviality(
            stripped_request, effort_class=effort_class
        )
        challenge_result = evaluate_challenge_contract(
            stripped_response,
            request_is_trivial=triviality.value == "trivial",
        )
        if not challenge_result.satisfied:
            challenge_violation = challenge_result

    ok = not style_violations and challenge_violation is None
    return EnforcementCheck(
        ok=ok,
        mode=mode_value,
        style_violations=style_violations,
        challenge_violation=challenge_violation,
    )


# Per-violation corrective nudges. Stable, deterministic, no secrets / no PII —
# each names the specific violated contract so a regenerate turn can repair it.
_STYLE_NUDGES: dict[str, str] = {
    "mobile_voice_too_long": "Mobile Voice: keep it to <=2 sentences.",
    "critic_no_objection": (
        "Critic Mode: name at least one objection, risk, or point of pushback."
    ),
    "builder_no_verification": (
        "Builder Mode: state how the change will be verified (tests / "
        "validation / how it'll be checked)."
    ),
}

_CHALLENGE_NUDGE = (
    "Your reply must name at least one risk, counterproposal, or stronger "
    "version."
)


def _corrective_nudge(check: EnforcementCheck) -> str:
    """Return a short deterministic system message naming the violated contract.

    Composes one line per detected violation (style first, then the challenge
    contract). Returns ``""`` when ``check`` is ok (nothing to correct). No
    secrets, no PII — only the fixed contract-repair strings above.
    """
    if check.ok:
        return ""
    lines: list[str] = []
    seen: set[str] = set()
    for violation in check.style_violations:
        nudge = _STYLE_NUDGES.get(violation.code)
        if nudge and nudge not in seen:
            seen.add(nudge)
            lines.append(nudge)
    if check.challenge_violation is not None and _CHALLENGE_NUDGE not in seen:
        seen.add(_CHALLENGE_NUDGE)
        lines.append(_CHALLENGE_NUDGE)
    return "\n".join(lines)


__all__ = [
    "EnforcementCheck",
    "style_enforcement_enabled",
    "resolve_max_attempts",
    "evaluate_enforcement",
    "DEFAULT_MAX_ATTEMPTS",
    "MAX_ATTEMPTS_CEILING",
]
