# Hermes Agent — File Inventory (Phase 00)

**Date:** 2026-05-23
**Branch:** `claude/hermes-repo-audit-TZ26F`

This document is the file-level inventory of the hermes-agent repository.
It pairs with `docs/audits/hermes-full-repo-audit.md` (verdict + analysis)
and `docs/audits/hermes-10-10-gap-report.md` (gap report).

**Headline counts:**

- 2,076 files under `hermes_cli/`, `agent/`, `tools/`, `gateway/`,
  `plugins/`, `ui-tui/`, `tui_gateway/`, `acp_adapter/`, `cron/`,
  `scripts/`, `docs/`, `tests/` (max-depth 3).
- 200 `SKILL.md` files across `skills/` + `optional-skills/`.
- 63 `plugin.yaml` files under `plugins/`.
- 1,151 test files under `tests/`.
- 14 GitHub Actions workflows.
- 22 model providers, 22+ messaging platforms, 6 worker adapters.

---

## Top-level files

```
.dockerignore                    Docker ignore
.env.example                     Documented env-var template
.envrc                           direnv hook
.gitattributes                   Git attributes
.gitignore                       Git ignore
.mailmap                         Git author mapping
AGENTS.md                        Authoritative dev guide (1,279 lines)
CLAUDE.md                        Claude-specific entry pointer to AGENTS.md
CONTRIBUTING.md                  PR + contributing process (922 lines)
Dockerfile                       Container image build
LICENSE                          MIT
MANIFEST.in                      sdist manifest
README.md                        User-facing intro (287 lines)
README.zh-CN.md                  Chinese README
RELEASE_v0.2.0.md…v0.14.0.md     Per-version release notes (13 files)
SECURITY.md                      Vulnerability disclosure (331 lines)
batch_runner.py                  Parallel batch processing
cli-config.yaml.example          Annotated config sample
cli.py                           HermesCLI interactive orchestrator
constraints-termux.txt           Termux pin overlay
docker-compose.yml               Compose for local dev
flake.lock / flake.nix           Nix build entry
hermes                           Shell launcher
hermes-already-has-routines.md   Manifesto-style note
hermes_bootstrap.py              First-import: Windows UTF-8 stdio
hermes_constants.py              get_hermes_home() / profile paths
hermes_logging.py                Triple-log setup
hermes_state.py                  SQLite + FTS5 session store
hermes_time.py                   Timezone helpers
mcp_serve.py                     Hermes-tools-as-MCP server
mini_swe_runner.py               SWE-bench harness
model_tools.py                   Tool discovery + dispatch
package.json                     Root npm (release/skills-index)
package-lock.json                Root npm lock
pyproject.toml                   Project metadata + extras
run_agent.py                     AIAgent (core conversation loop)
setup-hermes.sh                  Bootstrapper
setup.py                         Setuptools shim
toolset_distributions.py         Per-platform toolset bundles
toolsets.py                      _HERMES_CORE_TOOLS + TOOLSETS
trajectory_compressor.py         Trajectory compression
utils.py                         Misc utils
uv.lock                          uv lockfile
```

### Top-level directories (max-depth 1)

```
.github/                CI workflows + composite actions + PR template
.plans/                 Per-feature plans (openai-api-server, streaming-support)
acp_adapter/            ACP server (VS Code / Zed / JetBrains)
acp_registry/           agent.json + icon.svg for ACP discovery
agent/                  Agent internals (91 files; with lsp/, transports/)
apps/                   Native Android cockpit
assets/                 Banner png
cron/                   Cron scheduler
datagen-config-examples/  Trajectory/data generation samples
docker/                 Dockerfile assets, entrypoint, SOUL.md
docs/                   Documentation (audits/, orchestration/, android/, …)
enterprise/             Council / judge / monitor / policy / secrets / adapters
gateway/                Messaging gateway (run + session + platforms/)
hermes_cli/             111 files — CLI + workers + proxy + web_server
locales/                16 i18n YAMLs
nix/                    Nix overlays / NixOS module / devShell
optional-skills/        89 files — heavier or niche skills
packaging/              Homebrew formula
plans/                  Free-form plans (gemini-oauth-provider, …)
plugins/                205 files — model providers, memory, web, …
providers/              Provider base abstractions
scripts/                install.sh / install.ps1 / orchestrate / radar / termux
skills/                 157 files — bundled skills (50+ skills)
templates/              Orchestration templates
tests/                  1,151 files — pytest suite
tools/                  95 files — tool registry + every built-in tool
tui_gateway/            Python JSON-RPC backend for Ink TUI
ui-tui/                 Ink (React) TUI
web/                    Vite/React 19 dashboard
website/                Docusaurus docs site
```

---

## `agent/` — Agent internals

