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


def local_generate(prompt: str, persona: str) -> str:
    """Tier 1: reply from the running local model. Raises if none reachable."""
    base = _ollama_base()
    model = pick_model(base)
    text = ollama_generate(prompt, persona, model, base=base)
    if not text:
        raise RuntimeError(f"empty response from local model {model!r}")
    return text


# ---------------------------------------------------------------------------
# Tier 2 — all configured cloud / subscription brains (policy + fallback)
# ---------------------------------------------------------------------------


def policy_generate(prompt: str, persona: str, *, timeout: float = 120.0) -> str:
    """Tier 2: reply from the configured brains via the centralized LLM call.

    ``call_llm`` resolves the user's main provider + model and falls back
    across configured providers (Codex/ChatGPT, DeepSeek, Gemini, Anthropic,
    aggregators) on auth/credit errors. Lazy import so a pure-local Termux box
    without the OpenAI SDK still works via tier 1.
    """
    from agent.auxiliary_client import call_llm

    resp = call_llm(
        messages=[
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        timeout=timeout,
    )
    text = ((resp.choices[0].message.content) or "").strip()
    if not text:
        raise RuntimeError("empty response from configured model")
    return text


def default_prose_generator(prompt: str, persona: str) -> str:
    """Free-first: local model, then configured cloud/subscription brains.

    Raises only if *every* tier fails; the responder then degrades to the
    turn summary so chat never hard-fails.
    """
    try:
        return local_generate(prompt, persona)
    except Exception as local_exc:
        try:
            return policy_generate(prompt, persona)
        except Exception:
            raise local_exc


__all__ = [
    "default_prose_generator",
    "installed_chat_models",
    "local_generate",
    "ollama_generate",
    "pick_model",
    "policy_generate",
]
