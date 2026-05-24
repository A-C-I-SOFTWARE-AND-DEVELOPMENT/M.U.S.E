# 01 — Source-of-Truth Hierarchy

**Status:** Installed 2026-05-17

When repository documents disagree, this hierarchy decides which one
wins. The hierarchy exists because docs drift: HANDOFF.md is dated
2026-04-27 and does not mention Stage 1–4 or the v1.0.0 release;
AUDIT.md is dated 2026-04-20; portions of older marketing notes
reference DNS state that may have moved. Agents must resolve, not
amplify, those contradictions.

## Precedence order (highest first)

1. **Live code and tests** — what `git grep` and `npm test` show is
   authoritative for current behavior. If a doc says feature X exists
   and the code does not implement it, the code wins (and the doc is
   stale).
2. **`AGENTS.md`** — constitutional law. Owner-only walls, two-gate
   preview-before-publish, branch rules, taxonomy, authority/risk/
   tool-trust headlines. Never overridden by any other doc.
3. **`PUBLISH.md`** — release playbook. Gate definitions and rollback
   procedures.
4. **`SKIPPED.md`** — stub inventory and deferred-risk schema. If a
   doc claims a stub is wired but SKIPPED.md still lists it as open
   and the `TODO(stub:<name>):` token is live, SKIPPED.md + the code
   token win.
5. **`tests/inventory/skipped-coverage.test.js`** — the CI gate
   defines the exact pairing rule between SKIPPED.md and live
   `TODO(stub:…)` tokens. If a stub entry passes the gate, the gate's
   verdict overrides verbal disagreement.
6. **`docs/inventory/blockers-final.md`** — launch-blocker rollup
   (R4-X-authored, 2026-05-15). Severity assignments here outrank
   older P-tagging in marketing or runbook docs.
7. **`docs/releases/v1.0.0-enterprise-ready.md`** — capabilities at
   tag time. If a doc says capability X is missing but the release
   notes record it shipped, the release notes win.
8. **`docs/iso27001/`, `docs/security/`, `docs/runbooks/`,
   `docs/compliance/`** — operational discipline and compliance
   evidence. Authoritative for ISMS scope and operational procedure.
9. **`docs/AUTONOMOUS_ORGANIZATION_INDEX.md` + this `docs/governance/`
   set** — the AEO operating system. Authoritative for how future
   agents organize their work, not for product behavior.
10. **`HANDOFF.md`, `AUDIT.md`, `SMOKE_TEST.md`, `CLOUD_SYNC.md`,
    `PLAY_STORE.md`** — historical context. Use for orientation;
    treat dated entries as advisory.
11. **`marketing/`** — owner-facing operational notes (Square setup,
    Vercel status, launch checklist). Authoritative for the
    procedures they describe; not authoritative for product
    behavior.
12. **Older planning docs (e.g. anything pre-v1.0.0 not on this
    list)** — historical only.

## Resolving contradictions

When a contradiction appears:

1. Identify which doc in the hierarchy is highest-ranked among the
   conflicting parties.
2. Treat the higher doc as authoritative; flag the lower doc for
   reconciliation via the `doc-freshness-reconcile` skill.
3. If the higher doc is itself wrong (proven by code/tests), the
   `doc-freshness-reconcile` skill reaches up the hierarchy as far
   as needed. Updates to `AGENTS.md` require an explicit commit and
   are owner-reviewed.
4. Record the contradiction in the next `agent-run-retrospective`
   artifact so the AEO learns.

## Known stale-doc risks (as of 2026-05-17)

| Doc | Stale because | Reconcile via |
|---|---|---|
| `HANDOFF.md` | Dated 2026-04-27. Does not mention Stage 1–4 or v1.0.0-enterprise-ready. The "What's NOT done" tracks list items already shipped (Vercel project, Capacitor sync, brand icons). | `doc-freshness-reconcile` skill; either prepend a 2026-05-17 update or schedule a full rewrite |
| `AUDIT.md` | Dated 2026-04-20. The "User collection leaks cross-tenant" finding pre-dates Stage 3 authz and RLS migrations. | `doc-freshness-reconcile` skill; re-run the 5-role audit against the v1.0.0 codebase |
| `AGENTS.md` "Vercel + DNS gotcha (2026-05-03)" | DNS state may have moved. | Owner-confirmed check; update or label "as of 2026-05-03" if unchanged |
| `SKIPPED.md` "End-of-build rollup" count (23) vs full active entry count (26 incl. meta-blockers) | The rollup buckets don't tally meta-blockers (`supabase-project-provisioned`, `sor-shadow-write-wiring`, `certified-translator-engagement`) that are listed in the entries. | The bucket count is a navigation aid only; entries are source-of-truth |
| `CLOUD_SYNC.md` "NOT done yet" list | Dated 2026-05-03; some items may have landed since. | `doc-freshness-reconcile` skill |
| `PLAY_STORE.md` "Deliberately left NOT-DONE" list | Some items may have moved status. | `doc-freshness-reconcile` skill |

The `doc-freshness-reconcile` skill in `docs/skills/` is the standard
mechanism for working through this list.

## When in doubt

Live code and tests beat any document. `AGENTS.md` beats any
document below it. Owner judgment beats every document.