```
agent/__init__.py
agent/account_usage.py
agent/agent_init.py
agent/agent_runtime_helpers.py
agent/anthropic_adapter.py
agent/async_utils.py
agent/auxiliary_client.py
agent/azure_identity_adapter.py
agent/background_review.py
agent/bedrock_adapter.py
agent/browser_provider.py
agent/browser_registry.py
agent/chat_completion_helpers.py
agent/codex_responses_adapter.py
agent/codex_runtime.py
agent/context_compressor.py
agent/context_engine.py
agent/context_references.py
agent/conversation_compression.py
agent/conversation_loop.py
agent/copilot_acp_client.py
agent/credential_pool.py
agent/credential_sources.py
agent/curator.py
agent/curator_backup.py
agent/display.py
agent/error_classifier.py
agent/file_safety.py
agent/gemini_cloudcode_adapter.py
agent/gemini_native_adapter.py
agent/gemini_schema.py
agent/google_code_assist.py
agent/google_oauth.py
agent/i18n.py
agent/image_gen_provider.py
agent/image_gen_registry.py
agent/image_routing.py
agent/insights.py
agent/iteration_budget.py
agent/lmstudio_reasoning.py
agent/lsp/__init__.py
agent/lsp/cli.py
agent/lsp/client.py
agent/lsp/eventlog.py
agent/lsp/install.py
agent/lsp/manager.py
agent/lsp/protocol.py
agent/lsp/range_shift.py
agent/lsp/reporter.py
agent/lsp/servers.py
agent/lsp/workspace.py
agent/manual_compression_feedback.py
agent/markdown_tables.py
agent/memory_manager.py
agent/memory_provider.py
agent/message_sanitization.py
agent/model_metadata.py
agent/models_dev.py
agent/moonshot_schema.py
agent/nous_rate_guard.py
agent/onboarding.py
agent/plugin_llm.py
agent/portal_tags.py
agent/process_bootstrap.py
agent/prompt_builder.py
agent/prompt_caching.py
agent/rate_limit_tracker.py
agent/redact.py
agent/retry_utils.py
agent/shell_hooks.py
agent/skill_bundles.py
agent/skill_commands.py
agent/skill_preprocessing.py
agent/skill_utils.py
agent/stream_diag.py
agent/subdirectory_hints.py
agent/system_prompt.py
agent/think_scrubber.py
agent/title_generator.py
agent/tool_dispatch_helpers.py
agent/tool_executor.py
agent/tool_guardrails.py
agent/tool_result_classification.py
agent/trajectory.py
agent/transports/__init__.py
agent/transports/anthropic.py
agent/transports/base.py
agent/transports/bedrock.py
agent/transports/chat_completions.py
agent/transports/codex.py
agent/transports/codex_app_server.py
agent/transports/codex_app_server_session.py
agent/transports/codex_event_projector.py
agent/transports/hermes_tools_mcp_server.py
agent/transports/types.py
agent/usage_pricing.py
agent/video_gen_provider.py
agent/video_gen_registry.py
agent/web_search_provider.py
agent/web_search_registry.py
```

---

## `hermes_cli/` — CLI + workers + proxy + web server

