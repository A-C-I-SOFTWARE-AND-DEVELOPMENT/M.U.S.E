# Phase 0 — Evidence Audit for muse Prompt-First Orchestration

> **Status:** Read-only audit. No features implemented. No code edited. This
> document is the factual baseline that later phases (1+) will build on.
>
> **Auditor:** Claude Code, branch `claude/hermes-phase-0-audit-TOYyJ`
> **Audited tree:** `/home/user/hermes-agent` (Nous Research `hermes-agent`
> @ `pyproject.toml` version `0.14.0`)

---

## 1. Executive verdict

The muse repository is a **mature, shipping AI-agent framework**
(~35k LOC across `cli.py`, `gateway/run.py`, `hermes_cli/commands.py`,
`toolsets.py` alone, plus a deep `agent/` package and a large plugin
ecosystem). It already provides most of the *primitives* the proposed
"prompt-first orchestration system" needs — skill registry with
slash-command dispatch, a kanban multi-agent dispatcher, a cron
scheduler, a webhook gateway, MCP server, plugins, a memory subsystem,
and a self-improvement loop hook in `agent/background_review.py`.

It does **not** currently contain the specific AOS / muse
"orchestration council" described in the brief. In particular:

- There is **no `.claude/` directory** anywhere in the repo (no
  `.claude/agents/`, no `.claude/commands/`).
- There is **no root-level `CLAUDE.md`** file. The closest analogue is
  `AGENTS.md` (a 51 KB developer guide for AI coding assistants working
  on this codebase).
- **None** of the proposed agent identities exist as files or as
  references anywhere in the tree:
  `aos-council-director`, `evidence-architect`,
  `principal-systems-architect`, `product-experience-architect`,
  `commercial-strategist`, `assurance-risk-director`,
  `delivery-scope-controller`, `contrarian-reviewer`,
  `contrarian-red-flag-analyst`, `codex-dispatch-governor`,
  `model-router`, `github-publisher`, `developer-ux-command-center`,
  `decision-quality-gate`, `research-validator`,
  `ai-improvement-radar`, `self-improvement-loop` (as a skill).
- The closest existing analogue is **`skills/enterprise-council/`**,
  an 8-role council with a different naming taxonomy
  (`orchestrator`, `finance`, `hr`, `customer-service`, `operations`,
  `sales`, `judge`, `monitor`). It demonstrates that a multi-agent
  council pattern already runs inside muse via the skill system.
- A `self-improvement-loop` *reference document* is alluded to in
  `agent/background_review.py:15` and `agent/system_prompt.py:7` as
  `references/self-improvement-loop.md` inside a `hermes-agent-dev`
  skill, but neither that file nor a `hermes-agent-dev` skill
  directory exists on disk (only `hermes-agent-skill-authoring` and
  `skills/autonomous-ai-agents/hermes-agent/` exist).

**Bottom line:** Phase 1 cannot simply "convert `.claude/agents/*.md`
into muse skills" because the source agent files do not exist in
this repository. Phase 1's plan needs to be re-grounded against what
is actually here. See §10 (Recommended phase dependencies).

---

## 2. Files inspected

