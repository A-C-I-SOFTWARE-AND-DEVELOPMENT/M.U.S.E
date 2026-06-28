/**
 * Home — the Singularity landing surface.
 *
 * Mirrors the cockpit's Home view: pairing card, welcome card, chat card,
 * and a phase rail showing the studio pipeline.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { PhaseRail } from "../components/PhaseRail";
import { SectionHeader } from "../components/SectionHeader";
import {
  chat,
  getToken,
  pairConfirm,
  pairStart,
  type ChatTurn,
} from "../lib/gateway";

export function Home() {
  const [paired, setPaired] = useState<boolean>(() => Boolean(getToken()));
  return (
    <div className="view">
      {!paired && <PairCard onPaired={() => setPaired(true)} />}
      <WelcomeCard />
      <PhaseRailCard />
      <ChatCard paired={paired} onNeedsPairing={() => setPaired(false)} />
    </div>
  );
}

function WelcomeCard() {
  return (
    <div className="card">
      <SectionHeader
        eyebrow="Welcome to muse"
        title="Your local-first AI operating partner"
      />
      <p className="muted" style={{ marginBottom: 0 }}>
        This is the desktop Singularity client. Talk to the local agent below;
        jobs, approvals, autonomy and other surfaces arrive as additive routes.
      </p>
    </div>
  );
}

function PhaseRailCard() {
  const phases = [
    { id: "concept", label: "Concept", state: "done" as const },
    { id: "prototype", label: "Prototype", state: "current" as const },
    { id: "vertical", label: "Vertical Slice", state: "pending" as const },
    { id: "alpha", label: "Alpha", state: "pending" as const },
    { id: "beta", label: "Beta", state: "pending" as const },
    { id: "gold", label: "Gold", state: "pending" as const },
    { id: "launch", label: "Launch", state: "pending" as const },
  ];
  return (
    <div className="card">
      <SectionHeader eyebrow="Studio pipeline" title="AAA milestone gates" />
      <PhaseRail phases={phases} />
    </div>
  );
}

function PairCard({ onPaired }: { onPaired: () => void }) {
  const [deviceName, setDeviceName] = useState("");
  const [code, setCode] = useState("");
  const [phrase, setPhrase] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const start = useCallback(async () => {
    setBusy(true);
    setMsg("Requesting a pairing code…");
    const r = await pairStart(deviceName);
    setBusy(false);
    if (!r.ok) {
      setMsg("Pairing unavailable: " + (r.error || "") + (r.hint ? " — " + r.hint : ""));
      return;
    }
    setCode(r.pairingCode || "");
    setMsg("Code generated. Enter the owner phrase, then confirm.");
  }, [deviceName]);

  const confirm = useCallback(async () => {
    if (!code) {
      setMsg("Get a pairing code first.");
      return;
    }
    if (!phrase.trim()) {
      setMsg("The owner phrase is required.");
      return;
    }
    setBusy(true);
    setMsg("Confirming…");
    const r = await pairConfirm(code, phrase.trim());
    setBusy(false);
    if (r.forbidden) {
      setMsg("Owner authorization required — re-enter the exact phrase.");
      return;
    }
    if (!r.ok) {
      setMsg("Pairing failed: " + (r.error || ""));
      return;
    }
    setPhrase("");
    setMsg("Paired. This device now has its own token.");
    onPaired();
  }, [code, phrase, onPaired]);

  return (
    <div className="card" style={{ borderColor: "var(--ring-1)" }}>
      <SectionHeader
        eyebrow="Pair this device"
        title="Owner-gated pairing"
        trailing={<span className="pill">owner-gated</span>}
      />
      <p className="muted">
        Generate a short-lived pairing code, then confirm it with the owner
        phrase. A per-device token is minted once and stored only on this device.
      </p>
      <div className="row">
        <input
          type="text"
          placeholder="Device name (optional)"
          value={deviceName}
          onChange={(e) => setDeviceName(e.target.value)}
          style={{ flex: 1 }}
        />
        <button className="primary" onClick={start} disabled={busy}>
          Get pairing code
        </button>
        {code && <span className="mono">code: {code}</span>}
      </div>
      {code && (
        <div className="row" style={{ marginTop: 12 }}>
          <input
            type="password"
            placeholder="Owner authorization phrase"
            value={phrase}
            onChange={(e) => setPhrase(e.target.value)}
            style={{ flex: 1 }}
          />
          <button className="primary" onClick={confirm} disabled={busy}>
            Confirm & pair
          </button>
        </div>
      )}
      {msg && (
        <div className="muted" style={{ marginTop: 10, fontSize: 12 }}>
          {msg}
        </div>
      )}
    </div>
  );
}

type Msg = { role: "user" | "asst"; text: string };

function ChatCard({
  paired,
  onNeedsPairing,
}: {
  paired: boolean;
  onNeedsPairing: () => void;
}) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const logRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const send = useCallback(async () => {
    const prompt = draft.trim();
    if (!prompt || sending) return;
    if (!getToken()) {
      onNeedsPairing();
      return;
    }
    setDraft("");
    setSending(true);
    // History is the prior turns in the gateway's {role, content} shape.
    const history: ChatTurn[] = messages.map((m) => ({
      role: m.role === "user" ? "user" : "assistant",
      content: m.text,
    }));
    setMessages((prev) => [...prev, { role: "user", text: prompt }, { role: "asst", text: "…" }]);
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
    setSending(false);
  }, [draft, sending, messages, onNeedsPairing]);

  return (
    <div className="card chat-card">
      <SectionHeader
        eyebrow="Talk to muse"
        title="Chat with muse"
        trailing={
          <span className="pill accent">
            <span className="dot live"></span> online
          </span>
        }
      />
      <div className="chatlog" ref={logRef}>
        {messages.length === 0 ? (
          <div className="empty">
            Ask muse anything. Responses stream live from the local agent.
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={"msg " + (m.role === "user" ? "user" : "asst")}>
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
              : "Pair this device to chat…"
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
        <button className="primary" onClick={() => void send()} disabled={sending}>
          Send
        </button>
      </div>
    </div>
  );
}