# Phase 0 Reality Capture Report

**Generated:** 2026-08-12T16:30:11.709999Z

## 1. Repository State

- **Current Commit:** bb78a5bf1c4373672a949056d256c75cc3165945
- **Branch:** main
- **Dirty Files Count:** 56
- **Sample Dirty Files:**   - M agent/agent_runtime_helpers.py
  -  M agent/conversation_loop.py
  -  M agent/fusion_model_router.py
  -  M agent/fusion_router.py
  -  M agent/models_dev.py
  -  M api/gateway/[...path].ts
  -  M apps/desktop/ui/src/omni/components/setup/ConnectWizard.tsx
  -  M apps/desktop/ui/src/omni/lib/capabilities.ts
  -  M apps/desktop/ui/src/omni/lib/connect.ts
  -  M apps/desktop/ui/src/omni/lib/modelCatalog.ts

## 2. Provider Inventory

The M.U.S.E. provider layer is defined in `config/model-catalog.yaml` and the authentication/runtime resolution in `hermes_cli/auth.py`.

### Configured Providers

| Provider ID | Requires Env Var | Model Count | Sample Models |
|-------------|------------------|-------------|---------------|
| openrouter | OPENROUTER_API_KEY | 15 | llama-3.3-70b (meta-llama/llama-3.3-70b-instruct), llama-3.1-8b (meta-llama/llama-3.1-8b-instruct) |
| novita | NOVITA_API_KEY | 3 | llama-3.3-70b (meta-llama/llama-3.3-70b-instruct), qwen-2.5-7b (qwen/qwen-2.5-7b-instruct) |
| cerebras | CEREBRAS_API_KEY | 2 | gpt-oss-120b (gpt-oss-120b), zai-glm-4.7 (zai-glm-4.7) |
| nvidia | NVIDIA_API_KEY | 2 | llama-3.1-nemotron-70b (nvidia/llama-3.1-nemotron-70b-instruct), mistral-nemo-12b (nv-mistralai/mistral-nemo-12b-instruct) |
| huggingface | HF_TOKEN | 2 | qwen-2.5-coder-32b (Qwen/Qwen2.5-Coder-32B-Instruct), llama-3.1-8b (meta-llama/Llama-3.1-8B-Instruct) |
| ollama-cloud | OLLAMA_CLOUD_API_KEY | 2 | llama3.3-70b (llama3.3:70b), deepseek-r1-70b (deepseek-r1:70b) |
| ollama-local | (none) | 13 | gemma4-e2b (gemma4:e2b), gemma4-e4b (gemma4:e4b) |
| llamacpp-local | (none) | 1 | qwen2.5-7b (qwen2.5-7b-instruct) |

### Default Model Tiers

- **Frontier:** openrouter/llama-3.3-70b, novita/llama-3.3-70b, nvidia/llama-3.1-nemotron-70b, cerebras/zai-glm-4.7
- **Fast:** ollama-local/qwen3_5-9b, ollama-local/gemma4-12b, cerebras/gpt-oss-120b, openrouter/llama-3.1-8b
- **Local:** ollama-local/qwen3_5-9b, ollama-local/gemma4-12b, ollama-local/qwen3-coder-30b

## 3. AXIOM Niche Ecosystem

- **Total Niche Specs:** 137 (all `.yaml` files in `hermes_cli/jarvis_prime/niches/specs`)
- **Niche Spec Schema:** Defined in `hermes_cli/jarvis_prime/niches/schema.py` (see `NicheSpec` dataclass)
- **Example Niche:** (see any `.yaml` file in the specs directory)

The niches are currently routing specifications rather than independently trained models. They include:
  - ID (e.g., `architecture.system.design`)
  - Keywords
  - System text (prompt)
  - Toolsets (default: `("filesystem", "codebase")`)
  - Scout queries (for information gathering)
  - Model lane (default: `"muse-local"`)
  - Iteration limit

## 4. Hardware & Environment

- **OS Name:** Microsoft Windows 11 Home
- **OS Version:** LENOVO Q6CN79WW, 4/23/2026
- **System Type:** x64-based PC
- **Processor(s):** 1 Processor(s) Installed.
- **Total Physical Memory:** 32,189 MB

**WSL2:** Available (as noted in the project context)
**Primary GPU:** RTX 5070 Laptop (12 GB VRAM) - as per project context
**Python Environment:** Likely via `.venv` or `venv` (see project context)
**JAX Version:** 0.10.2 (installed)
**CUDA Available:** Yes (via nvidia-smi and PyTorch)
**CUDA Version:** 13.1 (from nvidia-smi)
**GPU:** NVIDIA GeForce RTX 5070 Laptop GPU

## 5. Switchyard Evaluation

- **Local Switchyard Present:** True
- **Path:** C:\Users\Echer\Downloads\Switchyard-main

### Switchyard Description (from README)
```
<p align="center">
  <img src="assets/logo.png" alt="Switchyard" width="800">
</p>

# Switchyard

Switchyard is a Rust proxy and library for LLM traffic. It routes requests
across providers, translates between OpenAI and Anthropic APIs, records
operational metrics, and provides typed, composable routing algorithms.

**Why Switchyard?** Point a coding agent such as Claude Code or Codex at an
open-source model. Switchyard translates between the OpenAI Chat, Anthropic
Messages, and OpenAI Responses formats, so the agent keeps speaking its native
API while the request is served by vLLM, NVIDIA NIM, Ollama, or any
OpenAI-compatible endpoint. The same proxy can spread traffic across several
models for A/B benchmarking, apply signal-driven stage routing, or run a custom
algorithm you write yourself.

## Features


```

