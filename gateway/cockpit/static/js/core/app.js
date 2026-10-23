// muse cockpit — boot + header + router.
//
// Reads the token, wires the header (token dialog, pairing flow, emergency
// stop, health-ping dot, live indicator from the jobs stream), builds the nav,
// and routes: on nav select it shows the matching <section id="view-<key>">,
// lazy dynamic-imports /cockpit/js/views/<key>.js, and calls mount(container,
// ctx) once — then show/hide + optional onShow/onHide on subsequent switches.

import * as api from "/cockpit/js/core/api.js";
import * as components from "/cockpit/js/core/components.js";

const $ = (s) => document.querySelector(s);

// The 11 nav keys, in order. Each maps to a <section id="view-<key>"> in the
// shell and a /cockpit/js/views/<key>.js module exporting mount().
const NAV_KEYS = [
  "chat", "jobs", "approvals", "routes", "autonomy",
  "observatory", "memory", "evidence", "graph", "learning", "runtime",
];

// ======================================================================== //
// Header: health dot + live indicator
// ======================================================================== //
let streamLive = false; // set true by the jobs stream heartbeat; wins over health

function setDot(cls, text) {
  $("#dot").className = "dot " + cls;
  $("#statustext").textContent = text;
}

// Views (the jobs stream) call this to drive the header "live" dot.
function setLive(on) {
  streamLive = on;
  if (on) setDot("live", "live");
}

async function ping() {
  const ok = await api.health();
  if (!streamLive) setDot(ok ? "ok" : "off", ok ? "online" : "offline");
  $("#offline").classList.toggle("show", !ok);
}

// ======================================================================== //
// Header: token + pairing
// ======================================================================== //
function refreshTokenUi() {
  const token = api.getToken();
  $("#tokenbtn").textContent = token ? "Token ✓" : "Token";
  $("#pairbanner").classList.toggle("show", !token);
}

// Other modules (and the pairing flow) call this after the token changes so the
// active view can react (e.g. the jobs stream reconnects).
function onTokenChanged() {
  refreshTokenUi();
  emit("token", api.getToken());
}

function wireToken() {
  const open = () => { $("#tokenin").value = api.getToken(); $("#tokendlg").showModal(); };
  $("#tokenbtn").addEventListener("click", open);
  $("#tokenpastebtn").addEventListener("click", open);
  $("#tokensave").addEventListener("click", () => {
    api.setToken($("#tokenin").value);
    onTokenChanged();
  });
}

