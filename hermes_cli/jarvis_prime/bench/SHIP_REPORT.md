# SHIP REPORT — Cluster-Based Token Template Fast Path (`muse_TEMPLATES`)

Phases 0–6 implemented end-to-end on branch
`claude/cluster-token-template-fastpath-vbicqd`. Full per-phase evidence:
[`phase_reports.md`](phase_reports.md). **The flag is OFF by default and no
promotion was recorded** — adoption awaits the live ratchet run on the owner's
hardware (see Owner-gated proposals).

## 1. Measured-numbers table

Environment legend — **C** = this build container (4 cores, 15 GB, llama.cpp
`1593d56` built from source, synthetic 0.44 MiB random-weight GGUF only);
**L** = owner laptop (DEFERRED, script ready); **T** = Termux phone (DEFERRED,
script ready). No real Gemma model was reachable in C (no Ollama; Hugging Face
blocked by network policy).

| measurement | env | value | status |
|---|---|---|---|
| llama-bench pp512 (synthetic model) | C | 87 525 ± 1 114 tok/s | MEASURED (mechanical only) |
| llama-bench tg128 (synthetic model) | C | 7 496 ± 279 tok/s | MEASURED (mechanical only) |
| Prompt-cache reuse, same slot, shared prefix | C | req2 `prompt_n=1`, `tokens_cached=1428` | MEASURED — reuse works |
| Grammar forcing via `/completion` `grammar` | C | output cannot leave the grammar | MEASURED |
| Speculative-decoding flags (`--spec-draft-*`) | C | server starts + serves with draft | MEASURED (flag acceptance) |
| Fast path end-to-end vs live server | C | cluster 4, conf 1.0, `tokens_cached=1023`, forced-literal conformance ✓ | MEASURED (mechanical) |
| Cluster confidence separation (hashed backend) | C | train 0.981 / held-out 0.846 / off-topic ≈0.62 vs τ=0.75 | MEASURED |
| GBNF validation of mined scaffolds | C | 5/5 compile; 24/24 exemplars valid (`test-gbnf-validator`) | MEASURED |
| Real Gemma baseline tok/s + SWA cache probe (#21468) | L | — | DEFERRED → `phase0_baseline.sh` |
| Fast-path ≥20% latency gate + parse rate | L | — | DEFERRED → `phase3_bench.sh` |
| Live ratchet verdict (template-ON vs OFF) | L | — | DEFERRED → `phase4_ratchet.sh` |
| Diffusion (Dream-7B/LLaDA) vs AR fast path | L | — | DEFERRED → `phase5_diffusion.sh` (binary builds; flags verified in C) |
| Device memory budget + on-device speedup | T | — | DEFERRED → `phase6_termux.sh` |

## 2. Ratchet verdicts (with ledger references)

| run | verdict | reference |
|---|---|---|
| Container mechanical run (`--mechanical-only`, stub runner, rollback handle `b8273aa`) | **REJECTED** — all 6 domains 0.0 < 0.80 floor; held-out wall failed; win-rate 0.500 < 0.55 (correct for a no-model stub) | flywheel `improvement_queue.jsonl` entry **`a6b08522b47e`** (`kind=templates.ratchet`), `$HERMES_HOME/flywheel/` |
| Live run (real Gemma) | **PENDING** | will write SnapshotStore `champion_freeze` row + GuardrailLedger record via `ChampionStore.freeze` on PASS, or a queued entry on FAIL |

No champion was frozen. Thresholds in `research_fabric/catalog.py` were never
modified. Harness tests prove both store records exist on a pass-path freeze
and that `mechanical_only` can never freeze.

## 3. Deviations from the spec (rule 7 — intent kept)

1. **`gemma_runner.py` is Ollama-based, not llama.cpp.** The fast path wraps
   the Ollama runner and drives llama-server's native `/completion` API
   (new stdlib `llama_client.py`); Ollama exposes no grammar/slot/draft
   controls. Flag-guarded, fallback always the unchanged base runner.
2. **No flywheel event history** → corpus built from repo fixtures
   (sanctioned fallback), with PASS tags *earned* by executing every candidate
   through `score_algorithm_candidate` (30/30 good accepted, 0/30 bad).
3. **Confidence formula calibrated**: plain inverse-distance softmax compresses
   to ≈1/k, making τ=0.75 impossible; replaced with radius-normalized inverse
   distance (`conf = r/(r + max(d−r,0))`), measured separation preserved.
4. **`llama-gbnf-validator` renamed upstream** to `test-gbnf-validator`; the
   spec's `--draft-max` flags are now `--spec-draft-n-max` etc. (verified
   against `llama-server --help`, build `1593d56`).
