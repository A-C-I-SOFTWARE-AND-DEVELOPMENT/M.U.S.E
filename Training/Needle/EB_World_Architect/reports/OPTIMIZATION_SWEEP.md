# Rung 250 Optimization Sweep

Measured on 2026-08-13 with the pinned Needle 2 checkpoint, float32 LoRA path, WSL2 JAX CUDA device, and Cactus engine 2.0.0. Every run exported a distinct W2A8 `.cact` artifact and completed the required evaluation bundle without worker errors.

## Dataset variants

- Runs 001–004 used dataset hash `9d3c1f358f2ea5abfc9ff7210bb4117ac79259e31ad4beeb62f4eec944c2dcee`. Its rung-250 training split contained no `answers: []` examples, and its QA-250 pool contained no wrong-domain examples, so the QA wrong-domain rate for those runs has a zero-sized denominator and is not comparable.
- Runs 005–006 used corrected dataset hash `82a06c4523ea3f8b75700f9672cb3e5849c4de1ef1bc3e8bb4e984532e4e03e9`. The curriculum preserves the total 4,000-row distribution while moving an existing off-topic block into the first rung: 8 of 200 training rows and 10 of 250 QA rows now train and measure native no-call behavior.

## Measured candidates

| Run | Epochs | LR | Loss first → last | QA verdict | QA evidence | QA wrong-domain | QA critical | Holdout verdict | Holdout evidence | Holdout false-completion safety | Holdout wrong-domain | Holdout critical | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 001 | 1 | 0.0001 | 2.8482 → 2.6016 | 0.1360 | 0.9125 | N/A | 2 | 0.1975 | 0.99375 | 1.0000 | 0.3500 | 1 | FAILED |
| 002 | 3 | 0.0001 | 2.8677 → 2.0502 | 0.1640 | 0.3625 | N/A | 26 | 0.2925 | 0.5500 | 0.8375 | 0.3500 | 33 | FAILED |
| 003 | 2 | 0.0001 | 2.8855 → 2.3595 | 0.2680 | 0.7875 | N/A | 8 | 0.3125 | 0.7125 | 0.8500 | 0.3500 | 27 | FAILED |
| 004 | 3 | 0.00005 | 2.9320 → 2.5036 | 0.1680 | 0.8375 | N/A | 2 | 0.2375 | 0.8375 | 0.8750 | 0.5250 | 10 | FAILED |
| 005 | 3 | 0.00005 | 2.8633 → 2.5706 | 0.1600 | 0.9000 | 0.6000 | 4 | 0.1950 | 0.8125 | 0.8625 | 0.5750 | 12 | FAILED |
| 006 | 1 | 0.0001 | 2.9401 → 2.6339 | 0.0920 | 0.94444 | 0.2000 | 2 | 0.1725 | 0.9750 | 0.9875 | 0.3000 | 3 | FAILED |

## Outcome

Run 003 produced the highest verdict scores but was unsafe, with 27 critical holdout failures. On the corrected curriculum, run 006 was materially safer than run 005: early stopping reduced QA wrong-domain execution from 0.60 to 0.20 and holdout wrong-domain execution from 0.575 to 0.30 while reducing critical failures from 4/12 to 2/3 across QA/holdout.

Run 006 is the best corrected-curriculum safety candidate, but it remains below the strict accuracy thresholds and retains non-zero critical failures. Foundry therefore stopped at rung 250, did not train rung 500, and did not register or activate any candidate.

Evaluation now reuses a stock baseline only when both the serialized evaluation rows and stock model SHA-256 match a completed prior run. Run 006 reused run 005's verified 700-row stock baseline with explicit provenance and generated all 700 tuned predictions fresh.
