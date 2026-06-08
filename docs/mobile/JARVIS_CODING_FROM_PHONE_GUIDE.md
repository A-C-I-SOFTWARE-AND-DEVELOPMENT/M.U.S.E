# Coding from your phone with MUSE

You can drive real software work — plan a change, run a coding agent
against a repo, and review the resulting PR — entirely from the mobile
cockpit. The phone never runs the coding agent itself; it dispatches the
work to a worker lane on your backend and watches it. This keeps the
powerful part (writing to a repo, pushing) behind the owner gate.

> Background reading: the orchestration
> [getting-started](../orchestration/getting-started.md) and the
> [prompt-to-PR demo](../orchestration/prompt-to-pr-demo.md).

---

## The flow at a glance

```
phone: "build packet for X"        → MUSE plans (no execution)
phone: dispatch job (execute lane) → owner gate: "Yes, with authorization."
backend: worker (Codex / Claude)   → works on an isolated feature branch
backend: validation gates + ledger → opens a draft PR
phone: review the PR, approve/merge → owner gate again for merge
```

## 1. Plan first — a builder packet

Ask in chat: *"MUSE, builder mode. Prepare a build packet for: &lt;describe
the change&gt;."* MUSE produces a **bounded work packet** — intent, risk
class, allowed files, verification steps, and a rollback plan — **without
executing anything**. Planning and review never require the gate; only
execution does. (The packet model is the same one the
[`/jarvis-packetize`](../../skills/jarvis-prime/) skill produces.)

## 2. Dispatch the work

From the **Jobs** screen (or chat) dispatch the packet to a worker lane:

- **Codex lane** / **Claude Code lane** (`ClaudeExecuteWorker`) — real
  agentic coding against the repo.
- **Local planner / handoff lanes** — non-executing; these dispatch
  directly without the gate.

Pick your builder/reviewer defaults in Settings (`PreferredBuilder`,
`PreferredReviewer`).

## 3. The double gate on execution

Running a coding agent against your repo is the most powerful thing the
cockpit can trigger, so it is **double-gated** in
`gateway/cockpit/handlers.py` (`jobs_dispatch` / `job_run`):

1. **Owner phrase.** The execute phase is granted only when you reply with
   the exact authorization phrase:

   ```
   Yes, with authorization.
   ```

   Nothing weaker authorizes it (`hermes_cli/jarvis_prime/owner_auth.py`).

2. **Loopback only.** Agentic execution is **refused on a non-loopback
   cockpit** — if the backend was started with `--allow-external`, the
   execute lanes are disabled entirely
   (`configure_runtime(allow_remote_execute=...)`). Drive coding only over
   a loopback/tunnelled connection.

Both must pass. A missing phrase returns *"owner approval required to run
an execute lane"*; an externally-bound cockpit returns *"agentic execution
is disabled on a non-loopback cockpit."*

## 4. What the worker does (and the safety floor)

- Work happens on an **isolated feature branch — never `main`**.
- Validation gates run (build/test/review) before anything is proposed.
- Every decision is written to the **decision ledger**.
- The worker **opens a draft PR**; it does not merge.
- Reverting the branch / dropping the PR fully undoes the work. No schema
  or irreversible migration without a separate owner gate.

See [`../jarvis/JARVIS_HIGH_AUTONOMY_CODING_MODE.md`](../jarvis/JARVIS_HIGH_AUTONOMY_CODING_MODE.md)
for how autonomy scoping interacts with this.

## 5. Review the PR from the phone

Watch the job's task graph and ledger live, read the diff summary, and
when you're satisfied, **approve the merge** — which is itself an
owner-gated action (`main`-branch merge). Until then the PR sits as a
draft.

## 6. Heavier coding: the Windows / Claude Code bridge

For full Claude Code sessions driven from the phone against a desktop
workstation, use the remote bridge:

- [`../remote/windows-claude-code-bridge-guide.md`](../remote/windows-claude-code-bridge-guide.md)
  — the user-facing guide.
- [`../remote/claude-code-windows-bridge.md`](../remote/claude-code-windows-bridge.md),
  [`../remote/windows-agent-setup.md`](../remote/windows-agent-setup.md),
  [`../remote/secure-tunnel-options.md`](../remote/secure-tunnel-options.md).

## 7. Lightweight handoff (no backend execution)

If you'd rather hand a prompt to ChatGPT/Codex on the phone and paste the
result back, the clipboard-handoff workflow predates the cockpit and still
works: [`../hermes-local-orchestrator.md`](../hermes-local-orchestrator.md).
The **clipboard handoff** toggle is in Settings.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "owner approval required to run an execute lane" | No / wrong phrase | Reply exactly `Yes, with authorization.` |
| "agentic execution is disabled on a non-loopback cockpit" | Backend bound with `--allow-external` | Restart `hermes cockpit serve` on loopback; tunnel instead of binding wide |
| Job stuck in `queued` | No worker available for the lane | Check `hermes orchestrator status`; configure the builder/reviewer |
| PR never appears | Validation gate failed | Read the ledger / job detail; fix and re-dispatch |
