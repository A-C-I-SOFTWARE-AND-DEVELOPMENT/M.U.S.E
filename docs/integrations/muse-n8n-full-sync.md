# MUSE ↔ n8n — Full Sync (global end-to-end)

> Status: additive integration package. Nothing in here changes default runtime
> behavior until you deliberately wire the dispatcher in (see §12). Both live
> services were **down** when this was authored, so it is built to run the moment
> you bring them up — no round-trip was performed against your machine.

This document maps **every step a MUSE turn takes** — from the chat AI agent, through
the Atlas, through the AXIOM gate, out to the n8n connector layer, and back — and
specifies the exact contract at each hop. It leaves nothing implicit.

Companion files:

- `integrations/n8n/README.md` — operator quickstart (bring-up + smoke tests).
- `integrations/n8n/workflows/*.json` — importable n8n workflows.
- `integrations/n8n/muse_delegate_dispatcher.py` — host-side wiring.
- `integrations/n8n/diagrams/muse-n8n-global-flow.svg` / `.mmd` — the master flow diagram.

---

## 1. The one-paragraph model

A chat message enters at the Atlas **Neural Conversation** (`/chat`, Crown deck) and
runs a single streamed turn — `POST /v1/jarvis/chat` on the cockpit (`:8765`) — which
executes **perceive → recollect → classify → build_prompt → decide → gate (AXIOM) →
speak** inside `hermes_cli/jarvis_prime/runtime.py::JarvisPrime.handle()`. n8n is the
**execution + connector layer** on both sides of that turn: **outbound**, the *delegate*
stage hands an AXIOM-approved action to an n8n connector (email, Slack, 400+ apps);
**inbound**, an n8n webhook exposes MUSE itself as a callable node for Zapier / Make /
external systems. The verifier never moves: **intelligence proposes; the verifier
disposes** — the AXIOM gate stays in MUSE, n8n only executes what the gate already blessed.

---

## 2. The two directions (and the MCP angle)

| Direction | Trigger | Path | Built by |
|---|---|---|---|
| **Outbound** — MUSE → n8n (delegate) | AXIOM gate passes on an action | `JarvisPrime.delegate()` envelope → `N8nBridge.trigger_workflow()` → `POST {n8n}/webhook/muse-connector-*` | `muse_delegate_dispatcher.py` + `muse-delegate-connectors.json` |
| **Inbound** — n8n → MUSE (callable node) | external system hits a webhook | `POST {n8n}/webhook/muse-run` → `POST {cockpit}/v1/jarvis/chat` → answer | `muse-inbound-node.json` |
| **Master mirror** — the whole turn in n8n | chat message | `POST {n8n}/webhook/muse-global-chat` → full staged pipeline | `muse-global-pipeline.json` |
| **MCP angle** (read-mostly) | Hermes session | the `official/n8n` MCP bridge (`optional-mcps/n8n/manifest.yaml`) — list/get/export workflows, executions, failures | already catalogued; install with `muse mcp install official/n8n` |

Stage 1 (recovered prototype) built only the **echo** round-trip. This package builds the
rest: the full delegate hop with the correct ledger adapter, the inbound node, and the
master mirror.

---

## 3. Stage-by-stage contract (leave-nothing-out table)

Every stage, its live contract, and where it lives in code. `{cockpit}` =
`http://host.docker.internal:8765` from inside the n8n container (see §8).

