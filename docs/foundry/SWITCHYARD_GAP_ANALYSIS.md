# SWITCHYARD GAP ANALYSIS

**Date:** 2026-08-12 · **Local source:** `C:\Users\Echer\Downloads\Switchyard-main` (extracted zip; upstream: NVIDIA/NeMo Switchyard, pre-alpha per its README)
**Comparator:** M.U.S.E. provider layer (`hermes_cli/auth.py`, `agent/auxiliary_client.py`, `plugins/model-providers/*`, `config/model-catalog.yaml`)

Classification legend: MUSE_ALREADY_BETTER / SWITCHYARD_BETTER / EQUIVALENT / COMPLEMENTARY / NOT_NEEDED / RISKY

| Switchyard capability | M.U.S.E. equivalent | Verdict | Evidence |
|---|---|---|---|
| OpenAI Chat ↔ Anthropic Messages ↔ OpenAI Responses protocol translation | Per-provider adapters + `api_mode` selection (`chat_completions`, `codex_responses`, Anthropic wire handled in client layer) | EQUIVALENT | auth.py PROVIDER_REGISTRY entries carry per-provider `inference_base_url` + api_mode plumbing; auxiliary_client resolves each |
| Multi-backend routing (random, classifier, stage) | Fusion router w/ ACT difficulty routing + MoE model router + aux-loss-free load balance (`agent/fusion_router.py`, `agent/fusion_model_router.py`) | MUSE_ALREADY_BETTER | M.U.S.E. routing is difficulty-aware and provider-health aware; Switchyard classifier routing is a subset |
| Prometheus metrics (requests, errors, latency, tokens, routing overhead) | plugins/observability + per-provider health + model_scorecard (`hermes_cli/jarvis_prime/model_scorecard.py`) | EQUIVALENT | different export format, same signals |
| Standalone Rust proxy process | none — M.U.S.E. routes in-process | COMPLEMENTARY | a sidecar proxy could front external CLIs (Claude Code/Codex) pointing at M.U.S.E. backends; not needed for Tier-0 (adds a network hop to a 14MB reflex call) |
| Typed, composable routing algorithms as a Rust library | routing policy is Python, embedded | COMPLEMENTARY | borrow the *concept* of typed stage-routing for the Foundry's escalation ladder; do not embed Rust |
| Tool-call representation in protocol types | native OpenAI tool schemas throughout | EQUIVALENT | — |
| A/B traffic splitting | fusion parallel rounds + scorecards | EQUIVALENT | — |
| Pre-alpha status, rapidly changing API | M.U.S.E. routing is production | RISKY | Switchyard README: "Experimental software. Not for production use." |

## Decision (§31)

**REJECT for runtime embedding; BORROW_CONCEPTS for the Foundry escalation ladder.**

Rationale: M.U.S.E.'s existing provider resolution covers every protocol Switchyard translates,
with difficulty/MoE routing Switchyard lacks. Embedding a pre-alpha Rust proxy in front of Tier-0
reflex calls would add latency and an uncontrolled trust surface (§33, §34) for zero measured gain.
The one concept worth porting is *signal-driven stage routing* — escalation triggered by measured
signals (confidence bucket, schema-validity, retrieval reachability) — which the Foundry runtime
implements natively in Python under AXIOM gating.

**What would invalidate this decision:** a measured scenario where external CLI agents (Codex/Claude
Code) must speak Anthropic/Responses wire against M.U.S.E.-managed local backends at volume — then
evaluate Switchyard as a *sidecar* for those agents only, never in the M.U.S.E.→Needle path.