**Initial Assessment:** Switchyard is a Rust-based LLM traffic router that provides protocol translation (OpenAI Chat, Anthropic Messages, OpenAI Responses) and multiple backends. It is pre-alpha and experimental. M.U.S.E. already has a provider routing layer in `auxiliary_client.py` and `auth.py`. Switchyard may offer complementary concepts (e.g., signal-driven stage routing, metrics) but would need to be evaluated for integration without compromising M.U.S.E.'s authority boundaries.

## 6. Needle Ground Truth

We have cloned the official Needle 2 repository from https://github.com/cactus-compute/needle and conducted an initial investigation.

### Key Findings:

- **Repository:** https://github.com/cactus-compute/needle
- **Local Path:** C:\Users\Echer\M.U.S.E\third_party\needle
- **Commit:** abb5c2b7b32a3952ca2a576659702fa2edc15120
- **Git Describe:** v2.0.1
- **License:** MIT (as seen in LICENSE file)
- **Model License:** Need to check the model license on Hugging Face
- **Architecture:** Simple Attention Network (SAN) with Hadamard MLP, GQA, engram KV memory, multi-lane hyper-connections
- **Parameters:** 45M (as per README)
- **Size:** ~14 MB at INT4 (as per README)
- **Tokenizer:** SentencePiece with vocab size 8192 (from tokenizer.py: TOKENIZER_PREFIX + ".model")
- **Context Window:** 256-token sliding window (from README)
- **Tool Retrieval:** Built-in retrieval head renders only the top five tools per turn (from README)
- **Confidence Head:** Every response carries a calibrated confidence score from a learned head (from README)
- **Grammar Constrained Decoding:** needle.Field constraints compile into the decode grammar (from README)
- **CLI Commands:** run, finetune, generate-data, build, playground
- **Default Base Checkpoint:** checkpoints/needle2.pkl
- **Hardware Compatibility:** JAX 0.10.2, CUDA available (RTX 5070), PyTorch CUDA available
- **Notes:** The model weights are fetched from Hugging Face (Cactus-Compute/needle2) and cached locally.

### Verification Status:

We attempted to run the Needle 2 CLI and found that:
- The `needle` command is available after installation.
- The model weights are fetched from Hugging Face (Cactus-Compute/needle2) and cached locally.
- We encountered a 404 error when trying to download the default checkpoint (`checkpoints/needle2.pkl`) from the Hugging Face repository, suggesting that the checkpoint file may not be present at that path or the repository structure is different.
- The playground server starts successfully, indicating that the core engine is functional.

Further investigation is required to confirm the exact checkpoint format and the correct procedure for running inference and fine-tuning.

## 7. Axiom Ledger & Verification

- **Axiom Data Directory:** `C:\Users\Echer\M.U.S.E\.hermes\axiom`
- **Ledger Files:** `chain.jsonl` (size: N/A bytes)
- **Verification Components:** The Axiom directory contains core modules for contracts, effects, ledger, verifier, governance, forge, interface, memory, and orchestrator.

## 8. Open Questions & Next Steps

Based on the Phase 0 audit, the following questions arise for Phase 1 (Needle Ground Truth):

1. What is the exact location of the Needle 2 model checkpoint on Hugging Face? (We need to find the correct path for the base model.)
2. What is the license for the Needle 2 model weights? (We must verify this before proceeding with any distribution or integration.)
3. How does Needle 2 integrate with Hermes' existing provider layer? (Can it be added as a new provider plugin?)
4. What is the exact behavior of Needle 2 regarding tool retrieval, confidence scoring, and schema-constrained generation? (We need to run actual tests.)
5. What training pathways are supported for Needle 2 (LoRA, full fine-tuning, etc.)? (We have seen LoRA support in the code.)
6. Is the WSL2/JAX/GPU training path feasible on the local machine? (We need to run a actual fine-tune to verify.)

### Recommended Next Steps for Phase 1:

- Investigate the Hugging Face repository Cactus-Compute/needle2 to locate the model files and verify the license.
- Attempt to download the model via `huggingface_hub` directly to see what files are available.
- Set up an isolated environment to test stock Needle 2 inference, refusal behavior, and schema constraints (once we have the model).
- Probe the WSL2/JAX/GPU training path on the local machine (RTX 5070) to determine feasibility by running a minimal fine-tune.
- Examine the tokenizer and grammar compilation to understand how schemas are converted into decode constraints.

## 9. Evidence Appendices

- **Repository Snapshot:** `docs/foundry/PHASE0_REALITY_SNAPSHOT.json`
- **Provider Inventory:** `docs/foundry/PHASE0_PROVIDER_INVENTORY.json`
- **Needle Ground Truth:** `docs/foundry/NEEDLE_GROUND_TRUTH.json`
- **Full System Info:** Available upon request (command: `systeminfo`)

---

*This report is a living document and will be updated as Phase 0 progresses.*
