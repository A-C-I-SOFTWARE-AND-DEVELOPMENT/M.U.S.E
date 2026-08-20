# World-model routing (LingBot + Reactor)

Game Studio **Stage 1.5 World Vision** produces concept / cinematic clips that
feed look-dev. They are **not** in-engine assets and **not** a playable slice.

## Single command (prefer this)

```powershell
python C:\Users\Echer\models\lingbot-world-v2\muse\world_vision_router.py status

python C:\Users\Echer\models\lingbot-world-v2\muse\world_vision_router.py generate `
  --prompt "cinematic establishing shot of YOUR GAME WORLD" `
  --force-reactor
```

Outputs land in:
`C:\Users\Echer\models\lingbot-world-v2\muse\outputs\world-vision\`

JSON on stdout always includes `backend`, `ok`, and `path` (or `error`).
**Never claim success without a real file path.**

## Backend policy (this machine)

| Backend | When | Notes |
|---------|------|-------|
| **Reactor Helios** | Primary | `REACTOR_API_KEY` in `%HERMES_HOME%\.env`. Works today. Skill: `reactor-video-ai`. |
| **LingBot-World 2.0 local** | Secondary | Weights at `models\lingbot-world-v2\lingbot-world-v2-14b-causal-fast\`. Needs free VRAM. |

This laptop: **RTX 5070 Laptop 8GB**. Laguna (muse-local) usually holds ~7GB.
Local LingBot status reports `vram_insufficient`; even after `stop-muse.ps1`,
14B causal-fast often **OOM** (upstream examples use 8 GPUs).

### Free VRAM for local LingBot

```powershell
powershell -File C:\Users\Echer\models\laguna\stop-muse.ps1
python C:\Users\Echer\models\lingbot-world-v2\muse\world_vision_router.py generate `
  --prompt "..." --force-local --frames 17
powershell -File C:\Users\Echer\models\laguna\start-muse.ps1
```

## License / provenance

- LingBot-World weights: **CC BY-NC-SA 4.0** (non-commercial). Log provider +
  license in `templates/asset-provenance-log.md` when clips are used.
- Reactor: follow Reactor.inc ToS for commercial use; record `backend: reactor`
  in provenance.

## What World Vision is not

- Not a chat model — keep Muse on `muse-local`.
- Not mesh / gameplay / engine export — those stay Stages 3–9.
- Not WorldClaw. World Vision is a **clip**. WorldClaw
  (`references/worldclaw-pipeline.md`) is **explicit terrain + instance meshes**.
  Never import an MP4 as the world.
- Not a substitute for the Godot vertical-slice verify gate.
