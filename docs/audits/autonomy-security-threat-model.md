# Autonomy & Security Threat Model

Covers the new surfaces introduced this sprint (output compaction, credential
scrub, raw log, background-learner scaffold) and the gates that keep them safe.

## 1. Tool output → model context

| Threat | Mitigation |
|---|---|
| Secret in tool output reaches the model/provider | `scrub_credentials` runs **before** compaction in both tool paths (`tools/tokenjuice/scrub.py`). Key=value / Bearer / api_key / token / password / private-key patterns → `…*[REDACTED]`. |
| Compaction destroys evidence needed to debug | Full **pre-scrub** raw is written to an append-only raw log (`raw_log.py`) before scrub/compact; existing L2 sandbox persistence still keeps a re-readable copy. |
| Compaction corrupts/empties a result, hiding errors | **Fail-open**: any exception returns the original (scrubbed) text. **Pass-through**: tiny/incompressible/`skip_tools` outputs untouched. **Failure-aware**: on non-zero exit, larger head/tail is preserved. |
| Secrets written to disk via raw log | Raw log path is **gitignored**, local-first, session-scoped, and **never auto-read into context** (debug-only). Documented; rotation/retention is a ticket. |
| Prompt injection in tool output triggers actions | Compaction never executes content; it only filters/trims text. It cannot create memory/skills/cron. Injection defense remains upstream of the model as today. |

## 2. Raw-output log

- Location: `~/.hermes/tool-raw/<session>/<tool_use_id>.log` (configurable),
  gitignored. Pre-scrub content for fidelity.
- Access: written by the tool loop only; read only by an explicit debug command
  (future). Not surfaced to the model automatically.
- Disable: `tool_output.compaction.preserve_raw: false`.

## 3. Background-learner scaffold (inert this sprint)

The queue enforces an **allowlist at enqueue time** and runs **dry-run only**:

**Allowed kinds** (safe, local, read-mostly): `index_local_files`,
`summarize_session`, `extract_candidate_memory`, `update_embeddings`,
`refresh_integration_metadata`, `run_local_benchmark`, `evaluate_model_routing`,
`scan_outdated_deps`, `propose_skill`, `propose_code_patch`, `build_research_digest`.

**Disallowed without explicit approval** (rejected at enqueue): `send_message`,
`send_email`, `send_sms`, `change_production_code`, `install_package`,
`spend_money`, `access_new_account`, `exfiltrate_data`,
`create_external_schedule`, `modify_secret`, `auto_merge_self_update`,
`destructive_shell`.

Gates: per-job `permission_scope`, `dry_run=True` default, idle detection before
run, rate limit + resource budget (ticket), cancellation, audit log. **No job
executes an external effect this sprint** — the runner logs intended actions
only. High-risk kinds require a human approval token (not yet issuable → always
deferred).

## 4. Self-update (ticket, not built)

Any self-update must be PR/patch/proposal-based: detect gap → write proposal →
branch + patch → run tests → run evals → security review → summarize → **require
human approval before merge/activate**. Never silent. Policy doc: ticket
`docs/self-improvement/policy.md`.

## 5. Preserved guardrails (regression watch)

`enforce_turn_budget`, `maybe_persist_tool_result`, `iteration_budget`,
`_guardrail_block_result`/`_append_guardrail_observation`, `file_safety`,
`message_sanitization`, multimodal/vision handling, the `/steer` drain — all
unchanged and verified by the integration tests (budget still fires after
compaction; guardrail blocks still short-circuit).
