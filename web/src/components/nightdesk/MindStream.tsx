/**
 * MindStream — Night Desk "Mind" view (mockup 2 center column).
 *
 * The live chat with the muse agent, re-skinned to the Night Desk
 * ops-console density. This MIRRORS the verified gateway stack from
 * components/chat/ChatMode.tsx (same protocol, same libraries) rather
 * than composing <ChatMode />, because the mockup needs what ChatMode's
 * fixed layout does not expose: a session header strip (mono session id
 * + routed model · provider badge + streaming dot), interleaved
 * tool-trace rows, and the ops-dense transcript/composer treatment.
 *
 *   gw.request("session.create")                     → lazily, first send
 *   gw.request("prompt.submit", {session_id, text})  → turn accepted
 *   events: message.start / message.delta / message.complete / error
 *           session.info  { model, provider }        → header badge
 *           tool.start / tool.complete               → mono dim trace rows
 *
 * Slash commands run through the same shared pipeline as ChatMode
 * (lib/slashExec.ts slash.exec → command.dispatch fallback) with
 * SlashPopover autocomplete.
 *
 * Session continuity: one gateway session per mount lifetime, created
 * lazily on the first message; the websocket connects lazily on mount.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { AlertCircle, RotateCcw, SendHorizontal } from "lucide-react";

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

import "./nightdesk.css";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type MsgStatus = "streaming" | "complete" | "interrupted" | "error";

type TranscriptRow =
  | {
      kind: "msg";
      id: string;
      role: "user" | "muse" | "system";
      text: string;
      status?: MsgStatus;
      warning?: string;
    }
  | {
      kind: "tool";
      id: string;
      toolId: string;
      name: string;
      context?: string;
      status: "running" | "done";
      summary?: string;
    };

interface SessionInfoPayload {
  model?: string;
  provider?: string;
}

interface CompletePayload {
  text?: string;
  status?: string;
  warning?: string;
}

interface ToolStartPayload {
  tool_id?: string;
  name?: string;
  context?: string;
}

interface ToolCompletePayload {
  tool_id?: string;
  name?: string;
  summary?: string;
}

/* ------------------------------------------------------------------ */
/*  Small helpers                                                      */
/* ------------------------------------------------------------------ */

let rowSeq = 0;
function nextId(): string {
  return `nd${Date.now().toString(36)}-${++rowSeq}`;
}

function friendlyConnectError(msg: string): string {
  if (/token/i.test(msg)) {
    return "Session token unavailable — open this page through `hermes dashboard`.";
  }
  return "Can't reach the muse gateway — is the dashboard running with embedded chat?";
}

/** Night Desk small-caps section label. */
const labelStyle: React.CSSProperties = {
  fontVariantCaps: "all-small-caps",
  letterSpacing: "0.14em",
  color: "var(--fg-faint)",
};

