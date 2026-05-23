# Hermes Feature Backlog — Competitive Harvest Output

**Source:** Phase 21 harvest in
[`docs/competitive/developer-agent-feature-harvest.md`](../competitive/developer-agent-feature-harvest.md).

**Scope:** Only items rated **Gap — high value** or **Partial — high value**
in the harvest. Items marked **Already ships** or **Out of scope** are
excluded — see the harvest doc for the full table.

**Sort order:** by `(user value × architectural leverage) / implementation cost`.
Tier T1 = ship soon, T2 = quarter, T3 = directionally aligned but
unscheduled.

**Rules:**
- Nothing here is committed; this is a research-backed proposal list
- No feature is marked "shipped" unless a Hermes release / commit confirms it
- Sources cited in the harvest doc; not repeated here

---

## T1 — Highest leverage, ship next

### 1. Project rules system (`.hermes/rules/*.md` with glob activation)

**Inspiration:** Continue rules, Cursor `.cursorrules`, Cline `.clinerules`,
Goose `.goosehints`, Claude Code `CLAUDE.md` path-scoped rules.

**Why this is #1:** Five major competitors converge on the same pattern,
all loved by users for the same reason — conditional system-prompt injection
that fires only for relevant files. Hermes loads `AGENTS.md` but with no
glob/regex activation, so users either bloat the system prompt or fall
back to skills.

**Implementation target:**
- `_load_context_files()` in `run_agent.py` learns to read
  `.hermes/rules/*.md` with YAML frontmatter (`name`, `globs`, `regex`,
  `alwaysApply`, `description`)
- Rules with `globs` or `regex` only fire when the conversation references
  matching files
- Priority order matches Continue: project `.hermes/rules/` overrides
  global `~/.hermes/rules/`
- Reuse `AGENTS.md` semantics for the always-on case so existing setups
  keep working

**Effort:** ~1 week. Mostly loader logic + docs.

---

### 2. Auto-lint / auto-test loop (`code.auto_lint`, `code.auto_test`)

**Inspiration:** Aider `--auto-lint` / `--auto-test`, Plandex automated
debugging.

**Why:** Two of the most-cited Aider features. Closes the edit-lint-fix
loop without human prompting and gives Hermes parity with the agents
shipping on this pattern. Currently Hermes' `requesting-code-review` skill
is human-triggered.

**Implementation target:**
- New plugin hook `post_edit` (file-level granularity, not just tool-level)
- `code.auto_lint` / `code.auto_test` config sections naming the commands
  to run after edits
- On non-zero exit, re-prompt the agent with the failing output as
  `tool` role message; iterate up to `code.auto_lint_max_retries`
- Slash commands `/lint`, `/test` for on-demand triggering

**Effort:** ~1-2 weeks. Auto-loop logic is the hard part.

---

### 3. Repo map (tree-sitter + graph rank) as a tool

**Inspiration:** Aider repo map, Continue `@Repo-Map` context provider.

**Why:** Aider's signature feature. Lets the LLM see the whole repo's
classes/methods/signatures within a fixed token budget — strictly better
than blind grep for code-aware tasks. Hermes' delegation is strong but
sub-agents currently bootstrap with no symbol-level overview.

**Implementation target:**
- New tool `tools/repo_map.py` using `py-tree-sitter-languages`
- Schema: `repo_map(query: str = None, max_tokens: int = 4096) -> json`
- Surface in new toolset `code_intel` (off by default to avoid pulling
  tree-sitter for users who don't want it)
- Document caching at `~/.hermes/cache/repo_map/<repo_hash>/`

**Effort:** ~2 weeks. Tree-sitter integration is the bulk; ranking is
~200 LoC.

---

### 4. Reusable GitHub Action wrapper (`nousresearch/hermes-action@v1`)

**Inspiration:** Claude Code `anthropics/claude-code-action@v1`, Codex
`openai/codex-action@v1`, OpenHands Resolver, Cursor BugBot, Continue PR
Checks.

**Why:** Six competitors converge on "comment `@<agent>` on a PR / label an
issue → autonomous PR." Hermes has the plumbing (webhooks + skills +
`github-code-review` skill) but no off-the-shelf Action; every team rolls
their own YAML.

**Implementation target:**
- New repo `nousresearch/hermes-action` (or `.github/actions/` here for
  internal use first)
- Inputs: `prompt`, `prompt-file`, `skills`, `model`, `provider`,
  `allow-users`, `safety-strategy` (default `drop-sudo`),
  `unprivileged-user` — modeled on Codex Action's safety controls
