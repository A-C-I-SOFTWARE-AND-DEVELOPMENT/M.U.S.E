// ============================================================================
// GET /api/config — PUBLIC bootstrap configuration for the static cockpit page.
//
// The cockpit ships as a fully static file, so anything environment-specific
// it needs at runtime (which Supabase project to sign in against, whether the
// hosted chat/relay lanes exist, tier copy) is served here from env instead of
// being baked in at build time. ONLY public values belong in this response:
// the Supabase anon key is a publishable client key by design; secrets
// (service-role key, JWT secret, provider keys, Stripe secret) must NEVER be
// added here.
//
// Honest by construction: when a capability's env isn't set, its flag is
// false / its section is null — the page then hides that lane instead of
// pretending.
// ============================================================================

import { hasServerKey } from './_providers';
import { agentChatDailyLimit, agentLaneRequiresPro } from './_entitlements';

export const config = { runtime: 'edge' };

declare const process: { env?: Record<string, string | undefined> } | undefined;

function envVar(name: string): string {
  return (typeof process !== 'undefined' && process.env && process.env[name]) || '';
}

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== 'GET') {
    return new Response(JSON.stringify({ error: 'method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const supabaseUrl = envVar('SUPABASE_URL').replace(/\/$/, '');
  const supabaseAnonKey = envVar('SUPABASE_ANON_KEY') || envVar('VITE_SUPABASE_ANON_KEY');
  const authConfigured = !!(supabaseUrl && supabaseAnonKey);
  const relayConfigured = !!(
    supabaseUrl && (envVar('SUPABASE_SERVICE_ROLE_KEY') || envVar('SUPABASE_SERVICE_KEY'))
  );

  const body = {
    // Anonymous demo chat lane (/api/chat) — true when a server provider key
    // is configured (BYOK works regardless).
    demoChat: hasServerKey(),
    // Account sign-in (Supabase GoTrue) — the page mounts the Account panel
    // only when this is true.
    auth: authConfigured
      ? { supabaseUrl, supabaseAnonKey }
      : null,
    // Signed-in gateway relay (/api/gateway/*) + full-agent chat lane.
    relay: relayConfigured,
    agentLane: relayConfigured
      ? {
          requiresPro: agentLaneRequiresPro(),
          dailyLimitFree: agentChatDailyLimit('free'),
          dailyLimitPro: agentChatDailyLimit('pro'),
        }
      : null,
  };

  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      // Cache briefly at the edge; env changes surface within a minute.
      'Cache-Control': 'public, max-age=60',
    },
  });
}
