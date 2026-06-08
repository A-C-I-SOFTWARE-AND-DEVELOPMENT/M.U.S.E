# Demo — Prompt to PR

A complete walkthrough: one English sentence in, one draft GitHub PR
out, every step auditable. Roughly 6 minutes of human time, plus
however long the agents take.

## What we're going to do

> Goal: *"Audit this repo for unused imports, dead code, and stale
> dependencies. Open a draft PR with the cleanup."*

The orchestrator will fan this out into:

```
T1 (researcher) — find unused imports / dead code
T2 (researcher) — find stale / vulnerable dependencies
T3 (engineer)   — apply the changes from T1 and T2  [parents: T1, T2]
T4 (reviewer)   — sanity-check the diff             [parents: T3]
T5 (engineer)   — open a draft PR via github_assistant [parents: T4]
```

T1 and T2 run in parallel. T3 starts when both are done. T4 gates
T5. T5 publishes.

## Prerequisites

- A clone of the repository you want to audit. M.U.S.E. will run
  inside it.
- The `github_assistant` plugin enabled, with a fine-grained PAT
  scoped to that repo, write access allowed for *that one repo only*.
  See [docs/github-integration.md](../github-integration.md) for the
  exact config.
- At least three profiles configured — `researcher`, `engineer`,
  `reviewer`. If you only have `default`, the orchestrator will
  collapse the fan-out into a serial run on `default`; the demo
  still works, it just won't parallelize. See
  [worker-adapters.md](worker-adapters.md) for the profile recipes.

Confirm:

```bash
muse profile list | grep -E "researcher|engineer|reviewer"
muse config get github.enabled        # → true
muse config get github.allow_writes   # → true
muse config get github.allowed_repositories
```

## Step 1 — Kick the job off

From inside the repo:

```bash
bash scripts/hermes-orchestrate.sh \
  "Audit this repo for unused imports, dead code, and stale dependencies. Open a draft PR with the cleanup." \
  --deliver pr \
  --pr-draft
```

You'll see the job id in stdout:

```
✓ job_2026_05_23_a4f7c1 created
✓ orchestrator profile: default
✓ decomposing… (Sonnet, est. ~$0.02)
```

Equivalent inside `muse`:

```
/orchestrate Audit this repo for unused imports, dead code, and stale dependencies. Open a draft PR with the cleanup.
```

## Step 2 — Watch the decomposition

```bash
muse orchestrator status job_2026_05_23_a4f7c1
```

```
job_2026_05_23_a4f7c1   running   5 cards   3 ready, 0 done
  T1 [ready]    researcher  unused-imports scan
  T2 [ready]    researcher  dependency-staleness scan
  T3 [todo]     engineer    apply cleanup           parents: T1,T2
  T4 [todo]     reviewer    sanity-check diff       parents: T3
  T5 [todo]     engineer    open draft PR           parents: T4
```

The dispatcher picks up T1 and T2 immediately. T3 stays in `todo`
until both parents complete; the dependency engine promotes it
automatically.

## Step 3 — Follow one card

```bash
muse kanban tail T1
```

You'll see the worker's tool calls, model responses, and
intermediate findings streamed live. Every line is also written to
`~/.hermes/jobs/job_2026_05_23_a4f7c1/cards/T1/trace.jsonl` so you
can replay later.

## Step 4 — Validation kicks in

When T1 completes, the gate runs:

```
T1 → gate: schema=ok policy=LOW judge=pass(0.92) → done
T2 → gate: schema=ok policy=LOW judge=warn(0.58) "stale-dep list missing version pins"
       ↳ retry on researcher with sharper acceptance criteria
T2.retry1 → gate: schema=ok policy=LOW judge=pass(0.89) → done
```

T2's first attempt failed the judge — the orchestrator re-spawned
the same profile with the judge's feedback inlined. You didn't have
to touch anything.

## Step 5 — Engineer card runs

T3 is auto-promoted to `ready`, the dispatcher claims it for the
`engineer` profile, and the worker writes the actual diff. Because
`engineer` runs in a sandboxed docker environment, the changes land
on a worktree, not your main checkout.

```
T3 → engineer
  reads T1.output: 47 unused imports, 3 dead functions
  reads T2.output: 12 stale deps, 2 with known CVEs
  applies edits to worktree
  runs scripts/run_tests.sh
  ✓ all tests pass
  produces diff (4 files, +0 -78)
```

## Step 6 — Reviewer card runs

