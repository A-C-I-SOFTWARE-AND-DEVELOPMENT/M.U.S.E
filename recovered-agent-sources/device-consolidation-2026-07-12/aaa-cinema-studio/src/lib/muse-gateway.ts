'use client'

/**
 * muse gateway client — browser-side.
 *
 * Mirrors the M.U.S.E repo's desktop gateway contract (apps/desktop/ui/src/lib/gateway.ts):
 *   - token in localStorage `muse.cockpit.token`
 *   - base URL in localStorage `muse.gateway.base` (default https://musehq.io)
 *   - chat over POST /v1/jarvis/chat as newline-delimited JSON (NDJSON)
 *   - health over GET /v1/health
 *   - pairing via POST /v1/cockpit/pair/start → POST /v1/cockpit/pair/confirm
 *
 * All calls route through our Next.js proxy (/api/muse-gateway/*) to dodge CORS —
 * the browser cannot reach musehq.io directly. The proxy forwards server-side.
 */

export const TOKEN_KEY = 'muse.cockpit.token'
const BASE_KEY = 'muse.gateway.base'
export const DEFAULT_GATEWAY_BASE = 'https://musehq.io'

export const TOKEN_EVENT = 'muse:token'

function lsGet(k: string): string {
  try {
    return typeof window !== 'undefined' ? window.localStorage.getItem(k) || '' : ''
  } catch {
    return ''
  }
}
function lsSet(k: string, v: string) {
  try {
    if (typeof window !== 'undefined') window.localStorage.setItem(k, v)
  } catch {
    /* ignore */
  }
}

export function getGatewayBase(): string {
  const stored = lsGet(BASE_KEY)
  if (stored) return stored
  return DEFAULT_GATEWAY_BASE
}
export function setGatewayBase(base: string) {
  lsSet(BASE_KEY, base.trim().replace(/\/+$/, ''))
}
export function getToken(): string {
  return lsGet(TOKEN_KEY)
}
export function setToken(token: string) {
  lsSet(TOKEN_KEY, token.trim())
  try {
    window.dispatchEvent(new Event(TOKEN_EVENT))
  } catch {
    /* no window */
  }
}
export function clearToken() {
  lsSet(TOKEN_KEY, '')
  try {
    window.dispatchEvent(new Event(TOKEN_EVENT))
  } catch {
    /* no window */
  }
}

export type HealthResult = { ok: boolean; reachable: boolean; error?: string; status?: number }
export async function pingHealth(base?: string): Promise<HealthResult> {
  try {
    const r = await fetch('/api/muse-gateway/health', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base: base || getGatewayBase() }),
    })
    return await r.json()
  } catch (e: any) {
    return { ok: false, reachable: false, error: e?.message || 'unreachable' }
  }
}

export type PairStartResult = { ok: boolean; pairingCode?: string; error?: string; hint?: string }
export async function pairStart(base: string, deviceName?: string): Promise<PairStartResult> {
  try {
    const r = await fetch('/api/muse-gateway/pair/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base, device_name: deviceName || '' }),
    })
    return await r.json()
  } catch (e: any) {
    return { ok: false, error: e?.message || 'pair/start failed' }
  }
}

export type PairConfirmResult = { ok: boolean; token?: string; forbidden?: boolean; error?: string }
export async function pairConfirm(base: string, pairingCode: string, authorization: string): Promise<PairConfirmResult> {
  try {
    const r = await fetch('/api/muse-gateway/pair/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base, pairing_code: pairingCode, authorization }),
    })
    const j = await r.json()
    if (j.ok && j.token) setToken(j.token)
    return j
  } catch (e: any) {
    return { ok: false, error: e?.message || 'pair/confirm failed' }
  }
}

export type ChatTurn = { role: string; content: string }
export type ChatCallbacks = {
  onDelta?: (accumulated: string) => void
  onError?: (message: string) => void
}

/**
 * POST /v1/jarvis/chat (NDJSON), proxied. Streams the assistant reply line-by-line
 * and returns the final accumulated text. Mirrors the repo's NDJSON parser:
 * each line is a JSON object; assistant content is concatenated.
 */
export async function chat(prompt: string, history: ChatTurn[], cb?: ChatCallbacks): Promise<string> {
  let r: Response
  try {
    r = await fetch('/api/muse-gateway/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base: getGatewayBase(), token: getToken(), prompt, history }),
    })
  } catch {
    cb?.onError?.("Can't reach the gateway — is the brain running?")
    return ''
  }
  if (!r.ok || !r.body) {
    const j = await r.json().catch(() => ({ error: 'error: ' + r.status }))
    cb?.onError?.(j?.error || `error: ${r.status}`)
    return ''
  }
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  let acc = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      let nl: number
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).trim()
        buf = buf.slice(nl + 1)
        if (!line) continue
        try {
          const obj = JSON.parse(line) as Record<string, unknown>
          if (obj.error) {
            acc += '\n[error] ' + String(obj.error)
          } else if (obj.role === 'assistant' && obj.content != null) {
            acc += String(obj.content)
          } else if (obj.content != null && obj.role !== 'user' && obj.role !== 'system') {
            acc += String(obj.content)
          }
        } catch {
          /* ignore partial / non-JSON lines */
        }
        cb?.onDelta?.(acc)
      }
    }
  } catch {
    cb?.onError?.(acc ? acc + '\n[connection lost]' : 'Connection lost mid-reply — try again.')
  }
  return acc
}
