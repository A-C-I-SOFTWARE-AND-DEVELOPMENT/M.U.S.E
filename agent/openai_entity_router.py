"""Split OpenAI GPT chat and Codex into two routable entities.

The ChatGPT OAuth (``openai-codex``) provider historically fused *every*
model — pure GPT chat models like ``gpt-5.5`` *and* coding models like
``gpt-5.3-codex`` — into a single runtime that always spoke to the Codex
responses backend. That meant plain conversation and coding both rode the
same model slug and the same quota.

This module makes them two **entities** under the same credentials/endpoint:

* the **chat** entity — a GPT model you talk to by default, and
* the **codex** entity — a coding model the agent auto-switches to when a
  turn is about engineering / tool work.

Everything here is pure (no I/O, no agent mutation) so it is trivially unit
tested. The conversation loop calls :func:`select_turn_model` once per user
turn and swaps ``agent.model`` accordingly; provider, base_url, api_mode and
credentials are identical for both entities, so only the model slug changes.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

# A Codex coding model carries the ``-codex`` marker in its slug
# (gpt-5.3-codex, gpt-5.2-codex, gpt-5.1-codex-max, gpt-5.3-codex-spark, …).
_CODEX_MARKER = "-codex"

# Sensible fallbacks when config / live discovery can't supply one.
DEFAULT_CHAT_MODEL = "gpt-5.5"
DEFAULT_CODEX_MODEL = "gpt-5.3-codex"


def is_codex_model(model: Optional[str]) -> bool:
    """True when ``model`` is a Codex coding slug (contains ``-codex``)."""
    return _CODEX_MARKER in (model or "").strip().lower()


def is_gpt_chat_model(model: Optional[str]) -> bool:
    """True when ``model`` is a GPT chat slug (``gpt-…`` and *not* Codex)."""
    slug = (model or "").strip().lower()
    return slug.startswith("gpt-") and not is_codex_model(slug)


def split_model_ids(models: Iterable[str]) -> Tuple[List[str], List[str]]:
    """Partition a mixed model list into (gpt_chat_models, codex_models).

    Order is preserved within each bucket; non-GPT/non-Codex slugs are
    dropped (they belong to neither entity).
    """
    chat: List[str] = []
    codex: List[str] = []
    for model in models:
        if not isinstance(model, str) or not model.strip():
            continue
        slug = model.strip()
        if is_codex_model(slug):
            codex.append(slug)
        elif is_gpt_chat_model(slug):
            chat.append(slug)
    return chat, codex


# ── Coding-intent classification ────────────────────────────────────────────
# These signals decide whether a user turn is "code" work (route to Codex),
# plain "chat" (route to GPT), or "ambiguous" (keep the previous entity).

# Strong lexical signals that a turn is engineering / tool work.
_CODE_KEYWORDS = (
    r"refactor", r"debug", r"compile", r"stack ?trace", r"traceback",
    r"implement", r"function", r"class\b", r"method\b", r"variable",
    r"\bbug\b", r"\bfix\b", r"\berror\b", r"\bexception\b", r"\bcrash\b",
    r"\bcode\b", r"\bscript\b", r"\bapi\b", r"\bsdk\b", r"\bregex\b",
    r"unit ?test", r"\btests?\b", r"\bpytest\b", r"\blint\b", r"\bbuild\b",
    r"\bdeploy\b", r"\bcommit\b", r"\bpull request\b", r"\bpr\b",
    r"\bgit\b", r"\bmerge\b", r"\brebase\b", r"\bdiff\b", r"\bpatch\b",
    r"\brepo(sitory)?\b", r"\bcodebase\b", r"\bbranch\b",
    r"\bdockerfile\b", r"\bkubernetes\b", r"\bterraform\b",
    r"\bdatabase\b", r"\bschema\b", r"\bquery\b", r"\bendpoint\b",
    r"\bnpm\b", r"\bpip\b", r"\buv run\b", r"\bcargo\b", r"\bmakefile\b",
    r"write (me )?(a |an )?(python|javascript|typescript|rust|go|java|c\+\+|bash|shell|sql)",
)

# Programming languages / ecosystems that imply coding when named.
_CODE_LANGS = (
    r"python", r"javascript", r"typescript", r"\brust\b", r"\bgolang\b",
    r"\bjava\b", r"\bkotlin\b", r"\bswift\b", r"\bc\+\+\b", r"\bc#\b",
    r"\bbash\b", r"\bshell\b", r"\bsql\b", r"react", r"\bnode\b",
    r"django", r"flask", r"fastapi", r"\bnext\.?js\b",
)

# File-path / extension signals (e.g. ``run_agent.py``, ``src/app.tsx``).
_FILE_PATH = re.compile(
    r"[\w./~-]+\.(py|js|ts|tsx|jsx|rs|go|java|kt|swift|cpp|cc|h|hpp|cs|rb|"
    r"php|sh|bash|sql|yaml|yml|toml|json|md|html|css|scss)\b",
    re.IGNORECASE,
)

# A fenced code block or inline shell prompt is an unambiguous code signal.
_CODE_FENCE = re.compile(r"```|^\s*\$\s+\S", re.MULTILINE)

_CODE_KEYWORD_RE = re.compile("|".join(_CODE_KEYWORDS), re.IGNORECASE)
_CODE_LANG_RE = re.compile("|".join(_CODE_LANGS), re.IGNORECASE)

# Plain-chat signals: short greetings / meta questions that should *not*
# drag the conversation into Codex on their own.
_CHAT_ONLY_RE = re.compile(
    r"^\s*(hi|hey|hello|thanks|thank you|yo|sup|good (morning|afternoon|evening)|"
    r"how are you|who are you|what can you do|tell me about yourself)\b",
    re.IGNORECASE,
)


def classify_intent(text: Optional[str]) -> str:
    """Classify a user message as ``"code"``, ``"chat"`` or ``"ambiguous"``.

    The classifier is deliberately conservative: it only commits to
    ``"chat"`` for clear small-talk, and to ``"code"`` when an engineering
    signal is present. Everything else is ``"ambiguous"`` so the caller can
    keep the conversation's current entity (stickiness).
    """
    raw = (text or "").strip()
    if not raw:
        return "ambiguous"

    has_code_signal = bool(
        _CODE_FENCE.search(raw)
        or _FILE_PATH.search(raw)
        or _CODE_KEYWORD_RE.search(raw)
        or _CODE_LANG_RE.search(raw)
    )
    if has_code_signal:
        return "code"

    # No code signal at all + a clear small-talk opener ⇒ chat.
    if _CHAT_ONLY_RE.search(raw):
        return "chat"

    return "ambiguous"


def resolve_entity_models(
    *,
    default_model: Optional[str],
    chat_model: Optional[str] = None,
    codex_model: Optional[str] = None,
    available_models: Optional[Iterable[str]] = None,
) -> Tuple[str, str]:
    """Resolve the (chat_model, codex_model) pair for the two entities.

    Resolution favours explicit config, then the persisted default (placed
    in the bucket it belongs to), then live/curated discovery, then the
    hard-coded fallbacks. Always returns two non-empty, distinct-by-bucket
    slugs.
    """
    available = [m for m in (available_models or []) if isinstance(m, str) and m.strip()]
    disc_chat, disc_codex = split_model_ids(available)

    default_model = (default_model or "").strip()

    # Chat entity: explicit config > default (if it's a chat slug) >
    # discovered chat model > fallback.
    resolved_chat = (chat_model or "").strip()
    if not resolved_chat and is_gpt_chat_model(default_model):
        resolved_chat = default_model
    if not resolved_chat and disc_chat:
        resolved_chat = disc_chat[0]
    if not resolved_chat:
        resolved_chat = DEFAULT_CHAT_MODEL

    # Codex entity: explicit config > default (if it's a codex slug) >
    # discovered codex model > fallback.
    resolved_codex = (codex_model or "").strip()
    if not resolved_codex and is_codex_model(default_model):
        resolved_codex = default_model
    if not resolved_codex and disc_codex:
        resolved_codex = disc_codex[0]
    if not resolved_codex:
        resolved_codex = DEFAULT_CODEX_MODEL

    return resolved_chat, resolved_codex


def select_turn_model(
    *,
    user_text: Optional[str],
    chat_model: str,
    codex_model: str,
    previous_entity: Optional[str] = None,
) -> Tuple[str, str]:
    """Pick the model + entity for a single user turn.

    * a ``"code"`` intent ⇒ the Codex entity,
    * a ``"chat"`` intent ⇒ the GPT chat entity,
    * ``"ambiguous"`` ⇒ stay on ``previous_entity`` (defaulting to chat),

    Returns ``(model, entity)`` where ``entity`` is ``"chat"`` or ``"code"``.
    """
    intent = classify_intent(user_text)
    if intent == "ambiguous":
        entity = previous_entity if previous_entity in {"chat", "code"} else "chat"
    else:
        entity = intent

    if entity == "code":
        return codex_model, "code"
    return chat_model, "chat"
