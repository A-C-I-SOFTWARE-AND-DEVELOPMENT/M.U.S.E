# Azure representation of all M.U.S.E assets

M.U.S.E is represented in Azure AI Foundry through a safe, secret-free representation pack plus a Foundry Agent Service vector store.

## What is represented

The sync covers these project surfaces:

- Datasets: dataset files, dataset-producing scripts, eval/sample data references, and source-data pointers.
- Pipelines: GitHub workflows, Hermes orchestration, studio pipeline, research-fabric, Teams pipeline, and Azure sync automation.
- Karpathy system: LLM-wiki / compiled markdown knowledge-system assets and docs.
- RAG: retrieval, vector, embedding, parser, and GraphRAG-related project assets.
- Skills: Hermes skill library and optional skill library.
- Docs: repository docs and website docs.
- Runtime: `agent/` and `hermes_cli/` runtime code represented by inventory metadata.
- Config: Azure/Hermes/fusion/provider manifests, with secret-like lines redacted.
- Tests and scripts: represented by categorized path inventory and selected metadata.

## Azure surfaces

- Azure AI Foundry project:
  `https://echerd27-5762-resource.services.ai.azure.com/api/projects/echerd27-5762`

- Azure OpenAI-compatible endpoint:
  `https://echerd27-5762-resource.cognitiveservices.azure.com/openai/v1`

- Current RAG vector store:
  `vs_4p4BOhIhB7eA7QdfpG3vX4e9`

- Vector store name:
  `MUSE full project RAG`

## Agent updates

These agents are updated with Code Interpreter plus file_search against the full M.U.S.E RAG vector store:

- MUSE Long-Horizon Orchestrator
- MUSE Research Synthesizer
- MUSE Build Planner
- MUSE Quality Verifier

## Representation payload

The sync script generates the ignored local payload directory:

`.azure/sync_payload/`

Uploaded representation files include:

- `muse_full_azure_representation.md`
- `muse_path_index.md`
- `muse_datasets.md`
- `muse_pipelines.md`
- `muse_rag.md`
- `muse_karpathy_llm_wiki.md`
- `muse_skills.md`
- `muse_docs.md`
- `muse_config.md`

The full local JSONL inventory remains local/ignored at:

`.azure/sync_payload/muse_repo_inventory.jsonl`

## Foundry datasets

Created Azure AI Foundry dataset versions:

- `muse-full-representation` -> `azureai://accounts/echerd27-5762-resource/projects/echerd27-5762/data/muse-full-representation/versions/2026-07-02-025758`
- `muse-datasets-registry` -> `azureai://accounts/echerd27-5762-resource/projects/echerd27-5762/data/muse-datasets-registry/versions/2026-07-02-025758`
- `muse-pipelines-registry` -> `azureai://accounts/echerd27-5762-resource/projects/echerd27-5762/data/muse-pipelines-registry/versions/2026-07-02-025758`
- `muse-karpathy-llm-wiki-registry` -> `azureai://accounts/echerd27-5762-resource/projects/echerd27-5762/data/muse-karpathy-llm-wiki-registry/versions/2026-07-02-025758`
- `muse-rag-registry` -> `azureai://accounts/echerd27-5762-resource/projects/echerd27-5762/data/muse-rag-registry/versions/2026-07-02-025758`

## Latest sync stats

- Scanned safe files: 6684
- Uploaded Foundry files: 9
- Created Foundry datasets: 5
- Config assets: 6
- Dataset assets: 5
- Docs: 737
- Karpathy/LLM-wiki assets: 10
- Pipeline assets: 222
- RAG assets: 39
- Runtime assets: 528
- Script assets: 66
- Skill assets: 1253
- Test assets: 1570

## Run the sync

The sync script is:

`scripts/azure/sync_muse_to_foundry.py`

It is idempotent in behavior but creates a fresh vector store snapshot on each run, then updates all M.U.S.E Foundry agents to point at the latest vector store.

Security policy:

- Does not upload `.env` files.
- Skips `.git`, venvs, node_modules, caches, build outputs, databases, binary model weights, media files, and local Azure state.
- Redacts secret-like lines in snippets.
- Uploads generated manifests/digests rather than raw private secrets.

## Smoke test

The orchestrator was asked to use the attached M.U.S.E file_search/RAG and list representation layers. The run completed and cited uploaded files including `muse_config.md`, `muse_full_azure_representation.md`, `muse_datasets.md`, and `muse_karpathy_llm_wiki.md`.
