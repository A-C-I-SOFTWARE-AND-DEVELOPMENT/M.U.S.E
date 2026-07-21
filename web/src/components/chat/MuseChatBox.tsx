/**
 * MuseChatBox — the floating M.U.S.E. chat dock.
 *
 * A collapsible dock pinned bottom-right on every dashboard page. Unlike
 * the xterm.js PTY tab (/chat) it talks to the muse agent directly over
 * the tui_gateway JSON-RPC sidecar (`GatewayClient` → /api/ws), the same
 * protocol the Ink TUI speaks over stdio:
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
 * (`rendered` payloads are terminal-ANSI renderings for Ink — the dock
 * always consumes the raw `text` field and renders via <Markdown />.)
 *
 * Slash commands run through the shared pipeline in lib/slashExec.ts
 * (slash.exec → command.dispatch fallback) with autocomplete from
 * components/SlashPopover.tsx (complete.slash).
 *
 * Session continuity: one gateway session per dock lifetime, created
 * lazily on the first message; the websocket connects lazily on first
 * expand. Rendered only when the dashboard was started with embedded
 * chat (`hermes dashboard --tui`) — the /api/ws route 4403s otherwise.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { AlertCircle, RotateCcw, SendHorizontal, X } from "lucide-react";

import { Markdown } from "@/components/Markdown";
import {
  SlashPopover,
  type SlashPopoverHandle,
} from "@/components/SlashPopover";
import { isDashboardEmbeddedChatEnabled } from "@/lib/dashboard-flags";
import {
  GatewayClient,
  type ConnectionState,
  type GatewayEvent,
} from "@/lib/gatewayClient";
import { executeSlash } from "@/lib/slashExec";
import { cn } from "@/lib/utils";

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

function shortModel(model: string): string {
  const parts = model.split("/");
  return parts[parts.length - 1] || model;
}

const DOT_COLOR: Record<ConnectionState, string> = {
  idle: "var(--fg-faint)",
  connecting: "var(--warn)",
  open: "var(--ok)",
  closed: "var(--fg-faint)",
  error: "var(--err)",
};

function friendlyConnectError(msg: string): string {
  if (/token/i.test(msg)) {
    return "Session token unavailable — open this page through `hermes dashboard`.";
  }
  return "Can't reach the muse gateway — is the dashboard running with embedded chat?";
}

/** Observatory sigil — aperture rings + cardinal ticks + center dot. */
function Sigil({ className }: { className?: string }) {
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

export function MuseChatBox() {
  const enabled = isDashboardEmbeddedChatEnabled();

  const [open, setOpen] = useState(false);
  // `version` bumps on manual reconnect; gw is derived so we never call
  // setState for it inside an effect (React 19 set-state-in-effect rule).
  const [version, setVersion] = useState(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const gw = useMemo(() => new GatewayClient(), [version]);

  const [connState, setConnState] = useState<ConnectionState>("idle");
  const [model, setModel] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [portalRoot] = useState<HTMLElement | null>(() =>
    typeof document !== "undefined" ? document.body : null,
  );

  // Refs mirror the bits of state that event callbacks (registered once
  // per gw instance) need to read without going stale.
  const busyRef = useRef(false);
  const streamingIdRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const listEndRef = useRef<HTMLDivElement | null>(null);
  const textRef = useRef<HTMLTextAreaElement | null>(null);
  const slashRef = useRef<SlashPopoverHandle | null>(null);

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
      }
      if (ev.payload?.model) setModel(ev.payload.model);
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

  // Lazy connect: first expand opens the websocket; session.create stays
  // deferred to the first message. Re-expanding after a drop retries.
  useEffect(() => {
    if (!open) return;
    if (
      gw.connectionState === "idle" ||
      gw.connectionState === "closed" ||
      gw.connectionState === "error"
    ) {
      gw.connect().catch((e: unknown) => {
        setError(
          friendlyConnectError(e instanceof Error ? e.message : String(e)),
        );
      });
    }
  }, [open, gw]);

  // Close the websocket with the client instance (reconnect / unmount).
  useEffect(() => () => gw.close(), [gw]);

  // Await the socket actually reaching "open". GatewayClient.connect()
  // no-ops while a connect is already in flight (e.g. the expand effect
  // just fired), so senders subscribe to the state machine instead of
  // racing ahead and issuing requests against a half-open socket.
  const ensureConnected = useCallback(async (): Promise<void> => {
    if (gw.connectionState === "open") return;
    if (gw.connectionState !== "connecting") {
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

  /* ---------------- keyboard / focus / scroll -------------------- */

  // Esc collapses the dock — unless the slash popover already consumed
  // it (it preventDefaults its own Escape to close completions first).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (open) textRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (open) listEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, open]);

  // Composer auto-height: one line at rest, grows to ~6 lines.
  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [input, open]);

  const onComposerKey = (e: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (slashRef.current?.handleKey(e)) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  /* ---------------- render ---------------------------------------- */

  if (!enabled || !portalRoot) return null;

  const streaming = busy || messages.some((m) => m.status === "streaming");
  const fabColor =
    connState === "error"
      ? "var(--err)"
      : open || streaming
        ? "var(--accent)"
        : "color-mix(in srgb, var(--accent) 78%, var(--fg-dim))";

  const dock = (
    <div className="muse-enter fixed bottom-5 right-5 z-[45] flex flex-col items-end gap-3 normal-case">
      {open && (
        <section
          role="dialog"
          aria-label="M.U.S.E. chat"
          className={cn(
            "muse-chat-dock-in flex w-[380px] max-w-[calc(100vw-2.5rem)] flex-col",
            "h-[min(560px,calc(100dvh-7.5rem))] overflow-hidden rounded-lg border",
          )}
          style={{
            background: "var(--bg-elev)",
            borderColor:
              "color-mix(in srgb, var(--midground-base) 14%, transparent)",
            boxShadow: "0 16px 48px rgba(0, 0, 0, 0.55)",
          }}
        >
          {/* Header — wordmark + live state + model + collapse */}
          <header
            className="flex h-11 shrink-0 items-center gap-2 border-b px-3.5"
            style={{
              borderColor:
                "color-mix(in srgb, var(--midground-base) 10%, transparent)",
            }}
          >
            <span className="muse-wordmark font-display text-[0.95rem] font-bold leading-none tracking-[0.04em] text-midground">
              M.U.S.E.
            </span>
            <span
              aria-hidden
              className={cn(
                "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
                connState === "connecting" && "muse-status-dot",
              )}
              style={
                connState === "connecting"
                  ? undefined
                  : { background: DOT_COLOR[connState] }
              }
            />
            <span
              className="ml-auto truncate font-mono-ui text-[0.65rem] tracking-[0.06em]"
              style={{ color: "var(--fg-faint)" }}
            >
              {model
                ? shortModel(model)
                : connState === "open"
                  ? "ready"
                  : connState === "connecting"
                    ? "connecting"
                    : connState === "error"
                      ? "offline"
                      : ""}
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Collapse chat"
              className="muse-press flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-current/5"
              style={{ color: "var(--fg-dim)" }}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </header>

          {/* Error banner — gateway down / session failure, with retry */}
          {error && (
            <div
              role="alert"
              className="flex shrink-0 items-start gap-2 border-b px-3.5 py-2 text-xs"
              style={{
                borderColor:
                  "color-mix(in srgb, var(--err) 25%, transparent)",
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

          {/* Transcript */}
          <div className="muse-chat-scroll min-h-0 flex-1 overflow-y-auto px-3.5 py-3">
            {messages.length === 0 ? (
              <div
                className="flex h-full flex-col items-center justify-center gap-2.5 px-6 text-center"
                style={{ color: "var(--fg-faint)" }}
              >
                <Sigil className="h-7 w-7 opacity-40" />
                <p className="text-sm" style={{ color: "var(--fg-dim)" }}>
                  Ask muse anything.
                </p>
                <p
                  className="text-[0.7rem]"
                  style={{ color: "var(--fg-faint)" }}
                >
                  Type <code className="font-mono-ui">/</code> for commands.
                </p>
              </div>
            ) : (
              messages.map((m) => <MessageRow key={m.id} msg={m} />)
            )}
            <div ref={listEndRef} aria-hidden />
          </div>

          {/* Composer */}
          <div
            className="relative shrink-0 border-t px-3 pb-2 pt-2.5"
            style={{
              borderColor:
                "color-mix(in srgb, var(--midground-base) 10%, transparent)",
            }}
          >
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
                className="min-h-[34px] flex-1 resize-none bg-transparent px-1 py-1.5 text-sm outline-none placeholder:text-[var(--fg-faint)]"
                style={{ color: "var(--fg)" }}
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim() || busy}
                aria-label="Send message"
                className="muse-press mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border transition-opacity disabled:opacity-35"
                style={{
                  borderColor:
                    "color-mix(in srgb, var(--accent) 30%, transparent)",
                  background: "color-mix(in srgb, var(--accent) 10%, transparent)",
                  color: "var(--accent)",
                }}
              >
                <SendHorizontal className="h-3.5 w-3.5" />
              </button>
            </div>
            <div
              className="mt-1 px-1 text-[0.62rem] tracking-[0.04em]"
              style={{ color: "var(--fg-faint)" }}
            >
              Enter to send · Shift+Enter newline · / commands
            </div>
          </div>
        </section>
      )}

      {/* Sigil FAB */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close M.U.S.E. chat" : "Open M.U.S.E. chat"}
        aria-expanded={open}
        data-magnetic
        className={cn(
          "muse-chat-fab muse-press flex h-12 w-12 items-center justify-center rounded-full border",
          !open && "muse-chat-sigil-idle",
        )}
        style={{
          color: fabColor,
          background: "var(--bg-elev)",
          boxShadow: "0 8px 28px rgba(0, 0, 0, 0.5)",
        }}
      >
        {open ? (
          <X className="h-4.5 w-4.5" />
        ) : (
          <Sigil className="h-[22px] w-[22px]" />
        )}
      </button>
    </div>
  );

  return createPortal(dock, portalRoot);
}

/* ------------------------------------------------------------------ */
/*  Message rows                                                       */
/* ------------------------------------------------------------------ */

function MessageRow({ msg }: { msg: ChatMsg }) {
  if (msg.role === "user") {
    return (
      <div className="mb-2.5 flex justify-end">
        <div
          className="max-w-[85%] whitespace-pre-wrap rounded-md border px-3 py-2 text-sm leading-relaxed"
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
        className="mb-2.5 border-l-2 pl-2.5"
        style={{ borderColor: "var(--border)" }}
      >
        <pre
          className="whitespace-pre-wrap font-mono-ui text-[0.72rem] leading-relaxed"
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
        className="mb-3 flex items-center gap-1 py-1"
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
    <div className="mb-3">
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
