// Thin, optional Supabase client (REST + Auth, no SDK dependency). Used for
// persistence (push subscriptions) and a lightweight session check. Every call
// no-ops gracefully when the env vars are unset, so the app runs backend-free.

import { supabaseUrlCfg, supabaseAnonCfg } from './config';

export function supabaseConfigured(): boolean {
  return !!(supabaseUrlCfg() && supabaseAnonCfg());
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const ANON = supabaseAnonCfg();
  return {
    apikey: ANON,
    Authorization: `Bearer ${ANON}`,
    'Content-Type': 'application/json',
    ...extra,
  };
}

/** Upsert a row into a table via PostgREST. Returns false when unconfigured. */
export async function upsert(table: string, row: Record<string, unknown>): Promise<boolean> {
  if (!supabaseConfigured()) return false;
  try {
    const res = await fetch(`${supabaseUrlCfg()}/rest/v1/${table}`, {
      method: 'POST',
      headers: headers({ Prefer: 'resolution=merge-duplicates,return=minimal' }),
      body: JSON.stringify(row),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Persist a Web Push subscription for this device. */
export async function persistPushSubscription(sub: PushSubscriptionJSON): Promise<boolean> {
  return upsert('push_subscriptions', {
    endpoint: sub.endpoint,
    keys: sub.keys ?? {},
    updated_at: new Date().toISOString(),
  });
}

/** Best-effort current-session probe (anon by default). */
export async function getSessionUser(): Promise<{ id: string } | null> {
  if (!supabaseConfigured()) return null;
  try {
    const res = await fetch(`${supabaseUrlCfg()}/auth/v1/user`, { headers: headers() });
    if (!res.ok) return null;
    const u = await res.json();
    return u?.id ? { id: u.id } : null;
  } catch {
    return null;
  }
}
