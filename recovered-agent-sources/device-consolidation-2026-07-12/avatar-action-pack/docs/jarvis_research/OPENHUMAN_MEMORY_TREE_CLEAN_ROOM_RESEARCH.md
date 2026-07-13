# OpenHuman Memory Tree → JARVIS Prime Clean-Room Integration

## Decision

Do not copy OpenHuman code into Hermes/JARVIS Prime. Use a clean-room
implementation of the Memory Tree pattern inside `hermes_cli/jarvis_prime/`.
The ACI org OpenHuman repo is public, and its license file is GPLv3, so direct
code fusion into Hermes risks dragging copyleft obligations into the Hermes
runtime. Keep this repo test ZIP self-contained and implement only the ideas:
canonical chunks, hierarchical summaries, source provenance, confidence, local
reviewability, and context packing.

## Evidence gathered

- ACI org has `A-C-I-SOFTWARE-AND-DEVELOPMENT/openhuman`, public, default
  branch `main`.
- OpenHuman README describes a Memory Tree + Obsidian Wiki: connected data is
  canonicalized into bounded Markdown chunks, scored, folded into hierarchical
  summary trees, and stored locally in SQLite with Obsidian-compatible markdown.
- OpenHuman README describes auto-fetch on a recurring loop, integrations,
  TokenJuice compression, model routing, native voice, and a desktop mascot.
- OpenHuman license file is GNU GPLv3.

## JARVIS-safe interpretation

OpenHuman is the memory architecture reference, not a code dependency.
JARVIS Prime should implement:

1. **Memory chunks** — bounded, source-backed, confidence-scored records.
2. **Memory tree nodes** — hierarchical summaries over chunks.
3. **Context packs** — token-budgeted retrieval blocks for model/tool handoff.
4. **Auditability** — human-readable JSONL first, SQLite/Obsidian mirror later.
5. **Permission discipline** — no secrets, raw voice, raw camera, or unverified
   claims stored by default.
6. **Contradiction discipline** — future node conflict reports before overwrite.
7. **Owner control** — durable strategy, pricing, legal, privacy, and identity
   memories require owner approval.

## Implemented in this local ZIP

- `hermes_cli/jarvis_prime/memory_tree.py`
- `tests/test_jarvis_prime_memory_tree.py`

This is intentionally small. It is enough for local testing and can later be
wired into the existing `JarvisPrime.recollect()` flow after review.

## Next build lane

Add an adapter that mirrors accepted memory chunks to:

```text
~/.hermes/jarvis_prime/memory_tree.jsonl
~/.hermes/jarvis_prime/obsidian_vault/<namespace>/<topic>.md
```

Then add a `python -m hermes_cli.jarvis_prime memory-tree ...` CLI surface:

- `ingest`
- `search`
- `outline`
- `context-pack`
- `approve`
- `reject`

## Hard no-go lines

- Do not vendor GPL OpenHuman code into Hermes core.
- Do not silently persist secrets or temporary emotions.
- Do not let Memory Tree replace GitHub, tests, CI, or docs as source of truth.
- Do not make the avatar feel alive by hiding surveillance behavior.
