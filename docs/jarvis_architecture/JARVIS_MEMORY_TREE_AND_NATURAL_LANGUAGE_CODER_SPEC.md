# Memory Tree & Natural-Language Coder — Spec

Status: **shipped**. Files: `hermes_cli/jarvis_prime/memory_tree.py`,
`hermes_cli/jarvis_prime/natural_language_coder.py`. Tests:
`tests/test_jarvis_prime_memory_tree.py`,
`tests/test_jarvis_prime_natural_language_coder.py`.

## Memory Tree (`MemoryTreeStore`)

Three layers: `working`, `session`, `durable`. Durable nodes carry: stable
id, namespace, layer, title, summary, text/chunk refs, source pointers,
source URI, source trust tier, confidence, sensitivity, approval state,
freshness due date, contradiction status, supersedes/superseded_by,
timestamps, tags.

### Write policy (`MemoryWritePolicy`)
- Rejects secret-like text (API keys, tokens, private keys, session
  cookies, `password=…`) and chain-of-thought.
- Rejects `secret`-class sensitivity.
- Durable facts require provenance **or** owner approval.
- Durable writes below the confidence floor (0.6) require owner approval.
- Transient emotional state is **downgraded** durable → session.
- `dry_run=True` validates without committing.

### Contradictions & supersession
New durable facts never silently overwrite. Conflicting high-confidence
facts about the same `subject` create a `ContradictionReport`; both nodes
become `CONTESTED` and are excluded from default search/context packs.
`resolve_contradiction(report_id, winner_id)` records resolution: the
winner is `RESOLVED` + owner-approved, the loser is `SUPERSEDED`.

### Retrieval & context packing
`search()` ranks by term overlap, namespace, source trust, confidence,
layer, approval, and freshness (stale penalized). `context_pack(query,
token_budget, …)` packs source-cited sections under a hard token budget
and reports excluded contested nodes.

### Persistence
Local JSONL at `~/.hermes/jarvis_prime/memory_tree.jsonl` (caller-supplied
path for tests). Atomic writes, owner-only perms (best effort), malformed
lines tolerated with diagnostics, no network.

### Exports
`to_dict()`/`from_dict()`, `export_markdown(namespace=None)`,
`export_audit_cards(namespace=None)`, `outline()`.

### Backward compatibility
The lightweight stateless `MemoryTree`/`MemoryChunk` are unchanged and
still back the `memory-tree --add/--search` CLI lane.

## Natural-language coder (packetizer)

`build_work_packet(prompt, repo_root='.', branch_prefix='jarvis',
allowed_files=None, forbidden_files=None, context=None)` →
`CodingWorkPacket`. It **never executes**.

Intents: research, audit, implement, review, test, document, refactor,
model_routing, memory, android, avatar_presence, device_action, release,
security, unknown.

Risk classes: RC0 read-only · RC1 narrow local code/docs/tests · RC2
multi-file code · RC3 device/auth/external/release/spend · RC4 blocked.

Owner gates (`OwnerGate`): merge_main, deploy, publish, external_message,
purchase_or_spend, oauth_or_credentials, security_sensitive_change,
destructive_file_operation, android_accessibility_gesture,
app_store_or_public_release, explicit_or_mature_content_confirmation.

`validate_work_packet()` returns structured findings and fails on: unsafe/
missing branch, main/master target, empty allowed_files for write intents,
owner gates present below RC3, same builder/reviewer for RC2+, missing
rollback/acceptance/verification, empty mission, forbidden∩allowed overlap,
and blocked requests. `to_gate_packet()` is consumable by
`gates.run_gate_summary()` and passes the planning gate when complete.
`render_packet_markdown()` renders mission/risk/owner gates/verification/
rollback.

## CLI
```bash
python -m hermes_cli.jarvis_prime packetize "<request>" --json
python -m hermes_cli.jarvis_prime packetize "<request>" --markdown
python -m hermes_cli.jarvis_prime packet "<request>" --gate-check
python -m hermes_cli.jarvis_prime packet "<request>" --validate
python -m hermes_cli.jarvis_prime memory-tree add "ns::title::text" --store PATH --layer durable --source URI --trust primary --confidence 0.9
python -m hermes_cli.jarvis_prime memory-tree search "<query>" --store PATH
python -m hermes_cli.jarvis_prime memory-tree outline --store PATH
python -m hermes_cli.jarvis_prime memory-tree export-markdown --store PATH
```

