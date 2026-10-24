# NEEDLE GROUND TRUTH (Phase 1)

**Date:** 2026-08-12 · **Machine:** Lenovo Legion, RTX 5070 Laptop (8GB visible VRAM), 32GB RAM, Windows 11 + WSL2
**Status key:** VERIFIED_LOCAL = measured on this machine · VERIFIED_UPSTREAM = pinned source/doc · UNVERIFIED = not yet proven

## 1. Pinned artifacts

| Artifact | Value | Status |
|---|---|---|
| Source repo | github.com/cactus-compute/needle @ `abb5c2b7b32a3952ca2a576659702fa2edc15120` (tag v2.0.1) | VERIFIED_LOCAL |
| HF repo | huggingface.co/Cactus-Compute/needle2 @ revision `07f3e789e993e8ecf69ef5409fd7558f5fe43202` | VERIFIED_LOCAL |
| Training checkpoint | `checkpoints/needle2.pkl` sha256 `4b0a972d163ffc76…` (90,426,504 B) | VERIFIED_LOCAL |
| Deploy engine blob | `needle2.cact` sha256 `b43aabfcaf1a6db6…` (13,737,807 B ≈ 14 MB) | VERIFIED_LOCAL |
| Tokenizer | `tokenizer/tokenizer.model` sha256 `0871b8e3df78e0dd…` (SentencePiece, 8,192 vocab per config.json) | VERIFIED_LOCAL |
| Engine library | `libneedle.dll` from wheel `cactus_needle-2.0.1-py3-none-win_amd64.whl` | VERIFIED_LOCAL |

Full hashes: `docs/foundry/NEEDLE_HASHES.json`.

**Upstream drift event (VERIFIED_LOCAL):** between two polls on 2026-08-12 the HF repo moved
`weights/needle2.pkl` → `checkpoints/needle2.pkl` (snapshot `231364ff…` → `07f3e789…`).
Confirms the directive's drift-detection requirement: always pin revisions, never assume paths.

## 2. License

- Repo `LICENSE`: **MIT** (VERIFIED_UPSTREAM, source repo).
- HF model card: `license: apache-2.0` (VERIFIED_UPSTREAM, README front-matter) and HF `LICENSE` file is the Apache-2.0 text.
- Resolution: weights/engine = **Apache-2.0**, Python package = **MIT**. Both permissive, both allow
  fine-tuning/derivatives with notice preservation. No copyleft conflict. Distribution requires
  retaining both LICENSE texts. **Not blocked.**

## 3. Architecture (config.json, VERIFIED_UPSTREAM @ pinned revision)

45M total parameters; hidden 512; 27 layers; 8 heads / 4 KV heads (GQA); head_dim 64;
Hadamard MLP; engram KV memory at layers [2, 15] (orders 2,3; 8192 slots); 4 MHC lanes;
RoPE θ=100000; max_position_embeddings 2048; **sliding window 256 tokens**;
heads: contrastive_retrieval + confidence. Quantization: cactus-quants, effective 2.2 bits
(embedding=4, mhc=4, default=2), KV cache 8-bit, activations 8-bit. Deployment: self-contained
`.cact`, 14 MB binary, ~28 MB session RAM claimed.

## 4. Measured runtime behavior (VERIFIED_LOCAL, engine 2.0.1 + pinned .cact, Windows native)

| Test | Result |
|---|---|
| In-domain call | `check_polycount(max_tris=12000)` emitted correctly for "…under 12000 triangles" |
| Off-topic refusal | poem request → `function_calls: []` ✓ |
| Adjacent-domain refusal | cathedral floor-plan request → `[]` ✓ |
| Windows path arg | `D:\assets\hero.fbx` → **mangled** (`assets_hero.fbx`, garbage `scale`, invented `format` key); engine's own `validation.ungrounded` flagged it |
| >5 tool retrieval (8 tools declared) | tools #1–#6 reachable; **8th tool (`strip_unused`) unreachable → empty call**. Top-5 retrieval confirmed by measurement |
| Argument fidelity (stock) | fragile: schema metadata (`required`, `exclusiveMinimum`) bleeds into arguments; wrong arg key once (`type` instead of `axis`) |
| Confidence head | emits scores, but correct calls scored 0.0014–0.21 and broken calls 0.0003 — **does not cleanly separate good/bad in this probe; calibration study required before use as a gate** |
| Throughput | prefill ~315–353 tok/s, decode ~80–149 tok/s |
| Memory | peak ~107 MB RSS during calls |

**Consequence:** the stock model already refuses off-topic (the core contract holds), but argument
extraction is weak enough that per-niche LoRA fine-tuning is justified *if* it measurably beats this
stock baseline on the hidden eval (Phase 3 gate). The retrieval ceiling (top-5) validates the
macro-tool design rule in the directive (§13, §70).

## 5. Training path (VERIFIED_LOCAL unless noted)

