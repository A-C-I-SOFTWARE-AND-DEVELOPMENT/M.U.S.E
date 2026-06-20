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

// Register the PWA service worker (autoUpdate). No-op in the Tauri shell and in shell and in
// dev (devOptions.enabled = false), so this is safe everywhere.
registerSW({ immediate: true });

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("missing #root element");

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