```
hermes_cli/__init__.py
hermes_cli/_parser.py
hermes_cli/_subprocess_compat.py
hermes_cli/auth.py                            (7,474 LOC)
hermes_cli/auth_commands.py
hermes_cli/azure_detect.py
hermes_cli/backup.py
hermes_cli/banner.py
hermes_cli/browser_connect.py
hermes_cli/bundles.py
hermes_cli/callbacks.py
hermes_cli/checkpoints.py
hermes_cli/claw.py
hermes_cli/cli_output.py
hermes_cli/clipboard.py
hermes_cli/codex_models.py
hermes_cli/codex_runtime_plugin_migration.py
hermes_cli/codex_runtime_switch.py
hermes_cli/colors.py
hermes_cli/commands.py                        (1,787 LOC — slash registry)
hermes_cli/completion.py
hermes_cli/config.py                          (5,546 LOC)
hermes_cli/copilot_auth.py
hermes_cli/cron.py
hermes_cli/curator.py
hermes_cli/curses_ui.py
hermes_cli/debug.py
hermes_cli/default_soul.py
hermes_cli/dep_ensure.py
hermes_cli/dingtalk_auth.py
hermes_cli/doctor.py
hermes_cli/dump.py
hermes_cli/env_loader.py
hermes_cli/fallback_cmd.py
hermes_cli/gateway.py                         (5,467 LOC)
hermes_cli/gateway_windows.py
hermes_cli/github_publisher.py
hermes_cli/goals.py
hermes_cli/hooks.py
hermes_cli/inventory.py
hermes_cli/job_controller.py
hermes_cli/kanban.py
hermes_cli/kanban_db.py                       (6,233 LOC)
hermes_cli/kanban_decompose.py
hermes_cli/kanban_diagnostics.py
hermes_cli/kanban_specify.py
hermes_cli/kanban_swarm.py
hermes_cli/logs.py
hermes_cli/main.py                            (13,233 LOC — 140 subparsers)
hermes_cli/mcp_config.py
hermes_cli/memory_setup.py
hermes_cli/merge_engine.py
hermes_cli/model_catalog.py
hermes_cli/model_normalize.py
hermes_cli/model_switch.py
hermes_cli/models.py                          (3,788 LOC)
hermes_cli/nous_subscription.py
hermes_cli/oneshot.py
hermes_cli/orchestrator.py
hermes_cli/orchestrator_api.py
hermes_cli/orchestrator_models.py
hermes_cli/orchestrator_parallel.py
hermes_cli/pairing.py
hermes_cli/platforms.py
hermes_cli/plugins.py
hermes_cli/plugins_cmd.py
hermes_cli/profile_describer.py
hermes_cli/profile_distribution.py
hermes_cli/profiles.py
hermes_cli/providers.py
hermes_cli/proxy/__init__.py
hermes_cli/proxy/adapters/__init__.py
hermes_cli/proxy/adapters/base.py
hermes_cli/proxy/adapters/nous_portal.py
hermes_cli/proxy/adapters/xai.py
hermes_cli/proxy/cli.py
hermes_cli/proxy/server.py
hermes_cli/pt_input_extras.py
hermes_cli/pty_bridge.py
hermes_cli/relaunch.py
hermes_cli/runtime_provider.py
hermes_cli/scoring.py
hermes_cli/security_advisories.py
hermes_cli/send_cmd.py
hermes_cli/session_recap.py
hermes_cli/setup.py                           (3,557 LOC)
hermes_cli/skills_config.py
hermes_cli/skills_hub.py
hermes_cli/skin_engine.py
hermes_cli/slack_cli.py
hermes_cli/status.py
hermes_cli/stdio.py
hermes_cli/timeouts.py
hermes_cli/tips.py
hermes_cli/tools_config.py                    (3,205 LOC)
hermes_cli/uninstall.py
hermes_cli/validation.py                      (1,575 LOC — gates)
hermes_cli/vercel_auth.py
hermes_cli/voice.py                           (846 LOC)
hermes_cli/web_server.py                      (4,583 LOC)
hermes_cli/webhook.py
hermes_cli/workers/__init__.py
hermes_cli/workers/aider.py
hermes_cli/workers/base.py
hermes_cli/workers/chatgpt_handoff.py
hermes_cli/workers/claude_code.py
hermes_cli/workers/codex.py
hermes_cli/workers/goose.py
hermes_cli/workers/hermes_local.py
hermes_cli/workers/registry.py
hermes_cli/worktrees.py
```

---

## `tools/` — Built-in tools (registry-discovered)

```
tools/__init__.py
tools/ansi_strip.py
tools/approval.py
tools/binary_extensions.py
tools/browser_camofox.py
tools/browser_camofox_state.py
tools/browser_cdp_tool.py
tools/browser_dialog_tool.py
tools/browser_supervisor.py
tools/browser_tool.py                         (3,796 LOC)
tools/budget_config.py
tools/checkpoint_manager.py
tools/clarify_gateway.py
tools/clarify_tool.py
tools/code_execution_tool.py
tools/computer_use_tool.py
tools/credential_files.py
tools/cronjob_tools.py
tools/debug_helpers.py
tools/delegate_tool.py                        (2,801 LOC)
tools/discord_tool.py
tools/env_passthrough.py
tools/environments/__init__.py
tools/environments/base.py
tools/environments/daytona.py
tools/environments/docker.py
tools/environments/file_sync.py
tools/environments/local.py
tools/environments/managed_modal.py
tools/environments/modal.py
tools/environments/modal_utils.py
tools/environments/singularity.py
tools/environments/ssh.py
tools/environments/vercel_sandbox.py
tools/feishu_doc_tool.py
tools/feishu_drive_tool.py
tools/file_operations.py
tools/file_state.py
tools/file_tools.py
tools/fuzzy_match.py
tools/homeassistant_tool.py
tools/image_generation_tool.py
tools/interrupt.py
tools/kanban_tools.py
tools/lazy_deps.py
tools/managed_tool_gateway.py
tools/mcp_oauth.py
tools/mcp_oauth_manager.py
tools/mcp_tool.py                              (3,584 LOC)
tools/memory_tool.py
tools/microsoft_graph_auth.py
tools/microsoft_graph_client.py
tools/mixture_of_agents_tool.py
tools/neutts_synth.py
tools/openrouter_client.py
tools/osv_check.py
tools/patch_parser.py
tools/path_security.py
tools/process_registry.py
tools/registry.py
tools/schema_sanitizer.py
tools/send_message_tool.py
tools/session_search_tool.py
tools/skill_manager_tool.py
tools/skill_provenance.py
tools/skill_usage.py
tools/skills_guard.py
tools/skills_hub.py                            (3,438 LOC)
tools/skills_sync.py
tools/skills_tool.py
tools/slash_confirm.py
tools/terminal_tool.py
tools/tirith_security.py
tools/todo_tool.py
tools/tool_backend_helpers.py
tools/tool_output_limits.py
tools/tool_result_storage.py
tools/transcription_tools.py                   (936 LOC)
tools/tts_tool.py                              (2,289 LOC)
tools/url_safety.py
tools/video_generation_tool.py
tools/vision_tools.py
tools/voice_mode.py                            (1,018 LOC)
tools/web_tools.py
tools/website_policy.py
tools/x_search_tool.py
tools/xai_http.py
tools/yuanbao_tools.py
```

