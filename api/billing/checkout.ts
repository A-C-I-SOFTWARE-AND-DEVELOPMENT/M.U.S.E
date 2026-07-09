// ============================================================================
// POST /api/billing/checkout — create a Stripe Checkout Session for the Pro
// subscription and return its URL. The caller proves identity with their
// Supabase session JWT; we resolve/create their Stripe customer server-side.
//
// Body: { interval?: 'monthly' | 'yearly' }  (default monthly)
// Returns: { url } to redirect the browser to Stripe Checkout.
//
// Honest when commerce is off: 501 if Stripe env is unset.
// ============================================================================

import {
  bearerFromRequest,
  billingConfigured,
  ensureCustomer,
  envVar,
  json,
  siteOrigin,
  stripe,
  verifyAccount,
} from './_stripe';

export const config = { runtime: 'edge' };

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);
  if (!billingConfigured()) return json({ error: 'billing not configured' }, 501);

  const accountId = await verifyAccount(bearerFromRequest(req));
  if (!accountId) return json({ error: 'authentication required' }, 401);

  let interval = 'monthly';
  try {
    const body = (await req.json()) as { interval?: string };
    if (body?.interval === 'yearly') interval = 'yearly';
  } catch {
    /* default monthly */
  }

  const priceId =
    interval === 'yearly'
      ? envVar('STRIPE_PRICE_PRO_YEARLY') || envVar('STRIPE_PRICE_PRO_MONTHLY')
      : envVar('STRIPE_PRICE_PRO_MONTHLY');
  if (!priceId) return json({ error: 'no price configured for that interval' }, 501);

  // The account email rides the JWT verification; re-fetch minimal profile via
  // the customer creation path (email is optional for Checkout).
  let email = '';
  try {
    const u = await fetch(`${envVar('SUPABASE_URL').replace(/\/$/, '')}/auth/v1/user`, {
      headers: {
        apikey: envVar('SUPABASE_SERVICE_ROLE_KEY') || envVar('SUPABASE_SERVICE_KEY'),
        Authorization: `Bearer ${bearerFromRequest(req)}`,
      },
    });
    if (u.ok) email = ((await u.json()) as { email?: string })?.email || '';
  } catch {
    /* email is optional */
  }

  try {
    const customerId = await ensureCustomer(accountId, email);
    const origin = siteOrigin(req);
    const session = await stripe('checkout/sessions', {
      mode: 'subscription',
      customer: customerId,
      'line_items[0][price]': priceId,
      'line_items[0][quantity]': '1',
      client_reference_id: accountId,
      'subscription_data[metadata][account_id]': accountId,
      allow_promotion_codes: 'true',
      success_url: `${origin}/#account?checkout=success`,
      cancel_url: `${origin}/#account?checkout=cancel`,
    });
    return json({ url: session.url }, 200);
  } catch (e) {
    return json({ error: `checkout failed: ${(e as Error).message}` }, 502);
  }
}