```
T4 → reviewer
  reads T3.diff
  checks: behavior preserved? tests still cover removed code? deps still resolve?
  judge: pass(0.94) "diff is minimal, no behavior changes, deps resolve"
```

## Step 7 — Publishing card

T5 is the publishing step. It's the *only* card that goes through
the HIGH-risk policy gate because it mutates GitHub:

```
T5 → engineer
  builds PR body from T1/T2 reports + T3 diff
  classify: HIGH (mutation on external service: github)
  ESCALATE: pull-request open?
    repo:   echerd27-design/hermes-agent
    branch: hermes/audit-2026-05-23
    title:  "chore: remove unused imports, dead code, stale deps"
    body:   <preview>
```

You respond:

```bash
muse kanban respond T5 approve
```

(Or hit the green check on the Android cockpit, or reply `approve`
in your gateway DM — same backend.)

T5 calls `github_create_pull_request` via the `github_assistant`
plugin. The PR is created in draft mode because of `--pr-draft`. The
URL is written to `summary.md` and posted to your gateway DM.

## Step 8 — Final summary

```bash
cat ~/.hermes/jobs/job_2026_05_23_a4f7c1/summary.md
```

```markdown
# Audit summary

Job: job_2026_05_23_a4f7c1
Started: 2026-05-23 14:02:11 UTC
Finished: 2026-05-23 14:11:47 UTC
Duration: 9m 36s

## Results
- 47 unused imports removed
- 3 dead functions removed
- 12 dependencies updated (2 security advisories closed)
- PR: https://github.com/echerd27-design/hermes-agent/pull/142 (draft)

## Cards
- T1 researcher  done   65s    unused-imports scan
- T2 researcher  done   2m 18s dependency-staleness scan (1 retry)
- T3 engineer    done   3m 02s apply cleanup
- T4 reviewer    done   1m 51s sanity-check diff
- T5 engineer    done   2m 19s open draft PR (1 human approval)

## Costs (estimated)
- Model usage: $0.18
- Human approvals: 1
```

## What you can replay

The job folder is the source of truth. Useful follow-ups:

- **Replay a card** with a different model:

  ```bash
  muse orchestrator replay job_2026_05_23_a4f7c1 --card T2 --model anthropic:claude-opus
  ```

- **Diff two runs** of the same prompt across model providers:

  ```bash
  diff ~/.hermes/jobs/job_a/ledger.jsonl ~/.hermes/jobs/job_b/ledger.jsonl
  ```

- **Reuse the plan** as a template:

  ```bash
  muse orchestrator template save job_2026_05_23_a4f7c1 --name repo-audit
  muse orchestrator template run repo-audit --in ../other-repo
  ```

## Variations

### "Just give me the report — don't open a PR"

```bash
bash scripts/hermes-orchestrate.sh "Audit this repo for unused …" --deliver file
```

Drops the report to `~/.hermes/jobs/<id>/output/report.md`, no PR
step, no GitHub credentials touched.

### "Open the PR against a fork, not the upstream"

```bash
bash scripts/hermes-orchestrate.sh "Audit …" \
  --deliver pr \
  --pr-target your-fork/hermes-agent \
  --pr-base main \
  --pr-head hermes/audit
```

### "Stop asking me; just do it" (use carefully)

```bash
bash scripts/hermes-orchestrate.sh "Audit …" --autonomy yolo
```

`--autonomy` maps to the council's autonomy mode
(`default` / `strict` / `yolo`). `yolo` skips the HIGH-risk
escalation gate. Only use it for jobs whose worst case you've
already inspected. The audit trail still records the mutation, you
just don't get asked first.

## What can go wrong

Most failures fall into one of three buckets:

- **Unknown profile assignee** — the orchestrator picked a profile
  name that doesn't exist on this machine. The card sits in `ready`
  forever. Fix with `muse kanban reassign <task-id> <profile>` or
  by editing `~/.hermes/config.yaml` to add the missing profile.
  See [troubleshooting.md#stuck-in-ready](troubleshooting.md#stuck-in-ready).
- **Judge keeps failing** — the worker model is too weak for the
  card. Reassign with a stronger model:
  `muse kanban reassign T3 engineer-opus --reclaim`.
- **GitHub write blocked** — `allow_writes: false` or the target
  repo isn't in `allowed_repositories`. The plugin refuses cleanly
  and the orchestrator surfaces the error. Edit
  `~/.hermes/config.yaml` and `/reload-skills`.

The full list lives in [troubleshooting.md](troubleshooting.md).
