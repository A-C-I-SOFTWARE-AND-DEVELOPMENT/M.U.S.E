# Follow-up fu-5 — correct the stale "Supabase absent" claim in the program status doc

- **Status:** complete
- **Risk class:** doc-only (no code, no ledger, no behavior change)
- **Branch:** `claude/fu-5-supabase-doc`
- **Base:** `origin/main`
- **Owned / allowed files:**
  - `docs/launch/10_10_PROGRAM_STATUS.md` (the correction)
  - `docs/launch/followups/fu-5-supabase-doc.md` (this snapshot)
- No other file touched.

## Intent

`docs/launch/10_10_PROGRAM_STATUS.md` carried a **stale claim**: it scored
Sprint 11 (Supabase) as `🔴 1.5/10` and described Supabase as "absent — no
`plugins/supabase/`, no memory backend". That is wrong; Supabase is in fact
fully shipped in-repo. This follow-up corrects every understated mention to the
honest shipped inventory while keeping the doc's evidence-backed tone. It
changes documentation only.

## Verification evidence

### Tests (the load-bearing evidence)

Command:

```
uv run --extra all --extra dev pytest \
  tests/plugins/test_supabase_plugin.py \
  tests/plugins/memory/test_supabase_memory.py \
  tests/test_integration_supabase.py \
  -o addopts="" -q
```

Result: **47 passed in 3.16s** (matches the expected ~47).

### Components confirmed present

- `plugins/supabase/` — tool plugin. Four tools registered at
  `plugins/supabase/tools.py:348`:
  - `supabase_query` — read rows via PostgREST (read-only).
  - `supabase_list_tables` — list PostgREST-exposed tables (read-only).
  - `supabase_execute_sql` — **propose-only / owner-gated** SQL migration.
  - `supabase_apply_migration` — **propose-only / owner-gated** named migration.
  - Writes go through `_propose_write` (returns a proposal + a
    `DecisionVerdict`; never authors/applies the mutation).
- `plugins/memory/supabase/` — memory backend. Persistent, **recency-based**
  recall over a Supabase PostgREST table (most recent N turns per session);
  semantic/pgvector recall is a documented follow-up.
- `hermes_cli/integrations/supabase.py` — integration adapter with
  `detect` / `plan` / `explain` / `execute`, **dry-run by default**
  (`dry_run: bool = True`).

## What changed in the doc

All five Supabase mentions found via `grep -ni supabase
docs/launch/10_10_PROGRAM_STATUS.md` were reviewed; the four that understated
Supabase were corrected, plus a modest headline note:

1. **Score-summary table row (Sprint 11)** — was `🔴 1.5/10 | Supabase
   absent; …`. Now `🟡 6.5/10` citing the shipped tool plugin (4 tools),
   memory backend, integration adapter, and 47 tests, with the two optional
   owner-gated follow-ons named.
2. **"Optional / unchanged" line (post-merge audit update)** — was "Supabase
   (S11) absent". Now states Supabase is shipped (tool plugin / memory backend
   / integration adapter, 47 tests) with the two optional follow-ons named.
3. **Capstone "what remains" item (d)** — was "the optional integrations
   (Supabase S11)". Now names the two optional owner-gated Supabase follow-ons
   (live SQL execution behind a gate, pgvector semantic recall) atop the
   already-shipped plugin/backend/adapter.
4. **Per-sprint detail section "Sprint 11"** — was `🔴 MOSTLY MISSING` with
   "Supabase — absent. No `plugins/supabase/`, no memory backend …". Now
   `🟡 SUPABASE SHIPPED, VERCEL PARTIAL`, enumerating all three shipped
   surfaces with `path:line` citations and the 47-test list; the **Gap** now
   names the two optional Supabase follow-ons (Vercel deploy/preview/logs is
   still the genuinely-missing optional piece).
5. **Headline grade** — nudged modestly from ~85% to ~86%, explicitly framed
   as a *correction, not new work*: S11 was previously under-credited as
   "absent" but in fact ships the plugin/backend/adapter + 47 tests. Overall
   grade was not inflated beyond reflecting that S11 is shipped (not absent).

Vercel statements were left unchanged (still sandbox-exec only); the
shared-cockpit-token-at-rest note and all non-Supabase content are untouched.

## Validation

`git diff --name-only` shows only:

- `docs/launch/10_10_PROGRAM_STATUS.md`
- `docs/launch/followups/fu-5-supabase-doc.md`

No code, no ledger, no other file.

## Residual / deferred

Two **optional, owner-gated** Supabase follow-ons remain (named in the doc, not
overclaimed as done):

1. **Live SQL execution behind a gate** — today `supabase_execute_sql` /
   `supabase_apply_migration` are propose-only / owner-gated; a live execution
   path is a deliberate follow-up.
2. **pgvector semantic recall** — today the memory backend recall is
   recency-based; semantic / pgvector search is a documented follow-up.
