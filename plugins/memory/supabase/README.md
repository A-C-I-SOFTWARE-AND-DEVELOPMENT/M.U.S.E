# supabase memory provider

Persistent recall backed by a Supabase Postgres table. Each completed turn is
stored via PostgREST; the most recent turns for the session are surfaced before
the next reply. Recall is **recency-based** (no embeddings yet — semantic /
pgvector search is a follow-up). Built on `httpx` (a base dep) — no SDK, and no
dependency on the `supabase` *tool* plugin.

## Enable

1. Set credentials in `~/.hermes/.env` (or `$HERMES_HOME/supabase_memory.json`):
   - `SUPABASE_URL` — `https://<ref>.supabase.co`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_MEMORY_TABLE` — optional (default `hermes_memory`)
2. Create the table once — e.g. with the `supabase` tool plugin's
   `supabase_apply_migration`, then `supabase db push`:

   ```sql
   create table if not exists hermes_memory (
     id bigserial primary key,
     session_id text not null,
     user_content text,
     assistant_content text,
     created_at timestamptz default now()
   );
   create index if not exists hermes_memory_session_idx
     on hermes_memory (session_id, created_at desc);
   ```
3. Activate in `~/.hermes/config.yaml`:

   ```yaml
   memory:
     provider: supabase
   ```

## Behaviour & safety

- Uses the **anon key**, so row-level security applies; content is the user's own
  conversation stored in the user's own project.
- Non-primary contexts (`cron`, `flush`) are skipped so system prompts never
  pollute conversational memory.
- All network calls degrade silently — a memory backend never breaks the turn loop.

## Not yet (follow-ups)

- Semantic recall via pgvector + embeddings (today: recency by `session_id`).
- A `supabase_memory_search` tool for explicit lookups.
- Optional service-role mode for cross-session/admin recall.
