"""Local Ollama adapters — run the LLM-heavy studio stages on this device, free.

Endpoints: http://localhost:11434/v1/chat/completions (OpenAI-compatible).

Model routing (per ~/AppData/Local/hermes notes):
    gemma4:12b        → default narrative LLM (script, treatments, dialogue)
    gpt-oss:20b       → reasoning / world-bible / GDD systems design
    qwen3-coder:30b   → engine code / shaders / gameplay scripts
    qwen3.5:9b        → multimodal captioning / quick passes
    Qwythos-9B        → the project's own fine-tune (fusion-tuned default)

Each adapter is registered at priority 80 (higher than OpenRouter's 50),
so when Ollama is reachable, it wins. When Ollama is offline, it
gracefully fails over to the OpenRouter / stub adapters already present.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import List

from agent.studio.adapters.base import Adapter, default_registry
from agent.studio.types import Provider


OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def _ollama_chat(model: str, system: str, user: str,
                 max_tokens: int = 4096, timeout: float = 300.0) -> str:
    """Call Ollama's /api/chat. Returns text content.

    - Pins num_ctx (default 4096) so reasoning models don't default to 131k.
    - Forces num_gpu (default 999) so all layers offload to GPU when CUDA is present.
    - Disables thinking-mode for reasoning models (qwen3.5, gpt-oss) so
      output lands in `message.content` instead of `message.thinking`.
    - Falls back to `thinking` field if `content` is empty (truncated reasoning).
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": False,  # disable reasoning mode (Ollama 0.30+)
        "options": {
            "num_ctx": int(os.environ.get("AXIOM_NUM_CTX", "4096")),
            "num_predict": max_tokens,
            "num_gpu": int(os.environ.get("AXIOM_NUM_GPU", "999")),
            "temperature": 0.7,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    msg = data.get("message", {})
    content = msg.get("content", "").strip()
    if not content:
        # Reasoning model truncated before final answer — return raw thinking
        content = msg.get("thinking", "").strip()
    return content


def _ollama_available() -> bool:
    """Probe /api/tags. Cached for 60s to avoid hammering the daemon.

    Pinned-offline (``AXIOM_STUDIO_OFFLINE``) short-circuits to False so the
    hermetic pipeline tests stub these key-less local LLM stages instead of
    hitting a dev's running Ollama daemon. Production/unit tests leave it unset.
    """
    if os.environ.get("AXIOM_STUDIO_OFFLINE", "").strip().lower() in (
        "1", "true", "yes", "on"
    ):
        return False
    cache = getattr(_ollama_available, "_cache", None)
    now = time.time()
    if cache and now - cache[0] < 60:
        return cache[1]
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0) as r:
            ok = r.status == 200
    except Exception:
        ok = False
    _ollama_available._cache = (now, ok)  # type: ignore[attr-defined]
    return ok


def _save(workdir: Path, name: str, text: str) -> str:
    workdir.mkdir(parents=True, exist_ok=True)
    p = workdir / name
    p.write_text(text, encoding="utf-8")
    return str(p)


# ── Script / screenplay (narrative LLM) ─────────────────────────────

class OllamaScriptAdapter(Adapter):
    """Local screenplay / treatment generator. Free, runs on your GPU."""
    capability = "script"
    provider = Provider.OLLAMA_LOCAL
    requires_env: List[str] = []
    est_unit_cost_usd = 0.0

    def available(self) -> bool:
        return _ollama_available()

    def _real(self, prompt: str, workdir: Path, **kwargs):
        model = kwargs.get("ollama_model", "gemma4:12b")
        system = (
            "You are an award-winning screenwriter. Produce industry-standard "
            "screenplay format (Fountain or standard slugline / action / "
            "character / dialogue blocks). Be concrete, cinematic, character-driven."
        )
        text = _ollama_chat(model, system, prompt,
                            max_tokens=kwargs.get("max_tokens", 6000))
        out = _save(workdir, f"script_{int(time.time())}.md", text)
        return [out], f"{len(text)} chars via {model}"


# ── Game Design Document / world bible (reasoning LLM) ──────────────

class OllamaGDDAdapter(Adapter):
    """Local GDD / world-bible generator using gpt-oss reasoning model."""
    capability = "gdd"
    provider = Provider.OLLAMA_LOCAL
    requires_env: List[str] = []
    est_unit_cost_usd = 0.0

    def available(self) -> bool:
        return _ollama_available()

    def _real(self, prompt: str, workdir: Path, **kwargs):
        model = kwargs.get("ollama_model", "gpt-oss:20b")
        system = (
            "You are a senior game designer at a AAA studio. Produce a complete "
            "Game Design Document covering: high concept, core gameplay loop, "
            "world / setting bible, faction & character roster, level / mission "
            "structure, progression systems, narrative beats, monetization model, "
            "target platforms, tech stack, and a 12-month milestone schedule. "
            "Use clear Markdown headings."
        )
        text = _ollama_chat(model, system, prompt,
                            max_tokens=kwargs.get("max_tokens", 8000))
        out = _save(workdir, f"gdd_{int(time.time())}.md", text)
        return [out], f"{len(text)} chars GDD via {model}"


# ── World bible (used by film + game) ───────────────────────────────

