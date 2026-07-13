# MUSE ↔ n8n integration

Full, bidirectional sync between MUSE and self-hosted **n8n** — the external
app-connector + automation layer. This finishes the Stage-1 "echo" prototype into a
complete, global end-to-end pipeline.

> **Architecture reference (read this):** [`docs/integrations/muse-n8n-full-sync.md`](../../docs/integrations/muse-n8n-full-sync.md)
> — every stage → contract, the Atlas map, the 8 gates, owner gates, the two ledgers,
> networking, and the security invariants.

## What it does

- **Outbound (MUSE → n8n):** the *delegate* stage hands an **AXIOM-gated** action to an
  n8n connector (email, Slack, 400+ apps) — only after the gate passes and any owner
  authorization is present, with every attempt appended to the hash-chained ledger.
- **Inbound (n8n → MUSE):** a webhook exposes MUSE as a **callable node** for Zapier /
  Make / external systems — the direction Stage-1 left unbuilt.
- **Master mirror:** one importable workflow that walks the **entire turn** — chat AI
  agent → perceive → classify → decide → gate → owner gate → delegate → connectors →
  ledger → speak — mapped onto the Atlas decks.

**Invariant:** *intelligence proposes; the verifier disposes.* n8n executes; the AXIOM
gate stays in MUSE.

## Contents

```
.env.example                     n8n stack + bridge env (no real secrets)
docker-compose.yml               self-hosted n8n + Postgres, bound to 127.0.0.1
muse_n8n_bridge.py               Stage-1 outbound bridge (vetted, unchanged)
muse_delegate_dispatcher.py      host-side wiring: gate/owner enforce → bridge → ledger
workflows/
  muse-global-pipeline.json      master end-to-end mirror
  muse-inbound-node.json         n8n → MUSE (callable node)
  muse-delegate-connectors.json  delegate targets (gmail-send, slack-post; idempotent)
  muse-echo-smoketest.json       Stage-1 echo round-trip
diagrams/
  muse-n8n-global-flow.svg/.mmd  the master flow diagram
```

## Quickstart

**One command (WSL2)** — generates secrets, brings the stack up, imports + activates
all four workflows via the n8n CLI (no UI file-picker), and runs the echo smoke test:

```bash
cd integrations/n8n && ./bring-up.sh
```

Then start the cockpit and hand n8n its token:

```bash
muse omni                     # cockpit :8765 — prints the bearer token
#  put the token in .env as MUSE_COCKPIT_TOKEN, then:
docker compose up -d          # reloads env into the n8n container
```

<details><summary>Manual equivalent</summary>

```bash
muse omni                                    # cockpit on :8765
cp .env.example .env                         # fill secrets + MUSE_COCKPIT_TOKEN
docker compose up -d && docker compose ps    # both containers healthy
# n8n UI → Workflows → Import from File → import each, then flip Active ON.
```
</details>

Required n8n env (see `.env.example`): `MUSE_COCKPIT_URL` (default
`http://host.docker.internal:8765` — the host cockpit as seen from inside the container),
`MUSE_COCKPIT_TOKEN` (from `muse cockpit serve`), `MUSE_N8N_BASE` (default
`http://localhost:5678`).

## Smoke tests

```bash
python muse_n8n_bridge.py http://localhost:5678          # echo round-trip
python muse_delegate_dispatcher.py                        # gate/owner logic (no network)
curl -s http://localhost:8765/v1/health                   # cockpit up
curl -s -X POST http://localhost:5678/webhook/muse-run \
  -H 'Content-Type: application/json' -d '{"prompt":"status?"}'   # inbound → MUSE
```

## Turning the outbound hop on

The delegate dispatch is **off by default** (enabling it changes default runtime behavior —
an owner decision). Wire-in and rollback are in the architecture reference, §12–13.

## Safety

n8n binds to loopback only. The cockpit token lives in env, never in a workflow file.
Connector workflows ship with `NoOp` placeholders where the real Gmail/Slack node goes —
connecting a third-party account is an owner-gated action.
