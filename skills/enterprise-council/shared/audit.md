# Audit log schema & redaction rules

Every council session writes to
`~/.hermes/enterprise/audit/<session_id>.jsonl`. One JSON object per
line. The schema is the dataclass `enterprise.audit.AuditEvent`.

## Fields

| Field | Type | Notes |
|---|---|---|
| `ts` | float | Unix seconds. |
| `session_id` | str | Stable across all rows of one run. |
| `event` | str | One of `plan` / `dispatch` / `leaf_result` / `judge` / `retry` / `escalate` / `done` / `improvement`. |
| `agent` | str | `orchestrator` / `judge` / `monitor` / one of the five domain names. |
| `tool` | str? | The action invoked, e.g. `finance.invoice.create`. |
| `args_hash` | str? | 12-char SHA-256 prefix of canonicalised args. |
| `result_hash` | str? | 12-char SHA-256 prefix of canonicalised result. |
| `result_summary` | str | ≤200 chars, run through `agent.redact.redact_sensitive_text`. |
| `risk` | str? | `low` / `medium` / `high`. |
| `validation` | str? | `ok` / `schema_fail` / `policy_fail` / `judge_disagree` / `escalated`. |
| `retry_count` | int | Number of retries that have already fired for this leaf. |
| `duration_ms` | float? | Wall-clock of the leaf call. |
| `secret_fingerprints` | tuple[str] | `"<service>:<8-hex>"` for any secret fetched. |
| `extra` | dict | Free-form, per-event. |

## What is NEVER written

  * Raw secret values. Even where a secret was fetched, only the
    fingerprint goes here.
  * Verbatim tool args or model output. Always hashed or summarised.
  * Free-form chains of thought. The summary is bounded.

## Redaction

`enterprise.audit.audit(...)` runs `result_summary` through the global
`redact_sensitive_text(..., force=True)` so any token-shaped string
that slips into a summary is masked before the row is written. The
serialised row itself is then passed through the same redactor a
second time, so even an off-spec caller cannot leak a secret in
`extra`.

If `HERMES_REDACT_SECRETS=false`, redaction is disabled globally —
council audit still calls the redactor with `force=True` so the rows
on disk stay clean regardless.

## Reading the trail

```python
from enterprise.audit import read_events
for ev in read_events("council-abc12345"):
    print(ev.event, ev.agent, ev.tool, ev.validation)
```

The Monitor uses exactly this surface to compute its improvement
proposals.
