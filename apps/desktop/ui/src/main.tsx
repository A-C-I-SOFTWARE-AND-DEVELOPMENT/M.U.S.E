import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
// Seed the route registry (side-effect import) BEFORE rendering the shell.
import "./routes.register";
import { App } from "./App";
import "./styles/tokens.css";

// Register the PWA service worker (autoUpdate). No-op in the Tauri shell and in
// dev (devOptions.enabled = false), so this is safe everywhere.
registerSW({ immediate: true });

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("missing #root element");

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
