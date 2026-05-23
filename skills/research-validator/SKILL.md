---
name: research-validator
description: "Gather evidence and validate claims before Hermes commits to a decision. Companion to decision-quality-gate — fills the Evidence Reviewed and Validation Plan sections of the decision ledger with concrete, verifiable artefacts."
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows, android]
metadata:
  hermes:
    tags: [research, validation, evidence, fact-checking, verification, audit, explainability]
    related_skills:
      - decision-quality-gate
      - enterprise-judge
      - enterprise-monitor
      - spike
      - subagent-driven-development
---

# Research & Validator

This is Hermes's evidence-gathering and claim-checking arm. It pairs
with `decision-quality-gate`: the gate decides *what* should be
recorded in the decision ledger; this skill decides *what counts as
evidence good enough to record*.

The premise: the difference between a useful decision ledger and a
piece of agent theatre is whether the `## Evidence Reviewed` section
contains things a sceptic could actually go check. This skill exists
to keep that section honest, and to make sure the
`## Validation Plan` section is something that can actually fail.

## When to invoke this skill

Load `/skill research-validator` (or have the orchestrator load it
automatically) when:

- You are filling in the `## Evidence Reviewed` section of a decision
  ledger and you want to make sure the evidence is real.
- You are filling in the `## Validation Plan` section and you want
  concrete commands rather than wishful checks.
- You are about to commit to the `## Cost / Latency / Quality
  Tradeoff` section and you need a real measurement, not a guess.
- You are reviewing someone else's ledger (a prior session's, another
  agent's, a kanban handoff) and you need to confirm the cited
  evidence actually says what the ledger claims.
- The user explicitly asks "research X" or "validate that Y".
- A `spike` is producing a verdict and you need to record it in a way
  the next session can re-run.

If the task is purely "go execute this concrete instruction" with no
ambiguity, you do not need this skill. If the task is "decide what to
do about X", you almost certainly do.

## Research procedure

Work through the four evidence channels in order. Stop when you have
enough; do not stop earlier. **Enough** is defined per-channel below.
Track everything you do — the `## Evidence Reviewed` ledger section
will copy from this directly.

### 1. Local code & filesystem

The cheapest evidence and usually the most relevant for software work.

```bash
# Symbol / keyword
grep -rn "DecisionLedger" --include="*.py" .

# Where is X defined / called from
grep -rn "def classify_risk" agent/

# Recent changes to a file
git log -n 5 -p -- path/to/file.py
```

Record each command and a one-line summary of the result. If the
command returned nothing, **say so** — `(0 matches)` is evidence too.

**Enough:** you have either (a) found the relevant code and read it,
or (b) confirmed by grep that no such code exists in the repo. Half
of "enough" is being willing to write "this does not exist here".

### 2. Documentation

Project docs first (`AGENTS.md`, `CONTRIBUTING.md`, `docs/`,
`website/docs/`), then upstream library docs via the Context7 /
docs-query MCP server if available, then official websites the user
already trusts.

```bash
# Project docs
ls docs/ website/docs/
grep -rn "kanban" docs/ website/docs/

# Library docs via MCP (if available)
# Use the docs-query tool to fetch current API for the library in question
```

Record the doc path or URL and the specific section/heading you read.
Never cite "the docs" without a path.

**Enough:** the doc says what you need it to say, or you have read it
end-to-end and it does not.

### 3. Web sources

Only if local code and docs are insufficient. The bar here is higher
because web sources are less stable.

- Prefer first-party sources (vendor docs, RFC tracker, the project's
  own GitHub).
- Prefer permalinks (a specific commit, a tagged release, an archived
  blog post) over moving targets.
- Quote the passage you relied on. A bare URL becomes useless when
  the page changes.

```markdown
- Web sources:
  - https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
    (section: "How prompt caching works", retrieved 2026-05-23):
    "Cache breakpoints persist for 5 minutes by default."
```

