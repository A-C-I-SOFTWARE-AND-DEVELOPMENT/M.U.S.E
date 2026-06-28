"""Free local/public adapters — image (Pollinations) + voice (edge-tts).

Both are zero-cost and key-less; they activate whenever the network /
local daemon is reachable. They register at priority 70 (below local
Ollama's 80, above OpenRouter's 50), so they slot in for image + voice
stages without disturbing the LLM chain.

Pollinations: https://image.pollinations.ai/prompt/<urlencoded-prompt>
  - free, public, no key, returns PNG
  - backed by Flux / SDXL; respects width/height/seed via query params

edge-tts: Microsoft Edge's TTS endpoint, MIT-licensed Python client
  - free, no key, ~hundreds of voices
  - returns MP3 audio
"""
from __future__ import annotations

import asyncio
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import List

from agent.studio.adapters.base import Adapter, default_registry
from agent.studio.types import Provider


# ── Offline / stub-only gate ────────────────────────────────────────
#
# These adapters are key-LESS: they activate on mere network/daemon
# reachability, so blanking API keys does NOT stop them — they fire real
# HTTP calls and get rate-limited (HTTP 429) on CI, turning stub-mode
# pipeline tests red. The full-pipeline DAG tests set ``AXIOM_STUDIO_OFFLINE``
# to pin every key-less network adapter to its stub fallback so the DAG
# dry-runs hermetically. Production (and the adapter-unit tests that
# exercise the real/online path with mocked probes) leave it unset →
# behaviour is unchanged.

_OFFLINE_VALUES = ("1", "true", "yes", "on")


def studio_offline() -> bool:
    """True when the studio is pinned to stub-only mode (AXIOM_STUDIO_OFFLINE)."""
    return os.environ.get("AXIOM_STUDIO_OFFLINE", "").strip().lower() in _OFFLINE_VALUES


def _free_network_allowed() -> bool:
    """False when pinned offline, so key-less free network adapters stub."""
    return not studio_offline()


# ── Pollinations free image adapter ─────────────────────────────────

POLLINATIONS_BASE = os.environ.get(
    "POLLINATIONS_BASE", "https://image.pollinations.ai/prompt"
)


def _pollinations_available() -> bool:
    """Probe once per 60s; cache the result."""
    cache = getattr(_pollinations_available, "_cache", None)
    now = time.time()
    if cache and now - cache[0] < 60:
        return cache[1]
    try:
        # HEAD on the base; treat any HTTP response as "reachable"
        req = urllib.request.Request(POLLINATIONS_BASE + "/test",
                                     method="HEAD")
        with urllib.request.urlopen(req, timeout=4.0) as r:
            ok = r.status < 500
    except urllib.error.HTTPError as e:
        ok = e.code < 500
    except Exception:
        ok = False
    _pollinations_available._cache = (now, ok)  # type: ignore[attr-defined]
    return ok


class PollinationsImageAdapter(Adapter):
    """Free public Flux/SDXL image generation. No key required."""
    capability = "concept_art"
    provider = Provider.FLUX_PRO  # closest enum; backend is Flux behind Pollinations
    requires_env: List[str] = []
    est_unit_cost_usd = 0.0

    def available(self) -> bool:
        return _free_network_allowed() and _pollinations_available()

    def _real(self, prompt: str, workdir: Path, **kwargs):
        workdir.mkdir(parents=True, exist_ok=True)
        w = int(kwargs.get("width", 1024))
        h = int(kwargs.get("height", 1024))
        seed = int(kwargs.get("seed", int(time.time()) % 1_000_000))
        model = kwargs.get("pollinations_model", "flux")  # flux | turbo
        # URL-encode prompt; pollinations renders synchronously and streams PNG
        encoded = urllib.parse.quote(prompt[:1500], safe="")
        url = (
            f"{POLLINATIONS_BASE}/{encoded}"
            f"?width={w}&height={h}&seed={seed}&model={model}&nologo=true"
        )
        req = urllib.request.Request(url, headers={
            "Accept": "image/png",
            "User-Agent": "Mozilla/5.0 AxiomStudio/1.0",
            "Referer": "https://pollinations.ai/",
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            png = resp.read()
        fname = f"concept_{int(time.time()*1000)}_{seed}.png"
        out = workdir / fname
        out.write_bytes(png)
        return [str(out)], f"pollinations {model} {w}x{h} seed={seed} ({len(png)} bytes)"


# ── edge-tts free voice adapter ─────────────────────────────────────

# Voice presets per character archetype — caller can override via kwargs["voice"]
EDGE_VOICE_BY_ROLE = {
    "narrator": "en-US-GuyNeural",
    "protagonist": "en-US-AndrewNeural",
    "antagonist": "en-GB-RyanNeural",
    "hero": "en-US-AndrewNeural",
    "villain": "en-GB-RyanNeural",
    "mentor": "en-GB-RyanNeural",
    "companion": "en-US-AvaNeural",
    "merchant": "en-US-EmmaNeural",
    "guard": "en-US-EricNeural",
    "sage": "en-GB-RyanNeural",
    "child": "en-US-AnaNeural",
    "default": "en-US-AndrewNeural",
}


def _edge_tts_available() -> bool:
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return False
    # Trust import; the network endpoint is the same one Edge browser uses
    return True


def _pick_voice(prompt: str, kwargs: dict) -> str:
    if "voice" in kwargs:
        return kwargs["voice"]
    low = prompt.lower()
    for role, voice in EDGE_VOICE_BY_ROLE.items():
        if role in low:
            return voice
    return EDGE_VOICE_BY_ROLE["default"]


class EdgeTTSVoiceAdapter(Adapter):
    """Free Microsoft Edge TTS — high-quality neural voices, no key."""
    capability = "voice"
    provider = Provider.F5_TTS  # closest enum slot; backend is Edge Neural TTS
    requires_env: List[str] = []
    est_unit_cost_usd = 0.0

    def available(self) -> bool:
        return _free_network_allowed() and _edge_tts_available()

    def _real(self, prompt: str, workdir: Path, **kwargs):
        import edge_tts
        workdir.mkdir(parents=True, exist_ok=True)
        voice = _pick_voice(prompt, kwargs)
        rate = kwargs.get("rate", "+0%")
        # Extract the spoken text — if caller passed a "Sample dialogue line
        # for X" prompt, generate a short line; otherwise speak the prompt.
        text = kwargs.get("text", prompt)
        if text.lower().startswith("sample dialogue line for"):
            # Best-effort placeholder — caller can pass `text=` to override
            text = prompt

        fname = f"voice_{int(time.time()*1000)}_{voice.replace('-','_')}.mp3"
        out = workdir / fname

        async def _run() -> None:
            communicate = edge_tts.Communicate(text[:4000], voice, rate=rate)
            await communicate.save(str(out))

        # Run async TTS in a fresh event loop (works inside/outside running loops)
        try:
            asyncio.run(_run())
        except RuntimeError:
            # Already inside a loop — schedule on a separate thread
            import threading
            err: list = []
            def _runner():
                try:
                    asyncio.new_event_loop().run_until_complete(_run())
                except Exception as exc:
                    err.append(exc)
            t = threading.Thread(target=_runner)
            t.start()
            t.join(timeout=120)
            if err:
                raise err[0]

        size = out.stat().st_size if out.exists() else 0
        return [str(out)], f"edge-tts voice={voice} ({size} bytes)"


# ── Register at priority 70 (between local Ollama 80 and OpenRouter 50) ──

for cls in [PollinationsImageAdapter, EdgeTTSVoiceAdapter]:
    default_registry.register(cls(), priority=70)
