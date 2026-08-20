# Hearthhold contact gate

## Deterministic
- placed in still: 1813 (heroes 5, pine 1046, rock 122, wheat 480, clutter 160)
- missed ground rays: **0**
- sink: 4 cm
- still: `reports/r_hearth/contact.png` 1600x900, 1.7 MB
- brightness: mid (not black, not blown). Edges present. No purple.

## Visual (this still)
- Trees are joined trunk+cone. Contact looks planted.
- Terrain pad is flattened on purpose (settlement). Background shows a stepped pad wall, not authored cliffs.
- Kits are **primitives**. This is greybox density, not Skyrim beauty.
- Buildings are buried in pines — layout needs a cleared street.

## Verdict
CONTACT rays: PASS.
Skyrim-quality: **FAIL**. Need Nanite kits + UE World Partition + PCG + packaged `.exe`.
