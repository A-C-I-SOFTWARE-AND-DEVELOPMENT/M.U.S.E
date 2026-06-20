# Deploy a M.U.S.E. agent fleet on Azure Kubernetes Service (AKS)

This guide takes you from nothing to a **24/7 fleet of thousands of M.U.S.E.
agents** running on **Azure Kubernetes Service**, where every agent calls a
**hosted LLM API** (Claude / OpenAI / OpenRouter / NIM / Gemini …) — **no GPU
required**.

It is the horizontal-scale companion to the single-box
[`vps-deployment-guide.md`](vps-deployment-guide.md). Read that one first if you
just want *one* always-on instance; this page is specifically about running
**many agents at fleet scale** on Azure.

> **The most important thing on this page is the next section.** Get the
> per-pod model right and a thousand agents cost ~$1–3k/mo; get it wrong (one
> container per agent) and the same workload costs 10–50× more. Everything
> else is plumbing.

---

## Read this first: many agents per pod, **not** one pod per agent

M.U.S.E. agents that route to **hosted APIs** are **I/O-bound** — each agent
spends almost all of its wall-clock time *waiting* on an LLM response, using
essentially no CPU in between. So the naive design — one container (or pod) per
agent — would have you paying for thousands of containers that are idle >95% of
the time.

Instead, run **many concurrent agent sessions inside each worker pod**. A single
async Python worker comfortably holds **hundreds** of in-flight agent loops,
because they are all blocked on network I/O, not competing for a core.

```
"thousands of agents"  ≈  a few dozen worker pods × hundreds of async sessions each
```

Concretely:

| If you want… | …you do NOT need | You need |
|---|---|---|
| 2,000 concurrent agents | 2,000 pods | ~20–40 worker pods @ ~50–100 sessions each |
| 10,000 concurrent agents | 10,000 pods | ~100–200 worker pods |

Size each pod by **memory and file descriptors / connection limits**, not CPU.
A typical worker pod requests ~0.25–0.5 vCPU and 512Mi–1Gi RAM and hosts 50–100
sessions. Tune `sessions-per-worker` (see [`configmap.yaml`](../../deploy/aks/configmap.yaml))
against your provider's rate limits — at fleet scale **the LLM provider's
rate/limit quota, not the cluster, is usually the real ceiling.**

---

## What you're building

```
┌────────────────────────────────────────────────────────────────────┐
│  Azure subscription / resource group                                 │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  AKS cluster                                                   │  │
│   │                                                                │  │
│   │   system node pool (on-demand, small)   ── control + add-ons   │  │
│   │   worker node pool  (SPOT, autoscaled)  ── the agent fleet     │  │
│   │        └─ Deployment: muse-worker  (N pods)                    │  │
│   │              each pod = hundreds of async agent sessions       │  │
│   │              KEDA scales N on Redis queue depth                │  │
│   └───────────────┬───────────────────────────┬──────────────────┘  │
│                   │ jobs / coordination        │ shared memory        │
│                   ▼                            ▼                       │
│        Azure Cache for Redis        Azure Database for PostgreSQL      │
│        (work queue + locks)         (shared agent memory)             │
│                                                                      │
│   Azure Container Registry (ACR)  ── the `hermes-agent` image         │
│   Azure Key Vault                 ── API keys (CSI → pod env)         │
└────────────────────────────────────────────────────────────────────┘
                   │ model routing (hosted APIs only)
                   ▼
   OpenRouter · NVIDIA NIM · Gemini · Anthropic · OpenAI · Together · …
```

Two design choices make this work at scale, and they're the two things the
single-box guide deliberately does *not* do:

- **State is externalized.** A single VPS keeps everything in `~/.hermes`
  (SQLite + local files, bind-mounted to `/opt/data`, see
  [`../../docker/entrypoint.sh`](../../docker/entrypoint.sh)). That is **not
  shareable across pods**. At fleet scale you move coordination to **Redis** and
  agent memory to a **shared backend** (Postgres-backed Supabase, Honcho, mem0,
  or Supermemory — all already in [`../../plugins/memory/`](../../plugins/memory/)).
  Pods stay **stateless** so they can be killed/rescheduled freely (essential for
  Spot nodes).
- **Scaling follows the queue, not CPU.** Because agents are I/O-bound, CPU-based
  HPA under-scales badly. **KEDA** scales the worker Deployment on **Redis queue
  depth** instead.

---

## Prerequisites

```bash
# Azure CLI + kubectl
az version
az aks install-cli            # installs kubectl + kubelogin if missing

az login
az account set --subscription "<SUBSCRIPTION_ID>"

# pick names you'll reuse below
RG=muse-fleet-rg
LOC=eastus
ACR=musefleetacr             # must be globally unique, lowercase alnum
AKS=muse-fleet-aks
KV=muse-fleet-kv             # must be globally unique

az group create -n "$RG" -l "$LOC"
```