- Outputs: `result`, `commit-sha`, `pr-number`
- Reuses `hermes webhook subscribe` mechanic under the hood

**Effort:** ~1-2 weeks including docs + a sample workflow file.

---

### 5. Plan / Proactive permission modes

**Inspiration:** Cline plan-vs-act toggle, Claude Code plan mode + proactive
output style.

**Why:** Highest-cited "trust dial" pattern. Hermes has the approval system
but no `plan-only` mode (read-only tools, no edits) and no `proactive`
mode (auto-approve safe tool classes).

**Implementation target:**
- Two new modes in `tools/approval.py`:
  - `plan` — restricts to read-only tools (`read_file`, `search_files`,
    `web_extract`, `repo_map`); blocks every write/exec tool
  - `proactive` — auto-approves anything in a configurable safe-list,
    prompts for everything else
- Slash commands `/plan` and `/proactive` toggle modes mid-session
- Wire into existing approval flow; no new tools to write

**Effort:** ~3-5 days.

---

### 6. Recipes — YAML parameterized workflows

**Inspiration:** Goose recipes, SWE-agent single-file YAML config.

**Why:** Goose's distinguishing primitive. Hermes has skills (Markdown
procedures) and cron jobs (scheduled prompts), but no parameterized,
versionable, composable workflow artifact. Recipes plug a real gap for
shared team automations.

**Implementation target:**
- New top-level dir `recipes/` (and `~/.hermes/recipes/` for users)
- Recipe schema: `name`, `version`, `parameters` (with types + defaults),
  `instructions` (Jinja2-templated prompt), `skills` (auto-load),
  `extensions` (MCP servers), `sub_recipes` (sequential or parallel)
- Run via `hermes recipe run <name> --param key=value` or from cron
- Compose sub-recipes via `delegate_task` for parallel branches

**Effort:** ~2 weeks. Loader + Jinja2 wiring + runner.

---

## T2 — High value, next quarter

### 7. Expanded skill frontmatter: `allowed-tools`, `paths`, `context: fork`, dynamic `` !`shell` `` injection

**Inspiration:** Claude Code skills, OpenHands microagents.

**Why:** Hermes skills exist but lack tool-scoping, glob-based
auto-activation, fork-into-subagent option, and pre-send shell injection.
All four are standard in competing skill systems.

**Implementation target:**
- Extend SKILL.md frontmatter in `agent/skill_commands.py` loader
- `allowed-tools` filters the toolset for the skill's duration
- `paths` (globs) auto-activates the skill when conversation references
  matching files (overlaps with rules-file work; share the matcher)
