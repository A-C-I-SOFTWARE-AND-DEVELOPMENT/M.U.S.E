"""Real JARVIS Prime chat responder for the cockpit chat endpoint.

Replaces ``jarvis_local_http.echo_responder`` with one that drives the
**actual** ``JarvisPrime`` runtime: it perceives, recollects relevant
memory, classifies the mode, decides a route, and surfaces owner-gated
actions — then streams that as the cockpit chunk vocabulary the Android
avatar already understands (``thinking`` / ``tone`` / ``working`` /
``body`` / ``detail`` / ``done`` / ``error``).

Prose generation is pluggable: pass a ``generate`` callable (e.g. wired to
the configured model router) to produce free-form text. When no model is
configured the responder still returns a *real* JARVIS turn — its mode,
routing rationale, recollected memory, and any pending owner gate — which
is genuine agent behaviour, not a canned echo.
"""

from __future__ import annotations

from typing import Callable, Iterator, Optional

from gateway.jarvis_local_http import body, detail, done, thinking, tone, working

# A prose generator turns (prompt, persona_prompt) into reply text.
ProseGenerator = Callable[[str, str], str]


_MODE_TONE = {
    "companion": "WARM",
    "strategy": "FOCUSED",
    "critic": "DIRECT",
    "operator": "FOCUSED",
    "builder": "FOCUSED",
    "mobile_voice": "BRISK",
}


def jarvis_responder(
    prompt: str,
    history: list[dict],
    *,
    generate: Optional[ProseGenerator] = None,
) -> Iterator[dict]:
    """Stream a real JARVIS Prime turn for ``prompt``.

    ``generate`` (optional) produces the reply prose from the prompt + the
    persona system prompt; when omitted, a turn-derived response is
    streamed. Never raises — failures degrade to an ``error`` chunk via the
    caller's stream framing.
    """
    yield thinking()

    from hermes_cli.jarvis_prime.runtime import JarvisPrime

    jp = JarvisPrime()
    turn = jp.handle(prompt, skip_perceive=True)

    mode = turn.classification.mode.value
    yield tone(_MODE_TONE.get(mode, "NEUTRAL"))

    route = turn.route
    if route.delegate_to:
        yield working(f"routing to {route.delegate_to}")
    elif route.target.value not in ("direct_answer",):
        yield working(route.target.value.replace("_", " "))

    # Owner-gated actions are surfaced explicitly — never executed here.
    if route.pending_actions:
        yield detail("Owner approval required for: " + ", ".join(route.pending_actions))

    persona_prompt = turn.persona_prompt.render()
    if generate is not None:
        try:
            text = generate(prompt, persona_prompt).strip()
        except Exception as exc:  # pragma: no cover - defensive
            text = f"(model generation unavailable: {exc}) " + _turn_summary(turn, mode)
    else:
        text = _turn_summary(turn, mode)

    if turn.recollection:
        yield detail(turn.recollection.splitlines()[0][:200])

    yield body(text)
    yield done()


def _turn_summary(turn, mode: str) -> str:
    """A real (non-echo) reply derived from the JARVIS turn when no model is wired."""
    lines = [
        f"JARVIS Prime — {mode} mode (confidence {turn.classification.confidence:.0%}).",
        turn.route.rationale,
    ]
    if turn.route.council_questions:
        lines.append("Questions to resolve first:")
        lines.extend(f"  • {q}" for q in turn.route.council_questions)
    if turn.research_brief is not None:
        lines.append(
            "I'd research this before answering rather than guess — "
            "confidence is below my floor."
        )
    return "\n".join(lines)


__all__ = ["ProseGenerator", "jarvis_responder"]
