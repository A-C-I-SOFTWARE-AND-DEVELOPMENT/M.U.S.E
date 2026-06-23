# Troubleshooting

muse Orchestration has a lot of moving parts, but failures cluster
into a small number of patterns. This is the field guide. Open a
ticket only after you've checked the matching section here.

## First, gather the obvious

```bash
muse doctor                          # general health
muse orchestrator status             # is anything actually running?
muse orchestrator status <job-id>    # what state is each card in?
muse kanban tail <task-id>           # what is the worker actually doing
tail -f ~/.hermes/logs/agent.log       # raw log
```

Most problems are visible in `status` plus the tail of `agent.log`.
If they aren't, the answer is in the job's `ledger.jsonl`.

## Stuck in `ready`

**Symptom:** A card sits in `ready` indefinitely. The dispatcher
never claims it.

**Cause #1: unknown assignee.** The orchestrator picked a profile
name that doesn't exist on this machine. The dispatcher silently
ignores unknown assignees — it does *not* error, autocorrect, or
fall back.

```bash
# Confirm:
muse orchestrator status <job-id>      # → "assignee: researcher (no such profile)"
muse profile list                      # → does NOT include "researcher"
```

**Fix:** either add the missing profile, or reassign the card:

```bash
muse profile create researcher --model nous:hermes-3-405b
muse kanban reassign <task-id> researcher --reclaim
```

**Cause #2: tenant mismatch.** If `HERMES_TENANT` is set, the
dispatcher only spawns workers whose profile and the card share a
tenant. Check the ledger for the card's `tenant` field.

