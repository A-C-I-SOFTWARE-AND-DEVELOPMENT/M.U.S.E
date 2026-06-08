# Hermes Agent — Full Repo Audit (Phase 00)

**Date:** 2026-05-23
**Branch:** `claude/hermes-repo-audit-TZ26F`
**Auditor:** Phase 00 — repo truth audit
**Scope:** factual inventory + integration map prior to the 10/10 product build

This document is the **single source of truth for what currently exists**
in the hermes-agent repository, the integrations that are wired, and the
state of the orchestration substrate. It is paired with:

- `docs/audits/hermes-file-inventory.md` — file-level breakdown
- `docs/audits/hermes-10-10-gap-report.md` — gap analysis vs. the product
  vision (mobile-native, voice-first, autonomous orchestrator + remote
  Windows Claude Code bridge + Supabase/Vercel/GitHub)

---

## Executive verdict

**Hermes is already a serious, dense, multi-surface AI-agent codebase
that has independently arrived at most of the architectural pieces the
10/10 product vision needs.** The work is *foundation present, surface
not yet productized for Jeremiah*.

What is good:

- A real agent runtime (`run_agent.py` + `agent/`, ~54k LOC) with
  ~22 model providers and a clean transport layer.
- A mature tool registry (`tools/`, ~60k LOC, 95 tool modules) covering
  terminal/SSH/Docker/Modal/Daytona/Vercel-Sandbox, browser, MCP,
  file ops, vision, TTS/STT/voice mode, GitHub via plugin, etc.
- A skill system with **200 `SKILL.md` files** (active + optional)
  and a slash-command + autocomplete pipeline.
- A messaging gateway covering **22+ platforms** (Telegram, Discord,
  Slack, WhatsApp, Signal, Matrix, Email, Teams, Feishu, Dingtalk,
  WeCom, Weixin, QQbot, BlueBubbles, Yuanbao, IRC, Line, SimpleX,
  Home Assistant, Google Chat, SMS, webhook).
- A real orchestration substrate (Phase 24 declares 10/10): six
  worker adapters (`codex`, `claude-code`, `aider`, `goose`,
  `chatgpt_handoff`, `hermes_local`), a kanban dispatcher, scoring,
  arbiter, merge engine, five validation gates, GitHub publisher
  (dry-run by default), and a local FastAPI control plane
  (`hermes_cli/orchestrator_api.py`).
- A native Android cockpit (`apps/android/`, Kotlin + Compose) with
  a documented API contract, plus a Termux runtime path.
- A TUI built in Ink (React) backed by a Python JSON-RPC gateway,
  plus a browser dashboard that embeds the real TUI via PTY.
- An ACP adapter for VS Code / Zed / JetBrains.
- A web frontend (Vite + React 19) under `web/` and a docusaurus
  site under `website/`.
- Voice surface: `tools/voice_mode.py` (1k LOC), `tools/tts_tool.py`
  (2.3k LOC), `tools/transcription_tools.py` (940 LOC),
  `hermes_cli/voice.py` (846 LOC), plus a neutts synthesizer stub.

What is incomplete vs. the 10/10 product vision (full detail in the
gap report):

- **Voice-first cockpit UX**: voice primitives exist but are not the
  default conversational surface; no continuous wake-word, no
  duplex-voice-over-gateway delivery, no Android-native STT/TTS
  integration in the cockpit.
- **Mobile-native end-to-end loop**: the Android app is a thin client
  for a backend that is not yet productionized — auth/pairing,
  push notifications, background services, and the cockpit API surface
  are spec'd but not all live.
- **Remote Windows Claude Code bridge**: there is a *handoff* worker
  (writes a prompt + waits for the user to run `claude` locally) but
  **no secure SSH/WireGuard/agent-bridge that executes Claude Code on
  a Windows workstation from a phone or VPS**.
- **Worker actuators**: every orchestration worker still returns a
  Markdown *proposal*, not a patch — explicitly noted in
  `docs/orchestration/known-limitations.md`.
- **GitHub MCP / live publisher transport**: the publisher writes a
  PublishDescriptor; live posting is a caller-supplied seam, not a
  turnkey integration.
- **Supabase**: zero integration today. The only matches in the repo
  are doc-example strings.
- **Vercel**: only as a terminal sandbox (`tools/environments/vercel_sandbox.py`)
  and a model gateway provider (`plugins/model-providers/ai-gateway/`).
  No deploy/preview/log-tailing integration.
- **Decision validation**: gates exist, but the *policy / risk-tier*
  decision engine the cockpit needs (auto-approve, ask, refuse) is
  partially in `tools/tirith_security.py` + `tools/approval.py` and
  partially in `enterprise/policy.py` — not unified.
- **State preservation across disconnects**: SQLite session DB exists
  (`hermes_state.py`), kanban + decision-ledger + jobs are JSON+SQLite,
  but no "resumeable cockpit session" identity that survives an
  Android process death + reconnect with full replay.
- **Skill-aware orchestration routing** (item 10 in
  `docs/orchestration/next-roadmap.md`): not done — every job pays the
  full six-worker fan-out cost.

The shortest path to 10/10 is **product wiring, not foundation
re-architecture**. The substrate Phase 24 hardened is the right
substrate to build on; the work is closing the loop end-to-end on the
voice-first Android cockpit + secure remote Windows execution + native
Supabase/Vercel/GitHub integrations.

---

## Repo structure (top level)

