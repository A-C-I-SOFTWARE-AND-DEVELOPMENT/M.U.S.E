import { NextRequest } from 'next/server'
import { json, err } from '@/lib/server-utils'

export const dynamic = 'force-dynamic'
export const maxDuration = 20

// POST /api/muse-gateway/pair/confirm
// body: { base, pairing_code, authorization }
// Proxies POST ${base}/v1/cockpit/pair/confirm → returns { token }.
export async function POST(req: NextRequest) {
  try {
    const { base, pairing_code, authorization } = await req.json()
    const url = (base || '').trim().replace(/\/+$/, '')
    if (!url) return err('base required', 400)
    if (!pairing_code) return err('pairing_code required', 400)
    const r = await fetch(`${url}/v1/cockpit/pair/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pairing_code, authorization: authorization || '' }),
    })
    const data = await r.json().catch(() => ({}))
    if (r.status === 403) return json({ ok: false, forbidden: true }, 403)
    if (!r.ok || !data?.token) {
      return json({ ok: false, error: String(data?.error ?? r.status) }, r.status as any)
    }
    return json({ ok: true, token: String(data.token) })
  } catch (e: any) {
    return err(e?.message ?? 'pair/confirm failed')
  }
}