**Cause #3: dispatcher not running.** Check `muse orchestrator
status`. If it says `dispatcher: not running`, restart the daemon
or restart muse

## Stuck in `todo` (never promotes to `ready`)

**Symptom:** A child card sits in `todo` even after all its parents
look done.

**Cause:** One or more parents either isn't actually `done`, or it
errored without writing a completion record. `todo → ready`
promotion requires every parent to reach `done` (not `failed`, not
`blocked`).

```bash
muse orchestrator status <job-id>    # check parent states
muse kanban tail <parent-task-id>    # what happened to the parent
```

**Fix:** complete or reclaim the stuck parent. If the parent is
genuinely failed and you want to proceed anyway:

```bash
muse kanban force-complete <parent-task-id> --reason "manual override"
```

This writes a synthetic completion to the ledger (with the manual
override tag) and lets the children promote.

## Worker keeps hallucinating cards / ids

**Symptom:** Worker calls `kanban_complete(created_cards=[...])`
with ids that don't exist. The completion is rejected by the
schema gate.

**Cause:** The model is making up plausible-looking ids instead of
reading them out of the actual `kanban_create` return values.

**Fix:** in priority order:

1. Try a stronger model for that profile:
   `muse profile model engineer anthropic:claude-opus`, then
   `muse kanban reclaim <task-id>`.
2. Sharpen the playbook. If you wrote a custom orchestrator skill,
   make the "store the returned id, don't invent" rule explicit.
3. Re-spawn with a temperature reduction
   (`muse profile config engineer temperature 0.0`).

The dashboard's drawer flags hallucination warnings on cards where
this happens. The audit trail persists even after recovery.

## Judge keeps failing the same card

**Symptom:** Card retries 2–3 times, judge fails every retry with
similar reasons, then escalates to you.

**Causes & fixes:**

- **Acceptance criteria too vague.** If your orchestrator skill
  produces cards with hand-wavy bodies ("clean up the code"), the
  judge can't tell pass from fail. Make the orchestrator emit
  measurable acceptance criteria (e.g. "all tests still pass after
  the change; no public API removed").
- **Wrong worker model.** A 7B model writing a code review for a
  20-file diff is not going to pass a competent judge. Upgrade
  the worker or downgrade the card's scope.
- **Judge model too strict.** If you used the strongest available
  model as the judge, it may reject reasonable output. Try a peer
  model rather than a higher one.

If you intentionally want the output: `muse kanban respond
<task-id> approve --override-judge` writes an explicit override to
the ledger.

## Card escalates and you're not getting the notification

**Symptom:** Card is in `escalated` per `muse orchestrator status`
but no notification arrives on phone / gateway.

**Causes:**

- Gateway is not running. `muse gateway status` should show
  active.
- The Android cockpit isn't subscribed to events for this job. The
  cockpit subscribes to `jobs/*` by default but custom subscriptions
  might filter it out — check **Settings → Notifications** in the
  app.
- The escalation routed to a delivery target you've forgotten you
  configured. Check `~/.hermes/jobs/<job-id>/plan.json` →
  `delivery_targets`.

**Fix:** respond from any working surface (CLI works, cockpit
works, gateway DM works). All routes write to the same kanban
state.

## "No such profile" on a profile you swear you configured

**Symptom:** `muse profile list` doesn't show a profile you just
added to `~/.hermes/config.yaml`.

**Cause:** muse hasn't picked up the config change yet.

**Fix:**

```bash
/reload-skills      # inside muse
# or restart the process:
exit && muse
```

If it still doesn't show, you probably have a YAML syntax error.
Run `muse config validate` to see exactly where.

## Plugin tools missing inside a worker

**Symptom:** Worker reports "I don't have a `github_create_issue`
tool" even though the plugin is installed.

**Checklist:**

1. `muse config get github.enabled` → must be `true`.
2. The worker's profile must have `github_assistant` in
   `enabled_toolsets` (or not in `disabled_toolsets`).
3. The token file at `~/.hermes/.env` must contain
   `GITHUB_PERSONAL_ACCESS_TOKEN=...`.
4. For write actions, `github.allow_writes: true` and the repo
   under `github.allowed_repositories`. The plugin refuses writes
   silently from the tool's perspective.

The plugin logs token-redacted errors. Check `agent.log` for
`github_assistant ...`.

## Local model server keeps disconnecting mid-job

**Symptom:** Workers fail with connection errors to your local
model server.

**Causes & fixes:**

- **OOM on the model server.** Long-context cards push memory.
  Reduce `-c` (context) on llama.cpp, or switch to a smaller
  quant.
- **Timeout too short.** Set `providers.<local>.request_timeout:
  600` in `~/.hermes/config.yaml`. The default is fine for cloud
  models but a local 70B can take longer.
- **Server crashed.** Check the model server's own log. The
  orchestrator can't tell the difference between a slow server
  and a dead one.

## Job folder grows huge

Each card writes `input.md`, `output.md`, `trace.jsonl`. For long
runs this adds up.

```bash
muse orchestrator gc                # GC completed jobs older than N days
muse orchestrator gc --dry-run      # preview
```

Configure retention in `~/.hermes/config.yaml`:

```yaml
orchestration:
  retention:
    completed_jobs_days: 30
    failed_jobs_days: 90
    ledger_compression: gzip   # gzip old ledgers
```

## Android cockpit shows stale state

The cockpit polls `/v1/orchestrator/status` and subscribes to
`/v1/events`. If the gateway restarted but the cockpit didn't
reconnect, you can see stale rows.

**Fix:** pull-to-refresh on the dashboard, or **Settings →
Connection → Reconnect**.

## "Why did this card use Opus instead of Sonnet?"

Open the ledger:

```bash
jq 'select(.kind == "spawn") | {card, profile, model, route_match}' \
  ~/.hermes/jobs/<job-id>/ledger.jsonl
```

The `route_match` field tells you which routing rule fired (or
`default` if none did).

## "Why did the orchestrator decompose this way?"

The full reasoning is in
`~/.hermes/jobs/<job-id>/cards/T0/trace.jsonl` (T0 is the
orchestrator's own card — it completed itself when it returned the
plan).

```bash
jq -r 'select(.kind == "model_call") | .response_text' \
  ~/.hermes/jobs/<job-id>/cards/T0/trace.jsonl | less
```

Save the prompt + plan pair when you find a decomposition you want
to replicate — see `muse orchestrator template save`.

## I want to abort everything, right now

```bash
muse orchestrator cancel <job-id>         # one job
muse orchestrator cancel --all            # every active job
muse kanban reclaim --all-running         # also detach any in-flight workers
```

This writes `cancelled` to the ledger and lets workers shut down
on their next checkpoint. To kill workers harder:

```bash
muse orchestrator panic-stop
# kills the dispatcher, every worker, leaves SQLite intact
```

`panic-stop` is the seatbelt. If you reach for it twice in a week,
something is misconfigured upstream — open an issue with the job
folder attached.

## Self-help by reading the ledger

The ledger is the source of truth. Useful one-liners:

```bash
# how many escalations did this job hit?
jq -c 'select(.kind == "escalate")' ledger.jsonl | wc -l

# how much did each profile cost?
jq -r 'select(.kind == "model_call") | "\(.profile) \(.tokens_in) \(.tokens_out)"' \
  ledger.jsonl | awk '{i[$1]+=$2; o[$1]+=$3} END {for (p in i) print p, i[p], o[p]}'

# what tools got called, by frequency?
jq -r 'select(.kind == "tool_call") | .tool' ledger.jsonl | sort | uniq -c | sort -rn

# show every gate failure
jq -c 'select(.kind == "gate" and (.judge | startswith("fail") or .schema != "ok"))' ledger.jsonl
```

## Still stuck

1. Reproduce on a fresh job. Many "weird" failures are stale
   state from an aborted previous run.
2. Attach the job folder to the issue (it's mostly text, tar it).
3. Include `muse doctor` output.
4. Include the exact prompt and a `muse profile list` snapshot.

[FAQ](faq.md) covers common conceptual questions that aren't
exactly failures.
