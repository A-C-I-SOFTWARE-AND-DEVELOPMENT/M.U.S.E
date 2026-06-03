"""Custom avatar persona — "make my avatar Goku" → research + adopt a personality.

The owner describes a character ("Goku from Dragon Ball", "a sarcastic cat",
"a Victorian butler"); the configured model researches it from its knowledge and
writes a **persona directive** that the chat layers on top of JARVIS — so the
companion speaks and behaves in character while staying genuinely helpful and
capable. Persisted under ``${HERMES_HOME}/jarvis_prime/avatar_persona.json`` and
injected into every chat turn by :mod:`gateway.cockpit.agent`.

Stdlib at import; the model call is lazy so this loads under slim installs.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

_SYSTEM = (
    "You write a concise SYSTEM-PERSONA for an AI companion that takes on a "
    "character the user names. Draw on your knowledge of the character — their "
    "world, personality, speech style, catchphrases, values, and quirks. Output "
    "ONLY the persona directive, addressed in second person ('You are …'), 4–8 "
    "sentences, designed to layer on top of a helpful, capable assistant: stay "
    "genuinely useful, just in character. No preamble, no markdown headings."
)


def persona_path() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jarvis_prime" / "avatar_persona.json"


def load_persona() -> Optional[dict]:
    try:
        return json.loads(persona_path().read_text(encoding="utf-8"))
    except Exception:
        return None


def save_persona(data: dict) -> None:
    p = persona_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def clear_persona() -> None:
    try:
        persona_path().unlink()
    except FileNotFoundError:
        pass


def generate_persona(description: str, *, name: str = "") -> dict:
    """Research the described character and write+persist a persona directive.

    Uses the configured model (which knows the character); falls back to a
    plain directive when no model is reachable, so it never hard-fails.
    """
    desc = (description or "").strip()
    if not desc:
        raise ValueError("a character description is required")

    persona_prompt = ""
    try:
        from agent.auxiliary_client import call_llm

        resp = call_llm(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"Character to embody: {desc}"},
            ],
            timeout=60,
        )
        persona_prompt = ((resp.choices[0].message.content) or "").strip()
    except Exception:
        persona_prompt = ""

    generated = bool(persona_prompt)
    if not persona_prompt:
        # Honest fallback when no model is configured (the runtime will generate
        # a richer, researched persona once a brain is available).
        persona_prompt = (
            f"You take on the character described as: {desc}. Embody their "
            "personality, voice, mannerisms, and catchphrases while staying "
            "genuinely helpful and capable."
        )

    data = {
        "name": (name or desc[:48]).strip(),
        "description": desc,
        "persona_prompt": persona_prompt,
        "generated": generated,
        "created_at": time.time(),
    }
    save_persona(data)
    return data


def persona_directive() -> str:
    """Injectable directive for the chat persona, or '' when none is set."""
    p = load_persona()
    if not p:
        return ""
    name = (p.get("name") or "your character").strip()
    body = (p.get("persona_prompt") or "").strip()
    if not body:
        return ""
    return f"Adopted persona — speak and behave as {name}:\n{body}"


__all__ = [
    "clear_persona",
    "generate_persona",
    "load_persona",
    "persona_directive",
    "persona_path",
    "save_persona",
]
