# Hermes Feature Backlog — Competitive Harvest Output

**Source:** Phase 23 refresh of the Phase 21 harvest in
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
- `[P23]` markers identify items added in the Phase 23 refresh

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
- Reuses `muse webhook subscribe` mechanic under the hood

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

### 5b. `[P23]` Per-category usage accounting (`muse usage --by skill|subagent|plugin|mcp`)

**Inspiration:** Claude Code v2.1.149 `/usage` per-category breakdown.

**Why:** Hermes' decision ledger logs every model call but there's no
aggregated view by primitive. Users asking "where is my budget going?"
get raw rows, not a roll-up. Five major competitors expose some flavor
of this; Claude Code's per-category breakdown is the strongest pattern.

**Implementation target:**
- New `muse usage` subcommand reading the existing ledger
- Group-by options: `skill`, `subagent`, `plugin`, `mcp_server`, `model`
- Output: table + JSON; JSON feeds the dashboard
- Add a "projected vs actual" column once Claude Code's
  `estimated_context_tokens` pattern is borrowed for our `plugin.yaml`

**Effort:** ~3-5 days. Aggregation logic + dashboard widget.

---

### 5c. `[P23]` `/code-review` slash command (effort levels + PR comments)

**Inspiration:** Claude Code v2.1.147 `/code-review`, Goose v1.35.0 local
code review.

**Why:** Hermes has the `requesting-code-review` skill + `github_assistant`
plugin separately. Both Anthropic and Block converged on the same week on
"one slash command, effort dial, posts PR comments." Easy parity win.

**Implementation target:**
- New `/code-review [--effort low|medium|high] [--post-pr-comments]`
  slash command in `agent/skill_commands.py`
- Routes effort levels to the `auxiliary` model registry (cheap model for
  low, primary for high)
- When `--post-pr-comments` set, uses `github_assistant.add_pr_comment` to
  push findings inline rather than printing to stdout

**Effort:** ~3-5 days. Glue between existing skill, GitHub plugin, and
auxiliary model router.

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
- New CLI subcommand `muse session teleport <id> --to modal|daytona|local`
- Pack session DB row + working tree state + env vars into a transfer
  bundle
- Wakes/spawns target backend, restores state, prints new connection URL
- Reuses kanban claim mechanic to prevent dual-ownership

**Effort:** ~2-3 weeks. Working-tree sync is the hard part.

---

### 12b. `[P23]` `/goal` self-evaluation primitive

**Inspiration:** Goose v1.35.0 `/goal` self-evaluation slash command.

**Why:** Hermes' decision ledger captures what happened but doesn't tell
the agent (or the user) whether what happened achieved the goal. Goose
shipped this in May 2026 and the pattern is simple enough to copy
cleanly. Complements but doesn't duplicate the orchestrator's validation
gate (which evaluates artifacts, not goals).

**Implementation target:**
- `/goal set <text>` writes a `Goal` row to the session DB (status: open)
- `/goal evaluate` prompts the model with the goal + the decision ledger
  + the validation results, emits a structured pass/fail/partial verdict
- `/goal close` marks done; integrates with the kanban worker model so a
  worker can claim a goal, work it, and close it
- Surfaces in dashboard as a "goals" sidebar

**Effort:** ~1 week. New DB row + slash commands + dashboard widget.

---

### 12c. `[P23]` GitLab assistant plugin

**Inspiration:** Devin's May 22 GitLab PR review parity with GitHub.

**Why:** Hermes' `github_assistant` plugin is a flagship; GitLab users get
the GitHub MCP server's tools but no first-class plugin. Devin shipped
GitLab parity — Hermes should match before the gap becomes a competitive
talking point.

**Implementation target:**
- New `plugins/gitlab_assistant/` mirroring `github_assistant/` (same
  toolset shape: `list_mrs`, `comment_on_mr`, `create_mr`, etc.)
- Auth via `~/.hermes/.env` (`GITLAB_TOKEN` + optional `GITLAB_URL` for
  self-hosted)
- Update `docs/github-integration.md` → rename to
  `docs/scm-integration.md` and cover both surfaces

**Effort:** ~1-2 weeks. Most of the work is mapping GitLab's API onto the
existing tool surface.

---

### 12d. `[P23]` Jira gateway plugin (ticket-to-agent loop)

**Inspiration:** Cursor's May 19 Jira integration (assign work to agents
from tickets).

**Why:** Hermes has Slack/Discord/Telegram/Email gateways but no Jira
gateway. Tickets are where engineering work actually starts at most
orgs; Hermes' kanban covers the internal case but not the
"organization already uses Jira" case.

**Implementation target:**
- New `gateway/platforms/jira.py` listening for ticket assignments to
  the `hermes` user
- On assignment: pull description + comments, spawn a kanban worker, post
  progress back as ticket comments, close ticket on validation pass
- Reuse existing webhook plumbing

**Effort:** ~1-2 weeks. Jira webhook setup + reverse-direction comment
posting.

---

### 12e. `[P23]` Plugin manifest preview + dependency declaration