| # | Stage | Live contract | Source of truth |
|---|---|---|---|
| 1 | **Chat AI agent** (entry) | `POST {n8n}/webhook/muse-global-chat` `{prompt, history?, authorization?}` | Atlas `/chat` route (`apps/desktop/ui/src/omni/universe/catalog.ts`) |
| 2 | **RECEIVING** | normalize prompt + `idempotency_key` (`Idempotency-Key` header or generated) | wire vocab `phase:RECEIVING` (`gateway/jarvis_local_http.py`) |
| 3 | **TURN** (perceive→classify→decide→gate→speak) | `POST {cockpit}/v1/jarvis/chat` `{prompt, history}` → NDJSON stream | `gateway/cockpit/agent.py::jarvis_responder` → `runtime.py::JarvisPrime.handle` |
| 4 | **Parse** | fold NDJSON chunks: `phase, body, body_delta, detail, approval, evidence, ledger, done, error` | `gateway/jarvis_local_http.py` (chunk builders) |
| 5 | **Atlas read-back** | `GET {cockpit}/v1/cockpit/{axiom,ledger,memory/tree,evidence,autonomy,approvals}` (Bearer) | `gateway/cockpit/handlers.py` |
| 6 | **GATE** (8) | authoritative signal = `GET {cockpit}/v1/cockpit/axiom` → `audit.chain_valid`, `tip` | `hermes_cli/jarvis_prime/gates.py`, `axiom_bridge.py` |
| 7 | **Owner gate** | hold unless payload carries `authorization == "Yes, with authorization."` | `hermes_cli/jarvis_prime/owner_auth.py` |
| 8 | **DELEGATE** | `POST {n8n}/webhook/muse-connector-<name>` `{idempotency_key, verified_by, payload}` + `Idempotency-Key` header | `runtime.py::JarvisPrime.delegate` + `muse_n8n_bridge.py` |
| 9 | **LEDGER** (host-side) | `GuardrailLedger.append(kind, subject, payload)` → `$HERMES_HOME/jarvis_prime/guardrail_ledger.jsonl` (0600, O_APPEND) | `hermes_cli/jarvis_prime/guardrail_evidence.py` |
| 10 | **SPEAK** | final envelope streamed back to `/chat` (`phase:FINAL`, `body`, `done`) | `agent.py::jarvis_responder` |

Cockpit auth: every route except `/v1/health` needs `Authorization: Bearer <token>`
(`gateway/cockpit/auth.py::load_or_create_token`; printed by `muse cockpit serve` / `muse omni`).

---

## 4. Atlas mapping (deck / station → stage)

The Atlas is the surface; the pipeline is what runs under it. Mapping is exact
(`apps/desktop/ui/src/omni/universe/catalog.ts`).

| Atlas station | Route | Pipeline role |
|---|---|---|
| Neural Conversation (Crown) | `/chat`, `/` | entry (stage 1) + speak (stage 10) |
| Atlas Crown (Crown) | `/atlas` | home landmark / deck navigator |
| Quarantine Moon (Crown) | `/axiom` | GATE review + HOLD surface (stages 6–7) |
| Steering Core (Crown) | `/steer` | autonomy read (stage 5) |
| Deep Observatory | `/observatory` | evidence retrieve→rank→cite→verify (stage 5) |
| Memory Archive | `/second-brain` | recollect / memory tree (stage 5) |
| Neural Shipyard / Agent Fleet (Flight) | `/shipyard`, `/fleet` | `delegate_to` workers (stage 8) |
| Release Dock (Foundry) | `/release` | release gate + rollback (gate 6, owner gate) |
| Signal Broadcast (Embassy) | `/share` | `post_publicly` — owner-gated (stage 7) |

---

## 5. The 8 verification gates (and their packet contracts)

`hermes_cli/jarvis_prime/gates.py`, `GATES` tuple. Risk → profile from `GATE_PROFILES`
(`axiom_bridge.py`): **LOW** → build, test · **MED** → planning, build, review, test,
security, rollback · **HIGH** → all 8 (adds release + owner_approval).

| Gate | Passes when (packet contract) |
|---|---|
| planning | `repo_root, branch, mission, allowed_files, non_goals, acceptance_criteria` present |
| build | `files_changed ⊆ allowed_files`; no protected files; no concurrent editors; no secrets added |
| review | `diff_reviewed`, no blocking findings, `contrarian_objection` present; reviewer ≠ builder (Clause C19) |
| test | `tests_run` non-empty (or `tests_skipped_reason`), no `tests_failed`, `git_diff_check_passed` |
| security | no secrets; `.env`/credential edits need `env_edit_approved`; risky actions → NEEDS_OWNER_APPROVAL |
| release | `files_changed, commits_scoped, verification_summary, non_goals, remaining_risks, rollback_plan` + **AXIOM chain valid** |
| owner_approval | action ∈ `OWNER_GATED_ACTIONS` **and** `owner_authorization_phrase == "Yes, with authorization."` |
| rollback | `rollback_plan` + (`commit_hash` or `files_changed`) |

Strict evidence-bound variants (`strict_*_gate`) ignore self-attested packet fields and
pass only on captured `EvidenceArtifact`s (`git_diff, test_result, secret_scan, review,
rollback, owner_authorization_grant`). **n8n never runs these gates** — it reads the
result via `/v1/cockpit/axiom`.

---

## 6. Owner gates

