# MUSE evidence & research (RAG) guide

When MUSE researches something, it answers from a **cited evidence
store**, not from thin air. This guide explains the Research Vault, how
evidence connects to memory with provenance, and the hard rules that keep
research honest. It applies everywhere MUSE runs — including from the
[mobile cockpit](../mobile/JARVIS_MOBILE_NATIVE_USER_GUIDE.md#8-evidence--research).

---

## The Research Vault

Source: `hermes_cli/jarvis_prime/research_vault.py`. It is a first-class,
local, source-cited evidence store holding papers, official docs, OSS
practices, model-benchmark notes, courses, and skill proposals as
`ResearchArtifact`s.

Design properties (all enforced in code):

- **Summarizes only from stored citation text or user-provided excerpts.**
  It never fabricates a summary.
- **No network calls of its own**, and it never downloads copyrighted or
  private material.
- **Clean-room, stdlib-only**, with local JSONL persistence and atomic
  writes — your evidence stays on your machine.

## Provenance → Memory Tree

Each artifact connects to the **Memory Tree** through source pointers:
`ResearchArtifact.as_memory_source()` yields a `MemorySource` with a
`SourceTrust` level. That means anything MUSE "knows" from research can
be traced back to the artifact and excerpt it came from. The Memory Tree's
provenance, contradiction-handling, and sensitivity rules are specified in
[`../jarvis_architecture/JARVIS_MEMORY_TREE_AND_NATURAL_LANGUAGE_CODER_SPEC.md`](../jarvis_architecture/JARVIS_MEMORY_TREE_AND_NATURAL_LANGUAGE_CODER_SPEC.md)
and the vault overview in
[`../jarvis_architecture/JARVIS_RESEARCH_VAULT.md`](../jarvis_architecture/JARVIS_RESEARCH_VAULT.md).

## How a research answer is built

```
your excerpt / cited source ─▶ ResearchArtifact (stored, hashed, dated)
                                      │ as_memory_source()
                                      ▼
                               Memory Tree source pointer (SourceTrust)
                                      │
                                      ▼
MUSE answer ── cites the artifact, never invents one
```

If there is no stored evidence for a claim, MUSE says so rather than
guessing. Contested or contradictory entries are flagged, not silently
overwritten (see the memory-audit skill
[`/jarvis-memory-audit`](../../skills/)).

## Using it

- **On the phone:** ask a research question in chat; the answer is grounded
  in the vault. Add your own excerpts to strengthen an answer.
- **On the backend:** the research lane (`hermes_cli/jarvis_prime/research.py`)
  and the current dossier
  [`../jarvis_research/JARVIS_CURRENT_RESEARCH_DOSSIER.md`](../jarvis_research/JARVIS_CURRENT_RESEARCH_DOSSIER.md)
  show what's already gathered.
- **Deeper, multi-source web research** is a separate, explicit harness —
  the [`/deep-research`](../../skills/) skill — which fans out searches,
  fetches sources, and adversarially verifies claims before synthesizing a
  cited report. The Vault is where durable, reusable evidence lands.

## The honesty rules (do not weaken)

1. No fabricated sources or summaries — citation text or excerpt only.
2. No self-initiated network fetches from the Vault.
3. No copyrighted / private downloads.
4. Provenance is preserved; trust level travels with every fact.
5. Contradictions are surfaced, never silently resolved.
