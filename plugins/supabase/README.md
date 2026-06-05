# supabase plugin

Native Supabase access for Hermes via the project's PostgREST endpoint. Four
tools under the `supabase` toolset:

| Tool | Kind | What it does |
|---|---|---|
| `supabase_query` | read | Read rows from a table (PostgREST). |
| `supabase_list_tables` | read | List tables exposed by PostgREST. |
| `supabase_execute_sql` | write · gated | Author a SQL migration file. |
| `supabase_apply_migration` | write · gated | Author a named SQL migration file. |

## Configuration

Keys live in the environment or `~/.hermes/.env`:

- `SUPABASE_URL` — project URL (`https://<ref>.supabase.co`).
- `SUPABASE_ANON_KEY` — anon key (used by read tools by default).
- `SUPABASE_SERVICE_ROLE_KEY` — service-role key (bypasses row-level security).
  **Never** returned to the model or sent to the cockpit; only used when both
  `supabase.allow_service_role` is true and a call opts in with
  `use_service_role: true`.

Add a `supabase:` block to `~/.hermes/config.yaml`:

```yaml
supabase:
  enabled: true             # master switch (default: false)
  allow_writes: false       # write tools refuse without this (default: false)
  allow_service_role: false # gate for using the RLS-bypassing key (default: false)
  allowed_tables:           # optional; empty = no allowlist enforced
    - "profiles"
```

## Safety model

Write tools are **propose-only** and never touch a live database or author a
file. A write passes three gates:

1. `supabase.enabled` is true **and** the project is configured.
2. `supabase.allow_writes` is true.
3. The unified **decision engine** returns a verdict: owner-gated (`ask`), and a
   secret detected inside the SQL forces a `refuse`. The tool returns the
   verdict with `executed: false` — it does not trust a model-supplied phrase
   (a tool cannot self-enforce an owner gate). The migration is authored and
   applied **out-of-band** via the cockpit owner-approval path, then
   `supabase db push`.

Keys are scrubbed from any error text. Returned rows are size-capped.

## Not yet (follow-ups)

- Out-of-band authoring + execution of an approved migration via the cockpit
  owner-approval path (today the write tools only propose).
- A Supabase **memory provider** (`plugins/memory/supabase/`) conforming to
  `agent/memory_provider.py`.
- Optional decision-ledger mirror to Supabase for cockpit history.