**Enough:** you have a quote, a URL, and the date you read it.

### 4. Prior Hermes memory / session notes

The persistent memory layer (`hermes memory status`) and the session
store (`$HERMES_HOME/sessions/`) often hold the answer to "what did
we decide last time?". For a re-engaged task, check this *first*, not
last — it is faster than re-research.

```bash
hermes sessions browse              # interactive picker
hermes sessions export tmp.jsonl    # then grep for keywords
```

Past **decision ledgers** are the highest-signal slice of session
memory. Walk `$HERMES_HOME/decisions/<session_id>/` for any sessions
referenced in the task: each `NNNN-<slug>.md` file is already
formatted for this purpose.

```bash
# Show prior decisions in a known session
ls $HERMES_HOME/decisions/<session_id>/
grep -l "delegation model" $HERMES_HOME/decisions/*/*.md
```

If `memory` is enabled, search via the `session_search` toolset
inside the running session.

**Enough:** you have either found a prior decision (cite the session
id and the ledger path) or confirmed none exists for this question.

## Validation procedure

A research output is not a validation. Validation is the *post-hoc*
check that the decision actually worked. The `## Validation Plan`
section of the ledger should list, at minimum, one of each:

### Automated check

A command that returns a clear pass/fail. Examples:

```bash
python -m pytest tests/agent/test_prompt_builder.py -q
mypy --strict agent/
ruff check .
curl -fsS http://localhost:8080/health | jq .status   # expect "ok"
```

The command must be **runnable from a fresh shell** with no implicit
state. If it requires setup (start a service, set an env var), that
setup is part of the command.

### Manual check

A specific observation a human can make. Examples:

```markdown
- Open the dashboard at http://localhost:3000/decisions and confirm
  the new ledger appears at the top of the list.
- Send a `/skill decision-quality-gate` command and verify the
  resulting reply contains every one of the 15 H2 sections.
```

Vague manual checks ("looks fine", "seems to work") are not
acceptable. Name what you are looking for.

### Success criterion

The binary "did it work?" sentence. The validation plan is the
*procedure*; the success criterion is the *acceptance test*. They
are not the same:

```markdown
Validation Plan:
  Commands: `pytest tests/agent/`
  Manual checks: observe a passing run, no skips
  Success criteria: all tests pass; no new skipped tests; runtime
    within 10% of the pre-change baseline (52s).
```

A success criterion that cannot be measured is not a success
criterion — it is a hope.

## Cost / latency / quality measurement

The ledger's `## Cost / Latency / Quality Tradeoff` section asks for
numbers. When you have a previous run's numbers, cite them; when you
don't, take an honest measurement.

- **Cost** — token budget × model price, or wall-clock × runtime
  cost. If the action is going to run repeatedly (cron, webhook,
  kanban dispatch), multiply through.
- **Latency** — measured per-turn or per-request, not "feels fast".
  `time hermes …` or `curl -w '%{time_total}\n' …` is the right
  shape of evidence.
- **Quality** — the specific bar this decision clears. "Passes the
  12-file refactor benchmark within 5% of Opus" is a quality bar.
  "Seems good" is not.

If you cannot measure any of these honestly, your `## Confidence`
should be `low` and the gap should appear in `## Open Risks`.

## Cross-check (claim validation)

When you are checking *someone else's* claim — a prior ledger, an
agent's structured output, a user-provided statement — apply the same
four-channel discipline in reverse:

1. Does the local code match the claim? Grep / read it.
2. Do the cited docs say what the claim says they say? Open them.
3. Do the cited web sources still exist and say the quoted thing?
   Fetch them.
4. Has Hermes seen this question before with a different answer?
   Search session/memory.

Any of these channels disagreeing with the claim is grounds to mark
the claim **disputed** in the ledger you produce. Do not silently
"correct" the prior ledger — record the disagreement explicitly so
the audit trail survives.