---

## `gateway/` — Messaging gateway

```
gateway/__init__.py
gateway/assets/                                Assets (telegram BotFather screenshots)
gateway/builtin_hooks/__init__.py
gateway/channel_directory.py
gateway/config.py
gateway/delivery.py
gateway/display_config.py
gateway/hooks.py
gateway/memory_monitor.py
gateway/mirror.py
gateway/pairing.py
gateway/platform_registry.py
gateway/platforms/_http_client_limits.py
gateway/platforms/__init__.py
gateway/platforms/ADDING_A_PLATFORM.md
gateway/platforms/api_server.py
gateway/platforms/base.py
gateway/platforms/bluebubbles.py
gateway/platforms/dingtalk.py
gateway/platforms/discord.py
gateway/platforms/email.py
gateway/platforms/feishu.py
gateway/platforms/feishu_comment.py
gateway/platforms/feishu_comment_rules.py
gateway/platforms/helpers.py
gateway/platforms/homeassistant.py
gateway/platforms/matrix.py
gateway/platforms/mattermost.py
gateway/platforms/msgraph_webhook.py
gateway/platforms/qqbot/{__init__,adapter,chunked_upload,constants,crypto,keyboards,onboard,utils}.py
gateway/platforms/signal.py
gateway/platforms/signal_rate_limit.py
gateway/platforms/slack.py
gateway/platforms/sms.py
gateway/platforms/telegram.py
gateway/platforms/telegram_network.py
gateway/platforms/webhook.py
gateway/platforms/wecom.py
gateway/platforms/wecom_callback.py
gateway/platforms/wecom_crypto.py
gateway/platforms/weixin.py
gateway/platforms/whatsapp.py
gateway/platforms/yuanbao.py
gateway/platforms/yuanbao_media.py
gateway/platforms/yuanbao_proto.py
gateway/platforms/yuanbao_sticker.py
gateway/restart.py
gateway/run.py
gateway/runtime_footer.py
gateway/session.py
gateway/session_context.py
gateway/shutdown_forensics.py
gateway/slash_access.py
gateway/status.py
gateway/sticker_cache.py
gateway/stream_consumer.py
gateway/whatsapp_identity.py
```

---

## `plugins/` — Plugin system

### Model providers (`plugins/model-providers/`, 22)

`ai-gateway`, `alibaba`, `alibaba-coding-plan`, `anthropic`, `arcee`,
`azure-foundry`, `bedrock`, `copilot`, `copilot-acp`, `custom`,
`deepseek`, `gemini`, `gmi`, `huggingface`, `kilocode`, `kimi-coding`,
`minimax`, `nous`, `novita`, `nvidia`, `ollama-cloud`, `openai-codex`,
`opencode-zen`, `openrouter`, `qwen-oauth`, `stepfun`, `xai`,
`xiaomi`, `zai`.

### Memory (`plugins/memory/`, 8)

`byterover`, `hindsight`, `holographic`, `honcho`, `mem0`, `openviking`,
`retaindb`, `supermemory`.

### Web / search (`plugins/web/`, 7)

`brave_free`, `ddgs`, `exa`, `firecrawl`, `parallel`, `searxng`,
`tavily`.

### Browser (`plugins/browser/`, 3)

`browser_use`, `browserbase`, `firecrawl`.

### Image / video (`plugins/image_gen/`, `plugins/video_gen/`)

`image_gen/{openai, openai-codex, xai}`, `video_gen/{fal, xai}`.

### Platforms (extra gateway adapters, `plugins/platforms/`, 5)

`google_chat`, `irc`, `line`, `simplex`, `teams`.

### Single-plugin folders

`context_engine/`, `disk-cleanup/`, `example-dashboard/`,
`github_assistant/`, `google_meet/`, `hermes-achievements/`,
`kanban/`, `observability/langfuse/`, `spotify/`, `teams_pipeline/`.

