# Phase 00 — Baseline Audit

> Factual snapshot of the Hermes repo before any orchestration-command-center
> work begins. No code changes were made in this phase.
>
> Audited tree: `/home/user/hermes-agent` on branch
> `claude/hermes-baseline-audit-fKQOi`, working tree clean.
> Project version (pyproject.toml): `hermes-agent 0.14.0`, Python `>=3.11`.

---

## 1. Executive Verdict

Hermes today is **a very mature, multi-surface AI agent framework** that
already implements roughly 70 % of what a "10/10 private local-first
developer orchestration command center" requires — but the pieces are
scattered across `cli.py`, `gateway/`, `cron/`, `hermes_cli/kanban*.py`,
`enterprise/`, the `skills/devops/kanban-*` skill pair, the
`skills/enterprise-council/*` set, and `agent/delegate_tool` / `agent/curator`.
There is **no single "orchestration" surface** that ties scheduled work,
kanban tasks, sub-agent delegation, GitHub events, webhook triggers, model
routing and decision history into one private, locally hosted command-and-
control plane.

Concrete gaps:

- No `.claude/` directory and no `CLAUDE.md`. The project is not configured
  as a Claude-Code-style host; all agent state lives in `~/.hermes/` and the
  custom slash-command registry (`hermes_cli/commands.py`).
- No `docs/orchestration/` content prior to this phase. The closest existing
  docs are `docs/hermes-local-orchestrator.md` (Android client) and
  `docs/github-integration.md` (plugin + MCP wiring).
- No explicit **decision ledger** abstraction — `audit_log` and
  `enterprise/audit.py` exist, but a unified, queryable per-task decision
  record (model used, prompt, tool calls, cost, verdict) is missing.
