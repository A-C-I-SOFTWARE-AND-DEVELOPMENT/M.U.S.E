# Orchestrator slash command reference

The orchestrator surface is exposed as a set of first-class muse slash
commands.  Every command listed here is defined in
`hermes_cli/commands.py` and dispatched through the shared controller
in `hermes_cli/orchestrator.py`, so the CLI (`cli.py`) and the gateway
(`gateway/run.py`) hand identical text to identical Python.

## Design contract

* **Local-first.**  All state lives under
  `$HERMES_HOME/orchestrator/` (`jobs.json`, `decision_ledger.json`,
  `ai_radar.json`, `best_coding_tool_mission.json`,
  `voice_capture.json`, `remote_workers.json`, `self_improve.json`,
  `validation.json`, `publish_plans.json`,
  `profile_github_history.json`).  Nothing is uploaded.
* **No silent workers.**  Submitting a job (`/orchestrate <prompt>`)
  records the request and assigns it an id.  It does **not** spawn
  an agent — that requires explicit configuration and an explicit
  approval step.  This mirrors the local-orchestrator contract in
  `docs/hermes-local-orchestrator.md`.
* **Publish / remote / secret actions require approval.**  The
  `publish-plan`, `self-improve run`, and remote-worker dispatch paths
  refuse to advance until `/orchestrator approve <job-id> <phase>` has
  been called for the matching phase (`plan`, `publish`, `remote`, or
  `self_improve`).  Approvals are recorded on the job and in the
  decision ledger.
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

### `/orchestrator cancel <job-id>`

Mark a job as `cancelled`.  Cancellation is one-way for non-published
jobs — already-published jobs are left alone so the publish record
stays honest.  The orchestrator records a `cancel` entry in the
decision ledger.

### `/orchestrator approve <job-id> <phase>`

Record an operator approval for a publish/remote/secret phase.  Valid
phases are `plan`, `publish`, `remote`, and `self_improve`.  Approval
is required before `publish-plan`, `self-improve run`, or a remote
worker can advance.  Each approval is stamped on the job and
appended to the decision ledger.

### `/orchestrator validate <job-id>`

Run the local validation gate (`hermes_cli.validation.ValidationRunner`)
against the workspace and persist a compact summary under
`$HERMES_HOME/orchestrator/validation.json`.  `publish-plan` honours
the `publish_blocked` flag — a failing critical check refuses the
plan emission.  The orchestrator records a `validate` entry in the
decision ledger.

### `/orchestrator publish <job-id>`

Mark a job as `published`.  Records a `publish` entry in the decision
ledger and stamps `published_at`.

### `/orchestrator publish-plan <job-id>`

Emit a publish-plan record describing what would be handed off to a
downstream publisher (github_publisher plugin, kanban dispatcher,
GitHub release, etc.).  Requires:

1. `/orchestrator approve <job-id> plan` has been called.
2. The most recent `/orchestrator validate <job-id>` (if any) did
   not mark the job `publish_blocked`.

The plan lives in `$HERMES_HOME/orchestrator/publish_plans.json` and
the job status bumps to `plan_ready` so listings reflect readiness.

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
a `kind` (`submit`, `resume`, `cancel`, `approve`, `validate`,
`publish`, `publish-plan`, `self-improve`, or anything later written
by the worker), and optional structured extras serialized as JSON.

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

### `/voice-capture status`

Show the current voice-capture mode plus a short history of changes
(persisted under `$HERMES_HOME/orchestrator/voice_capture.json`).

### `/voice-capture mode <mode>`

Switch the voice-capture mode.  Valid modes:

| Mode | Behaviour |
|---|---|
| `push_to_talk` | Mic captures only while a key is held. |
| `wake_word` | Hot-word listener gates dictation. |
| `driving_capture` | Always-on, hands-free; queues prompts for review. |
| `disabled` | Mic capture is off. |

The previous mode is appended to the history list so users can audit
the mode-switch trail.

### `/remote-worker status`

Show the local snapshot of registered remote workers.  When the
registry is empty (the default) the command surfaces a placeholder
pointing at `$HERMES_HOME/orchestrator/remote_workers.json` so users
can add entries by hand or via config.  Remote workers must be
approved per-job (`/orchestrator approve <job-id> remote`) before
they may pick up work.

### `/self-improve run <job-id>`

