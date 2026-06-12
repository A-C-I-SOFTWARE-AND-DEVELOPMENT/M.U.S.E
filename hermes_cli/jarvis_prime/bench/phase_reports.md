# Template Fast Path — Phase Reports

Honest, measured results per phase for the Cluster-Based Token Template Fast Path
(`MUSE_TEMPLATES`). Numbers are labeled **MEASURED** (run in the environment named)
or **DEFERRED** (cannot be measured in this environment; ready-to-run owner script
listed). Expected numbers are never reported as measured.

## Phase 0 — Baseline benchmarking

**Environment:** remote Linux container, 4 physical cores, 15 GB RAM,
`ggml-org/llama.cpp` build `1593d56` compiled from source (Release, native).
**Constraint:** no Ollama install, no real Gemma GGUF present; huggingface.co
blocked by network policy (github.com/pypi.org allowed). All model-level numbers
below therefore use a **synthetic random-weight 0.44 MiB llama-arch GGUF**
(`bench/make_tiny_gguf.py`) — they validate *mechanics only* and say nothing
about real Gemma latency or quality.

### Deviations from the ship-plan spec (rule 7)

1. `gemma_runner.py` is **Ollama-based** (`ollama run <tag>`), not llama.cpp.
   Ollama exposes no GBNF/slot/draft controls, so the fast path (Phase 3) targets
   llama-server's native `/completion` API; the Ollama runner stays the fallback.
2. `llama-gbnf-validator` no longer exists as a target upstream; the binary is now
   `test-gbnf-validator` (built and used).
3. Speculative-decoding flags are now `--spec-draft-model/-md`,
   `--spec-draft-n-max`, `--spec-draft-n-min`, `--spec-draft-p-min` (the spec's
   `--draft-max` spelling is gone).
4. `~/.hermes/flywheel/events.jsonl` contained no usable (task, output, verdict)
   triples (file absent) — far below the 50-per-domain bar — so the corpus uses the
   spec's sanctioned fallback: repo fixtures (`bench/fixtures/algorithm_suite.jsonl`,
   30 tasks × {good, bad} candidates across the six REQUIRED_DOMAINS). Every PASS
   tag is mechanically earned by executing the candidate through
   `score_algorithm_candidate` (verified: 30/30 good accepted, 0/30 bad accepted).

### MEASURED (synthetic model, container): llama-bench

| model | size | backend | threads | test | tok/s |
|---|---|---|---|---|---|
| muse-tiny (llama, all F32, synthetic) | 0.44 MiB | CPU | 4 | pp512 | 87525.30 ± 1113.55 |
| muse-tiny (llama, all F32, synthetic) | 0.44 MiB | CPU | 4 | tg128 | 7496.20 ± 279.41 |

(Real Gemma rows: **DEFERRED** → `scripts/templates_fastpath/phase0_baseline.sh`.)

### MEASURED (synthetic model, container): prompt-cache probe

`llama-server -m muse-tiny.gguf -c 4096 -np 2 --slot-save-path /tmp/kv
--cache-reuse 256`, two requests sharing a long prefix on `id_slot: 0` with
`cache_prompt: true`:

| request | prompt_n (new tokens prefilled) | tokens_cached |
|---|---|---|
| 1 (cold) | full prefix | 0 |
| 2 (same slot, same prefix) | **1** | **1428** |

Prefix-cache reuse works mechanically on this build. The Gemma-SWA cache-reuse bug
(llama.cpp #21468) **cannot be probed without a real Gemma GGUF** — the owner
script reruns this probe on the real model and records whether `--swa-full` is
needed; if reuse fails there, Phase 3 leans on grammar + speculative decoding.

### MEASURED (synthetic model, container): grammar forcing

A `{"verdict": "allow"|"deny"}` GBNF passed via `grammar` forced the random-weight
model to emit only grammar-legal bytes (it cannot produce anything else) —
token-level masking confirmed end-to-end through `/completion`.

### MEASURED (container): speculative-decoding flag acceptance

`llama-server -m muse-tiny.gguf -md muse-tiny-draft.gguf --spec-draft-n-max 4`
starts and serves (`/health` ok). Draft acceptance-rate/timings fields are not in
the `/completion` `timings` object on this build (keys: `cache_n, prompt_n,
prompt_ms, predicted_n, predicted_ms, …`); acceptance rate must be read from
server logs/metrics. Speedup measurement: **DEFERRED** (needs real target+draft pair).

### Held-out eval sets (committed)

`bench/corpus.py` → `research_fabric/heldout/<domain>.jsonl`, stratified 20%
per domain by `sha256(seed:base_task_id)` (pass/fail siblings never split):
8 train / 2 held-out records per domain × 6 domains. Corpus content hash:
`ac0e5e8b3fef78b171722e1c0ff581fbf80201265045612e5312451ec99d8861`.

### Done-when check

- [x] Baseline tok/s table exists (synthetic MEASURED; real Gemma DEFERRED with script)
- [x] Cache-probe results recorded (mechanical PASS; Gemma-SWA probe DEFERRED)
- [x] Held-out sets exist per domain and are committed
- [x] Fallback corpus provenance stated (fixtures, verifier-earned tags)

**Rollback:** none needed (read-only + additive files).
