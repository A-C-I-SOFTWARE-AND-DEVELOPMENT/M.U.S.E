# M.U.S.E Dataflow

How the components in the [component registry](MUSE_COMPONENT_REGISTRY.md) pass
data — from a surface, through the Jarvis Prime runtime and the cognition plane,
out to workers and tools, and back. Module names below match real code in the
repository.

## 1. Context — surfaces into the brain

```mermaid
flowchart LR
  CLI["CLI / REPL: muse<br/>(hermes_cli/main.py)"] --> Hermes[Hermes command center]
  TUI["Terminal UI<br/>(tui_gateway/)"] --> Hermes
  Gateway["Gateway DMs<br/>(gateway/run.py)"] --> Hermes
  Android["Android cockpit<br/>(apps/android/)"] --> Hermes
  ACP["ACP adapter<br/>(acp_adapter/)"] --> Hermes
  Hermes --> JP["Jarvis Prime runtime<br/>(hermes_cli/jarvis_prime/__main__.py)"]
  JP --> Cog[Cognition plane]
  JP --> Orch["Orchestrator<br/>(hermes_cli/orchestrator_api.py)"]
  Cog --> Memory["Memory Tree + Research Vault<br/>(research_vault.py)"]
  Cog --> Graph["GraphRAG<br/>(jarvis_prime/graphrag/)"]
  Orch --> Workers["Workers<br/>(model_registry.py, remote_bridge.py)"]
  Workers --> Tools["Tools / providers<br/>(toolsets.py, providers/)"]
  Tools --> External[Local models, APIs, GitHub, terminals]
  External --> Cog
```

The **surface** changes how the prompt gets in and the answer comes back; the
**backend** is the same brain regardless of surface.

## 2. Goal-to-PR workflow

```mermaid
flowchart LR
  Goal[Owner goal] --> Packet["Work packet<br/>(work_packet.py)"]
  Packet --> Planning[Planning gate]
  Planning --> DAG[Task DAG]
  DAG --> Worker[Builder / Reviewer / Specialist]
  Worker --> Review[Review gate]
  Review --> Test[Test gate]
  Test --> Security[Security gate]
  Security --> Ledger["Decision ledger<br/>(decision_ledger.py)"]
  Ledger --> Owner{Owner approval required?}
  Owner -- Yes --> Approval["Nonce-bound owner grant<br/>(owner_auth.py)"]
  Owner -- No --> Publish[PR / file / gateway response]
  Approval --> Publish
  Review -- Blocking issue --> Worker
  Test -- Failure --> Worker
  Security -- Risk found --> Worker
```

## 3. The eight-gate control chain

```mermaid
flowchart LR
  A[Planning] --> B[Build]
  B --> C[Review]
  C --> D[Test]
  D --> E[Security]
  E --> F[Release]
  F --> G[Owner Approval]
  G --> H[Rollback]
```

The gates are implemented in
[`hermes_cli/jarvis_prime/gates.py`](../../hermes_cli/jarvis_prime/gates.py) and
specified in [`../jarvis-verification-gates.md`](../jarvis-verification-gates.md).
In strict evidence mode each observation gate must produce a captured artifact
(git diff, review, test result, secret scan, owner grant, rollback) rather than a
self-attested packet field.

## 4. Cognition + GraphRAG

```mermaid
flowchart LR
  Events[Session events: chat, tools, code, docs] --> Normalize[Source normalizer]
  Normalize --> Memory[Memory Tree]
  Normalize --> Vault[Research Vault]
  Memory --> Graph[GraphRAG index]
  Vault --> Graph
  Graph --> TokenJuice[TokenJuice context pack]
  TokenJuice --> Router["Model router<br/>(providers/)"]
  Router --> Agents[Jarvis / workers]
  Agents --> Events
```

Memory stays **provenance-bound**: it preserves sourced claims, confidence,
sensitivity, contradiction reports, and supersession status, but is never the
sole source of truth. GraphRAG *supplements* RAG/memory; it does not replace it
(see [`../jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md`](../jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md)).

## 5. Remote worker bridge

```mermaid
flowchart LR
  Muse["M.U.S.E bridge<br/>(remote_bridge.py)"] --> Job[Job folder / manifest]
  Job --> Poller[Worker daemon]
  Poller --> Checks[Schema + allowlist + approval + device id + repo root]
  Checks --> Exec[Run allowlisted command]
  Exec --> Artifacts[output.md + patch.diff + changed-files.txt + validation-output.txt]
  Artifacts --> Status[status.json]
  Status --> Collect[M.U.S.E collect + audit]
```

The remote worker only executes allowlisted commands, only inside configured repo
roots, only after approval, while writing structured artifacts back to the shared
workspace. Phase state machine: `todo → ready → in_progress → validating → done`.
See [MUSE_WORKFLOW_SCHEMAS.md](MUSE_WORKFLOW_SCHEMAS.md) and
[`../remote/windows-claude-code-bridge-guide.md`](../remote/windows-claude-code-bridge-guide.md).

## 6. Model routing

```mermaid
flowchart LR
  Task[Task class] --> Registry["Worker registry<br/>(model_registry.py)"]
  Registry --> Route{Route by capability + cost + latency}
  Route --> Anthropic[Anthropic]
  Route --> OpenAI[OpenAI]
  Route --> Gemini["Google Gemini<br/>(plugins/model-providers/gemini/)"]
  Route --> OpenRouter[OpenRouter / NovitaAI / NIM]
  Route --> Local[Local llama.cpp]
  Anthropic --> Decision[Decision ledger entry]
  Gemini --> Decision
  Local --> Decision
```

Providers self-register lazily through
[`providers/__init__.py`](../../providers/__init__.py); routing decisions land in
the decision ledger so every model choice is auditable. See the
[technology disposition](MUSE_TECHNOLOGY_DISPOSITION.md) for which backends are
adopted vs. evaluated-and-declined.
