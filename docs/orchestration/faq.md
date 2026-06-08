# FAQ

Conceptual questions that come up over and over. For symptoms-of-
failure, read [troubleshooting.md](troubleshooting.md) instead.

## Concepts

### Is this just another agent framework?

No. M.U.S.E. Orchestration is the **runtime** that turns a goal into
a graph of validated tasks. The "agent" is whatever M.U.S.E. profile
you point at each card — and a M.U.S.E. profile is just a model +
tools + skills + environment combination.

Concretely: there is no `Agent` class to subclass, no decorator API
to learn. You write a Markdown playbook (a skill) and configure a
profile in YAML.

### How is this different from Claude Code Routines / GitHub Actions / etc.?

| | Claude Code Routines | GitHub Actions | M.U.S.E. Orchestration |
|---|---|---|---|
| Triggers | Cron, GH events, API | Cron, GH events, API | All of the above + slash commands + gateway DM + Android cockpit + scripts |
| Decomposition | Single prompt → single agent run | Pre-defined workflow YAML | Orchestrator decomposes prompt into task graph at runtime |
| Worker isolation | Anthropic infra, fixed | GH runners, opinionated | 7 environment backends, your infra |
| Model choice | Claude only | Any (via API key in secret) | Any, with per-card routing rules |
| Audit trail | GH comments | Action logs | Decision ledger + per-card trace |
| Cost model | Subscription with daily cap | Per-minute compute | Your API key, your rates |
| Offline / private | No | Self-hosted runners possible | First-class private/local mode |

The orchestration *shape* — decompose, fan out, validate, publish —
is the same idea. The pieces are interchangeable.

### Why "Kanban" inside the orchestrator?

The job substrate is literally a Kanban board with the standard
states (`todo → ready → in_progress → done | blocked | failed`).
This was a deliberate choice in March 2026: it makes the work
inspectable, it makes the dependency graph explicit, and it gives
human operators a familiar visual model when things go sideways.

The orchestrator is "just" the agent that creates and links cards.
The dispatcher is "just" the worker that turns `ready` into
`in_progress`. You can read the SQLite directly if you want.

### Why is the decision ledger append-only JSONL?

Because:

- `jq` and `grep` work without any tooling.
- Replay is trivial: re-run from any line.
- Diffing two runs of the same prompt is a literal `diff`.
- Compression compresses well (~10x with gzip).
- No vendor format to depend on.

If you need a structured query layer on top, mirror the ledger
into your favorite database from the `observability` plugin. The
ledger stays canonical.

## Behavior

### What does the orchestrator do if the user prompt is ambiguous?

The `kanban-orchestrator` skill is explicit: cheap to ask, expensive
to spawn the wrong fleet. The orchestrator will ask a clarifying
question *before* creating cards if the goal is unclear. The
`enterprise-council/orchestrator` skill in contrast accepts the
prompt verbatim and never asks — it's optimized for the
"one-tap" flow.

You pick which orchestrator skill to load based on which behavior
you want. Or load neither and write your own.

### Can the orchestrator spawn another orchestrator?

Yes. Orchestrators are profiles, profiles can be assigned to cards,
so a card can have an orchestrator as its worker. This is useful
when a high-level lane is itself complex enough to want
decomposition.

There is a depth gate (`hermes_cli/_parser.py`) that prevents
infinite recursion — leaves spawned with `role="leaf"` cannot
spawn deeper. The orchestrator skill mentions this in its
"Don't pre-create the whole graph if the shape depends on
intermediate findings" pitfall.

### What if I don't want validation gates?

Set `orchestration.gates.enabled: false` in `~/.hermes/config.yaml`.
Cards then flip straight from `in_progress` to `done` on worker
completion. You lose the judge feedback loop, the policy gate, and
the schema gate.

This is supported but not recommended outside development. The
default is to fail loudly than to publish silently-wrong output.

### Can I run the same job on multiple model providers and compare?

Yes:

```bash
bash scripts/hermes-orchestrate.sh "<goal>" --tag run-a --model engineer=anthropic:claude-sonnet
bash scripts/hermes-orchestrate.sh "<goal>" --tag run-b --model engineer=openai:gpt-5
diff ~/.hermes/jobs/job_run-a*/summary.md ~/.hermes/jobs/job_run-b*/summary.md
```

Or use the routing rules to A/B by tag.

## Capabilities

### Self-improvement