```
hermes-agent/
├── run_agent.py             # AIAgent — core conversation loop
├── cli.py                   # HermesCLI — interactive CLI orchestrator
├── model_tools.py           # Tool discovery + dispatch
├── toolsets.py              # _HERMES_CORE_TOOLS + TOOLSETS map
├── batch_runner.py          # Parallel batch processing
├── trajectory_compressor.py # Trajectory compression for training data
├── mcp_serve.py             # Standalone MCP server (exposes Hermes tools)
├── mini_swe_runner.py       # SWE-bench harness
├── hermes_state.py          # SQLite session store (FTS5 search)
├── hermes_constants.py      # get_hermes_home / display_hermes_home
├── hermes_logging.py        # agent.log / errors.log / gateway.log
├── hermes_time.py           # tz helpers
├── hermes_bootstrap.py      # Windows UTF-8 stdio + early init
├── utils.py
├── agent/                   # 91 files — adapters, memory, prompt, transports, lsp
│   ├── transports/          # anthropic, bedrock, chat_completions, codex, codex_app_server, hermes_tools_mcp_server
│   └── lsp/                 # LSP client (manager, protocol, install, workspace)
├── hermes_cli/              # 111 files — main entry, subcommands, web server, workers
│   ├── workers/             # claude_code, codex, aider, goose, chatgpt_handoff, hermes_local + registry
│   └── proxy/               # API proxy + adapters (xai, nous_portal)
├── tools/                   # 95 files — tool registry + every built-in tool
│   ├── environments/        # local, docker, ssh, modal, daytona, singularity, vercel_sandbox
│   ├── computer_use/        # macOS computer-use bridge
│   └── neutts_samples/      # NeuTTS sample audio
├── gateway/                 # Messaging gateway (run.py + session.py + platforms/)
│   ├── platforms/           # 23 adapter files (Telegram, Discord, Slack, …)
│   └── builtin_hooks/       # gateway hook extension point
├── plugins/                 # 205 files — model providers, memory, web, browser, dashboards
│   ├── model-providers/     # 22 providers (anthropic, openrouter, gemini, novita, NVIDIA NIM, …)
│   ├── memory/              # honcho, mem0, supermemory, hindsight, holographic, byterover, retaindb, openviking
│   ├── browser/             # browser_use, browserbase, firecrawl
│   ├── web/                 # tavily, exa, brave_free, ddgs, searxng, firecrawl, parallel
│   ├── github_assistant/    # native GitHub REST plugin (8 tools)
│   ├── kanban/              # multi-agent board dispatcher + worker plugin
│   ├── hermes-achievements/ # gamified achievement tracking
│   ├── observability/       # langfuse plugin
│   ├── platforms/           # google_chat, irc, line, simplex, teams (extra gateway adapters)
│   ├── spotify/, image_gen/, video_gen/, google_meet/, teams_pipeline/, disk-cleanup/,
│   │ context_engine/, example-dashboard/
├── skills/                  # 157 files / ~50 skills bundled with the repo
├── optional-skills/         # 89 files / ~80 heavier or niche skills
├── enterprise/              # council, judge, monitor, policy, secrets, audit + adapters
├── acp_adapter/             # ACP server (VS Code / Zed / JetBrains) — 10 files
├── tui_gateway/             # Python JSON-RPC backend for the Ink TUI
├── ui-tui/                  # Ink (React) terminal UI
├── web/                     # Vite/React 19 dashboard (uses xterm.js + PTY for chat)
├── website/                 # Docusaurus marketing/docs site
├── apps/android/            # Native Android cockpit (Kotlin + Compose)
├── cron/                    # Cron scheduler (jobs.py + scheduler.py)
├── docs/                    # 53 .md/.pdf files, including 35-doc orchestration set
├── scripts/                 # install.sh / .ps1 / .cmd, termux-doctor, orchestrate, ai-radar, …
├── nix/                     # Nix packaging (devShell, packages, NixOS module, overlays)
├── docker/                  # Dockerfile + entrypoint + soul/system prompt
├── locales/                 # 16 i18n YAMLs
├── packaging/homebrew/      # Homebrew formula
├── templates/orchestration/ # council-review, job-retrospective, scorecard
├── providers/               # provider base abstractions
├── tests/                   # 1,151 files (subdirs: gateway, hermes_cli, plugins, e2e, …)
└── .github/workflows/       # 14 CI workflows (tests, lint, nix, android-build, …)
```

---

## Important files (load-bearing entry points)

| File | LOC | Role |
|---|---|---|
| `run_agent.py` | (largest) | `AIAgent` class — conversation loop, ~60-param init |
| `cli.py` | (largest after main) | `HermesCLI` — interactive orchestrator |
| `hermes_cli/main.py` | 13,233 | CLI entry: 140 subcommands wired here |
| `hermes_cli/auth.py` | 7,474 | OAuth/PAT/api-key for every provider |
| `hermes_cli/kanban_db.py` | 6,233 | SQLite multi-board kanban substrate |
| `hermes_cli/config.py` | 5,546 | `DEFAULT_CONFIG`, `OPTIONAL_ENV_VARS`, loaders |
| `hermes_cli/gateway.py` | 5,467 | Gateway controller (start/stop/install/status) |
| `agent/auxiliary_client.py` | 5,289 | Side-LLM resolution (curator/vision/title/...) |
| `hermes_cli/web_server.py` | 4,583 | FastAPI dashboard + PTY WebSocket |
| `agent/conversation_loop.py` | 4,099 | Main streaming loop internals |
| `tools/browser_tool.py` | 3,796 | Browser automation surface |
| `tools/mcp_tool.py` | 3,584 | MCP client + tool bridge |
| `tools/skills_hub.py` | 3,438 | Marketplace/Hub for skills |
| `hermes_cli/commands.py` | 1,787 | `COMMAND_REGISTRY` — 91 slash commands |
| `hermes_cli/validation.py` | 1,575 | Local validation gates (PT-14) |
| `tools/tts_tool.py` | 2,289 | TTS providers + voice generation |
| `tools/voice_mode.py` | 1,018 | Voice-mode loop (record → transcribe → reply → speak) |
| `hermes_cli/voice.py` | 846 | Process-wide voice API for the TUI gateway |
| `model_tools.py` | — | Tool discovery + `handle_function_call()` |
| `toolsets.py` | 866 | `_HERMES_CORE_TOOLS` + `TOOLSETS` definitions |
| `agent/transports/anthropic.py` | 2,220 | Direct Anthropic transport |
| `tools/registry.py` | — | Central tool registry (AST-based discovery) |
| `tools/tirith_security.py` | — | Content-level command safety (tirith binary) |
| `tools/approval.py` | — | Dangerous-command approval gate |

### Orchestration-specific entry points

| File | Role |
|---|---|
| `hermes_cli/orchestrator.py` | Job dataclass + `Orchestrator` (fan-out) + `WorktreeManager` |
| `hermes_cli/orchestrator_api.py` | Local-only FastAPI control plane |
| `hermes_cli/orchestrator_models.py` | Pydantic models for job state |
| `hermes_cli/orchestrator_parallel.py` | Parallel worktree fan-out |
| `hermes_cli/job_controller.py` | Job lifecycle controller |
| `hermes_cli/scoring.py` | 4-signal weighted scorer |
| `hermes_cli/merge_engine.py` | Winner-or-draw merge artifact |
| `hermes_cli/validation.py` | Validation gate runner |
| `hermes_cli/github_publisher.py` | PublishDescriptor + dry-run by default |
| `hermes_cli/workers/{claude_code,codex,aider,goose,chatgpt_handoff,hermes_local}.py` | Worker adapters |
| `enterprise/{audit,council,judge,monitor,policy,secrets}.py` | Enterprise council / judge / policy |
| `templates/orchestration/{council-review.md,job-retrospective.md,scorecard.json}` | Output templates |
| `scripts/hermes-orchestrate.sh` | One-shot bash entry |
| `scripts/hermes-ai-radar.sh` | AI-improvement radar entry |

---

## Important packages / modules

- `agent/` — provider adapters (`anthropic_adapter`, `bedrock_adapter`,
  `gemini_native_adapter`, `gemini_cloudcode_adapter`, `azure_identity_adapter`,
  `codex_responses_adapter`, `copilot_acp_client`), memory
  (`memory_manager`, `memory_provider`), context engineering
  (`context_engine`, `context_compressor`, `context_references`,
  `conversation_compression`), prompt + caching (`prompt_builder`,
  `prompt_caching`, `system_prompt`), credentials
  (`credential_pool`, `credential_sources`, `google_oauth`),
  transports (`transports/`), LSP (`lsp/`), reasoning helpers
  (`lmstudio_reasoning`, `gemini_schema`, `moonshot_schema`),
  trajectory + curator (`trajectory`, `curator`), accounting
  (`account_usage`, `usage_pricing`, `iteration_budget`,
  `nous_rate_guard`, `rate_limit_tracker`), and tool execution
  (`tool_executor`, `tool_guardrails`, `tool_dispatch_helpers`,
  `tool_result_classification`).

