# Developer-Agent Feature Harvest

**Phase 23 — Competitive feature harvest for Hermes (refresh of Phase 21).**

A verified survey of distinctive features across competing AI developer agents,
cross-referenced against what Hermes already ships. The output of this doc is a
research base; the prioritized adoption list lives in
[`docs/product/hermes-feature-backlog.md`](../product/hermes-feature-backlog.md).

**Date:** 2026-05-23 (Phase 23 refresh; Phase 21 baseline was ~2026-05-16)
**Scope:** Claude Code, Codex CLI, Aider, OpenHands, Continue, Goose, OpenHuman,
Paperclip, plus adjacent tools (Cline, Cursor, Roo Code, Zed/ACP, Gemini CLI,
Devin, SWE-agent, Plandex, bolt.new/Lovable, Smol Developer, GPT Engineer,
Bernstein).

**Method (Phase 21):** Eight parallel research subagents (one Hermes inventory
+ seven competitor groups). Each was briefed to cite official sources, mark
unverified claims, and flag dormant projects.

**Method (Phase 23 refresh):** Two parallel verification subagents — one to
re-verify the OpenHuman/Paperclip claims, one to harvest changelogs dated
after 2026-05-10 across all twelve products. Findings folded into the tables
below with `[P23]` markers on new rows. Full disambiguation of OpenHuman and
Paperclip lives in
[`openhuman-paperclip-research.md`](./openhuman-paperclip-research.md).

