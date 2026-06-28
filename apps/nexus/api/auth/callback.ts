// ============================================================================
// Edge: OAuth redirect landing.
//
// GET /api/auth/callback   — where GoTrue (Supabase) sends the browser back
// after an OAuth provider sign-in (we passed redirect_to=<origin>/api/auth/callback).
//
// Two GoTrue flows, both handled honestly:
//
//   • Implicit flow: the session arrives in the URL *fragment*
//     (#access_token=...&refresh_token=...). The server NEVER sees a fragment,
//     so we just bounce the browser to /signin and preserve the fragment; the
//     client (AuthProvider) verifies the token via /auth/v1/user before trusting it.
//
//   • Authorization-code (PKCE) flow: GoTrue returns ?code=...; we forward that
//     code to /signin as a query param so the client can complete the exchange.
//
//   • Error: GoTrue returns ?error=...&error_description=...; we forward those
//     so /signin can show an HONEST failure (never a faked success).
//
// This handler mints NOTHING and trusts NOTHING — it only redirects. The actual
// security boundary (signature verification) is /api/auth/session. It needs no
// secret of its own and degrades gracefully when auth env is unset.
// ============================================================================

export const config = { runtime: 'edge' };

export default async function handler(req: Request): Promise<Response> {
  const incoming = new URL(req.url);

  // Carry forward only the auth-relevant query params to /signin. The fragment
  // (#access_token=...) is preserved automatically by the browser across this
  // server redirect, so the client can pick it up.
  const dest = new URL('/signin', incoming.origin);
  for (const k of ['code', 'error', 'error_description', 'error_code', 'state']) {
    const v = incoming.searchParams.get(k);
    if (v) dest.searchParams.set(k, v);
  }

  return new Response(null, {
    status: 302,
    headers: {
      Location: dest.toString(),
      'Cache-Control': 'no-store',
    },
  });
}
