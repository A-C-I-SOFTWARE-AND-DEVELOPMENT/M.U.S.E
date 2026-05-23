# Orchestrator slash command reference

Phase 16 promotes the orchestrator from a skill-only surface to a set of
first-class Hermes slash commands.  Every command listed here is defined
in `hermes_cli/commands.py` and dispatched through the shared controller
in `hermes_cli/orchestrator.py`, so the CLI (`cli.py`) and the gateway
(`gateway/run.py`) hand identical text to identical Python.

## Design contract

* **Local-first.**  All state lives under
  `$HERMES_HOME/orchestrator/` (`jobs.json`, `decision_ledger.json`,
  `ai_radar.json`, `best_coding_tool_mission.json`).  Nothing is
  uploaded.
* **No silent workers.**  Submitting a job (`/orchestrate <prompt>`)
  records the request and assigns it an id.  It does **not** spawn
  an agent — that requires explicit configuration and an explicit
  approval step.  This mirrors the local-orchestrator contract in
  `docs/hermes-local-orchestrator.md`.
* **CLI is the source of truth.**  Both the interactive CLI and the
  gateway call the same `run_*` entry points in
  `hermes_cli/orchestrator.py`.  Skill-based invocation
  (`/enterprise-orchestrator` and the other slash skills under
  `skills/enterprise-council/`) continues to work unchanged — these
  native commands sit beside that surface, not in place of it.
* **Discoverable.**  Each command is registered with `CommandDef`, so
  it appears in `/help`, in the tab-completer, and (when not
  `cli_only`) in the gateway help, Telegram `setMyCommands`, Discord
  slash registration, and Slack subcommand mapping.

## Command catalogue

### `/orchestrate <prompt>`

Queue a new local orchestrator job.

```
> /orchestrate refactor the auth flow to use the new SessionDB helpers
✓ Orchestration job queued: orc-1a2b3c4d
  status:  queued
  prompt:  refactor the auth flow to use the new SessionDB helpers

No worker has started.  Use /orchestrator status orc-1a2b3c4d to inspect.
```

### `/orchestrator status [job-id]`

With no argument, list every job (newest first).  With a job id,
print the job's full record (prompt, status, timestamps, resumes,
publish state, notes, artifacts).

### `/orchestrator list`

Same as `/orchestrator status` with no argument — kept as an explicit
verb so users can type whichever feels natural.

### `/orchestrator open <job-id>`

Print the full job record.  Equivalent to `/orchestrator status <id>`
but kept distinct so it shows up in the subcommand picker.

### `/orchestrator resume <job-id>`

Mark a `paused` or `failed` job as `queued` and bump its `resumed_count`.
The orchestrator records a `resume` entry in the decision ledger.

### `/orchestrator publish <job-id>`

Mark a job as `published`.  Records a `publish` entry in the decision
ledger and stamps `published_at`.

### `/model-router explain <prompt>`

Explain which model/profile the router would pick for a prompt
**without** flipping the live model.  To actually switch, use `/model`.

```
> /model-router explain please review this diff
  route:     reviewer-profile
  rationale: code review prompts go to the reviewer profile
  matched:   reviewer-profile
```

### `/decision-ledger show [job-id]`

Print the decision ledger.  Without an argument, show every job; with
an id, show only that job's entries.  Each entry has a timestamp,
a `kind` (`submit`, `resume`, `publish`, or anything later written by
the worker), and optional structured extras serialized as JSON.

### `/ai-radar update`

Refresh the local AI-radar snapshot.  The CLI surface writes a stamped
JSON record under `$HERMES_HOME/orchestrator/ai_radar.json`; a real
external feed is wired by setting
`orchestrator.ai_radar.feed_url` in `config.yaml`.

### `/best-coding-tool-mission status`

Print the mission summary and live metrics
(`jobs_submitted` / `jobs_published` / `jobs_resumed`).  Metrics are
re-derived from `jobs.json` on every call so the snapshot is honest
even when the mission file has been hand-edited.

## Storage layout

```
$HERMES_HOME/orchestrator/
├── jobs.json                       # list[Job]
├── decision_ledger.json            # {job_id: [entry, …]}
├── ai_radar.json                   # {updated_at, source, note, …}
└── best_coding_tool_mission.json   # {mission, metrics, next_actions}
```

All writes go through an atomic temp-file rename so a Ctrl-C in the
middle of a write cannot leave a partial file.

## Gateway behaviour

All six Phase 16 commands are registered `cli_only`.  This is deliberate:
Slack's app manifest caps slash commands at 50 per app, and each new
gateway-visible canonical bumps a high-value alias (`/btw`, `/bg`, `/q`)
off the manifest.  CLI parity is the Phase 16 contract; gateway parity
is deferred.

The gateway dispatcher in
`gateway.run.HermesGateway._handle_orchestrator_slash` is wired and
ready — it calls the same `run_*` entry points in
`hermes_cli.orchestrator` via `asyncio.to_thread` and truncates output
longer than ~3800 characters to keep messaging adapters happy.  Because
the commands are `cli_only`, `is_gateway_known_command` returns False
for them and the dispatcher is dormant.  A future phase flips this on
by either:

* dropping `cli_only=True` from the six `CommandDef` entries, or
* adding `gateway_config_gate="orchestrator.gateway_enabled"` so an
  operator can opt in by setting the config key truthy.

Either path picks up the existing handler automatically — no further
gateway code changes are required.

Per-platform admin gating (`allow_admin_from`, `user_allowed_commands`)
covers these commands without any additional configuration because
`is_gateway_known_command` reads directly from the central
`COMMAND_REGISTRY`.

## Tests

`tests/test_orchestrator_commands.py` covers:

* The CommandDef entries are present, well-formed, and discoverable.
* Each `run_*` entry point handles missing args, unknown subcommands,
  help payloads, and the success path.
* Submitting / resuming / publishing jobs persists to disk and updates
  the decision ledger.
* `model_router_explain` returns a deterministic route for the curated
  keyword set.
* `ai-radar update` and `best-coding-tool-mission status` write /
  read their respective JSON files without touching jobs or the
  ledger.

Run with:

```bash
python -m pytest tests/test_orchestrator_commands.py -q
```
