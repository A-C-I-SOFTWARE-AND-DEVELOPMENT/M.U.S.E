# Composable Agent Design Patterns (in MUSE terms)

> **Status:** Guidance doc, 2026-06-04. MUSE already *has* the primitives for
> every effective agent pattern; what it lacked was a single doc naming them and
> mapping them to the building blocks. This closes the "operational
> superstructure" gap identified in
> [`../jarvis_architecture/MYTHOS_RECONSTRUCTION.md`](../jarvis_architecture/MYTHOS_RECONSTRUCTION.md).

Anthropic's [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
makes one core argument: **the most reliable agents are built from simple,
composable patterns, not heavyweight frameworks.** Hermes/MUSE independently
arrived at the same place — the orchestration system is five primitives (Job,
Worker, Model routing, Validation gate, Decision ledger), and the agent loop is
plain tool-calling. This doc names the patterns and points to where each already
lives, so contributors reach for the existing primitive instead of inventing a sixth.

## The five workflow patterns → MUSE primitives

| Pattern | What it is | Where it already lives in MUSE |
|---|---|---|
| **Prompt chaining** | Decompose into fixed sequential steps | The orchestrator's phase decomposition (a phase's output feeds the next); see [`muse-orchestration-pipeline.md`](muse-orchestration-pipeline.md) |
| **Routing** | Classify input, send to a specialized path | [`hermes_cli/model_router.py`](../../hermes_cli/model_router.py) (evidence-first worker routing) + [`hermes_cli/jarvis_prime/task_router.py`](../../hermes_cli/jarvis_prime/task_router.py) (mode/risk classification) |
| **Parallelization** | Run independent subtasks concurrently and aggregate | `_should_parallelize_tool_batch()` in [`run_agent.py`](../../run_agent.py); parallel phases on the kanban board |
| **Orchestrator-workers** | A lead LLM dynamically splits work, delegates, synthesizes | MUSE runtime ([`runtime.py`](../../hermes_cli/jarvis_prime/runtime.py)) over worker profiles ([`worker_registry.py`](../../hermes_cli/jarvis_prime/worker_registry.py)); the `delegate_task` tool |
| **Evaluator-optimizer** | One agent generates, another critiques; loop until good | Builder ≠ reviewer (Claude Code builds, Codex reviews); the contrarian + assurance-risk reviewers; **formalized below** |

## Multi-agent (lead → parallel subagents)

Anthropic's [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
uses a **lead agent** that plans a strategy and spawns **specialized subagents**
that explore in parallel, then synthesizes. MUSE's analogue:

- **Lead** = MUSE runtime / the AOS Council Director.
- **Subagents** = AOS council members + domain specialists
  ([`skills/aos-enterprise-council/`](../../skills/aos-enterprise-council/)) and
  `delegate_task` spawns.
- **Shared memory** = the GraphRAG knowledge graph + Memory Tree, so subagents
  reuse-before-duplicate instead of re-deriving context.
- **Audit** = every spawn/route/gate lands in the [decision ledger](decision-ledger.md).

Today this coordination is **folder-based and async-loose** (the
`.hermes-orchestrator/jobs/<job-id>/` contract); the external worker dispatcher
is mid-build. Prefer extending that contract over inventing a parallel harness.

## The evaluator-optimizer loop, formalized

This is the pattern MUSE most under-uses, and the one the **self-audit harness**
turns into infrastructure. The loop:

```text
generate ──▶ evaluate (against a rubric) ──▶ pass? ──yes──▶ ship
   ▲                                          │
   └──────────────── revise ◀──────no─────────┘
```

- **Generator** — the builder worker (or MUSE itself).
- **Evaluator** — a *separate* grader with an explicit rubric. In MUSE the
  rubric is the [MUSE Constitution](../jarvis-constitution.md); the graders are
  the [`contrarian-reviewer`](../../skills/contrarian-reviewer/SKILL.md) and
  [`assurance-risk-director`](../../skills/assurance-risk-director/SKILL.md) skills.
- **Stop condition** — the relevant [verification gate](../jarvis-verification-gates.md)
  passes on captured evidence (not self-attestation).

The **self-audit harness** (`self_audit/`, see the reconstruction blueprint) is
an evaluator-optimizer applied to MUSE *itself*: an auditor generates risky
scenarios, the judge evaluates the transcript against the Constitution, and the
result gates capability bands. It is Anthropic's [Petri](https://www.anthropic.com/research/petri-open-source-auditing)
auditor→target→judge loop expressed in MUSE's own primitives.

## "Don't add a sixth primitive"

Before building new agent machinery, check whether the need is already one of:
**a Job, a Worker (profile), a Model-routing rule, a Validation gate, or a
Decision-ledger entry.** Most "new agent feature" ideas are a tweak to one of
those — see [`README.md`](README.md) and the orchestration rules in
[`../../AGENTS.md`](../../AGENTS.md#hermes-orchestration). A genuinely new
coordination need (e.g., tighter lead→subagent handoff) extends the job-folder
contract; it does not fork a second orchestrator.

## When to reach for what

| You need to… | Pattern | Reach for |
|---|---|---|
| Run fixed known steps | Prompt chaining | Phase decomposition |
| Send work to the right specialist/model | Routing | `model_router` / `task_router` |
| Fan out independent work | Parallelization | parallel phases / parallel tool batch |
| Split an open-ended goal | Orchestrator-workers | MUSE runtime + `delegate_task` |
| Raise output quality / catch risk | Evaluator-optimizer | builder≠reviewer + Constitution rubric |
| Audit MUSE's own behavior | Evaluator-optimizer (self) | the `self_audit/` harness |

## Cross-references

- [`../jarvis_architecture/MYTHOS_RECONSTRUCTION.md`](../jarvis_architecture/MYTHOS_RECONSTRUCTION.md) — why this doc exists.
- [`../jarvis-constitution.md`](../jarvis-constitution.md) — the evaluator's rubric.
- [`README.md`](README.md) — the five orchestration primitives.
- [`decision-ledger.md`](decision-ledger.md) — the audit trail every pattern writes to.