5. **min_support:** spec's 10 would skip every fixture cluster; committed
   registry mined with `min_support=3` (module default stays 10 for live
   mining). Recorded per-cluster in `meta.json`.
6. **Split stratified per domain** (plain 20% hash split left whole domains
   without a held-out wall on a 30-task corpus).
7. **Synthetic-model artifact:** the random byte-vocab GGUF can emit invalid
   UTF-8, which the grammar engine 500s on — impossible for real BPE Gemma;
   mechanical grammar probe used ASCII-constrained slots, committed scaffolds
   validated separately (24/24).
8. **Diffusion clamping** approximated as blank-filling skeleton prompts;
   `llama-diffusion-cli` has no positional clamping API.
9. **Phase gates requiring real-model measurements** (Phase 3's ≥20% latency,
   Phase 4's live verdict, Phase 6's device numbers) are DEFERRED to
   ready-to-run owner scripts — per the owner's explicit choice of "full
   mechanical validation" for this container session.

## 4. Owner-gated proposals

1. **Flip `muse_TEMPLATES` default to `1`** — ONLY after
   `scripts/templates_fastpath/phase4_ratchet.sh` passes on owner hardware and
   freezes a champion. Prepared in `phase_reports.md` (Phase 4); not applied.
   **Status: owner authorization RECEIVED 2026-06-12** ("yes, with
   authorization."). Per the binding ratchet rule it was **not applied** — the
   only verdict on record is the container's mechanical REJECTED, and the
   ratchet (not the owner gate alone) is the adoption mechanism. The
   authorization is standing: on the first live PASS + frozen champion, the
   default flip may be applied without a further owner round-trip.
2. *(No other default-behavior changes exist; everything else is additive and
   flag-off-inert.)*

## 5. Rollback handle inventory

| scope | handle |
|---|---|
| Instant runtime kill-switch | `muse_TEMPLATES=0` (or unset) — returns to byte-identical champion behavior |
| Phase 0 (corpus, bench harness, heldout sets) | revert `834ce05` (additive) |
| Phase 1 (clusters.py + model artifact) | revert `fcd6006` (additive) |
| Phase 2 (mining + template registry) | revert `96b22e1` (additive; or delete `templates/<id>/`) |
| Phase 3 (fast path + the ONLY existing-file edit: `gemma_runner.py` flag guard) | revert `f1ef78e` |
| Phase 4 (ratchet harness) | revert `b8273aa` (additive) |
| Phase 5 (diffusion lane) | revert `a094786` (additive; nothing imports it) |
| Phase 6 (termux script) | revert `ad0b2b8` (additive) |
| Future live promotion | the frozen `Champion.rollback_handle` (git sha recorded at freeze time) |

## 6. Verification status (container)

- 47 new unit tests green (`tests/jarvis_prime/test_{bench_corpus,clusters,
  template_mining,llama_client,template_fastpath,gemma_runner_templates_flag,
  ratchet_run,diffusion_lane}.py`), plus all 15 pre-existing gemma-runner
  tests unchanged.
- `uv run ruff check .` clean; `uv run ty check` clean on every new module.
- Flag-off byte-identity: object-identity + no-import + output-hash tests.

**Handing back to the owner.** Next actions in order:
`phase0_baseline.sh` → `phase3_bench.sh` → `phase4_ratchet.sh` (laptop), then
`phase6_termux.sh` (phone), then — only on a frozen PASS — reply
`Yes, with authorization.` to the default-flip proposal.