## Owner gates / rollback / risks
- Owner gates: none executed; packetizer only describes them.
- Rollback: additive modules; legacy classes untouched; revert branch.
- Remaining risk: contradiction detection keys on `subject` (title by
  default); cross-subject semantic conflicts are out of scope by design.

## Live-loop wiring (MEM-2)

The Memory Tree is wired into the live muse loop — it no longer sits
beside it. The wiring **augments, never replaces** the legacy
`MemoryStore`, and is on by default (`HERMES_MEMORY_LAYERS=0` reverts to
byte-identical legacy recall).

**Recollection.** `JarvisPrime.recollect(query)` appends a token-bounded,
source-cited `MemoryTreeStore.context_pack` block after the legacy
recollection. Contested facts are excluded from the pack; sources are always
cited (memory cites, it never becomes the source of truth).

**Capture.** After a completed turn, `JarvisPrime.observe_turn(user, reply)`
extracts six typed candidates via deterministic cue heuristics
(`memory_capture.py`): `user_preference`, `project_decision`,
`architecture_fact`, `verified_code_fix`, `research_finding`,
`failed_assumption`. User text is owner-trusted; assistant/tool text is
low-trust so a model's own words can't self-promote. Candidates are written
**session-layer, PROPOSED** — never auto-durable. The write policy rejects
secrets / chain-of-thought / secret-class content. Wired into the cockpit
chat responder (`gateway/cockpit/agent.py`).

**Owner control (mobile).** Promotion to durable is owner-gated. The cockpit
exposes:

```
GET  /v1/cockpit/memory/tree?q=&include_contested=   ranked, cited search
GET  /v1/cockpit/memory/tree/proposed                proposed-memory inbox
POST /v1/cockpit/memory/tree/{id}/decision           approve | reject | supersede
GET  /v1/cockpit/memory/contradictions               open contradiction reports
POST /v1/cockpit/memory/contradictions/{id}/resolve  pick a winner
GET  /v1/cockpit/memory/freshness?within_days=        overdue review
```

`approve` promotes a candidate to durable and **re-runs contradiction
detection** — a conflict opens a `ContradictionReport` and is returned to
the caller rather than silently overwriting an existing durable fact. The
Android Memory screen surfaces these as the **Inbox / Conflicts / Review**
tabs (`apps/android/.../ui/screens/memory/`).

**Safety invariants preserved:** never silently overwrite (contradiction +
supersession); durable requires owner approval; secrets / chain-of-thought
rejected; capture is best-effort and never breaks a turn.

## Optional dense-embedding retrieval lane

Retrieval defaults to deterministic term-overlap scoring. Phase 1 (Option C) of
the JEPA integration adds an **opt-in, default-off** dense-embedding lane that
blends a cosine-similarity term into `MemoryTreeStore.search` / `_score`,
reusing the holographic plugin's embedding backend
(`plugins/memory/holographic/embeddings.py`). Implementation:
`hermes_cli/jarvis_prime/memory_tree_embeddings.py`.

- **Off by default:** with no config, retrieval is byte-for-byte the legacy
  keyword search (the dense term is 0 and zero-overlap candidates are dropped).
  When active, the query is embedded once and semantic-only candidates are kept
  so similarity can surface them.
- **Enable:** `HERMES_MEMORY_TREE_EMBEDDINGS=1`
  (`HERMES_MEMORY_TREE_EMBED_WEIGHT`, `..._BACKEND`, `..._MODEL`,
  `..._BASE_URL`), or a positive `JarvisConfig.memory_tree_embedding_weight`.
- **Storage:** a rebuildable JSONL **sidecar** (`memory_tree.emb.jsonl`) keyed
  by node id + text hash + model — the authoritative `memory_tree.jsonl` never
  carries vectors; `memory-tree reindex` rebuilds it. No FAISS/ANN (brute-force
  cosine over active nodes; the tree is small).
- **Graceful + safe:** a missing/failed backend degrades to the neutral
  keyword path; all existing filters (active / non-contested / awaiting-review)
  and the write policy are unchanged. Reuses the existing
  `memory.embeddings_local` lazy dep (no new root dependency).
- **Gated adoption:** `memory_tree_eval.score_retrieval` measures recall@k / MRR
  for keyword vs blended on a held-out set and disposes of the result through
  `benchmark_gate.evaluate_improvement` — turn the lane on only when it clears
  `min_margin`; otherwise keep keyword search.

Text chunks use a permissive text embedder; reserve frozen I-JEPA/V-JEPA
inference (CC-BY-NC, non-commercial) for image/video chunks only.