- No explicit **model router** module. `smart_model_routing` exists as a
  config section but there is no first-class API/CLI to declare per-task
  routing policy ("use Sonnet for code review, Haiku for triage, local Qwen
  for offline").
- No standing **worker** identity separate from kanban dispatcher
  spawn-on-demand. Long-lived, named workers with their own toolsets, model
  pin and queue do not exist as a top-level concept.
- The pieces that exist (kanban, cron, webhooks, enterprise-council,
  delegate_task) interact pairwise at best; there is no single "command
  center" view that shows _"what is Hermes doing right now, and why,
  across every surface?"_

The good news: every primitive needed to build that command center is
already in the tree (kanban event log, cron scheduler, webhook gateway,
delegate_task, profile isolation, skills, Curator, ACP adapter, TUI, web
dashboard hooks). Later phases are integration work, not greenfield.

---

## 2. Current Architecture

```
hermes-agent/                       (root)
├── run_agent.py        4 137 LOC   AIAgent class — synchronous tool loop
├── cli.py             14 528 LOC   HermesCLI — interactive terminal UI
├── model_tools.py        923 LOC   discover_builtin_tools, handle_function_call
├── toolsets.py           866 LOC   29 named toolsets + _HERMES_CORE_TOOLS
├── batch_runner.py                 Parallel trajectory generation
├── trajectory_compressor.py        Conversation compression for training
├── hermes_state.py                 SQLite + FTS5 session store
├── hermes_logging.py               agent.log / errors.log / gateway.log
├── hermes_constants.py             get_hermes_home() / display_hermes_home()
├── mcp_serve.py                    MCP server entry
├── mini_swe_runner.py              SWE-bench / lite-agent loop
│
├── agent/                          provider adapters + memory + curator
│   ├── conversation_loop.py        230 KB — main streaming loop
│   ├── anthropic_adapter.py        + bedrock_adapter, gemini_*, codex_*
│   ├── auxiliary_client.py         230 KB — per-task side-LLM resolution
│   ├── credential_pool.py           87 KB — multi-key rotation
│   ├── curator.py                   74 KB — skill lifecycle review loop
│   ├── memory_provider.py          MemoryProvider ABC + manager
│   ├── prompt_builder.py            KANBAN_GUIDANCE injected here
│   ├── skill_commands.py           Slash-command skill loader (CLI + gateway)
│   ├── system_prompt.py            Prompt assembly
│   └── …                           context_compressor, error_classifier, …
│
├── tools/                          ~70 tool implementations
│   ├── registry.py                 register() auto-discovery
│   ├── delegate_tool.py            delegate_task / sub-agent spawn
│   ├── kanban_tools.py             kanban_show/list/complete/block/…
│   ├── cronjob_tools.py            cronjob create/list/update tool
│   ├── terminal_tool.py            background, notify_on_complete
│   ├── send_message_tool.py        Cross-platform delivery
│   ├── computer_use/               macOS background desktop control
│   ├── browser_*.py                CDP + Camofox + dialog
│   ├── mcp_tool.py + mcp_oauth*    MCP client + OAuth
│   ├── skills_*.py                 Hub, sync, manager, usage, provenance
│   └── environments/               local, docker, ssh, modal, daytona,
│                                   singularity, vercel_sandbox
│
├── gateway/                        Messaging fan-out (≈ 1.3 MB of code)
│   ├── run.py            (856 KB) Main runner, command bypass guards
│   ├── session.py        ( 57 KB) Session lifecycle
│   ├── config.py         ( 94 KB) Per-platform settings
│   ├── status.py                   Process locks, profile/token scoping
│   ├── stream_consumer.py          Streaming event ingestion
│   ├── platforms/                  telegram, discord, slack, whatsapp,
│   │                               signal, matrix, mattermost, email,
│   │                               sms, dingtalk, wecom, weixin, feishu,
│   │                               qqbot, bluebubbles, yuanbao, webhook,
│   │                               api_server, …
│   └── builtin_hooks/              Empty (extension point)
│
├── hermes_cli/                     CLI subcommands + setup wizard
│   ├── main.py         (508 KB)   argparse root + _apply_profile_override
│   ├── commands.py     ( 75 KB)   COMMAND_REGISTRY (single source of truth)
│   ├── kanban.py       (104 KB)   `hermes kanban …` verbs
│   ├── kanban_db.py    (250 KB)   SQLite board + claim TTL + dispatcher
│   ├── kanban_decompose.py / kanban_specify / kanban_swarm /
│   │   kanban_diagnostics
│   ├── cron.py                    `hermes cron …` verbs
│   ├── webhook.py                 `hermes webhook …` verbs
│   ├── plugins.py / plugins_cmd.py PluginManager + CLI
│   ├── skills_hub.py   ( 61 KB)   Skills Hub client
│   ├── curator.py                 `hermes curator …` verbs
│   ├── profiles.py                `hermes -p <name> …` multi-instance
│   ├── doctor.py       ( 88 KB)   Diagnostics
│   ├── setup.py        (144 KB)   Setup wizard
│   ├── tools_config.py (134 KB)   curses tool picker
│   ├── web_server.py   (177 KB)   `hermes dashboard` + /api/pty
│   ├── auth*, config.py (240 KB), gateway.py (225 KB)
│   └── …
│
├── plugins/                        Repo-shipped plugins (run-time discovered)
│   ├── github_assistant/           Native GitHub plugin (8 tools, gated)
│   ├── kanban/                     dashboard/ web UI + systemd/ service
│   ├── memory/                     honcho, mem0, supermemory, byterover,
│   │                               hindsight, holographic, openviking,
│   │                               retaindb
│   ├── model-providers/            29 entries: anthropic, openai-codex,
│   │                               gemini, copilot, copilot-acp,
│   │                               openrouter, novita, nvidia, nous,
│   │                               bedrock, azure-foundry, alibaba,
│   │                               alibaba-coding-plan, deepseek, minimax,
│   │                               kimi-coding, stepfun, zai, xai,
│   │                               xiaomi, arcee, kilocode, gmi,
│   │                               opencode-zen, ollama-cloud,
│   │                               qwen-oauth, huggingface, ai-gateway,
│   │                               custom
│   ├── web/                        brave_free, ddgs, exa, firecrawl,
│   │                               parallel, searxng, tavily
│   ├── browser/                    browser_use, browserbase, firecrawl
│   ├── platforms/                  irc, teams, google_chat, line, simplex
│   ├── image_gen/                  openai, openai-codex, xai
│   ├── video_gen/                  fal, xai
│   ├── observability/              langfuse
│   ├── disk-cleanup, spotify, teams_pipeline, google_meet,
│   │   hermes-achievements, context_engine, example-dashboard
│   └── …
│
├── cron/                           Built-in scheduler
│   ├── jobs.py          ( 45 KB)  Job store, parse_schedule, get_due_jobs
│   └── scheduler.py     ( 84 KB)  Tick loop, lock file, catch-up + grace
│
├── enterprise/                     Enterprise Council runtime
│   ├── council.py                  plan() + dispatch(planned, runner)
│   ├── policy.py                   classify(task) → Risk LOW/MEDIUM/HIGH
│   ├── judge.py                    cross_check verdicts
│   ├── monitor.py                  Long-running observation
│   ├── audit.py                    AuditEvent log
│   ├── secrets.py                  fetch_secret + redaction
│   └── adapters/                   cs, finance, hr, ops, sales
│
├── acp_adapter/                    Agent Client Protocol (Zed/VS Code/JB)
│   ├── server.py        ( 81 KB)  ACP server
│   ├── tools.py         ( 57 KB)
│   ├── session.py, edit_approval.py, events.py, permissions.py, auth.py
│   └── entry.py
├── acp_registry/                   Single agent.json + icon for ACP discovery
│
├── tui_gateway/                    JSON-RPC backend for Ink TUI
│   ├── server.py        (241 KB)  Method/event catalog
│   ├── slash_worker.py             Persistent slash subprocess
│   └── transport.py, ws.py, event_publisher.py
│
├── ui-tui/                         Ink (React) terminal UI
│   └── src/{app,components,hooks,lib,protocol,…}/
│
├── apps/                           Native companions
│   └── android/                    Kotlin + Compose thin client
│       ├── app/, build.gradle.kts, gradle/, gradlew
│       └── docs/ARCHITECTURE.md   (no-embedded-Python decision)
│
├── skills/                         97 SKILL.md files (built-in)
├── optional-skills/                81 SKILL.md files (opt-in install)
├── tests/                          1 143 test_*.py files across 36 subdirs
├── scripts/                        install.sh (82 KB), install.ps1 (107 KB),
│                                   release.py, run_tests.sh,
│                                   benchmark_browser_eval.py, …
└── docs/                           4 files: github-integration.md,
                                    hermes-local-orchestrator.md, kanban
                                    v1 spec (PDF), 2 plans/*.md
```

Notable cross-cutting facts:

- **Profile-aware paths everywhere.** `get_hermes_home()` /
  `display_hermes_home()` are the single source of truth; `~/.hermes` is
  default but `-p name` shifts to `~/.hermes/profiles/<name>`.
- **Cache-preserving slash commands.** Skill / tool / memory mutations
  default to deferred invalidation with an opt-in `--now`.
- **Synchronous delegate_task.** Sub-agents run synchronously inside the
  parent's turn; for durable work the project routes through cron or
  `terminal(background=True, notify_on_complete=True)`.

---

## 3. Existing Skills

`skills/` ships **97** `SKILL.md` files; `optional-skills/` ships **81**
more. Categories (from `skills/<cat>/`):

`apple`, `autonomous-ai-agents`, `creative`, `data-science`, `devops`,
`diagramming`, `dogfood`, `domain`, `email`, `enterprise-council`,
`gaming`, `gifs`, `github`, `index-cache`, `inference-sh`, `mcp`, `media`,
`mlops`, `note-taking`, `productivity`, `red-teaming`, `research`,
`smart-home`, `social-media`, `software-development`, `yuanbao`.

Skills directly relevant to orchestration / command-center work:

| Skill | Purpose |
|---|---|
| `devops/kanban-orchestrator` | Decomposition playbook + anti-temptation rules for an orchestrator routing work through Kanban. |
| `devops/kanban-worker` | Worker lifecycle deep-dive (auto-injected as `KANBAN_GUIDANCE`). |
| `devops/webhook-subscriptions` | Webhook trigger guide. |
| `enterprise-council/orchestrator` | One-tap enterprise objective decomposition + dispatch. |
| `enterprise-council/{finance,hr,customer-service,operations,sales}` | Leaf domain agents. |
| `enterprise-council/judge` | Cross-check verdict skill. |
| `enterprise-council/monitor` | Long-running observation skill. |
| `autonomous-ai-agents/{hermes-agent,claude-code,codex,opencode}` | Cross-agent orchestration notes. |
| `autonomous-ai-agents/kanban-codex-lane` | Run Codex as an isolated implementation lane from a Hermes Kanban worker. |
| `software-development/{plan,spike,subagent-driven-development,writing-plans}` | Planning and sub-agent discipline. |
| `software-development/systematic-debugging`, `test-driven-development`, `requesting-code-review` | Per-discipline procedural memory. |
| `github/{codebase-inspection,github-auth,github-code-review,github-issues,github-pr-workflow,github-repo-management}` | Native + MCP GitHub work. |
| `mcp/native-mcp` | Hermes-native MCP setup. |
| `dogfood` | Self-improvement loop (issue taxonomy, dogfood-report template). |

`optional-skills/` mirrors the same category tree with heavier or niche
contents (blockchain, finance, health, full mlops, migration, web-dev,
plus the same autonomous-ai-agents / dogfood / mcp duplicates that ship
"installed-on-demand").

---

## 4. Existing Agents

There is no `.claude/agents/` directory in this repo. Hermes does not use
the Claude-Code agent-definition format. Instead, "agents" in Hermes are
expressed three different ways:

1. **`AIAgent` instances** (`run_agent.py`). The single class behind
   every interactive turn — CLI, gateway, ACP, cron, kanban worker.
   Configurable via ~60 init parameters (provider, model, toolsets,
   credential pool, callbacks, iteration_budget, fallback_model,
   reasoning_config, …).
2. **Delegated sub-agents** via `tools/delegate_tool.py`:
   - `role="leaf"` — focused worker, cannot recursively delegate, cannot
     call `clarify`, `memory`, `send_message`, `execute_code`.
   - `role="orchestrator"` — retains `delegate_task`, bounded by
     `delegation.max_spawn_depth` (default 2) and
     `delegation.max_concurrent_children` (default 3).
3. **Kanban workers** (`plugins/kanban/`, `hermes_cli/kanban*.py`,
   `tools/kanban_tools.py`). Spawned by the dispatcher with
   `HERMES_KANBAN_TASK` pinned, board-isolated, with their own
   `KANBAN_GUIDANCE` system-prompt block and a curated `kanban_*` tool
   subset.
4. **Enterprise Council leaves** (`enterprise/council.py +
   adapters/{cs,finance,hr,ops,sales}.py`). Same Hermes runtime, gated
   by `enterprise.policy.classify()` and observed by
   `enterprise.audit`.

There is no notion of a **named, long-lived "worker" identity** (e.g.
`docker-worker`, `cron-worker`, `researcher`) distinct from the kanban
dispatcher's spawn-on-demand model. Profiles approximate this — each
profile is a fully isolated Hermes — but they are not auto-discovered as
a worker fleet.

---

## 5. Existing Commands

There is no `.claude/commands/` directory. The slash-command registry
lives in `hermes_cli/commands.py` (`COMMAND_REGISTRY: list[CommandDef]`)
and is the single source of truth for CLI dispatch, gateway dispatch,
Telegram `BotCommand` menu, Slack subcommand mapping, autocomplete, and
help text.

The registry currently exposes **~70 canonical slash commands** across
five categories. Selected highlights (full list in `commands.py`):

- **Session:** `/new` (`reset`), `/clear`, `/redraw`, `/history`,
  `/save`, `/retry`, `/undo`, `/title`, `/handoff <platform>`,
  `/branch` (`fork`), `/compress`, `/rollback`, `/snapshot`, `/stop`,
  `/approve`, `/deny`, `/background` (`bg`, `btw`), `/agents`
  (`tasks`), `/queue`, `/steer`, `/goal`, `/subgoal`, `/status`,
  `/sethome`, `/resume`, `/sessions`, `/restart`, `/topic`.
- **Configuration:** `/config`, `/model`, `/codex-runtime`,
  `/personality`, `/statusbar` (`sb`), `/verbose`, `/footer`, `/yolo`,
  `/reasoning`, `/fast`, `/skin`, `/indicator`, `/voice`, `/busy`.
- **Tools & Skills:** `/tools`, `/toolsets`, `/skills`, `/bundles`,
  `/cron`, `/curator`, `/kanban`, `/reload`, `/reload-mcp`,
  `/reload-skills`, `/browser`, `/plugins`.
- **Info:** `/commands`, `/help`, `/usage`, `/insights`, `/platforms`
  (`gateway`), `/platform`, `/copy`, `/paste`, `/image`, `/update`,
  `/debug`, `/whoami`, `/profile`, `/gquota`.
- **Exit:** `/quit` (`exit`).

CLI subcommands (`hermes <verb>`, also routed through `hermes_cli/main.py`):

`hermes`, `hermes chat`, `hermes model`, `hermes tools`, `hermes config`,
`hermes gateway`, `hermes setup`, `hermes claw migrate`, `hermes update`,
`hermes doctor`, `hermes cron`, `hermes webhook`, `hermes kanban`,
`hermes curator`, `hermes plugins`, `hermes profile`, `hermes skills`,
`hermes memory`, `hermes logs`, `hermes dashboard`, `hermes mcp`,
`hermes-acp`, plus plugin-registered subcommands via
`PluginContext.register_cli_command(...)`.

Skill slash commands (`/<skill-name>`) are scanned from
`~/.hermes/skills/` at startup via
`agent/skill_commands.py::scan_skill_commands()` and injected as a
*user* message at invocation (deliberately, to preserve prompt-cache
prefix integrity).

---

## 6. Existing Local Tool Support

`tools/registry.py` is the single registration surface; ~70 tool modules
in `tools/` auto-register on import. **29 toolsets** are defined in
`toolsets.py::TOOLSETS`:

`browser`, `clarify`, `code_execution`, `cronjob`, `debugging`,
`delegation`, `discord`, `discord_admin`, `feishu_doc`, `feishu_drive`,
`file`, `homeassistant`, `image_gen`, `kanban`, `memory`, `messaging`,
`moa`, `rl`, `safe`, `search`, `session_search`, `skills`, `spotify`,
`terminal`, `todo`, `tts`, `video`, `vision`, `web`, `yuanbao`.

`_HERMES_CORE_TOOLS` is the default bundle most platforms inherit from
(`web_search`, `web_extract`, `terminal`, `process`, `read_file`,
`write_file`, `patch`, `search_files`, `vision_analyze`,
`image_generate`, `skills_list`, `skill_view`, `skill_manage`, full
`browser_*` set, `text_to_speech`, `todo`, `memory`, `session_search`,
`clarify`, `execute_code`, `delegate_task`, `cronjob`, `send_message`,
`ha_*`, `kanban_*`, `computer_use`).

Terminal backends (`tools/environments/`): `local`, `docker`, `ssh`,
`modal` (+ `managed_modal`), `daytona`, `singularity`, `vercel_sandbox`.
Each implements a uniform interface; the agent picks one per session.

MCP support: `mcp_serve.py` runs Hermes as an MCP server; `tools/mcp_tool.py`
+ `tools/mcp_oauth*.py` let Hermes consume external MCP servers (config
under `mcp_servers:` in `~/.hermes/config.yaml`).

Local AuxClient routing: `agent/auxiliary_client.py` resolves per-task
side-LLM model/provider/base_url overrides for curator, vision,
embedding, title-generation, session-search, etc. (`auxiliary:` config
section). This is the closest current analogue to a "model router" but
it is a configuration tree, not a runtime decision engine.

---

## 7. Existing Gateway / API / TUI Support

**Gateway (`gateway/`):**
- One `gateway.run` process fans out to every configured platform
  adapter in `gateway/platforms/` (telegram, discord, slack, whatsapp,
  signal, matrix, mattermost, email, sms, dingtalk, wecom, weixin,
  feishu, qqbot, bluebubbles, yuanbao, webhook, api_server, plus
  plugin-registered platforms: irc, teams, google_chat, line, simplex).
- Two-layer message guard for active-session safety
  (`gateway/platforms/base.py` queues; `gateway/run.py` intercepts
  control commands).
- Hooks: `pre_tool_call`, `post_tool_call`, `pre_llm_call`,
  `post_llm_call`, `on_session_start`, `on_session_end`.
- DM-pairing, sticker cache, mirror, runtime footer, channel
  directory, platform registry, memory monitor.

**Web dashboard (`hermes_cli/web_server.py`, 177 KB):**
- `hermes dashboard` boots a FastAPI + uvicorn SPA. Routes include
  `/api/pty?token=…` (WebSocket → real `hermes --tui` via
  `hermes_cli/pty_bridge.py`), REST for sessions/logs/profiles, and
  embedded plugin dashboards. Auth via ephemeral `_SESSION_TOKEN`.
- Plugin dashboards: `plugins/kanban/dashboard/`,
  `plugins/example-dashboard/`, etc. — `dashboard/manifest.json`
  is package-data.

**TUI:**
- `ui-tui/` is an Ink (React) terminal UI activated with
  `hermes --tui` (or `HERMES_TUI=1`). Python side
  `tui_gateway/server.py` (241 KB) speaks newline-delimited JSON-RPC
  over stdio. Persistent `_SlashWorker` subprocess handles slash
  commands without blocking the loop. Same TUI is embedded inside
  `hermes dashboard /chat` via the PTY bridge.

**ACP (`acp_adapter/`):**
- `hermes-acp` entry point. Implements Agent Client Protocol over
  stdio for Zed / VS Code / JetBrains; full server in `server.py`
  (81 KB) + `tools.py` (57 KB), including edit approvals, sessions,
  events, OAuth-style auth and per-tool permissions.
- `acp_registry/agent.json` packages a uvx-installable manifest for
  discovery (`hermes-agent[acp]==0.14.0` → `hermes-acp`).

**REST API:**
- `gateway/platforms/api_server.py` (mentioned in AGENTS.md). The
  `webhook` platform and the dashboard's REST surface together cover
  most "POST a prompt, get a session reply" use-cases. There is no
  dedicated "Hermes Orchestration API" doc.

---

## 8. Existing GitHub / Kanban / Cron Support

### GitHub
- **Native plugin:** `plugins/github_assistant/` registers eight
  tools (`github_audit_repo`, `github_get_repo_file`,
  `github_list_branches`, `github_list_issues`, `github_list_pull_requests`,
  `github_get_pull_request`, `github_create_issue`,
  `github_comment_on_issue_or_pr`). Gated by `github.enabled`
  (default false), `github.allow_writes` (default false), and a
  per-repo `github.allowed_repositories` allowlist. Token redaction
  in errors + global `RedactingFormatter`. Documented in
  `docs/github-integration.md`.
- **MCP server option:** `mcp_servers.github` block in
  `~/.hermes/config.yaml` runs `@modelcontextprotocol/server-github`.
  Tools appear under `github.*` prefix; coexists with the native
  plugin without name collisions.
- **Webhook ingest:** `hermes webhook subscribe …` route ingests
  GitHub events into the gateway, with HMAC auth + delivery
  targeting. Implemented via `hermes_cli/webhook.py`.

### Kanban
- **Durable SQLite board** in `hermes_cli/kanban_db.py` (250 KB).
- **CLI verbs** (`hermes kanban …`): `init`, `create`, `list` (alias
  `ls`), `show`, `assign`, `link`, `unlink`, `comment`, `complete`,
  `block`, `unblock`, `archive`, `tail`, `watch`, `stats`, `runs`,
  `log`, `assignees`, `heartbeat`, `notify-*`, `dispatch`, `daemon`,
  `gc`, plus boards subverbs (`boards list/create/rm/switch/show/
  rename/set-default-workdir`).
- **Dispatcher** runs inside the gateway by default
  (`kanban.dispatch_in_gateway: true`) every ~60 s: reclaims stale
  claims, promotes ready tasks, atomically claims, spawns assigned
  profiles. Standalone deployment via
  `plugins/kanban/systemd/hermes-kanban-dispatcher.service`.
- **Worker toolset:** `tools/kanban_tools.py` exposes
  `kanban_show`, `kanban_complete`, `kanban_block`,
  `kanban_heartbeat`, `kanban_comment`, `kanban_create`, `kanban_link`.
  Profiles that explicitly enable the `kanban` toolset get
  `kanban_list` and `kanban_unblock`.
- **Dashboard:** `plugins/kanban/dashboard/` (web UI) +
  `plugin_api.py`.
- **Isolation model:** board is the hard boundary
  (`HERMES_KANBAN_BOARD`); tenant is a soft namespace within a
  board. `kanban.failure_limit` (default 2) auto-blocks tasks that
  fail repeatedly. Hallucination warnings on
  `kanban_complete(created_cards=[...])` claims.
- Spec at `docs/hermes-kanban-v1-spec.pdf`.

### Cron
- `cron/jobs.py` (job store) + `cron/scheduler.py` (84 KB tick loop).
- Schedule formats: duration (`30m`, `2h`, `1d`), "every" phrases
  (`every monday 9am`), 5-field cron, ISO timestamp (one-shot).
- Per-job fields: `skills` (preload), `model` / `provider` overrides,
  `script` (Python pre-run, stdout injected into prompt; `no_agent=True`
  turns the script into the entire job), `context_from` (chain
  output of job A into job B's prompt), `workdir` (loads that dir's
  `AGENTS.md`/`CLAUDE.md`), multi-platform delivery
  (`--deliver telegram|discord|slack|sms|email|webhook|local`).
- Hardening: 3-min hard interrupt, half-period catch-up window,
  120 s grace, file lock at `~/.hermes/cron/.tick.lock`.
- `cronjob` agent-callable tool lives in `tools/cronjob_tools.py`.

### Webhook
- `hermes_cli/webhook.py` — `hermes webhook subscribe / list /
  remove / pause / resume`. Routes are HMAC-authed; payloads can be
  templated into prompts (e.g.
  `"PR #{pull_request.number}: {pull_request.title}"`).
- Routes are consumed by the `webhook` platform under
  `gateway/platforms/webhook.py`.

---

## 9. Existing Android / Termux Support

### Termux
- Two extras in `pyproject.toml`:
  - `[termux]` — curated baseline (telegram + cron + cli + pty + mcp
    + honcho + acp).
  - `[termux-all]` — `[termux]` + `[google]` + `[homeassistant]` +
    `[sms]` + `[web]`. Heavier backends still lazy-install through
    `tools/lazy_deps.py`.
- `constraints-termux.txt` and
  `scripts/install_psutil_android.py` cover Android-specific install
  quirks.
- `scripts/install.sh` (82 KB) handles the Termux path. README states
  Termux installs `.[termux]` because `.[all]` pulls Android-incompatible
  voice deps.
- Termux runs the same `hermes`, `hermes gateway`, `hermes cron` as
  Linux/macOS — the gateway can serve `http://127.0.0.1:8080`.

### Android Native App
- `apps/android/` — Kotlin + Jetpack Compose, Material 3, MVVM. A
  **thin client** for a remote or local Hermes backend; not a
  webview, not a desktop-TUI port.
- Three runtime modes (README + `docs/hermes-local-orchestrator.md`):
  1. Remote gateway (VPS / home server). Recommended.
  2. Local Termux gateway on-device (`http://127.0.0.1:8080`).
  3. Mock mode (UI sandbox, no backend).
- Foreground service (`HermesService`) with persistent notification,
  `android:exported="false"`, no intent-filter. Permissions:
  `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`,
  `FOREGROUND_SERVICE_DATA_SYNC`.
- Storage: DataStore Preferences (settings) + `hermes_tasks.json` in
  `filesDir`. No `EncryptedSharedPreferences`, no provider keys
  stored on device.
- Build: `apps/android/app/build/outputs/apk/debug/app-debug.apk` via
  Gradle. CI debug APK at
  `.github/workflows/android-build.yml`.
- Architecture & wire-format doc:
  `apps/android/docs/ARCHITECTURE.md`.
- Explicit "no-embedded-Python" design rationale:
  `docs/hermes-local-orchestrator.md`. The Android app prepares
  structured prompts and hands off to ChatGPT / Codex / Claude Code /
  Claude (clipboard + deep-link) — every external action requires a
  tap.

---

## 10. Missing Features for 10/10 Hermes

Items the audit could **not** find but which a private, local-first
developer orchestration command center needs:

### A. Orchestration data model
- **No unified "task" abstraction across kanban / cron / delegate_task
  / webhook.** Each surface has its own record. There is no
  single `Task` row that says "this work item exists; it was
  triggered by cron job X / webhook Y / agent delegate; it is now in
  worker Z; its decision history is L".
- **No decision ledger.** `enterprise/audit.py` and the kanban event
  log come close, but there is no per-task append-only ledger with
  fields like `{ts, model, provider, prompt_hash, tool_calls, cost,
  verdict, parent_task, child_tasks}` that is queryable across the
  whole system.
- **No replay / time-travel** for a task. Trajectories exist for
  research (`trajectory_compressor.py`) but not as a first-class
  ledger entry tied to operational tasks.

### B. Model router
- `config.yaml` has a `smart_model_routing:` section, but there is
  no `agent/model_router.py` module that an agent or sub-agent can
  query: "given task class X, return provider+model+toolset+budget
  for me right now". `auxiliary:` covers side-LLM tasks but not
  primary turns.
- No way to declare per-task budgets ("don't spend more than $0.10
  on triage").
- No automatic fallback chain on rate-limit or 5xx beyond the
  existing per-agent `fallback_model` parameter.

### C. Worker fleet
- No first-class **worker manifest** (e.g.
  `~/.hermes/workers/<name>.yaml`). The closest substitutes are
  profiles (one Hermes instance per worker) and the kanban dispatcher
  spawn-on-demand. A worker should declare: name, role
  (orchestrator/leaf/specialist), default toolsets, model pin,
  default board / queue, default workdir, allowed skills,
  health-check command.
- No `hermes worker` top-level CLI verb. (There is `hermes profile`,
  which is the existing best fit.)

### D. Single "command center" surface
- The TUI, the web dashboard, and the kanban dashboard each present
  partial views. There is no one screen that shows simultaneously:
  active sessions, queued kanban tasks, scheduled cron jobs that
  fire in the next 24 h, recent webhook deliveries, sub-agents
  currently running, last 50 decision-ledger entries, and live
  Hermes log tail.
- Most state lives in `~/.hermes/` and is accessible (SQLite +
  YAML + JSON) but the integrated view doesn't exist.

### E. Claude-Code-style host integration
- No `CLAUDE.md` at the repo root and no `.claude/` directory.
  Claude Code users dropping into this repo lose project-specific
  guidance (AGENTS.md is read but Claude Code prefers CLAUDE.md
  when both exist; some tooling looks for `.claude/commands/`,
  `.claude/agents/`).
- No `.claude/hooks/` settings; setup-hermes.sh and other
  bootstraps don't register Claude-Code lifecycle hooks.

### F. Local-first guarantees
- **Telemetry posture is unclear.** Plugins include `observability/
  langfuse/` and the dashboard hits the localhost only, but there
  is no `docs/local-first.md` enumerating which features phone home
  and which do not. Skills Hub and Curator pull from the internet
  when allowed.
- **No "offline mode"** flag that disables every outbound call
  except to user-pinned local model endpoints.

### G. Inter-surface routing
- A webhook subscription cannot directly create a kanban task; a
  kanban task cannot directly fire a cron-style follow-up; a cron
  job cannot enqueue a kanban card. Every combination today
  requires custom Python in the cron job's `script` field or a
  plugin.
- `send_message` exists, but there is no `enqueue_task(board, …)`
  or `schedule_followup(when, …)` exposed as a first-class tool.

### H. Observability for the operator (not the agent)
- `hermes logs` exists. There is no `hermes status --json` that
  prints "what is Hermes doing right now" in one machine-readable
  payload (gateway up?, dispatcher up?, active sessions, claimed
  tasks, next cron, last 5 decisions, current model usage caps).
- No `tools/health_tool.py`; doctor covers install diagnostics, not
  runtime liveness.

### I. Documentation hub for orchestration
- `docs/orchestration/` exists only as of this phase. There is no
  end-to-end "how do I run Hermes as my private orchestration
  command center?" tutorial — only the per-feature pages on the
  website.

---

## 11. Implementation Risks

Risks the next phases must respect — derived from `AGENTS.md`,
`CONTRIBUTING.md`, and the file-load survey:

1. **Prompt-cache invalidation.** Any new orchestration surface that
   touches system prompt / toolsets mid-conversation will trash
   prefix caching. `AGENTS.md` is explicit:
   > Cache-breaking forces dramatically higher costs. The ONLY
   > time we alter context is during context compression.
   Slash commands must default to deferred invalidation with an
   opt-in `--now`.
2. **Plugins MUST NOT modify core files.** PR #5295 is the
   precedent. Anything new orchestration-shaped must be a plugin or
   expand the generic plugin surface — never hardcode into
   `run_agent.py`, `cli.py`, `gateway/run.py`, `hermes_cli/main.py`.
3. **No new in-tree memory providers** (May 2026 policy). The set
   under `plugins/memory/` is closed; new backends ship as standalone
   plugin repos. If orchestration needs new persistence, it goes
   through the existing memory ABC or a brand-new top-level
   abstraction, not under `plugins/memory/`.
4. **Profile-safe paths.** Hardcoding `~/.hermes` breaks profiles.
   Always `get_hermes_home()` for IO, `display_hermes_home()` for
   strings.
5. **Gateway two-guard rule.** Any new control command that must
   reach the runner mid-run has to bypass both
   `gateway/platforms/base.py::_pending_messages` and
   `gateway/run.py`'s intercept list, and must be dispatched inline.
6. **Token / credential isolation.** Gateway platform adapters with
   unique credentials acquire token locks (`acquire_scoped_lock()`).
   Two profiles must not use the same bot token.
7. **delegate_task is not durable.** Long-running orchestration
   must use cron, `terminal(background=True, notify_on_complete=True)`,
   or the kanban dispatcher. Adding a "long delegate" without
   thinking through interrupt + cancellation will leak workers.
8. **Synchronous loop assumption.** `run_agent.py::run_conversation`
   is a single synchronous while-loop with interrupt checks.
   Plumbing async orchestration in must go through callbacks /
   tools / sub-processes, not by re-architecting the loop.
9. **Dependency pinning policy.** Every direct PyPI dep is
   exact-pinned (`==X.Y.Z`); CI rejects bare `>=`. Git deps use 40-char
   SHAs. Any new orchestration deps follow the same rule
   (`pyproject.toml` comments, May 2026 post-mistralai update).
10. **Test isolation.** `tests/conftest.py::_isolate_hermes_home`
    autouse fixture redirects `HERMES_HOME` to a temp dir; tests must
    never write `~/.hermes/`. Profile tests must mock `Path.home()`
    too. `scripts/run_tests.sh` is the only sanctioned runner
    (CI-parity: TZ=UTC, LANG=C.UTF-8, `-n 4`).
11. **No change-detector tests.** Reviewers reject snapshot tests on
    model catalogs, config versions, enumeration counts. Tests must
    assert *relationships*, not specific names.
12. **`_last_resolved_tool_names` is a process global**
    (`model_tools.py`). Sub-agent execution saves and restores it;
    new orchestration code that reads it must tolerate temporary
    staleness.
13. **No hardcoded cross-tool references in schema descriptions.**
    Cross-references that go between toolsets must be injected
    dynamically in `get_tool_definitions()` (browser_navigate /
    execute_code patterns).
14. **Skills hardline.** New skills introduced as part of
    orchestration phases must meet the 8-point standard
    (`description ≤ 60 chars`, no marketing language, tools named
    correctly, `platforms:` gating audited, modern section order,
    `scripts/` + `references/` + `templates/`, tests under
    `tests/skills/`, isolated `.env.example` blocks).
15. **Don't squash from stale branches.** PRs against this work must
    be rebased onto `main` immediately before squash-merge or
    unrelated regressions silently re-enter the tree.
16. **Squash-merge audit.** After landing, verify
    `git diff HEAD~1..HEAD` for unexpected deletions — recent
    examples in the codebase had unrelated files reverted by stale
    squashes.

---

## 12. Recommended File Map for Later Phases

This is **not** a commitment to build any of these in Phase 00 — it is
a target layout the next phases can implement against, expressed in the
existing project's conventions (plugins-first, profile-aware paths,
prompt-cache-safe slash commands, no core-file edits except the central
registry).

```
docs/orchestration/
├── phase-00-baseline-audit.md           # THIS FILE
├── phase-01-data-model.md               # task / worker / ledger schemas
├── phase-02-model-router.md             # agent/model_router.py spec
├── phase-03-worker-fleet.md             # ~/.hermes/workers/*.yaml spec
├── phase-04-command-center.md           # unified dashboard + /hermes status
├── phase-05-inter-surface-routing.md    # enqueue_task / schedule_followup
├── phase-06-local-first-mode.md         # offline flag, telemetry audit
├── phase-07-claude-code-host.md         # CLAUDE.md + .claude/ adoption
├── phase-08-android-companion.md        # tighter loop with apps/android
└── reference/
    ├── ledger-schema.md
    ├── router-policy-grammar.md
    ├── worker-manifest.md
    └── command-registry-extensions.md

# New code (proposed locations, plugin-first):
plugins/orchestration/                    # NEW — opt-in plugin
├── plugin.yaml                          # name: orchestration
├── __init__.py                          # register() — tools + hooks + CLI
├── ledger.py                            # append-only SQLite at
│                                        #   $HERMES_HOME/orchestration/ledger.db
├── model_router.py                      # policy → (provider, model, budget)
├── workers.py                           # ~/.hermes/workers/*.yaml loader
├── router_tool.py                       # tool: route_task(intent, budget)
├── enqueue_tool.py                      # tool: enqueue_task(board, task, …)
├── schedule_tool.py                     # tool: schedule_followup(when, …)
├── status_tool.py                       # tool: hermes_status() / hermes_health()
├── cli.py                               # hermes orchestration <verb>
└── dashboard/                           # web UI panel (manifest.json + dist/)

# Existing surfaces to extend (single-source-of-truth files only):
hermes_cli/commands.py
  + CommandDef("workers", …, "Tools & Skills",
               subcommands=("list","start","stop","tail"))
  + CommandDef("ledger",  …, "Info",
               subcommands=("tail","show","export"))
  + CommandDef("route",   …, "Configuration",
               args_hint="[policy]")
  + CommandDef("orchestrate", …, "Session",
               args_hint="<goal>")

# Skills (built-in additions, follow HARDLINE rules):
skills/devops/orchestration-command-center/SKILL.md
skills/devops/model-router/SKILL.md
skills/devops/worker-fleet/SKILL.md

# Tests (live alongside source, scripts/run_tests.sh-compatible):
tests/plugins/orchestration/
  test_ledger.py
  test_model_router.py
  test_workers.py
  test_enqueue_tool.py
  test_schedule_tool.py
  test_status_tool.py
tests/cli/test_orchestrate_command.py
tests/skills/test_orchestration_command_center_skill.py

# State at runtime (profile-aware):
$HERMES_HOME/orchestration/ledger.db
$HERMES_HOME/workers/<name>.yaml
$HERMES_HOME/orchestration/router-policy.yaml
$HERMES_HOME/orchestration/status.json     # snapshot, rewritten on tick
```

Why this shape:

- **Plugins-first** respects the May 2026 "plugins MUST NOT modify
  core" policy: every new tool, CLI command, and dashboard panel
  lives under `plugins/orchestration/` and registers through
  `PluginContext`.
- **Central registry extensions** keep CLI/gateway/Telegram/Slack/
  autocomplete in lockstep with one `CommandDef` per new command,
  per the AGENTS.md guidance.
- **Append-only ledger** under `$HERMES_HOME/orchestration/`
  inherits profile isolation for free.
- **Workers as YAML manifests** sidestep the closed in-tree
  memory-provider precedent: workers are configuration, not a new
  ABC under `plugins/`.
- **No edits to** `run_agent.py`, `cli.py`, `gateway/run.py`,
  `hermes_cli/main.py` are anticipated by this map. The single
  exceptions — adding entries to `hermes_cli/commands.py` and
  package-data globs in `pyproject.toml` — are the same touch
  points existing plugins (kanban, github_assistant) already use.

---

*End of Phase 00.*