| Path | Exists? | Notes |
|---|---|---|
| `README.md` | yes | Nous Research's public README, 14 KB. |
| `AGENTS.md` | yes | 51 KB developer guide for AI coding assistants. |
| `CLAUDE.md` | **no** | Absent. No root-level Claude-Code project file. |
| `pyproject.toml` | yes | `name = "hermes-agent"`, `version = "0.14.0"`. |
| `toolsets.py` | yes | 866 lines. Toolset registry + composition. |
| `hermes_cli/commands.py` | yes | 1,756 lines. CLI slash-command framework. |
| `agent/skill_commands.py` | yes | 19 KB. `/skill-name` dispatch shared by CLI + gateway. |
| `cli.py` | yes | 14,528 lines. `HermesCLI` interactive orchestrator. |
| `gateway/run.py` | yes | 18,205 lines. Messaging gateway entry. |
| `skills/` | yes | 28 categories, ~80 SKILL.md files. |
| `optional-skills/` | yes | 19 categories, ~60 SKILL.md files. |
| `.claude/` | **no** | Directory absent. |
| `.claude/agents/` | **no** | Directory absent. |
| `.claude/commands/` | **no** | Directory absent. |
| `docs/` | yes | Only `github-integration.md`, `hermes-local-orchestrator.md`, `hermes-kanban-v1-spec.pdf`, `plans/` (2 files). Sparse. |
| `scripts/` | yes | Install / release / build / test scripts. |
| `tests/` | yes | ~20 test subdirectories (`agent/`, `cron/`, `gateway/`, `tools/`, `skills/`, etc.). |
| `cron/` | yes | `jobs.py` (45 KB) + `scheduler.py` (84 KB). |
| `gateway/` | yes | Platforms, hooks, run, session, status, etc. |
| `tui_gateway/` | yes | Python JSON-RPC backend for the Ink TUI. |
| `ui-tui/` | yes | Ink/React TUI source under `src/`. |
| `plugins/` | yes | 18 plugin families (model-providers, kanban, memory, observability, webhooks, etc.). |
| `enterprise/` | yes | Python runtime that `skills/enterprise-council/*` reference. |

### Auxiliary files of interest
- `hermes_bootstrap.py`, `hermes_constants.py`, `hermes_state.py`,
  `hermes_logging.py`, `hermes_time.py`
- `mcp_serve.py` — MCP server entry (31 KB).
- `mini_swe_runner.py`, `batch_runner.py`, `run_agent.py` (180 KB),
  `trajectory_compressor.py`, `model_tools.py`.
- `hermes-already-has-routines.md` — marketing doc demonstrating
  muse' existing cron / webhook / API-trigger automation parity
  with Claude Code Routines.
- `docs/hermes-local-orchestrator.md` — describes an **Android**
  app's "local orchestrator" pattern (not the agent council).
- `docs/plans/` — two existing planning docs (Telegram multi-session
  topics; ACP Zed edit-approval diffs).

---

## 3. Confirmed features (what muse already has)

### 3.1 Skill registry + slash-command dispatch
- `agent/skill_commands.py` scans `skills/`, `optional-skills/`, and
  `~/.hermes/skills/` and exposes each SKILL.md as a `/skill-name`
  command shared by **both** CLI (`cli.py`) and gateway
  (`gateway/run.py`).
- Slug normalization handled by `_SKILL_INVALID_CHARS` /
  `_SKILL_MULTI_HYPHEN`.
- Per-platform disabling via `skills.platform_disabled`.
- `hermes_cli/commands.py:609-700` ties `/skill-name` keys into the
  gateway help / Telegram menu / Discord / Slack subcommand maps.
- `hermes_cli/skills_hub.py`, `hermes_cli/skills_config.py` provide
  hub & config CLIs.

### 3.2 Multi-agent kanban dispatcher
- `plugins/kanban/` — full dispatcher + worker plugin.
- `hermes_cli/kanban.py` (104 KB), `hermes_cli/kanban_db.py` (250 KB),
  `hermes_cli/kanban_decompose.py`, `hermes_cli/kanban_specify.py`,
  `hermes_cli/kanban_swarm.py`, `hermes_cli/kanban_diagnostics.py`.
- `skills/devops/kanban-orchestrator/SKILL.md` (14 KB) — decomposition
  playbook for orchestrator profiles.
- `skills/devops/kanban-worker/SKILL.md` — worker lifecycle.
- `skills/autonomous-ai-agents/kanban-codex-lane/SKILL.md` —
  Codex-specific lane.
- Auto-decompose, manual `Specify`, parent/child task graphs, profile
  routing by description, sub-agent delegation, parallel batches.

### 3.3 Cron scheduler
- `cron/jobs.py` + `cron/scheduler.py` (~130 KB combined).
- `hermes_cli/cron.py` user-facing CLI.
- Persisted jobs at `~/.hermes/cron/jobs.json`; outputs at
  `~/.hermes/cron/output/<job_id>/<ts>.md`.
- Supports cron expressions + human-readable intervals; delivery to
  any gateway platform; per-job `--script` and `--skills` injection.

### 3.4 Webhook & API triggers
- `hermes_cli/webhook.py`, `gateway/platforms/webhook/`,
  `gateway/platforms/api_server/`.
