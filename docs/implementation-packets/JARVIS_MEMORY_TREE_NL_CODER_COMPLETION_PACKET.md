# Implementation Packet — Memory Tree & NL Coder Completion

Status: **shipped in this PR.** This packet records what landed and the
bounded follow-ups.

## Shipped
- `MemoryTreeStore` (provenance, write policy, contradictions/supersession,
  ranked search, context packs, JSONL persistence, exports).
- `natural_language_coder` full packetizer (intents, risk classes, owner
  gates, routing, validation, markdown, gate-packet).
- CLI: `packetize`, `packet --markdown/--validate/--gate-check`,
  `memory-tree {add,search,outline,export-markdown} --store`.
- Tests: `tests/test_jarvis_prime_memory_tree.py`,
  `tests/test_jarvis_prime_natural_language_coder.py`.

## Files involved
`hermes_cli/jarvis_prime/memory_tree.py`,
`hermes_cli/jarvis_prime/natural_language_coder.py`,
`hermes_cli/jarvis_prime/__main__.py`, `hermes_cli/jarvis_prime/__init__.py`.

## Exact commands
```bash
python -m compileall -q hermes_cli/jarvis_prime
pytest -q tests/test_jarvis_prime_memory_tree.py tests/test_jarvis_prime_natural_language_coder.py
python -m hermes_cli.jarvis_prime packetize "add memory tree support" --json
```

## Owner gates
None executed. The packetizer only describes owner gates; durable memory
writes that touch decisions require owner approval per the write policy.

## Rollback
Additive; legacy `MemoryTree`/`MemoryChunk` and prior CLI unchanged. Revert
the branch to fully undo.

## Remaining (bounded follow-ups)
1. ~~Optional: promote Memory Tree retrieval into the runtime's recollect
   path behind a flag (today `MemoryStore` remains the default recall).~~
   **Done (MEM-2).** `JarvisPrime.recollect` now *augments* the legacy
   `MemoryStore` block with a token-bounded, source-cited Memory Tree
   context pack; `JarvisPrime.observe_turn` captures six typed candidates
   per turn as session-layer **PROPOSED** nodes (never auto-durable). Wired
   into the cockpit chat responder, exposed over new cockpit Tree endpoints
   (`/v1/cockpit/memory/tree*`, `/contradictions*`, `/freshness`), and
   surfaced on the Android Memory screen (Inbox / Conflicts / Review tabs).
   Default ON; `HERMES_MEMORY_LAYERS=0` reverts to legacy-only recall. See
   `hermes_cli/jarvis_prime/memory_capture.py`, `runtime.py`,
   `gateway/cockpit/handlers.py`, and `apps/android/.../data/memory/`.
2. Optional: semantic (embedding) retrieval lane — currently deterministic
   lexical only by design (avoids a vector-store dependency).
