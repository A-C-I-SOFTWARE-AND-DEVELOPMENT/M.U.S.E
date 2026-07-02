/**
 * Settings — gateway connection, the brain process, device pairing, and the
 * Emergency stop.
 *
 * Four cards:
 *   1. Gateway — view/change the gateway base URL (persisted in localStorage
 *      `muse.gateway.base`); a live health ping confirms reachability.
 *   2. Brain (gateway process) — native-shell only: running/stopped status,
 *      the detected `muse` binary, autostart toggle, and start/stop buttons
 *      wired to the shell's brain commands (lib/brain → src-tauri/src/brain.rs).
 *   3. Device pairing — the scaffold's owner-gated pairing flow (pair/start →
 *      pair/confirm), plus paste-a-token and clear-token. The bearer token lives
 *      only in localStorage `muse.cockpit.token`; the owner phrase is entered to
 *      confirm and never stored.
 *   4. Emergency stop — POST /v1/cockpit/emergency-stop (cancel all jobs, latch
 *      autonomy to read-only). Owner-gated and styled as a danger action; the
 *      owner phrase is prompted for at action time and a 403 re-prompts once.
 *
 * Reuses lib/gateway + lib/brain exclusively; no secrets in code.
 */
import { useCallback, useEffect, useState } from "react";
import {
  autoPairLocal,
  DEFAULT_GATEWAY_BASE,
  emergencyStop,
  getGatewayBase,
  getToken,
  isLoopbackBase,
  pairConfirm,
  pairStart,
  pingHealth,
  promptOwnerPhrase,
  setGatewayBase,
  setToken,
  TOKEN_EVENT,
} from "../lib/gateway";
import {
  autostartSet,
  brainAvailable,
  brainStart,
  brainStatus,
  brainStop,
  type BrainStatus,
} from "../lib/brain";

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
      <UpdatesCard />
      <BrainCard />
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
        The local muse gateway this client talks to. Default{" "}
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

// ---- updates --------------------------------------------------------------

/**
 * Rolling desktop release — always the latest installer for every OS
 * (.dmg / .exe / .AppImage / .deb). Installing it over the current build is how
 * the app updates.
 */
const LATEST_DESKTOP_RELEASE_URL =
  "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/releases/tag/muse-desktop-latest";

/**
 * Manual "install update": shows the installed version and a one-click link to
 * download the latest installer for the user's OS. Running it updates in place
 * (settings preserved). No background/auto-update and no signing-key machinery —
 * just the always-fresh installer. Opening the release page uses the same
 * external-link path as the rest of Settings (Tauri opens it in the browser).
 */
function UpdatesCard() {
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const g = window as unknown as {
          __TAURI__?: { app?: { getVersion?: () => Promise<string> } };
        };
        const v = await g.__TAURI__?.app?.getVersion?.();
        if (alive && v) setVersion(v);
      } catch {
        // Plain browser build / API unavailable — leave the version unknown.
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="card">
      <div className="row">
        <b>Updates</b>
      </div>
      {version && (
        <div className="row">
          <span className="k">Installed version</span>
          <span className="mono">{version}</span>
        </div>
      )}
      <p className="muted">
        M.U.S.E. updates by installing the latest build over the current one.
        Download the installer for your OS and run it — your settings are kept.
      </p>
      <div className="row gap-top">
        <a
          className="primary"
          href={LATEST_DESKTOP_RELEASE_URL}
          target="_blank"
          rel="noreferrer"
        >
          Download the latest installer
        </a>
      </div>
    </div>
  );
}

// ---- brain (gateway process) ------------------------------------------------

/** GitHub README with the CLI install one-liner. */
const INSTALL_DOCS_URL =
  "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse#readme";

