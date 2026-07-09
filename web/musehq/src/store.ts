import { createStore, produce } from "solid-js/store"
import { createMemo } from "solid-js"
import type { MessageV2 } from "../vendor/opencode/message-v2"
import { streamChat, probeChatReady, type WireMessage } from "./api"

export type MessageWithParts = MessageV2.Info & { parts: MessageV2.Part[] }

export interface Session {
  id: string
  title: string
  createdAt: number
  messages: MessageWithParts[]
}

export type ChatStatus = "idle" | "streaming" | "error"
export type Readiness = "unknown" | "ready" | "needs-key" | "none"

interface State {
  sessions: Session[]
  activeId: string
  status: ChatStatus
  // Id of the session whose assistant turn is currently streaming (or null).
  // Streaming is single-flight (one AbortController), but this is per-session so
  // switching sessions mid-stream doesn't show a false "responding" state or let
  // another session's Stop button abort an unrelated stream.
  streamingId: string | null
  readiness: Readiness
  banner: string | null
  model: string
  byokKey: string
  byokProvider: string
}

let seq = 0
function uid(prefix: string): string {
  seq += 1
  const rand = Math.random().toString(36).slice(2, 8)
  return `${prefix}_${Date.now().toString(36)}${seq.toString(36)}${rand}`
}

function newSession(): Session {
  return { id: uid("ses"), title: "New conversation", createdAt: Date.now(), messages: [] }
}

const first = newSession()

const [state, setState] = createStore<State>({
  sessions: [first],
  activeId: first.id,
  status: "idle",
  streamingId: null,
  readiness: "unknown",
  banner: null,
  model: "auto",
  byokKey: "",
  byokProvider: "",
})

let abort: AbortController | null = null

function activeIndex(): number {
  return state.sessions.findIndex((s) => s.id === state.activeId)
}

export const store = {
  state,

  activeSession: createMemo(() => state.sessions.find((s) => s.id === state.activeId) ?? state.sessions[0]),

  async probe() {
    const r = await probeChatReady()
    setState("readiness", r)
    if (r === "needs-key") {
      setState(
        "banner",
        "Public chat isn't configured on this deployment yet. Open Muse Omni (/) to Connect a gateway, or set a server provider key.",
      )
    } else if (r === "none") {
      setState(
        "banner",
        "No /api backend detected — open Muse Omni (/) and pair a muse gateway to chat.",
      )
    } else {
      setState("banner", null)
    }
  },

  setModel(model: string) {
    setState("model", model)
  },

  setByok(key: string, provider: string) {
    setState("byokKey", key)
    setState("byokProvider", provider)
  },

  selectSession(id: string) {
    setState("activeId", id)
  },

  startNewSession() {
    if (state.streamingId) abort?.abort()
    const s = newSession()
    setState(
      produce((st) => {
        st.sessions.unshift(s)
        st.activeId = s.id
        st.status = "idle"
        st.streamingId = null
      }),
    )
  },

  stop() {
    abort?.abort()
    setState(
      produce((st) => {
        st.status = "idle"
        st.streamingId = null
      }),
    )
  },

  async send(text: string) {
    const body = text.trim()
    // Single-flight: block a new send while any session is streaming.
    if (!body || state.streamingId) return

    const idx = activeIndex()
    if (idx < 0) return
    const sid = state.sessions[idx].id
    const now = Date.now()

    const userMsg: MessageWithParts = {
      id: uid("msg"),
      sessionID: sid,
      role: "user",
      time: { created: now },
      agent: "user",
      model: { providerID: "", modelID: "" },
      parts: [{ id: uid("prt"), sessionID: sid, messageID: "", type: "text", text: body }],
    }
    userMsg.parts[0].messageID = userMsg.id

    const asstId = uid("msg")
    const textPartId = uid("prt")
    const asstMsg: MessageWithParts = {
      id: asstId,
      sessionID: sid,
      role: "assistant",
      time: { created: now + 1 },
      parentID: userMsg.id,
      modelID: state.model,
      providerID: state.byokProvider || "muse",
      mode: "build",
      agent: "build",
      path: { cwd: "", root: "" },
      cost: 0,
      tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
      parts: [{ id: textPartId, sessionID: sid, messageID: asstId, type: "text", text: "", time: { start: now + 1 } }],
    }

    setState(
      produce((st) => {
        const s = st.sessions.find((x) => x.id === sid)!
        s.messages.push(userMsg, asstMsg)
        if (s.messages.length <= 2) s.title = body.slice(0, 48) || "New conversation"
        st.status = "streaming"
        st.streamingId = sid
        st.banner = null
      }),
    )

    // Build the wire history from the session's text parts.
    const wire: WireMessage[] = []
    for (const m of state.sessions[activeIndex()].messages) {
      if (m.id === asstId) continue
      const txt = m.parts
        .filter((p): p is MessageV2.TextPart => p.type === "text")
        .map((p) => p.text)
        .join("\n")
        .trim()
      if (txt) wire.push({ role: m.role === "assistant" ? "assistant" : "user", content: txt })
    }

    abort = new AbortController()

    const patchText = (mutate: (prev: string) => string) => {
      setState(
        produce((st) => {
          const s = st.sessions.find((x) => x.id === sid)
          const m = s?.messages.find((x) => x.id === asstId)
          const part = m?.parts.find((p) => p.id === textPartId)
          if (part && part.type === "text") part.text = mutate(part.text)
        }),
      )
    }

    await streamChat(
      wire,
      {
        onDelta: (delta) => patchText((prev) => prev + delta),
        onDone: () => {
          setState(
            produce((st) => {
              const s = st.sessions.find((x) => x.id === sid)
              const m = s?.messages.find((x) => x.id === asstId)
              if (m && m.role === "assistant") {
                m.time.completed = Date.now()
                const part = m.parts.find((p) => p.id === textPartId)
                if (part && part.type === "text" && !part.text) {
                  part.text = "_(no content returned)_"
                }
              }
              st.status = "idle"
              if (st.streamingId === sid) st.streamingId = null
            }),
          )
        },
        onError: (err) => {
          setState(
            produce((st) => {
              const s = st.sessions.find((x) => x.id === sid)
              const m = s?.messages.find((x) => x.id === asstId)
              if (m && m.role === "assistant") {
                m.error = { name: "APIError", data: { message: err.message } }
              }
              st.status = "error"
              if (st.streamingId === sid) st.streamingId = null
              st.banner =
                err.status === 501
                  ? "Public chat isn't configured on this deployment. Add a provider key via Connect, or pair a gateway."
                  : err.status === 429
                    ? "Rate limit reached — give it a moment and try again."
                    : `Chat error: ${err.message}`
            }),
          )
        },
      },
      {
        model: state.model,
        byokKey: state.byokKey || undefined,
        byokProvider: state.byokProvider || undefined,
        signal: abort.signal,
      },
    )
  },
}

export { setState }
