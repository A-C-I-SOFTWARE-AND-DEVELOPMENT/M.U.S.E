# muse — System Overview

muse is Jeremiah Echerd's local-first, owner-authorized,
memory-backed, model-routed AI operating partner running **inside
Hermes**. Hermes is the canonical backend. muse plans, researches,
codes, reviews, remembers, monitors, and briefs — while preserving
provenance, owner authority, reversibility, and verification.

> This document describes what muse **is**, what it **can** do today,
> what it **cannot yet** do, and how to run it. It does not overclaim.
> muse is **not** "fully autonomous" or "unrestricted." It is loyal to
> the owner's long-term mission and defers owner-gated actions.

## Three planes

muse is organized into three planes (see `hermes_cli/jarvis_prime/`):

### 1. Control plane — Hermes / muse
Owner gates, emergency stop, mode classification, routing, model
selection, work-packet creation, verification gates, self-update
proposals, approval inbox data, audit ledger, and the daily owner brief.

- `runtime.py`, `modes.py`, `router.py`, `gates.py`, `owner_auth.py`
- `natural_language_coder.py` — plain-English → bounded work packet
- `self_update.py` + `proposal_executor.py` — proposals → bounded plans
- `monitors.py` + `owner_brief.py` — fail-visible monitors + daily brief

### 2. Cognition plane — muse Memory OS
Working / session / durable memory, the **Memory Tree**, Research Vault,
contradiction handling, freshness, source trust, retrieval, and context
packing (TokenJuice).

- `memory.py` (existing `MemoryStore`) — unchanged
- `memory_tree.py` — production `MemoryTreeStore` (provenance,
  contradictions, supersession, context packs, JSONL persistence)
- `research_vault.py` — source-cited evidence store
- `tokenjuice.py` — deterministic, token-bounded context compiler
- `model_scorecard.py` — evidence-backed model routing records

### 3. Execution plane — bounded workers
Workers execute **bounded** work only: Claude Code builder, an
independent Codex/frontier reviewer, local tests, the GitHub PR publisher
**after approval**, research fetchers, and the Termux/Android action
broker **after permission and final confirmation**. muse never executes
owner-gated actions itself.

## What muse can do today

- Turn a plain-English request into a bounded, gate-compatible work packet
  with risk class, owner gates, allowed/forbidden files, verification, and
  rollback (`packetize` / `packet`).
- Store provenance-first durable memory that never silently overwrites,
  raises contradictions, and excludes contested facts from context packs.
- Hold source-cited research artifacts and bridge them into memory.
- Compile a deterministic, token-bounded context pack (TokenJuice).
- Record per-(model, task) scorecards and recommend models from evidence.
- Convert an **approved** self-update proposal into a bounded execution
  plan (branch, tests, rollback) — without merging/deploying/publishing.
- Run read-only monitors and produce a daily owner brief with a coverage
  attestation that surfaces blind spots.

## What muse cannot yet do (honest gaps)

- It does **not** execute real Android accessibility gestures, external
  posts/messages, purchases, merges, deploys, credential changes, or
  releases. Those remain owner-gated and, on Android, also gated by system
  permissions. See the Android completion packet.
- Local OSS models are **wired** (config + local-endpoint packets) but not
  confirmed running unless a smoke request succeeds.
- The monitors consume a supplied context; live collectors (git, GitHub,
  pytest) are an integration step, documented as remaining.

## How to run it

```bash
python -m hermes_cli.jarvis_prime --help
python -m hermes_cli.jarvis_prime handle "audit hermes repo for jarvis readiness" --skip-perceive --json
python -m hermes_cli.jarvis_prime packetize "add memory tree support" --json
python -m hermes_cli.jarvis_prime packetize "click Facebook when I ask" --gate-check
python -m hermes_cli.jarvis_prime memory-tree add "jarvis/architecture::backend::Hermes is the backend" --store ~/.hermes/jarvis_prime/memory_tree.jsonl --layer durable --source docs/jarvis-prime-operating-system.md --trust primary --confidence 0.9
python -m hermes_cli.jarvis_prime owner-brief --json
```

## Cross-references
- `docs/jarvis-prime-operating-system.md` — identity, modes, hierarchy
- `docs/jarvis-verification-gates.md` — the eight gates
- `JARVIS_OWNER_GATES_AND_PERSONAL_AUTHORITY.md`
- `JARVIS_MEMORY_TREE_AND_NATURAL_LANGUAGE_CODER_SPEC.md`
- `JARVIS_PERSONAL_USE_COMPLETION_STATUS.md`
