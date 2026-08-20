---
name: local-role-loras
description: "Use when adding a local LM per agent role."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [unsloth, lora, qwen, game-studio, seats, vlm]
    category: mlops
    related_skills: [muse-local-llm, game-studio, seat-roster]
---

# Local Role LoRAs

One shared multimodal GGUF + a named LoRA per Hermes seat or game-studio
role. That *is* a separate LM per agent. Copying a 27B per role is not.

## When to Use

- "add a trainable qwen to unsloth"
- "a separate LM for each agent"
- "train an LM for each game-pipeline job title"
- Any request to give seats/roles their own local weights on this 8 GB box

Do not use for Laguna inference ops (`muse-local-llm`) or for routing a game
brief (`game-studio`). Those skills own launch and production; this skill owns
the **weight layout**.

## Hardware truth (this machine)

RTX 5070 Laptop **8 GB VRAM** + **32 GB RAM**. Typical free disk ~70 GB.

| Ask | Fits? |
|---|---|
| One Qwen3.8-27B UD-Q3_K_XL + mmproj (~14.3 GB) | yes |
| 7–9 full 27B copies | **no** (~94–121 GB) |
| GPU-resident QLoRA of 27B | **no** (Unsloth table ~56 GB VRAM) |

There is **no** `unsloth/Qwen3.8-27B-unsloth-bnb-4bit` (HF 404).

**Studio will not train GGUF.** `POST /api/train/start` with
`model_format: gguf` returns `400 training_model_gguf_not_trainable`.
The 27B UD-Q3_K_XL is the **inference** base only.

**Trainable path on this box:** `unsloth/Qwen3-8B-bnb-4bit` (safetensors)
via the `muse-local-llm` QLoRA playbook (`device_map={'': 0}`). Start
adapters as soon as that file is complete — do not wait on the 27B GGUF.

## Naming (owner-corrected)

**Qwen3.8-27B** is a 27B native VLM. It is **not** Qwen3-8B (the 8B QLoRA
base owned by the `muse-local-llm` skill). If the owner says "qwen 3.8 27b",
do not swap in an 8B.

## Architecture

| Layer | What | Disk |
|---|---|---|
| Shared base | `unsloth/Qwen3.8-27B-GGUF` **UD-Q3_K_XL** + `mmproj-F16` | ~14.3 GB |
| Per-role LM | LoRA named for the job title | ~200–400 MB |

Slots: `C:\Users\Echer\models\agents\`

- Seats: `orchestrator`, `executor`, `critic`, `researcher`, `operator`, `scribe`, `game-creator`
- **Game pipeline first:** `game-pipeline/{studio-director,game-designer,level-designer,gameplay-engineer,graphics-tech-artist,3d-asset-artist,audio-designer,qa-playtest,build-release-engineer}`

World Vision (Reactor/LingBot) and WorldClaw are **workflows**, not a tenth
weight file. WorldClaw maps onto the nine game-studio seats (see the
`game-studio` skill).

After the GGUF lands, **hardlink** it into each slot. Do not copy.

## Studio download

API `:8888`, bearer `UNSLOTH_API_KEY`, optional `X-Unsloth-HF-Token`.

```
POST /api/hub/download
  repo_id: unsloth/Qwen3.8-27B-GGUF
  gguf_variant: UD-Q3_K_XL
  transport_mode: http
  use_xet: false
```

**Xet stalls at 0 bytes.** Force HTTP. Cancel stuck jobs with
`POST /api/hub/download/cancel` `{repo_id, gguf_variant, generation}`.
Watch the `.incomplete` blob under
`~/.cache/huggingface/hub/models--unsloth--Qwen3.8-27B-GGUF/blobs/` —
Studio `download-progress` can sit at 0 while bytes land.

`POST /api/hub/scan-folders` `{path: C:\Users\Echer\models\agents}` so slots
show up. `/v1/models` 200 ≠ loaded.

Do not pick `Q4_K_S` — not Unsloth Dynamic.

## Procedure

1. Confirm the owner means Qwen3.8-27B (27B VLM), not Qwen3-8B.
2. Refuse N full 27Bs. State the shared-GGUF + LoRA layout immediately.
3. Cancel any Xet / `Q4_K_S` pull. Start `UD-Q3_K_XL` over HTTP.
4. Ensure one folder + `JOB.md` per role (game-pipeline first).
5. When the blob completes: verify it is not a sparse hole (see Pitfalls),
   then hardlink + scan-folders.
6. Start 8B QLoRA as soon as `Qwen3-8B-bnb-4bit` `model.safetensors` is
   complete — do not block adapters on the 27B GGUF.
7. Vision-heavy adapters first: `graphics-tech-artist`, `3d-asset-artist`,
   `level-designer`, `qa-playtest`.
8. Say up front: a LoRA does not emit a Skyrim-class world. Density lives
   in World Partition + PCG + instanced kits.

## Pitfalls

- Treating "3.8" as an 8B model.
- Copying the GGUF seven/nine times.
- Starting `Q4_K_S` because the picker shows it first.
- Promising GPU QLoRA of 27B on this card.
- **Submitting a GGUF to Studio `/api/train/start`.** It 400s. Train
  safetensors/bnb-4bit (8B) instead.
- `check-vision` on a missing bnb-4bit repo 404s then hangs ~60s.
- Adding a tenth seat for World Vision or WorldClaw.
- Treating `ls` size or GGUF magic as "download done". Multi-range
  writers can leave a file whose size is the highest offset written
  and whose middle is zeros. Sample ≥8 evenly spaced 4 KiB blocks;
  any all-zero block means holes — delete and sequential-resume.
- Splitting one CDN pipe across 27B + mmproj + 8B at once. Measure
  one stream first.
- Claiming a world exists because training loss dropped. Eval =
  world-spec + terrain + instance place + packaged `.exe` cell load.
- Studio `state=running` with 0-byte blobs. Trust blob `st_size`
  growth over 10–15s, not the active-downloads row.
- **Empty HF cache ≠ in-progress.** A prior turn claimed ~1.9/13.4 GB
  in `models--unsloth--Qwen3.8-27B-GGUF/blobs/` while that folder was
  empty and Studio `active-downloads` was `[]`. Canonical pull is
  sequential curl into `C:\Users\Echer\models\agents\game-pipeline\base\`
  via `resume-qwen38-gguf.py` (HF token, `-C -`, 8-block hole check).
  Do not restart aria2 multi-range (403 / holes).

## RPG / D&D corpus

Do **not** ingest copyrighted D&D books. Legal path is SRD 5.1/5.2.1
CC-BY-4.0. Builder: `C:\Users\Echer\models\agents\game-pipeline\datasets\build_srd_sft.py`.
Attribution: `docs/game-studio/SRD-ATTRIBUTION.md`.

## References

- `references/unsloth-studio-api.md` — Studio download endpoints, cancel, scan-folders.
- `references/studio-train-and-completeness.md` — GGUF-not-trainable, check-format/chatml, hole check.

## Overlap

`muse-local-llm` still owns Laguna launch + the **Qwen3-8B** QLoRA specialist
path. `game-studio` owns production routing + WorldClaw stages. This skill
only owns the local per-role weight layout. Adopt those two if the curator
should maintain them: `hermes curator adopt muse-local-llm` /
`hermes curator adopt game-studio`.
