/**
 * Chat — the full-page NDJSON conversation surface with voice input/output.
 *
 * Talks to POST /v1/jarvis/chat via the shared `chat()` client (lib/gateway),
 * which streams the assistant reply line-by-line (newline-delimited JSON) and
 * accumulates it. User bubbles sit right (void-2 fill); the assistant sits left
 * with the one spectral accent in the view — a thin ring-gradient left border
 * (see .msg.asst in app.css). The composer sends on Enter and inserts a newline
 * on Shift+Enter.
 *
 * Voice: mic button uses the Web Speech API for speech-to-text. When voice
 * preferences enable TTS, assistant replies are spoken automatically.
 *
 * This is a route registered via the append-only registry.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { chat, getToken, stopAgent, TOKEN_EVENT, type ChatTurn } from "../lib/gateway";
import {
  VoiceListener,
  isSTTSupported,
  isTTSSupported,
  speak,
  stopSpeaking,
  isSpeaking,
  getVoices,
  getVoicePrefs,
  type VoicePrefs,
} from "../lib/voice";

type Msg = { role: "user" | "asst"; text: string };

export function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [paired, setPaired] = useState<boolean>(() => Boolean(getToken()));
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [voicePrefs, setVoicePrefs] = useState<VoicePrefs>(() => getVoicePrefs());
  const logRef = useRef<HTMLDivElement | null>(null);
  const listenerRef = useRef<VoiceListener | null>(null);
  const requestRef = useRef<AbortController | null>(null);

  // Init voice listener
  useEffect(() => {
    listenerRef.current = new VoiceListener();
    return () => {
      listenerRef.current?.stop();
      requestRef.current?.abort();
      void stopAgent();
      stopSpeaking();
    };
  }, []);

  // Re-check pairing when the token changes
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

  // Auto-speak assistant replies when TTS is enabled
  const lastSpokenRef = useRef<number>(-1);
  useEffect(() => {
    if (!voicePrefs.ttsEnabled || !isTTSSupported()) return;
    const lastIdx = messages.length - 1;
    if (lastIdx < 0 || lastIdx === lastSpokenRef.current) return;
    const last = messages[lastIdx];
    if (last.role !== "asst" || last.text === "…" || !last.text.trim()) return;
    // Only speak if the assistant is done sending (not streaming)
    if (!sending) {
      lastSpokenRef.current = lastIdx;
      const voices = getVoices();
      const voice = voicePrefs.ttsVoiceURI
        ? voices.find((v) => v.voiceURI === voicePrefs.ttsVoiceURI) || null
        : null;
      speak(last.text, {
        voice,
        rate: voicePrefs.ttsRate,
        pitch: voicePrefs.ttsPitch,
      });
      setSpeaking(true);
    }
  }, [messages, sending, voicePrefs]);

  // Track speaking state
  useEffect(() => {
    if (!speaking) return;
    const interval = setInterval(() => {
      if (!isSpeaking()) setSpeaking(false);
    }, 500);
    return () => clearInterval(interval);
  }, [speaking]);

  const toggleListen = useCallback(() => {
    const listener = listenerRef.current;
    if (!listener) return;

    if (listening) {
      listener.stop();
      setListening(false);
      return;
    }

    // Human barge-in: listening immediately stops both local speech and the
    // in-flight full-agent turn before opening the microphone.
    stopSpeaking();
    setSpeaking(false);
    requestRef.current?.abort();
    requestRef.current = null;
    if (sending) {
      void stopAgent();
      setSending(false);
    }
    setListening(true);
    listener.start(voicePrefs.sttLang, {
      onInterim: (text) => {
        setDraft(text);
      },
      onFinal: (text) => {
        setDraft((prev) => {
          const base = prev.trim();
          return base ? `${base} ${text}` : text;
        });
      },
      onError: (msg) => {
        setListening(false);
        console.warn("Voice recognition error:", msg);
      },
      onEnd: () => {
        setListening(false);
      },
    });
  }, [listening, sending, voicePrefs.sttLang]);

  const toggleSpeak = useCallback(() => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
    } else {
      // Speak the last assistant message
      const lastAsst = [...messages].reverse().find((m) => m.role === "asst");
      if (lastAsst) {
        const voices = getVoices();
        const voice = voicePrefs.ttsVoiceURI
          ? voices.find((v) => v.voiceURI === voicePrefs.ttsVoiceURI) || null
          : null;
        speak(lastAsst.text, {
          voice,
          rate: voicePrefs.ttsRate,
          pitch: voicePrefs.ttsPitch,
        });
        setSpeaking(true);
      }
    }
  }, [speaking, messages, voicePrefs]);

  const toggleAutoTTS = useCallback(() => {
    const next = { ...voicePrefs, ttsEnabled: !voicePrefs.ttsEnabled };
    setVoicePrefs(next);
    localStorage.setItem("muse.voice.prefs", JSON.stringify(next));
    if (!next.ttsEnabled) {
      stopSpeaking();
      setSpeaking(false);
    }
  }, [voicePrefs]);

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
    const controller = new AbortController();
    requestRef.current?.abort();
    requestRef.current = controller;
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
    }, controller.signal);
    if (requestRef.current === controller) requestRef.current = null;
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

  const sttSupported = isSTTSupported();
  const ttsSupported = isTTSSupported();

  return (
    <div className="view">
      {!paired && (
        <div className="card notice">
          This device isn't paired yet. Open <b>Settings</b> to pair it, then
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
          {sttSupported && (
            <button
              className={"voice-btn" + (listening ? " active" : "")}
              onClick={toggleListen}
              title={listening ? "Stop listening" : "Speak"}
              disabled={!paired}
            >
              {listening ? "⏹" : "🎙"}
            </button>
          )}
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
          {ttsSupported && (
            <button
              className={"voice-btn" + (speaking ? " active" : "")}
              onClick={toggleSpeak}
              title={speaking ? "Stop speaking" : "Read aloud"}
              disabled={messages.length === 0}
            >
              {speaking ? "🔇" : "🔊"}
            </button>
          )}
          {ttsSupported && (
            <button
              className={"voice-btn" + (voicePrefs.ttsEnabled ? " active" : "")}
              onClick={toggleAutoTTS}
              title={
                voicePrefs.ttsEnabled
                  ? "Auto-read OFF"
                  : "Auto-read replies ON"
              }
            >
              {voicePrefs.ttsEnabled ? "🔔" : "🔕"}
            </button>
          )}
        </div>
        {listening && (
          <div className="voice-hint">
            Listening… speak now. Text will appear in the input field.
          </div>
        )}
      </div>
    </div>
  );
}