**Rules used:**
- Prefer official sources (docs.*, github.com/<org>/<repo>/README.md, release notes)
- Reputable reviews are secondary and marked as such
- Unverified claims marked unverified
- "Applies to Hermes?" reflects the codebase as of commit on `claude/competitive-feature-harvest-x5Qbk`
- No feature is claimed as "copied" unless verified in a Hermes release
- Phase 23 additions are marked `[P23]` so the next refresh can diff easily

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
| Claude Code | GitHub Actions v1 (`anthropics/claude-code-action@v1`) — `@claude` mention in issue/PR triggers PR creation | https://code.claude.com/docs/en/github-actions | One-shot setup, no bespoke webhook plumbing | PARTIAL — Hermes has webhooks + `github-code-review` skill; no off-the-shelf reusable Action | Ship `nousresearch/hermes-action@v1` wrapping `muse webhook subscribe` + GitHub App template | H |
| Claude Code | Plan mode + Proactive mode (output-style + permission-mode pair) | https://code.claude.com/docs/en/permission-modes | Cautious review vs hands-off automation toggle | GAP — high value | Add two permission modes wired into approval system: `plan-only` (read-only tools), `proactive` (auto-approve safe tool classes) | H |
| Claude Code | Bundled `/security-review`, `/init`, `/verify` skills | https://code.claude.com/docs/en/skills | Zero-config security and onboarding | PARTIAL — Hermes has `requesting-code-review` skill and `setup-hermes.sh`; no `/security-review` skill nor a `/verify` that drives a running app | Add bundled `security-review` skill (cf. Hermes' existing `red-teaming` category); add `verify` skill referencing `skills/run` pattern | H |
| Claude Code | Multi-directory workspaces (`--add-dir`) — grants tool access to extra dirs and auto-loads their `.claude/skills/` | https://code.claude.com/docs/en/skills | Monorepo / multi-repo agent sessions | GAP — Hermes `terminal.cwd` is single-rooted | Add `--add-dir` to CLI + gateway `terminal.allowed_roots` config + skill discovery sweep | H |
| Claude Code | Effort levels (low / medium / high / xhigh / max) per skill, plus per-skill model override | https://code.claude.com/docs/en/skills | Cost/quality dial per workflow | GAP — Hermes has `reasoning_config` and `auxiliary` clients; not exposed per-skill | Add `model:` and `effort:` frontmatter fields in `SKILL.md` → resolved at skill activation | H |
| Claude Code | Routines / scheduled tasks / `/loop` (Anthropic-managed scheduling) | https://code.claude.com/docs/en/routines (referenced) | Cron-grade scheduling integrated with agent context | ALREADY SHIPS — see `cron/` and `hermes-already-has-routines.md` | — | H |
| Claude Code | Channels (Telegram / Discord / iMessage / webhook ingress into existing session) | https://code.claude.com/docs/en/channels (referenced) | Direct overlap with Hermes' gateway concept | ALREADY SHIPS — see `gateway/platforms/` | — | H |
| Claude Code `[P23]` | `/usage` now reports per-category cost breakdown — skills, subagents, plugins, per-MCP-server | https://code.claude.com/docs/en/changelog (v2.1.149) | "Where is my budget going?" answered without spreadsheets | GAP — high value | Aggregate the existing ledger by primitive; new `muse usage --by skill\|subagent\|plugin\|mcp` view in `hermes_cli/` and dashboard | H |
| Claude Code `[P23]` | `/code-review` (renamed from `/simplify`) with effort levels + GitHub PR-comment posting; pinned background sessions auto-restart on idle | https://code.claude.com/docs/en/changelog (v2.1.147) | Code review as a first-class subagent flow, not an ad-hoc skill | PARTIAL — Hermes has `requesting-code-review` skill + `github_assistant` plugin; no unified slash command with effort dial nor auto-PR-comment posting | New `/code-review [--effort low\|medium\|high]` slash command wrapping the existing skill + `github_assistant` comment poster | H |
| Claude Code `[P23]` | `claude agents --json` for scripting; `/plugin` Discover lists commands/agents/skills/hooks/MCP/LSP before install | https://code.claude.com/docs/en/changelog (v2.1.145) | Pre-install plugin manifest preview avoids "what does this thing do" surprise | PARTIAL — Hermes plugin loader registers tools; no pre-install manifest preview UI | Add `muse plugin show <name>` that prints the plugin's exposed tools, hooks, slash commands, and MCP servers before activation | H |
| Claude Code `[P23]` | Plugin dependency enforcement + projected context-cost shown in marketplace | https://code.claude.com/docs/en/changelog (v2.1.143) | npm-like rigor for plugins | GAP — Hermes plugin manifests don't declare deps or projected token cost | Add `dependencies:` and `estimated_context_tokens:` to `plugin.yaml`; validate at load | H |

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
| Codex CLI `[P23]` | Goals enabled by default with dedicated storage; permission profile management; lifecycle events for plugins | https://github.com/openai/codex/releases (v0.133.0) | Goals as a persistent primitive separate from session messages | PARTIAL — Hermes has memory (Honcho / Mem0 / supermemory) but no explicit "goal" entity distinct from chat memory | Add `Goal` row to session DB with status (open/done/dropped) + linked task graph nodes; surface in dashboard | H |
| Codex CLI `[P23]` | Resumed automations enforce structured JSON output schemas | https://github.com/openai/codex/releases (v0.132.0) | Output schemas survive resume — automation reliability | PARTIAL — Hermes cron supports prompts but no per-job output schema enforcement | Add `output_schema:` field to cron job spec + validator in `cron/` | H |
| Codex CLI `[P23]` | Unified `@`-mention picker; `codex doctor` diagnostic; marketplace plugin workflows; remote daemon management | https://github.com/openai/codex/releases (v0.131.0) | Doctor command is now standard across agents | ALREADY SHIPS (mostly) — Hermes has `muse doctor`, `@`-mention is on the backlog (T2 #9), plugin marketplace overlaps with skills hub | Cross-reference T2 #9 (`@`-mention syntax) — Codex's picker UX is worth borrowing | H |

### Aider

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| Aider | Repo map: tree-sitter symbol extraction + PageRank-style graph ranking, fixed `--map-tokens` budget | https://aider.chat/docs/repomap.html | "Enough context to solve many tasks" within a token budget | GAP — high value | New tool: `tools/repo_map.py` using `py-tree-sitter-languages`; surface via toolset `code_intel` | H |
| Aider | Auto-commit every AI edit with Conventional-Commit messages; pre-existing dirty changes auto-committed first; "(aider)" author tag | https://aider.chat/docs/git.html | Safe undo + clean history + attribution | PARTIAL — Hermes checkpoints use git diff/restore but don't author conventional commits per turn | Optional `git.auto_commit` mode in `tools/checkpoint_manager.py` | H |
| Aider | `/undo`, `/diff`, `/commit`, `/git` in-chat commands | https://aider.chat/docs/git.html | One command rolls back risky edits | PARTIAL — Hermes has checkpoint restore; no `/undo` slash command | Add `/undo`, `/diff` slash commands wrapping checkpoint manager | H |
| Aider | Watch mode (`--watch-files`) with `AI!` / `AI?` triggers in code comments | https://aider.chat/docs/usage/watch.html | Any editor becomes an agent frontend with zero plugin | GAP — high value | New `muse watch` mode using `watchdog`; configurable trigger patterns | H |
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
| Aider `[P23]` | **Project status:** no new release in the Phase 23 window; last release v0.86.0 (Aug 2025). Project may be entering low-maintenance mode. | https://aider.chat/blog/, GitHub releases | — | — | Watch — if dormant continues, downgrade Aider rows from "shipping reference" to "historical inspiration" in the next refresh | M |

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
| Continue `[P23]` | **Project status:** atom feed shows last release 2026-03-27; no new feature in Phase 23 window | https://changelog.continue.dev/ | — | — | Continue's Phase 21 rows above are still the canonical reference; no refresh needed this cycle | M |

