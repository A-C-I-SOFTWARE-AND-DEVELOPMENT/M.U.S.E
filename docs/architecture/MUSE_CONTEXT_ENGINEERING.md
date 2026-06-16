# M.U.S.E Context Engineering

How M.U.S.E manages the information an agent needs — memory, state, tools, and
retrieved knowledge — mapped to the real subsystems in this repo. The point of
this page: the modern "context engineering" playbook (the four core elements,
agentic RAG, CAG, static-vs-dynamic context, plan-first prompting) is **already
structurally enforced** in MUSE; this records where, and the few additive
directions still open.

## The four core elements → MUSE subsystems

| Element | What it is | Where it lives in MUSE |
|---|---|---|
| **Memory systems** | short-term (conversation) + long-term (durable, sourced) | Memory Tree + Research Vault (`hermes_cli/jarvis_prime/research_vault.py`) — provenance-bound, with confidence floors, contradiction reports, supersession, and no silent overwrites; FTS5 session search for cross-session recall. See `cognition_memory` in the [component registry](MUSE_COMPONENT_REGISTRY.md). |
| **Dynamic state management** | tracks multi-step task progress | Work packets (`hermes_cli/jarvis_prime/work_packet.py`) + the orchestrator Job/task DAG (`hermes_cli/orchestrator_api.py`): each phase is a validatable unit on the kanban graph, with a tamper-evident decision ledger. |
| **Tool schemas** | defined tool APIs + parameters | the plugin/tool registry (`hermes_cli/plugins.py`, `toolsets.py`) — every tool ships a schema; tools are opt-in via the `plugins.enabled` allowlist and gated by `requires_env`. |
| **Retrieved knowledge** | inject task-relevant facts at the moment of need | GraphRAG (`hermes_cli/jarvis_prime/graphrag/`, now including typed `COMPONENT` nodes) + the evidence engine (BM25 + memory hybrid with citation verification) + **fusion** retrieval (`second_brain/`). |

## Agentic RAG

MUSE's retrieved-knowledge path is agentic RAG, not single-shot lookup: GraphRAG
answers local/global/coding queries over a typed, source-backed graph, and the
evidence engine verifies citations before injection. **Fusion** (`second_brain/`)
adds hybrid dense+graph+keyword signal blending — combining vector similarity,
memory confidence, and recency into one ranking. The fusion *ranking* is also
available **database-free** in MUSE via
[`hermes_cli/jarvis_prime/fusion_ranker.py`](../../hermes_cli/jarvis_prime/fusion_ranker.py)
(a faithful port of Second Brain's blend, same weights + `SECOND_BRAIN_W_*` env
overrides), so MUSE can fuse the candidates its own retrieval already produces
without the Postgres/Neo4j backend. Retrieval is explainable
(deterministic path-based CITES edges, no opaque embedding guesses) so every
injected fact is attributable.

## Static vs. dynamic context (and CAG)

MUSE already separates the constant from the changing through **TokenJuice**, its
deterministic, token-bounded context compiler that screens secrets:

- **Static context** — system instructions, the MUSE persona, and tool schemas.
  Constant across turns and therefore ideal for provider **prefix-caching**
  (cache-augmented generation, CAG) to cut cost and latency.
- **Dynamic context** — the current request, task status, tool outputs, and
  recent history, appended on the fly to keep the window focused.

**Open additive direction (CAG):** expose TokenJuice's static block as an
explicit, stable, prefix-cache-friendly segment so providers that support prompt
caching reuse it across turns. This is purely a packaging/ordering change to the
compiled context — no new dependency — and is tracked as a follow-up to be done
against a clean base with CI validation.

## Plan-first + strict boundaries (ReAct / Reflexion, structurally)

The agent-prompting principles ("force a plan before acting", "define what the
agent must not do") are enforced by MUSE's **gates**, not by prompt text alone:

- **Plan first** → the Planning gate (`gates.py:planning_gate`) requires a
  mission, scope, allowed files, non-goals, and acceptance criteria before
  execution; the eight-gate chain then runs Build → Review → Test → Security →
  Release → Owner Approval → Rollback.
- **Strict boundaries / "don't act without confirmation"** → owner gates
  (`owner_auth.OWNER_GATED_ACTIONS`) + the Autonomy Charter (bounded, scoped,
  revocable), with a permanent C34 hard wall keeping the safety-critical core
  (gates, owner-auth, model registry, routing, verifier, Constitution)
  owner-gated forever.
- **Reflexion (evaluate + retry)** → the Review/Test gates loop work back to the
  builder on a blocking finding, and the research fabric's canary re-checks and
  auto-rolls-back on regression.

## Model choice as context (the registry)

Which model runs a task is part of the information architecture. The default
router is local-first/tier-gated; the opt-in
[`full_registry_router`](../../hermes_cli/jarvis_prime/full_registry_router.py)
ranks the **entire** model catalog on the merits (measured scorecard evidence
first, then catalog signals) so MUSE can pick the best model anywhere in the
registry for the task at hand.

## See also

- [MUSE_COMPONENT_REGISTRY.md](MUSE_COMPONENT_REGISTRY.md) — the subsystems named above.
- [MUSE_DATAFLOW.md](MUSE_DATAFLOW.md) — how context flows through cognition + routing.
- [`../jarvis-verification-gates.md`](../jarvis-verification-gates.md) — the gate contract behind "plan first".
