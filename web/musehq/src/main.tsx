import { render } from "solid-js/web"
import "./theme.css"
import App from "./App"

const root = document.getElementById("root")
if (!root) throw new Error("#root not found")
render(() => <App />, root)

// Register the migration kill-switch worker (public/sw.js) to retire any stale
// cockpit service worker. Kept here (a module script) rather than inline in the
// HTML so the page carries no inline <script> and CSP script-src can be 'self'.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {})
  })
}