- `skills/devops/webhook-subscriptions/SKILL.md` — user-facing guide.
- HMAC auth, event templates, skill chaining, multi-target delivery.

### 3.5 Background self-improvement loop (partial)
- `agent/background_review.py` (29 KB) — `spawn_background_review_thread`
  replays trajectories in a daemon thread to propose memory writes,
  skill creates, and skill updates.
- `agent/system_prompt.py` — references the same loop documentation.
- **Caveat:** the referenced `hermes-agent-dev` skill and its
  `references/self-improvement-loop.md` are **not present in this
  checkout**. The runtime hook exists; the doc/skill it points at
  does not.

### 3.6 Multi-platform gateway
- `gateway/run.py` (18 k LOC) orchestrates Telegram, Discord, Slack,
  WhatsApp, Signal, Matrix, Email, SMS, DingTalk, WeCom, Weixin,
  Feishu, QQBot, BlueBubbles, Yuanbao, Webhook, API server, etc.
- `gateway/builtin_hooks/`, `gateway/platform_registry.py`,
  `gateway/channel_directory.py`, `gateway/session.py` (57 KB).

### 3.7 MCP integration
- `mcp_serve.py` — server entry.
- `hermes_cli/mcp_config.py` — config wiring.
- `optional-skills/mcp/fastmcp/`, `optional-skills/mcp/mcporter/`,
  `skills/mcp/native-mcp/`.

### 3.8 Provider routing / model switching
- `hermes_cli/models.py` (144 KB), `hermes_cli/model_catalog.py`,
  `hermes_cli/model_normalize.py`, `hermes_cli/model_switch.py`
  (74 KB), `agent/model_metadata.py` (77 KB), `model_tools.py` (41 KB).
- Plugins under `plugins/model-providers/` for 30+ providers
  (Anthropic, OpenAI, Gemini, Bedrock, Azure, Copilot, DeepSeek, GMI,
  HuggingFace, OpenRouter, Nous, NVIDIA, NovitaAI, MoonShot, MiniMax,
  Qwen, StepFun, XAI, Xiaomi, Zai, etc.).
- Credential pools / rotation in `agent/credential_pool.py` (88 KB).
- **No** standalone `model-router` skill; routing logic lives in the
  CLI + plugin layer, not as a prompt-callable skill.

### 3.9 ACP / IDE bridges
- `acp_adapter/`, `acp_registry/` — VS Code / Zed / JetBrains.
- `agent/copilot_acp_client.py`.

### 3.10 Memory subsystem
- `agent/memory_manager.py` (23 KB), `agent/memory_provider.py`.
- Pluggable memory backends under `plugins/memory/` (Honcho, Mem0,
  Supermemory, Holographic, Hindsight, ByteRover, OpenViking, Retaindb).

### 3.11 Existing "council" pattern (Enterprise Council)
- `skills/enterprise-council/` ships an 8-role council:
  `orchestrator`, `finance`, `hr`, `customer-service`, `operations`,
  `sales`, `judge`, `monitor` plus `shared/policy.md` and
  `shared/audit.md`.
- Runtime shim lives at `enterprise/` (Python).
- Proves muse can host a council via the skill system today.

### 3.12 Test infrastructure
- Pytest suite under `tests/` (~20 subdirs).
- `scripts/run_tests.sh` probes venv locations.

### 3.13 Other notable surfaces
- `hermes_cli/voice.py` (33 KB) — voice memo / STT / TTS.
- `hermes_cli/clipboard.py`, `hermes_cli/pairing.py`.
- `hermes_cli/security_advisories.py`.
- `hermes_cli/profiles.py`, `hermes_cli/profile_distribution.py`,
  `hermes_cli/profile_describer.py` — profile/persona system that the
  kanban orchestrator routes against.
- `hermes_cli/goals.py` (31 KB) — goals subsystem.
- `hermes_cli/web_server.py` (178 KB) — embedded web dashboard.
- `cli-config.yaml.example` (59 KB) — exhaustive config reference.

---

## 4. Missing features (relative to the proposed orchestration system)

> **Bold = blocks Phase 1 directly.** Italics = needs design before
> later phases can land.

