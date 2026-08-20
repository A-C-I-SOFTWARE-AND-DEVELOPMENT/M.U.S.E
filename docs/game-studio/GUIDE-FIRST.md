# Guide-first (LEGO box)

Seats do not invent a 3D pipeline. They open a box of instructions.

1. Classify the fail (`blocky`, `no UVs`, `grey plastic`, `float`).
2. Open `skills/creative/guide-first/references/guide-ledger.md`.
3. Take **one official doc** + **one dated high-signal tutorial**.
4. Distill to `instruction-card.json` (numbered steps).
5. Execute in order. Adapt names to the kit. Do not skip.
6. Judge. If FAIL, a *different* URL. Max two swaps.

Runner:

```powershell
python skills/creative/guide-first/scripts/follow_guide.py `
  --task blender-kit --subject pine `
  --symptom "blocky, no bevels" `
  --out C:\Users\Echer\models\agents\game-pipeline\reports\r_hearth
```

The LoRA is trained to *drive* this loop. It does not replace the card.
