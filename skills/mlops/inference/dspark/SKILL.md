---
name: serving-llms-dspark
description: "DSpark: DeepSeek speculative decoding — 60-85% faster inference, identical outputs."
version: 1.0.0
author: Nous Research
license: MIT
dependencies: []
platforms: [linux, macos]
metadata:
  hermes:
    tags: [DSpark, DeepSpec, Speculative Decoding, Draft Model, Inference Acceleration, llama.cpp, vLLM, DeepSeek, Efficiency]

---

# DSpark - Speculative Decoding Acceleration

## When to use

Use when local or self-hosted inference feels slow and you want 60-85% faster generation **without changing outputs, models, or hardware**. DSpark (DeepSeek + Peking University, MIT, arXiv:2606.19348) attaches a small draft module that proposes several tokens per step; the target model verifies them in one forward pass. Output quality is *identical* — the target model still decides every token.

Muse's plan builder lives at `hermes_cli/local_models/dspark.py` (`runtime: dspark` in the server-adapter layer): it picks llama.cpp or vLLM, resolves the right draft checkpoint, and emits the exact launch command.

## Quick start

**Zero-install path — DeepSeek API.** `api.deepseek.com` serves V4-Flash/V4-Pro with DSpark server-side since 2026-06-27. Routing to the `deepseek` provider already gets the speedup.

**llama.cpp (CPU / Metal / consumer GPU):**

```bash
# 1. Grab a DSpark draft GGUF (community conversion of the official draft)
huggingface-cli download ankk98/dspark-qwen3-8b-block7-Q4_K_M-GGUF

# 2. Serve target + draft
llama-server -m qwen3-8b-instruct-Q4_K_M.gguf --port 8080 \
  --spec-draft-model dspark-qwen3-8b-block7-Q4_K_M.gguf \
  --spec-draft-n-max 16 --spec-draft-n-min 1 --spec-draft-p-min 0.75
```

**vLLM (GPU hosts):**

```bash
vllm serve Qwen/Qwen3-8B \
  --speculative-config '{"model": "mgoin/Qwen3-8B-speculator.dspark", "num_speculative_tokens": 5}'
```

**Self-contained V4 checkpoints** (draft module already attached; server-class GPUs):

```bash
vllm serve deepseek-ai/DeepSeek-V4-Flash-DSpark
```

Point muse at the endpoint as usual (`provider: custom`, `base_url: http://127.0.0.1:8080/v1`). Speculative decoding is invisible to clients.

## Draft catalog (official DeepSpec releases)

| Target | Official draft (safetensors) | GGUF (llama.cpp) | speculators (vLLM) |
|---|---|---|---|
| Qwen3-4B | `deepseek-ai/dspark_qwen3_4b_block7` | — | — |
| Qwen3-8B | `deepseek-ai/dspark_qwen3_8b_block7` | `ankk98/dspark-qwen3-8b-block7-Q4_K_M-GGUF` | `mgoin/Qwen3-8B-speculator.dspark` |
| Qwen3-14B | `deepseek-ai/dspark_qwen3_14b_block7` | — | — |
| Gemma4-12B-it | `deepseek-ai/dspark_gemma4_12b_block7` | `ankk98/dspark-gemma4-12b-block7-Q4_0-GGUF` | — |
| DeepSeek-V4-Flash | self-contained: `deepseek-ai/DeepSeek-V4-Flash-DSpark` | — | (serves directly) |
| DeepSeek-V4-Pro | self-contained: `deepseek-ai/DeepSeek-V4-Pro-DSpark` | — | (serves directly) |

For any other target, train a custom draft with [DeepSpec](https://github.com/deepseek-ai/DeepSpec) — data prep → multi-GPU draft training → 9-benchmark eval (defaults assume 1 node × 8 GPUs).

## Tuning

- `num_speculative_tokens` / draft window: DeepSeek's deployed config drafts 5 ("DSpark-5"). llama.cpp's `--spec-draft-n-max 16` lets acceptance run longer on easy text.
- Speedup concentrates in **decode-heavy** work: long generations, agent loops, code. Prefill-bound work (huge prompt, tiny answer) sees less.
- Draft acceptance drops on out-of-distribution prompts — the speedup shrinks but never reverses, and outputs stay exactly the target model's.
- Measure before/after with the same prompt set; llama.cpp reports draft acceptance in its server logs.

## When to use vs alternatives

**Use DSpark when:** the model you already run has an official or community draft (see catalog), or you can afford a DeepSpec training run for a custom one.

**Use alternatives instead:**
- **Quantization** (Q4/AWQ/FP8): when memory, not latency, is the constraint — composable with DSpark.
- **Cerebras / Groq cloud**: when you want raw speed and cloud is acceptable — no draft management at all.
- **Smaller model**: when quality margin allows — speculative decoding never changes quality; a smaller model does.

## Resources

- DeepSpec (training + eval, MIT): https://github.com/deepseek-ai/DeepSpec
- Paper: arXiv:2606.19348
- Muse integration: `hermes_cli/local_models/dspark.py`, tests at `tests/hermes_cli/test_dspark_runtime.py`
