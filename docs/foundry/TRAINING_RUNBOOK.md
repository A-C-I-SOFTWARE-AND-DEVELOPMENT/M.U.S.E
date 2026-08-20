# TRAINING RUNBOOK

**Verified on:** 2026-08-12, Lenovo Legion RTX 5070, Windows 11 native Python 3.11, JAX 0.10.2 (CPU).

## Environment lock (§29)

| Component | Pin |
|---|---|
| Source | `third_party/needle` @ abb5c2b7b32a3952ca2a576659702fa2edc15120 (v2.0.1) **+ f32-LoRA patch** |
| Base checkpoint | HF `Cactus-Compute/needle2` @ 07f3e789e993e8ecf69ef5409fd7558f5fe43202, `checkpoints/needle2.pkl` sha256 4b0a972d163ffc76… |
| Engine (serve tuned) | `libneedle.dll` from `cactus_needle-2.0.0-py3-none-win_amd64.whl` (0x82 container) |
| Engine (serve stock) | `cactus_needle-2.0.1` wheel (0x83 container) |
| Tokenizer | `tokenizer/tokenizer.model` sha256 0871b8e3df78e0dd… |
| JAX | 0.10.2 CPU (Windows native) **and 0.11.0 cuda12 (WSL2, GPU-verified)** |

## Critical rules (all measured, not optional)

1. **Schema dialect:** generate every tool schema via `needle.agent.tools.build_schema` / `@tool` +
   `Field`. The `"parameters"` key is mandatory. Wrong dialect silently breaks the decode grammar
   (arg accuracy 0.0 vs 1.0 measured).
2. **f32 LoRA:** never revert the `init_lora` f32 patch. Stock f16 path NaNs on the first update.
3. **One engine load per process.** `needle_load` is not re-entrant; eval harnesses must spawn
   one process per artifact.
4. **Container pairing:** artifacts from `needle build` (0x82) run on engine 2.0.0 only.

## Commands

```bash
# data (JSONL rows: {"query","reasoning","answers":[{name,arguments}],"tools":[native schemas]})
needle finetune data.jsonl --epochs 3 --batch-size 8 --lr 1e-4 --lora-rank 16 \
    --checkpoint checkpoints/needle2.pkl --out out_lora.pkl
needle build checkpoints/needle2.pkl --lora out_lora.pkl --out tuned.cact   # ~13 s
# serve tuned.cact with engine 2.0.0
```

## Measured cost (26 examples, 3 epochs, batch 8, CPU)

Wall clock 10m42s · peak training RSS not separately metered (JAX) · adapter .pkl per weight group
A/B f32 · export 12.8 s → 13.74 MB .cact.

**GPU path (WSL2, VERIFIED 2026-08-12):** same 26-example epoch in **62 s** vs 295 s Windows CPU
(~4.7×). JAX 0.11.0 `jax[cuda12]` in a WSL2 venv sees `CudaDevice(0)` (RTX 5070). All losses
finite. Use WSL2 for the dataset ladder. Record: `docs/foundry/NEEDLE_COMPUTE_PATH.json`.

## Dataset-size policy (§18)

26 examples is a *pipeline probe*, not a training set. Real specialists start at the 250/500/1000/2000/4000
learning-curve ladder and stop when validation gain flattens. `foundry/dataset.py` enforces
provenance, dedupe, and cluster-safe partitioning on every build.

## Failure responses already encoded in the belief ledger

- loss NaN at any step → check f32 patch first (belief `needle.finetune.f32_fix`)
- arguments contain schema keys (`required`, `minimum`) → wrong dialect (belief `needle.schema_dialect_native`)
- `needle_load rc=-1` → container/engine pairing (belief `needle.container_pairing`)
