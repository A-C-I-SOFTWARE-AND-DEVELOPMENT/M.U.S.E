# Game-dev API toolkit setup (Windows)

Unified Python client for game-development APIs. Installed at
`~/game-dev-apis/`. Tested 2026-07-18.

## What this gives you

A single Python venv with all game-dev API SDKs, a unified client
class (`GameDevAPI`) that auto-activates any API whose key is set in
`.env`, and working access to free APIs that need no key at all.

## Install

```bash
# Create dedicated venv
uv venv ~/game-dev-apis
source ~/game-dev-apis/Scripts/activate   # Windows

# Python SDKs
uv pip install elevenlabs replicate fal-client openai httpx \
  pydantic python-dotenv websockets aiohttp anthropic hume
```

Node global SDKs (for JS-based pipelines):

```bash
npm install -g @elevenlabs/elevenlabs-js @anthropic-ai/sdk openai replicate
```

## Free APIs that work with zero keys

These are always available from the toolkit, no signup needed:

1. **AmbientCG** — 2,866+ CC0 PBR textures and HDRIs. REST API at
   `ambientcg.com/api/v1/full_json`. No key, no auth, just GET.
   ```python
   r = httpx.get('https://ambientcg.com/api/v1/full_json', timeout=30)
   assets = r.json()['Assets']  # dict of name → {Tags, DownloadCount, ...}
   ```

2. **Poly Haven** — CC0 HDRIs, textures, 3D models. Accessible via
   Blender MCP addon (enabled in addon settings). No direct REST API;
   use the blender_mcp socket commands `search_polyhaven_assets` and
   `download_polyhaven_asset`.

3. **Sketchfab** — 3D model marketplace. Search is free; downloads
   need an API key set in Blender MCP addon settings.

## Unified client

The `gamedev_api.py` file at `~/game-dev-apis/` provides:

```python
from gamedev_api import GameDevAPI
api = GameDevAPI()
api.status()  # → {'ambientcg': 'AmbientCGClient', 'blender_mcp': 'BlenderMCPClient', ...}
```

Any API with a key in `.env` is auto-enabled. APIs without keys are
skipped silently.

## API key locations

| API | Where to get key | Env var |
|---|---|---|
| Meshy | app.meshy.ai/settings/api | `MESHY_API_KEY` |
| Tripo3D | platform.tripo3d.ai | `TRIPO_API_KEY` |
| Hyper3D Rodin | hyper3d.ai | `HYPER3D_API_KEY` |
| ElevenLabs | elevenlabs.io/app/settings/api-keys | `ELEVENLABS_API_KEY` |
| FAL.ai | fal.ai/dashboard/keys | `FAL_KEY` |
| Replicate | replicate.com/account/api-tokens | `REPLICATE_API_TOKEN` |
| Inworld AI | studio.inworld.ai/settings/api-keys | `INWORLD_API_KEY` |
| Sketchfab | sketchfab.com/developers | `SKETCHFAB_API_KEY` |

## Self-hosted open-source models

Cloned to `~/Desktop/projects/`:

- **TripoSR** (64M) — single image to 3D mesh, unlimited, Apache 2.0.
  github.com/VAST-AI-Research/TripoSR
- **Hunyuan3D-2** (156M) — Tencent's open 3D generation model.
  github.com/Tencent/Hunyuan3D-2
- **BlenderProc** (111M) — procedural Blender scene pipeline for
  synthetic training data. github.com/DLR-RM/BlenderProc

## Pitfalls

1. **sketchfab-api PyPI package doesn't exist**. Use the REST API
   directly or via Blender MCP addon integration.
2. **Poly Haven has no public REST API**. Access is through the
   Blender MCP addon's built-in integration only.
3. **npm global omit=dev**: Same trap as everywhere — `npm install -g`
   silently strips dev deps. Not applicable here since these are
   runtime packages, but watch for it if installing SDK dev tools.
