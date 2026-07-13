/**
 * App shell — Singularity design.
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────────┐
 *   │ header (lockup + status)                            │
 *   ├──────────────┬──────────────────────────────────────┤
 *   │ nav rail     │ main (view)                           │
 *   │              │                                        │
 *   │              │                                        │
 *   └──────────────┴──────────────────────────────────────┘
 *
 * SacredGeometry canvas sits fixed behind the app shell (z-index: 0).
 * The app shell is z-index: 2 with semi-transparent header/nav for depth.
 *
 * Adding a route is purely additive — register it in routes.register.ts
 * and it appears in the nav automatically. This file never changes.
 */
import { useEffect, useState } from "react";
import { SacredGeometry } from "./components/SacredGeometry";
import { Glyph } from "./components/Glyph";
import { Dock } from "./components/Dock";
import { getRoutes, type RouteDef } from "./routes";
import { autoPairLocal, getToken, pingHealth } from "./lib/gateway";
import "./styles/app.css";

type Health = "connecting" | "online" | "offline";

// Tauri invoke — uses the native Rust gateway_status command which probes
// /v1/health over a raw TCP socket (no CSP / WebView2 fetch restriction).
// Falls back to the fetch-based pingHealth when not running inside Tauri.
async function nativeHealth(): Promise<boolean> {
  if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
    try {
      const internals = (window as unknown as {
        __TAURI_INTERNALS__?: {
          invoke?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
        };
      }).__TAURI_INTERNALS__;
      const status = await internals!.invoke!("gateway_status") as { reachable?: boolean };
      return status?.reachable === true;
    } catch {
      return false;
    }
  }
  return pingHealth();
}

function currentHashId(): string {
  return (window.location.hash || "").replace(/^#\/?/, "");
}

export function App() {
  const routeList = getRoutes();
  const [activeId, setActiveId] = useState<string>(() => {
    const fromHash = currentHashId();
    if (fromHash && routeList.some((r) => r.id === fromHash)) return fromHash;
    const omni = routeList.find((r) => r.id === "omni");
    return omni?.id ?? routeList.find((r) => r.id === "chat")?.id ?? routeList[0]?.id ?? "";
  });
  const [health, setHealth] = useState<Health>("connecting");

  // Hash routing — keep the active view in sync with the URL hash.
  useEffect(() => {
    const onHash = () => {
      const id = currentHashId();
      if (id && getRoutes().some((r) => r.id === id)) setActiveId(id);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // Health poll — drives the status dot. Mirrors the cockpit's 10s cadence.
  // Bumping `healthNonce` (the offline banner's Retry) re-runs the ping
  // immediately and restarts the interval.
  const [healthNonce, setHealthNonce] = useState(0);
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const ok = await nativeHealth();
      if (alive) setHealth(ok ? "online" : "offline");
      // Zero-touch connect: the gateway is up but this device holds no token
      // (first run, cleared storage, or the brain finished booting after the
      // pre-render attempt). autoPairLocal() is single-flight, spaced, and a
      // no-op outside the native shell / off-loopback — safe to call each tick.
      if (ok && !getToken()) void autoPairLocal();
    };
    void tick();
    const t = setInterval(() => void tick(), 10000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [healthNonce]);

  const retryHealth = () => {
    setHealth("connecting");
    setHealthNonce((n) => n + 1);
  };

  const select = (id: string) => {
    window.location.hash = "#/" + id;
    setActiveId(id);
  };

  const active: RouteDef | undefined =
    routeList.find((r) => r.id === activeId) ?? routeList[0];

  return (
    <>
      {/* Depth pool canvas — fixed behind the app shell, full viewport. */}
      <SacredGeometry width={520} height={480} className="sacred-geometry" />

      <div className={"app" + (active?.id === "omni" ? " app--omni" : "")}>
        {/* Header / lockup */}
        <header className="app-header">
          <span className="brand">
            <span className="glyph">
              <span
                style={{
                  position: "absolute",
                  inset: "-14px",
                  borderRadius: "50%",
                  pointerEvents: "none",
                  background:
                    "radial-gradient(circle at 50% 50%, rgba(122,224,255,0.10) 0%, rgba(122,224,255,0) 70%)",
                }}
              />
              <Glyph size={30} spin={true} />
            </span>
            <span className="wordmark">
              muse
              <span className="full">Multi-Use Synaptic Entity</span>
            </span>
          </span>

          <span className="grow" />

          <span className="status">
            <span
              className={
                "dot " +
                (health === "online"
                  ? "ok"
                  : health === "offline"
                  ? "off"
                  : "")
              }
            />
            <span>
              {health === "online"
                ? "online"
                : health === "offline"
                ? "offline"
                : "connecting…"}
            </span>
          </span>
        </header>

        {/* Left nav rail — driven by the append-only route registry. */}
        <nav className="app-nav" aria-label="muse destinations">
          {routeList.map((r) => (
            <button
              key={r.id}
              className={"nav-item" + (r.id === active?.id ? " active" : "")}
              onClick={() => select(r.id)}
            >
              {r.label}
            </button>
          ))}
        </nav>

        {/* Main view */}
        <main className={"app-main" + (active?.id === "omni" ? " app-main--omni" : "")}>
          {active?.id === "omni" && (
            <button className="omni-desktop-return" onClick={() => select("chat")} aria-label="Return to desktop workspace">
              <span aria-hidden="true">←</span>
              Desktop
            </button>
          )}
          {health === "offline" && (
            <div className="offline-banner" role="status">
              <span>
                Offline — can't reach the gateway. Start the brain in Settings
                (or run <span className="mono">muse cockpit serve</span>), then
                retry.
              </span>
              <button className="retry" onClick={retryHealth}>
                Retry
              </button>
            </div>
          )}

          <section className={"view" + (active?.id === "omni" ? " view--omni" : "")}>
            {active ? active.render() : null}
          </section>
        </main>

        {/* Global overlay: the movable MUSE dock floats above desktop surfaces. */}
        {active?.id !== "omni" && <Dock />}
      </div>
    </>
  );
}

export default App;
