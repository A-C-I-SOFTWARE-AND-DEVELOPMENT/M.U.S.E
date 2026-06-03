# JARVIS Learning Dataset Pipeline

JARVIS turns its day-to-day work — coding tasks, research answers, evidence
checks, mobile actions, worker reviews, even failures — into a
**high-quality, source-backed dataset** for future fine-tuning, preference
training, skill creation, and model evaluation. The pipeline is built so it
**only ever stores validated traces**, **never stores secrets or raw
chain-of-thought**, and **requires owner approval** before any example is
exportable.

It is an *extension* of systems Hermes already ships — it does not
re-implement trajectory capture, redaction, the research vault, the
verification gates, or the owner-approval queue.

## What it reuses

| Need | Reused module |
|---|---|
| Trajectory capture (ShareGPT JSONL) | `agent/trajectory.py`, `trajectory_compressor.py` |
| Secret / private-key / token / PII redaction | `agent/redact.py` (`redact_sensitive_text`) |
| Chain-of-thought detection | `agent/trajectory.py` (`<think>` / `<REASONING_SCRATCHPAD>` handling) |
| Provenance + citations | `hermes_cli/jarvis_prime/research_vault.py`, `memory_tree.MemorySource` / `SourceTrust` |
| Quality gates | `hermes_cli/jarvis_prime/gates.py` (`run_gate_summary`) |
| Owner approve/reject + cockpit owner phrase | `gateway/cockpit/handlers.py` (`approvals_decide`), `owner_auth.AUTHORIZATION_PHRASE` |
| Local JSONL store pattern (atomic, `0o600`) | `research_vault.ResearchVault` |

## Record types (`TraceType`)

- `coding_task_trace`
- `research_answer_trace`
- `evidence_verification_trace`
- `mobile_action_trace`
- `worker_review_trace`
- `failed_attempt_trace`
- `user_approved_skill_trace`

## Filters (enforced at write time)

`DatasetStore.add_candidate` runs every filter and **refuses to store**
(`RejectedTrace`) anything that fails:

1. **No secrets / private keys / tokens** — every string field is run through
   `redact_sensitive_text(force=True)`; a residual-secret guard rejects
   anything that survives.
2. **No raw chain-of-thought** — `<think>…</think>` and
   `<REASONING_SCRATCHPAD>…</…>` blocks are stripped; an unclosed scratchpad
   is rejected outright.
3. **No unlicensed bulk-scraped content** — large uncited blobs from
   untrusted sources are refused.
4. **No failed patch unless labeled** — a `failed_attempt_trace` must carry
   the `negative_example` label or it is refused.

## Quality gates (the labels every example carries)

Mirrors the JARVIS verification gates — `tests_passed`,
`citations_verified`, `owner_approved`, `reviewer_passed`,
`rollback_available`. A non-negative example must satisfy the gates required
for its type before it can be exported. `QualityGates.from_gate_summary`
derives these by running the real `gates.run_gate_summary`.

## Lifecycle

```
ingest/build → PENDING ──owner approve (gated)──► APPROVED ──export──► EXPORTED
                   └──────owner reject──────────► REJECTED
```

Only **validated** traces are stored (`PENDING`). Only **owner-approved**,
gate-passing traces (and labeled negatives) are exported. The owner gate
requires the exact phrase `Yes, with authorization.` on approve — both the
cockpit endpoint and the CLI enforce it; it is never bypassed.

## Export formats

- `jsonl` — approved traces with content + provenance + quality labels.
- `preference` — `{chosen, rejected}` pairs (a passing positive vs. its
  `negative_example` sibling on the same `task_key`).
- `eval` — eval cases from research/evidence traces (carry citations).
- `skill` — skill candidates from `user_approved_skill_trace`.

## Storage

`${HERMES_HOME:-~/.hermes}/jarvis_prime/learning_dataset.jsonl` — local,
atomic writes, `0o600`. No secrets, no chain-of-thought, no private keys.

## Surfaces

### CLI

```
python -m hermes_cli.jarvis_prime learning list [--json]
python -m hermes_cli.jarvis_prime learning ingest-trajectory <path.jsonl>
python -m hermes_cli.jarvis_prime learning approve <id> --phrase "Yes, with authorization."
python -m hermes_cli.jarvis_prime learning reject <id>
python -m hermes_cli.jarvis_prime learning export --format jsonl|preference|eval|skill --out <file>
```

### Cockpit gateway (mobile cockpit + any client)

- `GET  /v1/cockpit/learning` — list candidates as provenance-first cards.
- `POST /v1/cockpit/learning/{id}` — approve (owner phrase required) / reject.
- `GET  /v1/cockpit/learning/export` — exportable counts per format
  (read-only; never streams the raw payload).

### Android cockpit

The **Learning** tab inside the **Approvals** screen lists pending
candidates with trace type, source, citation count, and the quality gates
they have cleared, plus Approve / Reject. Approve routes through the same
owner-gate ceremony as every other cockpit approval (the app submits the
owner phrase only after the on-device confirmation; the gateway still
verifies it server-side).

## Ingest bridges

`hermes_cli/jarvis_prime/learning_ingest.py`:

- `from_trajectory_file(path, store, quality=…)` — reads a
  `save_trajectory`-format JSONL; completed runs become
  `coding_task_trace`, failed runs become `failed_attempt_trace`
  auto-labeled `negative_example`.
- `from_research_artifact(artifact, store, question=…, …)` — turns a
  Research Vault artifact into a `research_answer_trace` /
  `evidence_verification_trace` carrying its citation + evidence strength as
  provenance.

## Tests

- `tests/hermes_cli/test_learning_dataset.py` — filters, negative-example
  rule, quality gates, owner approval, exports, persistence.
- `tests/hermes_cli/test_learning_ingest.py` — trajectory + research ingest.
- `tests/gateway/test_cockpit_learning.py` — list / decide (owner phrase) /
  export endpoints.
- `apps/android/.../learning/LearningRepositoryTest.kt` — gateway-backed
  load + owner-gate decide.