- `hermes_cli/` — CLI subcommand modules, including:
  `setup`, `doctor`, `auth`/`auth_commands`, `config`, `models`,
  `model_catalog`, `model_normalize`, `model_switch`, `model_picker`,
  `profiles`/`profile_describer`/`profile_distribution`,
  `kanban`/`kanban_db`/`kanban_decompose`/`kanban_diagnostics`/
  `kanban_specify`/`kanban_swarm`, `cron`, `curator`, `skills_hub`,
  `skills_config`, `skin_engine`, `voice`, `webhook`,
  `vercel_auth`, `azure_detect`, `dingtalk_auth`, `copilot_auth`,
  `gateway`/`gateway_windows`, `pty_bridge`, `web_server`,
  `worktrees`, `proxy/server.py`, `workers/*`, `commands`,
  `validation`, `orchestrator*`, `job_controller`, `scoring`,
  `merge_engine`, `github_publisher`, `security_advisories`,
  `nous_subscription`.

- `tools/` — tool implementations (each calls
  `registry.register()` at import time). Includes:
  `terminal_tool`, `code_execution_tool`, `file_operations`,
  `file_tools`, `web_tools`, `browser_*` (`browser_tool`,
  `browser_cdp_tool`, `browser_camofox`, `browser_supervisor`,
  `browser_dialog_tool`), `vision_tools`,
  `transcription_tools`, `tts_tool`, `voice_mode`, `neutts_synth`,
  `image_generation_tool`, `video_generation_tool`,
  `computer_use_tool`, `discord_tool`, `homeassistant_tool`,
  `feishu_*`, `x_search_tool`, `yuanbao_tools`,
  `kanban_tools`, `todo_tool`, `delegate_tool`,
  `clarify_tool`/`clarify_gateway`, `send_message_tool`,
  `session_search_tool`, `mixture_of_agents_tool`,
  `cronjob_tools`, `memory_tool`, `mcp_tool`/`mcp_oauth*`,
  `skill_manager_tool`/`skills_tool`/`skills_hub`/`skills_sync`/`skills_guard`/`skill_provenance`/`skill_usage`,
  `tirith_security`, `approval`, `slash_confirm`,
  `path_security`, `url_safety`, `website_policy`,
  `process_registry`, `interrupt`, `budget_config`,
  `checkpoint_manager`, `tool_output_limits`,
  `tool_result_storage`, `binary_extensions`,
  `microsoft_graph_*`, `openrouter_client`, `xai_http`,
  `osv_check`, `patch_parser`, `fuzzy_match`,
  `ansi_strip`, `env_passthrough`, `credential_files`,
  `lazy_deps`, `managed_tool_gateway`,
  `tool_backend_helpers`, `schema_sanitizer`, `debug_helpers`.

- `gateway/` — `run.py` (orchestrator), `session.py` +
  `session_context.py` (per-chat state), `delivery.py` (outbound),
  `platform_registry.py`, `channel_directory.py`, `config.py`,
  `hooks.py`/`builtin_hooks/`, `status.py`/`restart.py`/`shutdown_forensics.py`,
  `stream_consumer.py`, `mirror.py`, `pairing.py`,
  `slash_access.py`, `sticker_cache.py`,
  `whatsapp_identity.py`, `runtime_footer.py`,
  `display_config.py`, `memory_monitor.py`.

- `plugins/` — see Current integrations.

- `enterprise/` — council / judge / monitor / policy / secrets / audit
  + per-department adapters (`cs`, `finance`, `hr`, `ops`, `sales`).

- `acp_adapter/` — server, session, auth, permissions,
  edit_approval, events, tools, entry, `__main__`.

- `cron/` — `jobs.py` (job model) + `scheduler.py` (cron loop).

- `tui_gateway/` — `server.py` (JSON-RPC over stdio),
  `transport.py`, `ws.py`, `render.py`, `event_publisher.py`,
  `slash_worker.py`, `entry.py`.

- `ui-tui/src/` — Ink (React) — `app.tsx`, `entry.tsx`,
  `gatewayClient.ts`, plus `components/`, `domain/`, `lib/`,
  `config/`, `types/`, with `packages/hermes-ink/` as a local
  ink helper.

- `web/src/` — Vite + React 19 dashboard
  (`ChatPage`, `ConfigPage`, `EnvPage`, `DocsPage`, `PluginsPage`,
  `SessionsPage`, `ProfilesPage`, `CronPage`, `LogsPage`,
  `AnalyticsPage`, `SkillsPage`, `ModelsPage`).