class OllamaWorldBibleAdapter(Adapter):
    """Setting / lore bible — locations, history, cultures, magic / tech rules."""
    capability = "world_bible"
    provider = Provider.OLLAMA_LOCAL
    requires_env: List[str] = []
    est_unit_cost_usd = 0.0

    def available(self) -> bool:
        return _ollama_available()

    def _real(self, prompt: str, workdir: Path, **kwargs):
        model = kwargs.get("ollama_model", "gpt-oss:20b")
        system = (
            "You are a world-building consultant trained on the methodologies of "
            "Tolkien, Sapkowski, Martin, Le Guin, Miyazaki, and modern open-world "
            "game design. Produce a rigorous world bible: cosmology, geography, "
            "history (3 eras), ~6 factions with conflicts, 5 cultures with rituals, "
            "the central mystery / theme, and 10 hook locations with sensory detail."
        )
        text = _ollama_chat(model, system, prompt,
                            max_tokens=kwargs.get("max_tokens", 8000))
        out = _save(workdir, f"world_bible_{int(time.time())}.md", text)
        return [out], f"{len(text)} chars world bible via {model}"


# ── Dialogue generation (character voice / NPC barks) ───────────────

class OllamaDialogueAdapter(Adapter):
    """Per-character dialogue lines, barks, branching trees."""
    capability = "dialogue_text"
    provider = Provider.OLLAMA_LOCAL
    requires_env: List[str] = []
    est_unit_cost_usd = 0.0

    def available(self) -> bool:
        return _ollama_available()

    def _real(self, prompt: str, workdir: Path, **kwargs):
        model = kwargs.get("ollama_model", "gemma4:12b")
        system = (
            "You are a dialogue writer. Output JSON-lines, one per line, "
            "with shape {\"character\":\"NAME\",\"emotion\":\"...\","
            "\"line\":\"...\",\"tags\":[\"bark|cinematic|branching\"]}. "
            "Voice each character distinctly: vocabulary, rhythm, idiom."
        )
        text = _ollama_chat(model, system, prompt,
                            max_tokens=kwargs.get("max_tokens", 4000))
        out = _save(workdir, f"dialogue_{int(time.time())}.jsonl", text)
        return [out], f"{len(text)} chars dialogue via {model}"


# ── Gameplay / engine code (coder LLM) ──────────────────────────────

class OllamaGameplayCodeAdapter(Adapter):
    """C++ / Blueprint / C# / GDScript starter modules for the engine project."""
    capability = "gameplay_code"
    provider = Provider.OLLAMA_LOCAL
    requires_env: List[str] = []
    est_unit_cost_usd = 0.0

    def available(self) -> bool:
        return _ollama_available()

    def _real(self, prompt: str, workdir: Path, **kwargs):
        model = kwargs.get("ollama_model", "qwen3-coder:30b")
        engine = kwargs.get("engine", "ue5")
        lang = {"ue5": "C++ (UE5)", "unity": "C# (Unity 6)",
                "godot": "GDScript (Godot 4)"}.get(engine, "C++")
        system = (
            f"You are a senior {engine} engine programmer. Generate a "
            f"compilable starter module in {lang} implementing the requested "
            f"gameplay system. Include header + source, follow engine idioms, "
            f"comment public APIs. Output as fenced code blocks, one per file, "
            f"with the filename on the line before each block."
        )
        text = _ollama_chat(model, system, prompt,
                            max_tokens=kwargs.get("max_tokens", 6000))
        out = _save(workdir, f"gameplay_{engine}_{int(time.time())}.md", text)
        return [out], f"{len(text)} chars {engine} code via {model}"


# ── Shot list / scene breakdown (for film pipeline) ─────────────────

class OllamaShotListAdapter(Adapter):
    """Scene-by-scene shot list with lens, motion, composition, duration."""
    capability = "shot_list"
    provider = Provider.OLLAMA_LOCAL
    requires_env: List[str] = []
    est_unit_cost_usd = 0.0

    def available(self) -> bool:
        return _ollama_available()

    def _real(self, prompt: str, workdir: Path, **kwargs):
        model = kwargs.get("ollama_model", "gpt-oss:20b")
        system = (
            "You are a cinematographer + 1st AD. Produce a JSON array of shots. "
            "Each shot: {scene, shot_num, slug, description, lens_mm, "
            "shot_size (ECU|CU|MS|MWS|WS|EWS), camera_motion, duration_s, "
            "characters, location, time_of_day, mood, vfx_notes}. "
            "Aim for 80-200 shots for a feature."
        )
        text = _ollama_chat(model, system, prompt,
                            max_tokens=kwargs.get("max_tokens", 8000))
        out = _save(workdir, f"shotlist_{int(time.time())}.json", text)
        return [out], f"{len(text)} chars shot list via {model}"


# ── Register: priority 80 beats OpenRouter's default 50 ─────────────

for cls in [
    OllamaScriptAdapter,
    OllamaGDDAdapter,
    OllamaWorldBibleAdapter,
    OllamaDialogueAdapter,
    OllamaGameplayCodeAdapter,
    OllamaShotListAdapter,
]:
    default_registry.register(cls(), priority=80)
