---
name: security-privacy-review
description: Review a diff or surface for secrets, auth, authz/RLS, multi-tenant boundaries, PII handling, deletion/export, telemetry, and dangerous operations. Use whenever a change touches auth, secrets, user data, third-party APIs, or destructive ops.
---

# Security & Privacy Review

## Use when

- The diff touches auth, secrets, RBAC, RLS, tenant boundaries.
- The diff touches user data lifecycle (storage, deletion, export).
- The diff adds a third-party API call or telemetry.
- The diff adds destructive operations or migrations.
- Before any release that includes such changes.

## Checklist

1. **Secrets** — no secret values in source, history, logs, error
   messages. `.env.example` lists keys without values.
2. **AuthN** — sessions signed, short-lived where appropriate,
   invalidatable; no client-side auth bypass.
3. **AuthZ** — every privileged action checks permission server-side; no
   "trusted client".
4. **Tenant isolation** — every user-data query scoped at the data layer.
5. **RLS** — policies cover both read and write paths; tested with the
   intended role, not just superuser.
6. **PII** — minimum collection; deletion path exists and is tested;
   export path if required; logs don't capture PII.
7. **Telemetry / third-party** — each external call justified, scoped,
   consent-respecting.
8. **Destructive ops** — reversible where possible; gated behind explicit
   production flag; migrations reviewed.
9. **Dependency risk** — new packages checked for CVEs and ownership.
10. **Audit log** — privileged actions write to an append-only log.

## Procedure

1. Identify the surface and the diff under review.
2. Walk the checklist, citing file:line for each finding.
3. Assign severity: CRITICAL / HIGH / MEDIUM / LOW / INFO.
4. Required fixes block merge; recommended fixes do not.

## Output

```
## Surface reviewed
## Findings (severity, file:line, finding, required fix)
## Compliance impact (if any)
## Required fixes before merge
## Recommended fixes (non-blocking)
## Verdict: SAFE TO MERGE | FIX REQUIRED | DO NOT MERGE
```

## Hard rules

- Print secret names, never secret values.
- A finding without file:line is not a finding.
- Any CRITICAL or HIGH finding → verdict is FIX REQUIRED or stronger.
- If you cannot see the auth model, verdict is UNVERIFIABLE.
