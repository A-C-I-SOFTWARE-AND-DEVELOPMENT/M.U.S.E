/**
 * musehq.io chat transport — talks to the repo-root Edge function `/api/chat`.
 *
 * Contract (see api/chat.ts):
 *   POST /api/chat  { model?, messages: {role,content}[] }
 *     headers (optional BYOK): x-provider-key, x-provider-id
 *   -> 200 text/event-stream of OpenAI delta frames:
 *        data: {"choices":[{"delta":{"content":"..."}}]}\n\n
 *        data: [DONE]\n\n
 *   -> 501 { error: "server chat not configured" }  (no server key & no BYOK)
 *   -> 429 { error, scope }  (rate limited)
 *   -> 4xx/5xx { error }     (validation / upstream)
 *
 * This is a plain *text* stream — the public endpoint does not emit tool calls —
 * so the adapter maps deltas into a single streaming assistant text part. Tool
 * cards remain supported by the renderer for a paired-gateway transport.
 */

export interface WireMessage {
  role: "system" | "user" | "assistant"
  content: string
}

export interface StreamHandlers {
  onDelta: (text: string) => void
  onDone: () => void
  onError: (err: { status?: number; message: string; code?: string }) => void
}

export interface StreamOptions {
  model?: string
  byokKey?: string
  byokProvider?: string
  signal?: AbortSignal
}

/** Readiness probe: is `/api/chat` served by this deployment (server key or BYOK)? */
export async function probeChatReady(): Promise<"ready" | "needs-key" | "none"> {
  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [] }),
    })
    // 400 "messages required" means the function is present & configured.
    if (r.status === 400) return "ready"
    if (r.status === 501) return "needs-key"
    if (r.ok) return "ready"
    return "needs-key"
  } catch {
    return "none"
  }
}

export async function streamChat(
  messages: WireMessage[],
  handlers: StreamHandlers,
  opts: StreamOptions = {},
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (opts.byokKey) headers["x-provider-key"] = opts.byokKey
  if (opts.byokProvider) headers["x-provider-id"] = opts.byokProvider

  let resp: Response
  try {
    resp = await fetch("/api/chat", {
      method: "POST",
      headers,
      body: JSON.stringify({ model: opts.model ?? "auto", messages }),
      signal: opts.signal,
    })
  } catch (e) {
    if ((e as Error).name === "AbortError") return
    handlers.onError({ message: `network error: ${(e as Error).message}` })
    return
  }

  if (!resp.ok || !resp.body) {
    let message = `request failed (${resp.status})`
    let code: string | undefined
    try {
      const body = await resp.json()
      if (body?.error) message = String(body.error)
      if (body?.scope) code = String(body.scope)
    } catch {
      /* non-JSON error body */
    }
    handlers.onError({ status: resp.status, message, code })
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let done = false

  // Returns true if [DONE] was seen (caller should stop).
  const drainFrame = (frame: string): boolean => {
    for (const line of frame.split(/\r?\n/)) {
      const trimmed = line.trim()
      if (!trimmed.startsWith("data:")) continue
      const data = trimmed.slice(5).trim()
      if (data === "[DONE]") return true
      try {
        const json = JSON.parse(data)
        const delta = json?.choices?.[0]?.delta?.content
        if (typeof delta === "string" && delta) handlers.onDelta(delta)
      } catch {
        /* ignore keep-alive / non-JSON frames */
      }
    }
    return false
  }

  try {
    for (;;) {
      const { value, done: rdone } = await reader.read()
      if (rdone) break
      buffer += decoder.decode(value, { stream: true })

      // SSE frames are separated by a blank line (tolerate CRLF).
      const parts = buffer.split(/\r?\n\r?\n/)
      buffer = parts.pop() ?? "" // keep the last (possibly partial) frame
      for (const frame of parts) {
        if (drainFrame(frame)) {
          done = true
          handlers.onDone()
          return
        }
      }
    }
    // Flush any residual buffered frame (abnormal truncation without a trailing
    // blank line) before completing, so the final delta is never dropped.
    if (!done && buffer.trim()) drainFrame(buffer)
    handlers.onDone()
  } catch (e) {
    if ((e as Error).name === "AbortError") return
    handlers.onError({ message: `stream error: ${(e as Error).message}` })
  }
}