Exact phrase (`owner_auth.py::AUTHORIZATION_PHRASE`): `Yes, with authorization.` — no
casing/punctuation variants authorize. The 16 `OWNER_GATED_ACTIONS`: `spend_money,
post_publicly, create_third_party_account, oauth_change, credential_change,
production_deploy, dns_change, force_push, package_publish, app_store_submission,
delete_recovered_sources, modify_secrets, change_default_active_agents,
registry_mutation, regulated_claim, grant_autonomy_charter`.

In this integration the owner gate is enforced **three** times, defensively:

1. In the cockpit turn itself (surfaced as an `approval` / `detail("Owner approval required…")` chunk).
2. In the master pipeline (`Owner phrase valid?` IF node → `HOLD` if not exact).
3. In the host dispatcher (`DelegateDispatcher.plan()` refuses without the exact phrase).

A delegation is **never** auto-executed on an owner-gated action without the phrase.

---

## 7. The two hash-chained ledgers

| Ledger | Path | Shape | Written by |
|---|---|---|---|
| **AXIOM event chain** | `$HERMES_HOME/axiom/chain.jsonl` | `{v, seq, ts, kind, payload, prev, hash}`; `hash = sha256(canonical_json({kind,payload,prev,seq,ts,v}))`; genesis `prev="0"*64` | `axiom_bridge.py::record_event` |
| **GuardrailLedger** | `$HERMES_HOME/jarvis_prime/guardrail_ledger.jsonl` (0600) | `{record_id, created_at, kind, subject, payload, previous_record_hash, record_hash}`; `record_hash = sha256(canonical_json(record − record_hash))` | `guardrail_evidence.py::GuardrailLedger.append` |

The **delegation** lane appends to the GuardrailLedger — one record per attempt (allow,
refuse, success, failure). This is the append the Stage-1 prototype only *illustrated*
(`ledger_writer=axiom_ledger.append`). The real signatures differ
(`GuardrailLedger.append(kind, subject, payload)` — 3 args), so `muse_delegate_dispatcher.py`
ships the arity adapter (`LedgerWriter`). **n8n cannot write the host chain** — the master
pipeline emits the record and the host dispatcher appends it.

---

## 8. Networking (the part that actually bites)

- **n8n runs in Docker; the cockpit runs on the host.** From inside the n8n container,
  `localhost` is the container. To reach the host cockpit use **`http://host.docker.internal:8765`**
  (Docker Desktop / WSL2 resolves it). This is baked into every cockpit-targeting node as
  `MUSE_COCKPIT_URL` (default `http://host.docker.internal:8765`).
- **Host → n8n** (the delegate bridge) and **workflow → connector webhook** use
  `http://localhost:5678` (`MUSE_N8N_BASE`). n8n's port is published `127.0.0.1:5678` on the host.
- **Auth token**: workflows send `Authorization: Bearer {{ $env.MUSE_COCKPIT_TOKEN }}`. Set
  `MUSE_COCKPIT_TOKEN` in n8n's environment (or use an HTTP Header Auth credential). The token
  comes from `gateway/cockpit/auth.py` / is printed by `muse cockpit serve`. **Never commit it.**

Required n8n env vars: `MUSE_COCKPIT_URL`, `MUSE_COCKPIT_TOKEN`, `MUSE_N8N_BASE`
(see `integrations/n8n/.env.example`).

---

## 9. Bring-up against the live instances

**Fastest path (WSL2):** `cd integrations/n8n && ./bring-up.sh` — generates secrets,
`docker compose up -d`, imports **and activates** all four workflows via the n8n CLI
(`n8n import:workflow` / `update:workflow` — no API key, no OS file-picker), and runs the
echo smoke test. Then start the cockpit (`muse omni`), put its token in `.env` as
`MUSE_COCKPIT_TOKEN`, and `docker compose up -d` to reload it into the container. The
compose file forwards `MUSE_COCKPIT_URL`, `MUSE_COCKPIT_TOKEN`, and `MUSE_N8N_BASE` into
n8n so the workflows' `$env.*` expressions resolve, and maps `host.docker.internal` via
`host-gateway`.

Manual equivalent:

