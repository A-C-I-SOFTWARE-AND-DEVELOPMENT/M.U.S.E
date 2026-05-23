# Developer-Agent Feature Harvest

**Phase 21 — Competitive feature harvest for Hermes.**

A verified survey of distinctive features across competing AI developer agents,
cross-referenced against what Hermes already ships. The output of this doc is a
research base; the prioritized adoption list lives in
[`docs/product/hermes-feature-backlog.md`](../product/hermes-feature-backlog.md).

**Date:** 2026-05-23
**Scope:** Claude Code, Codex CLI, Aider, OpenHands, Continue, Goose, OpenHuman,
Paperclip, OpenClaw, plus adjacent tools (Cline, Cursor, Roo Code, Zed/ACP,
Gemini CLI, Devin, SWE-agent, Plandex, bolt.new/Lovable, Smol Developer,
GPT Engineer).

**Method:** Eight parallel research subagents (one Hermes inventory + seven
competitor groups). Each was briefed to cite official sources, mark unverified
claims, and flag dormant projects. Results synthesized below. Full disambiguation
of OpenHuman and Paperclip lives in
[`openhuman-paperclip-research.md`](./openhuman-paperclip-research.md).

**Rules used:**
- Prefer official sources (docs.*, github.com/<org>/<repo>/README.md, release notes)
- Reputable reviews are secondary and marked as such
- Unverified claims marked unverified
- "Applies to Hermes?" reflects the codebase as of commit on `claude/competitive-feature-harvest-2XQx8`
- No feature is claimed as "copied" unless verified in a Hermes release

---

## Hermes baseline (as of May 2026)

Confirmed shipping (from the inventory pass on this branch):

| Area | Status |
|---|---|
| Multi-turn agent loop, tool calling | ✅ `run_agent.py`, `model_tools.py` |
| Subagent delegation (single + batch, orchestrator role) | ✅ `tools/delegate_tool.py` |
| Context compression / session resume / FTS5 session search | ✅ `agent/context_compressor.py`, `hermes_state.py` |
| Persistent memory (Honcho, Mem0, byterover, supermemory, …) | ✅ `plugins/memory/` |
| Multi-platform gateway (Telegram, Discord, Slack, WhatsApp, Signal, Email, Matrix, SMS, …) | ✅ `gateway/platforms/` |
| OpenAI-compatible API server | ✅ `gateway/platforms/api_server.py` |
| MCP client + ACP adapter | ✅ `acp_adapter/`, MCP tool surfaces |
| Cron / webhooks / hooks (pre/post tool, session lifecycle) | ✅ `cron/`, `gateway/platforms/webhook.py`, plugin lifecycle hooks |
| Skills + skill auto-creation + curator | ✅ `skills/`, `agent/curator.py` |
| Skill hub (ClawHub / GitHub discovery) | ✅ `tools/skills_hub.py` |
| Sandboxes (local, Docker, SSH, Modal, Daytona, Singularity, Vercel) | ✅ `tools/environments/` |
| Checkpoints / git-based undo | ✅ `tools/checkpoint_manager.py` |
| Voice in, image in, web search, browser tool | ✅ `hermes_cli/voice.py`, browser/web tools |
| Kanban multi-agent board | ✅ `plugins/kanban/`, `tools/kanban_tools.py` |
| SWE-bench mini runner, batch trajectory gen, trajectory compression | ✅ `mini_swe_runner.py`, `batch_runner.py`, `trajectory_compressor.py` |
| Profiles, personality, skin/theme engine, doctor, dashboard | ✅ `hermes_cli/` |
| Android native companion app | ✅ `apps/android/` |
| Cloud / serverless backends (Modal, Daytona, Vercel) | ✅ `tools/environments/` |
| Observability plugin (metrics/traces/logs) | ✅ `plugins/observability/` |

Confirmed gaps (the harvest below maps competitor features into these):