- `needle finetune data.jsonl --epochs N --lora-rank 16` → LoRA on frozen base (targets
  q/k/v/gate/out proj kernels), merge + `needle build` → tuned `.cact`.
- Data format (from `model/finetune.py`): JSONL rows
  `{"query": str, "reasoning": str, "answers": [{"name": …, "arguments": {…}}], "tools": [schemas]}`.
  Empty `answers: []` = refusal example. Loader: `load_jsonl` (line 211); renderer: `render_example`.
- Base checkpoint default `checkpoints/needle2.pkl` (auto-downloads from HF if absent).
- `needle generate-data` teacher = OpenRouter (`OPENROUTER_API_KEY`, default model
  `deepseek/deepseek-v4-flash`). Teacher is swappable only by editing `finetune.py` constants —
  M.U.S.E. teacher-ladder integration must wrap/replace this.
- Compute: JAX 0.10.2 + jaxlib (Windows native install succeeded). GPU offload under WSL2/native
  Windows JAX: CUDA plugin presence **UNVERIFIED** — the controlled fine-tune run below establishes
  the actual supported path.
- Controlled fine-tune probe: dataset `foundry_test/qa_tiny.jsonl` (26 examples; 35% negatives;
  positives/paraphrases/boundary/under-specified/off-topic/adjacent/conflicting/malformed classes),
  1 epoch, batch 8, LoRA rank 16. Result recorded in `NEEDLE_FINETUNE_PROBE.json` when complete.

## 6. Needle v1 vs v2

v1 referenced encoder-decoder, 26M params in the older prompt — **superseded**: pinned v2.0.1 is
45M params, decoder-style SAN per config.json, and `run.py` explicitly rejects format-v1 checkpoints
("Old encoder-decoder/tool-calling" error, line 89). Do not mix facts.

## 7. Container/engine version pairing (VERIFIED_LOCAL, 2026-08-12)

The `.cact` container tag and the engine are version-locked:

| Artifact | Container tag | Loads on engine 2.0.0 | Loads on engine 2.0.1 |
|---|---|---|---|
| HF `needle2.cact` (pinned revision) | `0x05E12A83` | (not tested) | YES |
| `needle build` output from pinned source | `0x05E12A82` | YES | **NO (needle_load rc=-1)** |

The pinned source's exporter writes the 0x82 container; the 0x83 writer is not present in any
public branch (`git log --all -S 0x05E12A83` empty). Consequence: **tuned artifacts exported by the
vendored pipeline must be served by engine 2.0.0**, or the exporter must be ported to 0x83.
Also: `needle_load` is once-per-process — evaluate multiple artifacts in separate processes.

## 8. Schema dialect (VERIFIED_LOCAL — the decisive ground truth)

The engine expects the package's native schema shape (`needle.agent.tools.build_schema` /
`@tool` + `Field`): `{"name", "description", "parameters": {...}}`.
Feeding raw JSON-Schema-with-`"arguments"` instead compiles a broken grammar and the model emits
schema metadata as argument values (`"required": [...]`, `"minimum": 1` inside args).

Measured impact (same 10-query held-out QA eval, stock engine):
- wrong dialect: argument_value_accuracy **0.000**
- native dialect: argument_value_accuracy **1.000**

All training data and runtime tool declarations MUST be generated via `build_schema`/`Field`.

## 9. f16 optimizer NaN bug + fix (VERIFIED_LOCAL)

The released `checkpoints/needle2.pkl` stores **float16** params while config declares bfloat16.
Stock `init_lora` casts adapters to the weight dtype (f16); optax.adamw then keeps moment state in
f16, where `eps=1e-8` underflows to 0 → 0/0 → NaN on the first optimizer update.
Measured: 2,064,382/2,064,384 LoRA elements non-finite after one step at both lr 1e-4 and 1e-5.
All 26 probe examples produce finite forward losses and finite gradients — the corruption is born
inside the f16 optimizer update, not the data, not the forward, not jit (eager reproduces it).

**Fix applied in vendored copy** (`third_party/needle/needle/model/finetune.py`, MUSE-FOUNDRY
comment): keep LoRA A/B in float32; `merge_lora` already casts the delta back. Verified: 3-epoch /
12-step run completes with finite losses (adapter `foundry_test/qa_lora_fixed.pkl`, 10m42s CPU).
Upstream should receive this patch; any re-pull of the repo must re-apply it.

## 10. Contract reminders baked by measurement

- Off-topic → `[]` holds on stock. ✓
- Optional fields without evidence: mostly omitted, but stock still invents keys under path/keyboard
  noise (TEST4) → fine-tune target + deterministic post-validation is mandatory.
- >5 declared tools → unselected tools unreachable that turn. Measured. Design for ≤5 macro-tools
  per specialist or accept the retrieval-miss rate.
- Confidence is present but not yet trustworthy as a gate (needs reliability curve per §24).
