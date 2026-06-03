"""Default prose generator for the cockpit chat responder.

Wires JARVIS's chat to the **configured brains, free-first**, so replies are
real model output instead of the mode-routing envelope. Two tiers, matching
the ``model_policy.json`` route order (local → cloud/subscription):

1. **Local model (Ollama)** — stdlib ``urllib`` only, so it works on Termux
   even without the OpenAI SDK. Asks Ollama what is *actually installed*
   (``/api/tags``) and picks a chat model, preferring a tag from
   ``model_policy.json`` when present. This covers local Qwen, DeepSeek-R1,
   etc., and survives the phone RAM-misdetect case (policy default never
   pulled while a smaller model was).
2. **All configured cloud/subscription brains** via
   :func:`agent.auxiliary_client.call_llm` — the centralized, policy-resolving
   call with automatic multi-provider fallback (Codex/ChatGPT, DeepSeek,
   Gemini, Anthropic, aggregators, …). Used when no local model is reachable.

Any total failure raises; :func:`gateway.cockpit.agent.jarvis_responder`
catches it and falls back to the turn summary, so chat never hard-fails.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Optional

# Substrings that mark an embedding / reranker model (not a chat model).
_EMBED_HINTS = ("embed", "bge", "rerank", "nomic")


# ---------------------------------------------------------------------------
# Tier 1 — local model via Ollama (stdlib only, Termux-safe)
# ---------------------------------------------------------------------------


def _ollama_base() -> str:
    """Ollama base URL — ``OLLAMA_HOST`` override, else the local default."""
    host = (os.environ.get("OLLAMA_HOST") or "").strip()
    if not host:
        return "http://127.0.0.1:11434"
    if not host.startswith("http"):
        host = "http://" + host
    return host.rstrip("/")


def _http_json(url: str, payload: Optional[dict] = None, *, timeout: float = 120.0) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (loopback)
        return json.loads(resp.read().decode("utf-8"))


def installed_chat_models(base: Optional[str] = None) -> list[str]:
    """Names of installed Ollama models, embeddings/rerankers filtered out."""
    base = base or _ollama_base()
    info = _http_json(f"{base}/api/tags", timeout=10.0)
    names = [m.get("name", "") for m in info.get("models", []) if m.get("name")]
    return [n for n in names if not any(h in n.lower() for h in _EMBED_HINTS)]


def _collect_ollama_tags(obj: Any, out: list[str]) -> None:
    """Recursively gather every ``ollama_tag`` value in the policy JSON."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "ollama_tag" and isinstance(v, str) and v:
                out.append(v)
            else:
                _collect_ollama_tags(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_ollama_tags(v, out)


def _policy_preferred_tags() -> list[str]:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    path = Path(base) / "jarvis_prime" / "model_policy.json"
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    tags: list[str] = []
    _collect_ollama_tags(cfg, tags)
    return tags


def pick_model(base: Optional[str] = None) -> str:
    """Choose the local chat model: a policy tag if installed, else first."""
    base = base or _ollama_base()
    installed = installed_chat_models(base)
    if not installed:
        raise RuntimeError("no local Ollama chat model installed")
    for tag in _policy_preferred_tags():
        if tag in installed:
            return tag
    return installed[0]


# Name fragments that mark a model as suited to a task kind. Lets JARVIS pick a
# coder model for code and a reasoning model for hard problems when several are
# installed locally — "knowing when to switch" within the local tier too.
_KIND_NAME_HINTS: dict[str, tuple[str, ...]] = {
    "code": ("coder", "code", "qwen3-coder"),
    "reasoning": ("r1", "deepseek", "reason", "think", "qwq"),
}


# Map a task class to the coarse local-selection ``kind`` used by the
# name-hint fallback when the routed model isn't installed locally.
_TASK_CLASS_KIND: dict[str, str] = {
    "coding_plan": "reasoning",
    "coding_build": "code",
    "coding_review": "code",
    "test_debug": "code",
    "research": "reasoning",
    "citation_verification": "reasoning",
    "memory_curator": "reasoning",
    "mobile_chat": "chat",
    "voice_reply": "chat",
    "summarization": "chat",
}


def _route_preference(task_class: str) -> tuple[Optional[str], str]:
    """Evidence-backed (preferred model, kind) for a task class.

    Defensive: any failure (no policy, stripped install) degrades to
    ``(None, kind)`` so generation still works via the name-hint fallback.
    """
    kind = _TASK_CLASS_KIND.get(task_class, "chat")
    try:
        from hermes_cli.jarvis_prime import task_router as tr

        decision = tr.route_for_task(task_class)
        return decision.chosen, kind
    except Exception:
        return None, kind


def select_local_model(
    installed: list[str], kind: str = "chat", preferred: Optional[str] = None
) -> str:
    """Pick the best installed local model for a task ``kind``.

    When ``preferred`` (the evidence-backed task-class route) is installed
    locally it wins; otherwise: code → a coder model; reasoning → a reasoning
    model (e.g. DeepSeek-R1); else a policy-preferred tag, else the first
    installed model. ``preferred`` is matched exactly first, then by substring
    (so a route of ``qwen3-coder`` matches an installed ``qwen3-coder:7b``).
    """
    if not installed:
        raise RuntimeError("no local Ollama chat model installed")
    if preferred:
        if preferred in installed:
            return preferred
        low = preferred.lower()
        for name in installed:
            if low in name.lower() or name.lower() in low:
                return name
    for frag in _KIND_NAME_HINTS.get(kind, ()):
        for name in installed:
            if frag in name.lower():
                return name
    for tag in _policy_preferred_tags():
        if tag in installed:
            return tag
    return installed[0]


def ollama_generate(
    prompt: str, persona: str, model: str, *, base: Optional[str] = None, timeout: float = 120.0
) -> str:
    base = base or _ollama_base()
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
    }
    out = _http_json(f"{base}/api/chat", payload, timeout=timeout)
    return ((out.get("message") or {}).get("content") or "").strip()


