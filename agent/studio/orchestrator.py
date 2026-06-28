"""Studio orchestrator — runs the full DAG for a film or a game.

Pipelines
─────────
FILM (theatrical):
    1. logline → treatment → screenplay (LLM)
    2. screenplay → scene breakdown + shot list (LLM)
    3. shot list → concept art per location/character (image gen)
    4. shot list → animatic clips (video gen, 8s/shot)
    5. screenplay → dialogue takes per character (voice gen)
    6. emotional beats → score cues (music gen)
    7. shot list → SFX/Foley (sfx gen)
    8. assemble manifest with EDL (edit decision list) for NLE import

GAME (AAA):
    1. brief → high-level GDD + core loop (LLM)
    2. GDD → narrative beats + character bios + level outlines (LLM)
    3. characters → concept art + 3D meshes (image + mesh3d)
    4. levels → playable interactive worlds (Genie 3 / world model)
    5. NPCs → voice barks + dialogue trees (voice gen)
    6. zones → adaptive score stems (music gen)
    7. ambient → SFX library (sfx gen)
    8. engine project scaffold (UE5 / Unity / Godot)
    9. assemble manifest with import map for engine

Every stage runs through the AdapterRegistry — if real API keys are
present, real generation happens; otherwise stub manifests are
written and the DAG completes without spending money.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Optional

from agent.studio.adapters.base import AdapterRegistry, default_registry
from agent.studio.types import (
    FilmBrief, GameBrief, ProjectManifest, Provider, Quality, StageResult,
)
# Force adapter registration on import:
from agent.studio import adapters  # noqa: F401
from agent.studio.adapters import ollama_local  # noqa: F401 — registers local adapters
from agent.studio.adapters import free_providers  # noqa: F401 — pollinations + edge-tts


class StudioOrchestrator:
    def __init__(
        self,
        registry: Optional[AdapterRegistry] = None,
        root: Optional[Path] = None,
    ) -> None:
        self.registry = registry or default_registry
        self.root = Path(root or Path.cwd() / "studio_output")

    # ── helpers ────────────────────────────────────────────────────

    def _workdir(self, kind: str, title: str) -> Path:
        slug = "".join(c if c.isalnum() else "_" for c in title.lower()).strip("_")
        wd = self.root / kind / f"{slug}_{int(time.time())}"
        wd.mkdir(parents=True, exist_ok=True)
        return wd

    def _run(
        self,
        capability: str,
        prompt: str,
        workdir: Path,
        quality: Quality,
        prefer: Optional[Provider] = None,
        **kwargs,
    ) -> StageResult:
        adapter = self.registry.pick(capability, quality=quality, prefer=prefer)
        if adapter is None:
            return StageResult(
                stage=capability,
                provider=Provider.STUB,
                status="skipped",
                notes=f"no adapter registered for {capability}",
            )
        return adapter.run(prompt, workdir, **kwargs)

    # ── FILM pipeline ──────────────────────────────────────────────

    def produce_film(self, brief: FilmBrief) -> ProjectManifest:
        wd = brief.workdir or self._workdir("film", brief.title)
        manifest = ProjectManifest(
            kind="film", title=brief.title, workdir=wd, quality=brief.quality
        )
        t_start = time.perf_counter()

        # 1. Screenplay
        screenplay_prompt = (
            f"Write a {brief.runtime_min}-minute {brief.genre} screenplay "
            f"in industry-standard format (Fountain or final-draft style).\n"
            f"Title: {brief.title}\nLogline: {brief.logline}\nTone: {brief.tone}\n"
            f"Target rating: {brief.target_rating}\n"
            f"Output the full screenplay including INT/EXT slug lines, "
            f"action, dialogue, and parentheticals. Target a structure "
            f"with a strong inciting incident at ~12% and climax at ~85%."
        )
        manifest.stages.append(self._run("script", screenplay_prompt, wd, brief.quality))

        # 2. Shot list
        shotlist_prompt = (
            f"Break the screenplay into a shot list. Output as JSON array of "
            f"{{scene, shot, slug, description, camera, lens_mm, duration_s, "
            f"dialogue, sfx_cue, music_cue}}. Aim for {brief.runtime_min * 7} shots "
            f"({brief.runtime_min} min film at ~7 shots/min average)."
        )
        manifest.stages.append(
            self._run("shot_list", shotlist_prompt, wd, brief.quality, max_tokens=8000)
        )

        # 3. Concept art (key frames per scene)
        art_prompt = (
            f"Cinematic key frame, {brief.aspect} aspect ratio, {brief.tone}, "
            f"shot on Arri Alexa 65, anamorphic lens flare, film grain, "
            f"based on this scene: {brief.logline}"
        )
        for i in range(min(20, brief.runtime_min // 5)):
            manifest.stages.append(
                self._run("concept_art", f"{art_prompt} — frame {i}", wd, brief.quality,
                          width=2048, height=int(2048 / 2.39))
            )

        # 4. Animatic / final video — one shot per scene
        scenes = max(8, brief.runtime_min // 4)
        shot_dur = 8 if brief.quality != Quality.THEATRICAL else 10
        for i in range(scenes):
            manifest.stages.append(
                self._run(
                    "video",
                    f"{brief.tone} scene {i+1} of {brief.title}: {brief.logline}",
                    wd, brief.quality,
                    duration_s=shot_dur, aspect=brief.aspect,
                    resolution="4k" if brief.quality == Quality.THEATRICAL else "1080p",
                )
            )

        # 5. Voice — main characters
        for character in brief.extra.get("characters", ["NARRATOR", "PROTAGONIST", "ANTAGONIST"]):
            manifest.stages.append(
                self._run(
                    "voice",
                    f"Sample dialogue line for {character} in {brief.title}.",
                    wd, brief.quality, chars=2000,
                )
            )

        # 6. Score
        manifest.stages.append(
            self._run(
                "music",
                f"Orchestral score, main theme for {brief.title}. "
                f"Tone: {brief.tone}. Genre cue: {brief.genre}.",
                wd, brief.quality, duration_s=240, instrumental=True,
            )
        )

        # 7. SFX
        for cue in brief.extra.get("sfx_cues", ["ambient room tone", "thunder crack", "door slam"]):
            manifest.stages.append(self._run("sfx", cue, wd, brief.quality, duration_s=5))

        # 8. EDL assembly (just a manifest file, the real NLE work is downstream)
        edl_path = wd / "timeline.edl"
        edl_path.write_text("\n".join([
            "TITLE: " + brief.title,
            f"FCM: NON-DROP FRAME ({brief.fps}fps)",
            "# Generated by Axiom Studio — import into DaVinci Resolve / Premiere",
        ]))
        manifest.stages.append(StageResult(
            stage="edl", provider=Provider.STUB, status="ok",
            artifacts=[str(edl_path)], notes="timeline manifest written"
        ))

        # tally
        manifest.total_cost_usd = sum(s.est_cost_usd for s in manifest.stages)
        manifest.total_duration_s = time.perf_counter() - t_start
        (wd / "manifest.txt").write_text(manifest.summary())
        return manifest

    # ── OPEN-WORLD RPG pipeline (Skyrim-class) ─────────────────────

    def produce_open_world_rpg(self, brief: GameBrief, blueprint=None) -> ProjectManifest:
        """Scaffold + plan a Skyrim-CLASS open-world RPG from the capability blueprint.

        This *builds* (it does not merely describe): it scaffolds the engine
        project, materializes the machine-readable build plan (phases / domains /
        critical path / dependency graph as JSON the team can query), and runs the
        foundational P0 production stages. Network/key-less adapters stub when the
        studio is pinned offline (``AXIOM_STUDIO_OFFLINE``) so the whole plan
        materializes without spend. The blueprint defaults to the shipped one
        (``data/open_world_rpg_blueprint.json``); pass one to override.
        """
        from agent.studio.blueprints import load_open_world_rpg_blueprint

        bp = blueprint or load_open_world_rpg_blueprint()
        wd = brief.workdir or self._workdir("open_world_rpg", brief.title)
        manifest = ProjectManifest(
            kind="game", title=brief.title, workdir=wd, quality=brief.quality
        )
        t_start = time.perf_counter()

        # 1. Engine project scaffold — the blueprint recommends UE5 unless the
        #    brief explicitly pins another engine.
        engine_name = {Provider.UE5: "ue5", Provider.UNITY6: "unity6", Provider.GODOT4: "godot"}.get(
            brief.engine, "ue5"
        )
        manifest.stages.append(self._run(
            "engine_project",
            f"{brief.title} — {brief.genre} — open-world RPG ({bp.engine_recommended} recommended)",
            wd, brief.quality, engine=engine_name, title=brief.title,
        ))

        # 2. Materialize the build plan as queryable data (NOT prose docs):
        #    phases, domains, critical path, dependency graph, engine decision.
        plan_dir = wd / "build_plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan = bp.as_plan()
        written: List[str] = []
        for fname, payload in (
            ("blueprint.json", plan),
            ("phases.json", plan["phases"]),
            ("domains.json", plan["domains"]),
            ("critical_path.json", plan["critical_path"]),
            ("dependency_graph.json", plan["dependency_edges"]),
            ("engine.json", plan["engine"]),
        ):
            p = plan_dir / fname
            p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            written.append(str(p))
        manifest.stages.append(StageResult(
            stage="build_plan", provider=Provider.STUB, status="ok",
            artifacts=written,
            notes=(f"{len(bp.domains)} domains, {len(bp.phases)} phases, "
                   f"{len(bp.dependency_edges)} dep-edges; engine={bp.engine_recommended}"),
        ))

        # 3. Foundational production stages drawn from the P0 / critical-path
        #    domains (real adapters; stub when offline).
        p0_keys = ", ".join(d.key for d in bp.p0_domains) or "core systems"
        manifest.stages.append(self._run(
            "gdd",
            f"Write the Game Design Document for the open-world RPG '{brief.title}'.\n"
            f"Genre: {brief.genre}\nSetting: {brief.setting}\nCore loop: {brief.core_loop}\n"
            f"Build the GDD around these foundational (P0) capability domains: {p0_keys}.",
            wd, brief.quality, max_tokens=8000,
        ))
        manifest.stages.append(self._run(
            "world_bible",
            f"Original world bible for '{brief.title}' — {brief.setting}. "
            f"Cosmology, geography, factions, cultures, the central theme, and "
            f"hook locations. Original IP only; no existing-franchise content.",
            wd, brief.quality, max_tokens=8000,
        ))
        manifest.stages.append(self._run(
            "gameplay_code",
            f"Implement the Phase-0 substrate keystones for '{brief.title}' on "
            f"{engine_name}: deterministic fixed-timestep tick + seeded RNG, the "
            f"World/Object registry with stable persistent IDs, a versioned save "
            f"serializer, and the save-bound scripting/quest VM seam.",
            wd, brief.quality, engine=engine_name, max_tokens=6000,
        ))

        # tally
        manifest.total_cost_usd = sum(s.est_cost_usd for s in manifest.stages)
        manifest.total_duration_s = time.perf_counter() - t_start
        # encoding="utf-8": the summary contains ✓/→ glyphs that would crash on a
        # non-UTF-8 default (e.g. Windows cp1252).
        (wd / "manifest.txt").write_text(manifest.summary(), encoding="utf-8")
        return manifest

    # ── GAME pipeline ──────────────────────────────────────────────

    def produce_game(self, brief: GameBrief) -> ProjectManifest:
        wd = brief.workdir or self._workdir("game", brief.title)
        manifest = ProjectManifest(
            kind="game", title=brief.title, workdir=wd, quality=brief.quality
        )
        t_start = time.perf_counter()

        # 1. GDD
        gdd_prompt = (
            f"Write a complete AAA Game Design Document for '{brief.title}'.\n"
            f"Genre: {brief.genre}\nTarget platform: {brief.target}\n"
            f"Perspective: {brief.perspective}\nSetting: {brief.setting}\n"
            f"Core loop: {brief.core_loop}\nArt style: {brief.art_style}\n"
            f"Target campaign length: {brief.runtime_hours} hours.\n"
            f"Sections required: Vision, Pillars, Mechanics, Systems, "
            f"Progression, Economy, Narrative Arc, Characters (5+), Levels (10+), "
            f"Enemies, UI, Audio Direction, Art Direction, Tech Stack, Risk Register."
        )
        manifest.stages.append(self._run("gdd", gdd_prompt, wd, brief.quality, max_tokens=8000))

        # 2. Narrative beats + character bios
        narr_prompt = (
            f"Given the GDD for {brief.title}, produce: (a) 3-act narrative beat "
            f"sheet with ~25 beats, (b) 8 character bios with motivations and arcs, "
            f"(c) 12 level outlines with objectives, mood, hazards, rewards."
        )
        manifest.stages.append(self._run("world_bible", narr_prompt, wd, brief.quality, max_tokens=8000))

        # 2b. Per-character dialogue
        for ch in brief.extra.get("characters", ["Hero", "Rival", "Mentor", "Villain", "Companion"])[:3]:
            manifest.stages.append(self._run(
                "dialogue_text",
                f"Generate 20 dialogue lines for {ch} in {brief.title}: "
                f"mix of cinematic, branching, and combat barks.",
                wd, brief.quality, max_tokens=3000,
            ))

        # 2c. Starter gameplay code module
        engine_name_early = {Provider.UE5: "ue5", Provider.UNITY6: "unity",
                              Provider.GODOT4: "godot"}.get(brief.engine, "ue5")
        manifest.stages.append(self._run(
            "gameplay_code",
            f"Implement the core gameplay loop ({brief.core_loop}) for {brief.title}: "
            f"player controller, primary verb, one enemy AI, one progression hook.",
            wd, brief.quality, engine=engine_name_early, max_tokens=5000,
        ))

        # 3. Character concept art + 3D meshes
        for ch in brief.extra.get("characters", ["Hero", "Rival", "Mentor", "Villain", "Companion"]):
            manifest.stages.append(self._run(
                "concept_art",
                f"{brief.art_style} character concept sheet: {ch} from {brief.title}",
                wd, brief.quality, width=1536, height=2048,
            ))
            manifest.stages.append(self._run(
                "mesh3d",
                f"Game-ready character mesh, PBR textures, rigged, T-pose: {ch}",
                wd, brief.quality,
            ))

        # 4. Interactive worlds for each major level
        for lvl in brief.extra.get("levels", ["Prologue Town", "Underdark", "Sky Citadel", "Final Sanctum"]):
            manifest.stages.append(self._run(
                "world",
                f"Interactive game world: {lvl}. Setting: {brief.setting}. "
                f"Style: {brief.art_style}. Genre: {brief.genre}.",
                wd, brief.quality, duration_s=120,
            ))

        # 5. NPC voice barks
        for npc in brief.extra.get("npc_voices", ["Merchant", "Guard", "Sage", "Child"]):
            manifest.stages.append(self._run(
                "voice",
                f"Greeting line for {npc} NPC in {brief.title}.",
                wd, brief.quality, chars=500,
            ))

        # 6. Adaptive score stems
        for zone in brief.extra.get("score_zones", ["exploration", "combat", "boss", "stealth", "menu"]):
            manifest.stages.append(self._run(
                "music",
                f"{zone} music stem for {brief.title}. Adaptive loop, "
                f"layered for vertical re-mixing. {brief.art_style} tone.",
                wd, brief.quality, duration_s=180, instrumental=True,
            ))

        # 7. SFX library
        for sfx in brief.extra.get("sfx_set", [
            "footsteps on stone", "footsteps on metal", "sword draw",
            "magic cast", "UI confirm", "UI cancel", "level up", "enemy hit", "ambient wind",
        ]):
            manifest.stages.append(self._run("sfx", sfx, wd, brief.quality, duration_s=3))

        # 8. Engine project scaffold
        engine_name = {Provider.UE5: "ue5", Provider.UNITY6: "unity6", Provider.GODOT4: "godot"}.get(
            brief.engine, "ue5"
        )
        manifest.stages.append(self._run(
            "engine_project",
            f"{brief.title} — {brief.genre} — {brief.core_loop}",
            wd, brief.quality, engine=engine_name, title=brief.title,
        ))

        # tally
        manifest.total_cost_usd = sum(s.est_cost_usd for s in manifest.stages)
        manifest.total_duration_s = time.perf_counter() - t_start
        (wd / "manifest.txt").write_text(manifest.summary())
        return manifest