let pendingPairCode = "";
let pendingPairId = "";
function wirePairing() {
  $("#pairbtn").addEventListener("click", () => {
    $("#paircode").textContent = "";
    $("#pairmsg").textContent = "";
    $("#pairconfirmrow").style.display = "none";
    $("#pairconfirm").disabled = true;
    pendingPairCode = "";
    pendingPairId = "";
    $("#pairdlg").showModal();
  });

  $("#pairstart").addEventListener("click", async () => {
    $("#pairmsg").textContent = "Requesting a pairing code…";
    try {
      // pair/start is unauthenticated by design (a new device has no token).
      const r = await fetch("/v1/cockpit/pair/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_name: $("#pairname").value.trim() }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        $("#pairmsg").textContent = "Pairing unavailable: " + (d.error || r.status) + (d.hint ? " — " + d.hint : "");
        return;
      }
      pendingPairId = d.pairing_id || "";
      pendingPairCode = d.pairing_code || "";
      $("#paircode").textContent = "code: " + pendingPairCode;
      $("#pairconfirmrow").style.display = "block";
      $("#pairconfirm").disabled = false;
      $("#pairmsg").textContent = "Code generated. Press Confirm & pair to finish.";
    } catch (e) { $("#pairmsg").textContent = "Pairing failed: " + e; }
  });

  $("#pairconfirm").addEventListener("click", async () => {
    const phrase = $("#pairphrase").value.trim();
    if (!pendingPairId || !pendingPairCode) { $("#pairmsg").textContent = "Get a pairing code first."; return; }
    $("#pairmsg").textContent = "Confirming…";
    try {
      const body = { pairing_id: pendingPairId, pairing_code: pendingPairCode };
      if (phrase) body.authorization = phrase; // only sent if the user typed one
      const r = await fetch("/v1/cockpit/pair/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json().catch(() => ({}));
      if (r.status === 403) { $("#pairmsg").textContent = "Owner authorization required — re-enter the exact phrase."; return; }
      if (!r.ok || !d.token) { $("#pairmsg").textContent = "Pairing failed: " + (d.error || r.status); return; }
      api.setToken(d.token);
      $("#pairphrase").value = "";
      pendingPairId = "";
      pendingPairCode = "";
      onTokenChanged();
      $("#pairmsg").textContent = "Paired. This device now has its own token.";
      setTimeout(() => $("#pairdlg").close(), 700);
    } catch (e) { $("#pairmsg").textContent = "Pairing failed: " + e; }
  });
}

// ======================================================================== //
// Header: emergency stop (confirm() gated)
// ======================================================================== //
function wireEmergencyStop() {
  $("#estop").addEventListener("click", async () => {
    if (!api.getToken()) { $("#pairdlg").showModal(); return; }
    if (!confirm("Emergency stop: cancel all jobs and latch autonomy to read-only?")) return;
    try {
      await api.postJSON("/v1/cockpit/emergency-stop", {});
      alert("Emergency stop engaged.");
    } catch (e) { alert("Emergency stop failed: " + (e.status || e)); }
  });
}

// ======================================================================== //
// Lightweight app event bus (token changes, live indicator hooks)
// ======================================================================== //
const listeners = {};
function on(name, fn) { (listeners[name] = listeners[name] || []).push(fn); }
function emit(name, payload) { (listeners[name] || []).forEach((fn) => { try { fn(payload); } catch (e) {} }); }

// ======================================================================== //
// Router
// ======================================================================== //
// ctx passed to every view's mount(container, ctx).
const ctx = {
  api,
  components,
  els: {}, // shared element refs (header dot, etc.) — see boot()
  // Lifecycle hooks a view may call:
  setLive,                         // drive the header live dot from the jobs stream
  onTokenChange: (fn) => on("token", fn), // subscribe to token changes
};

const mounted = new Map(); // key → { instance:{onShow,onHide}, container }
let current = null;

async function show(key) {
  if (!NAV_KEYS.includes(key) || key === current) {
    if (key === current) return;
  }
  // Toggle nav active state.
  document.querySelectorAll(".nav-item").forEach((b) =>
    b.classList.toggle("active", b.dataset.nav === key));
  // Hide the outgoing view.
  if (current) {
    const prev = mounted.get(current);
    document.getElementById("view-" + current)?.classList.remove("active");
    if (prev?.instance?.onHide) { try { prev.instance.onHide(); } catch (e) {} }
  }
  current = key;
  try { location.hash = key; } catch (e) {}

  const container = document.getElementById("view-" + key);
  container.classList.add("active");

  // Lazy mount once; show/hide thereafter.
  let entry = mounted.get(key);
  if (!entry) {
    entry = { instance: null, container };
    mounted.set(key, entry);
    try {
      const mod = await import("/cockpit/js/views/" + key + ".js");
      const instance = (mod && typeof mod.mount === "function")
        ? await mod.mount(container, ctx)
        : null;
      entry.instance = instance || {};
    } catch (e) {
      entry.instance = {};
      container.replaceChildren(
        components.emptyState({
          title: "View unavailable",
          body: 'Could not load "' + key + '". ' + (e && e.message ? e.message : ""),
        })
      );
    }
  }
  if (entry.instance?.onShow) { try { entry.instance.onShow(); } catch (e) {} }
}

function wireNav() {
  document.querySelectorAll(".nav-item").forEach((b) =>
    b.addEventListener("click", () => show(b.dataset.nav)));
}

function initialKey() {
  const h = (location.hash || "").replace(/^#/, "");
  return NAV_KEYS.includes(h) ? h : NAV_KEYS[0];
}

// ======================================================================== //
// Boot
// ======================================================================== //
function boot() {
  ctx.els = { dot: $("#dot"), statustext: $("#statustext"), header: $(".app-header") };

  refreshTokenUi();
  wireToken();
  wirePairing();
  wireEmergencyStop();
  wireNav();

  ping();
  setInterval(ping, 10000);

  window.addEventListener("hashchange", () => {
    const h = (location.hash || "").replace(/^#/, "");
    if (NAV_KEYS.includes(h) && h !== current) show(h);
  });

  show(initialKey());
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