**Inspiration:** Claude Code v2.1.143-2.1.145 `/plugin` Discover, dependency
enforcement, projected context-cost in the marketplace.

**Why:** Hermes plugins register tools at load time with no pre-install
preview and no dependency declaration. Borrowing the `npm`-style rigor
from Claude Code is a low-cost reliability win.

**Implementation target:**
- Add `dependencies:` and `estimated_context_tokens:` fields to
  `plugin.yaml`
- New `muse plugin show <name>` that prints the plugin's exposed tools,
  hooks, slash commands, MCP servers, dependencies, and projected cost
  before activation
- Loader validates dependencies and refuses to load on missing prereqs
  (or installs them with `--with-deps`)

**Effort:** ~1 week. Manifest schema + loader changes + CLI subcommand.

---

### 12f. `[P23]` Output schemas for cron jobs

**Inspiration:** Codex CLI v0.132.0 — resumed automations enforce
structured JSON output schemas.

**Why:** Hermes cron jobs return free-form text; downstream consumers
(other cron jobs, kanban tasks, dashboards) have to parse it
defensively. Schema-enforced output makes the output graph reliable.

**Implementation target:**
- Add `output_schema:` (JSON Schema) to cron job spec
- Validator in `cron/scheduler.py` re-prompts the agent on schema
  violation up to N retries
- Schema-violating jobs fail loudly to the dashboard rather than emitting
  bad data downstream

**Effort:** ~3-5 days.

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

**Target:** `muse watch <dir>` mode using `watchdog`; configurable
trigger pattern (default `HERMES!` / `HERMES?`); on save, extract the
trigger comment + surrounding context and dispatch to the agent.

---

### 18. Plan branches / diff sandbox (`muse plan branch`)

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

**Target:** `muse session export <id> --format md|json|yaml`.

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

### 24b. `[P23]` Concurrent plugin loading

**Inspiration:** Cline CLI v3.0.9 — concurrent plugin loading for faster
startup.

**Why:** Hermes plugin discovery is sequential; cold-start matters for
Termux/mobile use cases. Cline shipped concurrent loading as a measured
win.

**Target:** Switch `agent/plugins/__init__.py` to `asyncio.gather()` over
plugin discoverers; benchmark startup time pre/post.

---

### 24c. `[P23]` Goal entity in session DB

**Inspiration:** Codex CLI v0.133.0 — goals enabled by default with
dedicated storage.

**Why:** Memory backends store facts and preferences; goals are different
in shape (status, deadline, owner, validation criteria). A first-class
`Goal` row enables better summarization, better dashboards, and the
`/goal evaluate` flow above without reusing the memory table.

**Target:** New `Goal` row in `hermes_state.py` linked to session ID and
optional kanban task; CRUD via `/goal` slash commands.

---

### 24d. `[P23]` Tamper-evident decision ledger (HMAC chain option)

**Inspiration:** Bernstein's HMAC-chained audit log + signed agent cards.

**Why:** Hermes' decision ledger is append-only but doesn't cryptographically
chain entries. For compliance-positioned users (Bernstein's pitch), a
tamper-evident option is the deciding factor between Hermes and a
purpose-built compliance orchestrator. Not every Hermes user needs it —
hence T3.

**Target:** Optional `ledger.hmac_chain: true` config. Each ledger row
includes `prev_hmac` computed from the previous row + a per-job key. Add
`muse ledger verify <job-id>` to detect breaks. Document the threat
model honestly: this defends against post-hoc tampering of a stored
ledger, not against a compromised process while a job runs.

---

### 24e. `[P23]` Triage recipe (autonomous issue triage)

**Inspiration:** Devin Auto-Triage (May 18 blog).

**Why:** Once recipes (T1 #6) ship, autonomous issue triage is a natural
demo. Sits on top of existing primitives (`github_assistant`, kanban,
delegate_task) — the recipe is the choreography.

**Target:** Ship `recipes/triage.yaml` once T1 #6 lands. Inputs: repo,
label-filter, since-date. Output: PRs opened or comments posted.

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

---

## Phase 23 refresh summary (2026-05-23)

- **Verified:** OpenHuman and Paperclip both still alive and growing;
  Phase 21 claims hold with one drift (Paperclip's headline adapter list
  no longer includes Gemini; OpenClaw is now first-class).
- **New T1-shaped items:** per-category usage accounting (`5b`), code
  review slash command (`5c`).
- **New T2-shaped items:** goal self-evaluation (`12b`), GitLab plugin
  (`12c`), Jira gateway (`12d`), plugin manifest preview (`12e`), cron
  output schemas (`12f`).
- **New T3-shaped items:** concurrent plugin loading (`24b`), goal entity
  (`24c`), tamper-evident ledger (`24d`), triage recipe (`24e`).
- **No-changes products in window:** Aider (last release Aug 2025),
  Continue (last release March 2026), Plandex (next release July 2026).
- **One new competitor identified:** Bernstein — Python orchestrator with
  HMAC-chained audit log; closest direct competitor to Hermes
  orchestration. Tamper-evident ledger item (`24d`) is the response.