M.U.S.E. has a built-in learning loop (the "skill system"). When the
orchestrator completes a complex job, it can propose a new skill
that codifies what worked. The `enterprise/monitor.py` curator
reviews these proposals and either accepts (writes to
`~/.hermes/skills/`) or discards.

You see this in action by running a few orchestrated jobs and then
checking:

```bash
muse skills list --user-created
```

Skills authored by M.U.S.E. itself show up with a `[auto]` tag. You
edit them like any other skill and `/reload-skills` picks up the
change.

This is the only AI agent we know of that ships with skill
self-authorship turned on by default. It can be turned off:

```yaml
self_improvement:
  skill_proposals: false
  memory_curation: false
```

### AI radar

M.U.S.E. ships an "AI radar" — a scheduled scan that watches a small
set of authoritative sources (GitHub releases of major model
providers, arXiv categories, well-known blogs) and surfaces
relevant changes. It's a cron job under the hood:

```bash
muse cron list | grep ai-radar
```

The default radar pings your gateway DM when something material
ships (new SOTA model, new agent framework, security advisory in
a dep we use). You can scope it to topics, frequencies, and
delivery targets. See `skills/research/ai-radar/SKILL.md`.

The orchestrator hooks into the radar in one direction: if a radar
hit changes the optimal model choice for a profile, the routing
layer's "freshness" rule picks up the change on next dispatch.

### Why is the audit so heavy?

Because *not* having it caused real incidents. The ledger lets you:

- Answer "what did the agent actually do?" in a regulated
  environment.
- Replay a run that produced a surprising outcome.
- Diff two runs to localize a behavior change.
- Reconstruct cost / latency by-profile, by-card, by-job.

The cost is ~1-5 KB per card. For a 10-card job that's 50 KB. The
benefit is that "I don't know what it did" is never an answer.

## Practical

### How do I write a custom orchestrator skill?

Copy `skills/devops/kanban-orchestrator/SKILL.md` to
`~/.hermes/skills/<your-org>/<your-orchestrator>.md` and edit.

The contract a skill must satisfy:

- Run `muse profile list` (or accept it from context) before
  decomposing.
- Emit a plan as either:
  - A series of `kanban_create` tool calls, or
  - A single JSON block per the enterprise-council contract.
- Set parent links via the `parents=[...]` arg, not via prose.
- Call `kanban_complete` on its own card when done planning.

Then load it in your orchestrator profile:

```yaml
profiles:
  orchestrator:
    preloaded_skills:
      - <your-org>/<your-orchestrator>
```

### How do I gate the orchestrator from running expensive jobs?

Cost-cap with a routing rule:

```yaml
orchestration:
  routing:
    - when: job.budget_usd_remaining < 0.50
      use: anthropic:claude-haiku    # or your cheapest model
  budgets:
    default_job_budget_usd: 5.00
```

The orchestrator and every worker check `job.budget_usd_remaining`
before each model call. When it hits zero, the gate refuses
further model calls and the job escalates.

### How do I run this in CI?

```yaml
# .github/workflows/hermes-audit.yml
on:
  schedule: [ {cron: '0 6 * * 1'} ]   # Mondays 06:00 UTC
  workflow_dispatch:

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: |
          curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
          source ~/.bashrc
      - env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_PERSONAL_ACCESS_TOKEN: ${{ secrets.HERMES_GH_PAT }}
        run: |
          bash scripts/hermes-orchestrate.sh "Audit this repo and open a draft PR" \
            --deliver pr --pr-draft --autonomy strict
```

`--autonomy strict` means HIGH-risk steps fail rather than escalate
(no human is around to approve in CI). The PR opens in draft so a
human reviews before merging.

### Where do I report bugs?

GitHub issues on the main repo. Attach:

- The job folder (tar / zip the directory).
- `muse doctor` output.
- `muse profile list` and the relevant section of
  `~/.hermes/config.yaml` (redact keys).

### Where does the name come from?

M.U.S.E.. Messenger of the gods, escorted things between worlds,
sometimes a trickster. We thought it fit.

## See also

- [README.md](README.md) — the overview.
- [getting-started.md](getting-started.md) — five-primitive intro.
- [troubleshooting.md](troubleshooting.md) — failure patterns and
  fixes.
- [worker-adapters.md](worker-adapters.md) — when one profile isn't
  enough.
- [`skills/devops/kanban-orchestrator/SKILL.md`](../../skills/devops/kanban-orchestrator/SKILL.md)
  — the actual orchestrator playbook.
- [`enterprise/`](../../enterprise/) — the council pattern.
