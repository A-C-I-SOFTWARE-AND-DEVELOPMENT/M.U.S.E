/**
 * Floating M.U.S.E. dock — a movable, minimizable chat overlay available on
 * every screen.
 *
 * It streams to the same gateway endpoint as the full Chat view (lib/gateway
 * `chat()`), so you can talk to M.U.S.E. without leaving the surface you're on.
 * Position / size / open / minimized state persist across launches
 * (localStorage). Every action is a bound quick-command (lib/dockCommands): the
 * title-bar buttons and the keyboard chords dispatch the *same* command set, so
 * clicking and the keyboard stay in lockstep.
 *
 * Mounted once by the app shell (App.tsx) as a global overlay — it is NOT a
 * route, so it floats above whichever surface is active. Honors the design
 * language: tonal elevation (no drop-shadow), the ring as a single sparing
 * accent, focus-visible rings (global), reduced-motion (global).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { chat, getToken, TOKEN_EVENT, type ChatTurn } from "../lib/gateway";
import {
  DOCK_CHROME_COMMANDS,
  matchGlobalDockCommand,
  type DockCommandId,
} from "../lib/dockCommands";

type Msg = { role: "user" | "asst"; text: string };
type Pos = { x: number; y: number };
type Size = { w: number; h: number };

const POS_KEY = "muse.dock.pos";
const SIZE_KEY = "muse.dock.size";
const OPEN_KEY = "muse.dock.open";
const MIN_KEY = "muse.dock.min";

const MIN_W = 300;
const MIN_H = 240;
const DEFAULT_W = 360;
const DEFAULT_H = 440;
const MARGIN = 16;

function loadJSON<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

function saveJSON(key: string, val: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(val));
  } catch {
    /* storage unavailable */
  }
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(Math.max(n, lo), hi);
}

/** Default bottom-right anchor for a fresh install (no stored position). */
function defaultPos(size: Size): Pos {
  const vw = typeof window !== "undefined" ? window.innerWidth : 1280;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  return {
    x: Math.max(MARGIN, vw - size.w - MARGIN),
    y: Math.max(MARGIN, vh - size.h - MARGIN),
  };
}

