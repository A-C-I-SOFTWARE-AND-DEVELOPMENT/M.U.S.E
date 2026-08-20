# Game Studio — muse's game-creation capability

This guide explains how muse orchestrates the production of a graphically
state-of-the-art PC game, and how to drive it.

## Honest framing first

A single agent turn cannot literally ship a 100-person, $100M AAA title. What
muse *does* is **drive every step of a gated production pipeline through SOTA
generative + engine APIs** — one-line brief → GDD → concept art → 3D assets →
greybox level → gameplay systems → lighting → audio → a **playable, runnable
vertical slice** in one orchestrated, ledgered run. Quality scales with the
model and engine access you point it at. This sits on top of the existing
generative production engine documented in [`../studio/README.md`](../studio/README.md).

## The pieces

| Piece | Path | Role |
|---|---|---|
| Council skill | `skills/creative/game-studio/SKILL.md` | Routing layer — maps a brief to game-dev roles, engine profiles, and owner gates. |
| Agent roster | `skills/creative/game-studio/agents/` | 9 single-domain roles (director, designer, gameplay, graphics, 3D, audio, QA, release). |
| Workflow | `skills/creative/game-studio/workflows/game-production-pipeline.md` | Staged pipeline + WorldClaw open-world stages (2.6 / 3.5 / 4 / 4.5). |
| WorldClaw | `skills/creative/game-studio/references/worldclaw-pipeline.md` | Tencent Hunyuan arXiv:2608.05248 distilled onto the 9 seats. Explicit terrain + instance meshes. |
| World spec | `skills/creative/game-studio/templates/world-spec.md` | Intent (extract) vs Plan (complete schema). |
| Nine-hold plan | `skills/creative/game-studio/references/nine-hold-world-spec.md` | Filled Skyrim-class *plan* (not a shipped world). |
| Weight/STATUS | `docs/game-studio/STATUS.md` + `C:\\Users\\Echer\\models\\agents\\game-pipeline\\STATUS.md` | Honest download + LoRA state. |
| Engine profiles | [`engine-profiles.md`](engine-profiles.md) | UE5 / Godot / Unity as pluggable worker profiles. |
| 3D asset tool | `tools/asset3d_generation_tool.py` + `agent/asset3d_gen_provider.py` | `asset3d_generate` — text-to-3D meshes via a pluggable backend. |
| 3D backends | `plugins/asset3d_gen/meshy/`, `plugins/asset3d_gen/hunyuan3d/` | Meshy (hosted text-to-3D) and Hunyuan3D-2 (Replicate, image-to-3D) — both opt-in behind their API keys. |
| Reference slice | `skills/creative/game-studio/reference-slice/` | A real, runnable Godot 4 slice — the proof artifact. |
| SOTA graphics | `skills/creative/ue5-render/` | Unreal Nanite/Lumen render path (owner GPU host). |
| Textures/audio | `skills/creative/comfyui/` | Image/video/audio asset generation. |

## How muse runs it

1. Say "build a vertical slice" (or any phrase in the skill's
   `activation_phrases`). The `studio-director` role classifies scope and picks
   an engine profile.
2. The pipeline runs stage by stage; parallel asset/level/audio work fans out
   over **disjoint file domains** via `/swarm`.
3. Each gate is enforced; owner-gated steps wait for `Yes, with authorization.`
4. The build is produced and **verified** — a build claim always ships with the
   export log + artifact path.

## Engine reality

| Engine | Status |
|---|---|
| **Godot 4** (`game-godot`) | The only path that builds + runs **headlessly** here / in CI. Default for the vertical slice. |
| **Unreal Engine 5** (`game-ue5`) | The **SOTA-graphics** path (Nanite/Lumen/MetaHuman). Needs an owner-provided GPU + licensed engine host; drives renders via `ue5-render`. |
| **Unity 6** (`game-unity`) | Documented profile only. |

## Owner gates (require `Yes, with authorization.`)

1. **Engine process spawn** — `MUSE_GAME_ALLOW_SPAWN=1` (modeled on
   `MUSE_UE5_ALLOW_SPAWN`). Ungranted, the export script dry-runs.
2. **GPU / paid-API spend** — 3D mesh generation and texture batches cost money;
   `asset3d_generate` returns `est_cost_usd` to surface before bulk runs.
3. **Asset licensing** — third-party / AI-generated assets need owner sign-off
   with recorded provenance.
4. **Publishing a build** — store upload is an absolute owner-only wall.

See [`../jarvis-verification-gates.md`](../jarvis-verification-gates.md) for the
full gate model.

## Run the full pipeline from a brief

```bash
# Stub-safe: with no API keys this dry-runs the whole DAG and shows every stage.
python skills/creative/game-studio/scripts/run_pipeline.py \
    --title "Aether Drift" --genre "sci-fi explorer" --engine godot \
    --core-loop "scan, salvage, upgrade, survive" --offline
```

This drives the existing `agent/studio/` production DAG (GDD → narrative →
concept art → 3D meshes → gameplay code → audio → engine scaffold). It drives
the *pipeline*; for a runnable artifact, pair `--engine godot` with the
reference slice below.

## Try the reference slice

```bash
# Inspect / play (needs Godot 4 installed)
godot --path skills/creative/game-studio/reference-slice

# Headless build (owner-gated)
MUSE_GAME_ALLOW_SPAWN=1 python skills/creative/game-studio/scripts/export_godot_slice.py
python skills/creative/game-studio/scripts/verify_slice.py \
    skills/creative/game-studio/reference-slice/build/slice.x86_64
```

## Unified 3D path

The studio engine's `mesh3d` stage (`agent/studio/adapters/Mesh3DAdapter`) and
the muse `asset3d_generate` tool share one backend registry **when you opt in**:
set `asset3d_gen.provider` in `config.yaml` and the studio DAG routes its 3D
stage through the same provider (Meshy / Hunyuan3D / …). Leave it unset and the
studio keeps its legacy direct-Replicate path — default behaviour is unchanged.

## Add a 3D backend

Two ship today — `meshy` (text-to-3D) and `hunyuan3d` (image-to-3D via
Replicate). Add more by copying either directory and swapping the HTTP calls
(Tripo3D, TRELLIS also fit the `Asset3DGenProvider` interface). Pick the active
one interactively via `hermes tools` → **3D Generation** (it walks you through
provider + API key and writes `asset3d_gen.provider`), or set
`asset3d_gen.provider` in `config.yaml` directly.
