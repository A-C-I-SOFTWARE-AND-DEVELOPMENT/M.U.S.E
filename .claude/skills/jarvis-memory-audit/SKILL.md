---
name: jarvis-memory-audit
description: Audit the JARVIS Memory Tree for contradictions, stale facts, missing provenance, and contested entries; export audit cards.
---

# jarvis-memory-audit

Use to review the health of durable memory before relying on it.

## Steps
1. Outline and export the tree:
   ```bash
   python -m hermes_cli.jarvis_prime memory-tree outline --store ~/.hermes/jarvis_prime/memory_tree.jsonl
   python -m hermes_cli.jarvis_prime memory-tree export-markdown --store ~/.hermes/jarvis_prime/memory_tree.jsonl
   ```
2. In code, inspect open contradictions and audit cards:
   ```python
   from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore
   store = MemoryTreeStore.load()
   print(store.open_contradictions())
   print(store.export_audit_cards())
   ```
3. For each open contradiction, gather evidence and propose a resolution to
   the owner. Resolution (`resolve_contradiction`) supersedes the losing
   record — it is owner-approved, not silent.

## Never
- Never delete or overwrite a node directly; use supersession.
- Never store secrets, credentials, or chain-of-thought.