---

## `skills/` — bundled (50+ skills, 157 files)

```
ai-improvement-radar/
aos-council-director/
aos-full-agent-team/
apple/{apple-notes,apple-reminders,findmy,imessage,macos-computer-use}
assurance-risk-director/
autonomous-ai-agents/{claude-code,codex,hermes-agent,kanban-codex-lane,opencode}
best-coding-tool-mission/
codex-dispatch-governor/
commercial-strategist/
competitive-feature-harvester/
contrarian-red-flag-analyst/
contrarian-reviewer/
creative/{architecture-diagram,ascii-art,ascii-video,baoyu-article-illustrator,
          baoyu-comic,baoyu-infographic,claude-design,comfyui,creative-ideation,
          design-md,excalidraw,humanizer,manim-video,p5js,pixel-art,
          popular-web-designs,pretext,sketch,songwriting-and-ai-music,
          touchdesigner-mcp}
data-science/jupyter-live-kernel
decision-quality-gate/
delivery-scope-controller/
developer-ux-command-center/
devops/{kanban-orchestrator,kanban-worker,webhook-subscriptions}
diagramming/
dogfood/
domain/
email/himalaya/
enterprise-council/{customer-service,finance,hr,judge,monitor,operations,orchestrator,sales,shared}
evidence-architect/
gaming/{minecraft-modpack-server,pokemon-player}
gifs/
github/{codebase-inspection,github-auth,github-code-review,github-issues,github-pr-workflow,github-repo-management}
github-publisher/
hermes-orchestration-pipeline/
index-cache/  (cached marketplace indexes)
inference-sh/
local-quality-gate/
mcp/native-mcp/
media/{gif-search,heartmula,songsee,spotify,youtube-content}
mlops/{huggingface-hub,evaluation,inference,models,research,training,vector-databases}
model-router/
note-taking/obsidian/
principal-systems-architect/
product-experience-architect/
productivity/{airtable,google-workspace,linear,maps,nano-pdf,notion,ocr-and-documents,powerpoint,teams-meeting-pipeline}
red-teaming/godmode/
research/{arxiv,blogwatcher,llm-wiki,polymarket,research-paper-writing}
research-validator/
self-improvement-loop/
smart-home/openhue/
social-media/xurl/
software-development/{debugging-hermes-tui-commands,hermes-agent-skill-authoring,
                     node-inspect-debugger,plan,python-debugpy,requesting-code-review,
                     spike,subagent-driven-development,systematic-debugging,
                     test-driven-development,writing-plans}
yuanbao/
```

---

## `optional-skills/` — opt-in (80 skills, 89 files)

```
autonomous-ai-agents/{blackbox,honcho}
blockchain/{evm,hyperliquid,solana}
communication/one-three-one-rule
creative/{blender-mcp,concept-diagrams,hyperframes,kanban-video-orchestrator,meme-generation}
devops/{cli,docker-management,pinggy-tunnel,watchers}
dogfood/adversarial-ux-test
email/agentmail
finance/{3-statement-model,comps-analysis,dcf-model,excel-author,lbo-model,merger-model,pptx-author,stocks}
health/{fitness-nutrition,neuroskill-bci}
mcp/{fastmcp,mcporter}
migration/openclaw-migration
mlops/{accelerate,chroma,clip,faiss,flash-attention,guidance,huggingface-tokenizers,
       instructor,lambda-labs,llava,modal,nemo-curator,peft,pinecone,
       pytorch-fsdp,pytorch-lightning,qdrant,saelens,simpo,slime,
       stable-diffusion,tensorrt-llm,torchtitan,whisper}
productivity/{canvas,here-now,memento-flashcards,shop-app,shopify,siyuan,telephony}
research/{bioinformatics,darwinian-evolver,domain-intel,drug-discovery,duckduckgo-search,
          gitnexus-explorer,osint-investigation,parallel-cli,qmd,scrapling,searxng-search}
security/{1password,oss-forensics,sherlock}
software-development/rest-graphql-debug
web-development/page-agent
```

---

## `tui_gateway/`, `acp_adapter/`, `cron/`

```
tui_gateway/{__init__,entry,event_publisher,render,server,slash_worker,transport,ws}.py
acp_adapter/{__init__,__main__,auth,edit_approval,entry,events,permissions,server,session,tools}.py
cron/{__init__,jobs,scheduler}.py
acp_registry/{agent.json,icon.svg}
```

---

## `ui-tui/` — Ink (React) TUI

