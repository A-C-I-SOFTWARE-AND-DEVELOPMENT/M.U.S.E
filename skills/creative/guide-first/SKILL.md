---
name: guide-first
description: "Look up a top-quality how-to, distill it to LEGO steps, follow or adapt. Use when an asset is blocky/crap, a seat does not know the next step, or the user says follow a tutorial."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    category: creative
    tags: [tutorial, blender, unreal, pbr, qa, game-studio, lookup]
    related_skills: [game-studio, muse-frontier-assets, game-asset-pipeline]
---

# Guide-First (LEGO box)

A toddler can assemble a whole set if the box has the right numbered
steps. Seats here do the same: **do not invent a pipeline**. Open the
box (official doc + one dated high-signal tutorial), lay out the
pieces (instruction card), snap in order, then look at the photo on
the box (quality judge). If it is blocky or wrong, **get a different
box** — do not mash the same bricks harder.

This is the production process. The LoRA is trained to *drive* it.
Weights do not replace the card.

## When to use

- 3D asset looks blocky, default-cube, stretched, floating, or "AI slop"
- Seat does not know a Blender / UE / PBR / FBX step
- User says "look up a tutorial", "follow a guide", "how-to"
- QA bounce: missing `instruction-card.json` or `lookups.md`

Do not use this to scrape paid courses or Megascans into jsonl.

## Hard rules

1. **Allowlist only.** Rank from `references/guide-ledger.md`. Refuse
   clickbait, "60-second Blender", undated shorts, and purple AI mesh
   videos.
2. **Two sources, then stop.** One official doc + one dated tutorial
   (engine ≥ 5.3 or Blender ≥ 4.0). Write both URLs.
3. **Distill to a card.** Never "watch this and vibe". Emit
   `instruction-card.json` (schema in `references/instruction-card.schema.json`).
4. **Execute in order.** Adapt a step to the current kit (pine ≠ barrel)
   but do not skip numbered steps.
5. **Judge, then swap.** If the judge fails, pick the *next* ledger
   guide (different URL). Max **2** swaps. Same URL twice = process fail.
6. **Evidence.** `reports/<task>/lookups.md` + `instruction-card.json`
   + judge verdict in the same message. Missing any one = QA FAIL.

## Loop

```
gap or judge FAIL
  → classify task (blender-kit | fbx-ue | pbr | landscape | pcg | lighting)
  → ledger.pick(official, tutorial, exclude=already_tried)
  → distill(official, tutorial) → InstructionCard
  → execute steps 1..N (adapt names/paths, keep order)
  → judge(artifact)
  → PASS: ship + provenance
  → FAIL: swap guide (budget 2) or return to 3d-asset-artist
```

Runner (no GPU, safe while QLoRA is training):

```powershell
python skills/creative/guide-first/scripts/follow_guide.py `
  --task blender-kit --subject pine `
  --symptom "blocky, no bevels, default material" `
  --out C:\Users\Echer\models\agents\game-pipeline\reports\r_hearth
```

Optional mesh judge:

```powershell
python skills/creative/guide-first/scripts/follow_guide.py `
  --judge C:\Users\Echer\models\agents\game-pipeline\assets\kits\pine.fbx
```

## Quality judge (blocky / crap)

FAIL if any:

| Signal | Why |
|---|---|
| Leftover default cube / plane / Suzanne | Not a kit |
| All 90° edges, no bevel / support loops | Toy brick, not game-ready |
| No UVs or 0-area islands | Cannot take PBR |
| Only Principled default (no albedo/normal/rough) | Grey plastic |
| `min_z` not ~0 | Float |
| Hero mesh < ~200 tris *and* box silhouette | Undermodeled |
| Purple / indigo / violet | House ban |
| No instruction card | Guessed the pipeline |

PASS needs: grounded pivot, triangulated FBX (`FBX_SCALE_NONE`, `-Z`/`Y`),
PBR trio (diff/nor/rough), lookups + card cited.

## Training

SFT teaches the *process*, not mesh bytes. Builder:

`C:\Users\Echer\models\agents\game-pipeline\datasets\build_guide_first_sft.py`

Merge into `worldclaw-srd-train.jsonl`. Continue-train the 8B adapter
after the current SRD job — do not start a second GPU train.

## Pitfalls

- Citing a URL without a numbered card (that is a bookmark, not a box).
- Following a 2018 Blender 2.79 video on 5.2.
- Second try on the same Grant Abbitt URL after it already failed.
- Claiming SOTA because the LoRA loss dropped.
- Scraping FlippedNormals / Gnomon / paid Fab into jsonl.
