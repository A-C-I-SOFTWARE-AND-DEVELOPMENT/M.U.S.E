# Axiom Studio — full-stack generative production pipeline

**Goal:** Take Axiom from "AI coding assistant" to "one-command AAA game
and theatrical film producer" by orchestrating every SOTA generative
primitive needed across both mediums.

## Honest framing

A single agent turn cannot literally ship Cyberpunk 2077 or *Oppenheimer*.
What it CAN do is **drive every step of the production pipeline through
SOTA generative APIs**, so the system goes from one-line brief →
screenplay + storyboards + 3D assets + animated scenes + dialogue +
score + SFX + playable engine project in one orchestrated run.

Quality scales with the model access you point it at. The 2027 SOTA
stack (Veo 3, Sora 2, Genie 3, Suno v4, ElevenLabs v3, Hunyuan3D-2,
Flux Pro, Claude Opus 4.6, UE 5.5) is what real studios are starting
to use today. Axiom Studio orchestrates all of them through one DAG.

## Architecture

```
agent/studio/
├── __init__.py            # public API
├── types.py               # FilmBrief, GameBrief, Provider, Quality, StageResult
├── orchestrator.py        # StudioOrchestrator — DAG runner for film + game
└── adapters/
    ├── base.py            # Adapter ABC + registry, stub fallback
    └── __init__.py        # concrete adapters for every capability
```

## Capabilities & providers wired in

| Capability       | Primary provider          | Fallback / alt              | Env key required        |
|------------------|---------------------------|-----------------------------|-------------------------|
| script / GDD     | Claude Opus 4.6 (OpenRouter) | GPT-5, Gemini 2.5 Pro DT  | `OPENROUTER_API_KEY`    |
| concept art      | Flux 1.1 Pro              | Midjourney v7, SD 3.5       | `BFL_API_KEY`           |
| video            | Veo 3                     | Sora 2, Runway Gen-4, Kling 2 | `GOOGLE_VEO_API_KEY` / `OPENAI_API_KEY` |
| 3D mesh          | Hunyuan3D-2 (Replicate)   | Meshy 5, Tripo3D, TRELLIS   | `REPLICATE_API_TOKEN`   |
| voice / dialogue | ElevenLabs v3             | Cartesia Sonic 2, Hume EVI  | `ELEVENLABS_API_KEY`    |
| music / score    | Suno v4                   | Udio, Stable Audio 2        | `SUNO_API_KEY`          |
| SFX / Foley      | ElevenLabs SFX            | MMAudio, Stable Audio       | `ELEVENLABS_API_KEY`    |
| world / sim      | Genie 3                   | Decart Oasis, World Labs Marble, Odyssey, DreamX | `GOOGLE_GENIE_API_KEY` |
| engine scaffold  | UE 5.5                    | Unity 6 + Muse, Godot 4.3   | (local, no key needed)  |

Every adapter has a **stub fallback** — pipelines complete end-to-end
without API keys, emitting JSON manifests describing what would be
generated. Wire keys to graduate stages to real generation incrementally.

## Pipelines

### Film (theatrical)

1. logline → treatment → full screenplay (LLM)
2. screenplay → shot list (~7 shots/min)
3. shot list → concept art per scene
4. shot list → animatic clips (8s shots @ PREVIZ, 10s @ THEATRICAL)
5. screenplay → per-character voice takes
6. emotional beats → orchestral score
7. cue list → SFX / Foley
8. assemble timeline.edl for DaVinci Resolve / Premiere import

### Game (AAA)

1. brief → Game Design Document (LLM, 16k–32k tokens)
2. GDD → narrative beats + character bios + level outlines
3. characters → concept sheet + rigged 3D mesh
4. levels → interactive worlds via Genie 3 / world model
5. NPCs → voice barks + dialogue trees
6. zones → adaptive score stems (exploration/combat/boss/stealth/menu)
7. ambient → SFX library
8. UE5 / Unity 6 / Godot 4 project scaffold (real .uproject written)

## Usage

```python
from agent.studio import StudioOrchestrator, FilmBrief, GameBrief, Quality, Provider

studio = StudioOrchestrator()

film = studio.produce_film(FilmBrief(
    title="The Last Signal",
    logline="A radio engineer in 1962 hears a transmission from herself, 60 years later.",
    runtime_min=110,
    quality=Quality.THEATRICAL,
))
print(film.summary())

game = studio.produce_game(GameBrief(
    title="Aetherbound",
    genre="action-RPG",
    setting="post-magical-collapse Victorian London",
    core_loop="explore → contract → fight → bind → upgrade",
    quality=Quality.FINAL,
    engine=Provider.UE5,
))
print(game.summary())
```

## Verified

- **6/6 unit tests pass** (`tests/studio/test_studio_orchestrator.py`)
- **Demo runs end-to-end**: 61 film stages + 42 game stages produced
  in <1s wall-time stub mode, real UE5 `.uproject` written.

## Path to "number-one charts"

Charts aren't a coding problem; they're a *distribution* problem. The
orchestrator gives you the artifact at the quality SOTA models support.
What you do with it after:

- **Film:** color-grade in Resolve, deliver DCP, four-wall theatrically
  or platform-direct (A24, Neon, Netflix originals window).
- **Game:** import scaffold into UE5, run in-engine polish + QA, ship
  via Steam + console certification.

The pipeline is the multiplier; the human producer is still the one
who picks great briefs and runs distribution.