def local_generate(
    prompt: str, persona: str, *, kind: str = "chat", preferred: Optional[str] = None
) -> str:
    """Tier 1: reply from the running local model best-suited to ``kind``.

    ``preferred`` is the evidence-backed task-class route (from
    ``task_router``); when it is installed locally it is used, otherwise we
    fall back to the existing kind/name-hint selection — no behavior change
    when ``preferred`` is absent.
    """
    base = _ollama_base()
    model = select_local_model(installed_chat_models(base), kind, preferred=preferred)
    text = ollama_generate(prompt, persona, model, base=base)
    if not text:
        raise RuntimeError(f"empty response from local model {model!r}")
    return text


# ---------------------------------------------------------------------------
# Tier 2 — all configured cloud / subscription brains (policy + fallback)
# ---------------------------------------------------------------------------


def policy_generate(
    prompt: str, persona: str, *, task: Optional[str] = None, timeout: float = 120.0
) -> str:
    """Tier 2: reply from the configured brains via the centralized LLM call.

    ``call_llm`` resolves the user's main provider + model and falls back
    across configured providers (Codex/ChatGPT, DeepSeek, Gemini, Anthropic,
    aggregators) on auth/credit errors. ``task`` is a hint (e.g. ``"code"``)
    that lets config route the kind to a specific provider. Lazy import so a
    pure-local Termux box without the OpenAI SDK still works via tier 1.
    """
    from agent.auxiliary_client import call_llm

    kwargs: dict = {
        "messages": [
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        "timeout": timeout,
    }
    if task:
        kwargs["task"] = task
    resp = call_llm(**kwargs)
    text = ((resp.choices[0].message.content) or "").strip()
    if not text:
        raise RuntimeError("empty response from configured model")
    return text


def default_prose_generator(prompt: str, persona: str, hint: Optional[dict] = None) -> str:
    """Route to the right brain, then generate.

    ``hint`` (from the JARVIS turn) carries ``kind`` (``chat``/``code``/
    ``reasoning``), ``escalate`` (low confidence / council / research), and
    optionally ``task_class`` (a :class:`task_router.TaskClass` value). When a
    ``task_class`` is present the evidence-backed router picks the preferred
    model + refines the kind; the free-first local→cloud policy and all
    fallbacks are otherwise unchanged, so behavior is identical without it.
    """
    hint = hint or {}
    kind = str(hint.get("kind") or "chat")
    escalate = bool(hint.get("escalate"))

    preferred_model: Optional[str] = None
    task_class = hint.get("task_class")
    if task_class:
        preferred_model, routed_kind = _route_preference(str(task_class))
        if routed_kind:
            kind = routed_kind

    def _local() -> str:
        return local_generate(prompt, persona, kind=kind, preferred=preferred_model)

    def _cloud() -> str:
        return policy_generate(prompt, persona, task=kind if kind != "chat" else None)

    tiers = [_cloud, _local] if escalate else [_local, _cloud]
    last_exc: Optional[Exception] = None
    for tier in tiers:
        try:
            return tier()
        except Exception as exc:  # try the next brain
            last_exc = exc
    raise last_exc or RuntimeError("no brain available")


__all__ = [
    "default_prose_generator",
    "installed_chat_models",
    "local_generate",
    "ollama_generate",
    "pick_model",
    "policy_generate",
    "select_local_model",
]
