/**
 * Chat — the full-page NDJSON conversation surface.
 *
 * Talks to POST /v1/jarvis/chat via the shared `chat()` client (lib/gateway),
 * which streams the assistant reply line-by-line (newline-delimited JSON) and
 * accumulates it. User bubbles sit right (void-2 fill); the assistant sits left
 * with the one spectral accent in the view — a thin ring-gradient left border
 * (see .msg.asst in app.css). The composer sends on Enter and inserts a newline
 * on Shift+Enter. Unpaired devices are routed to Settings to pair.
 *
 * This is a route registered via the append-only registry; it does not modify
 * the shell or Home.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { chat, getToken, TOKEN_EVENT, type ChatTurn } from "../lib/gateway";

type Msg = { role: "user" | "asst"; text: string };

export function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [paired, setPaired] = useState<boolean>(() => Boolean(getToken()));
  const logRef = useRef<HTMLDivElement | null>(null);

  // Re-check pairing when the token changes in this document (auto-pair /
  // Settings), when the window regains focus, and on storage changes from
  // another tab.
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
    // History = prior turns in the gateway's {role, content} shape.
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
      // If the assistant produced nothing, say so rather than leaving the dots.
      const next = prev.slice();
      const last = next[next.length - 1];
      if (last && last.role === "asst" && last.text === "…") {
        next[next.length - 1] = { role: "asst", text: "(no response)" };
      }
      return next;
    });
    setSending(false);
  }, [draft, sending, messages]);

  return (
    <div className="view">
      {!paired && (
        <div className="card notice">
          This device isn’t paired yet. Open <b>Settings</b> to pair it, then
          come back to chat.
        </div>
      )}
      <div className="card chat-card">
        <div className="chatlog" ref={logRef}>
          {messages.length === 0 ? (
            <div className="empty">
              Ask muse anything. Responses stream live from the local agent.
            </div>
          ) : (
            messages.map((m, i) => (
              <div
                key={i}
                className={"msg " + (m.role === "user" ? "user" : "asst")}
              >
                {m.text}
              </div>
            ))
          )}
        </div>
        <div className="composer">
          <textarea
            rows={2}
            placeholder={
              paired
                ? "Message muse…  (Enter to send, Shift+Enter for newline)"
                : "Pair this device in Settings to chat…"
            }
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <button
            className="primary"
            onClick={() => void send()}
            disabled={sending || !draft.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
