# Status — guide-first (LEGO) shipped; SRD 8B train still running

## Verified this pass
- **Guide-first** skill: `skills/creative/guide-first/` — official + one
  dated ledger tutorial → instruction card → judge → swap if blocky.
- SFT `guide-first.jsonl` 24 rows merged to 1544. Continue-train queued
  until the in-flight 1520-row SRD job frees the 8GB GPU.
- SRD 5.1/5.2.1 CC-BY corpus ingested (not copyrighted D&D books).
- **Legal RPG corpus (not copyrighted D&D books).** PHB/MM/DMG/adventure modules refused.
  Official **SRD 5.1 + 5.2.1 CC-BY-4.0** via https://www.dnd5eapi.co + Wizards SRD page.
  Credit: `C:\Users\Echer\models\agents\game-pipeline\datasets\srd\ATTRIBUTION.md` and `docs/game-studio/SRD-ATTRIBUTION.md`
  - 319 SRD spells (full text)
  - 334 SRD monsters (stat blocks)
  - 12 SRD classes, 9 races, 15 conditions
  - 362 SRD magic items, 237 equipment cards
  - Original mission/dungeon/land cards for the 9 holds
  - `srd-rpg.jsonl` **1344** + WorldClaw **176** → `worldclaw-srd-train.jsonl` **1520**
- **8B continue-train running** from existing adapter on the 1520-row mix (2 epochs, 380 steps).
- Prior 176-row QLoRA: 3 epochs, 66 steps, 328.9 s, loss 2.049, acc 0.858
- CC0 Poly Haven 2K + wheat kit on HearthTerrain (769 PBR actors, 0 BasicShapes)

## Honest ceiling
- Not all D&D books. Legal complete ruleset = SRD only.
- LoRA does not emit 37 km².
- No Landscape+PCG, no packaged `.exe`

## Remaining
Finish 8B SRD continue-train + smoke infer. Then Nanite/PBR, Landscape+PCG, packaged cell, 27B finish + hole-check + mmproj + hardlink.