This is the same discipline the enterprise Judge applies to leaf
results (see [`skills/enterprise-council/judge/SKILL.md`](../enterprise-council/judge/SKILL.md)).
The Judge enforces it on a structured-output boundary; this skill
enforces it on a free-text ledger.

## Output contract

When invoked, produce one of two outputs:

### A. Evidence packet (research mode)

Markdown block ready to paste into a ledger's `## Evidence Reviewed`
section. Each item starts with its channel marker:

```markdown
- Files: `agent/prompt_builder.py:142-180` — defines
  `build_environment_hints`; reads `TERMINAL_ENV` to decide local vs
  remote.
- Commands: `grep -rn "build_environment_hints" .` → 4 hits, all in
  `agent/` and `tests/agent/`.
- Docs: `docs/hermes-local-orchestrator.md` — describes the Android
  app's lifecycle; no mention of decision ledgers.
- Web sources: (none consulted; question answered from local code)
- Prior memory: session `20260520_141200_a1b2c3` decided to use
  DataStore Preferences for Android settings; ledger at
  `$HERMES_HOME/decisions/.../0001-android-settings.md`.
- Gaps: have not verified Windows behaviour; flagged as open risk.
```

### B. Validation packet (validate mode)

Markdown block ready to paste into a ledger's `## Validation Plan`
section:

```markdown
- Commands:
  - `python -m pytest tests/test_decision_ledger.py -q`
  - `python -c "from hermes_cli import decision_ledger as dl; dl.parse_markdown(open('templates/orchestration/decision-ledger-template.md').read())"`
- Manual checks:
  - Open `skills/decision-quality-gate/SKILL.md` and confirm all 15
    ledger sections are referenced by name.
  - Cross-link from `docs/orchestration/decision-quality-system.md`
    resolves on GitHub.
- Success criteria:
  - All checks pass; the schema in `decision_ledger.py` matches the
    schema in `docs/orchestration/decision-ledger.md`; no broken
    cross-links.
```

## Anti-patterns

| Anti-pattern | Fix |
|---|---|
| "I read the codebase" with no paths | Cite specific files and line ranges, or admit you didn't |
| Validation: "looks correct on inspection" | Give a command or named manual check |
| Citing a doc without saying which section | Include the heading / anchor / line you relied on |
| "Standard practice" with no source | Either cite the source or call it "Hermes convention" |
| Skipping memory/session search on a re-engaged task | Always check session store first when resuming |
| "Tests pass" as the only success criterion | Name *which* tests, and what "pass" means including timing/skip budget |
| Estimating cost/latency from gut feel | Take a measurement; if you can't, say so and lower confidence |
| Treating the curator's last review as definitive | Re-check; the curator can be wrong too |

## Cross-references

- **Gate that consumes this output:** [`skills/decision-quality-gate/SKILL.md`](../decision-quality-gate/SKILL.md)
- **Ledger schema:** [`docs/orchestration/decision-ledger.md`](../../docs/orchestration/decision-ledger.md)
- **Blank template:** [`templates/orchestration/decision-ledger-template.md`](../../templates/orchestration/decision-ledger-template.md)
- **Python helper:** [`hermes_cli/decision_ledger.py`](../../hermes_cli/decision_ledger.py) — render, parse, validate, write, read
- **System overview:** [`docs/orchestration/decision-quality-system.md`](../../docs/orchestration/decision-quality-system.md)
- **Spike skill:** [`skills/software-development/spike/SKILL.md`](../software-development/spike/SKILL.md) — when research itself requires a throwaway experiment
- **Enterprise judge:** [`skills/enterprise-council/judge/SKILL.md`](../enterprise-council/judge/SKILL.md) — formal validator for leaf results
- **Enterprise monitor:** [`skills/enterprise-council/monitor/SKILL.md`](../enterprise-council/monitor/SKILL.md) — flags systemic ledger-quality regressions
