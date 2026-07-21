/**
 * ChatMode — the full-page conversational chat with the muse agent.
 *
 * This is the primary mode of the /chat tab: a calm, centered reading
 * column with a streaming transcript and a composer at the bottom. It
 * speaks to the muse agent directly over the tui_gateway JSON-RPC sidecar
 * (`GatewayClient` → /api/ws), the same protocol the Ink TUI speaks over
 * stdio and the same one the floating MuseChatBox dock uses:
 *
 *   gw.request("session.create")                → { session_id }
 *   gw.request("prompt.submit", {session_id, text}) → { status: "streaming" }
 *   …then the server pushes newline-delimited events:
 *     message.start      (no payload)               turn opened
 *     message.delta      { text, rendered? }        streamed increment
 *     message.complete   { text, status, warning? } turn closed
 *     error              { message }                turn/session failure
 *     session.info       { model, provider, cwd? }  session metadata
 *
 * (`rendered` payloads are terminal-ANSI renderings for Ink — the page
 * always consumes the raw `text` field and renders via <Markdown />.)
 *
 * Slash commands run through the shared pipeline in lib/slashExec.ts
 * (slash.exec → command.dispatch fallback) with autocomplete from
 * components/SlashPopover.tsx (complete.slash).
 *
 * Session continuity: one gateway session per page lifetime, created
 * lazily on the first message; the websocket connects lazily the first
 * time the tab becomes visible. ChatPage mounts this component
 * persistently, so transcript + session survive tab switches and
 * chat/terminal mode toggles. Status (connection, model, session) is
 * reported to the host via `onStatus` for the tab header strip.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { AlertCircle, Plus, RotateCcw, SendHorizontal } from "lucide-react";

import { Markdown } from "@/components/Markdown";
import {
  SlashPopover,
  type SlashPopoverHandle,
} from "@/components/SlashPopover";
import {
  GatewayClient,
  type ConnectionState,
  type GatewayEvent,
} from "@/lib/gatewayClient";
import { executeSlash } from "@/lib/slashExec";

import "./muse-chat.css";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type MsgStatus = "streaming" | "complete" | "interrupted" | "error";

interface ChatMsg {
  id: string;
  role: "user" | "muse" | "system";
  text: string;
  status?: MsgStatus;
  warning?: string;
}

/** Status snapshot reported to the ChatPage host for the header strip. */
export interface ChatModeStatus {
  connState: ConnectionState;
  model: string | null;
  provider: string | null;
  sessionId: string | null;
}

interface SessionInfoPayload {
  model?: string;
  provider?: string;
}

interface CompletePayload {
  text?: string;
  status?: string;
  warning?: string;
}

/* ------------------------------------------------------------------ */
/*  Small helpers                                                      */
/* ------------------------------------------------------------------ */

let msgSeq = 0;
function nextId(): string {
  return `m${Date.now().toString(36)}-${++msgSeq}`;
}

function friendlyConnectError(msg: string): string {
  if (/token/i.test(msg)) {
    return "Session token unavailable — open this page through `hermes dashboard`.";
  }
  return "Can't reach the muse gateway — is the dashboard running with embedded chat?";
}

