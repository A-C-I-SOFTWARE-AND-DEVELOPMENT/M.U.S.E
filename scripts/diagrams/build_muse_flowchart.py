#!/usr/bin/env python3
"""Generate the M.U.S.E architecture flow-chart poster as a single HTML page.

The HTML is rendered to a one-page vector PDF (Playwright/Chromium) so it stays
crisp at any zoom — far beyond 4K. The poster is purely conceptual: it describes
*what each part of the repository does*, with no filenames and no source code.

Data model: PLANES (horizontal bands, top -> bottom flow) -> CARDS (components).
Each card carries a title, a plain-English description and optional tag chips.
"""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Card:
    title: str
    desc: str
    tags: list[str] = field(default_factory=list)
    gate: bool = False  # owner-gated component badge


@dataclass
class Plane:
    num: str
    title: str
    subtitle: str
    accent: str  # primary hue
    accent2: str  # secondary hue (for gradient)
    cards: list[Card]
    strip: list[str] | None = None  # an inline flow strip (chips with arrows)
    strip_label: str | None = None


PLANES: list[Plane] = [
    Plane(
        "01",
        "Surfaces",
        "Where the owner talks to MUSE — one mind, many surfaces",
        "#36e6f0",
        "#2f8bff",
        [
            Card(
                "CLI · REPL",
                "The interactive command center and chat shell — config, tool invocation, skill loading, and direct control of the orchestrator from a terminal.",
                ["chat", "config", "skills"],
            ),
            Card(
                "Terminal UI",
                "A full-screen terminal cockpit with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and live streaming of tool output, backed by a session RPC server.",
                ["streaming", "slash cmds"],
            ),
            Card(
                "Messaging Gateway",
                "One process that bridges 20+ chat platforms into Hermes: session routing, owner-approval cards, live streaming, voice-memo transcription and cross-platform conversation continuity.",
                ["multi-platform", "approvals"],
                gate=True,
            ),
            Card(
                "Android Cockpit",
                "A native mobile app: streaming chat, on-device voice intake, job control, lockscreen-style owner approvals, a living avatar, evidence/memory/graph views and an emergency stop — no provider keys on the phone.",
                ["voice", "approvals"],
                gate=True,
            ),
            Card(
                "Desktop Cockpit",
                "A native desktop app — Chat, Jobs, Approvals, Autonomy, Observatory and Settings — that auto-manages a local gateway, speaks the same protocol as mobile, and holds no keys.",
                ["tauri", "observatory"],
                gate=True,
            ),
            Card(
                "Nexus PWA",
                "A mobile-first command console: a 32-capability registry across seven planes, a draggable octagon steering vector, a neural observatory, a live repo mirror and an offline zero-server mode.",
                ["pwa", "steering"],
            ),
            Card(
                "Synapse (UE5)",
                "A real-time game-engine scaffold that visualises live system state — pipeline, nodes and gates — over the frozen cockpit wire contract.",
                ["3D viz"],
            ),
            Card(
                "ACP Adapter",
                "An Agent Client Protocol bridge that exposes MUSE to external editors: session fork / resume / load, event streaming and an OpenAI-compatible surface.",
                ["editor bridge"],
            ),
            Card(
                "Voice-first · Driving Mode",
                "Push-to-talk and continuous capture that turn speech into job intake with spoken confirmation; raw audio is never persisted and driving mode confirms before any action.",
                ["push-to-talk"],
                gate=True,
            ),
            Card(
                "Web Dashboard",
                "A browser cockpit served by the runtime: agent status, dynamic configuration, API-key management and a playground.",
                ["status", "config"],
            ),
        ],
        strip=[
            "Telegram",
            "Discord",
            "Slack",
            "WhatsApp",
            "Signal",
            "Email",
            "Matrix",
            "Teams",
            "LINE",
            "Google Chat",
            "Home Assistant",
            "iMessage",
            "SMS",
            "IRC",
            "SimpleX",
            "ntfy",
            "Feishu",
            "DingTalk",
            "WeChat / WeCom",
            "QQ",
            "Yuanbao",
            "Webhook",
        ],
        strip_label="Gateway platform adapters",
    ),
    Plane(
        "02",
        "Command Center · Operating Layer",
        "Hermes runs the loop; the MUSE operating layer gives it modes, persona and bounded context",
        "#33d6c4",
        "#36e6f0",
        [
            Card(
                "Core Agent Loop",
                "The model–tool loop every surface shares: tool dispatch, toolset resolution and error recovery — the single engine behind the runtime.",
                ["tool loop"],
            ),
            Card(
                "MUSE Operating Runtime",
                "The apex operating layer: six modes — Companion, Strategy, Critic, Operator, Builder and Mobile Voice — runtime persona injection, the routing hierarchy and the entry into cognition.",
                ["six modes", "routing"],
                gate=True,
            ),
            Card(
                "Intent & Mode Classifier",
                "Reads keyword, surface and risk signals to pick a mode with a confidence and a reason — deterministic and offline; the runtime can override.",
                ["deterministic"],
            ),
            Card(
                "Persona & Voice Identity",
                "The branded MUSE identity — glyph, palette, six response-format templates and a locale-aware speech profile — as one serializable source of truth.",
                ["branding"],
            ),
            Card(
                "Plugin Loader",
                "Auto-discovers tools behind an opt-in allowlist, gates them by required environment, and registers their schemas so the default surface never grows silently.",
                ["opt-in", "schemas"],
            ),
            Card(
                "TokenJuice Context Compiler",
                "A deterministic, token-bounded context packer that carries provenance, screens secrets and never truncates mid-source — separating constant (cache-friendly) from dynamic context.",
                ["token-bounded", "secret screen"],
            ),
        ],
    ),
    Plane(
        "03",
        "Governance · The Safety Spine",
        "Owner control by construction — nothing risky executes without authorization",
        "#ff5a7a",
        "#ff8f3f",
        [
            Card(
                "Owner Authorization",
                "The canonical owner-gated action set; high-impact actions defer until the owner replies with an exact phrase plus a one-time, nonce-bound challenge — so a replayed approval can never act.",
                ["exact phrase", "nonce"],
                gate=True,
            ),
            Card(
                "Work Packet Schema",
                "Bounded coding intent — mission, risk class, allowed/forbidden files, acceptance criteria, verification plan, builder/reviewer and owner gates. It describes scope; it never executes.",
                ["RC0–RC4", "bounded"],
            ),
            Card(
                "System Contract",
                "A pre-prompt behavioural floor, seen before any prompt, that fuses persona, Constitution and gates into one ordered preamble with a branding guard; injection is opt-in.",
                ["pre-prompt"],
            ),
            Card(
                "Constitution & Self-Audit",
                "A versioned behavioural rubric scored across seven dimensions, with a capability-band wall and attestation plus reward-hacking / Goodhart detection.",
                ["rubric", "capability wall"],
            ),
            Card(
                "Behavioral Risk Classifier",
                "Flags privilege escalation, destructive cleanup or workarounds, scope expansion and reward hacking — degrading worker trust and excluding tainted traces from learning.",
                ["risk patterns"],
            ),
            Card(
                "Goal Boundary Layer",
                "Mandatory brakes on every loop: objective, allowed/forbidden actions, stop conditions and iteration/cost ceilings — it refuses to run a loop with no stop condition.",
                ["loop brakes"],
            ),
            Card(
                "Guardrail Evidence Ledger",
                "Content-addressed evidence in a hash-chained, append-only log — any edit breaks the chain — with opportunistic cryptographic signing; it never silently repairs.",
                ["hash-chained"],
            ),
            Card(
                "Decision Ledger",
                "A tamper-evident, append-only record of every decision, routing choice, gate summary and proposal — rebuildable and auditable end to end.",
                ["append-only"],
            ),
            Card(
                "Emergency Stop · Monitors · Owner Brief",
                "An un-gated killswitch, fail-visible read-only monitors that track blind spots, and a daily under-one-minute owner brief with a coverage attestation.",
                ["killswitch", "fail-visible"],
            ),
            Card(
                "Autonomy Charter & Hard Wall",
                "Bounded, scoped, revocable autonomy — while a permanent hard wall keeps the safety-critical core (gates, owner-auth, registry, routing, verifier, Constitution) owner-gated forever.",
                ["bounded autonomy"],
                gate=True,
            ),
        ],
        strip=[
            "Planning",
            "Build",
            "Review",
            "Test",
            "Security",
            "Release",
            "Owner Approval",
            "Rollback",
        ],
        strip_label="The eight verification gates — each emits a captured evidence artifact in strict mode",
    ),
    Plane(
        "04",
        "Orchestration · Goal → PR",
        "One goal becomes a validated task graph, then a pull request — every decision audited",
        "#a06bff",
        "#6b8bff",
        [
            Card(
                "Goal-to-PR Orchestrator",
                "Decomposes a single goal into a validated task graph and drives the job lifecycle locally, rebuildable from its own event log.",
                ["task DAG", "local-first"],
                gate=True,
            ),
            Card(
                "Worker Profiles & Routing",
                "Detects builder, reviewer and specialist roles, routes each task to a profile and runs workers in parallel, logging the routing in the ledger.",
                ["profiles", "parallel"],
                gate=True,
            ),
            Card(
                "Swarm · Grainler Parallel",
                "Partitions a goal into non-overlapping, collision-proof file-domain grains — each its own specialised model in an isolated worktree, dated and ledgered.",
                ["disjoint grains", "worktrees"],
            ),
            Card(
                "Navigator · Repo Index · Localizer",
                "Builds a symbol graph, traces dependencies and ranks edit sites, mapping a natural-language issue to focused files before a coding worker is dispatched.",
                ["symbol graph"],
            ),
            Card(
                "Remote Worker Bridge",
                "Executes only allowlisted commands inside scoped repo roots, only after approval — writing structured artifacts and a status manifest back to a shared workspace.",
                ["allowlisted", "scoped"],
            ),
            Card(
                "Cron Scheduler",
                "Runs scheduled, unattended jobs through the same gates and prompt-injection scanner as interactive ones, delivering results to any platform.",
                ["unattended"],
                gate=True,
            ),
        ],
        strip=["Job", "Worker", "Model routing", "Validation gate", "Decision ledger"],
        strip_label="The five orchestration primitives",
    ),
    Plane(
        "05",
        "Cognition Plane",
        "Provenance-first memory and agentic retrieval — memory cites its sources; it is never the source of truth",
        "#2fd07a",
        "#36e6c4",
        [
            Card(
                "Memory Tree",
                "Working, session and durable memory with source provenance, confidence floors, sensitivity, contradiction reports and supersession — no silent overwrites — plus ranked, token-bounded recall.",
                ["provenance", "no overwrite"],
            ),
            Card(
                "Research Vault",
                "An append-only store of source-cited evidence with strength tiers; vendor benchmarks are recorded as vendor-reported, never as fact.",
                ["source-cited"],
            ),
            Card(
                "Evidence Engine",
                "Hybrid keyword + memory + repo-symbol retrieval that verifies every citation and audits for contradiction and hallucination before injection.",
                ["citation check"],
            ),
            Card(
                "Epistemics Layer",
                "An anti-hallucination discipline: confidence-floor gates and a fail-honest posture that catches fabricated paths, links and versions before they reach the owner.",
                ["fail-honest"],
            ),
            Card(
                "Research Fabric",
                "An eight-step pipeline — decompose, gather, rank, card, synthesise, verify citations, detect contradictions, calibrate — that never fabricates a source.",
                ["multi-step"],
            ),
            Card(
                "GraphRAG Knowledge Graph",
                "Unifies code, docs, the vault, the memory tree and ledgers into one typed, source-backed graph (tens of thousands of nodes) with local, global and coding queries so work reuses what exists.",
                ["typed graph", "reuse"],
            ),
            Card(
                "Second Brain",
                "A five-layer hybrid knowledge system — ingestion, storage, retrieval, reasoning, governance — blending vector, graph and keyword signal; wired in through an opt-in, credential-free bridge.",
                ["hybrid RAG"],
            ),
            Card(
                "Fusion Ranker",
                "A database-free blend of dense, graph and keyword signals — similarity, confidence and recency — producing an explainable, attributable ranking.",
                ["explainable"],
            ),
            Card(
                "Intent Graph",
                "A lightweight semantic intermediate form that models requested program semantics — trigger, operation, constraint, entity — frozen, deterministic and side-effect-free.",
                ["semantic IR"],
            ),
        ],
    ),
    Plane(
        "06",
        "Model Routing & Providers",
        "Free-first, measured-merit routing — use any model, with no lock-in",
        "#ffb13d",
        "#ff7a59",
        [
            Card(
                "Model Router",
                "Discovers providers and routes each task by capability, cost and latency, recording every model choice in the decision ledger.",
                ["routing"],
                gate=True,
            ),
            Card(
                "Registry & Scorecards",
                "Per-job scorecards — tests passed, latency, cost, hallucinations, diff acceptance — aggregated per model, task and risk to drive selection on measured evidence.",
                ["evidence"],
                gate=True,
            ),
            Card(
                "Full-Registry Router",
                "An opt-in ranker that scores the entire open model catalogue on merit with no tier gating, choosing the best fit for the task at hand.",
                ["merit-ranked"],
            ),
        ],
        strip=[
            "Local OSS (llama.cpp · Gemma)",
            "Hosted-free",
            "Claude Code / Codex worker lanes",
            "Paid (opt-in)",
        ],
        strip_label="Routing lanes — local-first, escalating only when needed · Providers: Anthropic · OpenAI · Gemini · OpenRouter · NovitaAI · NVIDIA NIM · z.ai · Kimi · MiniMax · Hugging Face · DeepSeek · xAI · Bedrock · Azure · Ollama · custom",
    ),
    Plane(
        "07",
        "Capability Layer",
        "Tools, plugins, skills and MCP servers — every capability opt-in, gated and audit-logged",
        "#4f9dff",
        "#36c6f0",
        [
            Card(
                "Plugin System",
                "A folder-based plugin layer covering model providers, memory backends, image and video generation, web search, browser automation, GitHub, kanban, observability and dozens of utility services.",
                ["~39 plugins"],
            ),
            Card(
                "Tool Registry",
                "Auto-discovered executable tools: files and terminal, sandboxed code execution, computer-use and browser control, MCP dispatch, search, vision, voice and scheduling.",
                ["~95 tools"],
            ),
            Card(
                "Memory Backends",
                "Pluggable, opt-in long-term memory — local store, dialectic user-modelling and several cloud and graph providers — selectable by configuration.",
                ["pluggable"],
                gate=True,
            ),
            Card(
                "Visual Synthesis",
                "A multi-provider image and video stack — text-to-image, image-to-video — plus vision and video analysis tools.",
                ["image", "video"],
                gate=True,
            ),
            Card(
                "Built-in Skills",
                "Markdown playbooks for orchestration, code, quality review, research, product strategy and creative work — data, not code, loaded on demand.",
                ["~65 skills"],
            ),
            Card(
                "Optional Skills",
                "Heavier, opt-in toolkits across MLOps, research, finance, productivity, creative, security, DevOps, blockchain (read-only) and health.",
                ["17 categories"],
            ),
            Card(
                "Optional MCP Servers",
                "Modular Model-Context-Protocol integrations for GitHub, Linear, Notion, Slack, Figma, Vercel, Supabase, Cloudflare, search and developer-docs services.",
                ["~29 servers"],
            ),
            Card(
                "AOS Enterprise Council",
                "A routed catalogue of hundreds of agent roles and sub-agents spanning architecture, security, compliance, QA, release, product and psychology — convened for audits and launch readiness.",
                ["routed council"],
            ),
        ],
    ),
    Plane(
        "08",
        "Self-Improvement & Learning",
        "Winners surface only as reviewable proposals — never a silent rewrite",
        "#ff5fb3",
        "#a06bff",
        [
            Card(
                "SIA Self-Improve Worker",
                "Rewrites a scaffold on a sandboxed copy and emits a proposal only when the candidate beats the baseline; it never edits the live target and never applies itself.",
                ["sandboxed"],
                gate=True,
            ),
            Card(
                "Autoresearch Engine",
                "A vendored training engine running short, disposable, cost- and VRAM-ceilinged pretraining experiments; winners surface as owner-gated proposals.",
                ["disposable", "ceilinged"],
                gate=True,
            ),
            Card(
                "Learning Dataset Pipeline",
                "Captures validated, source-backed traces — no secrets, no raw chain-of-thought — with provenance and quality labels, exported only after owner approval.",
                ["source-backed"],
            ),
            Card(
                "Flywheel",
                "A working log of prompts, actions, skill use and routing that auto-queues improvement entries on failure — soft by design, it never raises.",
                ["working log"],
            ),
            Card(
                "Proposal Executor",
                "Routes an approved proposal through the standard pull-request flow with a builder and a reviewer; it never merges, deploys or publishes.",
                ["PR flow"],
            ),
            Card(
                "Benchmark Gate & Canary",
                "An offline, deterministic proof-bar that passes only when a candidate beats baseline by a margin, with a post-apply canary that auto-rolls-back on regression.",
                ["proof-bar", "canary"],
            ),
        ],
    ),
    Plane(
        "09",
        "Verification Kernel",
        "AXIOM — no intelligence is trusted without external verification",
        "#ffd24a",
        "#ffb13d",
        [
            Card(
                "L0 · Record",
                "A hash-chained, signed ledger with Merkle checkpoints — a tamper-evident audit trail underneath everything.",
                ["ledger"],
            ),
            Card(
                "L1 · Identity",
                "A content-addressed registry that resolves or fails — a hallucinated reference is a hard error, never an execution.",
                ["resolve-or-fail"],
            ),
            Card(
                "L2 · Semantics",
                "Machine-readable intent, formal contracts and declared effects so behaviour is specified before it runs.",
                ["contracts"],
            ),
            Card(
                "L3 · Memory",
                "A spaced-repetition memory economy with belief revision and routed retrieval behind a single facade.",
                ["beliefs"],
            ),
            Card(
                "L4 · Interface",
                "Typed tool surfaces with machine-readable errors and explicit agent guidance.",
                ["typed tools"],
            ),
            Card(
                "L5 · Orchestration",
                "Hierarchical planning with verifier nodes and an eight-gate, risk-tiered authorization pipeline.",
                ["verifier nodes"],
            ),
            Card(
                "L6 · Evolution (Forge)",
                "Rating tournaments and quality-diversity search with a kill-switch — distilling only verified winners.",
                ["tournaments"],
            ),
            Card(
                "L7 · Governance",
                "A trust scorecard, graded autonomy bands and sovereignty clauses over the whole kernel.",
                ["autonomy bands"],
            ),
        ],
        strip=[
            "I1 · resolve or fail",
            "I2 · verify before attest",
            "I3 · history is append-only",
        ],
        strip_label="Kernel invariants",
    ),
    Plane(
        "10",
        "Federation & Sovereign Nodes",
        "Run MUSE as a sovereign node that federates with peers — trust earned, never assumed",
        "#7c8bff",
        "#a06bff",
        [
            Card(
                "Node Identity & TOFU Pinning",
                "Trust-on-first-use peer-identity pinning with signed ledger-head attestations and split-brain detection — peers verify, no one centrally controls.",
                ["TOFU"],
            ),
            Card(
                "M-of-N Quorum Authorization",
                "Generalises the single owner phrase to multi-person sign-off, while a single-owner deployment stays byte-for-byte identical.",
                ["quorum"],
                gate=True,
            ),
            Card(
                "Cross-Attestation",
                "Sovereign nodes attest to each other by content hash, keeping the protected core disjoint from the contributor pool.",
                ["by hash"],
            ),
            Card(
                "Content-addressed Forge",
                "A poison-filtered intake in front of the distillation set, with every intake decision appended to the ledger.",
                ["poison filter"],
            ),
            Card(
                "Contributor Trust Ladder",
                "Earned-trust bands that instrument who may do what and feed the scaling decisions.",
                ["earned trust"],
            ),
            Card(
                "Anti-Goal Covenant",
                "Non-amendable core clauses plus a scale-graded amendment process and a structural asset-lock.",
                ["non-amendable"],
            ),
        ],
    ),
    Plane(
        "11",
        "Supporting Fabric",
        "Design, documentation, governance, localization and heritage",
        "#9aa7bd",
        "#6b7a92",
        [
            Card(
                "Design System",
                "A single source of truth for visual tokens that generates web and mobile artifacts — three colour roles, tonal elevation, a strict grid and the MUSE glyph.",
                ["tokens"],
            ),
            Card(
                "Documentation Site",
                "A multi-language static documentation site: getting-started, user and developer guides, integrations and reference.",
                ["multi-lang"],
            ),
            Card(
                "Localization",
                "A sixteen-language catalogue of static prompts and gateway replies, kept at parity by test.",
                ["16 languages"],
            ),
            Card(
                "Enterprise Governance",
                "A runtime policy, risk-classification, secrets, audit and cross-check layer for the council agent team.",
                ["policy · audit"],
            ),
            Card(
                "Architecture Map",
                "A machine-readable component registry with a drift test, dataflow diagrams, work-packet and remote-worker schemas, and a technology-disposition matrix.",
                ["registry", "drift test"],
            ),
            Card(
                "Recovered Agent Sources",
                "Preserved pre-recovery agent, skill and governance definitions kept for audit and reversion.",
                ["audit trail"],
            ),
            Card(
                "Research & Trajectory Tooling",
                "Batch trajectory generation and trajectory compression for training the next generation of tool-calling models.",
                ["trajectories"],
            ),
        ],
    ),
    Plane(
        "12",
        "Execution Substrate & External World",
        "Runs anywhere — seven terminal backends — reaching the outside only through gated tools",
        "#8a93a6",
        "#5b6477",
        [
            Card(
                "Terminal Backends",
                "Seven interchangeable execution environments, including serverless options that hibernate when idle and wake on demand.",
                [
                    "Local",
                    "Docker",
                    "SSH",
                    "Singularity",
                    "Modal",
                    "Daytona",
                    "Vercel Sandbox",
                ],
            ),
            Card(
                "Deploy Targets",
                "The same agent on a low-cost VPS, a GPU cluster, serverless infrastructure, a phone, or a Windows scheduled-task service.",
                ["$5 VPS", "GPU", "serverless", "phone", "Windows"],
            ),
            Card(
                "External World",
                "GitHub, model APIs, the web, read-only blockchains, local models and operating-system terminals — reached only through gated tools and providers.",
                ["GitHub", "APIs", "web", "chains"],
                gate=True,
            ),
        ],
    ),
]


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_card(c: Card) -> str:
    tags = "".join(f'<span class="chip">{esc(t)}</span>' for t in c.tags)
    gate = (
        '<span class="gatebadge" title="reaches an owner-gated action">OWNER-GATED</span>'
        if c.gate
        else ""
    )
    return f"""
      <div class="card">
        <div class="card-top"><span class="dot"></span><h3>{esc(c.title)}</h3>{gate}</div>
        <p>{esc(c.desc)}</p>
        <div class="chips">{tags}</div>
      </div>"""