```bash
# 1) cockpit (host) — prints the bearer token on start
muse omni                 # full-agent cockpit on :8765 (or: muse cockpit serve --port 8765)

# 2) n8n stack (Docker)
cd integrations/n8n && cp .env.example .env    # fill secrets + MUSE_COCKPIT_TOKEN
docker compose up -d && docker compose ps       # both containers healthy

# 3) import workflows (n8n UI → Workflows → Import from File), then ACTIVATE each:
#    workflows/muse-echo-smoketest.json      (round-trip sanity)
#    workflows/muse-global-pipeline.json     (the master mirror)
#    workflows/muse-inbound-node.json        (n8n → MUSE)
#    workflows/muse-delegate-connectors.json (delegate targets)
```

n8n's CLI/JSON import always lands **inactive** — flip the **Active** toggle per workflow.

---

## 10. Verification (smoke tests)

```bash
# a) n8n reachable + echo works (Stage-1 sanity)
python integrations/n8n/muse_n8n_bridge.py http://localhost:5678

# b) cockpit reachable (no auth needed for health)
curl -s http://localhost:8765/v1/health

# c) dispatcher gate/owner logic (no network)
python integrations/n8n/muse_delegate_dispatcher.py

# d) inbound node: external → MUSE
curl -s -X POST http://localhost:5678/webhook/muse-run \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"one-line status of the release dock"}'

# e) master pipeline end-to-end (owner-gated action HOLDS without the phrase)
curl -s -X POST http://localhost:5678/webhook/muse-global-chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"post to slack that the build is green"}'
#   → expect status:"pending_owner_approval" (no phrase supplied)
```

---

## 11. Security invariants — what n8n must never do

1. **Never verify.** The AXIOM gate is authoritative and lives in MUSE. n8n reads the
   result; it does not decide it.
2. **Never bypass the owner gate.** Owner-gated actions require the exact phrase, enforced
   in the dispatcher and the pipeline.
3. **Never hold the cockpit token in a workflow file.** Env var / credential only.
4. **Bind n8n to loopback** (`127.0.0.1:5678`, as in `docker-compose.yml`). Do not expose it
   on the LAN without a reverse proxy + auth.
5. **Connector credentials are owner-gated.** The connector workflows ship with `NoOp`
   placeholders where the real Gmail/Slack node goes — connecting a third-party account is an
   `oauth_change` / `create_third_party_account` owner gate.

---

## 12. Wire-in (owner-reviewable — off by default)

The delegate stage is a *method* (`JarvisPrime.delegate`) that builds an envelope and does
**not** dispatch. To make the outbound hop live, the caller of `delegate()` invokes the
dispatcher — after the gate has passed:

```python
from integrations.n8n.muse_delegate_dispatcher import DelegateDispatcher

dispatcher = DelegateDispatcher(n8n_base_url="http://localhost:5678")
envelope = jarvis.delegate(route, packet)          # existing runtime call
envelope["gate_passed"] = turn.gate.ok             # authoritative gate result
result = dispatcher.dispatch_envelope(
    envelope, owner_authorization=owner_phrase_if_any)   # refuses without it
```

This is intentionally **not** wired into `runtime.py` here — turning it on changes default
runtime behavior and is an owner decision. Review, then enable in the module that owns the
Delegate stage.

---

## 13. Rollback

- **Workflows**: deactivate/delete the four workflows in the n8n UI. No host state changes.
- **Stack**: `docker compose down` (add `-v` to drop volumes). Back up `N8N_ENCRYPTION_KEY` first.
- **Dispatcher**: it is additive and imported nowhere by default — deleting `integrations/n8n/`
  removes it with zero effect on the rest of Hermes.
- **Ledger**: delegation records are append-only in `guardrail_ledger.jsonl`; they are evidence,
  not runtime state, and safe to retain.

---

## 14. File inventory

```
integrations/n8n/
  README.md                         operator quickstart
  .env.example                      n8n stack + bridge env (no real secrets)
  docker-compose.yml                self-hosted n8n + Postgres (loopback)
  muse_n8n_bridge.py                Stage-1 outbound bridge (vetted, unchanged)
  muse_delegate_dispatcher.py       host-side wiring: gate/owner enforce → bridge → ledger
  workflows/
    muse-global-pipeline.json       master end-to-end mirror (chat → Atlas → delegate → speak)
    muse-inbound-node.json          n8n → MUSE (callable node)
    muse-delegate-connectors.json   delegate targets (gmail-send, slack-post; idempotent)
    muse-echo-smoketest.json        Stage-1 echo round-trip
  diagrams/
    muse-n8n-global-flow.svg        the master flow diagram
    muse-n8n-global-flow.mmd        Mermaid source
docs/integrations/
  muse-n8n-full-sync.md             this document
```
