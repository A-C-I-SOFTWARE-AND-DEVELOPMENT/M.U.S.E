// ============================================================================
// GET /api/me — resolve the authenticated account's stored MUSE gateway binding
// WITHOUT ever returning the gateway bearer token to the browser.
//
// Flow:
//   1. The browser sends its own Supabase session JWT as `Authorization:
//      Bearer <supabase-access-token>` (the anon-scoped user session, NOT a
//      secret — it's the user proving who they are).
//   2. This edge function verifies that JWT against Supabase Auth using the
//      SERVER-ONLY service-role key (process.env, never VITE_-prefixed, never
//      shipped to the browser), yielding a trusted account id.
//   3. It reads that account's row from the `account_gateways` table (also with
//      the service-role key) and returns ONLY non-sensitive fields:
//        { account_id, gateway_url, connected, has_token }
//      The per-account gateway bearer is deliberately NEVER serialized — it
//      stays server-side and is used only by the /api/gateway relay.
//
// Honest by construction:
//   • No Supabase env configured  -> 501 { error: 'gateway relay not configured' }
//   • No / invalid Authorization  -> 401 { error: 'authentication required' }
//   • Authed but no stored binding -> 200 { connected: false } (empty, not fake)
//
// Compiles when Supabase / env are unset: all secrets are read lazily from
// process.env via a guarded ambient declaration, so there is no build-time
// dependency on any env var being present.
// ============================================================================

import { resolveAccountGateway, gatewayRelayConfigured, bearerFromRequest } from './gateway/[...path]';

export const config = { runtime: 'edge' };

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== 'GET') {
    return json({ error: 'method not allowed' }, 405);
  }

  // No server-side Supabase wiring -> honest "not configured" (the browser then
  // falls back to direct gateway pairing for the local path).
  if (!gatewayRelayConfigured()) {
    return json({ error: 'gateway relay not configured' }, 501);
  }

  const accessToken = bearerFromRequest(req);
  if (!accessToken) {
    return json({ error: 'authentication required' }, 401);
  }

  const account = await resolveAccountGateway(accessToken);
  if (!account.ok) {
    // Distinguish "who are you" (401) from "you have no gateway yet" (200 empty).
    if (account.reason === 'unauthenticated') {
      return json({ error: 'authentication required' }, 401);
    }
    // Authenticated but nothing bound yet — honest empty state, no fabrication.
    return json(
      {
        account_id: account.accountId ?? null,
        gateway_url: null,
        connected: false,
        has_token: false,
      },
      200,
    );
  }

  // Return only non-sensitive fields. The bearer token is NEVER serialized to
  // the browser — it lives server-side and is used solely by the relay.
  return json(
    {
      account_id: account.accountId,
      gateway_url: account.gatewayUrl,
      connected: true,
      has_token: !!account.gatewayToken,
    },
    200,
  );
}
