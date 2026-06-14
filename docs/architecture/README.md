# M.U.S.E Architecture

The inspectable map of the M.U.S.E system: what the components are, how data
flows between them, the schemas that bound their work, and which external
technologies are adopted vs. declined. These docs implement Phases A–E of the
M.U.S.E Engineering Blueprint.

| If you want to… | Read this |
|---|---|
| See every component, its owner module, risk class, and owner gates | [MUSE_COMPONENT_REGISTRY.md](MUSE_COMPONENT_REGISTRY.md) |
| Read the machine-readable registry (source of truth) | [muse-component-registry.yaml](muse-component-registry.yaml) |
| Follow how data flows (context, goal-to-PR, gates, cognition, remote worker, routing) | [MUSE_DATAFLOW.md](MUSE_DATAFLOW.md) |
| Learn the work-packet + remote-worker schemas, owner-approval examples, failure playbooks | [MUSE_WORKFLOW_SCHEMAS.md](MUSE_WORKFLOW_SCHEMAS.md) |
| See which external technologies are adopted, migrated, or declined | [MUSE_TECHNOLOGY_DISPOSITION.md](MUSE_TECHNOLOGY_DISPOSITION.md) |
| Read architecture decision records | [decisions/](decisions/) |

## New-contributor one-pager

M.U.S.E is a **governed, local-first AI operating partner**: one coordinated
intelligence layer across CLI, gateway messaging, Android, terminal UI, worker
bridges, memory, tools, and model providers. It is **not** unrestricted
autonomy — it plans, proposes, executes bounded work, verifies results, preserves
provenance, and **stops before high-impact owner-gated actions**.

The pieces, in one breath: a **surface** (CLI / TUI / gateway / Android / ACP)
hands a goal to the **Jarvis Prime runtime**, which routes through the **cognition
plane** (Memory Tree, Research Vault, GraphRAG) and the **orchestrator** (Job →
task DAG → workers). Work passes the **eight gates** (Planning, Build, Review,
Test, Security, Release, Owner Approval, Rollback), every decision lands in a
**tamper-evident ledger**, and anything high-impact stops for the owner's exact
`Yes, with authorization.`

The registry, dataflow, and schema docs above are kept honest by
[`tests/hermes_cli/test_component_registry.py`](../../tests/hermes_cli/test_component_registry.py),
which fails if a documented module path, doc link, risk class, or owner-gated
action drifts from the code.

## The single operating rule

> M.U.S.E may plan autonomously, propose edits, and run bounded verification. It
> must preserve provenance, stop before high-impact actions, and leave every
> major decision inspectable, reversible, and attributable.

## See also

- [`../../AGENTS.md`](../../AGENTS.md) — full development guide.
- [`../jarvis-prime-operating-system.md`](../jarvis-prime-operating-system.md) — identity, modes, owner gates.
- [`../jarvis-verification-gates.md`](../jarvis-verification-gates.md) — the eight gates.
- [`../jarvis-constitution.md`](../jarvis-constitution.md) — the behavioral rubric.
- [`../orchestration/README.md`](../orchestration/README.md) — orchestration end to end.