- **No `.claude/` directory at all** — no `agents/`, no `commands/`.
  Phase 1's premise ("Convert each `.claude/agents/*.md` into muse
  skills") has no source files to convert.
- **No root `CLAUDE.md`** — the naming-drift fix described in the
  brief (`contrarian-red-flag-analyst` → `contrarian-reviewer`)
  cannot be performed because neither the file nor either of those
  agent names exists in the repo. The closest hit is the unrelated
  prose phrase "red flag" at `AGENTS.md:987` (about merge regressions).
- **No `contrarian-reviewer.md` agent file**, no `contrarian-reviewer`
  skill, and no `contrarian-red-flag-analyst` reference anywhere.
- **None of the proposed council roles exist** as agents or skills:
  `aos-council-director`, `evidence-architect`,
  `principal-systems-architect`, `product-experience-architect`,
  `commercial-strategist`, `assurance-risk-director`,
  `delivery-scope-controller`, `codex-dispatch-governor`,
  `github-publisher`, `developer-ux-command-center`,
  `decision-quality-gate`, `research-validator`,
  `ai-improvement-radar`.
- **No `model-router` skill** — model routing exists but only as CLI /
  plugin code (`hermes_cli/model_switch.py`, `agent/model_metadata.py`),
  not as a prompt-callable skill.
- **No `self-improvement-loop` skill**, though the runtime hook
  (`agent/background_review.py`) and a *reference* to such a doc
  exist. The referenced `hermes-agent-dev` skill is also absent.
- **No `decision-ledger` artifact, skill, schema, or storage**.
- **No `aos-full-agent-team` master skill**.
- **No `skills/contrarian-red-flag-analyst/` alias** (and no upstream
  to alias to).
- *No `docs/orchestration/` documentation* — created by this audit;
  Phase 1 will extend it (e.g. `hermes-agent-skill-map.md`).
- *No "AI improvement radar"* feature/skill/CLI.
- *No "competitive feature harvesting" subsystem*.
- *No "developer UX command center"* skill (the closest analogue is
  the `hermes` TUI + `hermes_cli/web_server.py` dashboard, but
  neither is exposed as a prompt-callable orchestration skill).
- *No "GitHub publisher" skill* — muse uses GitHub via webhooks,
  the GitHub MCP, and tool-level calls, not via a dedicated skill.
- *No "codex dispatch governor"* — `agent/codex_runtime.py` and
  `agent/codex_responses_adapter.py` exist but there is no orchestration
  layer exposed as a skill.

---

## 5. Existing agents

**There are no agent definition files in this repo.** The codebase
treats "agents" as runtime objects (`AIAgent` in `run_agent.py`,
subagent profiles, kanban worker profiles) rather than as static
markdown agent definitions of the `.claude/agents/*.md` shape.

The roles closest to "agents" that exist on disk are **skills with
role-shaped prompts**:

| Skill path | Role it plays |
|---|---|
| `skills/enterprise-council/orchestrator/SKILL.md` | Council orchestrator (`enterprise-orchestrator`) |
| `skills/enterprise-council/judge/SKILL.md` | Validator / second-opinion (`enterprise-judge`) |
| `skills/enterprise-council/monitor/SKILL.md` | Post-run improvement-proposal writer (`enterprise-monitor`) |
| `skills/enterprise-council/finance/SKILL.md` | Domain leaf |
| `skills/enterprise-council/hr/SKILL.md` | Domain leaf |
| `skills/enterprise-council/customer-service/SKILL.md` | Domain leaf |
| `skills/enterprise-council/operations/SKILL.md` | Domain leaf |
| `skills/enterprise-council/sales/SKILL.md` | Domain leaf |
| `skills/devops/kanban-orchestrator/SKILL.md` | Decomposition playbook for orchestrator profiles |
| `skills/devops/kanban-worker/SKILL.md` | Worker lifecycle for kanban worker profiles |
| `skills/autonomous-ai-agents/hermes-agent/SKILL.md` | Self-knowledge skill ("how to work with muse") |
| `skills/autonomous-ai-agents/claude-code/SKILL.md` | How muse drives Claude Code |
| `skills/autonomous-ai-agents/codex/SKILL.md` | How muse drives Codex |
| `skills/autonomous-ai-agents/opencode/SKILL.md` | How muse drives OpenCode |

