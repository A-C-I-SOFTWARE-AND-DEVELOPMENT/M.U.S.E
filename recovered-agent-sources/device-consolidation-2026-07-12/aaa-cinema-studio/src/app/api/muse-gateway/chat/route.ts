import { NextRequest } from 'next/server'
import { err } from '@/lib/server-utils'

export const dynamic = 'force-dynamic'
export const maxDuration = 180

// POST /api/muse-gateway/chat
// body: { base, token, prompt, history }
// Proxies POST ${base}/v1/jarvis/chat (NDJSON streaming) — server-side to dodge
// browser CORS. Streams the upstream NDJSON body straight back to the client.
export async function POST(req: NextRequest) {
  try {
    const { base, token, prompt, history } = await req.json()
    const url = (base || '').trim().replace(/\/+$/, '')
    if (!url) return err('base required', 400)
    if (!prompt) return err('prompt required', 400)

    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = 'Bearer ' + token

    const upstream = await fetch(`${url}/v1/jarvis/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ prompt, history: history || [] }),
    })

    if (!upstream.ok || !upstream.body) {
      const text = await upstream.text().catch(() => '')
      const msg =
        upstream.status === 401
          ? 'Not paired — connect this device in the Gateway Bridge first.'
          : upstream.status === 503
            ? "Can't reach the gateway — is the brain running?"
            : `error: ${upstream.status}${text ? ' — ' + text.slice(0, 200) : ''}`
      return err(msg, upstream.status as any)
    }

    // Stream the NDJSON body straight through.
    const stream = new ReadableStream({
      async start(controller) {
        const reader = upstream.body!.getReader()
        const enc = new TextEncoder()
        try {
          for (;;) {
            const { value, done } = await reader.read()
            if (done) break
            controller.enqueue(value)
          }
        } catch (e: any) {
          controller.enqueue(enc.encode(`\n{"error":"stream lost: ${e?.message || ''}"}\n`))
        } finally {
          controller.close()
        }
      },
    })

    return new Response(stream, {
      headers: {
        'Content-Type': 'application/x-ndjson; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
      },
    })
  } catch (e: any) {
    return err(e?.message ?? 'chat proxy failed')
  }
}
