import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
// Seed the route registry (side-effect imports) BEFORE rendering the shell.
// The scaffold registers Home; the DESK client surfaces register their own
// routes from their own module (views/register), keeping registration additive
// and conflict-free.
import "./routes.register";
import "./views/register";
// Design-system tokens (generated from design-system/tokens.json).
// The alias "@muse/design-system" resolves to the design-system root;
// import the generated tokens.css directly from dist/.
import "@muse/design-system/dist/tokens.css";
// Desktop-local token overrides / aliases (motion curves not yet reconciled).
import "./styles/tokens.css";
import { App } from "./App";
import { autoPairLocal } from "./lib/gateway";

const inTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

// The native shell must never be controlled by a service worker: its assets
// are versioned inside the executable, while an old PWA cache can survive an
// installer update and serve stale Chat/Observatory code. Older builds did
// register one, so actively remove legacy registrations and caches once.
async function clearLegacyNativePwa(): Promise<boolean> {
  if (!inTauri || !("serviceWorker" in navigator)) return false;
  const controlled = Boolean(navigator.serviceWorker.controller);
  const registrations = await navigator.serviceWorker.getRegistrations().catch(() => []);
  await Promise.all(registrations.map((registration) => registration.unregister()));
  if ("caches" in window) {
    const keys = await caches.keys().catch(() => []);
    await Promise.all(keys.map((key) => caches.delete(key)));
  }
  const reloadKey = "muse.native-pwa-cleared";
  if (controlled && sessionStorage.getItem(reloadKey) !== "1") {
    sessionStorage.setItem(reloadKey, "1");
    return true;
  }
  sessionStorage.removeItem(reloadKey);
  return false;
}

if (!inTauri) {
  registerSW({ immediate: true });
}

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("missing #root element");

function render(): void {
  createRoot(rootEl!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

async function bootstrap(): Promise<void> {
  if (await clearLegacyNativePwa()) {
    window.location.reload();
    return;
  }
  // Zero-touch connect: inside the native shell, silently pair with the local
  // gateway BEFORE first paint so the app mounts already-connected (no pairing
  // card flash). Bounded by a short timeout — if the gateway is still booting,
  // render immediately and let the App's health tick finish pairing.
  await Promise.race([
    autoPairLocal().catch(() => undefined),
    new Promise((res) => setTimeout(res, 1200)),
  ]);
  render();
}

void bootstrap();
