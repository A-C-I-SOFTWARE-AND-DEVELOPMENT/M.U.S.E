# Cockpit canonical contract — server-first enrichment plan

**Decision (owner):** the Android cockpit UI data models are the product
specification. The Python cockpit/JARVIS-Prime server contract is made
**canonical and complete enough to support them with real data** — no
fabricated fields, no gutted UI. Each screen is cut off mocks **only
after** its real, enriched endpoint exists.

## The pattern (proven on Memory)

Every domain follows the same five steps — Memory is the worked example:

1. **Canonical schema** in `gateway/cockpit/contract.py`, mirroring the
   Android model field-for-field (wire keys `snake_case`; enum values =
   Android enum constant names).
2. **Adapter** projecting the JARVIS-Prime subsystem record into that
   schema, deriving fields honestly. Genuinely-absent values are `null`
   or an explicit "unknown" vocabulary member (e.g. memory
   `UNCATEGORIZED`) — never guessed.
3. **Persist real product-need fields at the source** when there is no
   signal to derive them (e.g. `MemoryRecord.category`), additively and
   backward-compatibly.
4. **Endpoint** emits/accepts the canonical schema; honest empty/`422` on
   the failure paths (never fake data).
5. **Tests both sides** to prevent drift (server: adapter + endpoint;
   Android: DTO ↔ contract once the model is aligned).

Then, in a follow-up Android PR: align the Kotlin DTO/domain model to the
canonical schema, wire the repository to `HermesCockpitClient`, and remove
the mock production seed.

## Status

| Domain | UI model | Server source | Server contract | Android cutover |
|---|---|---|---|---|
| Runtime status | `RuntimeStatus` | live queue/host | ✅ live (#185) | ✅ client (#186) |
| Worker detection | `DetectedWorker` | `worker_registry` | ✅ live (#185) | ✅ client (#186) |
| Health/negotiation | `HealthStatus` | gateway | ✅ live (#185) | ✅ client (#186) |
| Chat | `JarvisChatChunk` | real agent | ✅ live (#185) | ✅ routed (#186) |
| **Memory** | `MemoryItem` | `MemoryStore` | ✅ **enriched (#187)** | ⏳ next |
| **Jobs** | `CockpitJob` | `JobQueue` | ✅ **enriched (this PR)** — read+dispatch+cancel | ⏳ next |
| **Audit / ledger** | `AuditRecord`/`ProofRecord` | `decision_ledger` | ✅ **enriched (this PR)** — list + proof | ⏳ next |
| **Approvals** | `ApprovalCard` | `proposals.jsonl` | ✅ **enriched (this PR)** — canonical cards + owner-phrase decide | ⏳ next |
| **Proposals** (self-update) | (native) | `proposals.jsonl` | ✅ **native view (this PR)** — `/v1/cockpit/proposals` | ⏳ |
| Capabilities / skills / tools | `Capability` | catalog | ⏳ | ⏳ |
| Automations | `AutomationIntent` | — | ⏳ | ⏳ |
| Sessions | — | `decision_ledger` dirs | ⏳ partial (#185) | ⏳ |
| Diagnostics | diagnostics screen | `launch_doctor` | ✅ live (#185) | ⏳ |
| Social patterns | `SocialPattern` | — | ⏳ | ⏳ |

Legend: ✅ done · ⏳ pending. "shape differs" = the subsystem stores a
different domain concept than the UI (e.g. ledger entries vs leveled log
lines); reconciliation means enriching/adapting the server, not faking.

## Honest-divergence notes (to resolve per domain)

- **Audit**: resolved (this PR) — the decision ledger's 15 prose sections
  map onto `AuditRecord`/`ProofRecord`. `GET /v1/cockpit/audit` and
  `GET /v1/cockpit/audit/{id}/proof` are live. Enums are derived honestly
  (risk from `open_risks` presence; approval from the yes/no/defer verb;
  result from the final-decision text; route from the worker). Fields the
  ledger genuinely lacks (files changed, per-step durations, enumerated
  tests) are emitted empty/0 — never fabricated.
- **Events**: server `audit_events` returns decision-**ledger** summaries;
  UI `CockpitEvent` wants leveled (`info|warn|error`) log lines with
  `job_id`/`attributes`. Still needs a real structured event source (a
  separate concern from the audit ledger); deferred.
- **Approvals**: resolved (this PR) — the Android Approvals screen is one
  `ApprovalCard` queue; the server's one real owner-gated queue is the
  self-update proposal store. `/v1/cockpit/approvals` projects proposals
  into canonical cards (risk class → tier; owner-phrase decide preserved);
  `/v1/cockpit/proposals` keeps the self-update-native shape. Future
  destructive-command approvals join the same card queue — no second store
  fabricated.
- **Memory**: resolved (#187) — `category` persisted; 3 store tiers map to a
  subset of the 5 UI durability levels (honest, lossless on read).
- **Jobs**: resolved (this PR) — the canonical `status` is a **superset** of
  the queue's execution states and the UI's publish-workflow states, so both
  are expressible with real data. Execution states come from `JobQueue`;
  workflow states from a pipeline-set `metadata.workflow_status`. Git/publish
  fields are surfaced from `metadata` or `null` (never fabricated). The
  Android `JobStatus` enum gains `PAUSED`/`BLOCKED`/`DISCONNECTED`/`COMPLETED`
  on alignment. Job **files/diff/validation/publish** sub-resources and the
  SSE stream remain pending.
