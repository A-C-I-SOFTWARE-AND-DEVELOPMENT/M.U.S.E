# Follow-up task snapshots

One file per follow-up task (`fu-<id>-<slug>.md`). Per the *Parallel
follow-up execution contract* in [`../../../CLAUDE.md`](../../../CLAUDE.md):

- **One writer per snapshot** — the agent that owns the task. Distinct
  filenames ⇒ no merge conflicts between parallel tasks.
- The orchestrator-owned index is [`../10_10_followups_ledger.md`](../10_10_followups_ledger.md);
  snapshots never edit it.
- A snapshot is the durable, resumable record of one task: intent, the exact
  files it may write, branch + base commit, validation results, PR, and
  residual risk. Copy [`_TEMPLATE.md`](_TEMPLATE.md) to start one.
