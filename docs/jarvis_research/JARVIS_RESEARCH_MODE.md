# muse Research Mode (the Evidence Engine)

Status: **shipped**. File: `hermes_cli/jarvis_prime/research_engine.py`.
Tests: `tests/test_jarvis_prime_research_engine.py`,
`tests/gateway/test_cockpit_research.py`.

Research Mode lets muse research facts, papers, docs, releases, repo
issues, and technical decisions — from the desktop CLI **or** the Android
cockpit — with Perplexity-style citations and stronger verification. It is a
thin orchestrator that *composes* primitives that already exist; it does not
add a second evidence store, memory store, or web client.

## Pipeline (eight steps)

`ResearchEngine.run(query, manual_sources=None)` runs:

1. **Decompose** — `decompose()` builds a `ResearchBrief`
   (`hermes_cli/jarvis_prime/research.py`) whose questions are the
   sub-questions.
2. **Gather** — `gather()` resolves the active web-search provider via
   `agent.web_search_registry.get_active_search_provider()` and merges any
   user-pasted `manual_sources`. **If no provider is configured and no manual
   sources are given, it returns an honest "no sources" result — it never
   fabricates.** The gatherer is injectable so tests run network-free.
3. **Rank** — `rank()` orders sources by trust tier (deterministic domain
   heuristics → `EvidenceStrength`) then query relevance.
4. **Evidence cards** — `to_cards()` stores each ranked source in the existing
   `ResearchVault` (excerpt-only summaries, atomic JSONL) and wraps it as an
   `EvidenceCard`.
5. **Synthesize** — `synthesize()` derives one claim per card, with confidence
   from the card's trust tier. No cross-source invention — every claim traces
   to exactly one cited source.
6. **Verify citations** — `verify_citations()` drops any claim whose cited
   card excerpt does not support it (no orphan / hallucinated citations).
7. **Contradictions** — `find_contradictions()` flags pairs of cards that
   share a subject but oppose each other. Reported, never auto-resolved.
8. **Final answer** — `compose_answer()` assembles the cited answer and runs
   `epistemics.audit_response()` to attach calibrated `uncertainty`.

Reports persist to `${HERMES_HOME:-~/.hermes}/jarvis_prime/research_reports.jsonl`
(atomic write, `0o600`), alongside the Research Vault.

## Promotion and tasks (gated, no new write paths)

- **Promote to Memory Tree** — `promotion_payload()` prepares a
  `MemoryStore.remember` payload (trust → confidence, source provenance,
  citation). The cockpit handler performs the gated write, so a promoted
  finding flows through the **same policy the Memory screen reads** and a
  secret-like / low-confidence card is honestly rejected.
- **Create coding task** — `task_prompt()` builds a prompt from the answer +
  citations; the cockpit handler enqueues it via the existing `JobQueue` (a
  queued entry only — owner/run gates unchanged).

## Surfaces

- **Backend / CLI**: `ResearchEngine` is importable anywhere in the Hermes
  process.
- **Cockpit API**: `POST/GET /v1/cockpit/research`, `GET /research/{id}`,
  `POST /research/{id}/promote`, `POST /research/{id}/task` — see
  [`docs/android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md)
  §10d.
- **Android**: the Research screen
  (`apps/android/.../ui/screens/research/ResearchScreen.kt`), a full-screen
  push reached from the Home quick links. Unpaired apps show an honest
  "pair a gateway" hint — never fabricated findings.

## Related

- [`muse Research Vault`](../jarvis_architecture/JARVIS_RESEARCH_VAULT.md) —
  the evidence store this engine writes into.