export function Dock() {
  const [open, setOpen] = useState<boolean>(() => loadJSON(OPEN_KEY, false));
  const [minimized, setMinimized] = useState<boolean>(() => loadJSON(MIN_KEY, false));
  const [size, setSize] = useState<Size>(() =>
    loadJSON(SIZE_KEY, { w: DEFAULT_W, h: DEFAULT_H }),
  );
  const [pos, setPos] = useState<Pos>(() => loadJSON(POS_KEY, defaultPos(size)));

  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [paired, setPaired] = useState<boolean>(() => Boolean(getToken()));

  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);
  // Mirror size into a ref so the drag/resize move handlers (bound once) read
  // the latest dimensions without being re-created on every resize.
  const sizeRef = useRef<Size>(size);
  useEffect(() => {
    sizeRef.current = size;
  }, [size]);

  // ---- persistence --------------------------------------------------------
  useEffect(() => saveJSON(OPEN_KEY, open), [open]);
  useEffect(() => saveJSON(MIN_KEY, minimized), [minimized]);
  useEffect(() => saveJSON(POS_KEY, pos), [pos]);
  useEffect(() => saveJSON(SIZE_KEY, size), [size]);

  // Re-check pairing when the token changes (auto-pair / Settings), the
  // window regains focus, or storage changes from another tab.
  useEffect(() => {
    const refresh = () => setPaired(Boolean(getToken()));
    window.addEventListener(TOKEN_EVENT, refresh);
    window.addEventListener("focus", refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(TOKEN_EVENT, refresh);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  // Keep the dock pinned within the viewport when the window is resized.
  useEffect(() => {
    const onResize = () => {
      setPos((p) => ({
        x: clamp(p.x, 0, Math.max(0, window.innerWidth - sizeRef.current.w)),
        y: clamp(p.y, 0, Math.max(0, window.innerHeight - sizeRef.current.h)),
      }));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Keep the log pinned to the latest message as it streams.
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const send = useCallback(async () => {
    const prompt = draft.trim();
    if (!prompt || sending) return;
    if (!getToken()) {
      setPaired(false);
      return;
    }
    setDraft("");
    setSending(true);
    const history: ChatTurn[] = messages.map((m) => ({
      role: m.role === "user" ? "user" : "assistant",
      content: m.text,
    }));
    setMessages((prev) => [
      ...prev,
      { role: "user", text: prompt },
      { role: "asst", text: "…" },
    ]);
    await chat(prompt, history, {
      onDelta: (acc) =>
        setMessages((prev) => {
          const next = prev.slice();
          next[next.length - 1] = { role: "asst", text: acc || "…" };
          return next;
        }),
      onError: (m) =>
        setMessages((prev) => {
          const next = prev.slice();
          next[next.length - 1] = { role: "asst", text: m };
          return next;
        }),
    });
    setMessages((prev) => {
      const next = prev.slice();
      const last = next[next.length - 1];
      if (last && last.role === "asst" && last.text === "…") {
        next[next.length - 1] = { role: "asst", text: "(no response)" };
      }
      return next;
    });
    setSending(false);
  }, [draft, sending, messages]);

  // ---- quick-command dispatch --------------------------------------------
  // Every dock action — clicked or keyed — flows through here, so the title-bar
  // buttons and the keyboard chords (lib/dockCommands) can never diverge.
  const run = useCallback(
    (id: DockCommandId) => {
      switch (id) {
        case "toggle":
          setOpen((o) => !o);
          break;
        case "minimize":
          setMinimized((m) => !m);
          break;
        case "clear":
          setMessages([]);
          break;
        case "close":
          setOpen(false);
          break;
        case "focusInput":
          setOpen(true);
          setMinimized(false);
          requestAnimationFrame(() => inputRef.current?.focus());
          break;
        case "send":
          void send();
          break;
      }
    },
    [send],
  );

  // Global keyboard chords (toggle / minimize / clear / focusInput).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const id = matchGlobalDockCommand(e);
      if (!id) return;
      e.preventDefault();
      run(id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [run]);

  // ---- drag (title bar) ---------------------------------------------------
  const dragRef = useRef<{ dx: number; dy: number } | null>(null);
  const onDragMove = useCallback((e: PointerEvent) => {
    const d = dragRef.current;
    if (!d) return;
    const { w, h } = sizeRef.current;
    setPos({
      x: clamp(e.clientX - d.dx, 0, Math.max(0, window.innerWidth - w)),
      y: clamp(e.clientY - d.dy, 0, Math.max(0, window.innerHeight - h)),
    });
  }, []);
  const onDragEnd = useCallback(() => {
    dragRef.current = null;
    window.removeEventListener("pointermove", onDragMove);
    window.removeEventListener("pointerup", onDragEnd);
  }, [onDragMove]);
  const onHeaderPointerDown = useCallback(
    (e: React.PointerEvent) => {
      // Don't start a drag from the chrome buttons.
      if ((e.target as HTMLElement).closest("button")) return;
      dragRef.current = { dx: e.clientX - pos.x, dy: e.clientY - pos.y };
      window.addEventListener("pointermove", onDragMove);
      window.addEventListener("pointerup", onDragEnd);
      e.preventDefault();
    },
    [pos.x, pos.y, onDragMove, onDragEnd],
  );

  // ---- resize (bottom-right handle) --------------------------------------
  const resizeRef = useRef<{ x: number; y: number; w: number; h: number } | null>(null);
  const onResizeMove = useCallback((e: PointerEvent) => {
    const r = resizeRef.current;
    if (!r) return;
    setSize({
      w: clamp(r.w + (e.clientX - r.x), MIN_W, Math.max(MIN_W, window.innerWidth - MARGIN)),
      h: clamp(r.h + (e.clientY - r.y), MIN_H, Math.max(MIN_H, window.innerHeight - MARGIN)),
    });
  }, []);
  const onResizeEnd = useCallback(() => {
    resizeRef.current = null;
    window.removeEventListener("pointermove", onResizeMove);
    window.removeEventListener("pointerup", onResizeEnd);
  }, [onResizeMove]);
  const onResizePointerDown = useCallback(
    (e: React.PointerEvent) => {
      resizeRef.current = { x: e.clientX, y: e.clientY, w: size.w, h: size.h };
      window.addEventListener("pointermove", onResizeMove);
      window.addEventListener("pointerup", onResizeEnd);
      e.preventDefault();
      e.stopPropagation();
    },
    [size.w, size.h, onResizeMove, onResizeEnd],
  );

  // ---- render -------------------------------------------------------------
  if (!open) {
    return (
      <button
        className="dock-launcher"
        onClick={() => run("toggle")}
        title="Open the M.U.S.E. dock (Ctrl/⌘ + `)"
        aria-label="Open the M.U.S.E. dock"
      >
        <span className="dock-launcher-dot" aria-hidden="true" />
        Ask M.U.S.E.
      </button>
    );
  }

  return (
    <section
      className={"dock" + (minimized ? " minimized" : "")}
      style={{ left: pos.x, top: pos.y, width: size.w, height: minimized ? undefined : size.h }}
      role="dialog"
      aria-label="M.U.S.E. dock"
    >
      <header className="dock-bar" onPointerDown={onHeaderPointerDown}>
        <span className="dock-title">
          <span className={"dot " + (paired ? "live" : "")} aria-hidden="true" />
          M.U.S.E.
        </span>
        <span className="dock-spacer" />
        {DOCK_CHROME_COMMANDS.map((c) => (
          <button
            key={c.id}
            className="dock-btn"
            onClick={() => run(c.id)}
            title={`${c.label} · ${c.hint}`}
            aria-label={c.label}
          >
            {c.id === "minimize" ? (minimized ? "▢" : "—") : c.id === "close" ? "✕" : "⌫"}
          </button>
        ))}
      </header>

      {!minimized && (
        <>
          {!paired && (
            <div className="dock-notice">
              Not paired — open <b>Settings</b> to pair this device, then chat here.
            </div>
          )}
          <div
            className="dock-log"
            ref={logRef}
            aria-live="polite"
            aria-label="Conversation"
          >
            {messages.length === 0 ? (
              <div className="empty">
                Ask M.U.S.E. from any screen. Replies stream from the local agent.
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={"msg " + (m.role === "user" ? "user" : "asst")}>
                  {m.text}
                </div>
              ))
            )}
          </div>
          <div className="dock-composer">
            <textarea
              ref={inputRef}
              rows={2}
              placeholder={
                paired ? "Message M.U.S.E.…  (Enter to send)" : "Pair in Settings to chat…"
              }
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                // Composer-local quick-commands: Enter sends, Esc closes,
                // Shift+Enter inserts a newline.
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  run("send");
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  run("close");
                }
              }}
            />
            <button
              className="primary"
              onClick={() => run("send")}
              disabled={sending || !draft.trim()}
            >
              Send
            </button>
          </div>
          <span
            className="dock-resize"
            onPointerDown={onResizePointerDown}
            aria-hidden="true"
            title="Resize"
          />
        </>
      )}
    </section>
  );
}
