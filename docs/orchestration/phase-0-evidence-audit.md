# Phase 0 — Evidence Audit for Hermes Prompt-First Orchestration

> **Status:** Read-only audit. No features implemented. No code edited.
> This document is the factual baseline for any later phase (1+) that
> wants to extend the prompt-first orchestration stack.
>
> **Auditor:** Claude Code, branch `claude/hermes-phase-0-audit-BKxnp`
> **Audit date:** 2026-05-23
> **Audited tree:** `/home/user/hermes-agent` (Nous Research
> `hermes-agent` @ `pyproject.toml` version `0.14.0`)
>
> **Supersedes:** the prior Phase 0 audit on this same path
> (auditor branch `claude/hermes-phase-0-audit-TOYyJ`). That audit was
> accurate at the time but has been overtaken by the Phase 1–24
> orchestration work logged in
> [`docs/orchestration/PHASES.md`](PHASES.md). Where the two reports
> disagree, this one wins; the previous one is preserved in git
> history only.

---

## 1. Executive verdict

The Hermes repository is a **mature, shipping AI-agent framework**
that already implements the bulk of the proposed prompt-first
orchestration system. Phase 24 (release-hardening) is logged as
delivered in [`PHASES.md`](PHASES.md), with 60 orchestration tests
passing.

Concretely, the repo today already has:

- A full **AoS council skill family** under `skills/` —
  `aos-council-director`, `aos-full-agent-team`,
  `evidence-architect`, `principal-systems-architect`,
  `product-experience-architect`, `commercial-strategist`,
  `assurance-risk-director`, `delivery-scope-controller`,
  `contrarian-reviewer` (plus the legacy alias
  `contrarian-red-flag-analyst`), `codex-dispatch-governor`,
  `model-router`, `github-publisher`,
  `developer-ux-command-center`, `decision-quality-gate`,
  `research-validator`, `self-improvement-loop`,
  `ai-improvement-radar`, `competitive-feature-harvester`,
  `best-coding-tool-mission`, `hermes-orchestration-pipeline`,
  `local-quality-gate`.
- An **orchestrator CLI surface** (`/orchestrate`, `/orchestrator`,
  `/model-router`, `/decision-ledger`, `/ai-radar`,
  `/best-coding-tool-mission`) defined in
  `hermes_cli/commands.py:230-247` and routed through
  `hermes_cli/orchestrator.py` + `hermes_cli/job_controller.py`.
- A **worker-adapter framework** under `hermes_cli/workers/` with
  concrete adapters for `aider`, `claude_code`, `codex`, `goose`,
  `chatgpt_handoff`, and `hermes_local`, plus a registry and base
  class.
- A **scoring + merge + validation + publishing** pipeline:
  `hermes_cli/scoring.py`, `hermes_cli/merge_engine.py`,
  `hermes_cli/validation_gates.py`, `hermes_cli/github_publisher.py`.
- An **AI intelligence layer** under `docs/ai-intelligence/`:
  `model-registry.yaml`, `model-routing-policy.md`,
  `tool-capability-matrix.md`, `ai-improvement-radar.md`.
- Substantial **orchestration documentation** under
  `docs/orchestration/` (44 markdown files at audit time).
- A `CLAUDE.md` root project file (new since the prior audit) that
  points at `AGENTS.md` as the authoritative dev guide.

The remaining gaps are concrete and bounded — they are **not** the
"build the whole orchestration stack" gap the prior audit identified.
They are best framed as polish, wiring, and tests-against-reality.
See §4 and §9.

**Naming-drift status (per Phase 0 task §3):** neither `CLAUDE.md`
nor `AGENTS.md` references `contrarian-red-flag-analyst` or
`contrarian-reviewer` directly. The alias relationship is documented
inside `skills/contrarian-red-flag-analyst/SKILL.md` and
`skills/contrarian-reviewer/SKILL.md`, and both files exist. **No
drift to fix.** Details in §12.

---

## 2. Files inspected