### Goose (Block)

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| Goose | Recipes — YAML workflows with Jinja2 parameters, semantic versioning, sub-recipe composition (sequential/parallel) | https://block-goose.mintlify.app/concepts/recipes | "Workflow infrastructure, not productivity shortcut" — team-shareable | GAP — high value | New `recipes/` primitive: YAML with `instructions`, `parameters`, `extensions`, `sub_recipes`; runner integrates with cron and `delegate_task` | H |
| Goose | MCP extensions (built-in + stdio + SSE), 70+ documented | https://block-goose.mintlify.app/concepts/extensions | Any MCP server works; "Goose shaped MCP" | ALREADY SHIPS — MCP client | — | H |
| Goose | Lead/Worker model split — `GOOSE_LEAD_MODEL` plans, `GOOSE_PLANNER_*` for `/plan`, cheaper model executes | https://github.com/block/goose | "Powerful model plans, faster/cheaper executes" — cost-optimal | PARTIAL — Hermes `auxiliary` covers this for many tasks; no canonical "lead model for planning, primary for execution" split | Document `auxiliary.planner` convention + `/plan` slash command using it | M |
| Goose | Sub-agents (parallel, isolated sessions, partial-success semantics) | https://dev.to/nickytonline/advent-of-ai-day-11-goose-subagents-2n2 (secondary) | Isolation + survives partial failures | ALREADY SHIPS — `delegate_task` batch mode | — | M |
| Goose | Built-in scheduler (`goose schedule`) on tokio-cron, recipe-aware | https://deepwiki.com/block/goose/4.1.5-scheduler-and-recurring-tasks (secondary) | Recipes become unattended automations | ALREADY SHIPS — `cron/scheduler.py` | — | H |
| Goose | Named sessions: `start`/`resume`/`list`/`remove`/`export` to JSON/YAML/Markdown with metadata | https://goose-docs.ai/docs/guides/goose-cli-commands/ | Easy to resume long-running engineering work | PARTIAL — Hermes resumes by session ID; no export to JSON/YAML/Markdown with full metadata + tokens + timestamps | Add `muse session export <id> --format md\|json\|yaml` | H |
| Goose | 15-25+ providers (Anthropic, OpenAI, Vertex, Azure, Bedrock, Databricks, Snowflake Cortex, Copilot, OpenRouter, Venice.ai, Ollama, LiteLLM, llama.cpp, …) | https://block-goose.mintlify.app/concepts/providers | One abstraction across all major LLMs | ALREADY SHIPS — `plugins/model-providers/` | — | H |
| Goose | CLI + Desktop + API on a single Rust core | https://github.com/block/goose | One codebase across surfaces | PARTIAL — Hermes has CLI + TUI + gateway + dashboard; no native desktop app (Android exists, not desktop) | — (deliberate: dashboard covers the desktop use case) | H |
| Goose | `.goosehints` — per-project lightweight hints file | (cited via search summary; docs page returned 404 during research — Medium confidence) | Lightweight per-project steering | PARTIAL — Hermes uses `AGENTS.md`; no shorter "hints" alternative | Document `AGENTS.md` as Hermes' equivalent (no second file format needed) | M |
| Goose | OpenTelemetry + Langfuse — trace prompt/messages/tool calls/responses/timing | https://langfuse.com/docs/integrations/goose (secondary) | Production-grade tracing and cost tracking | PARTIAL — `plugins/observability/` exists; need to verify OTel exporter + Langfuse integration | Audit observability plugin; add OTel exporter if missing | H |
| Goose | Agent Client Protocol (ACP) support | https://github.com/block/goose | Vendor-neutral IDE/host portability | ALREADY SHIPS — `acp_adapter/`, `acp_registry/` | — | M |
| Goose | `goose bench` evaluation harness | https://block.github.io/goose/docs/tutorials/benchmarking/ | Measure scaffold quality, not just model quality | PARTIAL — Hermes has `mini_swe_runner.py` (SWE-bench-specific) | Generalize to `hermes bench` with pluggable suites | M |
| Goose | Custom distributions — rebrand/repackage for enterprise rollout | https://block-goose.mintlify.app/llms.txt | Enterprise rollout story | PARTIAL — `enterprise/` dir exists; rebranding is via skin engine; not a documented "custom distribution" workflow | Document the skin engine + plugin-set as the "custom distribution" mechanism | M |
| Goose | MCP-UI widget rendering in Desktop | https://www.nickyt.co/blog/what-makes-goose-different-from-other-ai-coding-agents-2edc/ (secondary) | "Superior experience vs text-based" responses | GAP — Hermes TUI is text; dashboard is HTML | Render MCP-UI responses in the dashboard React surface | M |
| Goose | Server deployment (REST + WS + SSE) for multi-user production | https://block-goose.mintlify.app/llms.txt | Self-hosted shared backend | ALREADY SHIPS — `gateway/platforms/api_server.py` + dashboard | — | M |
| Goose `[P23]` | Extensible hooks system (v1.35.0, May 22 2026) | https://block.github.io/goose/docs/category/release-notes | Goose joins Claude Code's hooks pattern — taxonomy expansion | PARTIAL — Hermes has hooks; verify event coverage parity in next pass | Compare Goose's hook event taxonomy against Hermes' once Goose docs publish the full list | H |
| Goose `[P23]` | `/goal` self-evaluation slash command (v1.35.0) | https://block.github.io/goose/docs/category/release-notes | Agent grades its own progress against a stated goal | GAP — Hermes has decision ledger but no self-evaluation primitive against an explicit goal | New `/goal set <text>` then `/goal evaluate` flow that prompts the model with the goal + the session ledger and emits a structured pass/fail/partial verdict | H |
| Goose `[P23]` | Local code review (v1.35.0); Vercel AI Gateway provider | https://block.github.io/goose/docs/category/release-notes | Code review as a first-class flow (see Claude Code `/code-review` row) | PARTIAL — combine with Claude Code `[P23]` row above into one backlog item | — | H |

