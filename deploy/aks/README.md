# M.U.S.E. AKS fleet manifests

Starter Kubernetes manifests for running a **24/7 fleet of thousands of
hosted-API (no-GPU) M.U.S.E. agents** on **Azure Kubernetes Service**.

> These are **templated examples**, not turnkey config. Replace every
> `<PLACEHOLDER>` and size the knobs for your workload before applying. The full
> walkthrough — provisioning AKS, ACR, Redis, Postgres, and Key Vault — lives in
> [`../../docs/deploy/aks-fleet-deployment-guide.md`](../../docs/deploy/aks-fleet-deployment-guide.md).
> Read it first.

## The one idea that matters

**Many async agent sessions per pod — not one pod per agent.** Agents wait on
LLM APIs, so a few dozen worker pods (each hosting hundreds of sessions) serve
thousands of agents. This is the difference between a ~$1–3k/mo bill and a
10–50× larger one. Tune `SESSIONS_PER_WORKER` in `configmap.yaml`.

## Files & apply order

```bash
kubectl apply -f namespace.yaml            # 1. muse namespace
kubectl apply -f configmap.yaml            # 2. non-secret tunables
kubectl apply -f secretproviderclass.yaml  # 3. Key Vault -> Secret mapping
kubectl apply -f deployment.yaml           # 4. the muse-worker fleet
kubectl apply -f keda-scaledobject.yaml    # 5. queue-depth autoscaling
```

| File | What it is |
|---|---|
| `namespace.yaml` | The `muse` namespace. |
| `configmap.yaml` | Non-secret knobs (`SESSIONS_PER_WORKER`, memory backend, model policy). |
| `secretproviderclass.yaml` | Azure Key Vault → K8s `Secret` (API keys, Redis/DB URLs) via CSI. |
| `deployment.yaml` | The `muse-worker` Deployment; Spot-pool scheduling; many sessions/pod. |
| `keda-scaledobject.yaml` | KEDA scaling on Redis queue depth + Redis auth. |

## Placeholders to fill

| Placeholder | In | Value |
|---|---|---|
| `<ACR>` | `deployment.yaml` | ACR login server, e.g. `musefleetacr.azurecr.io` |
| `<KEYVAULT>` | `secretproviderclass.yaml` | Key Vault name |
| `<TENANT_ID>` | `secretproviderclass.yaml` | `az account show --query tenantId -o tsv` |
| `<CLIENT_ID>` | `secretproviderclass.yaml` | Workload-identity client ID with vault `get` |

## Validate before applying

```bash
kubectl apply --dry-run=client -f .   # schema sanity check (no cluster changes)
```

## Not included (by design)

- **Terraform/Bicep IaC** — the guide uses `az` CLI for clarity; wrap it in IaC later.
- **GPU / local-model hosting** — this fleet is hosted-API only.
- **Cluster add-on install** (KEDA, CSI driver) — enabled at the cluster level in the guide, not here.
