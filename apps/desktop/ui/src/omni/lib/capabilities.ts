// ============================================================================
// MUSE capability registry — the full README/architecture inventory, so EVERY
// MUSE capability is reachable from the PWA. Each entry declares its plane, the
// cockpit endpoint it binds to (if any), how it's surfaced (existing tab, an
// interactive drawer panel, or an info/doc card), and the canonical doc.
//
// Source of truth: README.md "What MUSE is" + the /v1/cockpit/* gateway surface.
// ============================================================================

export type Plane =
  | 'operating'
  | 'cognition'
  | 'orchestration'
  | 'governance'
  | 'intelligence'
  | 'federation'
  | 'surfaces';

export type PanelKind =
  | 'emergency'
  | 'approvals'
  | 'autonomy'
  | 'orchestrate'
  | 'modes'
  | 'memory'
  | 'packetize'
  | 'evidence'
  | 'research'
  | 'graph'
  | 'modelroutes'
  | 'learning'
  | 'proposals'
  | 'audit'
  | 'skills'
  | 'runtime'
  | 'commands'
  | 'info';

export type Surface =
  | { kind: 'tab'; to: string }
  | { kind: 'panel'; panel: PanelKind }
  | { kind: 'external'; href: string };

export interface Capability {
  id: string;
  title: string;
  blurb: string;
  plane: Plane;
  accent: string;
  surface: Surface;
  endpoint?: string;
  doc?: string;
}

export const PLANES: { key: Plane; label: string; accent: string }[] = [
  { key: 'operating', label: 'Operating Layer', accent: '#34E5C8' },
  { key: 'cognition', label: 'Cognition Plane', accent: '#7C9EFF' },
  { key: 'orchestration', label: 'Orchestration', accent: '#FFB020' },
  { key: 'governance', label: 'Governance & Gates', accent: '#FF6B8A' },
  { key: 'intelligence', label: 'Intelligence & Learning', accent: '#C264FE' },
  { key: 'federation', label: 'Federation', accent: '#5EE6EB' },
  { key: 'surfaces', label: 'Surfaces & Tooling', accent: '#3DD68C' },
];