- `apps/android/app/src/main/java/com/aci/hermes/` — Kotlin/Compose
  cockpit (MainActivity, HermesApplication, HermesService, AppContainer,
  ui/navigation/HermesNavGraph, ui/theme/*, ui/screens/{orchestrator,
  settings, splash, diagnostics}/*, data/{model, orchestrator,
  preferences, termux, cockpit}/*).

---

## Current integrations

### LLM / model providers (plugin-driven)

22 providers under `plugins/model-providers/`:
`anthropic`, `openrouter`, `ai-gateway`, `gemini`,
`bedrock`, `azure-foundry`, `nous`, `novita`, `nvidia`
(NIM Nemotron), `xiaomi` (MiMo), `zai` (z.ai/GLM),
`stepfun`, `arcee`, `huggingface`, `kilocode`,
`alibaba`, `alibaba-coding-plan`, `deepseek`,
`gmi`, `kimi-coding` (Moonshot), `minimax`,
`ollama-cloud`, `openai-codex`, `opencode-zen`,
`qwen-oauth`, `xai`, `copilot`, `copilot-acp`,
`custom` (any OpenAI-compatible endpoint).

Direct transport modules (in addition):
`agent/transports/{anthropic,bedrock,chat_completions,codex,codex_app_server,hermes_tools_mcp_server}.py`.

### Coding agents / workers (orchestration)

`hermes_cli/workers/`:

- `claude_code.py` — handoff to local `claude` CLI (Anthropic)
- `codex.py` — handoff to OpenAI Codex CLI
- `aider.py` — handoff to Aider
- `goose.py` — handoff to Block Goose
- `hermes_local.py` — local Hermes worker
- `chatgpt_handoff.py` — clipboard-based ChatGPT handoff (Android-friendly)
- `registry.py` — registry + `ALL_WORKERS` tuple

Phase-24 `docs/orchestration/final-10-10-readiness-report.md` declares the
"six workers in parallel via git worktree" milestone as **confirmed**.
Live actuation is gated — workers describe proposals; they don't yet apply
patches (see `known-limitations.md` §1–2).

### Memory backends

`plugins/memory/`: `honcho`, `mem0`, `supermemory`, `hindsight`,
`holographic`, `byterover`, `retaindb`, `openviking`.

### Web / search

`plugins/web/`: `tavily`, `exa`, `brave_free`, `ddgs`, `searxng`,
`firecrawl`, `parallel`. Plus `plugins/browser/`:
`browser_use`, `browserbase`, `firecrawl`.

### GitHub

- **Native plugin** `plugins/github_assistant/` — 8 tools
  (`github_audit_repo`, `github_get_repo_file`, `github_list_branches`,
  `github_list_issues`, `github_create_issue`, `github_list_pull_requests`,
  `github_get_pull_request`, `github_comment_on_issue_or_pr`).
  Token: `GITHUB_PERSONAL_ACCESS_TOKEN`. Allowlist + write-block gates.
- **MCP** option documented in `docs/github-integration.md`.
- **Publisher** `hermes_cli/github_publisher.py` — dry-run by default,
  live transport is a caller seam.

### Messaging gateway platforms

Gateway core: `gateway/platforms/` —
`telegram`, `discord`, `slack`, `whatsapp`, `signal`, `matrix`,
`mattermost`, `email`, `sms`, `homeassistant`, `webhook`,
`bluebubbles`, `dingtalk`, `feishu`/`feishu_comment*`, `wecom`/`wecom_callback`/`wecom_crypto`,
`weixin`, `qqbot/*`, `yuanbao` + `yuanbao_*`,
`api_server`, `msgraph_webhook`.

Plugin-side additions (`plugins/platforms/`):
`google_chat`, `irc`, `line`, `simplex`, `teams`.

### Voice (STT/TTS)

- STT — `faster-whisper` (local) via `tools/transcription_tools.py`
  + lazy-installed cloud STT backends; ElevenLabs, OpenAI, MiniMax
  for ASR options where applicable.
- TTS — `tools/tts_tool.py` (edge-tts default, ElevenLabs premium,
  OpenAI, MiniMax, NeuTTS local at `tools/neutts_synth.py`).
- Voice mode — `tools/voice_mode.py` does push-to-talk / silence-
  detected recording, transcription, and TTS reply.
- Telephony — `optional-skills/productivity/telephony/SKILL.md`
  (Google Voice + Twilio).

### Computer use / terminal sandboxes

`tools/environments/{local,docker,ssh,modal,daytona,singularity,vercel_sandbox}.py`
+ `tools/computer_use_tool.py` (macOS via cua-driver MCP stdio).

### MCP

`tools/mcp_tool.py` + `tools/mcp_oauth*.py` provide a generic MCP client.
`mcp_serve.py` exposes Hermes' own tools as an MCP server.
`skills/mcp/native-mcp/SKILL.md` documents native MCP authoring.

### Observability

`plugins/observability/langfuse/`. No native Prometheus/OTel
shipping today (telemetry is in `docs/orchestration/next-roadmap.md`).

### Validation / security

- `tools/tirith_security.py` — content-level guard (binary auto-installed).
- `tools/approval.py` + `tools/slash_confirm.py` — dangerous-command gate.
- `tools/path_security.py`, `tools/url_safety.py`, `tools/website_policy.py`.
- `enterprise/policy.py` / `enterprise/judge.py` / `enterprise/monitor.py` /
  `enterprise/audit.py` / `enterprise/secrets.py`.
- `hermes_cli/security_advisories.py`.
- Five built-in orchestration gates (`structure`, `size`, `secrets`,
  `unicode`, `policy`) in `hermes_cli/validation.py` /
  `hermes_cli/orchestrator.py`.

### Skills

200 `SKILL.md` files across `skills/` (157 files) +
`optional-skills/` (89 files). Categories include `productivity`,
`creative`, `software-development`, `research`, `mlops`, `finance`,
`gaming`, `media`, `note-taking`, `productivity`, `red-teaming`,
`security`, `social-media`, `smart-home`, `apple`,
`autonomous-ai-agents`, `enterprise-council`, `github`, `mcp`,
`dogfood`, `data-science`, `gifs`, `diagramming`,
`hermes-orchestration-pipeline`, `model-router`,
`self-improvement-loop`, `best-coding-tool-mission`,
`local-quality-gate`, `decision-quality-gate`,
`evidence-architect`, `principal-systems-architect`,
`product-experience-architect`, `contrarian-reviewer`,
`contrarian-red-flag-analyst`, `delivery-scope-controller`,
`assurance-risk-director`, `research-validator`,
`competitive-feature-harvester`, `commercial-strategist`,
`ai-improvement-radar`, `codex-dispatch-governor`,
`developer-ux-command-center`, `aos-council-director`,
`aos-full-agent-team`, `inference-sh`.

---

## Current dependencies / configurations

- Python ≥ 3.11; setuptools build backend.
- Core deps (exact-pinned post-Shai-Hulud, see `pyproject.toml`):
  `openai==2.24.0`, `httpx==0.28.1`, `rich==14.3.3`,
  `pydantic==2.12.5`, `prompt_toolkit==3.0.52`, `croniter==6.0.0`,
  `PyJWT[crypto]==2.12.1`, `tzdata==2025.3` (Windows only),
  `psutil==7.2.2`, `requests==2.33.0`, `jinja2==3.1.6`,
  `ruamel.yaml==0.18.17`, `pyyaml==6.0.3`, `fire==0.7.1`,
  `tenacity==9.1.4`, `python-dotenv==1.2.2`.
- Optional extras:
  `anthropic`, `exa`, `firecrawl`, `parallel-web`, `fal`,
  `edge-tts`, `modal`, `daytona`, `vercel`, `hindsight`,
  `dev` (debugpy, pytest, ty, ruff), `messaging` (telegram,
  discord, slack, qrcode), `slack`, `matrix`,
  `cli`, `tts-premium` (elevenlabs), `voice` (faster-whisper,
  sounddevice, numpy), `pty`, `honcho`, `mcp`,
  `homeassistant`, `sms`, `computer-use`, `acp`,
  `bedrock`, `azure-identity`, `termux` / `termux-all`,
  `dingtalk`, `feishu`, `google`, `youtube`, `web`
  (fastapi + uvicorn), `all` (curated lazy-resolved set).
- Config files:
  - `~/.hermes/config.yaml` — primary settings (`DEFAULT_CONFIG`
    in `hermes_cli/config.py`).
  - `~/.hermes/.env` — secrets only (`OPTIONAL_ENV_VARS`).
  - `~/.hermes/logs/{agent,errors,gateway}.log`.
  - `~/.hermes/jobs/<job-id>/{ledger.jsonl,…}` — per-job state.
  - `~/.hermes/orchestrator/{jobs.json,decision_ledger.json,…}`.
  - `~/.hermes/skills/` — user-installed skills.
  - `~/.hermes/plugins/` — user-installed plugins.
  - `~/.hermes/profiles/*` — multi-profile install isolation.
- Local-only API: `hermes_cli/orchestrator_api.py` enforces loopback
  + optional `HERMES_ORCHESTRATOR_API_TOKEN`.
- CI: 14 GitHub Actions workflows
  (`tests.yml`, `lint.yml`, `nix.yml`, `android-build.yml`,
  `orchestration-tests.yml`, `osv-scanner.yml`, `supply-chain-audit.yml`,
  `uv-lockfile-check.yml`, `upload_to_pypi.yml`, `deploy-site.yml`,
  `docs-site-checks.yml`, `nix-lockfile-fix.yml`, `skills-index.yml`,
  `history-check.yml`, `docker-publish.yml`, `contributor-check.yml`).
- Nix: `flake.nix` + `nix/{checks,configMergeScript,devShell,hermes-agent,lib,nixosModules,overlays,packages,python,tui,web}.nix`.
- Packaging: `packaging/homebrew/` (Homebrew formula).

---

## Existing skills

**Active skills** (`skills/`):
`ai-improvement-radar`, `aos-council-director`, `aos-full-agent-team`,
`apple/{apple-notes,apple-reminders,findmy,imessage,macos-computer-use}`,
`assurance-risk-director`, `autonomous-ai-agents/{claude-code,codex,hermes-agent,kanban-codex-lane,opencode}`,
`best-coding-tool-mission`, `codex-dispatch-governor`,
`commercial-strategist`, `competitive-feature-harvester`,
`contrarian-red-flag-analyst`, `contrarian-reviewer`,
`creative/{architecture-diagram,ascii-art,ascii-video,baoyu-article-illustrator,baoyu-comic,baoyu-infographic,claude-design,comfyui,creative-ideation,design-md,excalidraw,humanizer,manim-video,p5js,pixel-art,popular-web-designs,pretext,sketch,songwriting-and-ai-music,touchdesigner-mcp}`,
`data-science/jupyter-live-kernel`,
`decision-quality-gate`, `delivery-scope-controller`,
`developer-ux-command-center`,
`devops/{kanban-orchestrator,kanban-worker,webhook-subscriptions}`,
`dogfood`, `email/himalaya`,
`enterprise-council/{customer-service,finance,hr,judge,monitor,operations,orchestrator,sales}`,
`evidence-architect`,
`gaming/{minecraft-modpack-server,pokemon-player}`,
`github/{codebase-inspection,github-auth,github-code-review,github-issues,github-pr-workflow,github-repo-management}`,
`github-publisher`, `hermes-orchestration-pipeline`,
`local-quality-gate`, `mcp/native-mcp`,
`media/{gif-search,heartmula,songsee,spotify,youtube-content}`,
`mlops/huggingface-hub`, `model-router`,
`note-taking/obsidian`, `principal-systems-architect`,
`product-experience-architect`,
`productivity/{airtable,google-workspace,linear,maps,nano-pdf,notion,ocr-and-documents,powerpoint,teams-meeting-pipeline}`,
`red-teaming/godmode`,
`research/{arxiv,blogwatcher,llm-wiki,polymarket,research-paper-writing}`,
`research-validator`,
`self-improvement-loop`, `smart-home/openhue`,
`social-media/xurl`,
`software-development/{debugging-hermes-tui-commands,hermes-agent-skill-authoring,node-inspect-debugger,plan,python-debugpy,requesting-code-review,spike,subagent-driven-development,systematic-debugging,test-driven-development,writing-plans}`,
`yuanbao`.

**Optional skills** (`optional-skills/`, 80 of them) — see
`docs/audits/hermes-file-inventory.md` §Skills.

---

## Existing Claude agents

**None as repo-level `.claude/agents/`.** The repo has no `.claude/`
directory; agent definitions live as **skills** (above) and as worker
adapters (`hermes_cli/workers/`). The Hermes equivalent of "Claude
agents" is:

- The `autonomous-ai-agents/*` skill family
  (`claude-code`, `codex`, `hermes-agent`, `kanban-codex-lane`,
  `opencode`).
- The six `hermes_cli/workers/*.py` adapters.
- The Enterprise Council departments
  (`skills/enterprise-council/{operations,sales,finance,hr,judge,monitor,orchestrator,customer-service}`)
  backed by `enterprise/adapters/{cs,finance,hr,ops,sales}.py`.

The CLAUDE.md file at repo root is a *pointer* into AGENTS.md; not an
agent definition.

---

## Existing commands

91 slash commands defined in `hermes_cli/commands.py::COMMAND_REGISTRY`:

`/new`, `/topic`, `/clear`, `/redraw`, `/history`, `/save`, `/retry`,
`/undo`, `/title`, `/handoff`, `/branch`, `/compress`, `/rollback`,
`/snapshot`, `/stop`, `/approve`, `/deny`, `/background`, `/agents`,
`/queue`, `/steer`, `/goal`, `/subgoal`, `/status`, `/whoami`,
`/profile`, `/sethome`, `/resume`, `/sessions`, `/config`, `/model`,
`/codex-runtime`, `/gquota`, `/personality`, `/statusbar`, `/verbose`,
`/footer`, `/yolo`, `/reasoning`, `/fast`, `/skin`, `/indicator`,
`/voice`, `/busy`, `/tools`, `/toolsets`, `/skills`, `/bundles`,
`/cron`, `/curator`, `/kanban`, `/reload`, `/reload-mcp`,
`/reload-skills`, `/browser`, `/plugins`, `/commands`, `/help`,
`/restart`, `/usage`, `/insights`, `/platforms`, `/platform`,
`/copy`, `/paste`, `/image`, `/update`, `/debug`,
`/orchestrate`, `/orchestrator`, `/model-router`, `/decision-ledger`,
`/ai-radar`, `/best-coding-tool-mission`, `/quit`.

Plus any `/<skill-name>` resolved via `agent/skill_commands.py`
(scans `~/.hermes/skills/`).

CLI subcommands (`hermes ...`) — 140 add_parser sites in
`hermes_cli/main.py`. Top-level commands include: `chat`, `gateway`,
`setup`, `postinstall`, `whatsapp`, `slack`, `login`, `logout`,
`auth`, `status`, `cron`, `model`, `models`, `tools`, `toolsets`,
`profile`, `profiles`, `plugins`, `dashboard`, `acp`, `kanban`,
`logs`, `mcp`, `memory`, `insights`, `dump`, `bundles`,
`checkpoints`, `computer-use`, `curator`, `debug`, `doctor`,
`completion`, `claw`, `config`, `hooks`, `pairing`,
`backup`, `import`, `proxy`, `fallback`, `voice` (TTS subcommands),
`webhook`.

---

## Existing toolsets

Defined in `toolsets.py`:

`_HERMES_CORE_TOOLS` (default bundle) plus named toolsets:
`web`, `search`, `x_search`, `vision`, `video`, `image_gen`,
`video_gen`, `computer_use`, `terminal`, `moa`, `skills`,
`browser`, `cronjob`, `messaging`, `file`, `tts`, `todo`,
`memory`, `session_search`, `clarify`, `code_execution`,
`delegation`, `homeassistant`, `kanban`, `discord`,
`discord_admin`, `yuanbao`, `feishu_doc`, `feishu_drive`,
`spotify`, `debugging`, `safe`.

---

## Existing gateway surfaces

Built-in gateway adapters in `gateway/platforms/`:
- `telegram` + `telegram_network`
- `discord`
- `slack`
- `whatsapp`
- `signal` + `signal_rate_limit`
- `matrix`
- `mattermost`
- `email`
- `sms`
- `homeassistant`
- `webhook`
- `api_server` (HTTP/SSE backend for Android cockpit etc.)
- `bluebubbles`
- `dingtalk`
- `feishu` + `feishu_comment` + `feishu_comment_rules`
- `wecom` + `wecom_callback` + `wecom_crypto`
- `weixin`
- `qqbot/{adapter,chunked_upload,constants,crypto,keyboards,onboard,utils}`
- `yuanbao` + `yuanbao_media` + `yuanbao_proto` + `yuanbao_sticker`
- `msgraph_webhook`
- `helpers`, `base`, `_http_client_limits`

Plugin-side adapters (`plugins/platforms/`):
`google_chat`, `irc`, `line`, `simplex`, `teams`.

Shared infrastructure: `gateway/run.py` (entry),
`gateway/session.py` + `session_context.py` (state),
`gateway/delivery.py` (outbound), `gateway/platform_registry.py`
(adapter loading), `gateway/stream_consumer.py` (LLM stream → gateway),
`gateway/hooks.py` (extension), `gateway/mirror.py`,
`gateway/pairing.py`, `gateway/slash_access.py`.

---

## Existing TUI / dashboard surfaces

- **`muse --tui`** — Ink (React) TUI driven by
  `tui_gateway/server.py` over newline-delimited JSON-RPC.
  Surface: `ui-tui/src/{app.tsx,entry.tsx,gatewayClient.ts,components/*,domain/*,lib/*}`,
  ~26 `.tsx` components plus a local `hermes-ink` ink-helper package.
- **`muse dashboard`** — `hermes_cli/web_server.py` (FastAPI),
  serving `web/` (Vite + React 19) at `127.0.0.1:9119`. Pages:
  `ChatPage` (embeds TUI via PTY WebSocket), `ConfigPage`,
  `EnvPage`, `DocsPage`, `PluginsPage`, `SessionsPage`,
  `ProfilesPage`, `CronPage`, `LogsPage`, `AnalyticsPage`,
  `SkillsPage`, `ModelsPage`. xterm.js + WebGL renderer,
  `@xterm/addon-fit` + `@xterm/addon-unicode11`.
- **PTY bridge** — `hermes_cli/pty_bridge.py` +
  `/api/pty` WebSocket; spawns `muse --tui` and forwards bytes.
- **Curses UI** — `hermes_cli/curses_ui.py` (`muse tools` /
  `muse setup` use curses for TTY pickers).
- **ACP adapter** — `acp_adapter/{server,session,events,tools,permissions,edit_approval,auth,entry,__main__}.py`
  + `acp_registry/agent.json` + `acp_registry/icon.svg`. Drives
  VS Code / Zed / JetBrains.
- **TUI inside dashboard** — the same `muse --tui` is the canonical
  chat experience inside the dashboard; do NOT re-implement in React
  (per AGENTS.md).

---

## Existing Termux / Android / mobile support

### Termux runtime

- Install path: `pkg install ... && curl ... | bash`
- Service helpers: `scripts/hermes-termux-service.sh`,
  `scripts/hermes-termux-doctor.sh`,
  `scripts/install_psutil_android.py`.
- Constraints file: `constraints-termux.txt`.
- `pyproject.toml` defines `[termux]` and `[termux-all]` extras —
  curated set that avoids Android-incompatible voice deps and lazy
  installs telegram/slack/dingtalk/feishu/honcho.
- Docs: `docs/termux/{hermes-android-permissions,hermes-phone-first-runtime,hermes-termux-boot}.md`.

### Native Android cockpit (`apps/android/`)

- `com.aci.hermes`, min SDK 26, target SDK 35, Kotlin + Compose
  (Material 3), MVVM with hand-rolled DI (`AppContainer.kt`),
  OkHttp + OkHttp-SSE, kotlinx-serialization, DataStore +
  EncryptedSharedPreferences for tokens.
- Screens implemented: `splash`, `settings`, `orchestrator` (+ detail),
  `diagnostics`.
- Data layer: `data/model/{HermesTask,HermesRole,AiToolProfile}.kt`,
  `data/orchestrator/{HermesTaskRepository,PromptBuilder,HandoffLauncher}.kt`,
  `data/termux/TermuxIntentBridge.kt`,
  `data/cockpit/CockpitApi.kt`,
  `data/preferences/{ThemeMode,SettingsRepository}.kt`.
- Service: `service/HermesService.kt` (foreground service shell).
- Util: `util/LogBuffer.kt`.

### Mobile API contracts (spec only — not all live)

- `docs/android/hermes-apk-api-contract.md` — wire format spec
  for the cockpit ↔ gateway (Phase 18). Only `/v1/health` is live
  in gateway today.
- `docs/android/hermes-apk-cockpit.md` — cockpit spec.
- `docs/android/hermes-apk-ui-wireframes.md` — wireframes.
- `docs/android/termux-intent-bridge.md` — on-device Termux IPC.
- `docs/orchestration/android-termux-demo.md` — demo flow.
- `docs/hermes-local-orchestrator.md` — Android-only handoff
  (clipboard) that predates the orchestration stack.

### Gateway-side cockpit support

`gateway/platforms/api_server.py` is the HTTP/SSE adapter the cockpit
talks to (so the cockpit can use the same brain over any transport).

---

## Existing security / secrets handling

- `~/.hermes/.env` — secrets-only file; `OPTIONAL_ENV_VARS` in
  `hermes_cli/config.py` is the authoritative schema (label,
  category, password flag, URL).
- `tests/conftest.py` aggressively strips every credential-shaped env
  var (`*_API_KEY`, `*_TOKEN`, `*_SECRET`, `*_PASSWORD`,
  `*_CREDENTIALS`) before every test.
- `tools/tirith_security.py` — auto-installed `tirith` binary scans
  every shell command before execution.
- `tools/approval.py` + `tools/slash_confirm.py` — TTY approval gate
  for `/yolo`-off mode.
- `tools/path_security.py`, `tools/url_safety.py`,
  `tools/website_policy.py` — content-safety guards.
- `enterprise/policy.py` / `enterprise/judge.py` / `enterprise/monitor.py` /
  `enterprise/audit.py` / `enterprise/secrets.py` — enterprise council.
- `tools/skills_guard.py` + `tools/skill_provenance.py` — skill
  authenticity check.
- `tools/osv_check.py` — OSV vulnerability scan.
- `hermes_cli/security_advisories.py` — supply-chain advisories.
- `tools/credential_files.py` — credential file management.
- `tools/microsoft_graph_auth.py` + `tools/mcp_oauth*.py` +
  `agent/google_oauth.py` + `agent/azure_identity_adapter.py` —
  OAuth flows.
- CI workflows: `osv-scanner.yml`, `supply-chain-audit.yml`,
  `uv-lockfile-check.yml`, `contributor-check.yml`.
- `pyproject.toml` — every direct dependency exact-pinned post-
  Shai-Hulud (2026-05-12).
- `SECURITY.md` (331 lines) — vulnerability reporting.
- Five orchestration gates (`structure`, `size`, `secrets`, `unicode`,
  `policy`) at the publish boundary.

---

## Existing testing / CI

- **Suite size**: 1,151 test files (78 top-level, 1,073 in subdirs).
  Subdirs: `acp`, `acp_adapter`, `agent`, `cli`, `cron`, `e2e`,
  `enterprise`, `fakes`, `gateway`, `hermes_cli`, `hermes_state`,
  `honcho_plugin`, `integration`, `openviking_plugin`, `plugins`,
  `providers`, `run_agent`, `scripts`, `skills`, `stress`,
  `tools`, `tui_gateway`, `website`.
- **Pytest**: `pytest -m 'not integration' -n auto --timeout=30
  --timeout-method=signal`. Markers: `integration`,
  `real_concurrent_gate`.
- **Conftest invariants** (`tests/conftest.py`):
  - Strip every credential env var.
  - Isolate `HERMES_HOME` to a tempdir.
  - `TZ=UTC`, `LANG=C.UTF-8`, `PYTHONHASHSEED=0`.
- **Canonical runner**: `scripts/run_tests.sh` (probes `.venv` → `venv`
  → `$HOME/.hermes/hermes-agent/venv`).
- **GitHub Actions** (14 workflows):
  - `tests.yml` — pytest matrix
  - `orchestration-tests.yml` — orchestration-focused
  - `lint.yml` — `ruff` (PLW1514 only)
  - `nix.yml`, `nix-lockfile-fix.yml` — Nix build
  - `android-build.yml` — APK CI
  - `docker-publish.yml`
  - `osv-scanner.yml`, `supply-chain-audit.yml`,
    `uv-lockfile-check.yml`
  - `upload_to_pypi.yml`
  - `deploy-site.yml`, `docs-site-checks.yml`
  - `skills-index.yml`, `contributor-check.yml`,
    `history-check.yml`
- **Composite actions**: `.github/actions/hermes-smoke-test/`,
  `.github/actions/nix-setup/`.
- **Type checks**: `ty==0.0.21` (configured in `pyproject.toml`).

---

## Existing orchestration pieces

**Substrate (Phase 24 — declared 10/10):**

| Layer | File | Status |
|---|---|---|
| Entry — bash | `scripts/hermes-orchestrate.sh` | ✓ |
| Entry — slash | `/orchestrate` + `/orchestrator` in `hermes_cli/commands.py` | ✓ |
| Entry — Android | `docs/android/hermes-apk-api-contract.md` (`/v1/jobs`) | spec only |
| Controller | `hermes_cli/orchestrator.py` | ✓ |
| Local API | `hermes_cli/orchestrator_api.py` (FastAPI, loopback) | ✓ |
| Job models | `hermes_cli/orchestrator_models.py` | ✓ |
| Parallel fan-out | `hermes_cli/orchestrator_parallel.py` | ✓ |
| Job lifecycle | `hermes_cli/job_controller.py` | ✓ |
| Worker registry | `hermes_cli/workers/registry.py` (`ALL_WORKERS`) | ✓ |
| Workers | `claude_code, codex, aider, goose, chatgpt_handoff, hermes_local` | proposal-only |
| Scoring | `hermes_cli/scoring.py` (4 signals, weights sum to 1.0) | ✓ |
| Arbiter | `hermes_cli/arbiter.py` (referenced in readiness report) | ✓ |
| Merge engine | `hermes_cli/merge_engine.py` | ✓ |
| Validation | `hermes_cli/validation.py` (PT-14) + 5 substrate gates | ✓ |
| Publisher | `hermes_cli/github_publisher.py` (dry-run default) | live = seam |
| Worktrees | `hermes_cli/worktrees.py` + `.hermes/worktrees/` | ✓ |
| Templates | `templates/orchestration/{council-review.md,job-retrospective.md,scorecard.json}` | ✓ |
| Decision ledger | `~/.hermes/jobs/<id>/ledger.jsonl` + `~/.hermes/orchestrator/decision_ledger.json` | ✓ |
| Skills | `skills/hermes-orchestration-pipeline/`, `decision-quality-gate/`, `local-quality-gate/`, `principal-systems-architect/`, `model-router/`, `evidence-architect/`, `delivery-scope-controller/`, `assurance-risk-director/`, `enterprise-council/*` | ✓ |
| Tests | `tests/test_orchestrator*.py`, `tests/test_worker_*.py`, `tests/test_validation_gates.py`, `tests/test_scoring.py`, `tests/test_merge_engine.py`, `tests/test_github_publisher.py`, `tests/test_parallel_orchestration.py`, `tests/test_worktrees.py` (60+ tests) | ✓ |

**Documentation surface** (35 files in `docs/orchestration/`):

- `README.md`, `getting-started.md`, `PHASES.md` (phase log),
- `final-10-10-readiness-report.md`,
  `final-hermes-orchestration-integration-report.md`,
  `phase-0-evidence-audit.md`, `phase-9-validation-report.md`,
- `decision-ledger.md`, `decision-quality-system.md`,
- `worker-adapter-interface.md`, `worker-adapters.md`,
  `workers/{aider,claude-code,codex,goose}-worker.md`,
- `scoring-and-merge-engine.md`, `local-validation-gates.md`,
  `parallel-workers-and-worktrees.md`,
- `private-local-mode.md`, `local-api-backend.md`,
- `orchestrator-command-reference.md`, `orchestrator-command-roadmap.md`,
- `job-controller-roadmap.md`, `release-checklist.md`,
  `known-limitations.md`, `next-roadmap.md`,
- `android-termux-demo.md`, `prompt-to-pr-demo.md`,
- `troubleshooting.md`, `faq.md`,
- `hermes-orchestration-pipeline.md`, `hermes-agent-skill-map.md`,
  `github-publisher-runtime.md`, `self-improvement-loop.md`,
  `NEXT_PHASE_IMPLEMENTATION_PROMPT.md`.

**Outstanding items per `known-limitations.md`**:

1. Workers describe — don't actuate.
2. Workers don't call external models (Phase 24 ban).
3. Scoring weights are fixed (not learned).
4. GitHub publisher's live path is a transport seam, not a turnkey.
5. Worktree cleanup is best-effort.

---

## Missing pieces for 10/10 product (summary)

Full breakdown lives in `docs/audits/hermes-10-10-gap-report.md`.
Headline items:

1. **Voice-first cockpit UX** — continuous-wake or push-to-talk
   voice loop on the Android cockpit, duplex over the
   gateway, low-latency TTS playback.
2. **Production cockpit wiring** — implement the routes in
   `docs/android/hermes-apk-api-contract.md` end-to-end
   (jobs, approvals, sessions, push notifications, SSE).
3. **Secure remote Windows Claude Code bridge** — agent +
   reverse tunnel (WireGuard / Cloudflare Tunnel / Tailscale)
   + signed-command queue so a Windows workstation runs
   `claude` on behalf of the phone-side cockpit.
4. **Worker actuators** — turn proposal-only workers into
   patch-producing ones (Codex/Claude Code/Aider/Goose all
   actually mutate the worktree).
5. **Supabase integration** — plugin (auth, Postgres, edge functions,
   storage), wired as a memory backend option and as a tool.
6. **Vercel integration beyond sandbox** — `vercel` deploy/preview/
   logs/env tools + cockpit visibility of preview URLs.
7. **GitHub MCP / live publisher transport** — turnkey live mode
   for `hermes_cli/github_publisher.py`.
8. **Decision-quality policy unification** — fuse
   `enterprise/policy.py` + `tools/tirith_security.py` +
   `tools/approval.py` into one risk-tiered decision engine the
   cockpit can render.
9. **State across disconnects** — durable, replayable cockpit
   session identity (resume after Android process death or
   network change).
10. **Skill-aware orchestration routing** — pre-route on skill
    match instead of fanning out to all six workers every time.
11. **Cost + time telemetry** — per-worker, per-job, persisted
    + queryable from the cockpit.
12. **Multi-host orchestration** — workers running on different
    machines.
13. **Replay + re-arbitration** — `muse orchestrate replay`
    so a weight change can be A/B'd against a past run.
14. **More validation gates** — `tests` (pytest), `style` (ruff),
    `policy.skill` (SKILL.md version bump).
15. **Mobile-native wake-word / hotkey** — phone-level entry point
    that doesn't require unlocking the app.

---

## Implementation risk map

See `docs/audits/hermes-10-10-gap-report.md` for the full risk
matrix per item. Top risks called out here:

- **Remote Windows execution** — the riskiest piece: SSH/WireGuard
  setup, credential handling, command-injection containment, and
  fail-safe interrupts must all be right. Recommend an explicit
  threat model + a constrained command queue (allowlist) per
  workstation.
- **Voice-first on Android** — battery + STT latency + always-on
  microphone privacy posture. Default must be push-to-talk; wake
  word is opt-in. Use on-device STT (Whisper.cpp via NNAPI) when
  possible.
- **Supabase as memory backend** — Postgres latency from a phone
  network can dominate UX. Pair with a local SQLite cache; read-
  through pattern.
- **Live GitHub publish** — token scope explosion risk; require an
  explicit per-repo allowlist that matches `github_assistant`'s
  pattern.
- **Multi-host workers** — coordination, partial-failure handling,
  and clock skew make this 3–5× harder than the in-process
  version; postpone until the single-host actuator path is
  rock-solid.
- **Worker actuation** — patch conflicts when six workers all
  mutate the same files. Need a deterministic conflict resolution
  policy (orchestrator owns the merge).

---

## Strategic build order recommendation

The recommended order maximizes user-visible value-per-risk for
Jeremiah's mobile-native, voice-first cockpit, and minimizes
re-architecture later. Each phase has a clean exit criterion and
nothing earlier needs to be undone.

**Phase 01 — Voice-first cockpit (Android, push-to-talk first)**
- Wire `gateway/platforms/api_server.py` to the cockpit's
  `/v1/chat` SSE; implement on-device STT (Whisper.cpp via
  NNAPI fallback to gateway STT) and TTS playback in
  `apps/android/`. Exit: spoken question → spoken answer end-to-end.

**Phase 02 — Cockpit API surface (jobs, approvals, sessions, push)**
- Implement the spec'd Phase-18 routes in `gateway/run.py` +
  `gateway/platforms/api_server.py`. Add WS or SSE for live
  job tail. Exit: cockpit can start a job, see live tail, approve.

**Phase 03 — Worker actuators (Claude Code first)**
- Make `claude_code` worker write patches in its worktree, not
  just a proposal. Hook the merge engine to diffs. Exit: a
  `/orchestrate` run produces a real patch.

**Phase 04 — Remote Windows Claude Code bridge**
- Reverse tunnel + signed-command queue on the Windows side
  (PowerShell/WinSW service). Phone-side workers dispatch
  through the bridge. Exit: cockpit triggers a Windows-Claude-
  Code job and gets the diff back. ([go-deep] — see risk map.)

**Phase 05 — Live GitHub publisher transport**
- Use the existing `github_assistant` client (or GitHub MCP) as
  the transport; per-repo allowlist; `HERMES_PUBLISH_LIVE=1`
  becomes safe to flip on. Exit: real draft PR opened.

**Phase 06 — Decision policy unification**
- One risk-tiered decision engine: read inputs from
  `enterprise/policy.py` + `tools/tirith_security.py` +
  `tools/approval.py`; emit a single verdict + rationale; cockpit
  renders + can override. Exit: `/decision-ledger show` shows the
  unified verdict per mutation.

**Phase 07 — Supabase plugin**
- `plugins/supabase/`: auth + Postgres tool + edge-functions
  trigger + storage. Wire as an additional memory backend
  (alongside honcho/mem0/supermemory). Exit: a job's decision
  ledger can be queried in Supabase.

**Phase 08 — Vercel native integration**
- `plugins/vercel/`: deploy/preview/log-tail/env tools.
  Cockpit shows preview URLs after a PR job. Exit: PR job → live
  preview link visible in cockpit.

**Phase 09 — Skill-aware routing + cost telemetry**
- Pre-orchestration step picks workers by skill match (next-
  roadmap §10). Add per-worker cost + elapsed telemetry,
  persisted to `.hermes/runs/`. Exit: a skill-targeted job does
  not pay the 6× fan-out.

**Phase 10 — State preservation + replay**
- Durable cockpit session identity; auto-replay last-known
  state after reconnect. `hermes-orchestrate replay <job-id>`.
  Exit: closing the cockpit mid-run and reopening shows
  uninterrupted state.

**Phase 11 — More validation gates (tests / style / policy.skill)**
- Three additional gates wired into the orchestrator. Exit:
  GATES has 8 entries; CI exercises each.

**Phase 12 — Multi-host orchestration**
- Replace in-process executor with a dispatcher that can target
  multiple hosts. Exit: workers fan out across at least two hosts.

**Phase 13 — Wake-word + ambient voice mode (opt-in)**
- On-device wake word ("Hermes") with explicit privacy posture,
  Always-on opt-in. Exit: phone wakes on word, captures
  intent, dispatches.

Each phase remains scoped to "tweak one of the five primitives" per
`AGENTS.md`'s orchestration rule; no new primitives are introduced.

---

## Where to read more

- This audit: `docs/audits/hermes-full-repo-audit.md`
- File inventory: `docs/audits/hermes-file-inventory.md`
- Gap report: `docs/audits/hermes-10-10-gap-report.md`
- Phase ledger: `docs/orchestration/PHASES.md`
- Phase-24 verdict: `docs/orchestration/final-10-10-readiness-report.md`
- Known limitations: `docs/orchestration/known-limitations.md`
- Existing roadmap: `docs/orchestration/next-roadmap.md`
- Cockpit spec: `docs/android/hermes-apk-cockpit.md`
- Cockpit API: `docs/android/hermes-apk-api-contract.md`
- Termux: `docs/termux/{hermes-phone-first-runtime,hermes-android-permissions,hermes-termux-boot}.md`
- AGENTS.md (dev guide), CLAUDE.md (entry point), README.md (user intro)