There are also dynamic profile-based "agents" defined per user under
`~/.hermes/` (configured via `muse profile`); these are not files
in this repo.

---

## 6. Existing skills (inventory by category)

> Counts are of `SKILL.md` files at audit time.

### `skills/` (bundled, active by default)

| Category | Skill count | Notable members |
|---|---|---|
| `apple/` | 5 | apple-notes, apple-reminders, findmy, imessage, macos-computer-use |
| `autonomous-ai-agents/` | 5 | claude-code, codex, hermes-agent, kanban-codex-lane, opencode |
| `creative/` | 19+ | architecture-diagram, ascii-art, baoyu-*, claude-design, comfyui, excalidraw, manim-video, p5js, popular-web-designs, etc. |
| `data-science/` | 1 | jupyter-live-kernel |
| `devops/` | 3 | **kanban-orchestrator**, **kanban-worker**, **webhook-subscriptions** |
| `dogfood/` | 1 | dogfood (+ references, templates) |
| `email/` | 1 | himalaya |
| `enterprise-council/` | 8 | orchestrator, judge, monitor, finance, hr, customer-service, operations, sales (+shared) |
| `gaming/` | 2 | minecraft-modpack-server, pokemon-player |
| `github/` | 5 | codebase-inspection, github-auth, github-code-review, github-issues, github-pr-workflow, github-repo-management |
| `media/` | 5 | gif-search, heartmula, songsee, spotify, youtube-content |
| `mcp/` | 1 | native-mcp |
| `mlops/` | 2 (active SKILL.md) + many DESCRIPTION.md placeholders | huggingface-hub |
| `note-taking/` | 1 | obsidian |
| `productivity/` | 8 | airtable, google-workspace, linear, maps, nano-pdf, notion, ocr-and-documents, powerpoint, teams-meeting-pipeline |
| `red-teaming/` | 1 | godmode |
| `research/` | 5 | arxiv, blogwatcher, llm-wiki, polymarket, research-paper-writing |
| `smart-home/` | 1 | openhue |
| `social-media/` | 1 | xurl |
| `software-development/` | 11 | debugging-hermes-tui-commands, **hermes-agent-skill-authoring**, node-inspect-debugger, plan, python-debugpy, requesting-code-review, spike, **subagent-driven-development**, systematic-debugging, test-driven-development, writing-plans |
| `yuanbao/` | 1 | yuanbao |
| `index-cache/` | — | JSON indices (Anthropic, marketplace, LobeHub, OpenAI). |

### `optional-skills/` (shipped, off by default)

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
| `research/` | 10 | bioinformatics, darwinian-evolver, domain-intel, drug-discovery, duckduckgo-search, gitnexus-explorer, osint-investigation, parallel-cli, qmd, scrapling, searxng-search |
| `security/` | 3 | 1password, oss-forensics, sherlock |
| `software-development/` | 1 | rest-graphql-debug |
| `web-development/` | 1 | page-agent |

---

## 7. Existing command surfaces

### 7.1 muse CLI (`muse …`)
Implemented through `hermes_cli/main.py` (509 KB) and dispatch table
`hermes_cli/commands.py:CommandDef` / `_build_command_lookup`.
Selected entry points visible in `commands.py` + neighbouring files:

`muse`, `muse chat`, `muse setup`, `muse model`, `muse config`,
`muse tools`, `muse gateway`, `muse cron`, `muse webhook`,
`muse kanban`, `muse profile`, `muse skills`, `muse plugins`,
`muse doctor`, `muse claw migrate`, `muse update`, `muse logs`,
`muse goals`, `muse mcp`, `muse voice`, `muse web`, plus many
debug / dev subcommands (`muse debug …`, `muse dump`, etc.).

### 7.2 Interactive in-session slash commands
- Built-in slashes registered in `cli.py` / `gateway/run.py` (e.g.
  `/help`, `/model`, `/rollback`, `/skills`, `/skill <name>`, etc.).