const HAIRLINE =
  "color-mix(in srgb, var(--midground-base) 10%, transparent)";

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function MindStream() {
  // `version` bumps on manual reconnect; gw is derived so we never call
  // setState for it inside an effect (same pattern as ChatMode).
  const [version, setVersion] = useState(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const gw = useMemo(() => new GatewayClient(), [version]);

  const [connState, setConnState] = useState<ConnectionState>("idle");
  const [model, setModel] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [rows, setRows] = useState<TranscriptRow[]>([]);
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
  // tool_id (gateway) → transcript row id, so tool.complete can close the
  // row opened by tool.start regardless of interleaving.
  const toolRowRef = useRef(new Map<string, string>());
  // Scroll pinning: stay glued to the tail while streaming unless the
  // user has scrolled up to read.
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
          setRows((prev) =>
            prev.map((r) =>
              r.kind === "msg" && r.id === id && r.status === "streaming"
                ? { ...r, status: "error", warning: "connection lost" }
                : r,
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
        setRows((prev) => [
          ...prev,
          { kind: "msg", id, role: "muse", text: "", status: "streaming" },
        ]);
      }
    });

    const offDelta = gw.on<{ text?: string }>("message.delta", (ev) => {
      if (!matchSession(ev)) return;
      const delta = ev.payload?.text ?? "";
      const id = streamingIdRef.current;
      if (!id || !delta) return;
      setRows((prev) =>
        prev.map((r) =>
          r.kind === "msg" && r.id === id ? { ...r, text: r.text + delta } : r,
        ),
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
        setRows((prev) =>
          prev.map((r) =>
            r.kind === "msg" && r.id === id
              ? {
                  ...r,
                  text: p.text || r.text,
                  status,
                  warning: p.warning ?? r.warning,
                }
              : r,
          ),
        );
      } else if (p.text) {
        setRows((prev) => [
          ...prev,
          {
            kind: "msg",
            id: nextId(),
            role: "muse",
            text: p.text!,
            status,
            warning: p.warning,
          },
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
        setRows((prev) =>
          prev.map((r) =>
            r.kind === "msg" && r.id === id
              ? { ...r, status: "error", warning: message }
              : r,
          ),
        );
        streamingIdRef.current = null;
        busyRef.current = false;
        setBusy(false);
      } else {
        setError(message);
      }
    });

    // Tool trace — mono dim rows interleaved in the transcript. Payload
    // shape from tui_gateway/server.py: tool.start {tool_id, name,
    // context}; tool.complete {tool_id, name, summary?}.
    const offToolStart = gw.on<ToolStartPayload>("tool.start", (ev) => {
      if (!matchSession(ev)) return;
      const p = ev.payload ?? {};
      const toolId = p.tool_id ?? nextId();
      if (toolRowRef.current.has(toolId)) return;
      const id = nextId();
      toolRowRef.current.set(toolId, id);
      setRows((prev) => [
        ...prev,
        {
          kind: "tool",
          id,
          toolId,
          name: p.name ?? "tool",
          context: p.context,
          status: "running",
        },
      ]);
    });

    const offToolComplete = gw.on<ToolCompletePayload>(
      "tool.complete",
      (ev) => {
        if (!matchSession(ev)) return;
        const p = ev.payload ?? {};
        const toolId = p.tool_id ?? "";
        const rowId = toolRowRef.current.get(toolId);
        if (rowId) {
          toolRowRef.current.delete(toolId);
          setRows((prev) =>
            prev.map((r) =>
              r.kind === "tool" && r.id === rowId
                ? { ...r, status: "done", summary: p.summary }
                : r,
            ),
          );
        } else {
          // Late/orphaned complete (start arrived before mount) — record
          // it honestly as a finished row.
          setRows((prev) => [
            ...prev,
            {
              kind: "tool",
              id: nextId(),
              toolId: toolId || nextId(),
              name: p.name ?? "tool",
              status: "done",
              summary: p.summary,
            },
          ]);
        }
      },
    );

    return () => {
      offState();
      offInfo();
      offStart();
      offDelta();
      offComplete();
      offError();
      offToolStart();
      offToolComplete();
    };
  }, [gw, matchSession]);

  /* ---------------- connection lifecycle ------------------------- */

  // Lazy connect on mount; session.create stays deferred to the first
  // message. A drop is retried when the user sends again.
  useEffect(() => {
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
  }, [gw]);

  // Close the websocket with the client instance (reconnect / unmount).
  useEffect(() => () => gw.close(), [gw]);

  // Await the socket actually reaching "open" (same guard as ChatMode).
  const ensureConnected = useCallback(async (): Promise<void> => {
    if (gw.connectionState === "open") return;
    if (gw.connectionState !== "connecting") {
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
    toolRowRef.current.clear();
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
      stickToBottomRef.current = true;
      setRows((prev) => [
        ...prev,
        { kind: "msg", id: nextId(), role: "user", text },
        { kind: "msg", id: draftId, role: "muse", text: "", status: "streaming" },
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
        setRows((prev) =>
          prev.map((r) =>
            r.kind === "msg" && r.id === draftId
              ? {
                  ...r,
                  status: "error",
                  warning: /busy/i.test(msg)
                    ? "muse is still answering — try again in a moment"
                    : friendlyConnectError(msg),
                }
              : r,
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
      setRows((prev) => [
        ...prev,
        { kind: "msg", id: nextId(), role: "user", text: command },
      ]);
      setInput("");

      const sys = (t: string) =>
        setRows((prev) => [
          ...prev,
          { kind: "msg", id: nextId(), role: "system", text: t },
        ]);

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

  // Pin to the transcript tail on new content — unless the user scrolled
  // up to read, in which case their position is preserved.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottomRef.current) el.scrollTop = el.scrollHeight;
  }, [rows]);

  const onTranscriptScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    stickToBottomRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  }, []);

  // Composer auto-height: one line at rest, grows to ~6 lines.
  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 144)}px`;
  }, [input]);

  const onComposerKey = (e: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (slashRef.current?.handleKey(e)) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  /* ---------------- render ---------------------------------------- */

  const streaming =
    busy || rows.some((r) => r.kind === "msg" && r.status === "streaming");

  const dotColor =
    connState === "error" || connState === "closed"
      ? "var(--err)"
      : streaming
        ? "var(--accent)"
        : connState === "open"
          ? "var(--ok)"
          : "var(--fg-faint)";

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Header strip — streaming dot, mono session id, routed badge */}
      <div
        className="flex shrink-0 items-center gap-2 border-b px-3 py-2"
        style={{ borderColor: HAIRLINE }}
      >
        <span
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${streaming ? "animate-pulse" : ""}`}
          style={{ background: dotColor }}
          title={
            connState === "open"
              ? streaming
                ? "streaming"
                : "gateway connected"
              : `gateway ${connState}`
          }
        />
        <span className="text-[0.66rem]" style={labelStyle}>
          mind stream
        </span>
        <span
          className="min-w-0 flex-1 truncate font-mono-ui text-[0.66rem]"
          style={{ color: "var(--fg-dim)" }}
          title={sessionId ?? undefined}
        >
          {sessionId ?? "no session"}
        </span>
        {connState !== "open" && (
          <span
            className="shrink-0 text-[0.62rem]"
            style={{ color: "var(--fg-faint)" }}
          >
            {connState}
          </span>
        )}
        <span
          className="shrink-0 rounded-full border px-2 py-0.5 font-mono-ui text-[0.62rem]"
          style={{
            borderColor: model
              ? "color-mix(in srgb, var(--accent) 28%, transparent)"
              : HAIRLINE,
            color: model ? "var(--accent-dim)" : "var(--fg-faint)",
            background: model
              ? "color-mix(in srgb, var(--accent) 7%, transparent)"
              : "transparent",
          }}
        >
          {model
            ? `routed ${model}${provider ? ` · ${provider}` : ""}`
            : "not routed"}
        </span>
      </div>

      {/* Error banner — gateway down / session failure, with retry */}
      {error && (
        <div
          role="alert"
          className="mx-3 mt-2 flex shrink-0 items-start gap-2 rounded-md border px-3 py-1.5 text-[0.72rem]"
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
            className="muse-press flex h-5 w-5 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-current/10"
          >
            <RotateCcw className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* Transcript — user right / muse flat / tool trace mono dim */}
      <div
        ref={scrollRef}
        onScroll={onTranscriptScroll}
        className="min-h-0 flex-1 overflow-y-auto px-3 py-3"
      >
        {rows.length === 0 ? (
          <div
            className="flex min-h-[40%] flex-col items-center justify-center gap-2 px-6 text-center"
            style={{ color: "var(--fg-faint)" }}
          >
            <p className="text-[0.8rem]" style={{ color: "var(--fg-dim)" }}>
              Ask muse anything.
            </p>
            <p className="text-[0.66rem]">
              Type <code className="font-mono-ui">/</code> for commands ·{" "}
              <code className="font-mono-ui">/orchestrate</code> ·{" "}
              <code className="font-mono-ui">/jarvis</code>
            </p>
          </div>
        ) : (
          rows.map((r) =>
            r.kind === "tool" ? (
              <ToolTraceRow key={r.id} row={r} />
            ) : (
              <MessageRow key={r.id} msg={r} />
            ),
          )
        )}
      </div>

      {/* Composer */}
      <div
        className="relative shrink-0 border-t px-3 pb-2 pt-2"
        style={{ borderColor: HAIRLINE }}
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
            placeholder="Message muse… /orchestrate, /jarvis, slash commands"
            aria-label="Message muse"
            className="min-h-[32px] flex-1 resize-none bg-transparent px-1 py-1 text-[0.85rem] leading-relaxed outline-none placeholder:text-[var(--fg-faint)]"
            style={{ color: "var(--fg)" }}
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={!input.trim() || busy}
            aria-label="Send message"
            className="muse-press mb-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border transition-opacity disabled:opacity-35"
            style={{
              borderColor: "color-mix(in srgb, var(--accent) 30%, transparent)",
              background: "color-mix(in srgb, var(--accent) 10%, transparent)",
              color: "var(--accent)",
            }}
          >
            <SendHorizontal className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="mt-1 flex items-center gap-2 px-1 pb-0.5">
          <span
            className="text-[0.6rem] tracking-[0.04em]"
            style={{ color: "var(--fg-faint)" }}
          >
            Enter to send · Shift+Enter newline · / commands
          </span>
          {streaming && (
            <span
              className="text-[0.6rem] tracking-[0.04em]"
              style={{ color: "var(--accent-dim)" }}
            >
              muse is answering…
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Rows                                                               */
/* ------------------------------------------------------------------ */

function MessageRow({
  msg,
}: {
  msg: Extract<TranscriptRow, { kind: "msg" }>;
}) {
  if (msg.role === "user") {
    return (
      <div className="mb-2.5 flex justify-end">
        <div
          className="max-w-[85%] whitespace-pre-wrap rounded-md border px-3 py-1.5 text-[0.85rem] leading-relaxed"
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
          className="h-1.5 w-1.5 animate-pulse rounded-full"
          style={{ background: "var(--accent-dim)" }}
        />
        <span
          className="h-1.5 w-1.5 animate-pulse rounded-full"
          style={{ background: "var(--accent-dim)", animationDelay: "150ms" }}
        />
        <span
          className="h-1.5 w-1.5 animate-pulse rounded-full"
          style={{ background: "var(--accent-dim)", animationDelay: "300ms" }}
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
          className="mt-1 text-[0.7rem] leading-relaxed"
          style={{
            color: msg.status === "error" ? "var(--err)" : "var(--warn)",
          }}
        >
          {msg.warning}
        </div>
      ) : null}
      {msg.status === "interrupted" ? (
        <div className="mt-1 text-[0.7rem]" style={{ color: "var(--warn)" }}>
          interrupted
        </div>
      ) : null}
    </div>
  );
}

function ToolTraceRow({
  row,
}: {
  row: Extract<TranscriptRow, { kind: "tool" }>;
}) {
  return (
    <div
      className="mb-1 flex items-baseline gap-2 font-mono-ui text-[0.68rem] leading-relaxed"
      style={{ color: "var(--fg-faint)" }}
    >
      <span
        className={`h-1 w-1 shrink-0 translate-y-[-1px] rounded-full ${row.status === "running" ? "animate-pulse" : ""}`}
        style={{
          background:
            row.status === "running" ? "var(--accent-dim)" : "var(--fg-faint)",
        }}
      />
      <span style={{ color: "var(--fg-dim)" }}>{row.name}</span>
      {row.context ? (
        <span className="min-w-0 flex-1 truncate" title={row.context}>
          {row.context}
        </span>
      ) : null}
      {row.status === "done" && row.summary ? (
        <span className="min-w-0 flex-1 truncate" title={row.summary}>
          · {row.summary}
        </span>
      ) : null}
      {row.status === "running" ? <span>…</span> : null}
    </div>
  );
}
