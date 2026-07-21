-- 202607200001_research_fabric_snapshots.sql
-- Migrate the research-fabric snapshot index from local SQLite
-- (.hermes/research_fabric/snapshots.db) to Supabase Postgres.
--
-- Design notes:
--   * The SQLite store is an INDEX, not the truth — tamper-evidence lives in
--     the hash-chained GuardrailLedger. That contract is preserved here:
--     every row carries ledger_record_hash (the ledger row it corresponds to)
--     plus an internal prev_row_hash -> row_hash chain so verify_chain can
--     detect local tampering offline.
--   * payload_json (TEXT) becomes payload (jsonb) for queryability; the
--     application layer keeps canonical_json semantics for hashing.
--   * row_hash uniqueness is enforced exactly as in SQLite.
--   * RLS enabled, no policies: only the service role (used by the research
--     fabric runner, server-side) can read/write. No anon/authenticated
--     access — this is internal autonomy state, never client-facing.

create table if not exists public.research_fabric_snapshots (
    id                  bigint generated always as identity primary key,
    created_at          timestamptz not null default now(),
    kind                text not null,
    subject             text not null,
    payload             jsonb not null,
    ledger_record_hash  text not null default '',
    prev_row_hash       text not null,
    row_hash            text not null unique
);

-- Query paths used by the runner: latest-by-kind, subject lookups, chain walk.
create index if not exists research_fabric_snapshots_kind_created_idx
    on public.research_fabric_snapshots (kind, created_at desc);

create index if not exists research_fabric_snapshots_subject_idx
    on public.research_fabric_snapshots (subject);

alter table public.research_fabric_snapshots enable row level security;

-- No RLS policies on purpose: service_role bypasses RLS; all other roles are
-- denied by default. The research fabric only ever connects with the
-- service-role key from the runner host.

comment on table public.research_fabric_snapshots is
    'Research fabric snapshot index (runs/champions/candidates). Index only — '
    'tamper-evidence lives in the GuardrailLedger; row_hash chain mirrors the '
    'former SQLite store for offline tamper detection.';
