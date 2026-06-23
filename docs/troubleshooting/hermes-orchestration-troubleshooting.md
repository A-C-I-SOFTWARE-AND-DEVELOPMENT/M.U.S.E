# muse orchestration troubleshooting

The single-page symptom-to-fix table for everything in muse —
orchestration, mobile, voice, the Windows bridge, integrations,
disconnects, secrets.

> The orchestration-specific deep dive lives at
> [`../orchestration/troubleshooting.md`](../orchestration/troubleshooting.md).
> This page is the broader index across every surface, with the
> orchestration page linked at the top of each section.

---

## First, gather the obvious

```bash
muse doctor                          # general health
muse orchestrator status             # what's running
muse orchestrator status <job-id>    # one job in detail
muse kanban tail <task-id>           # streaming worker log
muse profile list                    # configured worker profiles
muse mcp status                      # MCP server health
muse gateway status                  # gateway / messaging
tail -f ~/.hermes/logs/agent.log       # raw log
```

Most problems are visible in `status` plus the tail of `agent.log`.
If they aren't, the answer is in the job's `ledger.jsonl`.

---

## Quick reference table

| Symptom | Most likely cause | Jump to |
|---------|-------------------|---------|
| Card stuck in `ready` forever | Unknown profile assignee | [Stuck in `ready`](#stuck-in-ready) |
| Card stuck in `todo` | Parent didn't reach `done` | [Stuck in `todo`](#stuck-in-todo) |
| Judge keeps failing | Worker model too weak, or criteria too vague | [Judge keeps failing](#judge-keeps-failing) |
| Approval notification missing | Gateway / cockpit reachability | [Approvals not arriving](#approvals-not-arriving) |
| Cockpit shows stale state | Subscription dropped after backend restart | [Cockpit stale state](#cockpit-stale-state) |
| Voice transcribed wrong | STT engine mismatch | [Voice issues](#voice-issues) |
| Driving mode won't auto-off | Motion sensor permission missing | [Voice issues](#voice-issues) |
| Wake word triggers on random sound | Sensitivity too high | [Voice issues](#voice-issues) |
| Windows bridge fails `host_unreachable` | OpenSSH stopped on Windows | [Windows bridge issues](#windows-bridge-issues) |
| Windows bridge fails `claude_not_found` | PATH issue for SSH user | [Windows bridge issues](#windows-bridge-issues) |
| GitHub write blocked | Repo not in `allowed_repositories` | [GitHub issues](#github-issues) |
| Supabase MCP won't start | `npx` not on PATH, token invalid | [Supabase issues](#supabase-issues) |
| Vercel deploy refuses | HIGH-risk auto-block | [Vercel issues](#vercel-issues) |
| `~/.hermes/.env` not readable | Permission bits wrong | [Secrets issues](#secrets-issues) |
| Suspect a leaked key | Rotate-and-audit playbook | [Secrets issues](#secrets-issues) |
| Job folder huge | Trace retention not configured | [Disk usage](#disk-usage) |
| Network drop mid-job | Reclaim + retry | [Disconnect recovery](#disconnect-recovery) |
| Phone lost / stolen | Revoke cockpit token | [Disconnect recovery](#disconnect-recovery) |
| Profile data feels stale | Refresh GitHub history | [Profile issues](#profile-issues) |
| Local model server crashes mid-job | OOM, timeout, server died | [Local model issues](#local-model-issues) |

---

## Stuck in `ready`

**Symptom.** A card sits in `ready` indefinitely. The dispatcher
never claims it.

**Most likely cause.** Unknown profile assignee. The orchestrator
picked a profile name (`researcher`, say) that doesn't exist on this
machine, and the dispatcher silently ignores unknown assignees — it
does not autocorrect.

**Diagnose.**

```bash
muse orchestrator status <job-id>    # → "assignee: researcher (no such profile)"
muse profile list                    # does NOT include "researcher"
```

**Fix.** Add the missing profile, or reassign the card:

```bash
muse profile create researcher --model nous:hermes-3-405b
muse kanban reassign <task-id> researcher --reclaim
```

Other causes (tenant mismatch, dispatcher not running) and detail in
[`../orchestration/troubleshooting.md#stuck-in-ready`](../orchestration/troubleshooting.md#stuck-in-ready).

---

## Stuck in `todo`

**Symptom.** A child card sits in `todo` even after its parents look
done.

**Cause.** One or more parents either isn't actually `done`, or
errored without writing completion. `todo → ready` requires every
parent at `done` (not `failed`, not `blocked`).

**Fix.** Find the broken parent and reclaim it, or force-complete:

```bash
muse kanban tail <parent-task-id>
muse kanban force-complete <parent-task-id> --reason "manual override"
```

Full notes at
[`../orchestration/troubleshooting.md#stuck-in-todo-never-promotes-to-ready`](../orchestration/troubleshooting.md#stuck-in-todo-never-promotes-to-ready).

---

## Judge keeps failing

**Symptom.** Card retries 2–3 times, judge fails every retry, then
escalates.

**Common causes.**

- Acceptance criteria too vague — sharpen the orchestrator skill's
  card body.
- Worker model too weak — upgrade the profile.
- Judge model too strict — try a peer-level judge instead of a
  higher-tier one.

**Fix.** Either reassign with a stronger model
(`muse kanban reassign T3 engineer-opus --reclaim`) or override
the judge with `muse kanban respond <task-id> approve
--override-judge` (logged in the ledger explicitly).

Full notes at
[`../orchestration/troubleshooting.md#judge-keeps-failing-the-same-card`](../orchestration/troubleshooting.md#judge-keeps-failing-the-same-card).

---

## Approvals not arriving

**Symptom.** Card is in `escalated` per
`muse orchestrator status` but the cockpit / gateway never pinged.

**Causes.**

- Gateway not running. `muse gateway status`.
- Cockpit unsubscribed for the job (custom subscription filter).
- Approval routed to a delivery target you forgot you configured.

**Fix.** Respond from any working surface (CLI, cockpit, gateway DM
— all share state):

```bash
muse kanban respond <task-id> approve
```

Full mobile notes at
[`../mobile/mobile-app-guide.md#disconnect-recovery`](../mobile/mobile-app-guide.md#disconnect-recovery).

---

## Cockpit stale state

**Symptom.** The Android cockpit shows yesterday's jobs and the
"latest" status doesn't update.

**Cause.** Long disconnect after a backend restart; the subscription
silently expired.

**Fix.**

1. **Pull-to-refresh** on the dashboard.
2. **Settings → Connection → Reconnect.**
3. If still stale, the gateway is down — restart it on the backend
   and pull-to-refresh again.

---

## Voice issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Hold-to-talk records, no turn appears | Gateway can't reach STT | Check `voice.stt.engine`; restart gateway. |
| Wrong transcript repeatedly | Wrong STT model size / engine | Try `whisper-server` with `medium.en`, or switch to Deepgram. |
| Driving mode won't disable on stop | Motion sensor permission off | Cockpit → **Settings → Permissions → Motion** → grant. |
| TTS cut off mid-sentence | `voice.tts.cap_seconds` hit | Increase, or read the queued long-form reply after the drive. |
| Wake word triggers on TV / random sound | Sensitivity too high | Lower `voice.wake_word.sensitivity` to ~0.5. |
| Voice command not matched | Wake-word audio quality | Re-record the wake-word sample, raise sensitivity, or hold-to-talk instead. |
| Audio uploaded but no turn appears | Network drop mid-upload | Cockpit retries automatically; manual retry from **Voice → Failed captures**. |

Full guide at
[`../voice/voice-first-user-guide.md#troubleshooting`](../voice/voice-first-user-guide.md#troubleshooting).

---

## Windows bridge issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `bridge: host_unreachable` | OpenSSH server stopped on Windows, firewall blocking 22 | `Get-Service sshd`; allow port 22; retry. |
| `bridge: claude_not_found` | Claude Code not on PATH for SSH user | Reinstall Claude Code with system-wide PATH or set `environment_config.claude_bin`. |
| Phase stuck `in_progress` for hours | UAC / interactive prompt blocking on Windows side | `muse kanban reclaim <task-id>`; run the same command in an interactive Windows shell to surface the prompt. |
| Output empty after completion | Workdir scope mismatch | Set `environment_config.workdir` explicitly; rerun. |
| `policy: HIGH-risk refused (sandbox=off)` | Policy rejects unsandboxed workdir | Narrow the workdir, or use a constrained Windows user. |

Full guide at
[`../remote/windows-claude-code-bridge-guide.md#troubleshooting`](../remote/windows-claude-code-bridge-guide.md#troubleshooting).

---

## GitHub issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `github: not configured` | Plugin not enabled or token missing | `muse plugin enable github_assistant`; check `~/.hermes/.env`. |
| `github: write blocked: repo not in allowed_repositories` | Defense-in-depth refusal | Add the repo to `github.allowed_repositories`; `/reload-skills`. |
| Tool returns 401 / 403 | PAT scope insufficient or expired | Regenerate PAT, update `~/.hermes/.env`, restart muse |
| Worker reports "I don't have a `github_create_issue` tool" | Toolset disabled in the worker profile | Profile's `enabled_toolsets` must include `github_assistant`, or remove from `disabled_toolsets`. |

Full guide at
[`../integrations/github-supabase-vercel-guide.md#troubleshooting`](../integrations/github-supabase-vercel-guide.md#troubleshooting).

---

## Supabase issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `mcp: supabase failed to start` | `npx` not on PATH | `which npx`; ensure Node is installed. |
| `mcp: supabase: 401` | Access token invalid / scope wrong | Rotate via Supabase Studio, update `~/.hermes/.env`. |
| `supabase: allow_destructive=false` refused | Second-fence refusal of `delete_*` / `reset_branch` | Set `supabase.allow_destructive: true` only if you mean it. |
| Project tools missing | `allowed_projects` excludes the one you want | Add to `allowed_projects`; restart. |

---

## Vercel issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `mcp: vercel failed to start` | Same as Supabase — Node / npx missing | Install Node; retry. |
| `vercel: production env write refused` | Second-fence refusal | Set `vercel.allow_production_env_writes: true` only if you mean it. |
| Build logs return empty | Wrong deployment id | `muse mcp call vercel list_deployments` to find the real id. |
| Deploy approved but didn't run | Worker failed silently in the publishing phase | `muse kanban tail <task-id>`; reclaim and retry. |

---

## Secrets issues

### `~/.hermes/.env` permission

```bash
ls -la ~/.hermes/.env
# Should be: -rw------- 1 you you ...
chmod 600 ~/.hermes/.env
```

### Suspect a leaked key

1. **Rotate at the provider first.** Anthropic / GitHub / Vercel /
   Supabase — invalidate the old token at the source.
2. **Update `~/.hermes/.env`** with the new key.
3. **Restart muse** `pkill hermes; hermes` (or restart the
   gateway service).
4. **Audit.** `grep -l <last-4-chars-of-old-key>
   ~/.hermes/jobs/*/ledger.jsonl`. The publishing layer redacts
   credentials; matches indicate a bug — open a security issue.

Full playbook at
[`../security/private-local-security-guide.md#disconnect--leak-recovery`](../security/private-local-security-guide.md#disconnect--leak-recovery).

---

## Disk usage

Job folders accumulate. Each card writes `input.md`, `output.md`,
and `trace.jsonl`.

```bash
du -sh ~/.hermes/jobs/* | sort -h | tail
muse orchestrator gc --dry-run    # preview
muse orchestrator gc              # actually GC
```

Configure retention in `~/.hermes/config.yaml`:

```yaml
orchestration:
  retention:
    completed_jobs_days: 30
    failed_jobs_days: 90
    ledger_compression: gzip
```

---

## Disconnect recovery

### Network drop mid-job

The backend keeps running. On reconnect, the cockpit / CLI resumes
streaming. If something's actually stuck, reclaim and retry:

```bash
muse kanban reclaim <task-id>
```

### Backend host restart

The dispatcher re-reads the ledger and resumes. `in_progress` cards
on the bridge are marked `failed` and retried (see
[Windows bridge issues](#windows-bridge-issues)).

### Phone lost / stolen

1. Revoke the cockpit token:
   ```bash
   muse gateway revoke-token <phone-device-id>
   ```
2. The phone never held API keys; only the bearer was on it. The
   conversation and job folders are on the backend.

---

## Profile issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `profile show github` says "no data yet" | Initial sync never ran | `muse profile sync github`. |
| Sync errors 401 / 403 | PAT scope insufficient | Regenerate PAT, update env. |
| Profile suggests wrong default branch | Convention changed | Re-sync; manually edit fact with `muse memory update`. |
| Unexpected memory appeared | Auto-derived from ambient observation | `muse memory rm <id>` — the curator respects deletions. |
| Sync is slow | Hundreds of repos | Lower `profile.github.history_window`. |

Full guide at
[`../profile/github-history-profile-guide.md#troubleshooting`](../profile/github-history-profile-guide.md#troubleshooting).

---

## Local model issues

Symptoms point to your local model server (llama.cpp / vLLM /
Ollama), not muse

| Symptom | Cause | Fix |
|---------|-------|-----|
| Workers fail with connection errors | Local model server crashed | Check the model server's own log. |
| Timeouts on long phases | muse timeout too short for the model | `providers.<local>.request_timeout: 600` in `~/.hermes/config.yaml`. |
| Server OOMs mid-job | Long-context cards push memory | Reduce `-c` on llama.cpp, or switch to a smaller quant. |
| Wrong model responded | Routing rule misfired | `jq 'select(.kind == "spawn") | {card, profile, model, route_match}' ledger.jsonl`. |

Air-gapped recipes at
[`../orchestration/private-local-mode.md`](../orchestration/private-local-mode.md).

---

## Self-help one-liners on the ledger

The ledger is the source of truth. Useful queries:

```bash
# how many escalations did this job hit?
jq -c 'select(.kind == "escalate")' ledger.jsonl | wc -l

# which profile cost how many tokens?
jq -r 'select(.kind == "model_call") | "\(.profile) \(.tokens_in) \(.tokens_out)"' ledger.jsonl \
  | awk '{i[$1]+=$2; o[$1]+=$3} END {for (p in i) print p, i[p], o[p]}'

# what tools got called, by frequency?
jq -r 'select(.kind == "tool_call") | .tool' ledger.jsonl | sort | uniq -c | sort -rn

# every gate failure
jq -c 'select(.kind == "gate" and (.judge // "" | startswith("fail") or .schema != "ok"))' ledger.jsonl

# what was the orchestrator's plan?
jq -r 'select(.kind == "model_call") | .response_text' \
  ~/.hermes/jobs/<job-id>/cards/T0/trace.jsonl | less
```

---

## Stop everything

```bash
muse orchestrator cancel <job-id>      # one job
muse orchestrator cancel --all         # every active job
muse kanban reclaim --all-running      # detach in-flight workers
muse orchestrator panic-stop           # nuclear: kill dispatcher + workers
```

`panic-stop` leaves SQLite intact so you can restart cleanly. Reach
for it twice in a week and something is misconfigured upstream —
open an issue with the job folder attached.

---

## Still stuck

1. Reproduce on a fresh job. Many "weird" failures are stale state
   from an aborted previous run.
2. Attach the job folder (tar / zip the directory).
3. Include `muse doctor` output.
4. Include the exact prompt and a `muse profile list` snapshot.
5. Redact secrets before attaching anything; the ledger should
   already be clean but double-check.

---

## See also

- [`../orchestration/troubleshooting.md`](../orchestration/troubleshooting.md)
  — the orchestration-specific deep dive (longer, with more
  ledger queries).
- [`../orchestration/faq.md`](../orchestration/faq.md) — conceptual
  questions (not failures).
- [`../mobile/mobile-app-guide.md`](../mobile/mobile-app-guide.md)
  — mobile-specific recovery.
- [`../voice/voice-first-user-guide.md`](../voice/voice-first-user-guide.md)
  — voice-specific recovery.
- [`../remote/windows-claude-code-bridge-guide.md`](../remote/windows-claude-code-bridge-guide.md)
  — Windows bridge recovery.
- [`../security/private-local-security-guide.md`](../security/private-local-security-guide.md)
  — secrets and leak recovery.
- [`../integrations/github-supabase-vercel-guide.md`](../integrations/github-supabase-vercel-guide.md)
  — integration-specific recovery.
