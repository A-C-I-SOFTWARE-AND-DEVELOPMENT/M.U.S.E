---
name: ue5-render
description: "Turn a prompt packet into a gated, ledgered Unreal Engine 5 offscreen render."
version: 1.0.0
author: Jeremiah Echerd + Hermes Agent
license: MIT
platforms: [linux, macos, windows]
---

# UE5 Render

Drive a locally running, free Unreal Engine 5 editor from muse live
control over the Remote Control API, and owner-gated offscreen
Movie-Render-Queue renders. Every action lands on the axiom event
chain (`ue5.ping` / `ue5.console` / `ue5.py` / `ue5.render`), so the
render's history verifies.

## When to Use

- Jeremiah asks for a cinematic, b-roll, product shot, scene render,
  or "make UE5 do X".
- A creative prompt packet (prompt → sequence/script) needs to become
  frames on disk.
- Builder mode needs a repeatable render recipe rather than a one-off.

## Preconditions (one-time, on the UE5 machine)

1. Install free UE5; open any project.
2. Enable **Remote Control API** and **Python Editor Script Plugin**
   (tick *Enable Remote Execution*).
3. Verify liveness:

```bash
python -m hermes_cli.jarvis_prime.research_fabric.ue5 ping       # → "ok": true
python -m hermes_cli.jarvis_prime.research_fabric.ue5 discover   # → node id
```

## Workflow

1. **Packetize the prompt.** Use
   `build_prompt_packet(prompt, modality=..., style=...)` from
   `hermes_cli.jarvis_prime.research_fabric.ue5` — background-only
   surface, no visible UI.
2. **Stage the scene.** Drive the editor live; small steps, verify each:

```bash
python -m hermes_cli.jarvis_prime.research_fabric.ue5 console "stat fps"
python -m hermes_cli.jarvis_prime.research_fabric.ue5 py "import unreal; unreal.log('muse')"
```

   Use editor Python (`py`) to build/modify the Level Sequence from the
   packet (camera, actors, timing). Long scripts: pipe via `py -`.
3. **Dry-run the render command.** `launch_offscreen_render(...)`
   *without* the grant returns the exact command and `"spawned": false`
   — show this to the owner first.
4. **Owner gate.** Rendering spawns a process — it waits for the owner
   to set `MUSE_UE5_ALLOW_SPAWN=1` for the invocation. Never set it
   yourself; never work around it.

```bash
MUSE_UE5_ALLOW_SPAWN=1 python -m hermes_cli.jarvis_prime.research_fabric.ue5 render \
    /path/Proj.uproject /Game/Maps/Main /Game/Cinematics/Seq --output-dir /tmp/frames
```

5. **Verify, don't vibe.** Frames exist on disk; the `ue5.render` event
   is on the chain:

```bash
python -m hermes_cli.jarvis_prime.axiom_bridge tail -n 5
python -m hermes_cli.jarvis_prime.axiom_bridge audit   # chain_valid must be true
```

## Builder-mode recipe

For repeatable renders, Builder mode emits a packet with:

- **intent**: one EARS-style sentence ("WHEN the owner approves, THE
  renderer SHALL produce N frames of <scene> at <res>.")
- **inputs**: project file, map, sequence, MRQ config asset, output dir
- **gates**: test (ping + discover green), security (no visible UI,
  background-only), owner_approval (`MUSE_UE5_ALLOW_SPAWN`), rollback
  (delete output dir; editor state untouched — renders are additive)
- **evidence**: the dry-run command, the `ue5.render` chain event, a
  frame listing (`ls <output-dir> | head`)

## Hard Rules

- Process spawn is owner-gated. A missing grant is an answer, not an
  obstacle.
- Background-only: never pop visible editor UI on the owner's machine.
- Python sent to the editor is fingerprinted on the chain (sha256+len),
  never stored — keep scripts in the repo or packet for review.
- No render claim without the frame listing and the chain event in the
  same message.