function BrainCard() {
  const native = brainAvailable();
  const [status, setStatus] = useState<BrainStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const refresh = useCallback(async () => {
    setStatus(await brainStatus());
  }, []);

  useEffect(() => {
    if (!native) return;
    void refresh();
    const t = setInterval(() => void refresh(), 10000);
    return () => clearInterval(t);
  }, [native, refresh]);

  const start = useCallback(async () => {
    setBusy(true);
    setMsg("Starting the brain…");
    try {
      setStatus(await brainStart());
      setMsg("Start requested — the status flips to running once it answers health.");
    } catch (e) {
      setMsg(String(e));
    }
    setBusy(false);
  }, []);

  const stop = useCallback(async () => {
    setBusy(true);
    setMsg("Stopping…");
    try {
      setStatus(await brainStop());
      setMsg("Stopped the managed gateway process.");
    } catch (e) {
      setMsg(String(e));
    }
    setBusy(false);
  }, []);

  const toggleAutostart = useCallback(
    async (enabled: boolean) => {
      await autostartSet(enabled);
      void refresh();
    },
    [refresh],
  );

  return (
    <div className="card">
      <div className="row">
        <b>Brain (gateway)</b>
        <span className="grow" />
        <span className={"streamdot " + (status?.reachable ? "live" : "")}>
          <span className="dot-mini" />
          {status == null ? (native ? "checking…" : "n/a") : status.reachable ? "running" : "stopped"}
        </span>
      </div>
      {!native ? (
        <p className="muted">
          Available in the desktop app only — this browser build can’t manage the
          gateway process. Start it from a terminal:{" "}
          <span className="mono">muse cockpit serve</span>.
        </p>
      ) : (
        <>
          <p className="muted">
            The local muse gateway process. With autostart on, the app starts it
            for you at launch (when the <span className="mono">muse</span> CLI is
            installed) and stops it when you quit — never on hide-to-tray.
          </p>
          <div className="row">
            <span className="k">Binary</span>
            {status?.binary ? (
              <span className="mono">{status.binary}</span>
            ) : (
              <span className="muted">
                not found — install the muse CLI via the one-liner (
                <a href={INSTALL_DOCS_URL} target="_blank" rel="noreferrer">
                  docs
                </a>
                )
              </span>
            )}
            {status?.managed && <span className="pill">managed by this app</span>}
          </div>
          <div className="row gap-top">
            <label className="row">
              <input
                type="checkbox"
                checked={status?.autostart ?? false}
                onChange={(e) => void toggleAutostart(e.target.checked)}
              />
              Start the brain automatically when the app opens
            </label>
          </div>
          <div className="row gap-top">
            <button
              className="primary"
              onClick={() => void start()}
              disabled={busy || status?.reachable === true}
            >
              Start
            </button>
            <button onClick={() => void stop()} disabled={busy || !status?.managed}>
              Stop
            </button>
            <button onClick={() => void refresh()} disabled={busy}>
              Refresh
            </button>
          </div>
          {msg && <div className="hint">{msg}</div>}
        </>
      )}
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

  // Keep the paired pill live when auto-pairing lands in the background.
  useEffect(() => {
    const refresh = () => setPaired(Boolean(getToken()));
    window.addEventListener(TOKEN_EVENT, refresh);
    return () => window.removeEventListener(TOKEN_EVENT, refresh);
  }, []);

  const autoConnect = useCallback(async () => {
    setBusy(true);
    setMsg("Connecting to the local gateway…");
    const outcome = await autoPairLocal({ force: true });
    setBusy(false);
    if (outcome === "paired") {
      setPaired(true);
      setMsg("Connected. A fresh token for this device was minted and stored.");
    } else if (outcome === "blocked") {
      setMsg(
        "This gateway requires the owner phrase (it accepts remote connections) — pair manually below.",
      );
    } else {
      setMsg(
        "Couldn't connect — the gateway didn't answer (or pairing is rate-limited; wait ~30s and retry).",
      );
    }
  }, []);

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
      {isLoopbackBase() && (
        <>
          <p className="muted">
            On this PC, muse connects to its local gateway <b>automatically</b> —
            no code or phrase needed. Use the button below to reconnect (for
            example after clearing the token).
          </p>
          <div className="row">
            <button className="primary" onClick={() => void autoConnect()} disabled={busy}>
              {paired ? "Reconnect (mint a fresh token)" : "Connect to this PC's gateway"}
            </button>
          </div>
          <div className="divider" />
        </>
      )}

      <p className="muted">
        Pairing a <b>remote</b> device: generate a short-lived pairing code, then
        confirm it with the owner phrase. A per-device token is minted once and
        stored only on this device (localStorage). The owner phrase is never
        stored.
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
        this if muse is doing something it shouldn’t. You’ll confirm and enter
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
