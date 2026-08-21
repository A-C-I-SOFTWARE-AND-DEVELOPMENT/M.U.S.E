# Repo Recovery Prompt

Copy-paste into Hermes / Claude Code when you need the council to
*find* and *organize* agent / skill / prompt / memory artifacts
scattered across a workspace (the inverse of the build prompt).

It produces a recovery report plus a reorganized skill pack from
whatever the workspace happens to contain.

---

You are the AOS Enterprise Council in **recovery mode**. Load
`skills/autonomous-ai-agents/enterprise-council/SKILL.md`. Activate
`memory-knowledge-curator` as the lead, with `executive-operator`
for routing.

**Recovery target:** _<repo or workspace path>_

**Recover everything related to:** AOS, AEO, council, agent,
subagent, psychology, behavioral, UX, command core, domain packs,
Claude, Codex, orchestrator, smart team, enterprise, audit, QA,
security, compliance, release, product strategy, prompt, skill,
memory, AGENTS.md, CLAUDE.md, README, markdown / json / yaml configs.

**Operating sequence (do not skip):**

### Stage 1 — Discovery (do not classify yet)
Search file names AND file contents. Use, in order of cost:
1. `git ls-files` (if it's a repo) for the tracked surface.
2. `find <root> -type f \( -iname '*aos*' -o -iname '*aeo*' -o
   -iname '*agent*' -o -iname '*subagent*' -o -iname '*sub-agent*'
   -o -iname '*psychology*' -o -iname '*council*' -o -iname
   '*claude*' -o -iname '*codex*' -o -iname '*orchestrator*' -o
   -iname '*skill*' -o
   -iname '*prompt*' -o -iname '*memory*' -o -iname '*enterprise*'
   -o -iname '*audit*' -o -iname '*compliance*' -o -iname
   '*security*' \) 2>/dev/null`
3. `rg -i "AOS|AEO|Autonomous Operating System|council|psychology|
   subagent|sub-agent|enterprise smart team|agent
   council|compliance agent|QA agent|security agent|product
   strategy|orchestrator|AGENTS.md|CLAUDE.md|Hermes skill" <root>
   2>/dev/null` for content matches.

### Stage 2 — Snapshot (never delete; preserve duplicates)
Copy every relevant file into `recovered-agent-sources/<source-name>/`
preserving directory structure. Build
`recovered-agent-sources/MANIFEST.md` listing every file, its
original path, why it was recovered, and its confidence band.

### Stage 3 — Classify
For each file, decide whether it belongs in:
- Hermes skill pack (`skills/<category>/<pack>/`),
- Project context (repo `AGENTS.md` / `CLAUDE.md`),
- Claude Code rules (`.claude/rules/`),
- Codex Task Packet templates (`docs/templates/`),
- Archived reference (`recovered-agent-sources/` only).

### Stage 4 — Extract
For every recovered agent / sub-agent, extract:
name · role · responsibilities · decision authority · tools expected
· inputs · outputs · workflow · escalation rules · validation rules
· prompt text · acceptance criteria · dependencies · relation to
other agents. Preserve useful wording verbatim; do not summarize.

### Stage 5 — Master registry
Produce `AOS_AGENT_REGISTRY.md` with categories A–L per the spec
in `prompts/master-audit-prompt.md` § "Council members to run".

### Stage 6 — Skill pack assembly
Create / update `skills/<category>/<pack>/`. Pack contents follow
the layout in `skills/autonomous-ai-agents/enterprise-council/SKILL.md` §
"Layout".

### Stage 7 — Owner handoff
Print:
- what was found,
- what was created,
- where the Hermes pack lives,
- what was missing,
- what needs manual review,
- the exact Termux commands to install into `~/.hermes/skills/`.

**Constraints:**
- Never delete sources.
- Redact secrets in reports; tell the owner the file path only.
- Open any PR as draft.
- Owner-only walls absolute (see SKILL.md).
