/**
 * Chat — the primary M.U.S.E. desktop surface.
 *
 * Conversation turns persist locally across route changes and restarts. The
 * gateway remains the source of truth for inference; this component stores only
 * the visible transcript and never stores provider credentials.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Glyph } from "../components/Glyph";
import { chat, getToken, TOKEN_EVENT, type ChatTurn } from "../lib/gateway";

const CHAT_STORAGE_KEY = "muse.desktop.chat.current";

type Msg = {
  id: string;
  role: "user" | "asst";
  text: string;
};

function messageId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }
}

function loadMessages(): Msg[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || "[]") as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is Msg =>
        Boolean(item) &&
        typeof item === "object" &&
        typeof (item as Msg).id === "string" &&
        ((item as Msg).role === "user" || (item as Msg).role === "asst") &&
        typeof (item as Msg).text === "string",
    );
  } catch {
    return [];
  }
}

const suggestions = [
  "What should I focus on today?",
  "Review the active work and surface blockers",
  "Plan and execute my next product milestone",
];

export function Chat() {
  const [messages, setMessages] = useState<Msg[]>(loadMessages);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [paired, setPaired] = useState<boolean>(() => Boolean(getToken()));
  const logRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

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

  useEffect(() => {
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
    } catch {
      // Private browsing / disabled storage: conversation remains in memory.
    }
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const sendPrompt = useCallback(
    async (candidate?: string) => {
      const prompt = (candidate ?? draft).trim();
      if (!prompt || sending) return;
      if (!getToken()) {
        setPaired(false);
        return;
      }

      const history: ChatTurn[] = messages.map((message) => ({
        role: message.role === "user" ? "user" : "assistant",
        content: message.text,
      }));
      const assistantId = messageId();
      setDraft("");
      setSending(true);
      setMessages((previous) => [
        ...previous,
        { id: messageId(), role: "user", text: prompt },
        { id: assistantId, role: "asst", text: "" },
      ]);

      await chat(prompt, history, {
        onDelta: (accumulated) =>
          setMessages((previous) =>
            previous.map((message) =>
              message.id === assistantId ? { ...message, text: accumulated } : message,
            ),
          ),
        onError: (text) =>
          setMessages((previous) =>
            previous.map((message) =>
              message.id === assistantId ? { ...message, text } : message,
            ),
          ),
      });
      setMessages((previous) =>
        previous.map((message) =>
          message.id === assistantId && !message.text
            ? { ...message, text: "Muse finished without returning a response." }
            : message,
        ),
      );
      setSending(false);
      requestAnimationFrame(() => inputRef.current?.focus());
    },
    [draft, messages, sending],
  );

  const newConversation = () => {
    if (messages.length && !window.confirm("Start a new conversation? The current transcript will be cleared from this device.")) {
      return;
    }
    setMessages([]);
    setDraft("");
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  return (
    <div className="view chat-view">
      <header className="chat-page-header">
        <div>
          <div className="eyebrow">Your operating partner</div>
          <h1>Ask Muse</h1>
          <p>Think, build, research, or delegate—your local context stays on this device.</p>
        </div>
        <div className="chat-header-actions">
          <span className="privacy-state"><span className="dot ok" /> Local &amp; private</span>
          <button onClick={newConversation} disabled={sending}>New conversation</button>
        </div>
      </header>

      {!paired && (
        <div className="connection-notice" role="status">
          <span className="connection-orbit" aria-hidden="true" />
          <div>
            <strong>Securely connecting this device</strong>
            <span>Muse will pair with the local gateway automatically. No owner phrase is needed on this PC.</span>
          </div>
          <button onClick={() => { window.location.hash = "#/settings"; }}>Connection settings</button>
        </div>
      )}

      <section className="conversation-shell">
        <div className="chatlog chatlog-primary" ref={logRef} aria-live="polite">
          {messages.length === 0 ? (
            <div className="chat-empty-state">
              <div className="chat-core" aria-hidden="true"><Glyph size={42} spin /></div>
              <h2>What are we working on?</h2>
              <p>Start with a goal. Muse can reason, use tools, and keep long-running work visible.</p>
              <div className="prompt-grid">
                {suggestions.map((suggestion) => (
                  <button key={suggestion} onClick={() => void sendPrompt(suggestion)} disabled={!paired || sending}>
                    <span>{suggestion}</span><span aria-hidden="true">↗</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <article key={message.id} className={"message-row " + message.role}>
                <div className="message-meta">{message.role === "user" ? "You" : "Muse"}</div>
                <div className={"msg " + message.role + (!message.text ? " streaming" : "")}>
                  {message.text || <span className="typing-dots"><i /><i /><i /></span>}
                </div>
                {message.text && (
                  <button
                    className="message-copy"
                    onClick={() => void navigator.clipboard?.writeText(message.text)}
                    aria-label={`Copy ${message.role === "user" ? "your message" : "Muse response"}`}
                    title="Copy"
                  >
                    Copy
                  </button>
                )}
              </article>
            ))
          )}
        </div>

        <div className="composer composer-primary">
          <textarea
            ref={inputRef}
            rows={3}
            placeholder={paired ? "Message Muse…" : "Connecting to your local Muse…"}
            value={draft}
            disabled={!paired}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void sendPrompt();
              }
            }}
            aria-label="Message Muse"
          />
          <div className="composer-footer">
            <span>Enter to send · Shift+Enter for a new line</span>
            <button className="send-orb" onClick={() => void sendPrompt()} disabled={sending || !paired || !draft.trim()} aria-label="Send message">
              {sending ? <span className="send-spinner" /> : <span aria-hidden="true">↑</span>}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
