/**
 * App shell.
 *
 * The lean Singularity client: an app on the void with a header lockup (animated
 * glyph + "muse" wordmark + a connection status dot), a nav driven by the
 * append-only route registry, and a minimal hash router that renders the active
 * route. Adding a route is purely additive — register it in src/routes.ts and it
 * shows up here automatically; this file never needs to change to add surfaces.
 */
import { useEffect, useState } from "react";
import { Glyph } from "./components/Glyph";
import { Dock } from "./components/Dock";
import { getRoutes, type RouteDef } from "./routes";
import { pingHealth } from "./lib/gateway";
import "./styles/app.css";

type Health = "connecting" | "online" | "offline";

// Tauri invoke — uses the native Rust gateway_status command which probes
// /v1/health over a raw TCP socket (no CSP / WebView2 fetch restriction).
// Falls back to the fetch-based pingHealth when not running inside Tauri.
async function nativeHealth(): Promise<boolean> {
  try {
    const inv = (
      window as unknown as {
        __TAURI__?: { core?: { invoke?: (cmd: string, args?: unknown) => Promise<unknown> } };
      }
    ).__TAURI__?.core?.invoke;
    if (inv) {
      const status = await inv("gateway_status") as { reachable?: boolean };
      return status?.reachable === true;
    }
  } catch {
    // invoke failed — fall through to fetch
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
    return routeList[0]?.id ?? "";
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

  // Keyboard nav — Cmd/Ctrl+1..n selects the nth registered route. The route
  // registry is append-only, so digit → index is stable across releases.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
      const n = Number(e.key);
      if (!Number.isInteger(n) || n < 1) return;
      const route = getRoutes()[n - 1];
      if (!route) return;
      e.preventDefault();
      window.location.hash = "#/" + route.id;
      setActiveId(route.id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const active: RouteDef | undefined =
    routeList.find((r) => r.id === activeId) ?? routeList[0];

  const select = (id: string) => {
    window.location.hash = "#/" + id;
    setActiveId(id);
  };

  return (
    <div className="app">
      <header className="app-header">
        <span className="brand">
          <Glyph size={28} />
          <span className="wordmark">
            muse
            <span className="full">Multi-Use Synaptic Entity</span>
          </span>
        </span>
        <span className="grow" />
        <span className="status">
          <span
            className={"dot " + (health === "online" ? "ok" : health === "offline" ? "off" : "")}
          />
          <span>
            {health === "online" ? "online" : health === "offline" ? "offline" : "connecting…"}
          </span>
        </span>
      </header>

      <nav className="app-nav">
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

      {health === "offline" && (
        <div className="offline-banner" role="status">
          <span>
            Offline — can’t reach the gateway. Is{" "}
            <span className="mono">hermes cockpit serve</span> running? Check
            the gateway URL in Settings.
          </span>
          <button className="retry" onClick={retryHealth}>
            Retry
          </button>
        </div>
      )}

      <main className="app-main">{active ? active.render() : null}</main>

      {/* Global overlay: the movable MUSE dock floats above every surface.
          Not a route — mounted once here so it persists across navigation. */}
      <Dock />
    </div>
  );
}
