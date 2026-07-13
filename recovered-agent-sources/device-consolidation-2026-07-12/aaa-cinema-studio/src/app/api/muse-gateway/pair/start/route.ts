import { NextRequest } from 'next/server'
import { json, err } from '@/lib/server-utils'

export const dynamic = 'force-dynamic'
export const maxDuration = 20

// POST /api/muse-gateway/pair/start
// body: { base, device_name }
// Proxies POST ${base}/v1/cockpit/pair/start — unauthenticated (new device).
export async function POST(req: NextRequest) {
  try {
    const { base, device_name } = await req.json()
    const url = (base || '').trim().replace(/\/+$/, '')
    if (!url) return err('base required', 400)
    const r = await fetch(`${url}/v1/cockpit/pair/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_name: (device_name || '').trim() }),
    })
    const data = await r.json().catch(() => ({}))
    if (!r.ok) {
      return json({ ok: false, error: String(data?.error ?? r.status), hint: data?.hint ? String(data.hint) : undefined }, r.status as any)
    }
    return json({ ok: true, pairingCode: String(data?.pairing_code ?? '') })
  } catch (e: any) {
    return err(e?.message ?? 'pair/start failed')
  }
}
