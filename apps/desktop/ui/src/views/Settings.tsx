/**
 * Settings — gateway connection, device pairing, and the Emergency stop.
 *
 * Three cards:
 *   1. Gateway — view/change the gateway base URL (persisted in localStorage
 *      `muse.gateway.base`); a live health ping confirms reachability.
 *   2. Device pairing — the scaffold's owner-gated pairing flow (pair/start →
 *      pair/confirm), plus paste-a-token and clear-token. The bearer token lives
 *      only in localStorage `muse.cockpit.token`; the owner phrase is entered to
 *      confirm and never stored.
 *   3. Emergency stop — POST /v1/cockpit/emergency-stop (cancel all jobs, latch
 *      autonomy to read-only). Owner-gated and styled as a danger action; the
 *      owner phrase is prompted for at action time and a 403 re-prompts once.
 *
 * Reuses lib/gateway exclusively; no secrets in code.
 */
import { useCallback, useEffect, useState } from "react";
import {
  DEFAULT_GATEWAY_BASE,
  emergencyStop,
  getGatewayBase,
  getToken,
  pairConfirm,
  pairStart,
  pingHealth,
  promptOwnerPhrase,
  setGatewayBase,
  setToken,
} from "../lib/gateway";

export function Settings() {
  return (
    <div className="view">
      <div className="section-header">
        <div>
          <div className="eyebrow">Device</div>
          <h2 className="section-title">Settings</h2>
        </div>
      </div>
      <GatewayCard />
      <PairingCard />
      <EmergencyCard />
    </div>
  );
}

// ---- gateway URL ----------------------------------------------------------

function GatewayCard() {
  const [base, setBase] = useState<string>(() => getGatewayBase());
  const [health, setHealth] = useState<"unknown" | "online" | "offline">("unknown");
  const [saved, setSaved] = useState(false);

  const check = useCallback(async () => {
    setHealth((await pingHealth()) ? "online" : "offline");
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  const save = useCallback(() => {
    setGatewayBase(base);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
    void check();
  }, [base, check]);

  return (
    <div className="card">
      <div className="row">
        <b>Gateway</b>
        <span className="grow" />
        <span className={"streamdot " + (health === "online" ? "live" : "")}>
          <span className="dot-mini" />
          {health === "online" ? "reachable" : health === "offline" ? "unreachable" : "checking…"}
        </span>
      </div>
      <p className="muted">
        The local M.U.S.E. gateway this client talks to. Default{" "}
        <span className="mono">{DEFAULT_GATEWAY_BASE}</span>.
      </p>
      <div className="row">
        <input
          type="text"
          placeholder={DEFAULT_GATEWAY_BASE}
          value={base}
          onChange={(e) => setBase(e.target.value)}
          className="flex-1"
        />
        <button onClick={() => void check()}>Test</button>
        <button className="primary" onClick={save}>
          Save
        </button>
        {saved && <span className="muted">Saved.</span>}
      </div>
    </div>
  );
}

// ---- pairing / token ------------------------------------------------------

function PairingCard() {
  const [paired, setPaired] = useState<boolean>(() => Boolean(getToken()));
  const [deviceName, setDeviceName] = useState("");
  const [code, setCode] = useState("");
  const [phrase, setPhrase] = useState("");
  const [pasteToken, setPasteToken] = useState("");
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
    setCode("");
    setMsg("Paired. This device now has its own token.");
    setPaired(true);
  }, [code, phrase]);

  const savePastedToken = useCallback(() => {
    const t = pasteToken.trim();
    if (!t) return;
    setToken(t);
    setPasteToken("");
    setPaired(true);
    setMsg("Token saved on this device.");
  }, [pasteToken]);

  const clearToken = useCallback(() => {
    setToken("");
    setPaired(false);
    setMsg("Token cleared. This device is no longer paired.");
  }, []);

  return (
    <div className="card" style={{ borderColor: "var(--ring-1)" }}>
      <div className="row">
        <b>Device pairing</b>
        <span className="grow" />
        <span className="pill">{paired ? "paired ✓" : "not paired"}</span>
        <span className="pill">owner-gated</span>
      </div>
      <p className="muted">
        Generate a short-lived pairing code, then confirm it with the owner
        phrase. A per-device token is minted once and stored only on this device
        (localStorage). The owner phrase is never stored.
      </p>

      <div className="row">
        <input
          type="text"
          placeholder="Device name (optional)"
          value={deviceName}
          onChange={(e) => setDeviceName(e.target.value)}
          className="flex-1"
        />
        <button className="primary" onClick={() => void start()} disabled={busy}>
          Get pairing code
        </button>
        {code && <span className="mono">code: {code}</span>}
      </div>

      {code && (
        <div className="row gap-top">
          <input
            type="password"
            placeholder="Owner authorization phrase"
            value={phrase}
            onChange={(e) => setPhrase(e.target.value)}
            className="flex-1"
            autoComplete="off"
          />
          <button className="primary" onClick={() => void confirm()} disabled={busy}>
            Confirm &amp; pair
          </button>
        </div>
      )}

      <div className="divider" />

      <div className="row">
        <span className="k">Paste a token instead</span>
        <input
          type="password"
          placeholder="cockpit token"
          value={pasteToken}
          onChange={(e) => setPasteToken(e.target.value)}
          className="flex-1"
          autoComplete="off"
        />
        <button onClick={savePastedToken} disabled={!pasteToken.trim()}>
          Save token
        </button>
        {paired && (
          <button onClick={clearToken} className="danger">
            Clear token
          </button>
        )}
      </div>

      {msg && <div className="hint">{msg}</div>}
    </div>
  );
}

// ---- emergency stop -------------------------------------------------------

function EmergencyCard() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const stop = useCallback(async () => {
    setMsg("");
    if (!getToken()) {
      setMsg("Pair this device first.");
      return;
    }
    const ok = window.confirm(
      "Emergency stop: cancel all jobs and latch autonomy to read-only?",
    );
    if (!ok) return;
    // Owner-gated: prompt for the phrase at action time; never stored.
    const phrase = promptOwnerPhrase("Emergency stop (cancel all jobs, latch read-only)");
    if (phrase == null) return;
    setBusy(true);
    let res = await emergencyStop(phrase);
    if (res.forbidden) {
      const retry = promptOwnerPhrase(
        "Authorization required — re-enter the exact phrase to emergency-stop",
      );
      if (retry == null) {
        setBusy(false);
        return;
      }
      res = await emergencyStop(retry);
    }
    setBusy(false);
    setMsg(
      res.ok
        ? "Emergency stop engaged. All jobs cancelled; autonomy latched to read-only."
        : "Emergency stop failed" +
            (res.forbidden ? " — authorization rejected" : "") +
            (res.error ? " (" + res.error + ")" : "") +
            ".",
    );
  }, []);

  return (
    <div className="card danger-card">
      <div className="row">
        <b>Emergency stop</b>
        <span className="grow" />
        <span className="pill">owner-gated</span>
      </div>
      <p className="muted">
        Immediately cancel all running jobs and latch autonomy to read-only. Use
        this if M.U.S.E. is doing something it shouldn’t. You’ll confirm and enter
        the owner phrase.
      </p>
      <div className="row">
        <button className="danger" onClick={() => void stop()} disabled={busy}>
          ■ Emergency stop
        </button>
      </div>
      {msg && <div className="hint">{msg}</div>}
    </div>
  );
}