Stage a self-improvement-loop request for `<job-id>`.  Requires prior
`/orchestrator approve <job-id> self_improve`.  The loop itself is
invoked by the `self-improvement-loop` skill (or by the background
curator); this command only records the request so the loop knows
what job to target.  Requests live under
`$HERMES_HOME/orchestrator/self_improve.json`.

### `/profile build-github-history`

Refresh the local profile's GitHub-history snapshot.  The CLI surface
stamps a JSON record under
`$HERMES_HOME/orchestrator/profile_github_history.json`; a real
GitHub-history walk is wired by setting `profile.github_history.feed`
in `config.yaml` or by handing off to the `github_assistant` plugin.

The bare `/profile` form still prints the active profile name and
home directory — unchanged.

## Storage layout

```
$HERMES_HOME/orchestrator/
├── jobs.json                       # list[Job]
├── decision_ledger.json            # {job_id: [entry, …]}
├── ai_radar.json                   # {updated_at, source, note, …}
├── best_coding_tool_mission.json   # {mission, metrics, next_actions}
├── approvals.json                  # reserved for future per-phase index
├── validation.json                 # {job_id: {status_counts, checks, …}}
├── publish_plans.json              # {job_id: {created_at, artifacts, …}}
├── voice_capture.json              # {mode, updated_at, history}
├── remote_workers.json             # {workers: [{id, kind, url, …}]}
├── self_improve.json               # {job_id: [{ts, status, …}, …]}
└── profile_github_history.json     # {profile, built_at, source, note}
```

All writes go through an atomic temp-file rename so a Ctrl-C in the
middle of a write cannot leave a partial file.

## Gateway behaviour

The orchestrator-family canonical commands (`/orchestrate`,
`/orchestrator`, `/model-router`, `/decision-ledger`, `/ai-radar`,
`/best-coding-tool-mission`, `/voice-capture`, `/remote-worker`,
`/self-improve`) are registered `cli_only`.  This is deliberate:
Slack's app manifest caps slash commands at 50 per app, and each new
gateway-visible canonical bumps a high-value alias (`/btw`, `/bg`, `/q`)
off the manifest.  CLI parity is the current contract; gateway parity
is deferred.

The gateway dispatcher in
`gateway.run.HermesGateway._handle_orchestrator_slash` is wired and
ready — it calls the same `run_*` entry points in
`hermes_cli.orchestrator` via `asyncio.to_thread` and truncates output
longer than ~3800 characters to keep messaging adapters happy.  Because
the commands are `cli_only`, `is_gateway_known_command` returns False
for them and the dispatcher is dormant.  A future phase flips this on
by either:

* dropping `cli_only=True` from the CommandDef entries, or
* adding `gateway_config_gate="orchestrator.gateway_enabled"` so an
  operator can opt in by setting the config key truthy.

Either path picks up the existing handler automatically — no further
gateway code changes are required.

`/profile build-github-history` is reachable from the gateway because
`/profile` is gateway-visible by default; the subcommand dispatcher in
`gateway.run.HermesGateway._handle_profile_command` delegates to the
shared `run_profile` controller.

Per-platform admin gating (`allow_admin_from`, `user_allowed_commands`)
covers these commands without any additional configuration because
`is_gateway_known_command` reads directly from the central
`COMMAND_REGISTRY`.

## Tests

`tests/test_orchestrator_commands.py` covers:

* The CommandDef entries are present, well-formed, and discoverable.
* Each `run_*` entry point handles missing args, unknown subcommands,
  help payloads, and the success path.
* Submitting / resuming / cancelling / publishing jobs persists to
  disk and updates the decision ledger.
* `approve_phase` validates the phase name, persists the approval,
  and unblocks `publish_plan` / `self_improve_run`.
* `validate_job` writes a structured summary and `publish_plan`
  honours the `publish_blocked` flag.
* `voice_capture_status` / `set_voice_capture_mode` round-trip
  through the JSON file and track a bounded history.
* `remote_worker_status` returns a usable placeholder when the
  registry is empty and reflects manually-added entries.
* `self_improve_run` is gated by approval and persists request
  records.
* `profile_build_github_history` writes the snapshot file and
  `profile_github_history_status` reads it back.
* `model_router_explain` returns a deterministic route for the curated
  keyword set.
* `ai-radar update` and `best-coding-tool-mission status` write /
  read their respective JSON files without touching jobs or the
  ledger.

Run with:

```bash
python -m pytest tests/test_orchestrator_commands.py -q
```
