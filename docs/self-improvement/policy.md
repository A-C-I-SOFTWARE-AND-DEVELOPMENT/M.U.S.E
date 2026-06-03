# Self-Improvement Policy

Hermes/JARVIS may *propose* improvements autonomously, but **never applies them
silently**. This policy governs the autonomy features added alongside TokenJuice
(eval-gated routing, background learner, layered memory) and how they interact
with the existing self-update machinery.

## Core invariant: propose, don't apply

Every change to code, skills, durable memory, routing rules, or runtime config
flows through the existing owner-approval gate:
`hermes_cli/jarvis_prime/self_update.py::ProposalBook` →
`ProposalStatus.NEEDS_OWNER_APPROVAL` → owner reviews → `APPROVED`/`REJECTED` →
only then applied (via the existing Claude Code / Codex PR flow). RC3+ proposals
*always* require owner approval.

## Where proposals originate

| Source | Mechanism | Risk class |
| --- | --- | --- |
| Background learner `propose_code_patch` | `BackgroundLearnerRunner` → `ProposalBook.propose(SELF_RUNTIME_UPDATE)` | RC3 |
| Background learner `propose_skill` | `ProposalBook.propose(NEW_SKILL)` | RC3 |
| Memory promotion (untrusted/trusted) | `memory_layers.curator_bridge` → `ProposalBook.propose(MEMORY_PROMOTION)` | RC2/RC3 |
| Owner-trusted + owner-approved memory | auto-promote (no proposal) | — |

## Hard prohibitions (no approval token issuable this sprint)

The background learner rejects these kinds at enqueue and the runner never
performs them: send message/email/SMS, spend money, install packages, mutate
production code directly, access new accounts, exfiltrate data, create external
schedules, modify secrets, auto-merge self-updates, destructive shell.

## Integrations

Communication integrations (email/SMS/calendar) are capability-typed; any
`send`/`create_event` capability is owner-gated and refused without an explicit
approval. No new outbound credential path is introduced — transports are wired
explicitly by callers (e.g. an existing gateway channel), never implicitly.

## Observability

Raw tool output (`~/.hermes/tool-raw/`) and raw memory events
(`~/.hermes/memory-raw/`) are logged with provenance, gitignored, and never
auto-read into the model context. Compaction/scrub stats are logged under the
`[tokenjuice]` prefix.
