# Connect M.U.S.E to Microsoft Foundry

This repository is wired for the Microsoft Foundry project opened from:

https://ai.azure.com/nextgen/r/3V-DMJbcS5a1F76OqO55Gg,M.U.S.E,,echerd27-5762-resource,echerd27-5762/operate/overview

Project metadata:

- Foundry project: `M.U.S.E`
- Azure resource group: `echerd27-5762-resource`
- Azure resource name: `echerd27-5762`
- Hermes connection manifest: `config/azure-foundry-muse.yaml`
- Connector script: `scripts/azure/connect_muse_foundry.py`

## What the connector does

`scripts/azure/connect_muse_foundry.py` connects the local Hermes/M.U.S.E configuration to this Foundry project without storing secrets.

It:

1. Reads `config/azure-foundry-muse.yaml`.
2. Checks Azure CLI login state.
3. If logged in, attempts to discover the Azure resource and candidate inference endpoints.
4. Updates the local Hermes config at `C:\Users\Echer\AppData\Local\hermes\config.yaml` with:
   - `azure_foundry_projects.muse`
   - provider metadata for `azure-foundry-muse`
   - aliases: `azure-foundry-muse`, `azure-muse`, `foundry-muse`
5. Preserves the current active default model unless `--activate` is explicitly passed.
6. Writes connection state to `.azure/muse-foundry-connection.json`.

## Authentication

Preferred auth is Microsoft Entra ID / Azure RBAC:

- Role: `Azure AI User` or renamed `Foundry User`
- Scope: the Foundry resource
- Token scope used by Hermes: `https://ai.azure.com/.default`

Static API-key auth is also supported through the existing Hermes variable:

- `AZURE_FOUNDRY_API_KEY`

No Azure secret should be committed to this repository.

## Endpoint discovery

The Azure portal URL identifies the Foundry project/resource, but it is not itself an inference endpoint. If Azure CLI is logged in and authorized, the connector will discover the resource metadata and candidate endpoint URLs.

If Azure CLI is not logged in yet, set the endpoint manually in your environment before running the connector:

- `AZURE_FOUNDRY_BASE_URL`
- `AZURE_FOUNDRY_MODEL`

Typical OpenAI-compatible endpoint shape:

`https://<resource>.openai.azure.com/openai/v1`

Some Foundry resources expose service endpoints instead; keep the exact endpoint from Foundry's "Keys and Endpoint" / deployment page.

## Runtime behavior

The default local config remains NVIDIA NIM unless Azure is explicitly activated. This is intentional: it connects the project while avoiding a broken default provider when Azure CLI is not authenticated yet.

To make Azure Foundry the active Hermes provider, run the connector with `--activate` after Azure login and endpoint discovery succeeds.