| Path | Exists? | Notes |
|---|---|---|
| `README.md` | yes | 17 KB user-facing intro. |
| `AGENTS.md` | yes | 59 KB authoritative dev guide. |
| `CLAUDE.md` | **yes (new)** | 5 KB Claude-Code entry point that defers to `AGENTS.md`. |
| `pyproject.toml` | yes | `name = "hermes-agent"`, `version = "0.14.0"`. |
| `toolsets.py` | yes | 866 lines. Toolset registry + composition. |
| `hermes_cli/commands.py` | yes | 1,787 lines. CLI slash-command framework; declares `/orchestrate`, `/orchestrator`, `/model-router`, `/decision-ledger`, `/ai-radar`, `/best-coding-tool-mission`. |
| `agent/skill_commands.py` | yes | 523 lines. `/skill-name` dispatch shared by CLI + gateway. |
| `cli.py` | yes | 14,576 lines. `HermesCLI` interactive orchestrator. |
| `gateway/run.py` | yes | 18,253 lines. Messaging gateway entry. |
| `skills/` | yes | 50 top-level entries; 119 `SKILL.md` files total (incl. nested). |
| `optional-skills/` | yes | 81 `SKILL.md` files. |
| `.claude/` | **no** | Directory still absent. Hermes uses `skills/` + `agent/skill_commands.py` instead. |
| `.claude/agents/` | **no** | Directory absent. |
| `.claude/commands/` | **no** | Directory absent. |
| `docs/` | yes | 55 files across 8 subtrees including `orchestration/`, `ai-intelligence/`, `android/`, `competitive/`, `mission/`, `plans/`, `product/`, `termux/`. |
| `docs/orchestration/` | yes | 44 markdown files (README, PHASES, getting-started, worker-adapters, decision-ledger, etc.). |
| `scripts/` | yes | Includes `hermes-orchestrate.sh`, `hermes-ai-radar.sh`, install / release / build scripts. |
| `tests/` | yes | 24 subdirectories. Orchestrator-specific tests: `test_parallel_orchestration.py`, `test_orchestrator_commands.py`, `test_orchestrator_job_controller.py`, `test_orchestrator_api.py`, `test_worker_claude_code.py`. Kanban: 14 test files. |
| `cron/` | yes | `jobs.py` + `scheduler.py`. |
| `plugins/` | yes | 18 plugin families. `github_assistant`, `kanban`, `memory`, `model-providers`, `observability`, `web`, `browser`, etc. |
| `enterprise/` | yes | Python runtime that `skills/enterprise-council/*` reference. |
| `apps/android/` | yes | Native cockpit app. |
| `tui_gateway/`, `ui-tui/` | yes | Ink/React TUI + JSON-RPC backend. |
| `acp_adapter/`, `acp_registry/` | yes | IDE bridges (VS Code, Zed, JetBrains). |

### Auxiliary files of interest

- `mcp_serve.py` — MCP server entry (31 KB).
- `run_agent.py` (180 KB), `model_tools.py` (41 KB),
  `trajectory_compressor.py` (65 KB), `batch_runner.py` (57 KB),
  `mini_swe_runner.py` (28 KB), `hermes_state.py` (138 KB SQLite
  layer).
- `cli-config.yaml.example` (59 KB) — exhaustive config reference.
- `hermes-already-has-routines.md` — marketing doc on cron / webhook
  parity with Claude Code Routines.
- `docs/orchestration/known-limitations.md` — Phase 24 honesty
  contract; lists what is still mocked / stubbed.

---

## 3. Confirmed features (what Hermes already has)

### 3.1 Skill registry + slash-command dispatch
- `agent/skill_commands.py` scans `skills/`, `optional-skills/`, and
  `~/.hermes/skills/` and exposes each `SKILL.md` as a
  `/skill-name` command shared by the CLI and every gateway
  platform.
- Slug normalization, per-platform disabling
  (`skills.platform_disabled`), and dynamic resync via
  `/reload-skills`.

### 3.2 AoS council skill family (NEW relative to prior audit)
All 17 council roles from the brief now exist as `skills/<role>/SKILL.md`:
- `aos-council-director` — Director / front door for the council.
- `aos-full-agent-team` — master skill that runs the full 16-specialist sequence.
- `evidence-architect`
- `principal-systems-architect`
- `product-experience-architect`
- `commercial-strategist`
- `assurance-risk-director`
- `delivery-scope-controller`
- `contrarian-reviewer` (canonical)
- `contrarian-red-flag-analyst` (alias of the above; see §12)
- `codex-dispatch-governor`
- `model-router`
- `github-publisher`
- `developer-ux-command-center`
- `decision-quality-gate`
- `research-validator`
- `self-improvement-loop`
- `ai-improvement-radar`
- `competitive-feature-harvester`
- `best-coding-tool-mission`
- `hermes-orchestration-pipeline`
- `local-quality-gate`

`AGENTS.md:698-758` describes how these compose; the master skill
list lives in `docs/orchestration/hermes-agent-skill-map.md`.

### 3.3 Orchestrator command surface (NEW)
- CLI-only slash commands declared in
  `hermes_cli/commands.py:230-247`:
  - `/orchestrate <prompt>` — queue a new local orchestrator job.
  - `/orchestrator [status|list|open|resume|publish]` — inspect /
    resume / publish jobs.
  - `/model-router explain <prompt>` — explain routing.
  - `/decision-ledger show [job-id]` — show the ledger.
  - `/ai-radar update` — refresh the AI-radar snapshot.
  - `/best-coding-tool-mission status` — mission tracker.
- Handlers live in `hermes_cli/orchestrator.py` (job submission,
  ledger persistence) and `hermes_cli/job_controller.py`
  (job-folder layout, `write_decision_ledger`).
