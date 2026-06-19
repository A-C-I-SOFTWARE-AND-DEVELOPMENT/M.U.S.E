# Template Fast Path — Phase Reports

Honest, measured results per phase for the Cluster-Based Token Template Fast Path
(`muse_TEMPLATES`). Numbers are labeled **MEASURED** (run in the environment named)
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

## Phase 1 — Shared cluster infrastructure

**MEASURED (container, hashed-ngram backend `hashed-ngram-d256-s0`):** fitted on
the 24 unique train prompts of the Phase-0 corpus, `k = round(sqrt(24)) = 5`,
seed 0. Cluster→domain alignment is exact (no mixed cluster except
safety+reasoning sharing one cluster at k=5):

| cluster | domains (train members) |
|---|---|
| 0 | code_generation ×4 |
| 1 | software_development ×4 |
| 2 | code_editing ×4 |
| 3 | safety ×4 + reasoning ×4 |
| 4 | code_review ×4 |

**Confidence calibration (deviation, intent kept):** the spec's plain
normalized-inverse-distance softmax compresses confidence to ≈1/k (measured
0.26–0.37 in-domain vs 0.21 gibberish — τ=0.75 would gate *everything* out).
Replaced with a radius-calibrated inverse distance
`conf = r/(r + max(d−r, 0))` (r = fitted cluster radius): still a normalized
inverse centroid distance in (0,1], but τ=0.75 now means d ≤ 4r/3. Measured:
train prompts mean 0.981 (min 0.880); unseen held-out prompts mean 0.846
(5/6 ≥ 0.75); gibberish 0.607 / off-topic 0.641 — correctly below the gate.

- MiniLM backend present but **unusable here** (HF blocked) — `resolve_backend("auto")`
  falls back to the hashed backend; the model artifact records the backend name and
  `assign` fail-closes on backend mismatch.
- Model artifact committed at `hermes_cli/jarvis_prime/templates/model/`
  (`centroids.npz` + `meta.json`, corpus hash recorded).

**Done-when:** ≥3 coherent clusters with visible confidence separation — met (5
coherent clusters; ≥0.2 separation between in-domain and off-topic). 11 unit
tests green. **Rollback:** delete `clusters.py` + `templates/model/` (nothing
else imports them yet).

## Phase 2 — Template mining

**MEASURED (container):** mined from the 24 verifier-PASSED train records only
(failed candidates are filtered before alignment; test
`test_failed_outputs_never_reach_templates` proves a poisoned failed output
cannot leak into any scaffold or source-hash list). All 5 clusters emitted
versioned template pairs at `hermes_cli/jarvis_prime/templates/<cluster_id>/`:

| cluster | domain(s) | mode | coverage | slots | support |
|---|---|---|---|---|---|
| 0 | code_generation | soft | 0.521 | 4 | 4 |
| 1 | software_development | soft | 0.330 | 5 | 4 |
| 2 | code_editing | soft | 0.421 | 4 | 4 |
| 3 | safety + reasoning | soft | 0.394 | 5 | 8 |
| 4 | code_review | **hard** | 0.589 | 4 | 4 |

- **GBNF validation:** all 5 scaffolds compile under llama.cpp's grammar engine
  and **all 24 source exemplars re-validate** through the real
  `test-gbnf-validator` binary (24 valid / 0 invalid). Each grammar is also
  self-checked in-process via a regex twin before emit.
- **Mode rule:** `hard` requires coverage ≥ 0.5, ≤ 4 slots, AND every slot
  single-line/number constrained (no free-text gaps) — reasoning is never
  hard-forced. Cluster 4's scaffold pins the full function shape
  (`# Reasoning: it returns <line>— …\ndef <line>(<line>):\n    return <line>`).
- **Reasoning-first ordering:** every scaffold and prefix places the
  `# Reasoning:` section before the answer code (test-enforced).
- **Deviation (rule 7):** the spec's min_support=10 would skip every fixture
  cluster (max support here is 8); the committed registry was mined with
  `min_support=3`, recorded here and in each `meta.json`'s `support` field. The
  module default remains `SPEC_MIN_SUPPORT = 10` for live mining.
- LCS post-pass merges `slot " " slot` fragmentation into single typed slots
  (raw LCS produced 9–17 word-sized slots per scaffold; merged: 4–5).

