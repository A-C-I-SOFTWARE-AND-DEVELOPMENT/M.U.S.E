import { NextRequest } from 'next/server'
import { json, err } from '@/lib/server-utils'

export const dynamic = 'force-dynamic'
export const maxDuration = 20

// POST /api/muse-gateway/health
// body: { base }
// Proxies GET ${base}/v1/health — server-side to dodge browser CORS.
export async function POST(req: NextRequest) {
  try {
    const { base } = await req.json()
    const url = (base || '').trim().replace(/\/+$/, '')
    if (!url) return err('base required', 400)
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(), 8000)
    try {
      const r = await fetch(`${url}/v1/health`, {
        method: 'GET',
        signal: ctrl.signal,
        headers: { Accept: 'application/json' },
      })
      clearTimeout(t)
      return json({ ok: r.ok, status: r.status, reachable: r.ok })
    } catch (e: any) {
      clearTimeout(t)
      return json({ ok: false, reachable: false, error: e?.name === 'AbortError' ? 'timeout' : (e?.message || 'unreachable') })
    }
  } catch (e: any) {
    return err(e?.message ?? 'health failed')
  }
}