### OpenHuman (`tinyhumansai/openhuman`)

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| OpenHuman | Single Rust binary, local-first runtime | https://github.com/tinyhumansai/openhuman | One install, no dependency tree | OUT OF SCOPE — Hermes is Python-first by design | — | H |
| OpenHuman | "Memory Tree" — SQLite + Obsidian-compatible markdown vault | https://tinyhumans.gitbook.io/openhuman | Users can browse/edit memory in their own knowledge tool | GAP — possible memory plugin | New `plugins/memory/obsidian/` provider | H |
| OpenHuman | 118+ OAuth integrations w/ periodic auto-fetch | github.com README | Personal-AI grounded in your services | OUT OF SCOPE — Hermes platform gateway covers messaging; deep OAuth-per-service is a plugin space | — | M |
| OpenHuman | TokenJuice compression (vendor claim ~80% reduction) | github.com README | Lower token spend | UNVERIFIED — vendor claim; no public benchmark | Compare against `trajectory_compressor.py` if a benchmark surfaces | L |
| OpenHuman | Voice + desktop mascot, can join Google Meets | github.com README | Personal-AI affordances | PARTIAL — Hermes voice exists; mascot is the skin engine + spinner faces; no Google Meet joining | — (low value; the `google_meet` plugin under `plugins/` already exists — verify scope) | M |
| OpenHuman `[P23]` | **Phase 23 status:** all Phase 21 claims verified; license confirmed GPL-3.0; auto-fetch cadence is 20-minute per active connection; v0.54.0 at 2026-05-19; repo at 26.3k★ in two weeks | github.com/tinyhumansai/openhuman | Validation that the personal-AI niche has traction — not a Hermes-relevance change | — | — | H |