**Done-when:** ≥1 structural cluster with a versioned, compiling template pair —
met (cluster 4, hard mode, plus 4 soft templates). 9 unit tests green.
**Rollback:** delete `templates/<cluster_id>/` dirs; mining is fully offline.

## Phase 3 — Fast-path integration (flag-guarded)

**Flag-off byte-identity (MEASURED, container):** with `muse_TEMPLATES`
unset/`""`/`"0"`/`"false"`/`"off"`/`"no"`, `build_gemma_runner` returns the
**same runner object** the invoke factory produced (object identity asserted),
never imports `template_fastpath`, and a fixed prompt set produces identical
output hashes. All 15 pre-existing gemma-runner tests pass unchanged.

**Architecture (deviation noted in Phase 0):** the fast path wraps the Ollama
runner and talks to llama-server's native `/completion` API via the new stdlib
`llama_client.py` (`grammar` + `id_slot` + `cache_prompt`), activated only when
`muse_TEMPLATES` is truthy AND `muse_TEMPLATES_SERVER` points at a healthy
server AND the cluster-model/template artifacts load. Anything missing →
the unchanged base runner. Confidence gate τ=0.75 (`muse_TEMPLATES_TAU`),
stable slot mapping `cluster_id % n_slots`, hard = single constrained pass,
soft = two-stage reason-then-format (reasoning never grammar-forced), all
errors → flywheel-logged fallback (repeated errors → one improvement-queue
entry). Speculative decoding is server-launch config
(`SpecDecodeConfig.to_server_args()`, current `--spec-draft-*` spellings).

**MEASURED (synthetic model, container) — mechanical fast-path probe** against
a real llama-server (`--parallel 4 --slot-save-path --cache-reuse 256`),
committed cluster model + an ASCII-slot probe scaffold:

| check | result |
|---|---|
| `build_fastpath` against live server | OK (health, model, templates loaded) |
| plan: cluster 4 (code_review prompt), mode hard, conf 1.0, slot 0 | OK |
| prompt-cache: `tokens_cached` on templated runs | **1023** (prefix reuse working) |
| grammar conformance: output starts with forced literal | **True** |
| error path: server 500 → silent fallback to base runner | OK (verified earlier probe) |

**Synthetic-model artifacts (do not extrapolate):** the random byte-vocab
model can emit invalid UTF-8, which this llama.cpp build's grammar engine /
response encoder rejects with HTTP 500 on free-text slots (`[^\n]+`) and free
generation. Real BPE Gemma cannot produce invalid UTF-8 — the committed
scaffolds were validated separately via `test-gbnf-validator` (24/24
exemplars). Latency speedup and parse-rate vs baseline are therefore
**DEFERRED** → `scripts/templates_fastpath/phase3_bench.sh` (laptop, real
Gemma; gate: ≥20% latency win on ≥1 templated cluster AND parse rate ≥
baseline).

**Done-when (adapted):** flag-off byte-identical — MET (test-enforced);
mechanical fast path proven against stub + real server — MET; ≥20% latency
gate — DEFERRED to the owner script (no real model reachable here; spec rule 7
deviation). 28 new unit tests green. **Rollback:** `muse_TEMPLATES=0`
(instant) or revert the phase-3 commit (the only one touching an existing
file: the flag guard at the tail of `build_gemma_runner`).

## Phase 4 — Ratchet verification (the adoption gate)

