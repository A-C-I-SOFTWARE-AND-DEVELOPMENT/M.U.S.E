# AOS Memory & Context Recovery

> Memory backends, namespaces, artifact-persistence rules, context-engine modules.

## Hermes memory subsystem (Python)

| Module | Path | Role |
| --- | --- | --- |
| `agent.memory_manager` | `agent/memory_manager.py` | Memory backend manager |
| `agent.memory_provider` | `agent/memory_provider.py` | Memory backend provider interface |
| `agent.context_engine` | `agent/context_engine.py` | Context management engine |
| `agent.context_compressor` | `agent/context_compressor.py` | Context compression / optimization |
| `agent.context_references` | `agent/context_references.py` | Context reference tracking |
| `agent.conversation_compression` | `agent/conversation_compression.py` | Conversation history compression |
| `agent.conversation_loop` | `agent/conversation_loop.py` | Conversation state + memory integration |
| `agent.prompt_caching` | `agent/prompt_caching.py` | Prompt caching for context reuse |

## Enterprise audit / memory runtime

| Module | Path | Role |
| --- | --- | --- |
| `enterprise.audit` | `enterprise/audit.py` | Council audit-trail runtime |
| `enterprise.secrets` | `enterprise/secrets.py` | `fetch_secret(...)` contract: secure-by-construction credential retrieval |

## AOS memory namespace conventions

From `skills/aos-council-director/SKILL.md` and `skills/aos-full-agent-team/SKILL.md`:

```
aos/council/<goal-slug>/
  brief                    # mission brief
  evidence                 # evidence bundle
  routing-decision         # executive operator routing
  builder-diff             # engineering builder output
  assurance-review         # security/compliance review
  ux-review                # psychology / UX review
  commercial-draft         # product-strategy draft + claim ledger
  codex-dispatch           # codex packet + envelope + verification log
  knowledge-ops            # doc-freshness, contradictions, retrospective
  hazmat-change            # hazmat-specialist citation chain
  nourish-change           # nourish-specialist citations
  release-judgment         # qa/release verdict
  quality_gate             # final pass/conditional/fail
  decision                 # decision-of-record
  retrospective            # post-run retro
  owner-handoff            # final owner-facing summary
```

## Hazmat artifact persistence rule

From `recovered-agent-sources/from-hazmat-command/HAZMAT-AGENTS.md` § "Artifact persistence rule":

> Chat memory is not enough. Every RC2/RC3 run produces durable artifacts (research dossier,
> PRD, ADR, threat model, compliance evidence matrix, pricing brief, legal draft, pilot
> readiness report, agent run retrospective). Artifacts land under `docs/aos/runs/YYYY-MM-DD-<slug>/`.

Recovered hazmat-canonical artifact registry policy: `recovered-agent-sources/from-hazmat-command/docs/governance/08-artifact-registry-and-memory-discipline.md`.

## Source-of-truth hierarchy (for resolving contradictions)

From `recovered-agent-sources/from-hazmat-command/HAZMAT-AGENTS.md` § "Source-of-truth hierarchy":

```
1. Live code + tests (git grep, npm test outcomes)
2. AGENTS.md (constitutional)
3. PUBLISH.md (release-governance)
4. SKIPPED.md (stub inventory)
5. CI gate verdicts
6. docs/inventory/blockers-final.md
7. docs/releases/v1.0.0-enterprise-ready.md
8. docs/iso27001/, docs/security/, docs/runbooks/, docs/compliance/
9. docs/AUTONOMOUS_ORGANIZATION_INDEX.md + docs/governance/**
10. HANDOFF.md, AUDIT.md, SMOKE_TEST.md, CLOUD_SYNC.md, PLAY_STORE.md (historical)
11. marketing/** (owner-facing operational notes)
12. Older planning docs (historical only)
```
