# MUSE Gap Analysis — State of the Art Push
**Date:** 2026-07-20
**Repo:** C:\Users\Echer\M.U.S.E (~730k LOC Python, 31,289 collectible tests)
**Goal:** Make MUSE state-of-the-art on all benchmarks, able to hire/create agents, run swarm loops.

---

## TL;DR

MUSE already has **~80% of the substrate** for a SOTA agent swarm: a hardened agent loop, 31k tests, a real swarm coordinator, a delegate_task chokepoint, an AoS council, an enterprise multi-leaf orchestrator, a research fabric with AlphaZero-style promotion gates, and free-model escalation scaffolding.

What's missing is **not more code** — it's **wiring, external benchmark runners, and the agent-creation/market layer**. The repo is in the "impressive infrastructure, not yet scored" state.

---

## 1. CURRENT STATE (what's actually here)

### 1.1 Core Agent Loop — SOLID
- `run_agent.py` — `AIAgent` class, ~12k LOC, sync conversation loop, 90 max iterations, full tool calling
- `cli.py` — `HermesCLI`, ~11k LOC, Rich + prompt_toolkit
- `model_tools.py` — tool orchestration, `discover_builtin_tools()`, `handle_function_call()`
- `tools/registry.py` — auto-discovery at import time
- **Verdict:** production-grade. Not the bottleneck.

### 1.2 Swarm / Delegation — REAL but STATIC
| Surface | File | What it does | Limitation |
|---|---|---|---|
| `delegate_task` tool | `tools/delegate_tool.py` (2,811 LOC) | Spawns isolated subagents via `AIAgent._dispatch_delegate_task` | Children are leaf-only; max_spawn_depth=1; no cross-process spawn |
| Swarm Coordinator | `hermes_cli/swarm/coordinator.py` (`run_swarm`) | Grainler decompose → lease claim → specialist build → parallel run → blackboard → ledger → self-update | Default executor is **PROMPT_ONLY** — materialises prompts but doesn't launch models |
| AoS Council | `hermes_cli/jarvis_prime/aos_council/dispatcher.py` | Static dispatch from hand-curated `registry.json` | Keyword-overlap scoring, not capability-driven; no reputation, no auction |
| Enterprise Orchestrator | `enterprise/council.py`, `enterprise/orchestrator.py` | Multi-leaf (Finance/HR/CS/OPS/Sales) + Judge + Monitor | Hand-coded leaf types; no dynamic leaf creation |
| Kanban plugin | `plugins/kanban/` | Multi-agent board dispatcher + worker | Job-shaped, not general-purpose |

**Verdict:** The swarm can *execute* a static plan. It cannot *invent* new agent types at runtime, hire based on capability, or bid on work.

### 1.3 Benchmark Infrastructure — PARTIAL
| Runner | Path | Status |
|---|---|---|
| mini_swe_runner | `mini_swe_runner.py` (737 LOC) | Present, single-task + batch JSONL, supports local/docker/modal envs |
| batch_runner | `batch_runner.py` (1,325 LOC) | Parallel batch with checkpointing + trajectory saving |
| bench_difficulty | `benchmarks/bench_difficulty.py` | Present |
| bench_lti | `benchmarks/bench_lti.py` | Present |
| bench_model_router | `benchmarks/bench_model_router.py` | Present |
| bench_studio_* | `benchmarks/bench_studio_*.py` (5 files) | Studio bundle/free/full/local |
| muse_eval | `tests/muse_eval/test_harness.py`, `test_jury.py` | Internal eval harness |
| research_fabric | `hermes_cli/jarvis_prime/research_fabric/` | AlphaZero-style promotion ratchet with `ABSOLUTE_FLOOR=0.80`, `EVAL_WIN_MARGIN=0.55`, `REQUIRED_DOMAINS` |
| SWE-bench verifier | `hermes_cli/jarvis_prime/research_fabric/verifier/swe.py` | Present |
| **MISSING:** GAIA, Terminal-Bench, Aider Polyglot, WebArena, OSWorld, SWE-bench Multimodal | — | **No runners** |

**Verdict:** Internal harness is rich. External SOTA benchmark coverage is ~20%.

### 1.4 Test Suite — HEALTHY
- **31,289 test cases collected, 0 collection errors**
- 1,698 test files, 86k LOC of tests
- Coverage: acp, agent, e2e, enterprise, gateway, hermes_cli, integration, jarvis_prime, muse_eval, muse_universe, plugins, providers, skills, stress
- **Verdict:** Excellent. This is a major asset.

### 1.5 Model Registry — COMPLETE (just finished)
- 112 models across 5 tiers
- 91 free models (18 Ollama local + 62 NVIDIA NIM + 10 Ollama cloud + 1 OpenRouter)
- 21 paid models for escalation
- **Verdict:** Done.

---

## 2. GAPS vs SOTA

