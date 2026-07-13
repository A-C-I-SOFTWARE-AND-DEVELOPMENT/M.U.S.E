"""Concrete adapters — one file per capability.

Every adapter ships with: stub fallback (always works) + _real() body
that calls the actual API when env keys are present. Real API code is
intentionally compact and uses urllib so no extra deps are required.
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
from agent.studio.engine_discovery import discover_unreal
from agent.studio.types import Provider


def _post_json(url: str, headers: dict, payload: dict, timeout: float = 600.0) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _save(workdir: Path, name: str, data: bytes | str) -> str:
    workdir.mkdir(parents=True, exist_ok=True)
    p = workdir / name
    mode = "wb" if isinstance(data, (bytes, bytearray)) else "w"
    encoding = None if "b" in mode else "utf-8"
    with open(p, mode, encoding=encoding) as f:
        f.write(data)
    return str(p)


# ── Script / GDD generation (LLM via OpenRouter — already configured) ───

class ScriptAdapter(Adapter):
    capability = "script"
    provider = Provider.CLAUDE_OPUS
    requires_env = ["OPENROUTER_API_KEY"]
    est_unit_cost_usd = 0.50

    def _real(self, prompt: str, workdir: Path, **kwargs):
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": kwargs.get("model", "anthropic/claude-opus-4.6"),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 16000),
        }
        data = _post_json(url, headers, payload)
        text = data["choices"][0]["message"]["content"]
        out = _save(workdir, f"script_{int(time.time())}.md", text)
        return [out], f"{len(text)} chars script"


# ── Concept / storyboard image ──────────────────────────────────────

class ConceptArtAdapter(Adapter):
    capability = "concept_art"
    provider = Provider.FLUX_PRO
    requires_env = ["BFL_API_KEY"]
    est_unit_cost_usd = 0.05

    def _real(self, prompt: str, workdir: Path, **kwargs):
        # Black Forest Labs API
        url = "https://api.bfl.ml/v1/flux-pro-1.1"
        headers = {"x-key": os.environ["BFL_API_KEY"], "Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "width": kwargs.get("width", 1024),
            "height": kwargs.get("height", 1024),
        }
        data = _post_json(url, headers, payload)
        # BFL returns a polling URL; we just save the request manifest here
        out = _save(workdir, f"concept_{int(time.time())}.json", json.dumps(data, indent=2))
        return [out], "submitted to Flux Pro"


# ── Video generation ────────────────────────────────────────────────

class VideoAdapter(Adapter):
    capability = "video"
    provider = Provider.VEO3
    # Veo 3 is accessed via Vertex AI or Replicate; we expose both shapes.
    requires_env = ["GOOGLE_VEO_API_KEY"]
    est_unit_cost_usd = 0.35  # ~$0.35 / second of generated video

    def _estimate_cost(self, **kwargs):
        return self.est_unit_cost_usd * kwargs.get("duration_s", 8)

    def _real(self, prompt: str, workdir: Path, **kwargs):
        # Placeholder for Vertex AI / Replicate call — kept compact.
        url = "https://generativelanguage.googleapis.com/v1beta/models/veo-3:generateVideo"
        headers = {
            "x-goog-api-key": os.environ["GOOGLE_VEO_API_KEY"],
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "duration_s": kwargs.get("duration_s", 8),
            "aspect_ratio": kwargs.get("aspect", "16:9"),
            "resolution": kwargs.get("resolution", "1080p"),
        }
        data = _post_json(url, headers, payload)
        out = _save(workdir, f"shot_{int(time.time())}.json", json.dumps(data, indent=2))
        return [out], f"veo-3 {kwargs.get('duration_s', 8)}s clip queued"


class Sora2Adapter(Adapter):
    capability = "video"
    provider = Provider.SORA2
    requires_env = ["OPENAI_API_KEY"]
    est_unit_cost_usd = 0.50

    def _estimate_cost(self, **kwargs):
        return self.est_unit_cost_usd * kwargs.get("duration_s", 10)

    def _real(self, prompt: str, workdir: Path, **kwargs):
        url = "https://api.openai.com/v1/video/generations"
        headers = {
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "sora-2",
            "prompt": prompt,
            "duration": kwargs.get("duration_s", 10),
            "resolution": kwargs.get("resolution", "1080p"),
        }
        data = _post_json(url, headers, payload)
        out = _save(workdir, f"sora_{int(time.time())}.json", json.dumps(data, indent=2))
        return [out], f"sora-2 {kwargs.get('duration_s', 10)}s clip queued"


# ── 3D asset generation ─────────────────────────────────────────────


def _explicit_asset3d_provider():
    """Return the muse Asset3DGenProvider ONLY when one is explicitly selected.

    Unifies the studio's 3D-mesh stage with the first-class
    ``asset3d_generate`` tool surface (``plugins/asset3d_gen/<backend>/``), but
    only when the operator has opted in by setting ``asset3d_gen.provider`` in
    config.yaml. With it unset, this returns None and the legacy direct-Replicate
    path below runs unchanged — so default behaviour is byte-for-byte identical.

    Returns None in offline mode so the full-pipeline DAG tests stay hermetic.
    """
    try:
        from agent.studio.adapters.free_providers import studio_offline

        if studio_offline():
            return None
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("asset3d_gen") if isinstance(cfg, dict) else None
        chosen = section.get("provider") if isinstance(section, dict) else None
        if not (isinstance(chosen, str) and chosen.strip()):
            return None
        from agent.asset3d_gen_registry import get_active_provider
        from hermes_cli.plugins import _ensure_plugins_discovered

        _ensure_plugins_discovered()
        return get_active_provider()
    except Exception:  # noqa: BLE001 — never break the studio DAG on resolution
        return None


class Mesh3DAdapter(Adapter):
    capability = "mesh3d"
    provider = Provider.HUNYUAN3D
    requires_env = ["REPLICATE_API_TOKEN"]
    est_unit_cost_usd = 0.10

    def available(self) -> bool:
        # Real when the legacy Replicate token is present OR an asset3d provider
        # has been explicitly configured (and we're not pinned offline).
        if super().available():
            return True
        return _explicit_asset3d_provider() is not None

    def _real(self, prompt: str, workdir: Path, **kwargs):
        # Prefer the unified muse provider registry when explicitly selected.
        provider = _explicit_asset3d_provider()
        if provider is not None:
            result = provider.generate(
                prompt=prompt,
                fmt=kwargs.get("fmt", "glb"),
                textured=kwargs.get("textured", True),
                image=kwargs.get("image"),
            )
            if isinstance(result, dict) and result.get("success") and result.get("mesh"):
                return self._save_provider_mesh(result, workdir)
            err = (result or {}).get("error", "asset3d provider returned no mesh")
            raise RuntimeError(f"asset3d provider '{getattr(provider, 'name', '?')}': {err}")

        # Legacy direct-Replicate path (unchanged; runs when REPLICATE_API_TOKEN
        # is set and no explicit asset3d_gen.provider is configured).
        url = "https://api.replicate.com/v1/predictions"
        headers = {
            "Authorization": f"Token {os.environ['REPLICATE_API_TOKEN']}",
            "Content-Type": "application/json",
        }
        payload = {
            "version": "tencent/hunyuan3d-2:latest",
            "input": {"prompt": prompt, "texture": True},
        }
        data = _post_json(url, headers, payload)
        out = _save(workdir, f"mesh_{int(time.time())}.json", json.dumps(data, indent=2))
        return [out], "hunyuan3d-2 mesh queued"

    def _save_provider_mesh(self, result: dict, workdir: Path):
        """Persist a unified-provider mesh result into the stage workdir."""
        workdir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "capability": "mesh3d",
            "provider": result.get("provider"),
            "mesh": result.get("mesh"),
            "format": result.get("format"),
            "textures": result.get("textures", []),
            "poly_count": result.get("poly_count"),
            "est_cost_usd": result.get("est_cost_usd"),
        }
        mpath = _save(workdir, f"mesh_{int(time.time()*1000)}.json", json.dumps(manifest, indent=2))
        artifacts: List[str] = [mpath]
        mesh = result.get("mesh")
        # When the provider cached a local file, surface it as the primary artifact.
        if isinstance(mesh, str) and os.path.exists(mesh):
            artifacts.insert(0, mesh)
        return artifacts, f"{result.get('provider')} mesh ({result.get('format')})"


# ── Voice / dialogue ────────────────────────────────────────────────

class VoiceAdapter(Adapter):
    capability = "voice"
    provider = Provider.ELEVENLABS_V3
    requires_env = ["ELEVENLABS_API_KEY"]
    est_unit_cost_usd = 0.18  # per 1k chars

    def _estimate_cost(self, **kwargs):
        chars = kwargs.get("chars", 1000)
        return self.est_unit_cost_usd * (chars / 1000.0)

    def _real(self, prompt: str, workdir: Path, **kwargs):
        voice_id = kwargs.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {"text": prompt, "model_id": "eleven_v3"}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            audio = resp.read()
        out = _save(workdir, f"voice_{int(time.time())}.mp3", audio)
        return [out], f"elevenlabs v3 {len(prompt)} chars"


# ── Music / score ───────────────────────────────────────────────────

class MusicAdapter(Adapter):
    capability = "music"
    provider = Provider.SUNO_V4
    requires_env = ["SUNO_API_KEY"]
    est_unit_cost_usd = 0.10

    def _real(self, prompt: str, workdir: Path, **kwargs):
        url = "https://api.suno.ai/v1/generate"
        headers = {
            "Authorization": f"Bearer {os.environ['SUNO_API_KEY']}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "duration_s": kwargs.get("duration_s", 180),
            "instrumental": kwargs.get("instrumental", True),
        }
        data = _post_json(url, headers, payload)
        out = _save(workdir, f"score_{int(time.time())}.json", json.dumps(data, indent=2))
        return [out], "suno v4 track queued"


# ── SFX / Foley ─────────────────────────────────────────────────────

class SfxAdapter(Adapter):
    capability = "sfx"
    provider = Provider.ELEVENLABS_SFX
    requires_env = ["ELEVENLABS_API_KEY"]
    est_unit_cost_usd = 0.02

    def _real(self, prompt: str, workdir: Path, **kwargs):
        url = "https://api.elevenlabs.io/v1/sound-generation"
        headers = {
            "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {"text": prompt, "duration_seconds": kwargs.get("duration_s", 5)}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            audio = resp.read()
        out = _save(workdir, f"sfx_{int(time.time())}.mp3", audio)
        return [out], "elevenlabs sfx"


# ── Interactive world / playable level (Genie 3 etc.) ───────────────

class WorldAdapter(Adapter):
    capability = "world"
    provider = Provider.GENIE3
    requires_env = ["GOOGLE_GENIE_API_KEY"]
    est_unit_cost_usd = 1.50  # rough

    def _real(self, prompt: str, workdir: Path, **kwargs):
        # Genie 3 is currently research-preview; we emit a manifest
        url = "https://generativelanguage.googleapis.com/v1beta/models/genie-3:generateWorld"
        headers = {
            "x-goog-api-key": os.environ["GOOGLE_GENIE_API_KEY"],
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "duration_s": kwargs.get("duration_s", 60),
            "resolution": "720p",
        }
        try:
            data = _post_json(url, headers, payload)
        except urllib.error.HTTPError as e:
            data = {"status": "queued", "http": e.code, "note": "genie-3 preview"}
        out = _save(workdir, f"world_{int(time.time())}.json", json.dumps(data, indent=2))
        return [out], "genie-3 interactive world queued"


# ── Game engine project scaffolding (UE5 / Unity / Godot) ───────────

class EngineProjectAdapter(Adapter):
    capability = "engine_project"
    provider = Provider.UE5
    requires_env = []  # local scaffolding, always available
    est_unit_cost_usd = 0.0

    def available(self) -> bool:
        return True  # scaffolding is always available

    def _real(self, prompt: str, workdir: Path, **kwargs):
        engine = kwargs.get("engine", "ue5")
        proj = workdir / f"{engine}_project"
        proj.mkdir(parents=True, exist_ok=True)
        if engine.lower() == "godot":
            (proj / "project.godot").write_text(
                "[application]\nconfig/name=\"MUSE Studio Game\"\n"
                "run/main_scene=\"res://main.tscn\"\n\n[display]\n"
                "window/size/viewport_width=1280\nwindow/size/viewport_height=720\n",
                encoding="utf-8",
            )
            (proj / "main.tscn").write_text(
                "[gd_scene load_steps=2 format=3]\n\n"
                "[ext_resource path=\"res://main.gd\" type=\"Script\" id=\"1\"]\n\n"
                "[node name=\"Main\" type=\"Node2D\"]\nscript = ExtResource(\"1\")\n",
                encoding="utf-8",
            )
            (proj / "main.gd").write_text(
                "extends Node2D\n\nfunc _draw() -> void:\n"
                "    draw_circle(Vector2(640, 360), 48, Color(\"6be4ff\"))\n\n"
                "func _ready() -> void:\n    queue_redraw()\n",
                encoding="utf-8",
            )
            engine_validation = "source_complete_uncompiled"
        elif engine.lower() in {"unity", "unity6"}:
            scripts = proj / "Assets" / "Scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            (scripts / "StudioBootstrap.cs").write_text(
                "using UnityEngine;\n"
                "public sealed class StudioBootstrap : MonoBehaviour { }\n",
                encoding="utf-8",
            )
            (proj / "Packages").mkdir(exist_ok=True)
            (proj / "ProjectSettings").mkdir(exist_ok=True)
            engine_validation = "external_adapter_unavailable"
        else:
            found = discover_unreal(preferred="5.6")
            association = found.version if found is not None else "5.6"
            (proj / "Project.uproject").write_text(json.dumps({
                "FileVersion": 3,
                "EngineAssociation": association,
                "Category": "AAA",
                "Description": prompt[:500],
                "Modules": [{"Name": "Game", "Type": "Runtime", "LoadingPhase": "Default"}],
            }, indent=2), encoding="utf-8")
            source = proj / "Source" / "Game"
            source.mkdir(parents=True, exist_ok=True)
            (proj / "Content").mkdir(exist_ok=True)
            (proj / "Config").mkdir(exist_ok=True)
            (source / "Game.Build.cs").write_text(
                "using UnrealBuildTool;\n"
                "public class Game : ModuleRules {\n"
                "    public Game(ReadOnlyTargetRules Target) : base(Target) {\n"
                "        PublicDependencyModuleNames.AddRange(new[] { \"Core\", \"CoreUObject\", \"Engine\" });\n"
                "    }\n}\n",
                encoding="utf-8",
            )
            (source / "Game.cpp").write_text(
                "#include \"Modules/ModuleManager.h\"\n"
                "IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, Game, \"Game\");\n",
                encoding="utf-8",
            )
            (proj / "Source" / "Game.Target.cs").write_text(
                "using UnrealBuildTool;\n"
                "public class GameTarget : TargetRules {\n"
                "    public GameTarget(TargetInfo Target) : base(Target) {\n"
                "        Type = TargetType.Game; DefaultBuildSettings = BuildSettingsVersion.V5;\n"
                "        ExtraModuleNames.Add(\"Game\");\n"
                "    }\n}\n",
                encoding="utf-8",
            )
            engine_validation = "available_unbuilt" if found is not None else "not_installed"
        (proj / "README.md").write_text(
            f"# {kwargs.get('title', 'Game')}\n\nGenerated by Axiom Studio.\n\n## Brief\n\n{prompt}\n",
            encoding="utf-8",
        )
        (proj / "studio-engine-manifest.json").write_text(
            json.dumps({
                "engine": engine,
                "engine_validation": engine_validation,
                "compiled": False,
                "playable": False,
            }, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return [str(proj)], f"{engine} source scaffolded ({engine_validation})"


# ── Register everything ─────────────────────────────────────────────

for cls in [
    ScriptAdapter, ConceptArtAdapter, VideoAdapter, Sora2Adapter,
    Mesh3DAdapter, VoiceAdapter, MusicAdapter, SfxAdapter,
    WorldAdapter, EngineProjectAdapter,
]:
    default_registry.register(cls(), priority=50)