```
ui-tui/{README.md,package.json,package-lock.json,
         tsconfig.{json,build.json},vitest.config.ts,eslint.config.mjs,
         babel.compiler.config.cjs,.prettierrc,.gitignore}
ui-tui/scripts/{build.mjs,profile-tui.mjs}
ui-tui/packages/hermes-ink/{index.{js,d.ts},text-input.{js,d.ts},ambient.d.ts,
                            package.json,package-lock.json}
ui-tui/src/{entry.tsx,app.tsx,banner.ts,gatewayClient.ts,gatewayTypes.ts,
            types.ts,theme.ts}
ui-tui/src/components/{thinking,appChrome,appOverlays,streamingMarkdown,
                      streamingAssistant,agentsOverlay,skillsHub,themed,
                      textInput,maskedPrompt,appLayout,overlayControls,
                      modelPicker,helpHint,fpsOverlay,prompts,markdown,
                      todoPanel,messageLine,branding,queuedMessages,
                      sessionPicker}.tsx
ui-tui/src/domain/{details,roles,messages,providers,usage,slash,paths,viewport}.ts
ui-tui/src/lib/{wheelAccel,externalLink,precisionWheel,openExternalUrl,
               memoryMonitor,virtualHeights,history,subagentTree,clipboard,
               forceTruecolor,circularBuffer,rpc,editor,termux,osc52,
               text,terminalParity,memory,inputMetrics,mathUnicode,fpsStore,
               perfPane,platform,terminalSetup,messages,gracefulExit,
               liveProgress,externalCli,viewportStore,emoji,prompt,
               terminalModes,reasoning,syntax,todo}.ts (plus *.test.ts)
ui-tui/src/config/{limits,timing}.ts
ui-tui/src/types/hermes-ink.d.ts
```

---

## `web/` — Vite/React 19 dashboard

```
web/{package.json,package-lock.json,tsconfig.{json,app.json,node.json},
      vite.config.ts,eslint.config.js,index.html,README.md}
web/public/
web/src/{App.tsx,main.tsx,index.css}
web/src/components/{SlashPopover,ModelInfoCard,ChatSidebar,SidebarStatusStrip,
                   PlatformsCard,SidebarFooter,BottomPickSheet,AutoField,
                   ThemeSwitcher,Toast,Backdrop,DeleteConfirmDialog,
                   OAuthProvidersCard,ToolCall,OAuthLoginModal,LanguageSwitcher,
                   Markdown,NouiTypography,ModelPickerDialog}.tsx
web/src/hooks/{useSidebarStatus,useConfirmDelete,useBelowBreakpoint,
              useToast,useModalBehavior}.ts
web/src/themes/{context.tsx,index.ts,presets.ts}
web/src/pages/{ConfigPage,EnvPage,DocsPage,ChatPage,PluginsPage,SessionsPage,
              ProfilesPage,CronPage,LogsPage,AnalyticsPage,SkillsPage,
              ModelsPage}.tsx
```

---

## `apps/android/` — Native Android cockpit

```
apps/android/{README.md,.gitignore,build.gradle.kts,settings.gradle.kts,
              gradle.properties,gradlew,gradlew.bat}
apps/android/gradle/{libs.versions.toml,wrapper/{gradle-wrapper.jar,gradle-wrapper.properties}}
apps/android/docs/ARCHITECTURE.md
apps/android/app/{build.gradle.kts,proguard-rules.pro}
apps/android/app/src/main/AndroidManifest.xml
apps/android/app/src/main/res/{xml/*,mipmap-anydpi-v26/*,values/*,
                              values-night/themes.xml,drawable/*}
apps/android/app/src/main/java/com/aci/hermes/{MainActivity,HermesApplication}.kt
apps/android/app/src/main/java/com/aci/hermes/util/LogBuffer.kt
apps/android/app/src/main/java/com/aci/hermes/service/HermesService.kt
apps/android/app/src/main/java/com/aci/hermes/di/AppContainer.kt
apps/android/app/src/main/java/com/aci/hermes/data/preferences/{ThemeMode,SettingsRepository}.kt
apps/android/app/src/main/java/com/aci/hermes/data/model/{AiToolProfile,HermesTask,HermesRole}.kt
apps/android/app/src/main/java/com/aci/hermes/data/orchestrator/{PromptBuilder,HermesTaskRepository,HandoffLauncher}.kt
apps/android/app/src/main/java/com/aci/hermes/data/termux/TermuxIntentBridge.kt
apps/android/app/src/main/java/com/aci/hermes/data/cockpit/CockpitApi.kt
apps/android/app/src/main/java/com/aci/hermes/ui/navigation/{Screen,HermesNavGraph}.kt
apps/android/app/src/main/java/com/aci/hermes/ui/theme/{Color,Type,Theme}.kt
apps/android/app/src/main/java/com/aci/hermes/ui/screens/orchestrator/{TaskDetailViewModel,OrchestratorScreen,OrchestratorViewModel,TaskDetailScreen}.kt
apps/android/app/src/main/java/com/aci/hermes/ui/screens/splash/SplashScreen.kt
apps/android/app/src/main/java/com/aci/hermes/ui/screens/settings/{SettingsScreen,SettingsViewModel}.kt
apps/android/app/src/main/java/com/aci/hermes/ui/screens/diagnostics/{DiagnosticsScreen,DiagnosticsViewModel}.kt
```