| Capability | SOTA Reference | MUSE Status | Gap Size |
|---|---|---|---|
| **SWE-bench Verified score** | Claude Code ~72%, Aider ~65%, Devin ~53% | Runner present, **no recorded score** | Measurement only |
| **GAIA** (general agent) | H Company ~65%, OpenAI Deep Research ~67% | **No runner** | Runner + harness |
| **Terminal-Bench** | Claude Code ~50%, Codex ~48% | **No runner** | Runner + harness |
| **Aider Polyglot** (multi-language code edit) | Claude Sonnet 4.5 ~76% | **No runner** | Runner + harness |
| **WebArena / OSWorld** (browser/OS use) | Claude Computer Use ~22-30% | **No runner** (browser tools exist) | Runner + harness |
| **Runtime agent creation** | LangGraph, AutoGen | Sub-agents are pre-defined | **Core capability** |
| **Capability-based hiring** | Auction mechanisms in AutoGen, CrewAI | `registry.json` is hand-curated | **Core capability** |
| **Cross-process spawn** | Ray, Modal | Depth=1, leaf-only | **Core capability** |
| **Self-improvement loop** | AlphaZero, Voyager | research_fabric ratchet exists | Wiring + corpus |
| **Free-model swarm** | None published | 91 free models registered, escalation chain defined | **First-mover advantage** |

---

## 3. PRIORITIZED FIX LIST

### Phase 0 — Measurement (must come first)
*You can't beat a benchmark you haven't run.*

1. **Run SWE-bench Verified with `mini_swe_runner.py`** on a small subset (10-50 tasks) using `anthropic/claude-sonnet-4-6` → record baseline. **Effort: 1-2 hours.**
2. **Add GAIA runner** — single Python file, ~200 LOC, uses existing `AIAgent`. **Effort: 2-3 hours.**
3. **Add Terminal-Bench runner** — same pattern. **Effort: 2-3 hours.**
4. **Add Aider Polyglot runner** — reuse `mini_swe_runner` with multi-language prompts. **Effort: 2 hours.**
5. **Wire all runners into `hermes_cli/jarvis_prime/research_fabric/`** so every run updates the ratchet. **Effort: 1 hour.**

### Phase 1 — Swarm Activation
6. **Replace `PROMPT_ONLY` executor with real model executor** in `hermes_cli/swarm/coordinator.py` — pass an executor that calls `AIAgent` per grain. **Effort: 3-4 hours.**
7. **Lift `max_spawn_depth` to 3** and add a `orchestrator` role to delegate_task (already partially present). **Effort: 1 hour.**
8. **Build `agent_factory.py`** — runtime creation of new specialist agents from a capability spec (name, tools, model, prompt). Register in `aos_council/registry.json` programmatically. **Effort: 4-6 hours.**
9. **Build `agent_market.py`** — capability-based scoring (replace keyword overlap), simple auction (cost × quality × reputation), tie into `aos_council/dispatcher.py`. **Effort: 6-8 hours.**

### Phase 2 — Self-Improvement
10. **Wire research_fabric ratchet to every benchmark run** — challenger vs champion, EVAL_WIN_MARGIN=0.55 gate. **Effort: 2 hours.**
11. **Auto-apply reversible self-updates from swarm ledger** (already partially present in coordinator). **Effort: 2 hours.**
12. **Build corpus ingestion** — every benchmark trajectory becomes training data for the free models. **Effort: 4 hours.**

### Phase 3 — Free-Model SOTA Push (differentiator)
13. **Run SWE-bench with `nvidia/llama-3.3-70b-instruct` (free NIM)** → baseline free-model score. **Effort: 1 hour.**
14. **Tune escalation chain**: try free first, escalate to Claude Sonnet only when quality gate fails. Measure cost/task. **Effort: 2 hours.**
15. **Target: SWE-bench Verified ≥ 50% on free models, ≥ 70% with escalation.** This would be publishable.

---

## 4. EFFORT ESTIMATE

| Phase | Time | Outcome |
|---|---|---|
| Phase 0: Measurement | 8-11 hours | Baselines on 4 SOTA benchmarks |
| Phase 1: Swarm Activation | 14-19 hours | MUSE can hire, create, auction agents |
| Phase 2: Self-Improvement | 8 hours | Auto-ratchet, corpus flywheel |
| Phase 3: Free-Model SOTA | 5 hours | Publishable free-model benchmark score |
| **TOTAL** | **35-43 hours** | **SOTA-capable MUSE** |

---

## 5. RECOMMENDED FIRST MOVE

**Run one SWE-bench Verified task right now** with `mini_swe_runner.py` + Claude Sonnet 4.6 to prove the harness works end-to-end. That single data point unlocks everything else.

Then parallelize:
- Subagent A: GAIA runner
- Subagent B: Terminal-Bench runner
- Subagent C: Aider Polyglot runner
- Subagent D: Replace PROMPT_ONLY executor with real model executor

---

## 6. WHAT I'M NOT RECOMMENDING

- **Don't refactor `run_agent.py` or `cli.py`** — they're battle-tested, 31k tests depend on them.
- **Don't build a new orchestrator** — `aos_council` + `swarm/coordinator` + `enterprise/council` are already three; unify, don't multiply.
- **Don't chase WebArena/OSWorld yet** — browser use is the weakest SOTA area (22-30%); win code benchmarks first.

---

**Ready for your approval to execute.**