See [`openhuman-paperclip-research.md`](./openhuman-paperclip-research.md) for
the full disambiguation.

### Paperclip (`paperclipai/paperclip`)

| Product | Feature | Source | User-loved reason | Applies to Hermes? | Implementation target | Confidence |
|---|---|---|---|---|---|---|
| Paperclip | Adapters for `claude_local`, `codex`, `cursor`, `gemini`, `opencode` + HTTP/webhook bots | https://github.com/paperclipai/paperclip/blob/master/docs/adapters/claude-local.md | Wrap multiple coding agents under one orchestrator | PARTIAL — Hermes can delegate via `terminal` to any of these; no formal "adapter contract" | Define `agent_adapter` protocol (start/stop/session-resume/heartbeat) in `tools/` | H |
| Paperclip | Persists Claude Code session IDs across heartbeats; resumes via `--add-dir` skill symlinks | https://github.com/paperclipai/paperclip/blob/master/docs/adapters/claude-local.md | Long-running delegated work survives ticks | GAP — Hermes cron spawns fresh sessions per run | Add `session_continuity` config to cron jobs (resume previous session ID if recent) | H |
| Paperclip | Org chart / roles / budgets / governance / ticket audit trail | https://github.com/paperclipai/paperclip | "Agents as employees of a company" | PARTIAL — Hermes kanban + observability covers tickets/audit; no budgets/roles UI | Add per-worker `budget` field to kanban + display in dashboard | H |
| Paperclip | Multi-company isolation in a single deployment | https://github.com/paperclipai/paperclip | One install for multiple teams | PARTIAL — Hermes profile system + kanban board isolation gets close | Document profile + kanban board boundary as the Hermes equivalent | M |
| Paperclip | Self-hosted Node.js + React + embedded Postgres | https://github.com/paperclipai/paperclip | Self-host on customer infra | OUT OF SCOPE — different stack | — | H |
| Paperclip `[P23]` | **Adapter list shift:** headline list is now OpenClaw, Claude Code, Codex, Bash, HTTP webhooks; Gemini dropped from the headline enumeration (whether removed or de-emphasized unknown — INSUFFICIENT EVIDENCE) | github.com/paperclipai/paperclip README | — | — | If Hermes ships an adapter contract (T3 #24), default to the current Paperclip headline set | M |
| Paperclip `[P23]` | AMI bundles 4 runtimes (Claude Code, Codex, OpenCode, OpenClaw) on Ubuntu 24.04; turnkey appliance | https://aws.amazon.com/marketplace/pp/prodview-bzyfsoqckclmy | Lower friction onboarding for orgs | PARTIAL — Hermes ships container/Modal/Daytona/Vercel sandboxes; no preconfigured AMI | Optional: Hermes Marketplace AMI as a packaging exercise; defer unless an enterprise user asks | M |

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
| Devin | Devin Wiki — auto-indexes repo every few hours, generates architecture diagrams | https://cognition.ai/blog/devin-2 | "Living documentation" | GAP — high value | Add `muse wiki build` periodic skill that indexes the repo + emits Markdown + Mermaid | H |
| Devin | Managed Devins — planner breaks tasks and delegates to a team of Devins | https://cognition.ai/blog/devin-can-now-manage-devins | "Devin manages Devins" | ALREADY SHIPS — `delegate_task` with orchestrator role + kanban | — | H |
| Devin | Sessions API — child sessions w/ structured-output schemas + playbooks; full activity search | https://docs.devin.ai/release-notes/2026 | Inspectable session graph | PARTIAL — session DB + FTS5 exist; no structured-output schemas per session | Add `output_schema` field to session config | H |
| Devin | Slack / Linear / Datadog / GitHub integration — 40+ platforms | https://cognition.ai/blog/devin-2 | "Trigger from where you already work" | ALREADY SHIPS — multi-platform gateway | — | H |
| SWE-agent | Agent-Computer Interface (ACI) — hand-tuned tool design that "leaves maximal agency to the LM" | https://github.com/SWE-agent/SWE-agent | Academic reference design | INSPIRATION — Hermes toolset design follows similar principles | Cite ACI as influence in `toolsets.py` docs | H |
| SWE-agent | Single YAML config defines entire agent | https://github.com/SWE-agent/SWE-agent | "Simple & hackable" | PARTIAL — Hermes config is YAML; no single-file agent definition | Could ship `recipes/` (see Goose row) | H |
| Plandex | Plan branches — git-style branches per plan, parallel solution paths | https://github.com/plandex-ai/plandex | "Git for prompts" | GAP — high value | Add `muse plan branch` primitive over checkpoint manager | H |
| Plandex | Cumulative diff sandbox — edits live in a review buffer until applied | https://github.com/plandex-ai/plandex | Explicit apply step | PARTIAL — checkpoints allow restore; not a separate review buffer | Add `--dry-run` mode that defers patches into a buffer | H |
| Plandex | REPL mode w/ fuzzy autocomplete | https://github.com/plandex-ai/plandex | Terminal UX | ALREADY SHIPS — TUI + prompt_toolkit + autocomplete | — | H |
| Plandex | Automated debugging — auto-fix loop for builds/linters/tests, Chrome-based browser debugging | https://github.com/plandex-ai/plandex | Closed loop | GAP — see Aider auto-lint/auto-test row | — | H |
| bolt.new | WebContainers — full Node.js dev env in-browser | https://github.com/stackblitz/bolt.new | Zero install, deploys from prompt | OUT OF SCOPE — different category (full-stack builder) | — | H |
| Lovable | Chat-driven full-stack builder, screenshot-to-app, GitHub sync | https://lovable.dev | Prompt-to-deployed-app | OUT OF SCOPE | — | H |
| Smol Developer | Spec → file-list → file-by-file generation | https://github.com/smol-ai/developer | "Junior developer" workflow | DORMANT — project stale; no recent releases | — (no action) | M |
| GPT Engineer | Natural-language spec → executed code; iterative loop | https://github.com/AntonOsika/gpt-engineer | Pioneered "describe an app, get a repo" | ARCHIVED 2026-04-22 — points users to gptengineer.app or Aider | — (no action) | H |
| Cursor `[P23]` | Cursor 3.5 (May 20) — Automations in the Agents Window with multi-repo / no-repo config | https://cursor.com/changelog | Cron-like agent automations baked into the IDE | ALREADY SHIPS — `cron/scheduler.py` + multi-platform gateway | — | H |
| Cursor `[P23]` | May 19 — Jira integration: assign work + trigger cloud agents from tickets | https://cursor.com/changelog | Ticket-to-agent loop | GAP — Hermes kanban covers internal tickets; no Jira gateway plugin | New `plugins/jira/` gateway plugin (mirrors existing `plugins/linear/` pattern if present, or new) | H |
| Cursor `[P23]` | Composer 2.5 (May 18) — improved sustained-task intelligence + instruction-following (vendor claim) | https://cursor.com/changelog | Long-task coherence | OUT OF SCOPE — proprietary model | — | M |
| Cursor `[P23]` | Cursor 3.4 (May 13) — full-screen tabs; customizable compactness for chat responses; Dockerfile-configurable multi-repo cloud-agent envs | https://cursor.com/changelog | "Compactness" as a tunable response axis (UX dial alongside output styles) | PARTIAL — Hermes output styles backlog item (T1 #5 family) should include a compactness axis | Add `verbosity:` (concise/normal/verbose) to output-style config | H |
| Cline `[P23]` | v3.84.0 + CLI v3.0.9-3.0.11 (May 19-22) — SAP AI Core, Poolside, Vertex Gemini Google auth providers; concurrent plugin loading | https://github.com/cline/cline/releases | Steady provider sprawl; concurrent plugin loading speeds cold start | PARTIAL — Hermes `plugins/model-providers/` has wide coverage; plugin loading is sequential | Add concurrent plugin discovery in `agent/plugins/__init__.py`; benchmark startup time | H |
| Gemini CLI `[P23]` | v0.43-0.44-preview (May 12-22) — agent session invocations + Auto modes merged; subagent protocols; Sublime Text and Emacs Client editors | https://github.com/google-gemini/gemini-cli/releases | Subagent protocol moving toward GA | ALREADY SHIPS (subagents) — `delegate_task`; editor list is IDE territory (out of scope) | — | H |
| Devin `[P23]` | May 22 — platform defaults, Slack-channel overrides, MCP OAuth improvements, custom automation schedules, GitLab PR reviews | https://docs.devin.ai/release-notes/overview | GitLab parity with GitHub | GAP — Hermes `github_assistant` plugin exists; no GitLab equivalent | New `plugins/gitlab_assistant/` mirroring `github_assistant/` (same MCP-style tool surface) | H |
| Devin `[P23]` | Windows VM support (May 21 blog) — Devin natively operates in Windows envs | https://cognition.ai/blog | First autonomous agent with native Windows | OUT OF SCOPE — Hermes Termux/Linux/macOS focus is deliberate (Windows users get WSL); revisit only on explicit user demand | — | M |
| Devin `[P23]` | Auto-Triage (May 18 blog) — monitors for issues, correlates reports, opens PRs | https://cognition.ai/blog | Issue triage as autonomous loop | PARTIAL — Hermes orchestrator can do this with a recipe; no canonical "triage" preset | Add `recipes/triage.yaml` once recipes (T1 #6) lands | M |
| Devin `[P23]` | Voice recording during agent runs (May 13) | https://docs.devin.ai/release-notes/overview | Voice-narrated sessions | OUT OF SCOPE — Hermes has voice-in; voice-narrated playback is dashboard territory, low priority | — | H |
| Zed / ACP `[P23]` | Terminal Threads (May 20) — run Claude Code, Amp, or any terminal agent as threads in Zed's sidebar | https://zed.dev/blog | Generic "any terminal agent as a thread" — protocol-neutral host UX | ALREADY ALIGNED — Hermes ACP adapter is the producer side of this pattern; verify Zed Terminal Threads can host Hermes via ACP | Audit `acp_adapter/` against Zed Terminal Threads protocol | H |
| Zed `[P23]` | Authenticate with ChatGPT subscription directly inside Zed (May 15) | https://zed.dev/blog | Subscription-auth pattern spreading beyond Anthropic Pro | OUT OF SCOPE — host-side auth flow; Hermes' `plugins/model-providers/openai_subscription/` already exists | — | H |
| Bernstein `[P23]` | Python orchestrator over 40+ CLI coding agents; HMAC-chained audit log; signed agent cards; parallel git-worktree isolation; MCP server mode | https://github.com/sipyourdrink-ltd/bernstein | Compliance-positioned orchestrator (direct competitor to Hermes orchestration stack) | PARTIAL — Hermes has orchestration with decision ledger + worker profiles + worktree isolation (via Phase 7+ work); no HMAC chaining or signed agent cards | (1) Confirm the decision ledger's tamper-evidence story is documented; (2) consider HMAC-chain or Merkle-tree option for the ledger; (3) decide whether "signed agent cards" matters for Hermes' threat model | M |

---

## Cross-cutting patterns

1. **Rules files are table stakes.** Cursor (`.cursorrules`), Cline
   (`.clinerules`), Continue (`.continue/rules`), Goose (`.goosehints`),
   Claude Code (`CLAUDE.md`), Codex (`AGENTS.md`). Hermes loads `AGENTS.md`
   but has no per-glob activation. Highest-leverage feature gap.
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
9. **[P23] Per-category usage accounting.** Claude Code v2.1.149 made
   `/usage` break costs down by skill, subagent, plugin, and per-MCP-server.
   Hermes' decision ledger has the raw data; a usage view by primitive
   is the obvious next surface.
10. **[P23] Code review as a first-class subagent flow.** Claude Code
    `/code-review` (effort levels + PR-comment posting) and Goose v1.35.0
    `local code review` converged in the same week. Hermes has a code-review
    skill and the `github_assistant` plugin — wiring them into a single slash
    command with effort levels is one PR.
11. **[P23] Hooks systems converging.** Goose v1.35.0 shipped an
    "extensible hooks system," joining Claude Code's existing 25+ event
    taxonomy. Hermes has hooks; refreshing the event-taxonomy comparison
    every release cycle is now a recurring chore.
12. **[P23] Compliance-grade audit logs.** Bernstein launched with
    HMAC-chained audit and signed agent cards. Hermes' decision ledger
    is similar in shape but doesn't claim tamper-evidence. Decision point
    for the security-review skill, not a guaranteed adoption.

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