---

## `enterprise/` — Council, judge, monitor, policy

```
enterprise/{__init__,audit,council,judge,monitor,policy,secrets}.py
enterprise/adapters/{__init__,cs,finance,hr,ops,sales}.py
```

---

## `scripts/` — install / orchestrate / radar / termux / linting

```
scripts/install.sh                    Linux/macOS/WSL2/Termux installer
scripts/install.ps1                   Windows PowerShell installer
scripts/install.cmd                   Windows .cmd shim
scripts/install_psutil_android.py     Android psutil wheel installer
scripts/hermes-orchestrate.sh         One-shot bash orchestrator entry
scripts/hermes-ai-radar.sh            AI-improvement radar entry
scripts/hermes-gateway                Gateway shell launcher
scripts/hermes-termux-service.sh      Termux service install/start/stop
scripts/hermes-termux-doctor.sh       Termux diagnostics
scripts/run_tests.sh                  Canonical pytest runner
scripts/lint_diff.py                  Ruff diff linter
scripts/check-windows-footguns.py     Cross-platform footgun scanner
scripts/keystroke_diagnostic.py
scripts/profile-tui.py
scripts/discord-voice-doctor.py
scripts/build_skills_index.py         Skills marketplace index builder
scripts/build_model_catalog.py        Model catalog generator
scripts/contributor_audit.py          Author + DCO audit
scripts/benchmark_browser_eval.py
scripts/sample_and_compress.py        Trajectory sampler/compressor
scripts/setup_open_webui.sh           Open WebUI integration setup
scripts/release.py                    Release helper
scripts/kill_modal.sh                 Modal sandbox cleanup
scripts/lib/node-bootstrap.sh         Shared shell helpers
scripts/tests/test-install-ps1-stage-protocol.ps1   Install script test
scripts/whatsapp-bridge/{bridge.js,allowlist.js,allowlist.test.mjs,
                         package.json,package-lock.json}   WhatsApp Node bridge
```

---

## `docs/` — Documentation

```
docs/github-integration.md
docs/hermes-kanban-v1-spec.pdf
docs/hermes-local-orchestrator.md
docs/ai-intelligence/{ai-improvement-radar.md,model-registry.yaml,model-routing-policy.md,tool-capability-matrix.md}
docs/android/{hermes-apk-api-contract,hermes-apk-cockpit,hermes-apk-ui-wireframes,termux-intent-bridge}.md
docs/competitive/{developer-agent-feature-harvest,openhuman-paperclip-research}.md
docs/mission/best-coding-tool-mission.md
docs/orchestration/{
  NEXT_PHASE_IMPLEMENTATION_PROMPT,
  PHASES,
  README,
  android-termux-demo,
  decision-ledger,
  decision-quality-system,
  faq,
  final-10-10-readiness-report,
  final-hermes-orchestration-integration-report,
  getting-started,
  github-publisher-runtime,
  hermes-agent-skill-map,
  hermes-orchestration-pipeline,
  job-controller-roadmap,
  known-limitations,
  local-api-backend,
  local-validation-gates,
  next-roadmap,
  orchestrator-command-reference,
  orchestrator-command-roadmap,
  parallel-workers-and-worktrees,
  phase-0-evidence-audit,
  phase-9-validation-report,
  private-local-mode,
  prompt-to-pr-demo,
  release-checklist,
  scoring-and-merge-engine,
  self-improvement-loop,
  troubleshooting,
  worker-adapter-interface,
  worker-adapters,
  workers/{aider,claude-code,codex,goose}-worker
}.md
docs/plans/{2026-05-02-telegram-dm-user-managed-multisession-topics,
            2026-05-15-acp-zed-edit-approval-diffs}.md
docs/product/hermes-feature-backlog.md
docs/termux/{hermes-android-permissions,hermes-phone-first-runtime,hermes-termux-boot}.md
docs/audits/{hermes-full-repo-audit,hermes-file-inventory,hermes-10-10-gap-report}.md  (this audit)
```

---

## `tests/` — Pytest suite (1,151 files)

