/**
 * Observatory — the interactive 3D cockpit, embedded full-bleed.
 *
 * The gateway serves the page at /cockpit/observatory.html; it authenticates
 * via a `#token=<bearer>` URL fragment (the page persists the token to its own
 * localStorage and strips the fragment). This view probes GET /v1/health
 * first and only mounts the iframe when the gateway answers — otherwise it
 * renders a designed fallback ("Start the brain") with a native start button
 * (Tauri shell only) and a retry. A shimmer panel covers the probe window.
 *
 * Reuses lib/gateway for the base URL + token (single source of truth) and
 * lib/brain for the native start command. The iframe origin is allow-listed
 * in the shell's CSP (frame-src http://127.0.0.1:8765 http://localhost:8765).
 */
import { useCallback, useEffect, useState } from "react";
import { getGatewayBase, getToken, pingHealth, TOKEN_EVENT } from "../lib/gateway";
import { brainAvailable, brainStart } from "../lib/brain";

type Probe = "checking" | "online" | "offline";

function observatoryUrl(): string {
  const token = getToken();
  const base = getGatewayBase() + "/cockpit/observatory.html";
  // Fragment auth: only attach when this device actually has a token; the
  // page strips the fragment after persisting it.
  return token ? base + "#token=" + encodeURIComponent(token) : base;
}

export function Observatory() {
  const [probe, setProbe] = useState<Probe>("checking");
  const [token, setToken] = useState(() => getToken());
  const [frameFailed, setFrameFailed] = useState(false);

  const check = useCallback(async () => {
    setProbe("checking");
    setFrameFailed(false);
    setProbe((await pingHealth()) ? "online" : "offline");
  }, []);

  useEffect(() => {
    const syncToken = () => setToken(getToken());
    window.addEventListener(TOKEN_EVENT, syncToken);
    window.addEventListener("storage", syncToken);
    void check();
    return () => {
      window.removeEventListener(TOKEN_EVENT, syncToken);
      window.removeEventListener("storage", syncToken);
    };
  }, [check]);

  return (
    <div className="view observatory">
      <div className="section-header">
        <div>
          <div className="eyebrow">Cockpit</div>
          <h2 className="section-title">Observatory</h2>
        </div>
        <span className="grow" />
        <span className={"streamdot " + (probe === "online" ? "live" : "")}>
          <span className="dot-mini" />
          {probe === "online" ? "live" : probe === "offline" ? "offline" : "checking…"}
        </span>
      </div>
      {probe === "checking" && <div className="card shimmer observatory-fill" />}
      {probe === "online" && !token && <ObservatoryPairingCard />}
      {probe === "online" && token && !frameFailed && (
        <iframe
          key={`${getGatewayBase()}:${token.slice(-6)}`}
          className="observatory-frame"
          src={observatoryUrl()}
          title="muse Observatory"
          onError={() => setFrameFailed(true)}
          allow="fullscreen"
        />
      )}
      {probe === "online" && token && frameFailed && (
        <div className="card observatory-fill">
          <b>Observatory couldn't load</b>
          <p className="muted">The gateway is online, but its visualization page failed to mount.</p>
          <button onClick={() => setFrameFailed(false)}>Reload Observatory</button>
        </div>
      )}
      {probe === "offline" && <BrainDownCard onRetry={check} />}
    </div>
  );
}

function ObservatoryPairingCard() {
  return (
    <div className="card observatory-fill">
      <div className="row">
        <b>Pair this device to open Observatory</b>
        <span className="grow" />
        <span className="pill">authentication required</span>
      </div>
      <p className="muted">
        The gateway is online. Pair in Settings once; Observatory will open
        automatically and remain signed in on this device.
      </p>
      <button onClick={() => { window.location.hash = "settings"; }}>
        Open Settings
      </button>
    </div>
  );
}

/** The designed fallback when /v1/health doesn't answer. */
function BrainDownCard({ onRetry }: { onRetry: () => void }) {
  const native = brainAvailable();
  const [starting, setStarting] = useState(false);
  const [msg, setMsg] = useState("");

  const start = useCallback(async () => {
    setStarting(true);
    setMsg("Starting the brain…");
    try {
      await brainStart();
      // The gateway needs a moment to bind; poll health before flipping back.
      for (let i = 0; i < 15; i++) {
        if (await pingHealth()) {
          setStarting(false);
          setMsg("");
          onRetry();
          return;
        }
        await new Promise((res) => setTimeout(res, 1000));
      }
      setMsg("Started, but the gateway isn't answering yet — retry in a moment.");
    } catch (e) {
      setMsg(String(e));
    }
    setStarting(false);
  }, [onRetry]);

  return (
    <div className="card observatory-fill">
      <div className="row">
        <b>The brain is offline</b>
        <span className="grow" />
        <span className="pill">gateway down</span>
      </div>
      <p className="muted">
        The Observatory streams live from your local muse gateway at{" "}
        <span className="mono">{getGatewayBase()}</span>, and it isn’t answering.
        Start the brain — <span className="mono">muse cockpit serve</span> — and
        this view comes alive.
      </p>
      <div className="row">
        {native && (
          <button className="primary" onClick={() => void start()} disabled={starting}>
            {starting ? "Starting…" : "Start the brain"}
          </button>
        )}
        <button onClick={onRetry} disabled={starting}>
          Retry
        </button>
        {!native && (
          <span className="muted">
            Running in a browser — start the gateway from a terminal, then retry.
          </span>
        )}
      </div>
      {msg && <div className="hint">{msg}</div>}
    </div>
  );
}