- **Dynamic `/skill-name` map** built by
  `agent/skill_commands.scan_skill_commands()` from every SKILL.md
  found in `skills/`, `optional-skills/`, and `~/.hermes/skills/`.
  Wired into:
  - CLI completer (`hermes_cli/commands.py:SlashCommandCompleter`)
  - Telegram menu (`telegram_menu_commands`)
  - Discord slash commands (`discord_skill_commands*`)
  - Slack manifest / subcommand map (`slack_app_manifest`,
    `slack_subcommand_map`)

### 7.3 Gateway platform endpoints
- `gateway/platforms/{telegram,discord,slack,whatsapp,signal,matrix,
  homeassistant,email,sms,dingtalk,wecom,weixin,feishu,qqbot,
  bluebubbles,yuanbao,webhook,api_server, …}/`

### 7.4 TUI surfaces
- `ui-tui/` (Ink/React) + `tui_gateway/` (Python JSON-RPC backend).
- `muse --tui` launches the Ink frontend.

### 7.5 Embedded web dashboard
- `hermes_cli/web_server.py` (178 KB) — separate from the gateway,
  used for kanban / achievements / example-dashboard plugin UIs.

### 7.6 MCP server
- `mcp_serve.py` — muse can expose its tools over MCP.

### 7.7 ACP server
- `acp_adapter/`, `acp_registry/` — VS Code / Zed / JetBrains.

---

## 8. Existing local tool capabilities

Tool discovery happens via `tools/registry.py` (imported by every tool
file at import time) and is surfaced through `model_tools.py` and
`toolsets.py`. Concrete capabilities currently in tree (selected):

- **Terminal backends** (`tools/environments/`): local, Docker, SSH,
  Singularity, Modal, Daytona, Vercel Sandbox.
- **Browser**: `plugins/browser/{browser_use,browserbase,firecrawl}`,
  `agent/browser_provider.py`.
- **Web search**: `plugins/web/{brave_free,ddgs,exa,firecrawl,
  parallel,searxng,tavily}`, `agent/web_search_provider.py`.
- **Image gen**: `plugins/image_gen/{openai,openai-codex,xai}`,
  `agent/image_gen_provider.py`.
- **Video gen**: `plugins/video_gen/{fal,xai}`,
  `agent/video_gen_provider.py`.
- **Memory providers**: see §3.10.
- **Observability**: `plugins/observability/langfuse/`.
- **GitHub**: `plugins/github_assistant/`,
  `skills/github/*` (auth, code-review, issues, PR workflow,
  repo-management, codebase-inspection).
- **Skill management** tool: `tools/skills_tool.py` (referenced via
  `agent/skill_commands.py:60`).
- **Todo / clarify / execute_code / delegate_task** agent-level
  tools (per `AGENTS.md:307` and `website/docs/.../features/tools.md`).
- **LSP / debugger**: `agent/lsp/`, plus skills
  `software-development/node-inspect-debugger`,
  `software-development/python-debugpy`.
- **Toolset composition**: `toolsets.py:_HERMES_CORE_TOOLS` is the
  default bundle; per-platform toolsets layer on top.

---

## 9. Risks and blockers

1. **Premise mismatch (HIGH).** Phase 1 assumes a `.claude/agents/`
   directory full of agent markdown files. None of that exists. Phase 1
   as written would either invent fictional sources or silently
   reinterpret the brief. The path forward is one of:
   - (a) Treat `skills/enterprise-council/` as the existing council
     baseline and *rename / extend* it into the proposed
     `aos-full-agent-team`.
   - (b) Author the proposed agents **from scratch** as muse skills
     under `skills/` (skipping the `.claude/agents` intermediate
     entirely, since muse' skill dispatch already does what those
     files would do).
   - (c) Import a known external `.claude/agents/*.md` collection
     into `.claude/agents/` first, then convert. The brief does not
     point at a source repo for these agents — see §11.
2. **Naming-drift fix is impossible as written.** `CLAUDE.md` does not
   exist, and neither `contrarian-red-flag-analyst` nor
   `contrarian-reviewer` is referenced anywhere. The "trivial typo
   fix" allowance in Phase 0 therefore yields no change. Record this
   for Phase 1 to re-scope.