Top-level test files (78 files) include:
`test_account_usage.py`, `test_atomic_replace_symlinks.py`,
`test_base_url_hostname.py`, `test_batch_runner_checkpoint.py`,
`test_cli_file_drop.py`, `test_cli_manual_compress.py`,
`test_cli_skin_integration.py`, `test_ctx_halving_fix.py`,
`test_empty_model_fallback.py`, `test_evidence_store.py`,
`test_gateway_streaming_nested_config.py`,
`test_get_tool_definitions_cache_isolation.py`,
`test_github_publisher.py`, `test_hermes_bootstrap.py`,
`test_hermes_constants.py`, `test_hermes_home_profile_warning.py`,
`test_hermes_logging.py`, `test_hermes_state.py`,
`test_hermes_state_wal_fallback.py`, `test_honcho_client_config.py`,
`test_install_sh_*` (5 files), `test_ipv4_preference.py`,
`test_lazy_session_regressions.py`, `test_lint_config.py`,
`test_live_system_guard_self_test.py`, `test_mcp_serve.py`,
`test_merge_engine.py`, `test_mini_swe_runner.py`,
`test_minimax_model_validation.py`, `test_minimax_oauth.py`,
`test_minisweagent_path.py`, `test_model_picker_scroll.py`,
`test_model_tools.py`, `test_model_tools_async_bridge.py`,
`test_ollama_num_ctx.py`, `test_orchestrator_api.py`,
`test_orchestrator_commands.py`, `test_orchestrator_job_controller.py`,
`test_package_json_lazy_deps.py`, `test_packaging_metadata.py`,
`test_parallel_orchestration.py`, `test_plugin_skills.py`,
`test_process_loop_event_loop_warning.py`, `test_project_metadata.py`,
`test_retry_utils.py`, `test_sanitize_tool_error.py`,
`test_scoring.py`, `test_sql_injection.py`,
`test_subprocess_home_isolation.py`,
`test_termux_all_extra_compat.py`, `test_timezone.py`,
`test_toolset_distributions.py`, `test_toolsets.py`,
`test_trajectory_compressor.py`, `test_trajectory_compressor_async.py`,
`test_transform_llm_output_hook.py`, `test_transform_tool_result_hook.py`,
`test_tui_gateway_server.py`, `test_utils_truthy_values.py`,
`test_validation_gates.py`,
`test_worker_adapter_base.py`,
`test_worker_aider.py`, `test_worker_claude_code.py`,
`test_worker_codex.py`, `test_worker_goose.py`,
`test_worker_hermes_local.py`, `test_worktrees.py`,
`test_yuanbao_integration.py`, `test_yuanbao_markdown.py`,
`test_yuanbao_pipeline.py`, `test_yuanbao_proto.py`,
plus `conftest.py` (972 LOC) and `run_interrupt_test.py`.

Subdirectories: `acp/`, `acp_adapter/`, `agent/` (with `lsp/`,
`transports/`), `cli/`, `cron/`, `e2e/` (with
`matrix_xsign_bootstrap/`), `enterprise/`, `fakes/`, `gateway/`,
`hermes_cli/`, `hermes_state/`, `honcho_plugin/`, `integration/`,
`openviking_plugin/`, `plugins/` (with `browser/`,
`github_assistant/`, `image_gen/`, `memory/`, `model_providers/`,
`video_gen/`, `web/`), `providers/`, `run_agent/`, `scripts/`,
`skills/`, `stress/`, `tools/`, `tui_gateway/`, `website/`.

---

## `.github/` — CI

```
.github/PULL_REQUEST_TEMPLATE.md
.github/dependabot.yml
.github/ISSUE_TEMPLATE/{bug_report,feature_request,setup_help,config}.yml
.github/actions/hermes-smoke-test/action.yml
.github/actions/nix-setup/action.yml
.github/workflows/{tests,lint,nix,nix-lockfile-fix,
                   android-build,docker-publish,deploy-site,
                   docs-site-checks,orchestration-tests,
                   osv-scanner,supply-chain-audit,uv-lockfile-check,
                   upload_to_pypi,skills-index,history-check,
                   contributor-check}.yml
```

---

## `templates/`

```
templates/orchestration/{council-review.md,job-retrospective.md,scorecard.json}
```

---

## Notable single-file root modules

These are exposed via `pyproject.toml`'s `py-modules` list and are
importable from any subdir without `package.` prefix:

```
run_agent           # AIAgent
model_tools         # tool dispatch
toolsets            # _HERMES_CORE_TOOLS / TOOLSETS
batch_runner        # parallel batch runner
trajectory_compressor
toolset_distributions
cli                 # HermesCLI
hermes_bootstrap    # Windows UTF-8 stdio
hermes_constants    # get_hermes_home / display_hermes_home
hermes_state        # SQLite session store
hermes_time         # tz helpers
hermes_logging      # logging setup
utils
```

The `[project.scripts]` block in `pyproject.toml` registers three CLIs:

```
hermes          → hermes_cli.main:main
hermes-agent    → run_agent:main
hermes-acp      → acp_adapter.entry:main
```
