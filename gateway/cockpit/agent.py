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
    # Adopted character persona ("make my avatar Goku") frames the whole reply.
    try:
        from gateway.cockpit.persona_store import persona_directive

        adopted = persona_directive()
        if adopted:
            persona_prompt = f"{adopted}\n\n{persona_prompt}"
    except Exception:  # persona is best-effort
        pass
    # Ground the reply in the owner profile + project references (bounded).
    try:
        from gateway.cockpit.grounding import reference_context

        refs = reference_context()
        if refs:
            persona_prompt = f"{persona_prompt}\n\n{refs}"
    except Exception:  # grounding is best-effort
        pass
    # Anti-hallucination: require citations/hedging in the reply (epistemic rule).
    try:
        from hermes_cli.jarvis_prime.epistemics import CITATION_REQUIRED_INSTRUCTION

        persona_prompt = f"{persona_prompt}\n\n{CITATION_REQUIRED_INSTRUCTION}"
    except Exception:
        pass
    # Natural stop-go cadence: pace this turn like a person, not a monologue.
    pacing = _pacing_directive(prompt)
    if pacing:
        persona_prompt = f"{persona_prompt}\n\n{pacing}"

    # Learn from explicit owner cues (secret-rejecting; surfaced, never silent).
    note = _maybe_remember(jp, prompt)
    if note:
        yield detail(note)

    if generate is not None:
        hint = _brain_hint(turn, mode)
        try:
            # Prefer the routing-aware 3-arg form; fall back for plain generators.
            try:
                text = generate(prompt, persona_prompt, hint).strip()
            except TypeError:
                text = generate(prompt, persona_prompt).strip()
        except Exception as exc:  # pragma: no cover - defensive
            text = f"(model generation unavailable: {exc}) " + _turn_summary(turn, mode)
    else:
        text = _turn_summary(turn, mode)

    if turn.recollection:
        yield detail(turn.recollection.splitlines()[0][:200])

    # Audit the generated prose; flag honestly if it reads as uncited/risky.
    caveat = _epistemic_caveat(jp, turn, text)
    if caveat:
        yield detail(caveat)

    yield body(text)
    yield done()


_REMEMBER_CUES = (
    "remember",
    "i prefer",
    "my name is",
    "note that",
    "for future",
    "don't forget",
    "keep in mind",
)


_CADENCE_HINT = {
    "BRIEF": "Keep it to a beat — one or two sentences, no preamble.",
    "NORMAL": "A few natural sentences; land the point, then stop.",
    "DEEP": "Go deeper here, but still in natural spoken paragraphs, not a wall.",
}


def _pacing_directive(prompt: str) -> str:
    """Turn the owner's pacing engine into a per-turn 'speak like a person'
    directive (stop-go cadence, length, posture) appended to the persona."""
    try:
        from hermes_cli.jarvis_prime import communication_style as cs

        ctx = cs.PacingContext(
            user_text_length=len(prompt or ""),
            surface="cockpit",
            topic_shift_signal=cs.is_topic_shift(prompt),
        )
        d = cs.decide_pacing(prompt, ctx)
        cadence = d.cadence.name
        posture = d.posture.name.lower()
        length = _CADENCE_HINT.get(cadence, "")
        lines = [
            "Conversational cadence (speak like a real person, not a chatbot):",
            f"- Posture: {posture}. Cadence: {cadence.lower()} "
            f"(aim ≤ {d.max_sentences} sentence(s)). {length}",
            "- Natural stop-go: if the user only acknowledged ('right', 'go on'), "
            "give a single beat and hand the floor back. Don't monologue.",
            "- It's fine to think out loud briefly, then commit — warm, direct, grounded.",
        ]
        return "\n".join(lines)
    except Exception:  # pacing is best-effort
        return ""


def _maybe_remember(jp, prompt: str) -> str:
    """Persist a durable memory when the owner explicitly asks to. Honest about
    rejection (secrets / below-floor) — returns a note only when stored."""
    low = prompt.lower()
    if not any(cue in low for cue in _REMEMBER_CUES):
        return ""
    try:
        rec = jp.config.memory.remember(
            key=prompt[:60], value=prompt, durability="durable", confidence=1.0
        )
        return "Noted to memory." if rec else ""
    except Exception:  # memory write is best-effort
        return ""


def _epistemic_caveat(jp, turn, text: str) -> str:
    """Run the anti-hallucination audit; return an honest caveat if not PASS."""
    try:
        report = jp.audit(text, confidence=turn.classification.confidence)
        if report.outcome.value != "pass":
            return (
                f"⚠ epistemic check: {report.outcome.value.replace('_', ' ')} "
                "— verify any specifics (paths/versions/links) before relying on them."
            )
    except Exception:
        pass
    return ""


_CODE_TARGETS = {
    "claude_code_builder",
    "codex_reviewer",
    "codex_bounded_fix",
    "local_test_runner",
    "github_pr_publisher",
}


def _brain_hint(turn, mode: str) -> dict:
    """Derive a routing hint from the JARVIS turn so the generator can switch
    brains: ``kind`` (chat/code/reasoning) + ``escalate`` (hard problem).

    This is how JARVIS "knows when to switch" — it reuses the turn's own
    classification (mode), route target, confidence, and research trigger.
    """
    target = getattr(getattr(turn.route, "target", None), "value", "") or ""
    confidence = float(getattr(turn.classification, "confidence", 1.0) or 1.0)
    escalate = (
        getattr(turn, "research_brief", None) is not None
        or target == "aos_council"
        or confidence < 0.5
    )
    if mode == "builder" or target in _CODE_TARGETS:
        kind = "code"
    elif mode in ("strategy", "critic") or escalate:
        kind = "reasoning"
    else:
        kind = "chat"
    return {
        "kind": kind,
        "escalate": escalate,
        "target": target,
        "mode": mode,
        "task_class": _task_class_for(turn, mode, target),
    }


# Map a JARVIS turn to one of the evidence-backed routing task classes, reusing
# the turn's own classification (mode/target/research). Returns a
# ``task_router.TaskClass`` value string the generator can route by.
def _task_class_for(turn, mode: str, target: str) -> str:
    if getattr(turn, "research_brief", None) is not None:
        return "research"
    if target == "codex_reviewer":
        return "coding_review"
    if target in ("local_test_runner", "codex_bounded_fix"):
        return "test_debug"
    if target == "claude_code_builder":
        return "coding_build"
    if mode == "builder" or target in _CODE_TARGETS:
        return "coding_plan"
    if mode == "mobile_voice":
        return "voice_reply"
    return "mobile_chat"


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