3. **`hermes-agent-dev` skill is missing but referenced.**
   `agent/background_review.py:15` and `agent/system_prompt.py:7`
   both point at `references/self-improvement-loop.md` inside a
   `hermes-agent-dev` skill that is not on disk. This is a real,
   pre-existing latent doc-link bug, not introduced by the
   orchestration project. Phase 1's `self-improvement-loop` skill
   work should fix this dangling reference at the same time.
4. **Massive `cli.py` (14 k LOC) and `gateway/run.py` (18 k LOC).**
   Any new orchestration command surface that touches these files
   risks merge pain. Prefer adding new dispatch via
   `hermes_cli/commands.py:CommandDef` and `agent/skill_commands.py`
   rather than editing the megafiles directly.
5. **No persistent decision-ledger primitive.** `hermes_state.py`
   (138 KB) is SQLite-backed and could host a ledger table, but the
   schema must be designed before any skill that *writes* ledger
   entries can land.
6. **Profile/specialist roster is user-configured.** Per
   `skills/devops/kanban-orchestrator/SKILL.md`, the kanban
   dispatcher does not know what profiles exist on a given machine
   and *silently drops* tasks routed to an unknown assignee. Any
   council orchestration that assumes a fixed specialist roster will
   misroute on real users' machines. Skills must discover the
   roster via `muse profile list` / `kanban_list(...)` (already
   the documented pattern).
7. **Voice / TUI / web-dashboard / ACP / MCP surfaces are
   independent.** Adding orchestration to one does not automatically
   add it to the others. Plan the rollout per surface.
8. **Branding & licensing.** This is Nous Research's MIT-licensed
   public repo. The Phase 0+ "private local-first developer command
   center" framing is fine for in-repo development, but the resulting
   skills will be visible to anyone who clones it; do not embed
   private workflows or secrets.

---

## 10. Recommended phase dependencies

> Concrete, ordered, non-prescriptive. Each item is a *should-precede*
> dependency.

1. **Phase 0.5 — Re-scope Phase 1's input set.** Decide which of
   (a)/(b)/(c) from §9.1 to take. Get user confirmation before any
   skill files are created. Phase 1 as currently written cannot be
   executed verbatim.
2. **Skill authoring convention pass.** Use
   `skills/software-development/hermes-agent-skill-authoring/SKILL.md`
   as the template for every new orchestration skill so they pass the
   in-repo validator.
3. **Decision-ledger schema design** (before any skill that writes
   ledger entries). Should integrate with `hermes_state.py`
   (`SessionDB`) and surface via the embedded web dashboard.
4. **Model-router skill design** must wrap the existing
   `hermes_cli/model_switch.py` + `agent/model_metadata.py` instead
   of duplicating their logic. Surface as a thin prompt layer; let
   the CLI/plugin remain the source of truth.
5. **GitHub-publisher skill** should wrap the existing
   `plugins/github_assistant/`, `skills/github/*`, and GitHub MCP
   tools, not reimplement publishing.
6. **Self-improvement-loop skill** must reconcile with
   `agent/background_review.py`'s existing
   `spawn_background_review_thread` hook and replace the dangling
   `hermes-agent-dev` doc reference.
7. **AOS council master skill** (`aos-full-agent-team`) should follow
   the `skills/enterprise-council/orchestrator/` pattern, which is
   already proven to compose multiple sub-skills inside muse
8. **Naming reconciliation memo.** Before creating any
   `contrarian-*` skill, decide whether the proposed
   `contrarian-reviewer` and `contrarian-red-flag-analyst` are two
   roles, one role with an alias, or one role full stop. The brief
   describes an alias; the repo has no precedent either way.

---

## 11. Files likely to be edited by later phases