- `context: fork` runs the skill body inside a delegated subagent
- `` !`shell command` `` and ```! fenced blocks pre-execute and inline output

**Effort:** ~1-2 weeks.

---

### 8. OS-level sandbox profiles (Seatbelt / Landlock wrappers)

**Inspiration:** Codex CLI sandbox profiles.

**Why:** Container-level isolation (Docker/Modal/Daytona) is now table
stakes; Codex set the bar for process-level syscall filtering. For users
who don't want to spin up Docker for every command, syscall-filtered
local execution is the missing trust dial.

**Implementation target:**
- Wrappers in `tools/environments/local.py`:
  - Linux: `bwrap` (preferred) or Landlock-direct via the `landlock` crate
    bindings
  - macOS: `sandbox-exec` (Seatbelt) with profile templates
- New config `terminal.sandbox_profile: read-only | workspace-write |
  full-access`
- Document the failure mode when the host doesn't support the requested
  primitive (graceful degradation to approval mode)

**Effort:** ~2-3 weeks. Profile authoring is the long pole.

---

### 9. `@<provider>` mention syntax in prompts

**Inspiration:** Continue context providers (`@File`, `@Codebase`, `@Diff`,
`@Terminal`, `@Docs`, `@Web`, `@Url`, `@Repo-Map`, `@Problems`, `@Debugger`).

**Why:** Hermes has tools for almost all of these but users have to phrase
intent in natural language. `@`-mentions are a denser, more reliable
composition primitive.

**Implementation target:**
- Prompt-preprocessor in CLI input handler + gateway message router
- `@file:path/to/file.py` → reads + inlines
- `@diff` → inlines current `git diff`
- `@codebase: query` → triggers `repo_map` + `search_files`
- `@docs: package` → context7-style doc fetch via existing MCP server
- Tab-completion for `@`-mentions in TUI

**Effort:** ~2 weeks.

---

### 10. `--add-dir` multi-directory workspaces

**Inspiration:** Claude Code `--add-dir`, monorepo support across Codex
and OpenHands.

**Why:** Hermes' `terminal.cwd` is single-rooted; monorepo and multi-repo
sessions force ugly workarounds.

**Implementation target:**
- `terminal.allowed_roots: [path1, path2, ...]` config
- CLI `--add-dir <path>` (repeatable) and slash command `/add-dir <path>`
- Auto-load `AGENTS.md` and `.hermes/rules/` from each added root
- Edit/read tools gain access to each rooted path; everything else stays
  blocked

**Effort:** ~1 week.

---

### 11. Continue-style PR checks (`.hermes/checks/*.md`)

**Inspiration:** Continue's `.continue/checks/`, Cursor BugBot.

**Why:** Source-controlled AI policies that block merges. Different from
the `hermes-action` wrapper above: checks are policy-as-code, action is
a generic agent wrapper.

**Implementation target:**
- Convention: `.hermes/checks/<name>.md` = check definition (prompt + pass
  criteria)
- Action runs each as a separate GitHub status check; green/red with
  suggested diff comment
- Could ship as a separate GitHub App or as a mode of `hermes-action`

**Effort:** ~1-2 weeks (depends on whether it's a mode of the action or
a separate app).

---

### 12. Session handoff between local and remote (`--teleport`)

**Inspiration:** Claude Code `--teleport`/`--remote`.

**Why:** Hermes has the backends (Modal, Daytona, Vercel) but no formal
"move this session to/from cloud" UX. Users either run local or remote,
never bounce.

**Implementation target:**
- New CLI subcommand `hermes session teleport <id> --to modal|daytona|local`
- Pack session DB row + working tree state + env vars into a transfer
  bundle
- Wakes/spawns target backend, restores state, prints new connection URL
- Reuses kanban claim mechanic to prevent dual-ownership

**Effort:** ~2-3 weeks. Working-tree sync is the hard part.

---

### 13. Public benchmark publication (Polyglot-style)

**Inspiration:** Aider Polyglot Leaderboard, OpenHands Index.

**Why:** Hermes runs SWE-bench mini but doesn't publish results.
Credibility moat for prospective users + ammunition for model-choice
guidance.

**Implementation target:**
- Pick a benchmark suite (SWE-bench Verified subset + Polyglot-style
  multilingual subset)
- Quarterly run pinned to release; publish to
  `website/docs/benchmarks/<date>-<model>.md`
- README badge with most recent headline number
- Include cost-per-task alongside accuracy (Aider's signature column)

**Effort:** Recurring; first run ~1 week of agent time + ~3 days of
plumbing.

---

## T3 — Directionally aligned, unscheduled

### 14. Repo wiki / living architecture diagrams

**Inspiration:** Devin Wiki, OpenHands architecture-summary skill.

**Why:** "Living documentation" auto-indexed on a cadence. Directionally
aligned with Hermes' diagramming + skills posture; not yet a screaming
user request.

**Target:** Periodic skill that runs the existing `diagramming` skill +
`repo_map` output → emits Markdown + Mermaid to `docs/wiki/` on cron.

---

### 15. Architect/editor split (`/architect` slash command)

**Inspiration:** Aider `/architect`, Goose Lead/Worker.

**Why:** Hermes' `auxiliary` config supports per-task model overrides;
formalizing the pattern as a named mode would make cost-optimal routing
discoverable.

**Target:** Document `auxiliary.planner` convention + ship `/architect`
slash command that routes the planning turn to the configured planner
model.

---

### 16. Read-only context paths (cache-eligible)

**Inspiration:** Aider `--read` / `/read-only`.

**Why:** Cheap safe grounding on big specs/docs without risking edits.
Hermes context loader already pulls files; adding a read-only flag +
edit-tool refusal closes the gap.

**Target:** `context.read_only_paths: [...]` config; edit tools refuse
matching paths; loader marks them cache-eligible.

---

### 17. Watch mode with inline triggers (`AI!` / `AI?` in code comments)

**Inspiration:** Aider watch mode.

**Why:** Any editor becomes a Hermes frontend with zero plugin. Hermes
currently requires CLI/gateway interaction.

**Target:** `hermes watch <dir>` mode using `watchdog`; configurable
trigger pattern (default `HERMES!` / `HERMES?`); on save, extract the
trigger comment + surrounding context and dispatch to the agent.

---

### 18. Plan branches / diff sandbox (`hermes plan branch`)

**Inspiration:** Plandex.

**Why:** "Git for prompts" — explore multiple solution paths in parallel.
Overlaps with kanban worker model; would need careful UX design to avoid
duplicating concepts.

**Target:** Wraps checkpoint manager + delegate_task batch mode; each
branch gets its own worktree + session ID.

---

### 19. Lead/Worker model split (`/plan` with `auxiliary.planner`)

**Inspiration:** Goose Lead/Worker.

**Why:** Cost-optimal routing for plan-then-execute workflows. Hermes has
the primitive (`auxiliary` config); needs a named convention + slash
command.

**Target:** Document `auxiliary.planner` model role + add `/plan` slash
command that uses it for the planning turn.

---

### 20. Modes system (Code / Architect / Ask / Debug / Orchestrator) with sticky models

**Inspiration:** Roo Code modes, Cline plan/act.

**Why:** Combines with rules + recipes + permission modes. Hermes
personalities cover persona, not per-mode tool restriction + sticky model
assignment.

**Target:** `modes:` config section with `tools`, `model`, `system_prompt`
per mode. Significant overlap with permission modes (T1 #5) — sequence
this after #5 lands.

---

### 21. AGENTS.md walk-up with `.override.md` layer + byte cap

**Inspiration:** Codex CLI three-tier AGENTS.md resolution.

**Why:** Hermes loads `AGENTS.md` at repo root. Codex walks from git root
down checking `AGENTS.override.md` and `AGENTS.md` at every level,
concatenated up to a byte cap. Cleaner for monorepos.

**Target:** Extend `_load_context_files()` in `run_agent.py`; respect
`project_doc_max_bytes` cap.

---

### 22. Session export to JSON / YAML / Markdown

**Inspiration:** Goose `session export`.

**Why:** Hermes resumes by session ID; export to portable formats with
metadata (tokens, model, cwd, timestamps) is missing.

**Target:** `hermes session export <id> --format md|json|yaml`.

---

### 23. MCP-UI widget rendering in dashboard

**Inspiration:** Goose Desktop MCP-UI.

**Why:** Hermes TUI is text-only; dashboard is HTML. Rendering MCP-UI
responses as interactive widgets is a dashboard-side feature only.

**Target:** Add MCP-UI renderer to the React surface in `web/`.

---

### 24. Adapter contract for external coding agents

**Inspiration:** Paperclip's `claude_local`, `codex`, `cursor`, `gemini`,
`opencode` adapters.

**Why:** Hermes can already delegate via `terminal` to any of these; a
formal adapter contract (start/stop, session-resume, heartbeat, results
capture) tidies multi-agent flows.

**Target:** `agent_adapter` protocol in `tools/`; reference adapters for
the existing `skills/autonomous-ai-agents/` skill set (claude-code, codex,
opencode).

---

### 25. Obsidian-format memory provider

**Inspiration:** OpenHuman Memory Tree.

**Why:** Lets users browse/edit Hermes memory in Obsidian.

**Target:** `plugins/memory/obsidian/` provider; SQLite + markdown vault
layout. Ship as a standalone plugin repo per Hermes' May 2026 policy on
new in-tree memory providers.

---

## Excluded items (recorded so we don't reconsider blindly)

| Item | Source | Reason for exclusion |
|---|---|---|
| Tab autocomplete / Next Edit | Continue, Cursor | IDE territory; Hermes is terminal + gateway |
| Cursor Composer / Devin proprietary model | Cursor, Devin | Hermes is deliberately model-agnostic |
| Bolt.new / Lovable in-browser builders | bolt, Lovable | Different product category |
| Rust-binary monolith distribution | OpenHuman | Python-first + plugin architecture is deliberate |
| Org-chart / "company" UI | Paperclip | Kanban + profiles already cover the substance |
| Streamlit GUI mode | Aider | Hermes dashboard already covers it |
| Separate `.goosehints` file format | Goose | `AGENTS.md` is the canonical Hermes equivalent |
| 118-OAuth-integration bundle | OpenHuman | Plugins + gateway cover the substance |

---

## How this list will be maintained

- Re-run the `competitive-feature-harvester` skill **quarterly** or when a
  major competitor releases (refresh the harvest doc first, then re-rank
  this backlog)
- When a Hermes release ships an item, **move the row from this doc to
  the release notes** with a citation to the original harvest entry — do
  not mark "shipped" inside this doc
- New items added by a future harvest go into the tier whose rationale
  they match; if no tier fits, default to T3
