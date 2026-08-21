---
paths:
  - "src/**/*.{js,jsx,ts,tsx,mjs,cjs}"
  - "api/**/*.{js,mjs,ts}"
  - "base44/**/*.{js,mjs,ts}"
  - "scripts/**/*.{js,mjs,sh}"
  - "supabase/**/*.{sql,ts}"
---

# Engineering production quality

**Path scope (auto-activates):** files matching the `paths` frontmatter
above — `src/**`, `api/**`, `base44/**`, `scripts/**`, and
`supabase/**`. Triggers when Claude reads files matching the pattern,
per the native rules behavior at
`https://code.claude.com/docs/en/memory#organize-rules-with-claude-rules`.
**Authority:** `AGENTS.md`, `docs/governance/03-change-risk-matrix.md`,
`.claude/rules/00-commercial-delivery-standard.md`.

When you write or modify product code in this repo, follow these
rules in addition to the unconditional commercial delivery standard.

## Discipline

1. **No speculative rewrites.** If the file already works and the
   task does not require a refactor, do not refactor it. Rename a
   symbol only when a caller needs it renamed.
2. **No hidden behavior changes.** A bug fix should not also tighten
   validation, alter response shape, or change a log line unless the
   change is explicitly part of the task and called out in the PR.
3. **No brittle one-off fixes.** If two callers will hit the same
   bug, fix the shared root. If only one caller has the bug, do not
   pre-emptively touch the other.
4. **Prefer existing patterns.** Inspect:
   - `src/lib/rbac.js` for role checks,
   - `src/api/localValidation.js` and
     `base44/functions/runValidation/` for 49 CFR rule-engine plumbing,
   - `api/_lib/authz.mjs` for authz envelopes,
   - `api/_lib/auditChain.mjs` for audit-ledger writes,
   - `src/lib/provenance/**` for OCR provenance,
   - `src/lib/documents/**` for regulator-facing builders,
   - `src/lib/workflow.js` for the six-state load machine.
   If your change touches any of these, extend the existing module —
   do not invent a parallel one.
5. **Preserve tenant isolation.** Every server-side handler must
   carry tenant scope through to every read and every write. RLS
   policy in `supabase/migrations/**rls**` is part of the contract,
   not an implementation detail.
6. **Explicit error handling.** No silent catches that swallow real
   errors. Either bubble (with context), or log via the existing
   logger, or convert to a typed error a caller knows about. Do not
   wrap a boundary in `try { ... } catch { /* ignore */ }`.
7. **Observability compatibility.** If you add a new failure path,
   it logs. If you add a new latency-sensitive call, it is timed by
   the existing instrumentation pattern (no new ad-hoc telemetry).
8. **Docs follow behavior.** If observable behavior changes
   materially, update the relevant doc: `HANDOFF.md`, the matching
   runbook in `docs/runbooks/`, or the matching compliance evidence
   record in `docs/compliance/` / `docs/iso27001/`. Update only what
   moved.

## Before opening a PR touching this scope

- `npm run lint` clean
- `npm run typecheck` clean
- `npm test` — count stable or explained
- `npm run build` exit 0
- If you touched an e2e-covered path: `npm run test:e2e`
- If you touched governance / index: `npm run governance:check`
- After native activation: `npm run agentos:check`

## When in doubt

Open the matching workflow in `docs/workflows/` before writing code.
For "complex-bug-fix" use `.claude/skills/complex-bug-fix`. For
RC3 surfaces (authz, audit, OCR, regulator-facing, Square, SCIM,
RLS) escalate to the maker-checker discipline of
`.claude/agents/principal-code-reviewer.md` plus
`.claude/agents/assurance-security-compliance-office.md`.
