// ============================================================================
// POST /api/billing/portal — open the Stripe Billing Portal for the signed-in
// account (manage/cancel their subscription, update payment method). Returns
// { url } to redirect to. 501 when billing is unconfigured; 409 when the
// account has no Stripe customer yet (i.e. never checked out).
// ============================================================================

import {
  bearerFromRequest,
  billingConfigured,
  json,
  serviceRoleKey,
  siteOrigin,
  stripe,
  supabaseUrl,
  verifyAccount,
} from './_stripe';

export const config = { runtime: 'edge' };

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);
  if (!billingConfigured()) return json({ error: 'billing not configured' }, 501);

  const accountId = await verifyAccount(bearerFromRequest(req));
  if (!accountId) return json({ error: 'authentication required' }, 401);

  // Resolve the account's existing Stripe customer id (do NOT create one here —
  // the portal only makes sense for an account that has checked out).
  let customerId = '';
  try {
    const q = new URL(`${supabaseUrl()}/rest/v1/profiles`);
    q.searchParams.set('user_id', `eq.${accountId}`);
    q.searchParams.set('select', 'stripe_customer_id');
    q.searchParams.set('limit', '1');
    const r = await fetch(q.toString(), {
      headers: {
        apikey: serviceRoleKey(),
        Authorization: `Bearer ${serviceRoleKey()}`,
        Accept: 'application/json',
      },
    });
    if (r.ok) {
      const rows = (await r.json()) as Array<{ stripe_customer_id?: string }>;
      customerId = rows?.[0]?.stripe_customer_id || '';
    }
  } catch {
    /* fall through to 409 */
  }
  if (!customerId) return json({ error: 'no subscription to manage yet' }, 409);

  try {
    const portal = await stripe('billing_portal/sessions', {
      customer: customerId,
      return_url: `${siteOrigin(req)}/#account`,
    });
    return json({ url: portal.url }, 200);
  } catch (e) {
    return json({ error: `portal failed: ${(e as Error).message}` }, 502);
  }
}