**Harness:** `bench/ratchet_run.py` — scores challenger (template-ON) vs
champion (template-OFF) through the EXISTING machinery only:
`research_fabric.benchmarks.run_suite` (executable verifiers; embedded fixture
candidates stripped so the live runner is what's scored) →
`validators.evaluate_ratchet` with catalog defaults untouched (0.80 floor,
0.05 composite margin, 0.55 evaluator win-rate, held-out wall, safety
non-regression). Per-task head-to-head win-rate (ties = 0.5) feeds the
evaluator gate; latency is captured as a co-metric. PASS →
`ChampionStore.freeze` (SnapshotStore row + GuardrailLedger record, git-sha
rollback handle, asserted present). FAIL or `--mechanical-only` → exactly one
structured `improvement_queue.jsonl` entry, then STOP.

**Test evidence (container, 5 tests green):** pass-path freezes with the
provided sha visible in BOTH stores; fail-path queues exactly one entry and
freezes nothing; `mechanical_only` never freezes even on a passing verdict; an
existing champion forces the composite margin (no free re-promotion).

**MEASURED (container) — honest mechanical run:**
`python -m hermes_cli.jarvis_prime.bench.ratchet_run --mechanical-only
--rollback-handle b8273aa (phase-4 commit)` with the no-model stub runner produced verdict
**REJECTED** (all domains 0.0 < 0.80 floor; win-rate 0.500 < 0.55 — exactly
right for a stub) and queued improvement entry **`a6b08522b47e`**
(`kind=templates.ratchet`) to `$HERMES_HOME/flywheel/improvement_queue.jsonl`.
No champion was frozen; `muse_TEMPLATES` remains off. The **live verdict** on
real Gemma is produced by `scripts/templates_fastpath/phase4_ratchet.sh`.

**Outcome (one of the two allowed):** clean rejection/deferral with a queued
structured entry. No promotion was recorded — and none may be implied.

### OWNER-GATED PROPOSAL (prepared, NOT applied)

> **Proposal:** after `phase4_ratchet.sh` produces a PASS verdict and a frozen
> champion on the owner's hardware, flip the default of `muse_TEMPLATES` from
> `0` to `1` (templates on by default for the Gemma curator lane).
> **This changes default runtime behavior and is therefore owner-gated.** It
> will be applied only after the owner replies exactly:
> `Yes, with authorization.`
> Rollback if approved and later regretted: set `muse_TEMPLATES=0` (instant)
> and/or `git revert` the flip commit; the frozen champion's
> `rollback_handle` records the pre-promotion sha.

## Phase 5 — Diffusion experimental lane (isolated, laptop only)

**MEASURED (container):** llama.cpp's `llama-diffusion-cli` target **builds**
from the same source checkout (build 1593d56) and exposes exactly the spec's
flags (`--diffusion-steps`, `--diffusion-algorithm`,
`--diffusion-block-length`, `-ub`). The probe harness
(`bench/diffusion_lane.py`) sweeps steps {64, 128, 256}, uses the same
Phase-4 verifier corpus prompts and a latency co-metric, and emits the
comparison table via `comparison_table()`.

**Isolation (test-enforced):** no module outside `bench/` imports the lane;
it never touches `gemma_runner.py`; missing binary/model degrades to
`{"available": False}`.

**Deviations (rule 7):**
- Dream-7B / LLaDA-8B GGUFs are **unobtainable in this container** (HF
  blocked, multi-GB) — the quality/latency comparison is **DEFERRED** to
  `scripts/templates_fastpath/phase5_diffusion.sh` on the laptop. The
  expectation to confirm/refute there: diffusion slower than the AR fast path
  on CPU at batch size 1.
- `llama-diffusion-cli` exposes no token-clamping API, so "clamped-template
  infilling" is realized as an explicit blank-filling skeleton prompt
  (`build_infill_prompt`); true positional clamping would need a llama.cpp
  patch.

**Done-when (adapted):** comparison-table scaffolding + harness exist and are
tested (6 tests green); measured table DEFERRED with the owner script.
**Rollback:** delete `bench/diffusion_lane.py` + the script; nothing imports it.

## Phase 6 — Termux/aarch64 port

**Plan + tooling shipped; device numbers DEFERRED** (no aarch64 device in this
environment) → `scripts/templates_fastpath/phase6_termux.sh`, which on-device:

1. Builds llama.cpp natively (`pkg install cmake clang git python`,
   `-DGGML_NATIVE=ON`) if absent.
2. Installs numpy via `constraints-termux.txt`; **no torch/sentence-transformers
   on device** — the hashed embedding backend (Phase 1) is the designed-in
   Termux answer and the committed cluster model already uses it.
3. Fills the measured memory-budget table (target + draft + KV/slot ≤ device
   `MemAvailable`) and applies the rule: **if RAM-bound, drop speculative
   decoding FIRST** — grammar forcing + prompt-cache stay (they work everywhere
   llama.cpp runs).
4. Reruns the Phase-3 bench (same gate: ≥20% latency win, parse rate ≥
   baseline) against a 1–3B Gemma Q4 GGUF, 2 slots, c=2048, with
   `muse_TEMPLATES_DIR` honored for on-device template artifacts.

**Done-when (adapted):** on-device steps + budget-table tooling ready; the
"runs within RAM budget with measured speedup" check is produced by the script
on the phone. **Rollback:** `muse_TEMPLATES=0` on device (instant).