def render_strip(label: str, items: list[str]) -> str:
    chips = '<span class="arrow">→</span>'.join(
        f'<span class="flowchip">{esc(i)}</span>' for i in items
    )
    return f"""
      <div class="flowstrip">
        <div class="flowstrip-label">{esc(label)}</div>
        <div class="flowstrip-row">{chips}</div>
      </div>"""


def render_plane(p: Plane) -> str:
    cards = "".join(render_card(c) for c in p.cards)
    strip = render_strip(p.strip_label or "", p.strip) if p.strip else ""
    return f"""
    <section class="plane" style="--accent:{p.accent};--accent2:{p.accent2}">
      <div class="plane-head">
        <div class="plane-num">{esc(p.num)}</div>
        <div class="plane-titles">
          <h2>{esc(p.title)}</h2>
          <div class="plane-sub">{esc(p.subtitle)}</div>
        </div>
      </div>
      <div class="cards">{cards}</div>
      {strip}
    </section>
    <div class="connector"><span>&#9660;</span></div>"""


def build_html() -> str:
    planes_html = "".join(render_plane(p) for p in PLANES)
    today = date.today().isoformat()
    # final connector after last plane is harmless; CSS hides the trailing one.
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>M.U.S.E — Architecture Flow</title>
<style>
  :root {{
    --bg0:#070b16; --bg1:#0c1326; --bg2:#111a31;
    --ink:#eef3ff; --ink-dim:#aab8d4; --ink-faint:#7d8bab;
    --panel:rgba(255,255,255,0.035);
    --panel-line:rgba(255,255,255,0.10);
    --page-w:3280px;
  }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; padding:0; }}
  body {{
    width:var(--page-w);
    background:
      radial-gradient(1400px 900px at 18% 4%, rgba(54,230,240,0.10), transparent 60%),
      radial-gradient(1500px 1000px at 85% 30%, rgba(160,107,255,0.10), transparent 60%),
      radial-gradient(1400px 1100px at 50% 96%, rgba(47,208,122,0.08), transparent 60%),
      linear-gradient(180deg,#070b16 0%, #0a1020 45%, #070b16 100%);
    color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;
    letter-spacing:0.1px;
  }}
  .poster {{ width:var(--page-w); padding:120px 110px 90px; position:relative; }}

  /* subtle dotted grid overlay */
  .poster::before {{
    content:""; position:absolute; inset:0;
    background-image:radial-gradient(rgba(255,255,255,0.045) 1px, transparent 1px);
    background-size:46px 46px; pointer-events:none; z-index:0;
  }}
  .poster > * {{ position:relative; z-index:1; }}

  /* ---------------- header ---------------- */
  header.masthead {{ display:flex; align-items:center; gap:46px; margin-bottom:34px; }}
  .glyph {{ width:160px; height:160px; flex:0 0 auto; }}
  .mast-text h1 {{
    font-size:92px; line-height:0.98; margin:0 0 14px; font-weight:800;
    letter-spacing:1px;
    background:linear-gradient(92deg,#ffffff,#bfe9ff 38%,#c8b3ff 70%,#ffd9a8);
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }}
  .mast-text .tag {{ font-size:30px; color:var(--ink-dim); max-width:2300px; line-height:1.35; font-weight:400; }}
  .mast-text .tag b {{ color:var(--ink); font-weight:650; }}

  .statbar {{ display:flex; gap:18px; margin:30px 0 8px; flex-wrap:wrap; }}
  .stat {{
    background:var(--panel); border:1px solid var(--panel-line); border-radius:16px;
    padding:16px 24px; min-width:150px;
  }}
  .stat .n {{ font-size:40px; font-weight:800; color:#fff; }}
  .stat .l {{ font-size:20px; color:var(--ink-faint); margin-top:2px; }}

  .legend {{
    display:flex; gap:34px; flex-wrap:wrap; align-items:center;
    margin:18px 0 6px; padding:18px 26px;
    background:var(--panel); border:1px solid var(--panel-line); border-radius:18px;
    font-size:21px; color:var(--ink-dim);
  }}
  .legend b {{ color:var(--ink); }}
  .legend .gatebadge {{ position:static; transform:none; }}
  .legend .flowdir {{ color:#36e6f0; font-weight:700; }}

  /* ---------------- planes ---------------- */
  .plane {{
    border:1px solid var(--panel-line);
    border-left:7px solid var(--accent);
    border-radius:24px;
    padding:30px 34px 30px;
    margin:0;
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--accent) 9%, transparent), transparent 42%),
      rgba(10,16,32,0.55);
    box-shadow:0 0 0 1px rgba(255,255,255,0.02) inset, 0 30px 60px -40px rgba(0,0,0,0.8);
  }}
  .plane-head {{ display:flex; align-items:center; gap:26px; margin-bottom:22px; }}
  .plane-num {{
    font-size:46px; font-weight:800; color:transparent;
    -webkit-text-stroke:2px var(--accent);
    background:linear-gradient(180deg,var(--accent),var(--accent2));
    -webkit-background-clip:text; background-clip:text;
    min-width:84px;
  }}
  .plane-titles h2 {{ margin:0; font-size:42px; font-weight:750; color:#fff; letter-spacing:0.4px; }}
  .plane-sub {{ font-size:23px; color:var(--ink-dim); margin-top:4px; }}

  .cards {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(330px, 1fr)); gap:18px; }}
  .card {{
    background:var(--panel); border:1px solid var(--panel-line);
    border-radius:18px; padding:20px 22px 16px; position:relative; overflow:hidden;
  }}
  .card::after {{
    content:""; position:absolute; left:0; top:0; bottom:0; width:4px;
    background:linear-gradient(180deg,var(--accent),var(--accent2)); opacity:0.85;
  }}
  .card-top {{ display:flex; align-items:center; gap:12px; margin-bottom:9px; }}
  .card .dot {{ width:13px; height:13px; border-radius:50%;
    background:radial-gradient(circle at 35% 30%, #fff, var(--accent) 65%);
    box-shadow:0 0 14px 1px color-mix(in srgb,var(--accent) 70%, transparent); flex:0 0 auto; }}
  .card h3 {{ margin:0; font-size:25px; font-weight:700; color:#fff; flex:1; line-height:1.1; }}
  .card p {{ margin:0 0 12px; font-size:20px; line-height:1.4; color:var(--ink-dim); }}
  .chips {{ display:flex; gap:8px; flex-wrap:wrap; }}
  .chip {{
    font-size:16.5px; color:var(--ink-faint);
    background:rgba(255,255,255,0.05); border:1px solid var(--panel-line);
    border-radius:999px; padding:3px 12px;
  }}
  .gatebadge {{
    font-size:14px; font-weight:800; letter-spacing:1px;
    color:#ffd0d8; background:rgba(255,90,122,0.16);
    border:1px solid rgba(255,90,122,0.5); border-radius:999px; padding:3px 10px;
  }}

  /* ---------------- flow strips ---------------- */
  .flowstrip {{ margin-top:22px; padding:18px 22px;
    background:linear-gradient(90deg, color-mix(in srgb,var(--accent) 13%, transparent), transparent);
    border:1px dashed color-mix(in srgb,var(--accent) 45%, transparent); border-radius:16px; }}
  .flowstrip-label {{ font-size:20px; color:var(--ink-dim); margin-bottom:12px; font-weight:600; }}
  .flowstrip-row {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .flowchip {{
    font-size:19px; font-weight:650; color:#fff;
    background:color-mix(in srgb,var(--accent) 22%, rgba(10,16,32,0.7));
    border:1px solid color-mix(in srgb,var(--accent) 55%, transparent);
    border-radius:12px; padding:8px 16px; white-space:nowrap;
  }}
  .flowstrip .arrow {{ color:var(--accent); font-size:22px; font-weight:800; }}

  /* ---------------- connectors between planes ---------------- */
  .connector {{ display:flex; justify-content:center; height:46px; align-items:center; }}
  .connector span {{ font-size:34px; color:rgba(255,255,255,0.32);
    text-shadow:0 0 18px rgba(120,160,255,0.4); }}
  .connector:last-of-type {{ display:none; }}

  /* ---------------- feedback note + footer ---------------- */
  .loopnote {{
    margin:8px 0 0; padding:22px 28px; border-radius:20px;
    border:1px solid var(--panel-line);
    background:linear-gradient(90deg, rgba(54,230,240,0.10), rgba(160,107,255,0.10));
    font-size:24px; color:var(--ink); text-align:center; font-weight:600;
  }}
  .loopnote .a {{ color:#36e6f0; font-weight:800; }}
  footer {{
    margin-top:40px; padding-top:26px; border-top:1px solid var(--panel-line);
    display:flex; justify-content:space-between; align-items:flex-end; gap:30px;
    color:var(--ink-faint); font-size:21px;
  }}
  footer .big {{ color:var(--ink); font-size:26px; font-weight:700; }}
</style>
</head>
<body>
<div class="poster">

  <header class="masthead">
    <svg class="glyph" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="core" cx="42%" cy="38%" r="65%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="55%" stop-color="#eaf4ff"/>
          <stop offset="100%" stop-color="#bcd6ff"/>
        </radialGradient>
        <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#36e6f0"/>
          <stop offset="38%" stop-color="#6b8bff"/>
          <stop offset="68%" stop-color="#a06bff"/>
          <stop offset="100%" stop-color="#ffb13d"/>
        </linearGradient>
      </defs>
      <g transform="rotate(-32 100 100)">
        <circle cx="100" cy="100" r="86" stroke="url(#ring)" stroke-width="9" opacity="0.9"/>
        <circle cx="100" cy="100" r="70" stroke="url(#ring)" stroke-width="2.5" opacity="0.45"/>
      </g>
      <circle cx="100" cy="100" r="40" fill="url(#core)"/>
      <circle cx="100" cy="100" r="40" stroke="#ffffff" stroke-width="1.5" opacity="0.5"/>
    </svg>
    <div class="mast-text">
      <h1>M.U.S.E — Multi-Use Synaptic Entity</h1>
      <div class="tag"><b>One mind, many pathways.</b> A self-improving, local-first AI operating partner — a single identity (the <i>mind</i>) running over a synaptic substrate of surfaces, governance, orchestration, cognition and model pathways. This map flows top&nbsp;→&nbsp;bottom: from the surfaces where you talk to it, through the command center and safety spine, into orchestration, cognition and the world — with results flowing back into memory as a closed learning loop.</div>
    </div>
  </header>

  <div class="statbar">
    <div class="stat"><div class="n">12</div><div class="l">architecture planes</div></div>
    <div class="stat"><div class="n">8</div><div class="l">verification gates</div></div>
    <div class="stat"><div class="n">5</div><div class="l">orchestration primitives</div></div>
    <div class="stat"><div class="n">6</div><div class="l">operating modes</div></div>
    <div class="stat"><div class="n">20+</div><div class="l">chat platforms</div></div>
    <div class="stat"><div class="n">~39</div><div class="l">plugins</div></div>
    <div class="stat"><div class="n">~95</div><div class="l">tools</div></div>
    <div class="stat"><div class="n">7</div><div class="l">execution backends</div></div>
  </div>

  <div class="legend">
    <span class="flowdir">▼ flow direction: surfaces → command center → governance → orchestration → cognition → world → back to memory</span>
    <span><span class="gatebadge">OWNER-GATED</span> &nbsp;= can reach an action that defers until the owner authorizes it</span>
    <span><b>RC0–RC4</b> = blast-radius risk class of changing a component</span>
  </div>

  {planes_html}

  <div class="loopnote">
    <span class="a">Closed learning loop:</span>&nbsp; session events &rarr; normalized sources &rarr; Memory Tree &amp; Research Vault &rarr; GraphRAG &amp; fusion &rarr; context compiler &rarr; model router &rarr; agents &amp; workers &rarr; new session events. &nbsp;Memory cites its sources and is never silently overwritten; the safety spine sits across every layer.
  </div>

  <footer>
    <div>
      <div class="big">M.U.S.E · Multi-Use Synaptic Entity</div>
      Governed, local-first, model-agnostic · owner-controlled by construction · provenance-first cognition
    </div>
    <div style="text-align:right">
      Conceptual architecture map — no filenames, no source code · generated {today}<br>
      Vector PDF — zoom without limit (rendered well beyond 4K)
    </div>
  </footer>

</div>
</body>
</html>"""


# --------------------------------------------------------------------------- #
# Shared architecture data — drives BOTH the PDF poster and the interactive 3D
# model so the two never drift. The pipeline below is the narrated "first prompt
# -> fully built product" journey the 3D scene animates down the spine.
# --------------------------------------------------------------------------- #
PIPELINE: list[dict[str, object]] = [
    {
        "plane": 0,
        "title": "First prompt",
        "desc": "You speak or type a goal at any surface — terminal, chat, cockpit or voice. One mind, many entry points.",
    },
    {
        "plane": 1,
        "title": "Routed",
        "desc": "The operating layer reads intent, picks one of six modes and chooses a route — deterministic and offline.",
    },
    {
        "plane": 2,
        "title": "Bounded into a work packet",
        "desc": "The goal becomes a scoped packet: mission, risk class, allowed files, verification and rollback.",
    },
    {
        "plane": 2,
        "title": "Eight verification gates",
        "desc": "Planning, Build, Review, Test, Security, Release, Owner Approval and Rollback — each emits captured evidence.",
        "gates": True,
    },
    {
        "plane": 3,
        "title": "Decomposed",
        "desc": "The orchestrator splits the goal into a validated task graph and routes each task to a worker.",
    },
    {
        "plane": 4,
        "title": "Grounded in cognition",
        "desc": "Workers build using provenance-first memory and source-backed retrieval — memory cites its sources.",
    },
    {
        "plane": 5,
        "title": "Best model chosen",
        "desc": "Each task is routed to the best-fit model on measured merit, free-first, with every choice logged.",
    },
    {
        "plane": 6,
        "title": "Built with tools & skills",
        "desc": "Plugins, tools and skills do the work — every capability opt-in, gated and audit-logged.",
    },
    {
        "plane": 7,
        "title": "Self-checked",
        "desc": "Improvements surface only as reviewable proposals; a benchmark gate and canary guard every change.",
    },
    {
        "plane": 8,
        "title": "Externally verified",
        "desc": "The AXIOM kernel verifies — no intelligence is trusted without external proof; history is append-only.",
    },
    {
        "plane": 2,
        "title": "Owner approval",
        "desc": "Anything risky defers until you authorize it with an exact, nonce-bound phrase. You own the final call.",
    },
    {
        "plane": 11,
        "title": "Fully built product",
        "desc": "The result ships as a reviewable pull request — bounded, grounded, verified and audited end to end.",
    },
]


def export_data() -> dict[str, object]:
    """Serialize the whole model to a plain dict for the 3D scene + JSON."""
    return {
        "schema": "muse.architecture_viz.v1",
        "generated": date.today().isoformat(),
        "planes": [asdict(p) for p in PLANES],
        "pipeline": PIPELINE,
        "stats": [
            {"n": "12", "l": "architecture planes"},
            {"n": "8", "l": "verification gates"},
            {"n": "5", "l": "orchestration primitives"},
            {"n": "6", "l": "operating modes"},
            {"n": "20+", "l": "chat platforms"},
            {"n": "7", "l": "execution backends"},
        ],
    }


def main() -> None:
    # Generated artifacts live in the git-ignored docs/_generated tree (repo policy);
    # this script (the reproducible source) is tracked under scripts/diagrams/.
    repo_root = Path(__file__).resolve().parents[2]
    out = repo_root / "docs" / "_generated" / "flowchart"
    out.mkdir(parents=True, exist_ok=True)
    html_path = out / "muse_architecture_flowchart.html"
    html_path.write_text(build_html(), encoding="utf-8")
    print("WROTE", html_path)

    # Shared data for the interactive 3D model (tracked, so GitHub reflects it).
    data = export_data()
    model_dir = repo_root / "docs" / "3d-model"
    if model_dir.exists():
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        (model_dir / "architecture_data.json").write_text(
            payload + "\n", encoding="utf-8"
        )
        js = "/* AUTO-GENERATED by scripts/diagrams/build_muse_flowchart.py — do not edit. */\n"
        js += "window.MUSE_ARCH = " + payload + ";\n"
        (model_dir / "architecture_data.js").write_text(js, encoding="utf-8")
        print("WROTE", model_dir / "architecture_data.js")


if __name__ == "__main__":
    main()