| Phase | Likely files | Why |
|---|---|---|
| 1 (skill conversion) | `skills/<new-skill>/SKILL.md` (many new dirs), `docs/orchestration/hermes-agent-skill-map.md` (new), `docs/orchestration/phase-0-evidence-audit.md` (cross-link) | Author council skills. |
| 1 | `CLAUDE.md` (would need to be **created**), `.claude/agents/` (would need to be **created**) — *only if* path (c) from §9.1 is chosen | Hosting source agents. |
| 1 | `agent/background_review.py:15`, `agent/system_prompt.py:7` | Replace dangling `hermes-agent-dev` reference once `self-improvement-loop` skill ships. |
| 2 (decision ledger) | `hermes_state.py`, `hermes_cli/web_server.py`, new `tools/decision_ledger_tool.py`, new `skills/decision-ledger/` | Persist + surface ledger. |
| 2/3 (model routing) | `hermes_cli/model_switch.py`, `hermes_cli/models.py`, `agent/model_metadata.py`, new `skills/model-router/` | Wrap existing logic in a skill without forking it. |
| 2/3 (GitHub publishing) | `plugins/github_assistant/`, `skills/github/*`, new `skills/github-publisher/` | Compose existing surfaces. |
| 3 (AI improvement radar) | `agent/background_review.py`, new `skills/ai-improvement-radar/`, new cron-job templates in `cron/jobs.py` examples | Periodic harvest + report. |
| 3 (developer UX command center) | `cli.py` (light), `hermes_cli/commands.py`, `ui-tui/src/*`, new `skills/developer-ux-command-center/` | New top-level slash plus TUI page. |
| 4 (orchestration docs) | `docs/orchestration/*`, `website/docs/user-guide/features/*` | Public docs. |
| 4 (codex dispatch governor) | `agent/codex_runtime.py`, `agent/codex_responses_adapter.py`, new `skills/codex-dispatch-governor/` | Wrap codex runtime. |
| All | `hermes_cli/commands.py` (CommandDef table), `agent/skill_commands.py` (cache), `gateway/run.py` (only if a slash needs gateway-specific behaviour) | Slash registration. |

---

## 12. Naming-drift check (per Phase 0 task §3)

| Check | Result |
|---|---|
| `CLAUDE.md` references `contrarian-red-flag-analyst`? | **N/A — `CLAUDE.md` does not exist.** |
| Actual file is `contrarian-reviewer.md`? | **No — no such file in repo.** |
| `contrarian-red-flag-analyst` referenced anywhere? | No matches. |
| `contrarian-reviewer` referenced anywhere? | No matches. |
| Closest hit | `AGENTS.md:987` — unrelated prose phrase "red flag" in a paragraph about merge regressions. |

**No fix applied in Phase 0.** Phase 1 should treat the contrarian
agent as a **new skill** rather than a rename, and decide whether to
add a `contrarian-red-flag-analyst` alias skill on top.

---

## 13. Validation commands used

The audit relied on these read-only commands (all safe; none mutate state):

```bash
find . -maxdepth 3 -name "CLAUDE.md" -o -name ".claude"
find .claude -maxdepth 3 -type f 2>/dev/null         # no output (dir absent)
find skills -maxdepth 3 -type f | sort
find optional-skills -maxdepth 3 -type f | sort
find docs -maxdepth 4 -type f | sort
ls -la .claude 2>/dev/null || echo "no .claude dir"   # confirmed absent
ls -la hermes_cli agent gateway scripts cron
grep -R "contrarian-red-flag-analyst|contrarian-reviewer|orchestration|model-router|decision-ledger" \
  -rn --include="*.md" .
grep -R "aos-council-director|evidence-architect|principal-systems-architect|\
product-experience-architect|commercial-strategist|assurance-risk-director|\
delivery-scope-controller|codex-dispatch-governor|github-publisher|\
developer-ux-command-center|decision-quality-gate|research-validator|\
ai-improvement-radar|self-improvement-loop" -rn .
find . -name "self-improvement-loop*" -type f
find . -name "*hermes-agent-dev*"
grep -rn "hermes-agent-dev" --include="*.md" .
head -50 agent/skill_commands.py
head -30 toolsets.py
wc -l toolsets.py hermes_cli/commands.py cli.py gateway/run.py
head -100 skills/autonomous-ai-agents/hermes-agent/SKILL.md
head -40 skills/devops/kanban-orchestrator/SKILL.md
head -25 skills/enterprise-council/{DESCRIPTION,orchestrator/SKILL,judge/SKILL}.md
grep -n "^def |^class " hermes_cli/commands.py
grep -n "skill_commands|_skill_commands|/skill-name|invoke_skill" \
  hermes_cli/commands.py cli.py agent/skill_commands.py
```

All commands returned the data summarised above. No write or destructive
operation was issued.