---

## 1. Build & publish the image to ACR

You reuse the **same image** the rest of M.U.S.E. ships — there is no special
"AKS image". The repo already builds and publishes it in CI via
[`../../.github/workflows/docker-publish.yml`](../../.github/workflows/docker-publish.yml);
here we push it to a private ACR so the cluster can pull it.

```bash
az acr create -g "$RG" -n "$ACR" --sku Standard

# Build the repo's Dockerfile straight in ACR (no local Docker needed):
az acr build -r "$ACR" -t hermes-agent:latest .
```

The container contract is unchanged from
[`../../Dockerfile`](../../Dockerfile) / [`../../docker/entrypoint.sh`](../../docker/entrypoint.sh):
the entrypoint drops root to the `hermes` user and runs the `hermes` CLI; you
select the role with the `command` (e.g. `["gateway","run"]`). **Only the state
backends change** for fleet mode — not the image.

---

## 2. Create the AKS cluster (on-demand baseline + Spot fleet)

```bash
# System pool: small, on-demand — runs add-ons and the control-plane-adjacent bits.
az aks create -g "$RG" -n "$AKS" \
  --node-count 2 --node-vm-size Standard_D2s_v5 \
  --enable-cluster-autoscaler --min-count 2 --max-count 3 \
  --attach-acr "$ACR" \
  --enable-addons azure-keyvault-secrets-provider \
  --enable-oidc-issuer --enable-workload-identity \
  --generate-ssh-keys

# Worker pool: SPOT, autoscaled — this is where the agent fleet lives.
az aks nodepool add -g "$RG" --cluster-name "$AKS" -n workers \
  --priority Spot --eviction-policy Delete --spot-max-price -1 \
  --node-vm-size Standard_D4s_v5 \
  --enable-cluster-autoscaler --min-count 1 --max-count 50 \
  --labels workload=muse-agents \
  --node-taints kubernetes.azure.com/scalesetpriority=spot:NoSchedule

az aks get-credentials -g "$RG" -n "$AKS"
kubectl get nodes
```

Why this shape:

- **Spot for workers** — stateless, queue-driven agent pods tolerate eviction, so
  Spot's 60–90% discount applies to the bulk of the fleet. The matching
  toleration is in [`deployment.yaml`](../../deploy/aks/deployment.yaml).
- **On-demand system pool** — keeps add-ons (KEDA, CSI, DNS) stable even when Spot
  capacity churns.
- **Cluster autoscaler** grows/shrinks nodes to match the pods KEDA asks for.

Install **KEDA** (queue-based autoscaling):

```bash
# Option A: AKS-managed add-on
az aks update -g "$RG" -n "$AKS" --enable-keda
# Option B: Helm (if you prefer to manage it yourself)
# helm repo add kedacore https://kedacore.github.io/charts && helm install keda kedacore/keda -n keda --create-namespace
```

---

## 3. Provision shared state (Redis + Postgres)

```bash
# Work queue + coordination/locks
az redis create -g "$RG" -n muse-fleet-redis -l "$LOC" \
  --sku Standard --vm-size c1

# Shared agent memory (Postgres-backed memory backend)
az postgres flexible-server create -g "$RG" -n muse-fleet-pg \
  -l "$LOC" --tier Burstable --sku-name Standard_B2s \
  --storage-size 32 --version 16
```

Then point M.U.S.E. at a **shared memory backend** instead of local SQLite. The
backends already exist under [`../../plugins/memory/`](../../plugins/memory/) —
pick one and supply its connection via env/secret rather than writing new code:

- **Supabase** (`plugins/memory/supabase/`) — Postgres-backed, the natural fit for
  the Flexible Server above.
- **Honcho / mem0 / Supermemory** (`plugins/memory/{honcho,mem0,supermemory}/`) —
  hosted shared-memory services; set their API keys as secrets (see step 4).

Keep agent *coordination* (the job queue, leases, locks) in Redis; keep agent
*memory* in the shared backend. Do **not** rely on the per-pod `/opt/data`
volume for anything that must survive a pod restart — on Spot nodes, it won't.

---

## 4. Secrets via Azure Key Vault (never in the image)

Per the repo rule (**no secrets in code; keys live in env** — CLAUDE.md §5), API
keys are stored in Key Vault and projected into pods by the CSI Secrets Store
driver. They are **never** baked into the image or committed.

