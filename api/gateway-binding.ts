// ============================================================================
// /api/gateway-binding — bind or clear the authenticated account's own MUSE
// gateway (the target of the /api/gateway relay).
//
//   POST   { gateway_url, gateway_token }  -> upsert the caller's binding
//   DELETE {}                              -> remove the caller's binding
//
// This is the ONLY endpoint where the per-account gateway bearer transits the
// browser — exactly once, over HTTPS, at bind time. It is stored via the
// service-role key (account_gateways has no anon-path policies at all) and is
// never returned by any endpoint afterwards (api/me.ts exposes has_token only).
//
// Constraints mirror the relay's requirements so a binding that can't work is
// rejected up front:
//   * gateway_url must be https:// (the relay refuses http targets);
//   * no credentials/fragment in the URL; the path is kept (a reverse proxy
//     may mount per-user gateways under /u/<slug>).
// ============================================================================

import { bearerFromRequest, gatewayRelayConfigured } from './gateway/[...path]';

export const config = { runtime: 'edge' };

declare const process: { env?: Record<string, string | undefined> } | undefined;

function envVar(name: string): string {
  return (typeof process !== 'undefined' && process.env && process.env[name]) || '';
}

function supabaseUrl(): string {
  return envVar('SUPABASE_URL').replace(/\/$/, '');
}

function serviceRoleKey(): string {
  return envVar('SUPABASE_SERVICE_ROLE_KEY') || envVar('SUPABASE_SERVICE_KEY');
}

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

/** Verify the caller's Supabase session JWT -> account id ('' when invalid). */
async function verifyAccount(accessToken: string): Promise<string> {
  if (!accessToken) return '';
  try {
    const res = await fetch(`${supabaseUrl()}/auth/v1/user`, {
      headers: { apikey: serviceRoleKey(), Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return '';
    const body = (await res.json()) as { id?: string };
    return body?.id || '';
  } catch {
    return '';
  }
}

/** Validate + normalize a user-supplied gateway base URL. */
function normalizeGatewayUrl(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  const trimmed = raw.trim().replace(/\/+$/, '');
  let u: URL;
  try {
    u = new URL(trimmed);
  } catch {
    return null;
  }
  if (u.protocol !== 'https:') return null;
  if (u.username || u.password) return null;
  if (u.hash || u.search) return null;
  return trimmed;
}

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== 'POST' && req.method !== 'DELETE') {
    return json({ error: 'method not allowed' }, 405);
  }
  if (!gatewayRelayConfigured()) {
    return json({ error: 'gateway relay not configured' }, 501);
  }

  const accountId = await verifyAccount(bearerFromRequest(req));
  if (!accountId) {
    return json({ error: 'authentication required' }, 401);
  }

  const base = supabaseUrl();
  const svc = serviceRoleKey();

  if (req.method === 'DELETE') {
    try {
      const q = new URL(`${base}/rest/v1/account_gateways`);
      q.searchParams.set('user_id', `eq.${accountId}`);
      const res = await fetch(q.toString(), {
        method: 'DELETE',
        headers: { apikey: svc, Authorization: `Bearer ${svc}`, Prefer: 'return=minimal' },
      });
      if (!res.ok) return json({ error: 'failed to clear binding' }, 502);
      return json({ ok: true, connected: false }, 200);
    } catch {
      return json({ error: 'failed to clear binding' }, 502);
    }
  }

  // POST — bind.
  let payload: { gateway_url?: unknown; gateway_token?: unknown };
  try {
    payload = (await req.json()) as typeof payload;
  } catch {
    return json({ error: 'invalid JSON body' }, 400);
  }

  const gatewayUrl = normalizeGatewayUrl(payload.gateway_url);
  if (!gatewayUrl) {
    return json(
      { error: 'gateway_url must be a clean https:// base URL (no query/fragment/credentials)' },
      400,
    );
  }
  const gatewayToken = typeof payload.gateway_token === 'string' ? payload.gateway_token.trim() : '';
  if (!gatewayToken || gatewayToken.length > 512) {
    return json({ error: 'gateway_token is required' }, 400);
  }

  try {
    const res = await fetch(`${base}/rest/v1/account_gateways`, {
      method: 'POST',
      headers: {
        apikey: svc,
        Authorization: `Bearer ${svc}`,
        'Content-Type': 'application/json',
        // Upsert on the user_id primary key.
        Prefer: 'resolution=merge-duplicates,return=minimal',
      },
      body: JSON.stringify({
        user_id: accountId,
        gateway_url: gatewayUrl,
        gateway_token: gatewayToken,
        updated_at: new Date().toISOString(),
      }),
    });
    if (!res.ok) return json({ error: 'failed to store binding' }, 502);
  } catch {
    return json({ error: 'failed to store binding' }, 502);
  }

  // Echo only non-sensitive state (the token is never serialized back).
  return json({ ok: true, connected: true, gateway_url: gatewayUrl }, 200);
}