- ❌ **Repo map / tree-sitter symbol graph** (Aider's signature feature)
- ❌ **Native lint/test auto-fix loop** (Aider `--auto-lint`/`--auto-test`)
- ❌ **Project rules file analog** (`.cursorrules`, `.continue/rules`,
  `.clinerules`, `.goosehints`; Hermes has `AGENTS.md` and `config.yaml`,
  no per-glob rule activation)
- ❌ **YAML recipes** (Goose-style parameterized workflows; Hermes has cron
  jobs and skills, no separate "recipe" primitive)
- ❌ **Inline editor trigger** (Aider's `AI!` / `AI?` watch-mode comments)
- ❌ **OS-level sandbox profiles** (Codex's Seatbelt/Landlock; Hermes has
  container-level isolation, not process-level syscall filtering)
- ❌ **Plan branches / diff sandbox** (Plandex git-style plan branching)
- ❌ **Public leaderboard for model selection** (Aider Polyglot)
- ⚠️ **Native git tool for branch/commit/PR** (PARTIAL — checkpoints use git,
  but no first-class `git` tool exposing branch/commit/PR to the agent)

---

## Master harvest table

> Read the columns as: **Product · Feature · Source · Why users love it ·
> Applies to Hermes? · Implementation target · Confidence**
>
> *Source confidence labels:* H = official docs, M = blog/reputable review,
> L = single source / vendor claim only.

### Claude Code (Anthropic)

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| Claude Code | Hooks with 25+ event taxonomy (PreToolUse, PostToolBatch, PreCompact, SubagentStart/Stop, FileChanged, Elicitation, …) + structured `permissionDecision` | https://code.claude.com/docs/en/hooks | Deterministic guardrails without prompt engineering | PARTIAL — Hermes has pre/post tool + session start/end; missing `PreCompact`, `SubagentStart/Stop`, `FileChanged`, `Elicitation` events and structured permission decisions | Extend plugin hook taxonomy in `model_tools.py` and `run_agent.py`; document in `AGENTS.md` plugin section | H |
| Claude Code | Skills as `SKILL.md` artifacts with `allowed-tools`, `paths` globs, `context: fork`, dynamic shell injection via `` !`cmd` `` | https://code.claude.com/docs/en/skills | One artifact serves as slash command, auto-workflow, or subagent task | PARTIAL — Hermes skills exist; missing `allowed-tools`, `paths` glob auto-activation, `context: fork`, and `` !`shell` `` dynamic injection | Add front-matter fields + loader logic in `agent/skill_commands.py` | H |
| Claude Code | Output styles (Default / Proactive / Explanatory / Learning + custom Markdown) | https://code.claude.com/docs/en/output-styles | Same engine becomes tutor, writer, analyst without per-turn re-prompting | GAP — high value | Add `output_styles` plugin surface + `/style` slash command; lives alongside personalities | H |
| Claude Code | Subagents with explicit isolation: bundled `Explore` and `Plan` skip CLAUDE.md/git to stay lean | https://code.claude.com/docs/en/sub-agents | Context-window savings + cheap-model routing | PARTIAL — Hermes `delegate_task` has roles (leaf/orchestrator), but no bundled `Explore`/`Plan` agents that pre-strip context | Ship two preset delegation profiles (`explore`, `plan`) in `tools/delegate_tool.py` | H |
| Claude Code | Agent SDK (Python + TypeScript) exposing the same loop, hooks, subagents, sessions, built-in tools | https://code.claude.com/docs/en/agent-sdk/overview | Lets you embed the full agent loop in your product | GAP — Hermes has an embeddable `AIAgent` class but no published SDK package | Document `AIAgent` as a public API + publish a thin TypeScript wrapper that speaks the gateway JSON-RPC | H |
| Claude Code | Claude Code on the web — managed sandboxed VM sessions, `--teleport`/`--remote` to move between cloud and laptop | https://code.claude.com/docs/en/claude-code-on-the-web | Long-running tasks survive laptop close; mobile monitoring | PARTIAL — Hermes runs on Modal/Daytona/Vercel sandboxes but no `--teleport` between local and remote sessions | Add session-handoff RPC between gateway instances; reuse existing kanban claim mechanic | H |
| Claude Code | GitHub Actions v1 (`anthropics/claude-code-action@v1`) — `@claude` mention in issue/PR triggers PR creation | https://code.claude.com/docs/en/github-actions | One-shot setup, no bespoke webhook plumbing | PARTIAL — Hermes has webhooks + `github-code-review` skill; no off-the-shelf reusable Action | Ship `nousresearch/hermes-action@v1` wrapping `hermes webhook subscribe` + GitHub App template | H |
| Claude Code | Plan mode + Proactive mode (output-style + permission-mode pair) | https://code.claude.com/docs/en/permission-modes | Cautious review vs hands-off automation toggle | GAP — high value | Add two permission modes wired into approval system: `plan-only` (read-only tools), `proactive` (auto-approve safe tool classes) | H |
| Claude Code | Bundled `/security-review`, `/init`, `/verify` skills | https://code.claude.com/docs/en/skills | Zero-config security and onboarding | PARTIAL — Hermes has `requesting-code-review` skill and `setup-hermes.sh`; no `/security-review` skill nor a `/verify` that drives a running app | Add bundled `security-review` skill (cf. Hermes' existing `red-teaming` category); add `verify` skill referencing `skills/run` pattern | H |
| Claude Code | Multi-directory workspaces (`--add-dir`) — grants tool access to extra dirs and auto-loads their `.claude/skills/` | https://code.claude.com/docs/en/skills | Monorepo / multi-repo agent sessions | GAP — Hermes `terminal.cwd` is single-rooted | Add `--add-dir` to CLI + gateway `terminal.allowed_roots` config + skill discovery sweep | H |
| Claude Code | Effort levels (low / medium / high / xhigh / max) per skill, plus per-skill model override | https://code.claude.com/docs/en/skills | Cost/quality dial per workflow | GAP — Hermes has `reasoning_config` and `auxiliary` clients; not exposed per-skill | Add `model:` and `effort:` frontmatter fields in `SKILL.md` → resolved at skill activation | H |
| Claude Code | Routines / scheduled tasks / `/loop` (Anthropic-managed scheduling) | https://code.claude.com/docs/en/routines (referenced) | Cron-grade scheduling integrated with agent context | ALREADY SHIPS — see `cron/` and `hermes-already-has-routines.md` | — | H |
| Claude Code | Channels (Telegram / Discord / iMessage / webhook ingress into existing session) | https://code.claude.com/docs/en/channels (referenced) | Direct overlap with Hermes' gateway concept | ALREADY SHIPS — see `gateway/platforms/` | — | H |

### Codex CLI (OpenAI)

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| Codex CLI | Sandbox profiles backed by Seatbelt (macOS) / Landlock (Linux): `read-only`, `workspace-write`, `danger-full-access` | https://developers.openai.com/codex/cli/reference | OS-enforced isolation vs prompt-level promises | GAP — high value | Add OS-level sandbox wrapper in `tools/environments/local.py`; document as `terminal.sandbox_profile` config | H |
| Codex CLI | Approval modes: `untrusted` / `on-failure` / `on-request` / `never`; switchable mid-session via `/permissions` | https://developers.openai.com/codex/cli/features | Granular trust dial separate from sandbox | PARTIAL — Hermes has `tools/approval.py` + `subagent_auto_approve`; no `/permissions` slash command or `on-failure` mode | Add `/permissions` slash command + `on-failure` policy in approval gate | H |
| Codex CLI | AGENTS.md with three-tier override (`~/.codex/AGENTS.override.md` → `~/.codex/AGENTS.md` → walk from git root); concatenated up to `project_doc_max_bytes` | https://developers.openai.com/codex/guides/agents-md | Vendor-neutral, override-friendly context file | PARTIAL — Hermes uses `AGENTS.md` at repo root; no `.override.md` layer, no walk-up concatenation, no byte cap | Extend `_load_context_files()` in `run_agent.py` to walk + cap | H |
| Codex CLI | `codex exec` headless mode with `--json` event stream, `--ephemeral`, `--output-last-message` | https://developers.openai.com/codex/cli/reference | Drop-in for shell pipelines and CI | PARTIAL — Hermes has `hermes` CLI; no documented `--json` event stream over stdout | Add `hermes exec --json` non-interactive subcommand to `hermes_cli/` | H |
| Codex CLI | Profiles loaded via `--profile`/`-p` bundling model + sandbox + approval + MCP defaults | https://developers.openai.com/codex/cli/reference | Switch personas without long flag strings | ALREADY SHIPS — Hermes profile system in `hermes_cli/profiles.py` | — | H |
| Codex CLI | Image input via `-i`/`--image` (PNG/JPEG attachments) | https://developers.openai.com/codex/cli/reference | UI bug reports with screenshots | ALREADY SHIPS — vision tools | — | H |
| Codex CLI | Resumable sessions (`codex resume [SESSION_ID]`, `codex exec resume --last`) | https://developers.openai.com/codex/cli/reference | Restart without losing place | ALREADY SHIPS — session resume in `hermes_state.py` | — | H |
| Codex CLI | Codex Cloud — browser/IDE-launched cloud sandbox; `@codex` mention in PRs/issues | https://developers.openai.com/codex/cloud | Background/parallel execution outside laptop | PARTIAL — Hermes has Modal/Daytona/Vercel sandboxes; no `@hermes` GitHub mention flow | See Claude-Code `nousresearch/hermes-action@v1` row above | H |
| Codex CLI | GitHub Action with `safety-strategy: drop-sudo`, `unprivileged-user`, `allow-users`/`allow-bots` | https://github.com/openai/codex-action | Privilege-drop guards in CI | GAP — high value | Include the same safety controls in the proposed `hermes-action@v1` template | H |
| Codex CLI | `--dangerously-bypass-approvals-and-sandbox` escape hatch | https://developers.openai.com/codex/cli/reference | Single explicit flag for disposable envs | GAP — low value | Optional `--unsafe` flag mirroring intent; explicit is better than ad-hoc env vars | H |
| Codex CLI | Codex SDK (TypeScript GA + Python experimental): `startThread()`, `run()`, `resumeThread()` | https://developers.openai.com/codex/sdk | Programmatic mirror of CLI behavior | GAP — see Claude Code SDK row | — | H |

### Aider

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| Aider | Repo map: tree-sitter symbol extraction + PageRank-style graph ranking, fixed `--map-tokens` budget | https://aider.chat/docs/repomap.html | "Enough context to solve many tasks" within a token budget | GAP — high value | New tool: `tools/repo_map.py` using `py-tree-sitter-languages`; surface via toolset `code_intel` | H |
| Aider | Auto-commit every AI edit with Conventional-Commit messages; pre-existing dirty changes auto-committed first; "(aider)" author tag | https://aider.chat/docs/git.html | Safe undo + clean history + attribution | PARTIAL — Hermes checkpoints use git diff/restore but don't author conventional commits per turn | Optional `git.auto_commit` mode in `tools/checkpoint_manager.py` | H |
| Aider | `/undo`, `/diff`, `/commit`, `/git` in-chat commands | https://aider.chat/docs/git.html | One command rolls back risky edits | PARTIAL — Hermes has checkpoint restore; no `/undo` slash command | Add `/undo`, `/diff` slash commands wrapping checkpoint manager | H |
| Aider | Watch mode (`--watch-files`) with `AI!` / `AI?` triggers in code comments | https://aider.chat/docs/usage/watch.html | Any editor becomes an agent frontend with zero plugin | GAP — high value | New `hermes watch` mode using `watchdog`; configurable trigger patterns | H |
| Aider | CONVENTIONS.md auto-loaded into context, cache-eligible | https://aider.chat/docs/usage/conventions.html | Per-project house style without re-prompting | PARTIAL — Hermes loads `AGENTS.md`; not a dedicated `CONVENTIONS.md` pattern with cache hint | Document `AGENTS.md` as the canonical conventions surface; add cache-eligibility flag in context loading | H |
| Aider | Linter integration (`--lint-cmd`, `--auto-lint`): runs after each edit, feeds errors back to LLM | https://aider.chat/docs/usage/lint-test.html | Closes edit-lint-fix loop automatically | GAP — high value | Add `code.auto_lint` config + post-edit hook that re-prompts on non-zero exit | H |
| Aider | Test-driven loop (`--test-cmd`, `--auto-test`, `/test`) | https://aider.chat/docs/usage/lint-test.html | Iterative auto-repair against real tests | GAP — high value | Same hook as above with `--test-cmd`; slash command `/test` | H |
| Aider | Architect/editor split: `/architect` plans with one model, edits with another | https://aider.chat/docs/usage/commands.html | Mix strong-reasoning + cheap-edit models | PARTIAL — Hermes `auxiliary` config supports per-task model overrides; no `/architect` slash command | Add `/architect` mode + document existing `auxiliary` knobs as the routing mechanism | H |
| Aider | Prompt caching (`--cache-prompts`, `--cache-keepalive-pings`) — Anthropic 5-min TTL refresh | https://aider.chat/docs/usage/caching.html | Avoid re-paying for the same context mid-session | PARTIAL — Hermes does prompt caching for Anthropic; no explicit keepalive ping loop | Add optional cache-keepalive ticker in `agent/` provider adapter | H |
| Aider | `--read` / `/read-only` for reference files (cache-eligible, not editable) | https://aider.chat/docs/usage/commands.html | Cheap safe grounding on big docs | PARTIAL — Hermes loads context files; no explicit read-only flag preventing edits | Add `read_only_paths` list in context loader + safety check in edit tools | H |
| Aider | Voice coding (`/voice`) | https://aider.chat/docs/usage/voice.html | Hands-free feature requests / tests / bug reports | ALREADY SHIPS — `hermes_cli/voice.py` | — | H |
| Aider | Image/URL ingestion (`/web <url>` scrapes to markdown; paste prompts to add URL) | https://aider.chat/docs/usage/images-urls.html | Ground model on UI screenshots and fresh API docs | PARTIAL — Hermes has `web_extract`; no `/web` slash command equivalent | Add `/web` slash command wrapping `web_extract` | H |
| Aider | Polyglot Leaderboard (225 Exercism problems × 6 languages, reports accuracy AND cost) | https://aider.chat/docs/leaderboards/ | Vendor-neutral, reproducible model selection guide | GAP — Hermes has `mini_swe_runner.py` but no published per-model cost+accuracy table | Run leaderboard at release time; publish to `website/docs/benchmarks/` | H |
| Aider | Browser mode (`--browser`) Streamlit-based GUI | https://aider.chat/docs/usage/browser.html | GUI without losing git integration | PARTIAL — Hermes dashboard is a web UI; deliberately differentiated from a Streamlit clone | — (out of scope vs Hermes dashboard) | H |

### OpenHands (All-Hands-AI)

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| OpenHands | CodeActAgent — unified action space: chat + bash + IPython | https://docs.openhands.dev/openhands/usage/agents | Strong SWE-bench numbers from action-space unification | PARTIAL — Hermes has `code_execution` toolset (Python) and `terminal`; not a single unified action space | Document existing combo as the equivalent; no code change | H |
| OpenHands | Docker sandbox runtime: client/server REST over OH Runtime Image | https://docs.openhands.dev/openhands/usage/architecture/runtime | Reproducible builds, isolation, "agent runs the build" | ALREADY SHIPS — `tools/environments/docker.py` | — | H |
| OpenHands | Headless mode (`openhands --headless -t "task"`, JSONL output) | https://docs.openhands.dev/openhands/usage/cli/headless | Same binary in CI and on desktop | PARTIAL — see Codex `codex exec` row; same backlog item | — | H |
| OpenHands | GitHub Resolver: `fix-me` label or `@openhands-agent` comment → sandboxed PR | https://docs.openhands.dev/openhands/usage/run-openhands/github-action | "Fully autonomous" backlog grinding | GAP — see `hermes-action@v1` row | — | H |
| OpenHands | Microagents / Skills (Permanent / Keyword / Organization / Global) | https://docs.openhands.dev/usage/prompting/microagents-overview | Same skill works across CLI, SDK, Local GUI, Cloud | PARTIAL — Hermes skills exist; no four-tier model (keyword vs org vs global) | Extend SKILL.md frontmatter with `triggers: [keyword: …]` + `scope: org\|global\|project` | H |
| OpenHands | Sub-agent delegation (`AgentDelegateAction`) — main agent spawns named sub-agents with custom prompts/tools | https://docs.openhands.dev/sdk/guides/agent-delegation | "Capabilities Claude Code and Codex don't offer" (secondary review) | ALREADY SHIPS — `delegate_task` with single + batch + orchestrator role | — | H |
| OpenHands | BrowsingAgent — dedicated browser-using sub-agent inside sandbox | https://docs.openhands.dev/openhands/usage/agents | Built-in browser automation | ALREADY SHIPS — `tools/browser_tool.py` + `browser_camofox.py` | — | M |
| OpenHands | Composable SDK (`openhands.sdk` + `tools` + `workspace` + `agent_server`); swappable `LocalWorkspace` / `DockerWorkspace` / `RemoteAPIWorkspace` | https://docs.openhands.dev/sdk/arch/overview | Same agent code laptop → 1000s in cloud | PARTIAL — Hermes terminals are swappable backends but not packaged as a published SDK | See Claude Code / Codex SDK row | H |
| OpenHands | Conversation / event-driven state, typed EventLog per sub-agent | https://docs.openhands.dev/sdk/arch/agent | Resumable, inspectable conversations in production | ALREADY SHIPS — session DB + per-subagent context | — | H |
| OpenHands | Security risk assessment layer: action validation pre-execution + `--llm-approve` | https://docs.openhands.dev/sdk/arch/overview | Zero-trust posture | PARTIAL — Hermes has approval system; no LLM-driven risk classifier | Add `llm_approve` plugin hook that runs a small model on proposed commands | M |
| OpenHands | Strong SWE-bench Verified track record (README badge 77.6; third-party citations ~72) | https://github.com/All-Hands-AI/OpenHands | Credibility moat | PARTIAL — Hermes has `mini_swe_runner.py`; no published headline SWE-bench number | Publish benchmark to website + README badge | M |
| OpenHands | Enterprise self-hosted on Kubernetes (VPC deployment) | https://github.com/All-Hands-AI/OpenHands | Compliance for orgs that can't use SaaS | PARTIAL — Hermes runs on any infra; no canonical Kubernetes chart | Ship `enterprise/k8s/` Helm chart (this directory already exists; verify completeness) | H |

### Continue

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| Continue | Four modes: Chat / Edit / Autocomplete / Agent in one extension | https://docs.continue.dev/ide-extensions/quick-start | One tool covers passive completion → autonomous agent | OUT OF SCOPE — Hermes is not an IDE extension | — | H |
| Continue | Agent mode with MCP tools, gated to Agent mode | https://docs.continue.dev/customize/deep-dives/mcp | Cross-tool MCP server reuse (Claude Desktop / Cursor / Cline configs all importable) | ALREADY SHIPS — Hermes MCP client | — | H |
| Continue | Next Edit prediction (Instinct / mercury-coder-nextedit models) | https://docs.continue.dev/ide-extensions/autocomplete/next-edit | Predicts the next change before you type it | OUT OF SCOPE — autocomplete is IDE territory | — | H |
| Continue | Context providers (`@File`, `@Codebase`, `@Diff`, `@Terminal`, `@Docs`, `@Web`, `@Url`, `@Repo-Map`, `@Problems`, `@Debugger`, …) | https://docs.continue.dev/customize/custom-providers | Granular composable context injection | PARTIAL — Hermes has many tools (web, browser, code search) but no unified `@`-prefix mention syntax in prompts | Add prompt-level `@<provider>` parser in CLI input handler; expand into tool calls | H |
| Continue | Continue Hub — marketplace of "blocks" (Models / Rules / Prompts / MCP / Docs / Data) composed into Assistants | https://docs.continue.dev/guides/understanding-assistants | `uses:` one-line imports | PARTIAL — Hermes skill hub (`tools/skills_hub.py`) covers skills; no marketplace for models/rules/prompts | Extend skills hub to a manifest format covering MCP servers, prompt templates, model presets | H |
| Continue | Rules system (`.continue/rules` + hub + global) with glob/regex activation, priority order, optional `alwaysApply` | https://docs.continue.dev/customize/deep-dives/rules | Conditional rules avoid bloating system prompt | GAP — high value | New `.hermesrules/` directory pattern (per-glob activation), loaded by `_load_context_files()` | H |
| Continue | Prompt files = custom slash commands; markdown with frontmatter, hub-shareable via `uses:` | https://docs.continue.dev/customize/deep-dives/prompts | Repeatable workflows version-controlled in repo | ALREADY SHIPS — Hermes skills are this exact pattern | — | H |
| Continue | Model roles: `chat`, `edit`, `apply`, `autocomplete`, `embeddings`, `rerank` | https://docs.continue.dev/customize/model-providers/overview | Per-role model assignment | PARTIAL — Hermes `auxiliary` config covers per-task overrides; not formalized as roles | Document `auxiliary` task list as the Hermes equivalent; add `apply` and `rerank` if missing | H |
| Continue | Dev data collection — JSON event capture to `.continue/dev_data` or remote HTTP | https://docs.continue.dev/customize/deep-dives/development-data | User-owned interaction data for fine-tuning / evals / audit | PARTIAL — Hermes has trajectory generation (`batch_runner.py`) but not an opt-in continuous interaction log | Add `data:` config section + writer that emits JSONL turn events | H |
| Continue | AI Checks on PRs (`.continue/checks/*.md` → GitHub status check) | https://github.com/continuedev/continue | Source-controlled AI policies that block merges | GAP — high value | Add `.hermes/checks/*.md` pattern + GitHub Action that runs each as a status check | H |
| Continue | Continue CLI (`cn`) — same hub prompts in IDE, CLI, CI | https://github.com/continuedev/continue | One assistant across surfaces | ALREADY SHIPS — Hermes CLI + gateway share skill set | — | H |

### Goose (Block)

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| Goose | Recipes — YAML workflows with Jinja2 parameters, semantic versioning, sub-recipe composition (sequential/parallel) | https://block-goose.mintlify.app/concepts/recipes | "Workflow infrastructure, not productivity shortcut" — team-shareable | GAP — high value | New `recipes/` primitive: YAML with `instructions`, `parameters`, `extensions`, `sub_recipes`; runner integrates with cron and `delegate_task` | H |
| Goose | MCP extensions (built-in + stdio + SSE), 70+ documented | https://block-goose.mintlify.app/concepts/extensions | Any MCP server works; "Goose shaped MCP" | ALREADY SHIPS — MCP client | — | H |
| Goose | Lead/Worker model split — `GOOSE_LEAD_MODEL` plans, `GOOSE_PLANNER_*` for `/plan`, cheaper model executes | https://github.com/block/goose | "Powerful model plans, faster/cheaper executes" — cost-optimal | PARTIAL — Hermes `auxiliary` covers this for many tasks; no canonical "lead model for planning, primary for execution" split | Document `auxiliary.planner` convention + `/plan` slash command using it | M |
| Goose | Sub-agents (parallel, isolated sessions, partial-success semantics) | https://dev.to/nickytonline/advent-of-ai-day-11-goose-subagents-2n2 (secondary) | Isolation + survives partial failures | ALREADY SHIPS — `delegate_task` batch mode | — | M |
| Goose | Built-in scheduler (`goose schedule`) on tokio-cron, recipe-aware | https://deepwiki.com/block/goose/4.1.5-scheduler-and-recurring-tasks (secondary) | Recipes become unattended automations | ALREADY SHIPS — `cron/scheduler.py` | — | H |
| Goose | Named sessions: `start`/`resume`/`list`/`remove`/`export` to JSON/YAML/Markdown with metadata | https://goose-docs.ai/docs/guides/goose-cli-commands/ | Easy to resume long-running engineering work | PARTIAL — Hermes resumes by session ID; no export to JSON/YAML/Markdown with full metadata + tokens + timestamps | Add `hermes session export <id> --format md\|json\|yaml` | H |
| Goose | 15-25+ providers (Anthropic, OpenAI, Vertex, Azure, Bedrock, Databricks, Snowflake Cortex, Copilot, OpenRouter, Venice.ai, Ollama, LiteLLM, llama.cpp, …) | https://block-goose.mintlify.app/concepts/providers | One abstraction across all major LLMs | ALREADY SHIPS — `plugins/model-providers/` | — | H |
| Goose | CLI + Desktop + API on a single Rust core | https://github.com/block/goose | One codebase across surfaces | PARTIAL — Hermes has CLI + TUI + gateway + dashboard; no native desktop app (Android exists, not desktop) | — (deliberate: dashboard covers the desktop use case) | H |
| Goose | `.goosehints` — per-project lightweight hints file | (cited via search summary; docs page returned 404 during research — Medium confidence) | Lightweight per-project steering | PARTIAL — Hermes uses `AGENTS.md`; no shorter "hints" alternative | Document `AGENTS.md` as Hermes' equivalent (no second file format needed) | M |
| Goose | OpenTelemetry + Langfuse — trace prompt/messages/tool calls/responses/timing | https://langfuse.com/docs/integrations/goose (secondary) | Production-grade tracing and cost tracking | PARTIAL — `plugins/observability/` exists; need to verify OTel exporter + Langfuse integration | Audit observability plugin; add OTel exporter if missing | H |
| Goose | Agent Client Protocol (ACP) support | https://github.com/block/goose | Vendor-neutral IDE/host portability | ALREADY SHIPS — `acp_adapter/`, `acp_registry/` | — | M |
| Goose | `goose bench` evaluation harness | https://block.github.io/goose/docs/tutorials/benchmarking/ | Measure scaffold quality, not just model quality | PARTIAL — Hermes has `mini_swe_runner.py` (SWE-bench-specific) | Generalize to `hermes bench` with pluggable suites | M |
| Goose | Custom distributions — rebrand/repackage for enterprise rollout | https://block-goose.mintlify.app/llms.txt | Enterprise rollout story | PARTIAL — `enterprise/` dir exists; rebranding is via skin engine; not a documented "custom distribution" workflow | Document the skin engine + plugin-set as the "custom distribution" mechanism | M |
| Goose | MCP-UI widget rendering in Desktop | https://www.nickyt.co/blog/what-makes-goose-different-from-other-ai-coding-agents-2edc/ (secondary) | "Superior experience vs text-based" responses | GAP — Hermes TUI is text; dashboard is HTML | Render MCP-UI responses in the dashboard React surface | M |
| Goose | Server deployment (REST + WS + SSE) for multi-user production | https://block-goose.mintlify.app/llms.txt | Self-hosted shared backend | ALREADY SHIPS — `gateway/platforms/api_server.py` + dashboard | — | M |

### OpenHuman (`tinyhumansai/openhuman`)

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| OpenHuman | Single Rust binary, local-first runtime | https://github.com/tinyhumansai/openhuman | One install, no dependency tree | OUT OF SCOPE — Hermes is Python-first by design | — | H |
| OpenHuman | "Memory Tree" + Obsidian Wiki — content canonicalized into ≤3k-token Markdown chunks, scored, folded into hierarchical summary trees in local SQLite; positioned as "persistent 1-billion-token memory" | https://tinyhumans.gitbook.io/openhuman, https://github.com/tinyhumansai/openhuman/blob/main/gitbooks/README.md | Users can browse/edit memory in their own knowledge tool; persistence survives across sessions and devices | GAP — possible memory plugin | New `plugins/memory/obsidian/` provider; the ≤3k-token chunking + hierarchical summary pattern is also worth porting into `agent/context_compressor.py` for non-Obsidian users | H |
| OpenHuman | TokenJuice rule overlay — HTML→Markdown, long URLs shortened, deduped/summarized tool outputs (vendor claim ~80% reduction in cost/latency) | https://github.com/tinyhumansai/openhuman/blob/main/gitbooks/features/token-compression.md | Cheaper turns without losing information | PARTIAL — Hermes has `trajectory_compressor.py` + `agent/context_compressor.py`; no documented per-tool-output rule overlay specifically targeting HTML/URL bloat | Add an opt-in `tool_output_filter` plugin hook that runs configured rewrite rules before tool results enter the message log | M |
| OpenHuman | 118+ OAuth integrations w/ periodic auto-fetch | https://github.com/tinyhumansai/openhuman | Personal-AI grounded in your services | OUT OF SCOPE — Hermes platform gateway covers messaging; deep OAuth-per-service is a plugin space | — | M |
| OpenHuman | Voice + desktop mascot + live Google Meet agent (STT in, ElevenLabs TTS out, mascot lip-sync) | https://github.com/tinyhumansai/openhuman | Personal-AI affordances | PARTIAL — Hermes voice exists; mascot is the skin engine + spinner faces; the `google_meet` plugin under `plugins/` covers the meeting integration — verify scope and TTS-out parity | Audit `plugins/google_meet/`; add ElevenLabs TTS-out adapter if missing | M |

See [`openhuman-paperclip-research.md`](./openhuman-paperclip-research.md) for
the full disambiguation.

### OpenClaw (`openclaw/openclaw`)

OpenClaw is the closest architectural analog to Hermes that exists today:
a local-first, multi-channel personal AI assistant with sandboxed sessions,
cron, webhooks, and a skill/plugin system. Treat this section as the most
load-bearing competitive read in the document.

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| OpenClaw | Local-first Gateway as "single control plane for sessions, channels, tools, and events" | https://github.com/openclaw/openclaw | One process, one config, everything talks through it | ALREADY SHIPS — `gateway/` is exactly this | — | H |
| OpenClaw | Multi-channel inbox across 24+ platforms (WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage, IRC, Teams, Matrix, Feishu, LINE, Mattermost, Nextcloud Talk, Nostr, Synology Chat, Tlon, Twitch, Zalo, WeChat, QQ, WebChat, …) | https://github.com/openclaw/openclaw | "Answers you on the channels you already use" | PARTIAL — Hermes ships ~10 platforms in `gateway/platforms/`; OpenClaw's list is ~2× longer (Feishu, LINE, Nostr, WeChat, QQ, Zalo, Tlon, Synology Chat, IRC notably missing from Hermes) | Add the missing channel adapters under `gateway/platforms/`; prioritize Feishu / WeChat / LINE for APAC reach | H |
| OpenClaw | Multi-agent routing — bind specific inbound channels/accounts to isolated agents | https://github.com/openclaw/openclaw | One Telegram account → ops agent, another → coding agent | PARTIAL — Hermes routes by user/channel but not by-account isolation as a first-class concept | Add `channel_routing:` config: per-channel/per-account profile binding | H |
| OpenClaw | Voice Wake + Talk Mode (macOS/iOS), continuous voice on Android | https://github.com/openclaw/openclaw | Hands-free always-on assistant | PARTIAL — Hermes has `hermes_cli/voice.py` (push-to-talk style); no wake-word/continuous mode on the Android app | Add wake-word listener to `apps/android/` companion + macOS menu-bar variant | H |
| OpenClaw | Live Canvas — agent-driven visual workspace | https://github.com/openclaw/openclaw | "Render a live Canvas you control" — visible reasoning surface for non-text outputs | GAP — high value | New canvas surface in the dashboard React app; agent tool `canvas.write(node, content)` | H |
| OpenClaw | SOUL.md — injected prompt file defining agent personality | https://github.com/openclaw/openclaw, https://github.com/mergisi/awesome-openclaw-agents | Personality as a file you can fork and PR | PARTIAL — Hermes personalities exist as YAML in `hermes_cli/personalities/`; no single SOUL.md convention nor a personality marketplace | Adopt SOUL.md as an alternate front-end for the existing personality system; document the marketplace pattern (see Continue Hub row) | H |
| OpenClaw | AGENTS.md, scoped — subdirectory-level overrides ("Read scoped `AGENTS.md` before subtree work") | https://github.com/openclaw/openclaw/blob/main/AGENTS.md | Per-subtree rules without bloating the root file | GAP — Hermes loads root `AGENTS.md`/`CLAUDE.md` only | Extend `_load_context_files()` in `run_agent.py` to walk up from cwd, concatenating scoped `AGENTS.md` files (cap by byte budget; cf. Codex `project_doc_max_bytes`) | H |
| OpenClaw | Workspace skills under `~/.openclaw/workspace/skills/` | https://github.com/openclaw/openclaw | User-owned skill location, separate from binary | ALREADY SHIPS — Hermes skill discovery covers `~/.hermes/skills/` etc. | — | H |
| OpenClaw | Sandbox modes for non-main sessions (Docker, SSH, OpenShell backends) | https://github.com/openclaw/openclaw | Isolation by default for delegated work | ALREADY SHIPS — `tools/environments/` covers Docker, SSH, Modal, Daytona, Singularity, Vercel | — | H |
| OpenClaw | First-class agent toolset: browser, canvas, nodes, cron, sessions | https://github.com/openclaw/openclaw | Batteries-included agent infra | PARTIAL — Hermes covers all except `canvas` and `nodes` (visual-flow editor) | Add `nodes`-style visual-flow editor as an optional `plugins/flow_designer/` (research effort first; not on the critical path) | M |
| OpenClaw | Companion apps for macOS, iOS, Android | https://github.com/openclaw/openclaw | "Always at hand" experience | PARTIAL — Hermes ships Android only (`apps/android/`); no macOS menu-bar nor iOS companion | Audit `apps/`; scope a macOS menu-bar app reusing the Android app's API client (lower priority than channel parity) | H |
| OpenClaw | DM pairing policies + explicit allowlisting for unknown senders | https://github.com/openclaw/openclaw | Security default that prevents stranger drift | PARTIAL — Hermes gateway has per-platform auth but no first-class "pair this DM thread" + allowlist UX | Add `gateway.security.allowlist` config + pairing flow in dashboard | H |
| OpenClaw | Marketplace of community agent templates ("162 production-ready AI agent templates… SOUL.md configs across 19 categories") | https://github.com/mergisi/awesome-openclaw-agents | Reusable agent profiles, low-friction discovery | PARTIAL — see Continue Hub / Roo Code marketplace rows; Hermes' skill hub doesn't cover personality marketplaces yet | Extend skill hub manifest to cover SOUL/personality templates | M |
| OpenClaw | Reported >100k GitHub stars within first week (late Jan 2026); active near-daily releases through 2026 | https://github.com/openclaw/openclaw/releases | Signal of fast iteration + community traction | INSPIRATION — not a feature, but a benchmark for Hermes' release cadence | Set a release/cadence target in `docs/orchestration/` | M |

**What stands out (and what to watch):** OpenClaw is, deliberately or
otherwise, the same product Hermes is trying to be — multi-channel gateway,
personal AI runtime, skills, cron, sandboxed sessions, voice, companion
app. The differentiation Hermes needs to invest in: **orchestration depth**
(Hermes has a full job/worker/validation/ledger system that OpenClaw does
not), **model-routing breadth** (Hermes ships dozens of provider plugins),
and **the published agent loop** (Hermes' embeddable `AIAgent` plus the
orchestration primitives are more reusable than OpenClaw's monolithic
gateway). Channel parity, scoped `AGENTS.md`, Live Canvas, and SOUL.md
personality-as-file are the four near-term gaps worth closing.

### Paperclip (`paperclipai/paperclip`)

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| Paperclip | Built-in adapters: official docs show `claude_local` + `codex_local` shipping in V1; a "Generic Process" adapter for arbitrary CLI tools is documented but marked "**not yet implemented in V1**" | https://paperclipai-paperclip.mintlify.app/agents/process-adapter, https://github.com/paperclipai/paperclip/blob/master/docs/adapters/claude-local.md | Wrap multiple coding agents under one orchestrator | PARTIAL — Hermes can delegate via `terminal` to any of these; no formal "adapter contract" | Define `agent_adapter` protocol (start/stop/session-resume/heartbeat) in `tools/`; ship `claude_code`, `codex`, `aider`, `goose` adapters under it | H |
| Paperclip | Supported runtimes shown on landing page: OpenClaw, Claude Code, Codex, Cursor, Bash, HTTP — but several appear to be roadmap or community-contributed rather than built-in V1 | https://paperclip.ing/ | Broad coverage messaging | PARTIAL — Hermes' `terminal` already covers any of these by command; what's missing is the named-adapter affordance | Same as adapter row above; document which adapters ship vs which are roadmap | M |
| Paperclip | Persists Claude Code session IDs across heartbeats; resumes via `--add-dir` skill symlinks | https://github.com/paperclipai/paperclip/blob/master/docs/adapters/claude-local.md | Long-running delegated work survives ticks | GAP — Hermes cron spawns fresh sessions per run | Add `session_continuity` config to cron jobs (resume previous session ID if recent) | H |
| Paperclip | Org chart / roles / budgets / governance / ticket audit trail | https://github.com/paperclipai/paperclip | "Agents as employees of a company" | PARTIAL — Hermes kanban + observability covers tickets/audit; no budgets/roles UI | Add per-worker `budget` field to kanban + display in dashboard | H |
| Paperclip | Multi-company isolation in a single deployment | https://github.com/paperclipai/paperclip | One install for multiple teams | PARTIAL — Hermes profile system + kanban board isolation gets close | Document profile + kanban board boundary as the Hermes equivalent | M |
| Paperclip | Self-hosted Node.js + React + embedded Postgres | https://github.com/paperclipai/paperclip | Self-host on customer infra | OUT OF SCOPE — different stack | — | H |

### Adjacent agents (Cline, Cursor, Roo, Zed/ACP, Gemini CLI, Devin, SWE-agent, Plandex, bolt/Lovable, Smol/GPT-E)

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| Cline | Plan / Act mode toggle (`plan_mode_respond` blocks switch to Act) | https://docs.cline.bot/features/plan-and-act | Read-only strategy then approved execution | GAP — high value | See Claude-Code "Plan mode" row | H |
| Cline | MCP Marketplace — 100+ pre-built servers, one-click install | https://cline.bot/mcp-marketplace | Discoverability | PARTIAL — see Continue Hub row | — | H |
| Cline | Checkpoint system — auto-snapshot after each operation, one-click rollback | https://github.com/cline/cline | Granular trust control | ALREADY SHIPS — `tools/checkpoint_manager.py` | — | H |
| Cline | `.clinerules` file | https://github.com/cline/cline | Project-scoped guidance | GAP — see Continue Rules row | — | H |
| Cline | Computer Use — drive a real browser to verify UI | https://github.com/cline/cline | Self-verification of UI changes | ALREADY SHIPS — browser tools + dashboard verify pattern | — | H |
| Cursor | Composer 2 / 2.5 model — first-party agentic model | https://cursor.com/docs | "4x faster than peer frontier models" (vendor claim) | OUT OF SCOPE — Hermes is model-agnostic by design | — | M |
| Cursor | Background Agents (Cursor Cloud) — async VMs clone repo, open PRs, self-evaluate w/ video/log/screenshot artifacts | https://cursor.com/docs | Move work off the laptop | PARTIAL — see Claude-Code cloud + Codex Cloud rows | — | H |
| Cursor | Parallel Agents (Cursor 2.0) — up to 8 isolated agents side-by-side | https://cursor.com/changelog | Throughput | ALREADY SHIPS — `delegate_task` batch mode (cap configurable) | — | H |
| Cursor | BugBot — GitHub App auto-reviews every PR, auto-fixes findings | https://cursor.com/bugbot | "PR review robot" | GAP — see Continue PR Checks + Claude Code GH Action rows | — | H |
| Cursor | Tab autocomplete + `@symbols` | https://cursor.com/docs | Predictive cursor jumps | OUT OF SCOPE — autocomplete is IDE territory | — | H |
| Cursor | `.cursorrules` / Rules for AI | https://cursor.com/docs | Workspace-level system-prompt injection | GAP — see Continue Rules row | — | H |
| Roo Code | Modes (Code / Architect / Ask / Debug / Orchestrator boomerang) | https://docs.roocode.com/features/boomerang-tasks | Mode-per-task with sticky model assignment | PARTIAL — Hermes personalities cover persona; no per-mode tool restriction + sticky model | Add `modes:` config with allowed tools + default model per mode | H |
| Roo Code | Marketplace of community Modes and MCPs | https://docs.roocode.com/features/marketplace | Shareable agent recipes | PARTIAL — see Continue Hub row | — | H |
| Roo Code | Sticky Models — each mode remembers last-selected model | https://docs.roocode.com/features/custom-modes | "Team of specialists" | GAP — see Modes row above | — | H |
| Roo Code | **Status note:** April 2026 shutdown announced, project archived May 2026; users migrating to Kilo | https://kilo.ai/articles/roo-to-kilo-migration-guide (secondary) | — | — | Verify before quoting; do not market Hermes as a "Roo replacement" without checking the Kilo handover | M |
| Zed ACP | LSP-style open protocol (JSON-RPC 2.0 over stdio; HTTP/WS for remote in development) | https://agentclientprotocol.com | "LSP for agents" | ALREADY SHIPS — `acp_adapter/`, `acp_registry/` | Continue investing — ACP compliance unlocks Zed/JetBrains/Cursor as free front-ends | H |
| Zed ACP | `session/request_permission` method + markdown-formatted diff UI | https://zed.dev/acp | Standardized approval UX | PARTIAL — Hermes ACP adapter has permissions; verify diff formatting matches Zed expectations | Audit `acp_adapter/permissions.py` against the latest spec | H |
| Gemini CLI | Generous free tier (60 req/min, 1000 req/day) | https://github.com/google-gemini/gemini-cli | Free + multimodal | OUT OF SCOPE — Hermes is provider-agnostic, free tier is the provider's offer | — | H |
| Gemini CLI | GEMINI.md context file | https://github.com/google-gemini/gemini-cli | Repo-level instructions | ALREADY SHIPS — `AGENTS.md` (and `CLAUDE.md`/`GEMINI.md` if present); Hermes context loader picks up multiple file names | — | H |
| Devin | Devin Wiki — auto-indexes repo every few hours, generates architecture diagrams | https://cognition.ai/blog/devin-2 | "Living documentation" | GAP — high value | Add `hermes wiki build` periodic skill that indexes the repo + emits Markdown + Mermaid | H |
| Devin | Managed Devins — planner breaks tasks and delegates to a team of Devins | https://cognition.ai/blog/devin-can-now-manage-devins | "Devin manages Devins" | ALREADY SHIPS — `delegate_task` with orchestrator role + kanban | — | H |
| Devin | Sessions API — child sessions w/ structured-output schemas + playbooks; full activity search | https://docs.devin.ai/release-notes/2026 | Inspectable session graph | PARTIAL — session DB + FTS5 exist; no structured-output schemas per session | Add `output_schema` field to session config | H |
| Devin | Slack / Linear / Datadog / GitHub integration — 40+ platforms | https://cognition.ai/blog/devin-2 | "Trigger from where you already work" | ALREADY SHIPS — multi-platform gateway | — | H |
| SWE-agent | Agent-Computer Interface (ACI) — hand-tuned tool design that "leaves maximal agency to the LM" | https://github.com/SWE-agent/SWE-agent | Academic reference design | INSPIRATION — Hermes toolset design follows similar principles | Cite ACI as influence in `toolsets.py` docs | H |
| SWE-agent | Single YAML config defines entire agent | https://github.com/SWE-agent/SWE-agent | "Simple & hackable" | PARTIAL — Hermes config is YAML; no single-file agent definition | Could ship `recipes/` (see Goose row) | H |
| Plandex | Plan branches — git-style branches per plan, parallel solution paths | https://github.com/plandex-ai/plandex | "Git for prompts" | GAP — high value | Add `hermes plan branch` primitive over checkpoint manager | H |
| Plandex | Cumulative diff sandbox — edits live in a review buffer until applied | https://github.com/plandex-ai/plandex | Explicit apply step | PARTIAL — checkpoints allow restore; not a separate review buffer | Add `--dry-run` mode that defers patches into a buffer | H |
| Plandex | REPL mode w/ fuzzy autocomplete | https://github.com/plandex-ai/plandex | Terminal UX | ALREADY SHIPS — TUI + prompt_toolkit + autocomplete | — | H |
| Plandex | Automated debugging — auto-fix loop for builds/linters/tests, Chrome-based browser debugging | https://github.com/plandex-ai/plandex | Closed loop | GAP — see Aider auto-lint/auto-test row | — | H |
| bolt.new | WebContainers — full Node.js dev env in-browser | https://github.com/stackblitz/bolt.new | Zero install, deploys from prompt | OUT OF SCOPE — different category (full-stack builder) | — | H |
| Lovable | Chat-driven full-stack builder, screenshot-to-app, GitHub sync | https://lovable.dev | Prompt-to-deployed-app | OUT OF SCOPE | — | H |
| Smol Developer | Spec → file-list → file-by-file generation | https://github.com/smol-ai/developer | "Junior developer" workflow | DORMANT — project stale; no recent releases | — (no action) | M |
| GPT Engineer | Natural-language spec → executed code; iterative loop | https://github.com/AntonOsika/gpt-engineer | Pioneered "describe an app, get a repo" | ARCHIVED 2026-04-22 — points users to gptengineer.app or Aider | — (no action) | H |

---

## Cross-cutting patterns

1. **Rules files are table stakes.** Cursor (`.cursorrules`), Cline
   (`.clinerules`), Continue (`.continue/rules`), Goose (`.goosehints`),
   Claude Code (`CLAUDE.md`), Codex (`AGENTS.md`), OpenClaw (scoped
   `AGENTS.md` per subtree). Hermes loads `AGENTS.md` but has no
   per-glob activation and no subtree walk. Highest-leverage feature gap.
2. **Sandbox profiles backed by OS primitives.** Codex's Seatbelt/Landlock
   model has set the bar; container isolation alone is now table stakes,
   not differentiation.
3. **PR-resident agents.** Claude Code Action, Codex Action, Cursor BugBot,
   Continue PR Checks, OpenHands Resolver all converge on: "comment
   `@<agent>` on a PR / label an issue → autonomous PR." Hermes has the
   plumbing (webhooks + skills), no reusable Action wrapping it.
4. **Recipes / parameterized workflows.** Goose recipes (YAML + Jinja2),
   Claude Code skills with dynamic shell injection, OpenHands microagents.
   Hermes skills are closest but lack parameter binding + sub-recipe
   composition.
5. **Cloud + handoff between surfaces.** Claude Code on the web,
   `--teleport`/`--remote`, Codex Cloud, Cursor Background Agents, Devin's
   sessions. Hermes has the backends (Modal, Daytona, Vercel) but no
   formalized session handoff between local and remote.
6. **Auto-lint / auto-test loops.** Aider, Plandex. Hermes' verification
   skill is human-triggered; an auto-loop would close the gap.
7. **Public leaderboards.** Aider Polyglot, OpenHands Index. Hermes runs
   SWE-bench mini but doesn't publish results.
8. **Multi-tier skill activation.** OpenHands microagents (permanent /
   keyword / org / global), Continue rules priority, Claude Code skill
   overrides. Hermes activates skills by name and category — a glob/keyword
   tier is missing.
9. **Multi-channel personal-assistant runtime.** OpenClaw (24+ channels) and
   Hermes (~10 channels) converge on the same shape: local-first gateway,
   per-channel routing, voice, sandboxed sessions, cron, skills. Hermes is
   ahead on orchestration depth and model breadth, behind on channel parity
   and a Live-Canvas-style visible-reasoning surface.

---

## What's deliberately out of scope for Hermes

Documented here so the backlog doesn't grow them in by accident:

- **IDE-native autocomplete** (Continue Next Edit, Cursor Tab) — IDE
  vendors win this race; Hermes' surface is terminal + gateway.
- **In-browser full-stack builders** (bolt.new, Lovable) — different
  product category.
- **Single-vendor SaaS lock-in stories** (Devin cloud-only, Cursor
  Composer-only model) — contradicts Hermes' model-agnostic stance.
- **Rust-binary monolith distribution** (OpenHuman) — Hermes' Python-first
  + plugin architecture is a deliberate choice.
- **Org-chart / company-metaphor UI** (Paperclip) — kanban + profiles
  already cover the substance.