- Gateway hook is staged but **not yet** registered to the platform
  manifests (the commands are `cli_only=True` so they do not eat
  Slack's 50-slot manifest cap).
- Bash entry point at `scripts/hermes-orchestrate.sh`.

### 3.4 Worker-adapter framework (NEW)
- `hermes_cli/workers/base.py` — shared `Worker` base.
- `hermes_cli/workers/registry.py` — `ALL_WORKERS` list.
- Concrete adapters: `aider.py`, `claude_code.py`, `codex.py`,
  `goose.py`, `chatgpt_handoff.py`, `hermes_local.py`.
- Tests: `tests/test_worker_claude_code.py`.
- Each worker runs in its own sandboxed git worktree under
  `.hermes/worktrees/<worker>-<task_id>`. Falls back to a directory
  copy when not in a git checkout, so tests stay hermetic.
- **Known limitation:** workers currently emit Markdown proposals
  rather than patches (Phase 24 chose not to actuate). See
  `docs/orchestration/known-limitations.md:1`.

### 3.5 Scoring, arbiter, merge engine, validation gates,
publisher (NEW)
- `hermes_cli/scoring.py` — four-signal weighted scorer
  (success, structure, coverage, hint).
- `hermes_cli/arbiter.py` — picks a single winner, a draw, or
  abstains below `MIN_PASS_SCORE`.
- `hermes_cli/merge_engine.py` — produces a `MergeArtifact`
  (winner's proposal, or a side-by-side union on draw).
- `hermes_cli/validation_gates.py` — five gates: `structure`,
  `size`, `secrets`, `unicode`, `policy`. Stdlib-only.
- `hermes_cli/github_publisher.py` — emits a `PublishDescriptor`
  (PR or Issue). Dry-run by default; live mode requires
  `HERMES_PUBLISH_LIVE=1` plus a caller-supplied transport (no
  embedded credentials).

### 3.6 Decision ledger primitive (NEW)
- Write path: `hermes_cli/job_controller.py:323`
  (`write_decision_ledger`) + `_append_ledger` /
  `_save_ledger` / `_load_ledger` in
  `hermes_cli/orchestrator.py:185-268`.
- Read path: `/decision-ledger show` slash command +
  `run_decision_ledger` at `hermes_cli/orchestrator.py:604`.
- Tests: `tests/test_orchestrator_commands.py:175-200`
  (`test_submit_writes_ledger_entry`,
  `test_resume_and_publish_append_ledger_entries`,
  `test_get_ledger_unknown_id_returns_empty`).
- Storage: `~/.hermes/jobs/<job-id>/ledger.jsonl` per
  `CLAUDE.md:107-109`.

### 3.7 AI intelligence (model registry / routing / radar)
- `docs/ai-intelligence/model-registry.yaml` — capability matrix
  (latency, cost, context window, modality).
- `docs/ai-intelligence/model-routing-policy.md` — written policy
  consumed by `model-router`.
- `docs/ai-intelligence/tool-capability-matrix.md`.
- `docs/ai-intelligence/ai-improvement-radar.md`.
- `scripts/hermes-ai-radar.sh` — radar refresh entry point.
- `skills/competitive-feature-harvester/SKILL.md` +
  `docs/competitive/developer-agent-feature-harvest.md` — competitor
  feature-harvest workflow.

### 3.8 Self-improvement loop
- Skill: `skills/self-improvement-loop/SKILL.md`.
- Runtime hook: `agent/background_review.py`
  (`spawn_background_review_thread`).
- Background review proposes memory writes, skill creates, and skill
  updates by replaying trajectories in a daemon thread.
- **Latent dangling reference:** `agent/background_review.py:15` and
  `agent/system_prompt.py:5-7` still point at a `hermes-agent-dev`
  skill (`references/self-improvement-loop.md`) that does not exist
  on disk. The canonical reference is now
  `skills/self-improvement-loop/SKILL.md` and
  `docs/orchestration/self-improvement-loop.md`. See §9.3.

### 3.9 Multi-agent kanban dispatcher (carry-over)
- `plugins/kanban/`, `hermes_cli/kanban*.py` (8 modules).
- `skills/devops/kanban-orchestrator/SKILL.md`,
  `skills/devops/kanban-worker/SKILL.md`,
  `skills/autonomous-ai-agents/kanban-codex-lane/SKILL.md`.
- Auto-decompose, manual Specify, parent/child graphs, profile
  routing, parallel batches.

### 3.10 Cron scheduler (carry-over)
- `cron/jobs.py` + `cron/scheduler.py` (~130 KB).
- `hermes_cli/cron.py` user-facing CLI.
- Persisted jobs at `~/.hermes/cron/jobs.json`; outputs under
  `~/.hermes/cron/output/<job_id>/<ts>.md`.

### 3.11 Webhook & API triggers (carry-over)
- `hermes_cli/webhook.py`, `gateway/platforms/webhook/`,
  `gateway/platforms/api_server/`.
- `skills/devops/webhook-subscriptions/SKILL.md`.

### 3.12 Multi-platform gateway (carry-over)
- `gateway/run.py` (18 k LOC) orchestrates Telegram, Discord, Slack,
  WhatsApp, Signal, Matrix, Email, SMS, DingTalk, WeCom, Weixin,
  Feishu, QQBot, BlueBubbles, Yuanbao, Webhook, API server, etc.

### 3.13 MCP integration (carry-over)
- `mcp_serve.py` server entry, `hermes_cli/mcp_config.py`,
  `skills/mcp/native-mcp/`, `optional-skills/mcp/{fastmcp,mcporter}/`.

### 3.14 ACP / IDE bridges (carry-over)
- `acp_adapter/`, `acp_registry/`.
- `agent/copilot_acp_client.py`.

### 3.15 Memory subsystem (carry-over)
- `agent/memory_manager.py`, `agent/memory_provider.py`.
- Backends under `plugins/memory/` (Honcho, Mem0, Supermemory,
  Holographic, Hindsight, ByteRover, OpenViking, Retaindb).

### 3.16 Enterprise Council (carry-over)
- `skills/enterprise-council/` ships an 8-role council
  (`orchestrator`, `finance`, `hr`, `customer-service`,
  `operations`, `sales`, `judge`, `monitor`) with a Python runtime
  under `enterprise/`. Pre-dates and runs alongside the new AoS
  council family.

### 3.17 Test infrastructure (carry-over)
- Pytest suite under `tests/` (24 subdirs).
- Orchestration tests: `tests/test_orchestrator_commands.py`,
  `tests/test_orchestrator_job_controller.py`,
  `tests/test_orchestrator_api.py`,
  `tests/test_parallel_orchestration.py`,
  `tests/test_worker_claude_code.py`.
- Council tests: `tests/enterprise/test_council.py`.

---

## 4. Missing features (relative to a fully closed prompt-first loop)

The prior audit listed entire subsystems as missing. Most have since
landed (Phases 1–24). Today's gaps are narrower and concrete:

- **Worker actuation gap.** Workers currently emit Markdown proposals,
  not file mutations. `docs/orchestration/known-limitations.md:1`
  documents this explicitly. Until a worker can mutate its worktree,
  the orchestrator publishes *plans*, not *patches*.
- **No external-model calls inside workers.** Every worker's
  `_execute` is heuristic and stdlib-only by Phase 24's "no paid API
  calls" constraint. Wiring real model calls (per
  `model-router`'s routing decision) is the next obvious step.
- **Scoring weights are static.** `hermes_cli/scoring.py:WEIGHTS`
  is source-pinned. No outcome-based adaptation yet.
- **Gateway-visibility of new slashes.** `/orchestrate`,
  `/orchestrator`, `/model-router`, `/decision-ledger`,
  `/ai-radar`, and `/best-coding-tool-mission` are `cli_only=True`.
  The handler in `gateway/run.py:_handle_orchestrator_slash` is
  wired and ready (per
  `hermes_cli/commands.py:225-229`), but the manifest flip is
  deferred to avoid bumping `/q` / `/btw` aliases off the Slack 50-cap.
- **Dangling `hermes-agent-dev` skill reference.**
  `agent/background_review.py:15` and `agent/system_prompt.py:5-7`
  still point at a non-existent skill. The canonical home is now
  `skills/self-improvement-loop/SKILL.md` /
  `docs/orchestration/self-improvement-loop.md`. Fix is one or two
  edits; safe to bundle into a polish PR.
- **No formal decision-ledger schema doc cross-link from
  `hermes_state.py`.** The ledger today is JSONL-on-disk under
  `~/.hermes/jobs/<job-id>/ledger.jsonl`. There is no SQLite mirror
  in `hermes_state.py` and no schema reference in
  `docs/orchestration/decision-ledger.md` linking back to the write
  paths in `hermes_cli/orchestrator.py:185-268`.
- **No tests for the new top-level skills.** Tests exist for the
  orchestrator plumbing but not for the AoS council skills' actual
  outputs. Skill-output tests are explicitly *not* the goal per
  `AGENTS.md`'s "don't write change-detector tests" rule, but
  contract tests (frontmatter validation, related_skills wiring) are
  reasonable.
- **Phase log is gap-y.** `docs/orchestration/PHASES.md` jumps
  straight to "Phase 24"; the earlier phases are scattered across
  individual reports (`phase-9-validation-report.md`,
  `final-10-10-readiness-report.md`,
  `final-hermes-orchestration-integration-report.md`,
  `NEXT_PHASE_IMPLEMENTATION_PROMPT.md`). A consolidated phase index
  would aid Phase 1+ planning.
- **Naming-drift target turned out to be a non-issue.** No PR
  needed for the contrarian fix — both names exist and the alias is
  documented. See §12.

---

## 5. Existing agents

This repo has **no `.claude/agents/*.md` files**. By design: Hermes
treats agent identities as `SKILL.md` files dispatched via
`/skill-name`. The closest analogues are:

| Skill path | Role |
|---|---|
| `skills/aos-council-director/SKILL.md` | Front-door director of the AoS council. |
| `skills/aos-full-agent-team/SKILL.md` | Master orchestration skill — spins up all 16 specialists. |
| `skills/evidence-architect/SKILL.md` | Evidence gatherer / fact-finder. |
| `skills/principal-systems-architect/SKILL.md` | Systems architecture. |
| `skills/product-experience-architect/SKILL.md` | UX / product design. |
| `skills/commercial-strategist/SKILL.md` | Commercial / pricing / market. |
| `skills/assurance-risk-director/SKILL.md` | Risk / compliance / assurance. |
| `skills/delivery-scope-controller/SKILL.md` | Scope and delivery management. |
| `skills/contrarian-reviewer/SKILL.md` | Devil's advocate / red-flag analysis. |
| `skills/contrarian-red-flag-analyst/SKILL.md` | Alias for `contrarian-reviewer`. |
| `skills/codex-dispatch-governor/SKILL.md` | Governs Codex dispatch / safety. |
| `skills/model-router/SKILL.md` | Resolves `task-type → model` against `model-registry.yaml`. |
| `skills/github-publisher/SKILL.md` | PR / Issue publisher wrapper. |
| `skills/developer-ux-command-center/SKILL.md` | Dev-UX command center. |
| `skills/decision-quality-gate/SKILL.md` | Quality gate on council decisions. |
| `skills/research-validator/SKILL.md` | Validates research output. |
| `skills/self-improvement-loop/SKILL.md` | Trajectory replay → memory / skill proposals. |
| `skills/ai-improvement-radar/SKILL.md` | Periodic AI-improvement radar. |
| `skills/competitive-feature-harvester/SKILL.md` | Competitor-feature harvesting. |
| `skills/best-coding-tool-mission/SKILL.md` | "Best coding tool" mission tracker. |
| `skills/hermes-orchestration-pipeline/SKILL.md` | Top-level pipeline driver. |
| `skills/local-quality-gate/SKILL.md` | Local validation gate. |
| `skills/enterprise-council/{orchestrator,judge,monitor,finance,hr,customer-service,operations,sales}/SKILL.md` | Pre-existing 8-role enterprise council. |
| `skills/devops/kanban-orchestrator/SKILL.md` | Kanban decomposition playbook. |
| `skills/devops/kanban-worker/SKILL.md` | Kanban worker lifecycle. |
| `skills/autonomous-ai-agents/{hermes-agent,claude-code,codex,opencode,kanban-codex-lane}/SKILL.md` | How Hermes drives each autonomous coding agent. |

Dynamic per-user agents (profiles / personas) live under
`~/.hermes/` and are configured by `hermes profile …`; they are not
files in this repo.

---

## 6. Existing skills (inventory by category)

> Counts are of `SKILL.md` files at audit time.

### `skills/` (bundled, active by default — 119 `SKILL.md` total)

| Category | Skill count | Notable members |
|---|---|---|
| *(top-level orchestration roles)* | 22 | `aos-council-director`, `aos-full-agent-team`, `ai-improvement-radar`, `assurance-risk-director`, `best-coding-tool-mission`, `codex-dispatch-governor`, `commercial-strategist`, `competitive-feature-harvester`, `contrarian-red-flag-analyst`, `contrarian-reviewer`, `decision-quality-gate`, `delivery-scope-controller`, `developer-ux-command-center`, `dogfood`, `evidence-architect`, `github-publisher`, `hermes-orchestration-pipeline`, `local-quality-gate`, `model-router`, `principal-systems-architect`, `product-experience-architect`, `research-validator`, `self-improvement-loop`, `yuanbao` |
| `apple/` | 5 | apple-notes, apple-reminders, findmy, imessage, macos-computer-use |
| `autonomous-ai-agents/` | 5 | claude-code, codex, hermes-agent, kanban-codex-lane, opencode |
| `creative/` | 19+ | architecture-diagram, ascii-art, baoyu-*, claude-design, comfyui, excalidraw, manim-video, p5js, popular-web-designs |
| `data-science/` | 1 | jupyter-live-kernel |
| `devops/` | 3 | **kanban-orchestrator**, **kanban-worker**, **webhook-subscriptions** |
| `email/` | 1 | himalaya |
| `enterprise-council/` | 8 | orchestrator, judge, monitor, finance, hr, customer-service, operations, sales (+`shared/{audit,policy}.md`) |
| `gaming/` | 2 | minecraft-modpack-server, pokemon-player |
| `github/` | 5 | codebase-inspection, github-auth, github-code-review, github-issues, github-pr-workflow, github-repo-management |
| `media/` | 5 | gif-search, heartmula, songsee, spotify, youtube-content |
| `mcp/` | 1 | native-mcp |
| `mlops/` | 1 active + many `DESCRIPTION.md` | huggingface-hub |
| `note-taking/` | 1 | obsidian |
| `productivity/` | 8 | airtable, google-workspace, linear, maps, nano-pdf, notion, ocr-and-documents, powerpoint, teams-meeting-pipeline |
| `red-teaming/` | 1 | godmode |
| `research/` | 5 | arxiv, blogwatcher, llm-wiki, polymarket, research-paper-writing |
| `smart-home/` | 1 | openhue |
| `social-media/` | 1 | xurl |
| `software-development/` | 11 | debugging-hermes-tui-commands, **hermes-agent-skill-authoring**, node-inspect-debugger, plan, python-debugpy, requesting-code-review, spike, **subagent-driven-development**, systematic-debugging, test-driven-development, writing-plans |
| `index-cache/` | — | JSON indices (Anthropic, marketplace, LobeHub, OpenAI). |

### `optional-skills/` (shipped, off by default — 81 `SKILL.md` total)

| Category | Count | Examples |
|---|---|---|
| `autonomous-ai-agents/` | 2 | blackbox, honcho |
| `blockchain/` | 3 | evm, hyperliquid, solana |
| `communication/` | 1 | one-three-one-rule |
| `creative/` | 5 | blender-mcp, concept-diagrams, hyperframes, kanban-video-orchestrator, meme-generation |
| `devops/` | 4 | cli, docker-management, pinggy-tunnel, watchers |
| `dogfood/` | 1 | adversarial-ux-test |
| `email/` | 1 | agentmail |
| `finance/` | 8 | 3-statement-model, comps-analysis, dcf-model, excel-author, lbo-model, merger-model, pptx-author, stocks |
| `health/` | 2 | fitness-nutrition, neuroskill-bci |
| `mcp/` | 2 | fastmcp, mcporter |
| `migration/` | 1 | openclaw-migration |
| `mlops/` | 22+ | accelerate, chroma, clip, faiss, flash-attention, guidance, huggingface-tokenizers, instructor, lambda-labs, llava, modal, nemo-curator, peft, pinecone, pytorch-fsdp, pytorch-lightning, qdrant, saelens, simpo, slime, stable-diffusion, tensorrt-llm, torchtitan, whisper |
| `productivity/` | 7 | canvas, here-now, memento-flashcards, shop-app, shopify, siyuan, telephony |
| `research/` | 11 | bioinformatics, darwinian-evolver, domain-intel, drug-discovery, duckduckgo-search, gitnexus-explorer, osint-investigation, parallel-cli, qmd, scrapling, searxng-search |
| `security/` | 3 | 1password, oss-forensics, sherlock |
| `software-development/` | 1 | rest-graphql-debug |
| `web-development/` | 1 | page-agent |

---

## 7. Existing command surfaces

### 7.1 Hermes CLI (`hermes …`)
Routed through `hermes_cli/main.py` and the `COMMAND_REGISTRY` table
in `hermes_cli/commands.py`. Surfaces include:

`hermes`, `hermes chat`, `hermes setup`, `hermes model`, `hermes config`,
`hermes tools`, `hermes gateway`, `hermes cron`, `hermes webhook`,
`hermes kanban`, `hermes profile`, `hermes skills`, `hermes plugins`,
`hermes doctor`, `hermes claw migrate`, `hermes update`, `hermes logs`,
`hermes goals`, `hermes mcp`, `hermes voice`, `hermes web`, plus debug /
dev subcommands.

### 7.2 Orchestrator-specific slashes (NEW)
Declared in `hermes_cli/commands.py:230-247` (all `cli_only=True`):

| Slash | Purpose |
|---|---|
| `/orchestrate <prompt>` | Queue a new local orchestrator job (no auto-execution). |
| `/orchestrator [status|list|open|resume|publish]` | Inspect / resume / publish jobs. |
| `/model-router explain <prompt>` | Explain routing decision for a prompt. |
| `/decision-ledger show [job-id]` | Show the ledger for one job (or all). |
| `/ai-radar update` | Refresh the local AI-radar snapshot. |
| `/best-coding-tool-mission status` | Show the "best coding tool" mission status. |

Gateway hook (`gateway/run.py:_handle_orchestrator_slash`) is wired but
not surfaced on the Slack manifest yet (50-cap).

### 7.3 Dynamic `/skill-name` map
Built by `agent/skill_commands.scan_skill_commands()`. Wired into:
CLI completer (`hermes_cli/commands.py:SlashCommandCompleter`),
Telegram menu (`telegram_menu_commands`),
Discord slash commands (`discord_skill_commands*`),
Slack manifest / subcommand map.

### 7.4 Gateway platform endpoints
Under `gateway/platforms/{telegram,discord,slack,whatsapp,signal,
matrix,homeassistant,email,sms,dingtalk,wecom,weixin,feishu,qqbot,
bluebubbles,yuanbao,webhook,api_server, …}/`.

### 7.5 TUI surfaces
`ui-tui/` (Ink/React) + `tui_gateway/` (Python JSON-RPC backend).
`hermes --tui` launches the Ink frontend.

### 7.6 Embedded web dashboard
`hermes_cli/web_server.py` — used for kanban / achievements /
example-dashboard plugin UIs.

### 7.7 MCP server
`mcp_serve.py` — Hermes exposes its tools over MCP.

### 7.8 ACP server
`acp_adapter/`, `acp_registry/` — VS Code / Zed / JetBrains.

### 7.9 Bash entry points
`scripts/hermes-orchestrate.sh`, `scripts/hermes-ai-radar.sh`,
`scripts/hermes-termux-doctor.sh`, `scripts/hermes-termux-service.sh`.

---

## 8. Existing local tool capabilities

Tool discovery via `tools/registry.py` (imported by every tool file at
import time), surfaced through `model_tools.py` and `toolsets.py`.
Selected capabilities:

- **Terminal backends** (`tools/environments/`): local, Docker, SSH,
  Singularity, Modal, Daytona, Vercel Sandbox.
- **Browser**:
  `plugins/browser/{browser_use,browserbase,firecrawl}`,
  `agent/browser_provider.py`.
- **Web search**:
  `plugins/web/{brave_free,ddgs,exa,firecrawl,parallel,searxng,tavily}`,
  `agent/web_search_provider.py`.
- **Image gen**: `plugins/image_gen/{openai,openai-codex,xai}`,
  `agent/image_gen_provider.py`.
- **Video gen**: `plugins/video_gen/{fal,xai}`,
  `agent/video_gen_provider.py`.
- **Memory providers**: see §3.15.
- **Observability**: `plugins/observability/langfuse/`.
- **GitHub**: `plugins/github_assistant/`, `skills/github/*`,
  GitHub MCP server.
- **Skill management**: `tools/skills_tool.py` (referenced via
  `agent/skill_commands.py`).
- **Agent-level tools**: todo, clarify, execute_code, delegate_task.
- **LSP / debugger**: `agent/lsp/`, plus skills
  `software-development/node-inspect-debugger`,
  `software-development/python-debugpy`.
- **Toolset composition**: `toolsets.py:_HERMES_CORE_TOOLS` is the
  default bundle; per-platform toolsets layer on top.
- **Validation gates** (NEW): `hermes_cli/validation_gates.py` —
  `structure`, `size`, `secrets`, `unicode`, `policy`.
- **Worktrees** (NEW): `hermes_cli/worktrees.py` — per-worker
  sandbox creation/teardown.
- **Worker adapters** (NEW): `hermes_cli/workers/{aider,
  claude_code,codex,goose,chatgpt_handoff,hermes_local}.py` + base
  and registry.

---

## 9. Risks and blockers

1. **Worker actuation gap (MEDIUM).** Workers describe; they do not
   patch. Closing this loop is the highest-leverage Phase-1 candidate
   work because it converts the orchestrator from "planner" into
   "shipper". Source of truth:
   `docs/orchestration/known-limitations.md:1-12`.
2. **`hermes-agent-dev` dangling reference (LOW, but staleness
   debt).** `agent/background_review.py:15` and
   `agent/system_prompt.py:5-7` both point at a skill that does not
   exist. Replacement target:
   `skills/self-improvement-loop/SKILL.md` +
   `docs/orchestration/self-improvement-loop.md`. Two-file edit.
3. **CLI / gateway megafile size (MEDIUM).** `cli.py` is 14,576
   lines; `gateway/run.py` is 18,253 lines. Any new orchestration
   surface that requires editing these files risks merge pain and
   review fatigue. Prefer extending `hermes_cli/commands.py` and
   `agent/skill_commands.py` instead, as the orchestrator slashes
   already do.
4. **No SQLite mirror for the decision ledger (LOW).**
   `hermes_state.py` (138 KB SQLite layer) could host a ledger table
   to enable cross-job queries / web-dashboard views. Right now the
   ledger is JSONL-on-disk only. Design first; do not silently
   change the ledger schema.
5. **Profile / specialist roster is user-configured (MEDIUM).**
   `skills/devops/kanban-orchestrator/SKILL.md` documents that the
   kanban dispatcher does not know what profiles exist on a given
   machine. Any council orchestration that assumes a fixed
   specialist roster will misroute on real users' machines. Skills
   must discover the roster via `hermes profile list` /
   `kanban_list(...)` (already the documented pattern). The
   orchestration stack also calls out in `AGENTS.md:1207`: *do not
   autocorrect unknown profile names*.
6. **Phase log lacks earlier phases (LOW).**
   `docs/orchestration/PHASES.md` only documents Phase 24. Phases
   1–23 are scattered (`phase-9-validation-report.md`,
   `final-*-report.md`, `NEXT_PHASE_IMPLEMENTATION_PROMPT.md`).
   A consolidated index would help.
7. **Gateway-visibility deferred for new slashes (LOW).**
   `/orchestrate`, `/orchestrator`, `/model-router`,
   `/decision-ledger`, `/ai-radar`, and
   `/best-coding-tool-mission` are CLI-only today; flipping any of
   them gateway-visible bumps existing aliases off Slack's 50-cap.
   Conscious deferral — see comment block in
   `hermes_cli/commands.py:218-229`.
8. **Branding & licensing (carry-over).** Nous Research's
   MIT-licensed public repo. Anyone who clones it sees these
   skills. Keep private workflows / secrets out of skill files.
9. **No automated parity check between
   `docs/orchestration/hermes-agent-skill-map.md` and
   `skills/`/(LOW).** Drift is possible. A cheap test that
   asserts every skill named in the map exists on disk (and vice
   versa for the AoS family) would catch it.

---

## 10. Recommended phase dependencies

> Concrete, ordered, non-prescriptive. Each item is a *should-precede*
> dependency for later phases.

1. **Phase 1 — close the worker actuation gap.** Pick one worker
   (Claude Code is the natural choice given `tests/test_worker_claude_code.py`),
   wire its `_execute` to actually mutate the worktree via a model
   call, and run the existing arbiter / merge / gates / publisher
   pipeline end-to-end. Land behind a flag.
2. **Phase 1 (polish) — fix the dangling `hermes-agent-dev`
   reference** in `agent/background_review.py:15` and
   `agent/system_prompt.py:5-7`. Two-file edit. Safe to bundle.
3. **Phase 2 — consolidate the phase log.** Backfill
   `docs/orchestration/PHASES.md` with one paragraph per prior
   phase, cross-linked to its existing report file. No code change.
4. **Phase 2 — decision-ledger SQLite mirror.** Design first
   (schema in `docs/orchestration/decision-ledger.md`), then add a
   table to `hermes_state.py`, then dual-write from
   `hermes_cli/orchestrator.py:_save_ledger`. Keep JSONL as the
   source of truth on disk; SQLite is a queryable mirror.
5. **Phase 2 — skill-map parity test.** Add
   `tests/orchestration/test_skill_map_parity.py` that asserts
   every name in `docs/orchestration/hermes-agent-skill-map.md`
   resolves to a `SKILL.md` and vice versa.
6. **Phase 3 — make the new orchestrator slashes gateway-visible
   on at least Telegram + Discord.** Slack's 50-cap requires
   alias triage; do that separately and document.
7. **Phase 3 — outcome-adaptive scoring.** Replace
   `hermes_cli/scoring.py:WEIGHTS` constants with a learned set,
   stored beside the ledger.
8. **Phase 4 — wire `model-router` into worker dispatch.** Today
   the router skill explains routing; once Phase 1 lands actuation,
   the orchestrator should consult it to choose which worker gets
   the job.

---

## 11. Files likely to be edited by later phases

| Phase | Likely files | Why |
|---|---|---|
| 1 (worker actuation) | `hermes_cli/workers/claude_code.py`, `hermes_cli/workers/base.py`, `hermes_cli/orchestrator.py`, `tests/test_worker_claude_code.py`, `docs/orchestration/known-limitations.md` | First worker that actually patches. |
| 1 (polish) | `agent/background_review.py:15`, `agent/system_prompt.py:5-7` | Replace dangling `hermes-agent-dev` reference. |
| 2 (phase log) | `docs/orchestration/PHASES.md` | Backfill Phases 1–23. |
| 2 (ledger SQLite mirror) | `hermes_state.py`, `hermes_cli/orchestrator.py`, `docs/orchestration/decision-ledger.md`, new `tests/orchestration/test_ledger_sqlite.py` | Persist + surface ledger across jobs. |
| 2 (skill-map parity) | New `tests/orchestration/test_skill_map_parity.py`, `docs/orchestration/hermes-agent-skill-map.md` | Catch drift. |
| 3 (gateway visibility) | `hermes_cli/commands.py:230-247` (flip `cli_only`), `gateway/run.py:_handle_orchestrator_slash`, Slack manifest tests under `tests/hermes_cli/test_commands.py` | Surface new slashes on gateways. |
| 3 (adaptive scoring) | `hermes_cli/scoring.py`, `tests/test_scoring.py`, ledger schema | Outcome-aware weights. |
| 4 (router-driven dispatch) | `hermes_cli/orchestrator.py`, `hermes_cli/workers/registry.py`, `skills/model-router/SKILL.md`, `docs/ai-intelligence/model-routing-policy.md` | Couple router's decisions to dispatch. |
| All | `hermes_cli/commands.py`, `agent/skill_commands.py`, `gateway/run.py` (only if a slash needs gateway-specific behavior) | Slash registration. |

---

## 12. Naming-drift check (per Phase 0 task §3)

| Check | Result |
|---|---|
| `CLAUDE.md` references `contrarian-red-flag-analyst`? | **No.** `CLAUDE.md` does not name either contrarian role. |
| `CLAUDE.md` references `contrarian-reviewer`? | **No.** |
| `AGENTS.md` references either? | **No.** `AGENTS.md` mentions the council generally (lines 698-758) but does not name contrarian roles. |
| Actual file `skills/contrarian-reviewer/SKILL.md` exists? | **Yes.** Canonical, 1 file. |
| Actual file `skills/contrarian-red-flag-analyst/SKILL.md` exists? | **Yes.** Declared as an explicit alias of `contrarian-reviewer` (line 19: *"This skill is an alias for contrarian-reviewer"*). |
| Cross-references between the two? | `skills/contrarian-reviewer/SKILL.md:23` documents the alias and points at the alias file. `skills/contrarian-red-flag-analyst/SKILL.md:27` instructs the model to load the canonical file and follow its playbook. |
| Other in-repo references | `skills/aos-full-agent-team/SKILL.md:19-20,52-53`, `skills/aos-council-director/SKILL.md`, `skills/{assurance-risk-director,principal-systems-architect,product-experience-architect}/SKILL.md`, `docs/orchestration/hermes-agent-skill-map.md:30,92-94` — all use the canonical name plus an explicit alias mention where helpful. |

**Verdict:** **No naming drift requires fixing.** The alias is
documented, both files exist, and the canonical-vs-alias relationship
is explicit. The brief's "trivial typo fix" allowance therefore does
not apply. Recorded here for Phase 1's awareness.

---

## 13. Validation commands used

The audit relied on these read-only commands (all safe; none mutate
state):

```bash
# Tree / file existence
ls -la .claude 2>/dev/null            # confirmed absent
find . -maxdepth 3 -type d -name ".claude"
find skills -maxdepth 3 -type f | sort
find optional-skills -maxdepth 3 -type f | sort
find docs -maxdepth 4 -type f | sort
find tests -name "test_*orchestrat*" -o -name "test_*kanban*" \
  -o -name "test_*ledger*" -o -name "test_*radar*"

# Skill inventory
grep -n "^name:" skills/*/SKILL.md
find skills -name SKILL.md | wc -l
find optional-skills -name SKILL.md | wc -l

# Naming-drift checks
grep -n "contrarian" CLAUDE.md AGENTS.md           # no output
grep -rn "contrarian-red-flag-analyst" --include="*.md" \
  --include="*.py" .
grep -rn "contrarian-reviewer" --include="*.md" \
  --include="*.py" .

# Orchestration surface
grep -n "orchestrate\|orchestrator\|model-router\|decision-ledger\|\
ai-radar\|best-coding-tool" hermes_cli/commands.py
ls hermes_cli/workers/
ls hermes_cli/ | grep -E "orchestrat|merge|score|arbiter|gates|publisher"
grep -ln "DecisionLedger\|decision_ledger" -r . --include="*.py"

# Self-improvement loop wiring
grep -n "hermes-agent-dev\|self-improvement-loop" \
  agent/background_review.py agent/system_prompt.py
find . -name "self-improvement-loop*" -print
find . -name "hermes-agent-dev*" -print     # no output

# Phase log
head -50 docs/orchestration/PHASES.md
grep -n "^## Phase" docs/orchestration/PHASES.md   # only "Phase 24"

# File-size / megafile awareness
wc -l cli.py gateway/run.py hermes_cli/commands.py \
  agent/skill_commands.py toolsets.py
```

All commands returned the data summarised above. No write or
destructive operation was issued.
