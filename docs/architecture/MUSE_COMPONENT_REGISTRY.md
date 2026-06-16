# M.U.S.E Component Registry

> **Source of truth:** the machine-readable
> [`muse-component-registry.yaml`](muse-component-registry.yaml). This page is
> its human-readable companion. The two are kept in sync by
> [`tests/hermes_cli/test_component_registry.py`](../../tests/hermes_cli/test_component_registry.py),
> which fails CI if any `owner_module` path, doc link, risk class, or
> owner-gated action drifts from the code.

This registry makes the running system **inspectable**: every major component
has a stable id, the module that owns it, what it can do, its blast radius if
changed (risk class), the owner-gated actions it can reach, how to verify it,
and how to roll a change back. It implements the `muse.component_registry.v1`
schema from the M.U.S.E Engineering Blueprint (§10).

## How to use it

```python
from hermes_cli.jarvis_prime.component_registry import (
    load_registry, by_kind, by_risk, owner_gated_components, get,
)

reg = load_registry()                      # all components, sorted by id
gates = get("verification_gates")          # one component
governance = by_kind("governance")         # safety spine
high_blast = by_risk("RC4")                # change these with the most care
gated = owner_gated_components()           # everything that can hit an owner gate
```

The loader validates on read: a wrong schema header, a duplicate id, an invalid
risk class, or an `owner_gated_actions` entry that is **not** a member of the
canonical `owner_auth.OWNER_GATED_ACTIONS` frozenset all raise loudly. The
registry therefore *references* the single source of truth for owner gates
(Constitution C9) and can never quietly grow a second copy.

### From the CLI

The same registry is browsable read-only from the `jarvis_prime` CLI:

```bash
# list every component (add --json for machine output)
python -m hermes_cli.jarvis_prime architecture list

# filter by kind, risk class, or owner-gated reach
python -m hermes_cli.jarvis_prime architecture list --kind governance
python -m hermes_cli.jarvis_prime architecture list --owner-gated --risk RC4

# show one component's full record
python -m hermes_cli.jarvis_prime architecture show owner_authorization
```

## The components

### Surfaces — where you talk to M.U.S.E

| id | Owner module | Risk | Owner gates |
|---|---|---|---|
| `cli` | `hermes_cli/main.py` | RC2 | — |
| `gateway` | `gateway/run.py` | RC2 | `post_publicly` |
| `tui` | `tui_gateway/entry.py` | RC1 | — |
| `acp_adapter` | `acp_adapter/entry.py` | RC1 | — |
| `android_cockpit` | `apps/android` | RC2 | `post_publicly`, `app_store_submission` |
| `desktop_cockpit` | `apps/desktop` | RC2 | `post_publicly`, `app_store_submission` |
| `voice` | `hermes_cli/voice.py` | RC2 | `post_publicly`, `spend_money`, `production_deploy` |

### Core runtime

| id | Owner module | Risk | Owner gates |
|---|---|---|---|
| `agent_loop` | `run_agent.py` | RC3 | — |
| `jarvis_prime_runtime` | `hermes_cli/jarvis_prime/__main__.py` | RC3 | `grant_autonomy_charter` |
| `plugin_system` | `hermes_cli/plugins.py` | RC2 | — |

### Governance — the safety spine

| id | Owner module | Risk | Owner gates |
|---|---|---|---|
| `verification_gates` | `hermes_cli/jarvis_prime/gates.py` | RC4 | — |
| `owner_authorization` | `hermes_cli/jarvis_prime/owner_auth.py` | RC4 | `grant_autonomy_charter` |
| `work_packet` | `hermes_cli/jarvis_prime/work_packet.py` | RC2 | — |
| `muse_system_contract` | `hermes_cli/jarvis_prime/system_contract.py` | RC2 | — |
| `decision_ledger` | `hermes_cli/decision_ledger.py` | RC3 | — |
| `federation` | `hermes_cli/jarvis_prime/federation` | RC3 | `grant_autonomy_charter`, `registry_mutation` |
| `emergency_stop_monitors` | `hermes_cli/jarvis_prime/monitors.py` | RC4 | — |

### Orchestration + workers

| id | Owner module | Risk | Owner gates |
|---|---|---|---|
| `orchestrator` | `hermes_cli/orchestrator_api.py` | RC3 | `production_deploy` |
| `worker_registry` | `hermes_cli/model_registry.py` | RC3 | `change_default_active_agents`, `registry_mutation` |
| `remote_worker_bridge` | `hermes_cli/remote_bridge.py` | RC3 | — |
| `cron_scheduler` | `cron/scheduler.py` | RC2 | `post_publicly`, `spend_money`, `production_deploy` |

### Cognition plane

| id | Owner module | Risk | Owner gates |
|---|---|---|---|
| `cognition_memory` | `hermes_cli/jarvis_prime/research_vault.py` | RC2 | — |
| `graphrag` | `hermes_cli/jarvis_prime/graphrag` | RC1 | — |
| `research_fabric` | `hermes_cli/jarvis_prime/research_fabric` | RC4 | `grant_autonomy_charter`, `registry_mutation`, `production_deploy` |

### Integrations + providers

| id | Owner module | Risk | Owner gates |
|---|---|---|---|
| `model_router` | `providers/__init__.py` | RC2 | `oauth_change`, `credential_change` |
| `visual_synthesis` | `plugins/image_gen` | RC1 | `spend_money` |
| `web3_skills` | `optional-skills/blockchain` | RC2 | — |
| `learning_pipeline` | `plugins/learning` | RC1 | — |
| `memory_backends` | `plugins/memory` | RC1 | `credential_change`, `modify_secrets` |

## Risk classes

Risk class describes the blast radius of **changing** a component, on the same
`RC0…RC4` scale used by [work packets](MUSE_WORKFLOW_SCHEMAS.md):

- **RC4** — the safety spine (`verification_gates`, `owner_authorization`). Touch
  with maximal care; changes here are owner-gated and need strict evidence.
- **RC3** — runtime, orchestration, remote execution, and the ledger.
- **RC2** — surfaces, plugin loading, memory, providers.
- **RC1** — supplemental/opt-in (GraphRAG, visual synthesis, TUI, ACP).

## Owner-gated actions

The `owner_gated_actions` column lists the high-impact actions each component can
*reach*. None of them execute without the owner replying with the exact phrase
`Yes, with authorization.` (and, in strict evidence mode, a nonce-bound
challenge). The canonical set lives in
[`hermes_cli/jarvis_prime/owner_auth.py`](../../hermes_cli/jarvis_prime/owner_auth.py);
see [MUSE_WORKFLOW_SCHEMAS.md](MUSE_WORKFLOW_SCHEMAS.md) for worked examples.

## See also

- [MUSE_DATAFLOW.md](MUSE_DATAFLOW.md) — how these components pass data.
- [MUSE_WORKFLOW_SCHEMAS.md](MUSE_WORKFLOW_SCHEMAS.md) — work packet + remote
  worker schemas, owner-approval examples, failure-mode playbooks.
- [`../jarvis-verification-gates.md`](../jarvis-verification-gates.md) — the eight gates.
- [`../jarvis-constitution.md`](../jarvis-constitution.md) — the behavioral rubric.
- [`../../AGENTS.md`](../../AGENTS.md) — full development guide.