```bash
az keyvault create -g "$RG" -n "$KV" -l "$LOC" --enable-rbac-authorization true

# Add the provider keys you actually have (only those you have):
az keyvault secret set --vault-name "$KV" -n OPENROUTER-API-KEY --value "sk-or-..."
az keyvault secret set --vault-name "$KV" -n ANTHROPIC-API-KEY  --value "sk-ant-..."
az keyvault secret set --vault-name "$KV" -n REDIS-URL          --value "rediss://:<key>@muse-fleet-redis.redis.cache.windows.net:6380/0"
az keyvault secret set --vault-name "$KV" -n REDIS-PASSWORD     --value "<redis-access-key>"   # KEDA queue-depth auth
az keyvault secret set --vault-name "$KV" -n DATABASE-URL       --value "postgresql://user:pass@muse-fleet-pg.postgres.database.azure.com:5432/postgres"
```

The mapping from Key Vault into a Kubernetes `Secret` is declared in
[`secretproviderclass.yaml`](../../deploy/aks/secretproviderclass.yaml). Fill in
your Key Vault name, tenant ID, and the workload-identity client ID there before
applying.

---

## 5. Deploy the fleet

The starter manifests live in [`../../deploy/aks/`](../../deploy/aks/). Edit the
placeholders (`<ACR>`, `<KEYVAULT>`, `<TENANT_ID>`, `<CLIENT_ID>`, sizes), then
apply **in order**:

```bash
cd deploy/aks
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secretproviderclass.yaml
kubectl apply -f deployment.yaml
kubectl apply -f keda-scaledobject.yaml
```

- [`deployment.yaml`](../../deploy/aks/deployment.yaml) — the `muse-worker`
  Deployment: pulls `hermes-agent` from ACR, schedules onto the Spot pool
  (toleration + nodeSelector), pulls config from the ConfigMap and keys from the
  CSI-mounted secret, and runs many async agent sessions per pod.
- [`keda-scaledobject.yaml`](../../deploy/aks/keda-scaledobject.yaml) — scales the
  Deployment between `minReplicaCount` and `maxReplicaCount` on **Redis list
  length** (queue depth).
- [`configmap.yaml`](../../deploy/aks/configmap.yaml) — non-secret knobs:
  `sessions-per-worker`, model-routing policy, memory-backend selection.

---

## 6. Verify & operate

```bash
kubectl -n muse get pods -o wide          # workers scheduled on the Spot pool?
kubectl -n muse logs -l app=muse-worker --tail=50
kubectl -n muse get scaledobject,hpa      # KEDA created the HPA?

# Drive the queue and watch the fleet scale:
#   push jobs into the Redis list, then:
kubectl -n muse get pods -w               # pods should multiply with queue depth
```

**Cost guardrails — set these and check them weekly:**

| Guardrail | Where | Why |
|---|---|---|
| `maxReplicaCount` (KEDA) + node-pool `--max-count` | `keda-scaledobject.yaml`, `az aks nodepool` | Hard ceiling on spend; a runaway queue can't scale you into bankruptcy. |
| Spot for the worker pool | `az aks nodepool add --priority Spot` | 60–90% of fleet cost lives here. |
| `sessions-per-worker` high enough | `configmap.yaml` | Under-packing wastes pods/nodes; this is the per-pod cost lever. |
| Provider rate limits | provider dashboards | Usually the true ceiling — raising replicas past your API quota just burns money on retries. |

**Teardown** (everything is in one resource group):

```bash
az group delete -n "$RG" --yes --no-wait
```

---

## How this differs from the single-VPS guide

| | Single VPS ([`vps-deployment-guide.md`](vps-deployment-guide.md)) | AKS fleet (this guide) |
|---|---|---|
| Scale | One always-on instance | Thousands of agents, autoscaled |
| Agent↔container | Everything in one process tree | Many async sessions per pod, many pods |
| State | `~/.hermes` SQLite + files (`/opt/data`) | Redis (queue) + shared memory backend |
| Keys | `~/.hermes/.env` | Azure Key Vault → CSI → pod env |
| Scaling | n/a | KEDA on Redis queue depth |
| Cost lever | VM size | Spot pool + sessions-per-worker |

Start on a VPS to learn M.U.S.E.; graduate to AKS when one box can't hold the
concurrency you need.

---

## See also

- [`vps-deployment-guide.md`](vps-deployment-guide.md) — the single-box, one-command deployment.
- [`../../deploy/aks/README.md`](../../deploy/aks/README.md) — the manifests this guide applies.
- [`../orchestration/README.md`](../orchestration/README.md) — how M.U.S.E. decomposes goals into jobs (the work this fleet executes).
- [`../../plugins/memory/`](../../plugins/memory/) — the shared memory backends referenced above.
- [`../../Dockerfile`](../../Dockerfile) · [`../../docker/entrypoint.sh`](../../docker/entrypoint.sh) — the container contract the image follows.
