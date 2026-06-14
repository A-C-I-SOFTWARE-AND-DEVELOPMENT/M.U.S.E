# M.U.S.E Technology Disposition Matrix

This records the **architectural disposition** of the external technologies
evaluated for M.U.S.E — what is adopted, what is reached differently, and what is
deliberately *not* adopted — mapped against the repo's real, local-first
architecture.

> **Scope honesty.** M.U.S.E is a local-first Python agent that runs on
> infrastructure the owner controls (a VPS, a laptop, a GPU box, or Termux on a
> phone) and is model/provider-agnostic. Several technologies in the source
> evaluation are Google-Cloud-specific managed services or rest on **unverified
> vendor specifications**; those are marked **N-A** or flagged inline. Adopting
> them would require owner-gated cloud credentials and spend, and in some cases
> describes hardware whose claimed specs could not be confirmed from primary
> sources. This document does not fabricate or wire any such service.

**Legend:** **INCLUDE** = already in the repo / adopted · **MIGRATE** = reachable
via existing config or a small adapter, no new managed service ·
**DISCARD** = deprecated or redundant, do not adopt · **N-A** = out of scope for a
local-first agent (recorded for completeness).

## AI & model platforms

| Technology | Disposition | Rationale & repo evidence |
|---|---|---|
| Google Gemini (AI Studio API + OAuth) | **INCLUDE** | Already a first-class provider: [`plugins/model-providers/gemini/`](../../plugins/model-providers/gemini/) (API-key `gemini` + OAuth `google-gemini-cli`). Routed via [`providers/__init__.py`](../../providers/__init__.py). |
| Gemini image generation | **INCLUDE** | Real backend in [`plugins/image_gen/`](../../plugins/image_gen/) alongside OpenAI, xAI, FAL. |
| Vertex AI / "Gemini Enterprise Agent Platform" | **N-A** | Google models are reached today via AI Studio API key / OAuth, **not** the Vertex API. No Vertex dependency exists or is needed for a local-first agent. |
| Legacy AI Platform (ML Engine: Training / Prediction / Data Labeling) | **DISCARD** | Deprecated by the vendor (sunset early 2025). M.U.S.E never depended on it; there is nothing to migrate. |
| "Custom Muse MGT" image generator (masked generative transformer) | **DISCARD** | Redundant. M.U.S.E already ships a multi-provider image/video stack (see below). The cited latency/throughput figures are **unverified vendor claims**. See [`decisions/visual-synthesis-disposition.md`](decisions/visual-synthesis-disposition.md). |
| Chrome Built-in AI / Gemini Nano (on-device) | **N-A** | Browser/edge runtime, not the Python agent. The real on-device story for M.U.S.E is the **local `llama.cpp`** provider path. Could be a future edge option; not adopted now. |
| AI Hypercomputer / TPU v6e / "TPU v8 Zebrafish/Sunfish" / Managed Lustre | **N-A** | Managed Google Cloud HPC. M.U.S.E is hardware-agnostic and runs on owner infra. The **"TPU v8 Zebrafish/Sunfish" hardware specs in the source are unverified** and are not relied upon. |
| Vertical agents (Automotive / Contact Center / Document AI / Food Ordering) | **N-A** | Domain-specific managed agents outside M.U.S.E's scope. M.U.S.E's own orchestrator + worker profiles cover specialist routing locally. |

## Visual synthesis (already real)

| Capability | Disposition | Repo evidence |
|---|---|---|
| Image generation | **INCLUDE** | [`plugins/image_gen/`](../../plugins/image_gen/) — OpenAI `gpt-image-2`, Google Gemini, xAI `grok-imagine`, and FAL (flux-2, nano-banana-pro, recraft, ideogram, qwen-image, …). |
| Video generation | **INCLUDE** | [`plugins/video_gen/`](../../plugins/video_gen/) — xAI `grok-imagine-video` and FAL (Veo 3.1, Kling v3 4K, Pixverse v6, Seedance 2.0, LTX). |
| Vision analysis | **INCLUDE** | `vision_analyze` / `video_analyze` tools registered in [`toolsets.py`](../../toolsets.py). |

The disposition for visual synthesis is to **keep and extend the existing
multi-provider stack**, not to build a bespoke transformer. The provider
abstraction means new backends (including any future masked-generative model) are
added as plugins without touching the agent core.

## Web3 / blockchain (already real)

| Technology | Disposition | Rationale & repo evidence |
|---|---|---|
| On-chain read skills | **INCLUDE** | [`optional-skills/blockchain/`](../../optional-skills/blockchain/): **Solana** (portfolio, tokens, NFTs, whale detection), **EVM** across 8 chains (Ethereum, BNB, Base, Arbitrum, Polygon, Optimism, Avalanche, zkSync; ENS, gas, contract/tx decode), **Hyperliquid** (read-only perps/spot). Stdlib-only, read-only (no signing). |
| Google Blockchain Node Engine / Blockchain RPC | **DISCARD** | Vendor-deprecated (Dec 2026). M.U.S.E never hosted nodes, so there is nothing to tear down. |
| QuickNode (or any managed RPC) | **MIGRATE (config, not code)** | The existing EVM/Solana skills accept a **configurable RPC endpoint via env** (e.g. `SOLANA_RPC_URL`). Pointing that at a QuickNode (or any) endpoint is a config change, not new code or a new managed dependency. |
| BigQuery blockchain analytics / Validator Manager | **N-A** | Managed Google Cloud analytics/validator services; out of scope for the local agent. Owner-gated (spend) if ever pursued. |

## Peripheral

| Technology | Disposition | Rationale & repo evidence |
|---|---|---|
| Android domain-layer architecture | **INCLUDE** | The companion app at [`apps/android/`](../../apps/android/) already separates UI / domain / data concerns. |
| API for Domain Connect (DNS) | **N-A** | `dns_change` is an owner-gated action; no automated DNS provisioning is wired, by design. |
| AMP for Email | **N-A** | Interactive-email surface not part of the agent; gateway Email is a plain messaging surface. |

## Why this matters

The source evaluation's instinct is right on two points the repo already honors:
**discard deprecated stacks** (legacy AI Platform, Google-hosted blockchain
nodes) and **stay provider-agnostic**. Where it overreaches — fabricated hardware
tiers, a redundant bespoke image model, managed-cloud lock-in — M.U.S.E's
local-first, plugin-based design is the stronger path: every capability above is
either already present or reachable by configuration, with no owner-gated cloud
spend required to keep the lights on.

## See also

- [MUSE_COMPONENT_REGISTRY.md](MUSE_COMPONENT_REGISTRY.md) — the components these map onto.
- [decisions/visual-synthesis-disposition.md](decisions/visual-synthesis-disposition.md) — the visual-synthesis decision in full.
- [`../../AGENTS.md`](../../AGENTS.md) — model providers and how to add one.