/** Observatory sigil — aperture rings + cardinal ticks + center dot. */
export function ChatSigil({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden className={className}>
      <circle
        cx="12"
        cy="12"
        r="7.25"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeOpacity="0.85"
      />
      <path
        d="M12 2.25v2.5M12 19.25v2.5M2.25 12h2.5M19.25 12h2.5"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeOpacity="0.45"
      />
      <circle cx="12" cy="12" r="2.4" fill="currentColor" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function ChatMode({
  isActive = true,
  onStatus,
}: {
  isActive?: boolean;
  onStatus?: (status: ChatModeStatus) => void;
}) {
  // `version` bumps on manual reconnect; gw is derived so we never call
  // setState for it inside an effect (React 19 set-state-in-effect rule).
  const [version, setVersion] = useState(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const gw = useMemo(() => new GatewayClient(), [version]);

  const [connState, setConnState] = useState<ConnectionState>("idle");
  const [model, setModel] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");

  // Refs mirror the bits of state that event callbacks (registered once
  // per gw instance) need to read without going stale.
  const busyRef = useRef(false);
  const streamingIdRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const textRef = useRef<HTMLTextAreaElement | null>(null);
  const slashRef = useRef<SlashPopoverHandle | null>(null);
  // Scroll pinning: stay glued to the tail while streaming unless the
  // user has scrolled up to read — then leave their position alone.
  const stickToBottomRef = useRef(true);

  const matchSession = useCallback(
    (ev: GatewayEvent) =>
      !ev.session_id ||
      !sessionIdRef.current ||
      ev.session_id === sessionIdRef.current,
    [],
  );

  /* ---------------- gateway event subscriptions ------------------ */

  useEffect(() => {
    const offState = gw.onState((s) => {
      setConnState(s);
      if (s === "closed" || s === "error") {
        const id = streamingIdRef.current;
        if (id) {
          streamingIdRef.current = null;
          busyRef.current = false;
          setBusy(false);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === id && m.status === "streaming"
                ? { ...m, status: "error", warning: "connection lost" }
                : m,
            ),
          );
        }
      }
    });

    const offInfo = gw.on<SessionInfoPayload>("session.info", (ev) => {
      if (ev.session_id && !sessionIdRef.current) {
        sessionIdRef.current = ev.session_id;
        setSessionId(ev.session_id);
      }
      if (ev.payload?.model) setModel(ev.payload.model);
      if (ev.payload?.provider) setProvider(ev.payload.provider);
    });

    const offStart = gw.on("message.start", (ev) => {
      if (!matchSession(ev)) return;
      busyRef.current = true;
      setBusy(true);
      // send() pre-creates the streaming placeholder; a turn opened by
      // the server itself (background notification) needs one here.
      if (!streamingIdRef.current) {
        const id = nextId();
        streamingIdRef.current = id;
        setMessages((prev) => [
          ...prev,
          { id, role: "muse", text: "", status: "streaming" },
        ]);
      }
    });

    const offDelta = gw.on<{ text?: string }>("message.delta", (ev) => {
      if (!matchSession(ev)) return;
      const delta = ev.payload?.text ?? "";
      const id = streamingIdRef.current;
      if (!id || !delta) return;
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, text: m.text + delta } : m)),
      );
    });

    const offComplete = gw.on<CompletePayload>("message.complete", (ev) => {
      if (!matchSession(ev)) return;
      const id = streamingIdRef.current;
      const p = ev.payload ?? {};
      const status: MsgStatus =
        p.status === "error" || p.status === "interrupted"
          ? p.status
          : "complete";
      if (id) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === id
              ? {
                  ...m,
                  text: p.text || m.text,
                  status,
                  warning: p.warning ?? m.warning,
                }
              : m,
          ),
        );
      } else if (p.text) {
        setMessages((prev) => [
          ...prev,
          { id: nextId(), role: "muse", text: p.text!, status, warning: p.warning },
        ]);
      }
      streamingIdRef.current = null;
      busyRef.current = false;
      setBusy(false);
    });

    const offError = gw.on<{ message?: string }>("error", (ev) => {
      if (!matchSession(ev)) return;
      const message = ev.payload?.message ?? "unknown gateway error";
      const id = streamingIdRef.current;
      if (id) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === id ? { ...m, status: "error", warning: message } : m,
          ),
        );
        streamingIdRef.current = null;
        busyRef.current = false;
        setBusy(false);
      } else {
        setError(message);
      }
    });

    return () => {
      offState();
      offInfo();
      offStart();
      offDelta();
      offComplete();
      offError();
    };
  }, [gw, matchSession]);

  /* ---------------- connection lifecycle ------------------------- */

  // Lazy connect: the first time the /chat tab becomes visible opens the
  // websocket; session.create stays deferred to the first message.
  // Returning to the tab after a drop retries.
  useEffect(() => {
    if (!isActive) return;
    if (
      gw.state === "idle" ||
      gw.state === "closed" ||
      gw.state === "error"
    ) {
      gw.connect().catch((e: unknown) => {
        setError(
          friendlyConnectError(e instanceof Error ? e.message : String(e)),
        );
      });
    }
  }, [isActive, gw]);

  // Close the websocket with the client instance (reconnect / unmount).
  useEffect(() => () => gw.close(), [gw]);

  // Await the socket actually reaching "open". GatewayClient.connect()
  // no-ops while a connect is already in flight (e.g. the activate effect
  // just fired), so senders subscribe to the state machine instead of
  // racing ahead and issuing requests against a half-open socket.
  const ensureConnected = useCallback(async (): Promise<void> => {
    if (gw.state === "open") return;
    if (gw.state !== "connecting") {
      // Failure surfaces through the "error" state transition below.
      gw.connect().catch(() => {});
    }
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        off();
        reject(new Error("gateway connection timed out"));
      }, 15_000);
      const off = gw.onState((s) => {
        if (s === "open") {
          clearTimeout(timer);
          off();
          resolve();
        } else if (s === "error" || s === "closed") {
          clearTimeout(timer);
          off();
          reject(new Error("gateway connection failed"));
        }
      });
    });
  }, [gw]);

  const ensureSession = useCallback(async (): Promise<string> => {
    if (sessionIdRef.current) return sessionIdRef.current;
    const r = await gw.request<{ session_id?: string }>("session.create", {});
    const sid = r?.session_id ?? "";
    if (!sid) throw new Error("session.create returned no session id");
    sessionIdRef.current = sid;
    setSessionId(sid);
    return sid;
  }, [gw]);

  const reconnect = useCallback(() => {
    setError(null);
    sessionIdRef.current = null;
    streamingIdRef.current = null;
    busyRef.current = false;
    setBusy(false);
    setVersion((v) => v + 1);
  }, []);

  // Start a fresh conversation: drop the gateway session handle and clear
  // the transcript. The next message lazily creates a new session.
  const newSession = useCallback(() => {
    if (busyRef.current) return;
    sessionIdRef.current = null;
    streamingIdRef.current = null;
    setSessionId(null);
    setMessages([]);
    setError(null);
    stickToBottomRef.current = true;
    textRef.current?.focus();
  }, []);

  /* ---------------- sending -------------------------------------- */

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || busyRef.current) return;

      const draftId = nextId();
      busyRef.current = true;
      setBusy(true);
      setError(null);
      streamingIdRef.current = draftId;
      stickToBottomRef.current = true;
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", text },
        { id: draftId, role: "muse", text: "", status: "streaming" },
      ]);
      setInput("");

      try {
        await ensureConnected();
        const sid = await ensureSession();
        // Resolves as soon as the server accepts the turn; the response
        // itself arrives through the message.* events above.
        await gw.request("prompt.submit", { session_id: sid, text });
      } catch (e) {
        streamingIdRef.current = null;
        busyRef.current = false;
        setBusy(false);
        const msg = e instanceof Error ? e.message : String(e);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === draftId
              ? {
                  ...m,
                  status: "error",
                  warning: /busy/i.test(msg)
                    ? "muse is still answering — try again in a moment"
                    : friendlyConnectError(msg),
                }
              : m,
          ),
        );
        setInput(text); // restore the draft so nothing is lost
      }
    },
    [gw, ensureConnected, ensureSession],
  );

  const runSlash = useCallback(
    async (command: string) => {
      if (busyRef.current) return;
      busyRef.current = true;
      setBusy(true);
      setError(null);
      setMessages((prev) => [...prev, { id: nextId(), role: "user", text: command }]);
      setInput("");

      const sys = (t: string) =>
        setMessages((prev) => [...prev, { id: nextId(), role: "system", text: t }]);

      try {
        await ensureConnected();
        const sid = await ensureSession();
        await executeSlash({
          command,
          sessionId: sid,
          gw,
          callbacks: {
            sys,
            // skill/send directives route back through the normal turn
            // pipeline, which takes over the busy flag itself.
            send: async (msg) => {
              busyRef.current = false;
              await send(msg);
            },
          },
        });
      } catch (e) {
        sys(`error: ${e instanceof Error ? e.message : String(e)}`);
      } finally {
        // When a nested send() opened a streaming turn it owns busy now.
        if (!streamingIdRef.current) {
          busyRef.current = false;
          setBusy(false);
        }
      }
    },
    [gw, ensureConnected, ensureSession, send],
  );

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || busyRef.current) return;
    if (text.startsWith("/")) void runSlash(text);
    else void send(text);
  }, [input, send, runSlash]);

  /* ---------------- status report to the host --------------------- */

  useEffect(() => {
    onStatus?.({ connState, model, provider, sessionId });
  }, [onStatus, connState, model, provider, sessionId]);

  /* ---------------- keyboard / focus / scroll -------------------- */

  // Focus the composer whenever the tab (or chat mode) becomes visible.
  useEffect(() => {
    if (isActive) textRef.current?.focus();
  }, [isActive]);

  // Pin to the transcript tail on new content — unless the user scrolled
  // up to read, in which case their position is preserved.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottomRef.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const onTranscriptScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    stickToBottomRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  }, []);

  // Composer auto-height: one line at rest, grows to ~7 lines.
  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }, [input]);

  const onComposerKey = (e: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (slashRef.current?.handleKey(e)) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  /* ---------------- render ---------------------------------------- */

  const streaming = busy || messages.some((m) => m.status === "streaming");

  return (
    <div className="flex min-h-0 flex-1 flex-col normal-case">
      {/* Error banner — gateway down / session failure, with retry */}
      {error && (
        <div
          role="alert"
          className="mx-auto mb-2 flex w-full max-w-[46rem] shrink-0 items-start gap-2 rounded-md border px-3.5 py-2 text-xs"
          style={{
            borderColor: "color-mix(in srgb, var(--err) 25%, transparent)",
            background: "color-mix(in srgb, var(--err) 8%, transparent)",
            color: "var(--err)",
          }}
        >
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0 flex-1 leading-relaxed">{error}</span>
          <button
            type="button"
            onClick={reconnect}
            aria-label="Reconnect"
            title="Reconnect"
            className="muse-press flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-current/10"
          >
            <RotateCcw className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* Transcript — centered reading column, generous measure */}
      <div
        ref={scrollRef}
        onScroll={onTranscriptScroll}
        className="muse-chat-scroll min-h-0 flex-1 overflow-y-auto"
      >
        <div className="mx-auto w-full max-w-[46rem] px-4 py-6 sm:px-6">
          {messages.length === 0 ? (
            <div
              className="flex min-h-[50vh] flex-col items-center justify-center gap-3 px-6 text-center"
              style={{ color: "var(--fg-faint)" }}
            >
              <ChatSigil className="h-9 w-9 opacity-40" />
              <p className="text-base" style={{ color: "var(--fg-dim)" }}>
                Ask muse anything.
              </p>
              <p className="text-[0.72rem]" style={{ color: "var(--fg-faint)" }}>
                Type <code className="font-mono-ui">/</code> for commands.
              </p>
            </div>
          ) : (
            messages.map((m) => <MessageRow key={m.id} msg={m} />)
          )}
        </div>
      </div>

      {/* Composer */}
      <div
        className="relative shrink-0 border-t"
        style={{
          borderColor: "color-mix(in srgb, var(--midground-base) 10%, transparent)",
        }}
      >
        <div className="mx-auto w-full max-w-[46rem] px-4 pb-2 pt-3 sm:px-6">
          <SlashPopover
            ref={slashRef}
            input={input}
            gw={connState === "open" ? gw : null}
            onApply={setInput}
          />
          <div className="flex items-end gap-2">
            <textarea
              ref={textRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onComposerKey}
              rows={1}
              placeholder="Message muse…"
              aria-label="Message muse"
              className="min-h-[36px] flex-1 resize-none bg-transparent px-1 py-1.5 text-[0.925rem] leading-relaxed outline-none placeholder:text-[var(--fg-faint)]"
              style={{ color: "var(--fg)" }}
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() || busy}
              aria-label="Send message"
              className="muse-press mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border transition-opacity disabled:opacity-35"
              style={{
                borderColor: "color-mix(in srgb, var(--accent) 30%, transparent)",
                background: "color-mix(in srgb, var(--accent) 10%, transparent)",
                color: "var(--accent)",
              }}
            >
              <SendHorizontal className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="mt-1 flex items-center gap-2 px-1 pb-1">
            <span
              className="text-[0.62rem] tracking-[0.04em]"
              style={{ color: "var(--fg-faint)" }}
            >
              Enter to send · Shift+Enter newline · / commands
            </span>
            {streaming && (
              <span
                className="text-[0.62rem] tracking-[0.04em]"
                style={{ color: "var(--accent-dim)" }}
              >
                muse is answering…
              </span>
            )}
            {messages.length > 0 && !busy && (
              <button
                type="button"
                onClick={newSession}
                className="muse-press ml-auto inline-flex items-center gap-1 rounded px-1 py-0.5 text-[0.62rem] tracking-[0.04em] transition-colors hover:bg-current/5"
                style={{ color: "var(--fg-faint)" }}
                title="Start a new session"
              >
                <Plus className="h-3 w-3" />
                new session
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Message rows                                                       */
/* ------------------------------------------------------------------ */

function MessageRow({ msg }: { msg: ChatMsg }) {
  if (msg.role === "user") {
    return (
      <div className="mb-3 flex justify-end">
        <div
          className="max-w-[80%] whitespace-pre-wrap rounded-md border px-3.5 py-2 text-[0.925rem] leading-relaxed"
          style={{
            background: "color-mix(in srgb, var(--accent) 13%, transparent)",
            borderColor: "color-mix(in srgb, var(--accent) 24%, transparent)",
            color: "var(--fg)",
          }}
        >
          {msg.text}
        </div>
      </div>
    );
  }

  if (msg.role === "system") {
    return (
      <div
        className="mb-3 border-l-2 pl-3"
        style={{ borderColor: "var(--border)" }}
      >
        <pre
          className="whitespace-pre-wrap font-mono-ui text-[0.75rem] leading-relaxed"
          style={{ color: "var(--fg-dim)" }}
        >
          {msg.text}
        </pre>
      </div>
    );
  }

  // muse turn
  if (msg.status === "streaming" && !msg.text) {
    return (
      <div
        className="mb-4 flex items-center gap-1 py-1"
        role="status"
        aria-label="muse is thinking"
      >
        <span
          className="muse-chat-typing-dot h-1.5 w-1.5 rounded-full"
          style={{ background: "var(--accent-dim)" }}
        />
        <span
          className="muse-chat-typing-dot h-1.5 w-1.5 rounded-full"
          style={{ background: "var(--accent-dim)" }}
        />
        <span
          className="muse-chat-typing-dot h-1.5 w-1.5 rounded-full"
          style={{ background: "var(--accent-dim)" }}
        />
      </div>
    );
  }

  return (
    <div className="mb-4">
      {msg.text ? (
        <Markdown content={msg.text} streaming={msg.status === "streaming"} />
      ) : null}
      {msg.warning ? (
        <div
          className="mt-1 text-[0.72rem] leading-relaxed"
          style={{
            color: msg.status === "error" ? "var(--err)" : "var(--warn)",
          }}
        >
          {msg.warning}
        </div>
      ) : null}
      {msg.status === "interrupted" ? (
        <div className="mt-1 text-[0.72rem]" style={{ color: "var(--warn)" }}>
          interrupted
        </div>
      ) : null}
    </div>
  );
}