export const CAPABILITIES: Capability[] = [
  // ---- Operating Layer ----
  { id: 'modes', title: 'Six Modes', blurb: 'Companion · Strategy · Critic · Operator · Builder · Voice — intent/mode classifier + runtime persona injection.', plane: 'operating', accent: '#34E5C8', surface: { kind: 'panel', panel: 'modes' }, doc: 'docs/jarvis-prime-operating-system.md' },
  { id: 'emergency', title: 'Emergency Stop', blurb: 'Halt all autonomous work immediately. The kill-switch over the runtime.', plane: 'operating', accent: '#FF5470', surface: { kind: 'panel', panel: 'emergency' }, endpoint: '/v1/cockpit/emergency-stop' },
  { id: 'jobs', title: 'Jobs & Task Graph', blurb: 'Live jobs, lanes, task trees, diffs, approve / pause / resume / cancel / publish.', plane: 'orchestration', accent: '#FFB020', surface: { kind: 'tab', to: '/jobs' }, endpoint: '/v1/cockpit/jobs' },
  { id: 'approvals', title: 'Owner Approvals', blurb: 'Owner-gated actions (spend, deploy, publish, OAuth, credentials) defer until you reply exactly "Yes, with authorization."', plane: 'governance', accent: '#FFB020', surface: { kind: 'tab', to: '/approvals' }, endpoint: '/v1/cockpit/approvals' },
  { id: 'autonomy', title: 'Autonomy Bands', blurb: 'B0–B3 capability-band wall. Workspace-scoped high-autonomy coding never weakens owner gates.', plane: 'operating', accent: '#FFB020', surface: { kind: 'tab', to: '/autonomy' }, endpoint: '/v1/cockpit/autonomy' },
  { id: 'runtime', title: 'Runtime & Monitors', blurb: 'Read-only fail-visible monitors, worker pool, and the daily owner brief.', plane: 'operating', accent: '#34E5C8', surface: { kind: 'panel', panel: 'runtime' }, endpoint: '/v1/cockpit/runtime/status' },

  // ---- Cognition Plane ----
  { id: 'memory', title: 'Memory Tree', blurb: 'Working/session/durable memory with provenance, confidence floors, contradiction reports, no silent overwrite.', plane: 'cognition', accent: '#7C9EFF', surface: { kind: 'panel', panel: 'memory' }, endpoint: '/v1/cockpit/memory/tree', doc: 'docs/jarvis_architecture/JARVIS_SYSTEM_OVERVIEW.md' },
  { id: 'packetize', title: 'Natural-Language Coder', blurb: 'Turn plain English into a bounded, gate-compatible work packet (intent, risk, owner gates, allowed files, rollback).', plane: 'cognition', accent: '#34E5C8', surface: { kind: 'panel', panel: 'packetize' }, endpoint: '/v1/cockpit/coding/plan' },
  { id: 'evidence', title: 'Evidence Engine', blurb: 'BM25 + memory hybrid retrieval with citation verification. Provenance-first.', plane: 'cognition', accent: '#5EE6EB', surface: { kind: 'panel', panel: 'evidence' }, endpoint: '/v1/cockpit/evidence/search' },
  { id: 'research', title: 'Research Vault', blurb: 'Source-cited evidence; vendor benchmarks recorded as vendor-reported.', plane: 'cognition', accent: '#7C9EFF', surface: { kind: 'panel', panel: 'research' }, endpoint: '/v1/cockpit/research' },
  { id: 'graph', title: 'GraphRAG Query', blurb: 'Query the typed, source-backed knowledge graph over code, docs, vault, memory, ledgers (local/global/coding).', plane: 'cognition', accent: '#34E5C8', surface: { kind: 'panel', panel: 'graph' }, endpoint: '/v1/cockpit/graph/query', doc: 'docs/jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md' },
  { id: 'second-brain', title: 'Second Brain', blurb: 'Hybrid vector + keyword retrieval over your knowledge (Postgres or zero-infra in-memory). Augments native recall; opt-in via MUSE_SECOND_BRAIN.', plane: 'cognition', accent: '#7C9EFF', surface: { kind: 'tab', to: '/second-brain' }, endpoint: '/v1/cockpit/second-brain/retrieve', doc: 'second_brain/README.md' },
  { id: 'graphviz', title: 'Neural Observatory', blurb: 'The GraphRAG graph as a live galaxy that pulses on real system actions.', plane: 'cognition', accent: '#FF8A3D', surface: { kind: 'tab', to: '/observatory' } },
  { id: 'tokenjuice', title: 'TokenJuice', blurb: 'Deterministic, token-bounded context compiler that carries provenance and screens secrets.', plane: 'cognition', accent: '#5EE6EB', surface: { kind: 'panel', panel: 'info' }, doc: 'docs/jarvis_architecture/JARVIS_SYSTEM_OVERVIEW.md' },

  // ---- Orchestration ----
  { id: 'orchestrate', title: 'Goal → PR Orchestration', blurb: 'Decompose a goal into a validated task graph run by specialist workers; publish the result.', plane: 'orchestration', accent: '#FFB020', surface: { kind: 'panel', panel: 'orchestrate' }, endpoint: '/v1/cockpit/orchestrate', doc: 'docs/orchestration/README.md' },
  { id: 'council', title: 'AOS Enterprise Council', blurb: '233 routed agent roles for audits, hardening, launch readiness, multi-perspective review.', plane: 'orchestration', accent: '#3DD68C', surface: { kind: 'tab', to: '/agents' }, doc: 'skills/aos-enterprise-council/' },
  { id: 'council-dispatch', title: 'Council Dispatch', blurb: 'Executable runtime: route a request to the active council + matching domain specialists, with owner gates surfaced.', plane: 'orchestration', accent: '#3DD68C', surface: { kind: 'tab', to: '/council' }, endpoint: '/v1/cockpit/council/dispatch' },
  { id: 'fleet', title: 'The Fleet', blurb: 'Massive 1-minute siloed fan-out: decompose a goal into N verifiable tasks, budget-capped, kill-switch, live galaxy mirror.', plane: 'orchestration', accent: '#FFB020', surface: { kind: 'tab', to: '/fleet' } },
  { id: 'forge', title: 'The Forge', blurb: 'Per-agent knowledge + specialization: knowledge packs (RAG), QLoRA adapters, persona/steering. Scope what an agent knows.', plane: 'intelligence', accent: '#C264FE', surface: { kind: 'tab', to: '/forge' }, endpoint: '/v1/cockpit/learning' },
  { id: 'championship', title: 'Championship', blurb: 'The Forge tournament: Glicko-2 ratings + MAP-Elites quality-diversity over competing candidates. Read-only standings.', plane: 'intelligence', accent: '#C264FE', surface: { kind: 'tab', to: '/championship' }, endpoint: '/v1/cockpit/forge/leaderboard' },

  // ---- Governance & Gates ----
  { id: 'gates', title: 'Eight Verification Gates', blurb: 'Planning · Build · Review · Test · Security · Release · Owner · Rollback — fused & attested in the Axiom Gate.', plane: 'governance', accent: '#FF6B8A', surface: { kind: 'tab', to: '/axiom' }, doc: 'docs/jarvis-verification-gates.md' },
  { id: 'federation', title: 'Federation', blurb: 'Sovereign-node identity + peers (public material only — keys never leave the node). Read-only.', plane: 'governance', accent: '#3DD68C', surface: { kind: 'tab', to: '/federation' }, endpoint: '/v1/cockpit/federation/status' },
  { id: 'audit', title: 'Evidence Ledger · verify_chain', blurb: 'Hash-chained, tamper-evident decision ledger with Merkle inclusion proofs.', plane: 'governance', accent: '#FF6B8A', surface: { kind: 'panel', panel: 'audit' }, endpoint: '/v1/cockpit/audit' },
  { id: 'constitution', title: 'Constitution & Self-Audit', blurb: 'Versioned behavioral rubric (C1…Cn), reward-hacking/Goodhart detection, capability-band wall, Anti-Goal Covenant.', plane: 'governance', accent: '#FF6B8A', surface: { kind: 'panel', panel: 'info' }, doc: 'docs/jarvis-constitution.md' },

  // ---- Intelligence & Learning ----
  { id: 'modelroutes', title: 'Free-First Model Routing', blurb: 'Local OSS → hosted-free → Claude Code / Codex lanes → paid (opt-in), chosen per task class from measured scorecards.', plane: 'intelligence', accent: '#C264FE', surface: { kind: 'panel', panel: 'modelroutes' }, endpoint: '/v1/cockpit/model-routes', doc: 'docs/ai-intelligence/' },
  { id: 'learning', title: 'Learning Loop', blurb: 'SFT → ORPO/DPO → GRPO. Validated, source-backed learning dataset feeds fine-tuning, retrieval, and the benchmark wall.', plane: 'intelligence', accent: '#C264FE', surface: { kind: 'panel', panel: 'learning' }, endpoint: '/v1/cockpit/learning', doc: 'docs/ai-intelligence/jarvis-learning-dataset.md' },
  { id: 'proposals', title: 'Self-Improvement (SIA · Autoresearch)', blurb: 'Owner-gated engines iterate in disposable sandboxes; MUSE promotes a winner only as a reviewable proposal.', plane: 'intelligence', accent: '#C264FE', surface: { kind: 'panel', panel: 'proposals' }, endpoint: '/v1/cockpit/proposals', doc: 'docs/integrations/sia-self-improvement.md' },
  { id: 'datasources', title: 'Open Data Sources', blurb: 'License-aware registry of public datasets for fine-tuning, retrieval, and a held-out benchmark wall.', plane: 'intelligence', accent: '#C264FE', surface: { kind: 'panel', panel: 'info' }, doc: 'docs/ai-intelligence/top-open-data-sources-for-training.md' },

  // ---- Federation ----
  { id: 'federation', title: 'Federation & Sovereign Nodes', blurb: 'TOFU peer-identity pinning, M-of-N quorum authorization, cross-attestation, content-addressed Forge, contributor trust ladder.', plane: 'federation', accent: '#5EE6EB', surface: { kind: 'panel', panel: 'info' }, doc: 'docs/federation/' },
  { id: 'architecture', title: 'Architecture Map', blurb: 'Machine-readable component registry (with drift test), dataflow diagrams, work-packet/remote-worker schemas, tech-disposition matrix.', plane: 'federation', accent: '#5EE6EB', surface: { kind: 'panel', panel: 'info' }, doc: 'docs/architecture/README.md' },
  { id: 'repo', title: 'Repo Mirror · Sync to main', blurb: 'The entire MUSE repo built in, end-to-end: browse every file, the full PR history (#1 → latest), and the parsed inventory (plugins/providers/skills/MCPs/docs) live from `main`, with one-click install/update that pulls the newest build from git.', plane: 'federation', accent: '#5EE6EB', surface: { kind: 'tab', to: '/repo' } },

  // ---- Surfaces & Tooling ----
  { id: 'chat', title: 'Unified Provider Chat', blurb: 'Chat with Claude / GPT / Gemini / OpenRouter / local through one local OpenAI-compatible gateway (official APIs, your keys).', plane: 'surfaces', accent: '#34E5C8', surface: { kind: 'tab', to: '/chat' }, doc: 'apps/nexus/server/README.md' },
  { id: 'models', title: 'Models', blurb: 'Every model across all connected providers (~30) — pick any with one click. Auto-routes direct / OpenRouter / gateway.', plane: 'intelligence', accent: '#C264FE', surface: { kind: 'tab', to: '/models' } },
  { id: 'addons', title: 'Add-ons (CLIs · MCPs · Custom)', blurb: 'The full MUSE integration surface — MCP servers, CLI lanes, and your own custom providers/MCPs/CLIs.', plane: 'surfaces', accent: '#3DD68C', surface: { kind: 'tab', to: '/settings' } },
  { id: 'fusion', title: 'Fusion Gate', blurb: 'Mixture-of-Agents: route / ensemble / pipeline / graph across providers, synthesized + AXIOM-attested. Presets, describe→recommend, favorites, history.', plane: 'intelligence', accent: '#C264FE', surface: { kind: 'tab', to: '/fusion' } },
  { id: 'steer', title: 'Agent Optimization Control', blurb: 'The octagon — real-time inference steering, mapped to the model-routing layer.', plane: 'surfaces', accent: '#34E5C8', surface: { kind: 'tab', to: '/steer' } },
  { id: 'skills', title: 'Skills System', blurb: 'Procedural memory: Markdown playbooks, the Skills Hub, the /<skill-name> slash invocation.', plane: 'surfaces', accent: '#3DD68C', surface: { kind: 'panel', panel: 'skills' }, endpoint: '/v1/cockpit/skills' },
  { id: 'commands', title: 'Command Palette', blurb: 'Run MUSE slash commands — /orchestrate, /swarm, /model, /jarvis, /personality, and more.', plane: 'surfaces', accent: '#34E5C8', surface: { kind: 'panel', panel: 'commands' } },
  { id: 'voice', title: 'Voice-First', blurb: 'On-device voice intake (STT) + TTS playback over the existing MUSE voice bridge.', plane: 'surfaces', accent: '#FF6B8A', surface: { kind: 'tab', to: '/settings' }, doc: 'docs/voice/voice-first-user-guide.md' },
  { id: 'activity', title: 'Activity Feed', blurb: 'Unified chronological event stream across all connected surfaces.', plane: 'surfaces', accent: '#3DD68C', surface: { kind: 'tab', to: '/activity' } },
  { id: 'android', title: 'Android Companion', blurb: 'Thin always-on daemon: foreground service, widget, QS tile, share target, authorization relay.', plane: 'surfaces', accent: '#3DD68C', surface: { kind: 'panel', panel: 'info' }, doc: 'apps/nexus/companion-android/README.md' },
  { id: 'mcp', title: 'MCP Integration', blurb: 'Connect any MCP server for extended capabilities.', plane: 'surfaces', accent: '#3DD68C', surface: { kind: 'panel', panel: 'info' }, doc: 'docs/github-integration.md' },
  { id: 'cron', title: 'Cron Scheduling', blurb: 'Scheduled tasks with platform delivery.', plane: 'surfaces', accent: '#3DD68C', surface: { kind: 'panel', panel: 'info' }, doc: 'docs/README.md' },
];

export function capabilitiesByPlane(plane: Plane): Capability[] {
  return CAPABILITIES.filter((c) => c.plane === plane);
}
