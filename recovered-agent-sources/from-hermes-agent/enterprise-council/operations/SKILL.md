---
name: enterprise-operations
description: "Operations leaf: logistics planning + execution, compliance checks + filings, incident declaration."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [enterprise, operations, logistics, compliance, incidents]
    related_skills: [enterprise-orchestrator, enterprise-judge]
---

# Operations leaf

Single task in, structured result out. Plan-and-check actions are
autonomous; execution and incident declarations escalate.

## Available services

| Service | Used for |
|---|---|
| `sap` | Logistics + ERP |
| `slackops` | Ops channels + incident comms |
| `compliancedb` | Compliance evidence + filings |

## Sub-skills (actions)

| Action | Args | Risk |
|---|---|---|
| `logistics.plan` | `origin, destination, weight_kg, priority` | LOW |
| `logistics.execute` | `shipment_id` | MEDIUM |
| `compliance.check` | `region, category, evidence: tuple[str, ...]` | LOW |
| `compliance.file` | `compliance_id` | MEDIUM |
| `incident.declare` | `summary, severity` | HIGH |

## Credentials

```python
fetch_secret("sap", caller_role="operations", scope="shipment.read")
```

Compliance checks require `fetch_secret("compliancedb", caller_role="operations")`.
Incident declarations also need `slackops` for the ops channel ping;
both fetches happen inside your tool call, never inside follow-ups.

## Structured output

Compliance check:
```json
{
  "status": "ok",
  "compliance_id": "CMP-XXXX",
  "verdict": "pass" | "issues",
  "findings": ["…"]
}
```

For `incident.declare`, include both `incident_id` and `severity` (one
of low/medium/high/critical). The Judge cross-checks severity against
the supplied summary's keywords (e.g. "data loss" → critical).

## Hard prohibitions

* Do not file compliance reports with `verdict == "issues"` unless the
  Orchestrator explicitly authorised it (the task will carry the
  `force-file` tag). The default behaviour for a failing check is to
  return findings and stop.
* Do not declare incidents above severity "medium" without surfacing
  the full evidence list in the result. The Orchestrator promotes the
  task to human-gated on declaration.
