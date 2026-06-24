/* muse Neural Observatory — the live 3D map of muse's mind.
 *
 * Renders real gateway data only (docs/synapse/design/10-observatory-spec.md):
 * the GraphRAG cluster galaxy, live job pipelines, the three-tier brain
 * ladder, measured bottleneck heat, and the recommendation verdict cards.
 * When telemetry is off it says so — nothing on this page is invented.
 *
 * Vendored renderer provenance (no CDN, no build step):
 *   three.js r180 — npm package three@0.180.0, fetched via `npm pack
 *   three@0.180.0` (npm registry tarball three-0.180.0.tgz, sha256
 *   ad66d724565ee29a2467277fa84daa5ed0211d6b8d446e9ef29f6bae0cd14144);
 *   the two build/ files were copied verbatim:
 *     vendor/three.module.min.js  sha256 e2b5ee6bccd38fd6d8a2428546b83c5f2426d84b152ef82be8055556e3b40eb6
 *     vendor/three.core.min.js    sha256 61ba0df005b05991361d040d8ff670e1aadfd0ce7aeebd1fdb0725957a8957de
 *   (three.module.min.js re-exports from its ./three.core.min.js sibling.)
 *   License: MIT, Copyright 2010-2025 Three.js Authors.
 *
 * Owner-gate doctrine: this page NEVER asks for or stores the owner phrase
 * except as a pass-through field inside an explicit diff-card whose exact
 * POST body is shown before firing (autonomy raises only, per the existing
 * /v1/cockpit/autonomy contract). Nothing is cached.
 */

import * as THREE from "./vendor/three.module.min.js";

/* ════════════════════════════════════════════════════════════════════════
 * 0. Tiny DOM + auth helpers (conventions copied from index.html)
 * ════════════════════════════════════════════════════════════════════════ */

const $ = (s) => document.querySelector(s);
const TOKEN_KEY = "muse.cockpit.token";
const BASE_KEY = "muse.cockpit.base";

// Token bootstrap: a launcher may hand us `#token=...&base=...` in the URL
// fragment. Persist, then strip the fragment so the token never sits in the
// address bar or browser history.
(function bootstrapFragment() {
  try {
    const h = window.location.hash || "";
    if (!h.startsWith("#") || (h.indexOf("token=") < 0 && h.indexOf("base=") < 0)) return;
    const params = new URLSearchParams(h.slice(1));
    const t = (params.get("token") || "").trim();
    const b = (params.get("base") || "").trim();
    if (t) localStorage.setItem(TOKEN_KEY, t);
    if (b) localStorage.setItem(BASE_KEY, b.replace(/\/+$/, ""));
    history.replaceState(null, "", window.location.pathname + window.location.search);
  } catch (e) { /* never block boot on a malformed fragment */ }
})();

let token = localStorage.getItem(TOKEN_KEY) || "";
// All API calls are relative to the page origin (the same gateway serves this
// file); a stored base overrides for split deployments.
const apiBase = (localStorage.getItem(BASE_KEY) || "").replace(/\/+$/, "");

// Wallpaper mode: a chromeless, full-bleed, gently auto-orbiting presentation
// for live device wallpapers. Toggled by `?wallpaper=1` on the page URL.
const WALLPAPER = (() => {
  try {
    const v = new URLSearchParams(window.location.search).get("wallpaper");
    return v === "1" || v === "true" || v === "yes";
  } catch (e) { return false; }
})();

// Standalone demo mode: serve a bundled, clearly-labeled static snapshot so the
// Observatory renders without a live gateway (always-on static hosting, e.g.
// GitHub Pages). Opt-in ONLY — enabled when the page sets
// `window.OBSERVATORY_DEMO_URL` (the Pages build does) or is visited with
// `?demo=1`. When off, every code path below is the live one, unchanged.
const DEMO_URL = (() => {
  try {
    if (window.OBSERVATORY_DEMO_URL) return String(window.OBSERVATORY_DEMO_URL);
    const v = new URLSearchParams(window.location.search).get("demo");
    if (v === "1" || v === "true" || v === "yes") return "./observatory-demo.json";
  } catch (e) { /* fall through to live mode */ }
  return "";
})();
const DEMO = !!DEMO_URL;
let demoData = null;

async function loadDemo() {
  try {
    const r = await fetch(DEMO_URL, { cache: "no-store" });
    demoData = await r.json();
  } catch (e) { demoData = null; }
}

// Synthesize a fetch-like Response from the bundled snapshot for the
// /v1/observatory/* GETs the page makes (callers only read .ok/.status/.json()).
function demoResponse(path) {
  const ok = (body) => ({ ok: true, status: 200, json: async () => body });
  const miss = (status) => ({ ok: false, status, json: async () => ({}) });
  if (!demoData) return miss(503);
  const p = path.split("?")[0];
  const snap = demoData.snapshot || {};
  if (p === "/v1/observatory/snapshot") return ok(snap);
  if (p === "/v1/observatory/metrics") return ok(snap.metrics_rollup || {});
  if (p === "/v1/observatory/recommendations")
    return ok(demoData.recommendations || { v: 1, generated_at: "", cards: [] });
  if (p === "/v1/observatory/layout") {
    const cid = new URLSearchParams(path.split("?")[1] || "").get("cluster") || "";
    const lay = (demoData.layouts || {})[cid];
    return lay ? ok(lay) : miss(404);
  }
  return miss(404);
}

function authHeaders(extra) {
  const h = Object.assign({}, extra || {});
  if (token) h["Authorization"] = "Bearer " + token;
  return h;
}
async function api(path, opts) {
  if (DEMO) return demoResponse(path);
  const o = Object.assign({}, opts || {});
  o.headers = authHeaders(o.headers);
  return fetch(apiBase + path, o);
}
// Safe DOM builders — the ONLY way dynamic strings reach the page. String
// children become text nodes (never parsed as HTML); Node children are
// appended as-is. `attrsOrClass` is either a class string or an attribute
// map (null/false values are skipped, true renders a bare attribute).
function el(tag, attrsOrClass, ...children) {
  const node = document.createElement(tag);
  if (typeof attrsOrClass === "string") {
    if (attrsOrClass) node.className = attrsOrClass;
  } else if (attrsOrClass) {
    for (const [k, v] of Object.entries(attrsOrClass)) {
      if (v == null || v === false) continue;
      if (k === "class") node.className = String(v);
      else node.setAttribute(k, v === true ? "" : String(v));
    }
  }
  node.append(...children.flat(Infinity)
    .filter((c) => c != null)
    .map((c) => (c instanceof Node ? c : String(c))));
  return node;
}
function frag(...children) {
  const f = document.createDocumentFragment();
  f.append(...children.flat(Infinity)
    .filter((c) => c != null)
    .map((c) => (c instanceof Node ? c : String(c))));
  return f;
}
function fmtMs(ms) {
  if (ms == null) return "—";
  if (ms < 1000) return Math.round(ms) + " ms";
  if (ms < 60000) return (ms / 1000).toFixed(1) + " s";
  return (ms / 60000).toFixed(1) + " min";
}

/* ════════════════════════════════════════════════════════════════════════
 * 1. Shared state
 * ════════════════════════════════════════════════════════════════════════ */

const state = {
  snapshot: null,          // last /v1/observatory/snapshot body
  metrics: null,           // last /v1/observatory/metrics body
  window: "1h",
  layout: "gateway",       // sacred-geometry galaxy layout (HUD "layout" select)
  graphAvailable: false,
  telemetryLive: false,    // collector has recorded events
  view: "galaxy",
  lastEventId: null,       // SSE Last-Event-ID resume cursor
  connLive: false,
};

const KIND_COLORS = {
  code: new THREE.Color(0x7ae0ff),   // cyan
  docs: new THREE.Color(0xb388ff),   // violet
  memory: new THREE.Color(0xf5c451), // amber
  ledger: new THREE.Color(0x5be3a0), // teal
  other: new THREE.Color(0x9aa3b8),
};
const GRAY = new THREE.Color(0x3c4254);   // heat-null desaturation target
const HOT = new THREE.Color(0xff6a3d);    // bottleneck glow
const HEAT_GLOW_THRESHOLD = 0.6;

function kindForType(t) {
  const v = String(t || "").toLowerCase();
  if (v.includes("doc") || v.includes("research") || v.includes("vault")) return "docs";
  if (v.includes("mem")) return "memory";
  if (v.includes("ledger") || v.includes("decision") || v.includes("audit")) return "ledger";
  if (!v) return "other";
  return "code";
}
function clusterKind(typeMix) {
  let best = "other", bestV = -1;
  for (const [t, frac] of Object.entries(typeMix || {})) {
    if (frac > bestV) { bestV = frac; best = kindForType(t); }
  }
  return best;
}
function hashStr(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
function taskClassColor(tc) {
  const c = new THREE.Color();
  c.setHSL((hashStr(String(tc || "task")) % 360) / 360, 0.72, 0.62);
  return c;
}
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/* ════════════════════════════════════════════════════════════════════════
 * 2. Renderer / scene / custom orbit rig
 * ════════════════════════════════════════════════════════════════════════ */

const stageEl = $("#stage");
let renderer = null;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
} catch (e) {
  $("#ctxlost").hidden = false;
}
const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x050507, 0.00085);
const camera = new THREE.PerspectiveCamera(55, 1, 0.5, 5000);

if (renderer) {
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); // DPR cap 2
  renderer.setClearColor(0x050507, 1);
  stageEl.appendChild(renderer.domElement);
  renderer.domElement.addEventListener("webglcontextlost", (e) => {
    e.preventDefault();
    $("#ctxlost").hidden = false; // recovery = reload (state refetches cleanly)
  });
}
$("#ctxreload").addEventListener("click", () => window.location.reload());

scene.add(new THREE.HemisphereLight(0x8899bb, 0x0a0c14, 1.1));
const dir = new THREE.DirectionalLight(0xffffff, 0.9);
dir.position.set(180, 260, 220);
scene.add(dir);

// Ambient starfield — pure dressing, visually distinct from data points.
(function starfield() {
  const N = 1400, pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const r = 900 + Math.random() * 1600;
    const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
    pos[i * 3] = r * Math.sin(ph) * Math.cos(th);
    pos[i * 3 + 1] = r * Math.cos(ph);
    pos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({
    color: 0x39415a, size: 1.6, sizeAttenuation: true,
    transparent: true, opacity: 0.55, depthWrite: false,
  })));
})();

// Minimal orbit/zoom/pan rig (three's OrbitControls lives in examples/, not
// the module build — this is a self-contained, damped equivalent).
class OrbitRig {
  constructor(dom) {
    this.target = new THREE.Vector3(0, 0, 0);
    this.goalTarget = this.target.clone();
    this.sph = new THREE.Spherical(320, 1.18, 0.35);   // current
    this.goal = new THREE.Spherical(320, 1.18, 0.35);  // damped toward
    this.tween = null;
    this.lastInput = -1e9;
    this._pointers = new Map();
    this._pinchDist = 0;
    dom.style.touchAction = "none";
    dom.addEventListener("contextmenu", (e) => e.preventDefault());
    dom.addEventListener("pointerdown", (e) => {
      dom.setPointerCapture(e.pointerId);
      this._pointers.set(e.pointerId, { x: e.clientX, y: e.clientY, button: e.button, shift: e.shiftKey });
      if (this._pointers.size === 2) {
        const [a, b] = [...this._pointers.values()];
        this._pinchDist = Math.hypot(a.x - b.x, a.y - b.y);
      }
      this.lastInput = performance.now();
    });
    dom.addEventListener("pointermove", (e) => {
      const p = this._pointers.get(e.pointerId);
      if (!p) return;
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      p.x = e.clientX; p.y = e.clientY;
      this.lastInput = performance.now();
      this.tween = null; // user input cancels any camera flight
      if (this._pointers.size === 2) {
        const [a, b] = [...this._pointers.values()];
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (this._pinchDist > 0) this.dolly(this._pinchDist / Math.max(d, 1));
        this._pinchDist = d;
        return;
      }
      if (p.button === 2 || p.shift) this.pan(dx, dy);
      else {
        this.goal.theta -= dx * 0.0052;
        this.goal.phi = Math.min(Math.PI - 0.06, Math.max(0.06, this.goal.phi - dy * 0.0052));
      }
    });
    const up = (e) => { this._pointers.delete(e.pointerId); this._pinchDist = 0; };
    dom.addEventListener("pointerup", up);
    dom.addEventListener("pointercancel", up);
    dom.addEventListener("wheel", (e) => {
      e.preventDefault();
      this.tween = null;
      this.lastInput = performance.now();
      this.dolly(Math.exp(e.deltaY * 0.001));
    }, { passive: false });
  }
  dolly(f) { this.goal.radius = Math.min(2200, Math.max(40, this.goal.radius * f)); }
  pan(dx, dy) {
    const scale = this.sph.radius * 0.0011;
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0);
    const upv = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
    this.goalTarget.addScaledVector(right, -dx * scale).addScaledVector(upv, dy * scale);
  }
  flyTo(target, radius, phi, theta, dur) {
    this.tween = {
      t: 0, dur: dur || 0.9,
      fromT: this.target.clone(), toT: target.clone(),
      from: new THREE.Spherical(this.sph.radius, this.sph.phi, this.sph.theta),
      to: new THREE.Spherical(radius, phi, theta),
    };
    this.goalTarget.copy(target);
    this.goal.set(radius, phi, theta);
  }
  update(dt) {
    if (this.tween) {
      const tw = this.tween;
      tw.t = Math.min(1, tw.t + dt / tw.dur);
      const k = easeInOutCubic(tw.t);
      this.target.lerpVectors(tw.fromT, tw.toT, k);
      this.sph.radius = tw.from.radius + (tw.to.radius - tw.from.radius) * k;
      this.sph.phi = tw.from.phi + (tw.to.phi - tw.from.phi) * k;
      this.sph.theta = tw.from.theta + (tw.to.theta - tw.from.theta) * k;
      if (tw.t >= 1) this.tween = null;
    } else {
      const k = 1 - Math.exp(-dt * 9); // critically-damped-ish smoothing
      this.target.lerp(this.goalTarget, k);
      this.sph.radius += (this.goal.radius - this.sph.radius) * k;
      this.sph.phi += (this.goal.phi - this.sph.phi) * k;
      this.sph.theta += (this.goal.theta - this.sph.theta) * k;
    }
    camera.position.setFromSpherical(this.sph).add(this.target);
    camera.lookAt(this.target);
  }
  idle() { return performance.now() - this.lastInput > 4000; }
}
const rig = renderer ? new OrbitRig(renderer.domElement) : null;

const VIEWS = {
  galaxy:    { target: new THREE.Vector3(0, 0, 0),       radius: 320, phi: 1.18, theta: 0.35 },
  pipelines: { target: new THREE.Vector3(0, -170, 0),    radius: 250, phi: 1.05, theta: 0.0 },
  ladder:    { target: new THREE.Vector3(0, 216, -140),  radius: 230, phi: 1.45, theta: 0.0 },
  all:       { target: new THREE.Vector3(0, 10, -20),    radius: 560, phi: 1.15, theta: 0.3 },
};
function setView(name) {
  state.view = name;
  document.querySelectorAll(".view").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name));
  const v = VIEWS[name] || VIEWS.galaxy;
  if (rig) rig.flyTo(v.target, v.radius, v.phi, v.theta);
}
document.querySelectorAll(".view").forEach((b) =>
  b.addEventListener("click", () => setView(b.dataset.view)));

function resize() {
  if (!renderer) return;
  const w = window.innerWidth, hgt = window.innerHeight;
  camera.aspect = w / hgt;
  camera.updateProjectionMatrix();
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(w, hgt);
}
window.addEventListener("resize", resize);
resize();

// Soft radial sprite texture used by halos / packets / flares (generated —
// no asset fetches).
const glowTex = (() => {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.35, "rgba(255,255,255,.55)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c);
  t.needsUpdate = true;
  return t;
})();

function makeLabel(text, colorCss) {
  const c = document.createElement("canvas");
  const g = c.getContext("2d");
  g.font = "600 26px system-ui, sans-serif";
  const w = Math.ceil(g.measureText(text).width) + 18;
  c.width = w; c.height = 40;
  const g2 = c.getContext("2d");
  g2.font = "600 26px system-ui, sans-serif";
  g2.fillStyle = colorCss || "#aab2c4";
  g2.textBaseline = "middle";
  g2.fillText(text, 9, 21);
  const tex = new THREE.CanvasTexture(c);
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({
    map: tex, transparent: true, depthWrite: false, opacity: 0.9,
  }));
  spr.scale.set(w * 0.16, 6.4, 1);
  return spr;
}

/* ════════════════════════════════════════════════════════════════════════
 * 3. Galaxy — InstancedMesh clusters + halos + edges + on-demand expansion
 * ════════════════════════════════════════════════════════════════════════ */

const galaxyGroup = new THREE.Group();
scene.add(galaxyGroup);

const galaxy = {
  clusters: [],            // snapshot cluster dicts (renderable, pos != null)
  byId: new Map(),
  mesh: null,              // InstancedMesh of cluster spheres
  halo: null,              // Points layer (heat glow)
  edges: null,
  expanded: new Map(),     // cid -> {group, nodes, byId, mesh, openedAt, anim}
  pulses: new Map(),       // cid -> pulse object (client-side coalescing)
  pulsePool: [],
  graphVersion: null,
};

const haloMaterial = new THREE.ShaderMaterial({
  uniforms: { map: { value: glowTex } },
  vertexShader: `
    attribute float size;
    attribute float alpha;
    attribute vec3 hcolor;
    varying float vAlpha;
    varying vec3 vColor;
    void main() {
      vAlpha = alpha; vColor = hcolor;
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      gl_PointSize = size * (320.0 / -mv.z);
      gl_Position = projectionMatrix * mv;
    }`,
  fragmentShader: `
    uniform sampler2D map;
    varying float vAlpha;
    varying vec3 vColor;
    void main() {
      vec4 t = texture2D(map, gl_PointCoord);
      gl_FragColor = vec4(vColor, 1.0) * t * vAlpha;
    }`,
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
});

function disposeObject(obj) {
  obj.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) {
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      mats.forEach((m) => { if (m.map && m.map !== glowTex) m.map.dispose(); m.dispose(); });
    }
  });
}

function clearGalaxy() {
  for (const cid of [...galaxy.expanded.keys()]) collapseCluster(cid, true);
  [galaxy.mesh, galaxy.halo, galaxy.edges].forEach((o) => {
    if (o) { galaxyGroup.remove(o); disposeObject(o); }
  });
  galaxy.mesh = galaxy.halo = galaxy.edges = null;
  galaxy.clusters = [];
  galaxy.byId.clear();
}

/* ════════════════════════════════════════════════════════════════════════
 * Sacred-geometry layouts (client-side). Reposition the gateway clusters onto
 * closed-form lattices — Vogel phyllotaxis, the spherical Fibonacci lattice,
 * Platonic (icosahedron) anchors, and a projected 4-polytope (24-cell). Opt-in
 * via the HUD "layout" select; "gateway" (default) leaves the gateway-computed
 * positions untouched. The math mirrors the UE renderer's MuseSacredGeometry
 * and the Python reference (same golden angle 137.50776° + exact vertex sets).
 * ════════════════════════════════════════════════════════════════════════ */
const SG_PHI = (1 + Math.sqrt(5)) / 2;
const SG_GOLDEN = Math.PI * (3 - Math.sqrt(5)); // golden angle (radians)

function sgVogel(n) {
  const o = [];
  for (let i = 0; i < n; i++) {
    const r = Math.sqrt(i), t = i * SG_GOLDEN;
    o.push([r * Math.cos(t), r * Math.sin(t)]);
  }
  return o;
}
function sgFibSphere(n) {
  const o = [];
  for (let i = 0; i < n; i++) {
    const y = 1 - 2 * (i + 0.5) / n;
    const ring = Math.sqrt(Math.max(0, 1 - y * y)), t = SG_GOLDEN * i;
    o.push([ring * Math.cos(t), y, ring * Math.sin(t)]);
  }
  return o;
}
function sgIcosa() {
  const p = SG_PHI, o = [];
  for (const a of [-1, 1]) for (const b of [-p, p]) {
    o.push([0, a, b]); o.push([a, b, 0]); o.push([b, 0, a]);
  }
  return o.map((v) => {
    const l = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / l, v[1] / l, v[2] / l];
  });
}
function sgCell24() {
  const o = [];
  for (let ax = 0; ax < 4; ax++) for (const s of [-1, 1]) {
    const v = [0, 0, 0, 0]; v[ax] = s; o.push(v);
  }
  for (const a of [-0.5, 0.5]) for (const b of [-0.5, 0.5])
    for (const c of [-0.5, 0.5]) for (const d of [-0.5, 0.5]) o.push([a, b, c, d]);
  return o; // 8 + 16 = 24 vertices
}
function sgProject(p, d) {
  const den = d - p[3], k = Math.abs(den) > 1e-9 ? d / den : 1e9;
  return [p[0] * k, p[1] * k, p[2] * k];
}

function sgTargets(mode, n, R) {
  const out = [];
  if (mode === "phyllotaxis") {
    const pts = sgVogel(n), maxr = Math.sqrt(Math.max(1, n - 1));
    for (let i = 0; i < n; i++) out.push([pts[i][0] / maxr * R, pts[i][1] / maxr * R, 0]);
  } else if (mode === "fibonacci") {
    for (const v of sgFibSphere(n)) out.push([v[0] * R, v[1] * R, v[2] * R]);
  } else if (mode === "platonic") {
    const verts = sgIcosa(), m = verts.length;
    for (let i = 0; i < n; i++) {
      const v = verts[i % m], shell = 1 + Math.floor(i / m) * 0.2;
      out.push([v[0] * R * shell, v[1] * R * shell, v[2] * R * shell]);
    }
  } else if (mode === "polytope") {
    const verts = sgCell24(), m = verts.length, c = Math.cos(0.62), s = Math.sin(0.62);
    for (let i = 0; i < n; i++) {
      const raw = verts[i % m];
      const l = Math.hypot(raw[0], raw[1], raw[2], raw[3]) || 1;
      const v = [raw[0] / l, raw[1] / l, raw[2] / l, raw[3] / l];
      const rot = [v[0], v[1], v[2] * c - v[3] * s, v[2] * s + v[3] * c]; // ZW rotation
      const p = sgProject(rot, 2.5);
      out.push([p[0] * R, p[1] * R, p[2] * R]);
    }
  }
  return out;
}

// Mutate each cluster's `.pos` for the active layout, remembering the gateway
// position once (`_gpos`) so modes can be switched losslessly.
function applyLayout(clusters) {
  const mode = state.layout || "gateway";
  for (const c of clusters) {
    if (!c._gpos && Array.isArray(c.pos) && c.pos.length === 3) c._gpos = c.pos.slice(0, 3);
  }
  if (mode === "gateway") {
    for (const c of clusters) if (c._gpos) c.pos = c._gpos.slice();
    return;
  }
  const n = clusters.length;
  let R = 0;
  for (const c of clusters) {
    if (c._gpos) R = Math.max(R, Math.hypot(c._gpos[0], c._gpos[1], c._gpos[2]));
  }
  if (!(R > 1)) R = 90;
  const targets = sgTargets(mode, n, R);
  for (let i = 0; i < n; i++) {
    const t = targets[i] || clusters[i]._gpos || [0, 0, 0];
    clusters[i].pos = [t[0], t[1], t[2]];
  }
}

function buildGalaxy(graph) {
  clearGalaxy();
  galaxy.graphVersion = graph.graph_version || null;
  const clusters = (graph.clusters || []).filter(
    (c) => Array.isArray(c.pos) && c.pos.length === 3);
  galaxy.clusters = clusters;
  clusters.forEach((c, i) => { c._index = i; galaxy.byId.set(c.id, c); });
  if (!clusters.length) return;
  applyLayout(clusters);

  // Cluster spheres — one InstancedMesh, color by dominant kind; heat==null
  // renders desaturated gray (no guessed glow, spec §5).
  const geo = new THREE.SphereGeometry(1, 18, 14);
  const mat = new THREE.MeshLambertMaterial({});
  const mesh = new THREE.InstancedMesh(geo, mat, clusters.length);
  const m4 = new THREE.Matrix4();
  const col = new THREE.Color();
  clusters.forEach((c, i) => {
    const r = Math.max(0.6, Number(c.radius) || 1);
    m4.makeScale(r, r, r).setPosition(c.pos[0], c.pos[1], c.pos[2]);
    mesh.setMatrixAt(i, m4);
    col.copy(KIND_COLORS[clusterKind(c.type_mix)] || KIND_COLORS.other);
    if (c.heat == null) col.lerp(GRAY, 0.72);
    mesh.setColorAt(i, col);
  });
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  mesh.userData.kind = "cluster";
  galaxyGroup.add(mesh);
  galaxy.mesh = mesh;

  // Heat halos — additive point sprites; size/alpha from measured heat only.
  const n = clusters.length;
  const pos = new Float32Array(n * 3), size = new Float32Array(n),
        alpha = new Float32Array(n), hcol = new Float32Array(n * 3);
  clusters.forEach((c, i) => {
    pos.set(c.pos, i * 3);
    const r = Math.max(0.6, Number(c.radius) || 1);
    const heat = c.heat;
    let cc, a, s;
    if (heat == null) { cc = GRAY; a = 0.06; s = r * 2.2; }
    else if (heat > HEAT_GLOW_THRESHOLD) {
      cc = HOT.clone().lerp(new THREE.Color(0xffd27a), 1 - heat);
      a = 0.3 + 0.5 * heat; s = r * (3.2 + heat * 4.5);
    } else {
      cc = KIND_COLORS[clusterKind(c.type_mix)] || KIND_COLORS.other;
      a = 0.1 + 0.2 * heat; s = r * (2.4 + heat * 2);
    }
    size[i] = s; alpha[i] = a;
    hcol[i * 3] = cc.r; hcol[i * 3 + 1] = cc.g; hcol[i * 3 + 2] = cc.b;
  });
  const hg = new THREE.BufferGeometry();
  hg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  hg.setAttribute("size", new THREE.BufferAttribute(size, 1));
  hg.setAttribute("alpha", new THREE.BufferAttribute(alpha, 1));
  hg.setAttribute("hcolor", new THREE.BufferAttribute(hcol, 3));
  const halo = new THREE.Points(hg, haloMaterial);
  halo.raycast = () => {}; // visual only — never intercepts picking
  galaxyGroup.add(halo);
  galaxy.halo = halo;

  // Cluster edges — additive low-opacity LineSegments, endpoint-tinted.
  const segs = [];
  const segCols = [];
  for (const e of graph.cluster_edges || []) {
    const a = galaxy.byId.get(e.a), b = galaxy.byId.get(e.b);
    if (!a || !b) continue;
    segs.push(...a.pos, ...b.pos);
    const ca = KIND_COLORS[clusterKind(a.type_mix)] || KIND_COLORS.other;
    const cb = KIND_COLORS[clusterKind(b.type_mix)] || KIND_COLORS.other;
    segCols.push(ca.r, ca.g, ca.b, cb.r, cb.g, cb.b);
  }
  if (segs.length) {
    const eg = new THREE.BufferGeometry();
    eg.setAttribute("position", new THREE.BufferAttribute(new Float32Array(segs), 3));
    eg.setAttribute("color", new THREE.BufferAttribute(new Float32Array(segCols), 3));
    const edges = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({
      vertexColors: true, transparent: true, opacity: 0.16,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    edges.raycast = () => {};
    galaxyGroup.add(edges);
    galaxy.edges = edges;
  }
}

// Refresh measured heat in place (same graph_version — positions are stable,
// only the activation share moved). Mirrors buildGalaxy's color/halo rules.
function updateGalaxyHeat(clusters) {
  if (!galaxy.mesh || !galaxy.halo) return;
  const byId = new Map((clusters || []).map((c) => [c.id, c]));
  const size = galaxy.halo.geometry.getAttribute("size");
  const alpha = galaxy.halo.geometry.getAttribute("alpha");
  const hcol = galaxy.halo.geometry.getAttribute("hcolor");
  const col = new THREE.Color();
  galaxy.clusters.forEach((c, i) => {
    const fresh = byId.get(c.id);
    if (fresh) c.heat = fresh.heat;
    const r = Math.max(0.6, Number(c.radius) || 1);
    const kindColor = KIND_COLORS[clusterKind(c.type_mix)] || KIND_COLORS.other;
    col.copy(kindColor);
    if (c.heat == null) col.lerp(GRAY, 0.72);
    galaxy.mesh.setColorAt(i, col);
    let cc, a, s;
    if (c.heat == null) { cc = GRAY; a = 0.06; s = r * 2.2; }
    else if (c.heat > HEAT_GLOW_THRESHOLD) {
      cc = HOT.clone().lerp(new THREE.Color(0xffd27a), 1 - c.heat);
      a = 0.3 + 0.5 * c.heat; s = r * (3.2 + c.heat * 4.5);
    } else {
      cc = kindColor; a = 0.1 + 0.2 * c.heat; s = r * (2.4 + c.heat * 2);
    }
    size.setX(i, s); alpha.setX(i, a); hcol.setXYZ(i, cc.r, cc.g, cc.b);
  });
  if (galaxy.mesh.instanceColor) galaxy.mesh.instanceColor.needsUpdate = true;
  size.needsUpdate = alpha.needsUpdate = hcol.needsUpdate = true;
}

// -- expansion (LOD): click a cluster → fetch its members, max 3 open --------

const MAX_EXPANDED = 3;

async function expandCluster(cid) {
  if (galaxy.expanded.has(cid)) { collapseCluster(cid); return; }
  const cluster = galaxy.byId.get(cid);
  if (!cluster) return;
  let body = null;
  try {
    const r = await api(`/v1/observatory/layout?cluster=${encodeURIComponent(cid)}`);
    if (r.status === 404) { await refreshAll(); return; } // stale graph version
    if (!r.ok) return;
    body = await r.json();
  } catch (e) { return; }
  if (!body || body.status === "unavailable" || !Array.isArray(body.nodes)) return;

  while (galaxy.expanded.size >= MAX_EXPANDED) {
    let oldest = null, oldestAt = Infinity;
    for (const [k, v] of galaxy.expanded) if (v.openedAt < oldestAt) { oldestAt = v.openedAt; oldest = k; }
    collapseCluster(oldest);
  }

  const nodes = body.nodes.filter((nd) => Array.isArray(nd.pos) && nd.pos.length === 3);
  const group = new THREE.Group();
  group.position.set(cluster.pos[0], cluster.pos[1], cluster.pos[2]);
  group.scale.setScalar(0.01);

  const geo = new THREE.SphereGeometry(1, 10, 8);
  const mesh = new THREE.InstancedMesh(geo, new THREE.MeshLambertMaterial({}), nodes.length || 1);
  const m4 = new THREE.Matrix4();
  const col = new THREE.Color();
  const byId = new Map();
  nodes.forEach((nd, i) => {
    byId.set(i, nd);
    const s = 0.35 + Math.min(1.1, (Number(nd.degree) || 0) * 0.05);
    m4.makeScale(s, s, s).setPosition(nd.pos[0], nd.pos[1], nd.pos[2]);
    mesh.setMatrixAt(i, m4);
    col.copy(KIND_COLORS[kindForType(nd.type)] || KIND_COLORS.other);
    if (nd.heat == null) col.lerp(GRAY, 0.45);
    mesh.setColorAt(i, col);
  });
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  mesh.userData.kind = "member";
  mesh.userData.cid = cid;
  group.add(mesh);

  const idToPos = new Map(nodes.map((nd) => [nd.id, nd.pos]));
  const segs = [];
  for (const e of body.edges || []) {
    const pa = idToPos.get(e.a), pb = idToPos.get(e.b);
    if (pa && pb) segs.push(...pa, ...pb);
  }
  if (segs.length) {
    const eg = new THREE.BufferGeometry();
    eg.setAttribute("position", new THREE.BufferAttribute(new Float32Array(segs), 3));
    const lines = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({
      color: 0x6b7388, transparent: true, opacity: 0.22,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    lines.raycast = () => {};
    group.add(lines);
  }

  galaxyGroup.add(group);
  galaxy.expanded.set(cid, {
    group, mesh, byId, openedAt: performance.now(),
    anim: { t: 0, dir: 1 }, truncated: !!body.truncated, count: nodes.length,
    layoutAlgo: body.layout_algo || null,
  });
  // Shrink the super-node so the starfield reads as "inside" it.
  setClusterScale(cluster, Math.max(0.6, (Number(cluster.radius) || 1)) * 0.35);
}

function setClusterScale(cluster, s) {
  if (!galaxy.mesh || cluster._index == null) return;
  const m4 = new THREE.Matrix4();
  m4.makeScale(s, s, s).setPosition(cluster.pos[0], cluster.pos[1], cluster.pos[2]);
  galaxy.mesh.setMatrixAt(cluster._index, m4);
  galaxy.mesh.instanceMatrix.needsUpdate = true;
}

function collapseCluster(cid, immediate) {
  const ex = galaxy.expanded.get(cid);
  if (!ex) return;
  const cluster = galaxy.byId.get(cid);
  if (cluster) setClusterScale(cluster, Math.max(0.6, Number(cluster.radius) || 1));
  if (immediate) {
    galaxyGroup.remove(ex.group);
    disposeObject(ex.group);
    galaxy.expanded.delete(cid);
  } else {
    ex.anim.dir = -1; // animated scale-out; removed in tick()
  }
}

// -- activation pulses (node.activate SSE → ring on the cluster) -------------

function getPulseMesh() {
  const free = galaxy.pulsePool.find((p) => !p.active);
  if (free) return free;
  if (galaxy.pulsePool.length >= 24) return null; // coalesce beyond the pool
  const mesh = new THREE.Mesh(
    new THREE.RingGeometry(1, 1.14, 48),
    new THREE.MeshBasicMaterial({
      color: 0x7ae0ff, transparent: true, opacity: 0.8, side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
  mesh.raycast = () => {};
  mesh.visible = false;
  galaxyGroup.add(mesh);
  const p = { mesh, active: false, t: 0, baseR: 1, cid: null };
  galaxy.pulsePool.push(p);
  return p;
}

function pulseCluster(cid, weight) {
  const cluster = galaxy.byId.get(cid);
  if (!cluster) return;
  let p = galaxy.pulses.get(cid);
  if (p && p.active) { p.t = 0; return; } // client-side coalescing
  p = getPulseMesh();
  if (!p) return;
  p.active = true; p.t = 0; p.cid = cid;
  p.baseR = Math.max(0.8, Number(cluster.radius) || 1);
  p.strength = Math.min(1, 0.5 + (Number(weight) || 1) * 0.1);
  p.mesh.position.set(cluster.pos[0], cluster.pos[1], cluster.pos[2]);
  p.mesh.visible = true;
  galaxy.pulses.set(cid, p);
}

/* ════════════════════════════════════════════════════════════════════════
 * 4. Pipelines — station lanes + live packets + gate flares
 * ════════════════════════════════════════════════════════════════════════ */

const PIPE_Y = -170;
const LANES = 5;
const LANE_DZ = 26;
const STATION_COLORS = {
  job: 0x9aa3b8, navigator: 0xb388ff, worker: 0x7ae0ff,
  gate: 0xf5c451, ledger: 0x5be3a0,
};
const PACKET_CAP = 50;

const pipeGroup = new THREE.Group();
pipeGroup.position.set(0, PIPE_Y, 0);
scene.add(pipeGroup);

const pipes = {
  stations: [],          // [{name, x, ring}]
  stationX: new Map(),
  packetMesh: null,      // InstancedMesh, cap PACKET_CAP
  packets: new Map(),    // job_id -> packet
  order: [],             // insertion order for the rolling cap
  flares: [],            // sprite pool for gate verdict bursts
};

function laneZ(taskClass, jobId) {
  return ((hashStr(String(taskClass || jobId || "")) % LANES) - (LANES - 1) / 2) * LANE_DZ;
}

function buildPipelines(stationNames) {
  while (pipeGroup.children.length) {
    const ch = pipeGroup.children.pop();
    disposeObject(ch);
  }
  pipes.stations = [];
  pipes.stationX.clear();
  const names = stationNames && stationNames.length
    ? stationNames : ["job", "navigator", "worker", "gate", "ledger"];
  const span = 320, step = span / (names.length - 1);
  names.forEach((name, i) => {
    const x = -span / 2 + i * step;
    pipes.stationX.set(name, x);
    const color = STATION_COLORS[name] || 0x9aa3b8;
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry((LANES * LANE_DZ) / 2 + 8, 0.55, 10, 60),
      new THREE.MeshBasicMaterial({
        color, transparent: true, opacity: 0.5,
        blending: THREE.AdditiveBlending, depthWrite: false,
      }));
    ring.rotation.y = Math.PI / 2; // ring plane ⟂ travel axis
    ring.position.x = x;
    ring.userData.kind = "station";
    ring.userData.station = name;
    pipeGroup.add(ring);
    const label = makeLabel(name.toUpperCase(), "#aab2c4");
    label.position.set(x, (LANES * LANE_DZ) / 2 + 18, 0);
    pipeGroup.add(label);
    pipes.stations.push({ name, x, ring });
  });
  // Lane rails.
  const segs = [];
  for (let l = 0; l < LANES; l++) {
    const z = (l - (LANES - 1) / 2) * LANE_DZ;
    segs.push(-span / 2, 0, z, span / 2, 0, z);
  }
  const lg = new THREE.BufferGeometry();
  lg.setAttribute("position", new THREE.BufferAttribute(new Float32Array(segs), 3));
  const rails = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({
    color: 0x39415a, transparent: true, opacity: 0.35, depthWrite: false,
  }));
  rails.raycast = () => {};
  pipeGroup.add(rails);

  // Packet instancing pool.
  const pm = new THREE.InstancedMesh(
    new THREE.SphereGeometry(2.4, 10, 8),
    new THREE.MeshBasicMaterial({ blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }),
    PACKET_CAP);
  pm.userData.kind = "packet";
  pm.count = 0;
  pipeGroup.add(pm);
  pipes.packetMesh = pm;
  pipes.packets.clear();
  pipes.order = [];
}

function stationXFor(stage) {
  const s = String(stage || "").toLowerCase();
  if (pipes.stationX.has(s)) return pipes.stationX.get(s);
  if (s === "queued" || s.includes("queue") || s.includes("pend") || s.includes("wait") || s === "draft")
    return (pipes.stationX.get("job") ?? -160) - 34;
  if (s.includes("approval")) return pipes.stationX.get("gate") ?? 80;
  if (s.includes("run")) return pipes.stationX.get("worker") ?? 0;
  if (s === "done" || s === "completed" || s === "published")
    return (pipes.stationX.get("ledger") ?? 160) + 40;
  if (s === "failed" || s === "cancelled") return pipes.stationX.get("gate") ?? 80;
  return pipes.stationX.get("job") ?? -160;
}

function upsertPacket(jobId, taskClass, stage, opts) {
  if (!pipes.packetMesh) return;
  let p = pipes.packets.get(jobId);
  const toX = stationXFor(stage);
  const terminal = ["done", "failed", "completed", "cancelled", "published"]
    .includes(String(stage || "").toLowerCase());
  if (!p) {
    if (pipes.order.length >= PACKET_CAP) {
      const evict = pipes.order.shift();
      pipes.packets.delete(evict);
    }
    p = {
      jobId, taskClass: taskClass || null,
      x: toX - 26, fromX: toX - 26, toX,
      z: laneZ(taskClass, jobId),
      t: 0, dur: 1.4,
      color: taskClassColor(taskClass || jobId),
      stage, fade: 1, terminal: false,
    };
    pipes.packets.set(jobId, p);
    pipes.order.push(jobId);
  } else {
    p.fromX = p.x; p.toX = toX; p.t = 0;
    p.dur = (opts && opts.bounce) ? 0.9 : 1.4;
    p.stage = stage;
    if (taskClass && !p.taskClass) { p.taskClass = taskClass; p.color = taskClassColor(taskClass); }
  }
  p.terminal = terminal;
  if (String(stage || "").toLowerCase() === "failed") p.color = new THREE.Color(0xff5c63);
  renderDockStations();
}

function gateFlare(jobId, verdict) {
  const p = pipes.packets.get(jobId);
  const gx = pipes.stationX.get("gate") ?? 80;
  const z = p ? p.z : 0;
  let f = pipes.flares.find((fl) => !fl.active);
  if (!f) {
    if (pipes.flares.length >= 12) return;
    const spr = new THREE.Sprite(new THREE.SpriteMaterial({
      map: glowTex, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending,
    }));
    spr.raycast = () => {};
    pipeGroup.add(spr);
    f = { spr, active: false, t: 0 };
    pipes.flares.push(f);
  }
  f.active = true; f.t = 0;
  f.fail = verdict === "fail";
  f.spr.material.color.set(f.fail ? 0xff5c63 : 0x5be3a0);
  f.spr.position.set(gx, 6, z);
  f.spr.visible = true;
  if (f.fail && p) {
    // Bounce the packet back to the worker station along the retry path.
    upsertPacket(jobId, p.taskClass, "worker", { bounce: true });
  }
}

/* ════════════════════════════════════════════════════════════════════════
 * 5. Brain Ladder — three strata, brightness ∝ measured share
 * ════════════════════════════════════════════════════════════════════════ */

const LADDER_POS = new THREE.Vector3(0, 190, -140);
const TIERS = ["local", "hosted", "paired"];
const TIER_COLORS = { local: 0x7ae0ff, hosted: 0xb388ff, paired: 0xf5c451 };
const TIER_DY = 26;
const LADDER_LEN = 260;

const ladderGroup = new THREE.Group();
ladderGroup.position.copy(LADDER_POS);
scene.add(ladderGroup);

const ladder = { bars: new Map(), streaks: [], rollup: new Map() };

(function buildLadder() {
  TIERS.forEach((tier, i) => {
    const bar = new THREE.Mesh(
      new THREE.BoxGeometry(LADDER_LEN, 2.2, 2.2),
      new THREE.MeshBasicMaterial({
        color: TIER_COLORS[tier], transparent: true, opacity: 0.18,
        blending: THREE.AdditiveBlending, depthWrite: false,
      }));
    bar.position.y = i * TIER_DY;
    bar.userData.kind = "tier";
    bar.userData.tier = tier;
    ladderGroup.add(bar);
    const label = makeLabel(tier.toUpperCase(), "#aab2c4");
    label.position.set(-LADDER_LEN / 2 - 30, i * TIER_DY, 0);
    ladderGroup.add(label);
    ladder.bars.set(tier, bar);
  });
})();

function setLadderBrightness(tiers) {
  ladder.rollup.clear();
  for (const t of tiers || []) ladder.rollup.set(t.tier, t);
  for (const tier of TIERS) {
    const bar = ladder.bars.get(tier);
    const info = ladder.rollup.get(tier);
    const share = info && info.share_1h != null ? Number(info.share_1h) : null;
    bar.material.opacity = share == null ? 0.12 : 0.18 + 0.72 * share;
    bar.scale.y = bar.scale.z = share == null ? 1 : 1 + share * 2.2;
  }
}

function routeStreak(tier) {
  if (!TIERS.includes(tier)) return;
  let s = ladder.streaks.find((x) => !x.active);
  if (!s) {
    if (ladder.streaks.length >= 16) return;
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(16, 1.6, 1.6),
      new THREE.MeshBasicMaterial({
        color: 0xffffff, transparent: true, opacity: 0.9,
        blending: THREE.AdditiveBlending, depthWrite: false,
      }));
    mesh.raycast = () => {};
    mesh.visible = false;
    ladderGroup.add(mesh);
    s = { mesh, active: false, t: 0, tier: null };
    ladder.streaks.push(s);
  }
  s.active = true; s.t = 0; s.tier = tier;
  s.mesh.material.color.set(TIER_COLORS[tier]);
  s.mesh.position.y = TIERS.indexOf(tier) * TIER_DY;
  s.mesh.visible = true;
}

/* ════════════════════════════════════════════════════════════════════════
 * 6. Per-frame animation
 * ════════════════════════════════════════════════════════════════════════ */

const tmpM4 = new THREE.Matrix4();

function tick(dt) {
  if (rig) {
    rig.update(dt);
    if (rig.idle() && state.view !== "pipelines" && state.view !== "ladder")
      galaxyGroup.rotation.y += dt * 0.02; // slow idle drift
  }

  // Expanded-cluster scale-in/out.
  for (const [cid, ex] of [...galaxy.expanded]) {
    ex.anim.t += dt * (ex.anim.dir > 0 ? 2.2 : 3.2) * ex.anim.dir;
    if (ex.anim.dir > 0 && ex.anim.t >= 1) { ex.anim.t = 1; }
    if (ex.anim.dir < 0 && ex.anim.t <= 0) {
      galaxyGroup.remove(ex.group);
      disposeObject(ex.group);
      galaxy.expanded.delete(cid);
      continue;
    }
    ex.group.scale.setScalar(Math.max(0.01, easeOutCubic(Math.max(0, Math.min(1, ex.anim.t)))));
  }

  // Activation pulses.
  for (const p of galaxy.pulsePool) {
    if (!p.active) continue;
    p.t += dt * 1.4;
    if (p.t >= 1) {
      p.active = false; p.mesh.visible = false;
      if (p.cid) galaxy.pulses.delete(p.cid);
      continue;
    }
    const k = easeOutCubic(p.t);
    p.mesh.scale.setScalar(p.baseR * (1.3 + k * 2.4));
    p.mesh.material.opacity = (1 - p.t) * 0.8 * (p.strength || 1);
    p.mesh.quaternion.copy(camera.quaternion); // billboard
  }

  // Packets — eased motion along the lane.
  if (pipes.packetMesh) {
    let i = 0;
    for (const jobId of pipes.order) {
      const p = pipes.packets.get(jobId);
      if (!p || i >= PACKET_CAP) continue;
      p.t = Math.min(1, p.t + dt / p.dur);
      p.x = p.fromX + (p.toX - p.fromX) * easeInOutCubic(p.t);
      if (p.terminal && p.t >= 1) p.fade = Math.max(0, p.fade - dt * 0.7);
      const s = 1 * p.fade;
      tmpM4.makeScale(s, s, s).setPosition(p.x, 4, p.z);
      pipes.packetMesh.setMatrixAt(i, tmpM4);
      pipes.packetMesh.setColorAt(i, p.color);
      p._instance = i;
      i++;
    }
    pipes.packetMesh.count = i;
    pipes.packetMesh.instanceMatrix.needsUpdate = true;
    if (pipes.packetMesh.instanceColor) pipes.packetMesh.instanceColor.needsUpdate = true;
    // Drop fully faded terminal packets.
    for (const jobId of [...pipes.order]) {
      const p = pipes.packets.get(jobId);
      if (p && p.terminal && p.fade <= 0) {
        pipes.packets.delete(jobId);
        pipes.order.splice(pipes.order.indexOf(jobId), 1);
      }
    }
  }

  // Gate flares.
  for (const f of pipes.flares) {
    if (!f.active) continue;
    f.t += dt * (f.fail ? 1.4 : 2.4);
    if (f.t >= 1) { f.active = false; f.spr.visible = false; continue; }
    const k = easeOutCubic(f.t);
    f.spr.scale.setScalar(8 + k * (f.fail ? 46 : 22));
    f.spr.material.opacity = 1 - f.t;
  }

  // Ladder streaks.
  for (const s of ladder.streaks) {
    if (!s.active) continue;
    s.t += dt / 0.7;
    if (s.t >= 1) { s.active = false; s.mesh.visible = false; continue; }
    s.mesh.position.x = -LADDER_LEN / 2 + LADDER_LEN * easeInOutCubic(s.t);
    s.mesh.material.opacity = 0.95 * (1 - s.t * 0.5);
  }
}

let rafId = null, lastT = 0;
function frame(t) {
  rafId = requestAnimationFrame(frame);
  const dt = Math.min(0.1, (t - lastT) / 1000 || 0.016);
  lastT = t;
  // Wallpaper mode drifts the camera slowly while the viewer is idle, so a
  // live wallpaper is never a frozen frame. User input (rig.idle() false)
  // pauses the drift immediately.
  if (WALLPAPER && rig && rig.idle()) rig.goal.theta += dt * 0.04;
  tick(dt);
  if (renderer) renderer.render(scene, camera);
}
function startLoop() {
  if (rafId == null && renderer) { lastT = performance.now(); rafId = requestAnimationFrame(frame); }
}
function stopLoop() {
  if (rafId != null) { cancelAnimationFrame(rafId); rafId = null; }
}
document.addEventListener("visibilitychange", () => {
  if (document.hidden) stopLoop(); else startLoop(); // pause rendering off-tab
});
startLoop();

/* ════════════════════════════════════════════════════════════════════════
 * 7. Picking — hover tooltips + click → drawer
 * ════════════════════════════════════════════════════════════════════════ */

const raycaster = new THREE.Raycaster();
const mouseNDC = new THREE.Vector2();
let hoverDirty = false, lastClient = { x: 0, y: 0 };

if (renderer) {
  renderer.domElement.addEventListener("pointermove", (e) => {
    lastClient = { x: e.clientX, y: e.clientY };
    mouseNDC.set((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
    hoverDirty = true;
  });
  renderer.domElement.addEventListener("click", (e) => {
    if (e.detail === 0) return;
    const hit = pick();
    if (hit) handleClick(hit);
  });
}

function pickables() {
  const out = [];
  if (galaxy.mesh) out.push(galaxy.mesh);
  for (const ex of galaxy.expanded.values()) if (ex.anim.dir > 0) out.push(ex.mesh);
  if (pipes.packetMesh && pipes.packetMesh.count > 0) out.push(pipes.packetMesh);
  for (const st of pipes.stations) out.push(st.ring);
  for (const bar of ladder.bars.values()) out.push(bar);
  return out;
}

function pick() {
  raycaster.setFromCamera(mouseNDC, camera);
  const hits = raycaster.intersectObjects(pickables(), false);
  if (!hits.length) return null;
  const h = hits[0];
  const kind = h.object.userData.kind;
  if (kind === "cluster") {
    const c = galaxy.clusters[h.instanceId];
    return c ? { kind, cluster: c } : null;
  }
  if (kind === "member") {
    const ex = galaxy.expanded.get(h.object.userData.cid);
    const nd = ex && ex.byId.get(h.instanceId);
    return nd ? { kind, node: nd, cid: h.object.userData.cid } : null;
  }
  if (kind === "packet") {
    const jobId = pipes.order.find((id) => {
      const p = pipes.packets.get(id);
      return p && p._instance === h.instanceId;
    });
    return jobId ? { kind, jobId, packet: pipes.packets.get(jobId) } : null;
  }
  if (kind === "station") return { kind, station: h.object.userData.station };
  if (kind === "tier") return { kind, tier: h.object.userData.tier };
  return null;
}

const tooltip = $("#tooltip");
function showTooltip(content) {
  tooltip.replaceChildren(content);
  tooltip.hidden = false;
  const pad = 14;
  let x = lastClient.x + pad, y = lastClient.y + pad;
  const r = tooltip.getBoundingClientRect();
  if (x + r.width > window.innerWidth - 8) x = lastClient.x - r.width - pad;
  if (y + r.height > window.innerHeight - 8) y = lastClient.y - r.height - pad;
  tooltip.style.left = x + "px";
  tooltip.style.top = y + "px";
}
function hideTooltip() { tooltip.hidden = true; }

function heatLine(heat) {
  if (heat == null) return el("span", "heat-null", "heat: no measured activations");
  return el("span", heat > HEAT_GLOW_THRESHOLD ? "heat-hot" : "",
    `heat: ${heat.toFixed(2)} `, el("span", "muted", "(measured, 1h)"));
}

setInterval(() => { // hover raycasts are throttled off the render loop
  if (!hoverDirty || document.hidden) return;
  hoverDirty = false;
  const hit = pick();
  if (!hit) { hideTooltip(); document.body.style.cursor = ""; return; }
  document.body.style.cursor = "pointer";
  if (hit.kind === "cluster") {
    const c = hit.cluster;
    const mix = Object.entries(c.type_mix || {})
      .sort((a, b) => b[1] - a[1])
      .map(([t, f]) => `${t} ${(f * 100).toFixed(0)}%`).join(" · ");
    showTooltip(frag(
      el("b", "", c.label),
      el("div", "muted", `${mix || "unknown mix"} · ${c.members} members`),
      el("div", "", heatLine(c.heat)),
      el("div", "muted", `click to ${galaxy.expanded.has(c.id) ? "collapse" : "expand"}`)));
  } else if (hit.kind === "member") {
    const nd = hit.node;
    showTooltip(frag(
      el("b", "", nd.label),
      el("div", "muted", `${nd.type} · degree ${nd.degree}`),
      el("div", "muted mono", nd.source_ref || "")));
  } else if (hit.kind === "packet") {
    const p = hit.packet;
    showTooltip(frag(
      el("b", "", `job ${hit.jobId}`),
      el("div", "muted", `${p.taskClass || "unknown class"} · stage: ${p.stage || "?"}`),
      el("div", "muted", "click for the job record")));
  } else if (hit.kind === "station") {
    showTooltip(frag(
      el("b", "", `station: ${hit.station}`),
      el("div", "muted", "click for measured stage metrics + heat evidence")));
  } else if (hit.kind === "tier") {
    const info = ladder.rollup.get(hit.tier);
    showTooltip(frag(
      el("b", "", `${hit.tier} tier`),
      el("div", "muted", info && info.share_1h != null
        ? `share ${(info.share_1h * 100).toFixed(0)}% · n=${info.n} · p50 ${fmtMs(info.p50_latency_ms)}`
        : "no measured routing decisions in window"),
      el("div", "muted", "click for rollup + owner-gated edits")));
  }
}, 50);

function handleClick(hit) {
  hideTooltip();
  if (hit.kind === "cluster") { expandCluster(hit.cluster.id); showClusterDrawer(hit.cluster); }
  else if (hit.kind === "member") showNodeDrawer(hit.node, hit.cid);
  else if (hit.kind === "packet") showJobDrawer(hit.jobId);
  else if (hit.kind === "station") showStationDrawer(hit.station);
  else if (hit.kind === "tier") showTierDrawer(hit.tier);
}

/* ════════════════════════════════════════════════════════════════════════
 * 8. Drawer (right) — evidence-first detail views
 * ════════════════════════════════════════════════════════════════════════ */

const drawer = $("#drawer"), drawerBody = $("#drawerbody"), drawerTitle = $("#drawertitle");
$("#drawerclose").addEventListener("click", () => drawer.classList.remove("open"));
function openDrawer(title, content) {
  drawerTitle.textContent = title;
  drawerBody.replaceChildren(content);
  drawer.classList.add("open");
}

function kv(rows) {
  const wrap = el("div", "kv");
  for (const [k, v] of rows) {
    if (v === undefined) continue;
    wrap.append(el("span", "k", k), el("span", "v", v == null ? "—" : v));
  }
  return wrap;
}

function evidenceButtons(container) {
  container.querySelectorAll("[data-evidence]").forEach((b) =>
    b.addEventListener("click", async () => {
      const ref = b.getAttribute("data-evidence");
      const out = b.closest(".drawersec").querySelector("pre.json");
      out.hidden = false;
      out.textContent = "fetching " + ref + " …";
      try {
        const r = await api(ref);
        const d = await r.json().catch(() => null);
        out.textContent = r.ok
          ? JSON.stringify(d, null, 2)
          : `error ${r.status}: ${d && d.error ? d.error : "request failed"}`;
      } catch (e) { out.textContent = "fetch failed: " + e; }
    }));
}

function showClusterDrawer(c) {
  const mixLines = Object.entries(c.type_mix || {}).sort((a, b) => b[1] - a[1])
    .map(([t, f]) => `${t}: ${(f * 100).toFixed(1)}%`);
  openDrawer("Cluster — " + (c.label || c.id), frag(
    el("div", "drawersec", kv([
      ["id", c.id], ["members", c.members],
      ["radius", (Number(c.radius) || 0).toFixed(2)],
      ["heat", c.heat == null
        ? el("span", "heat-null", "null — no measured activations")
        : c.heat.toFixed(4) + " (measured share, 1h)"],
      ["pos", (c.pos || []).map((v) => v.toFixed(1)).join(", ")],
    ])),
    el("div", "drawersec", el("h4", "", "Type mix"),
      el("div", "mono", mixLines.length
        ? mixLines.flatMap((line, i) => (i ? [el("br"), line] : [line]))
        : "—")),
    el("div", "drawersec", el("h4", "", "Graph"), kv([
      ["graph_version", galaxy.graphVersion || "—"],
      ["layout", (state.snapshot && state.snapshot.graph && state.snapshot.graph.layout_algo) || "—"],
    ])),
    el("p", "muted", `Click the cluster again to collapse its member starfield.
    Up to ${MAX_EXPANDED} clusters stay expanded; the oldest auto-collapses.`)));
}

function showNodeDrawer(nd, cid) {
  openDrawer("Node — " + (nd.label || nd.id), frag(
    el("div", "drawersec", kv([
      ["id", nd.id], ["type", nd.type],
      ["degree", nd.degree],
      ["heat", nd.heat == null ? el("span", "heat-null", "null — unmeasured") : nd.heat],
      ["cluster", cid],
      ["source", nd.source_ref || "—"],
    ])),
    el("p", "muted", "Every node is a real GraphRAG entry; ",
      el("code", "", "source"),
      " is its provenance reference inside the repo / vault.")));
}

async function showJobDrawer(jobId) {
  openDrawer("Job — " + jobId, el("div", "empty", "Loading the job record…"));
  let content;
  try {
    const r = await api("/v1/cockpit/jobs/" + encodeURIComponent(jobId));
    const d = await r.json().catch(() => null);
    if (r.ok && d) {
      const job = d.job || d;
      content = frag(
        el("div", "drawersec", kv([
          ["title", job.title || "—"], ["status", job.status || "—"],
          ["worker", job.worker_id || "—"], ["branch", job.branch || "—"],
          ["updated", job.updated_at || job.created_at || "—"],
        ])),
        el("div", "drawersec", el("h4", "", "Raw record"),
          el("pre", "json", JSON.stringify(job, null, 2))),
        el("p", "", el("a", { href: "index.html" }, "Open in the cockpit →")));
    } else {
      content = frag(
        el("p", "err", `Could not load the job record (${r.status}${d && d.error ? " — " + d.error : ""}).`),
        el("p", "", el("a", { href: "index.html" }, "Open the cockpit →")));
    }
  } catch (e) {
    content = el("p", "err", "Request failed: " + String(e));
  }
  drawerBody.replaceChildren(content);
}

function heatEntriesFor(prefix) {
  const heat = (state.metrics && state.metrics.heat) || [];
  return heat.filter((h) => String(h.key || "").startsWith(prefix));
}

function heatEntryNode(h) {
  const score = h.score == null
    ? el("span", "heat-null", `insufficient data (n=${h.n})`)
    : frag(
        el("span", h.score > HEAT_GLOW_THRESHOLD ? "heat-hot" : "", h.score.toFixed(3)),
        " ", el("span", "muted", `(n=${h.n})`));
  return el("div", "evidence", `${h.key} → `, score, " ",
    el("button", { "data-evidence": h.evidence_ref }, "evidence"));
}

function showStationDrawer(station) {
  const stages = ((state.metrics && state.metrics.stages) || [])
    .filter((s) => s.stage === station);
  const rows = stages.map((s) => kv([
    ["task class", s.task_class || "*"], ["count", s.count],
    ["p50", fmtMs(s.p50_ms)], ["p95", fmtMs(s.p95_ms)],
    ["queue wait p95", fmtMs(s.queue_wait_p95_ms)], ["retries", s.retries],
  ]));
  const heatRows = heatEntriesFor("stage:" + station).map(heatEntryNode);
  openDrawer("Station — " + station, frag(
    el("div", "drawersec",
      el("h4", "", `Measured stage metrics (${state.window})`),
      rows.length ? rows : el("div", "muted", "nothing recorded in this window")),
    el("div", "drawersec", el("h4", "", "Bottleneck heat"),
      heatRows.length ? heatRows
        : el("div", "muted", "no heat keys recorded for this station in the window"),
      el("pre", { class: "json", hidden: true })),
    el("p", "muted", `Heat is computed from real measurements only
    (latency / queue / retries / cost); keys with n < ${(state.metrics && state.metrics.min_n) || 5}
    report `, el("code", "", "null"), `, never a guessed glow. Every entry links to the
    exact ledger evidence behind it.`)));
  evidenceButtons(drawerBody);
}

function showTierDrawer(tier) {
  const info = ladder.rollup.get(tier);
  const models = ((state.metrics && state.metrics.models) || [])
    .filter((m) => m.tier === tier);
  const modelRows = models.map((m) => kv([
    ["model", m.model], ["calls", m.calls],
    ["p95 latency", fmtMs(m.p95_latency_ms)],
    ["tokens in/out", `${m.tokens_in} / ${m.tokens_out}`],
    ["est cost", "$" + (m.est_cost_usd ?? 0)],
  ]));
  openDrawer("Brain tier — " + tier, frag(
    el("div", "drawersec", el("h4", "", "Routing share (1h, measured)"),
      info ? kv([
        ["share", info.share_1h == null ? "—" : (info.share_1h * 100).toFixed(1) + "%"],
        ["decisions", info.n], ["top model", info.model || "—"],
        ["p50 latency", fmtMs(info.p50_latency_ms)], ["p95 latency", fmtMs(info.p95_latency_ms)],
      ]) : el("div", "muted", "no route.decision events recorded yet")),
    el("div", "drawersec", el("h4", "", `Models (${state.window})`),
      modelRows.length ? modelRows : el("div", "muted", "no measured calls in this window")),
    el("div", "drawersec", el("h4", "", "Owner-gated brain edits"),
      el("p", "muted", "These fire ", el("b", "", "existing"),
        ` cockpit routes — the diff
      card shows the exact POST before anything happens. Nothing is cached.`),
      el("button", { id: "pinroutebtn" }, "Pin a route"),
      el("button", { id: "autonomybtn" }, "Adjust autonomy"),
      el("div", { id: "editcard" }))));
  $("#pinroutebtn").addEventListener("click", () => renderPinRouteCard(tier, info));
  $("#autonomybtn").addEventListener("click", () => renderAutonomyCard());
}

// -- diff-cards over the existing POST routes --------------------------------

function knownTaskClasses() {
  const set = new Set();
  for (const s of (state.metrics && state.metrics.stages) || []) if (s.task_class) set.add(s.task_class);
  for (const c of (state.metrics && state.metrics.cost_per_task_class) || []) if (c.task_class) set.add(c.task_class);
  return [...set];
}

function renderPinRouteCard(tier, info) {
  const modelInput = el("input", {
    id: "pin-model", type: "text", placeholder: "model id (empty = clear override)",
  });
  modelInput.value = (info && info.model) || "";
  $("#editcard").replaceChildren(el("div", "diffcard",
    el("div", "target", "POST /v1/cockpit/model-routes/override"),
    el("p", "muted", `Pin a task class to a model (empty model clears the
      override). Per the existing contract this is a reversible,
      token-authenticated preference — `, el("b", "", "no owner phrase involved"),
      `; only
      the paid-routing flip is phrase-gated and this card never touches it.`),
    el("input", { id: "pin-tc", type: "text", placeholder: "task_class (e.g. code)", list: "tclist" }),
    el("datalist", { id: "tclist" },
      knownTaskClasses().map((tc) => el("option", { value: tc }))),
    modelInput,
    el("pre", { class: "json", id: "pin-preview" }),
    el("div", "row end", el("button", { class: "primary", id: "pin-send" }, "Send")),
    el("div", { id: "pin-result" })));
  const preview = () => {
    const body = { task_class: $("#pin-tc").value.trim(), model: $("#pin-model").value.trim() || null };
    $("#pin-preview").textContent = "body → " + JSON.stringify(body);
    return body;
  };
  ["#pin-tc", "#pin-model"].forEach((s) => $(s).addEventListener("input", preview));
  preview();
  $("#pin-send").addEventListener("click", async () => {
    const body = preview();
    const out = $("#pin-result");
    if (!body.task_class) { out.replaceChildren(el("span", "err", "task_class is required")); return; }
    try {
      const r = await api("/v1/cockpit/model-routes/override", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json().catch(() => ({}));
      if (r.status === 401 || r.status === 403) {
        out.replaceChildren(el("span", "err", r.status === 401
          ? "Unauthorized — pair this browser (Token button) first."
          : "Forbidden: " + (d.error || "owner authorization required")));
      } else if (!r.ok) {
        out.replaceChildren(el("span", "err", `Failed (${r.status}): ${d.error || ""}`));
      } else {
        out.replaceChildren(el("span", "ok", "Route pinned. The change is audited in the override store."));
      }
    } catch (e) { out.replaceChildren(el("span", "err", "Request failed: " + String(e))); }
  });
}

function renderAutonomyCard() {
  $("#editcard").replaceChildren(el("div", "diffcard",
    el("div", "target", "POST /v1/cockpit/autonomy"),
    el("p", "muted", `Raising autonomy is owner-gated server-side: the exact
      authorization phrase rides in this one request body and is discarded —
      never stored, never echoed back.`),
    el("select", { id: "aut-level" },
      el("option", { value: "read_only" }, "read_only"),
      el("option", { value: "assisted", selected: true }, "assisted"),
      el("option", { value: "autonomous" }, "autonomous"),
      el("option", { value: "owner_high_autonomy_coding" }, "owner_high_autonomy_coding"),
      el("option", { value: "yolo" }, "yolo")),
    el("input", { id: "aut-ws", type: "text", placeholder: "workspace_path (required for owner_high_autonomy_coding)" }),
    el("input", { id: "aut-phrase", type: "password", placeholder: "owner authorization phrase (raises only)", autocomplete: "off" }),
    el("pre", { class: "json", id: "aut-preview" }),
    el("div", "row end", el("button", { class: "primary", id: "aut-send" }, "Send")),
    el("div", { id: "aut-result" })));
  const preview = () => {
    const body = { level: $("#aut-level").value };
    const ws = $("#aut-ws").value.trim();
    if (ws) body.workspace_path = ws;
    const shown = Object.assign({}, body);
    if ($("#aut-phrase").value) shown.authorization = "(entered phrase — sent verbatim, not shown)";
    $("#aut-preview").textContent = "body → " + JSON.stringify(shown);
    return body;
  };
  ["#aut-level", "#aut-ws", "#aut-phrase"].forEach((s) => $(s).addEventListener("input", preview));
  preview();
  $("#aut-send").addEventListener("click", async () => {
    const body = preview();
    const phrase = $("#aut-phrase").value;
    if (phrase) body.authorization = phrase; // pass-through, this request only
    const out = $("#aut-result");
    try {
      const r = await api("/v1/cockpit/autonomy", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json().catch(() => ({}));
      if (r.status === 401) {
        out.replaceChildren(el("span", "err", "Unauthorized — pair this browser (Token button) first."));
      } else if (r.status === 403) {
        out.replaceChildren(el("span", "err",
          `${d.error || "owner authorization required"} — the exact phrase is required for raises.`));
      } else if (!r.ok) {
        out.replaceChildren(el("span", "err", `Failed (${r.status}): ${d.error || ""}`));
      } else {
        out.replaceChildren(el("span", "ok", "Autonomy is now ",
          el("b", "", d.level || body.level), ". Change audited."));
      }
    } catch (e) { out.replaceChildren(el("span", "err", "Request failed: " + String(e))); }
    $("#aut-phrase").value = ""; // never retained
    preview();
  });
}

/* ════════════════════════════════════════════════════════════════════════
 * 9. Recommendation cards (left panel) — honest by construction
 * ════════════════════════════════════════════════════════════════════════ */

$("#recstoggle").addEventListener("click", () => {
  $("#recs").classList.remove("open");
  $("#recsopen").hidden = false;
});
$("#recsopen").addEventListener("click", () => {
  $("#recs").classList.add("open");
  $("#recsopen").hidden = true;
});

function recCardNode(card) {
  const v = card.validation || {};
  const methodSpan = () => el("span", "method", `(${v.method || "unvalidated"})`);
  if (card.state === "insufficient_evidence") {
    // Hard rule (spec §6): no projected numbers below threshold — the note
    // carries the explicit "insufficient evidence (n=X) — collecting" text.
    return el("div", { class: "reccard insufficient", "data-rec": card.id },
      el("h4", "", card.title),
      el("div", "note", card.note || "collecting evidence…"));
  }
  if (card.state === "validated") {
    const ci = Array.isArray(v.ci95) ? `${v.ci95[0]}% … ${v.ci95[1]}%` : "—";
    return el("div", { class: "reccard validated", "data-rec": card.id },
      el("div", "row", el("h4", { style: "margin:0" }, card.title),
        el("span", "grow"), el("span", "badge validated", "validated")),
      el("div", "stat", el("span", "k", `median Δ ${v.metric || ""}:`),
        ` ${v.median_delta_pct == null ? "—" : v.median_delta_pct + "%"} `, methodSpan()),
      el("div", "stat", el("span", "k", "95% CI:"), ` ${ci} `, methodSpan()),
      el("div", "stat", el("span", "k", "n:"),
        ` ${v.n_baseline} baseline / ${v.n_candidate} candidate `, methodSpan()),
      card.note ? el("div", "note", card.note) : null,
      el("div", "recactions",
        el("button", { class: "primary", "data-stage": card.id }, "Stage for approval"),
        el("span", "recmsg muted")));
  }
  // staged
  return el("div", { class: "reccard staged", "data-rec": card.id },
    el("div", "row", el("h4", { style: "margin:0" }, card.title),
      el("span", "grow"), el("span", "badge staged", "staged")),
    card.note ? el("div", "note", card.note) : null,
    el("div", "recactions",
      el("a", { href: "index.html#approvals" }, "Review in cockpit Approvals →")),
    el("div", "note", `Apply stays owner-gated behind the existing approvals
    queue — this page never asks for the phrase.`));
}

async function loadRecs() {
  const listEl = $("#recslist");
  if (!token) {
    listEl.replaceChildren(el("div", "empty", "Pair this browser (Token) to load recommendations."));
    return;
  }
  try {
    const r = await api(`/v1/observatory/recommendations?window=${encodeURIComponent(state.window)}`);
    if (!r.ok) {
      listEl.replaceChildren(el("div", "empty", r.status === 401
        ? "Unauthorized — set the cockpit token." : "error " + r.status));
      return;
    }
    const d = await r.json();
    if (d.status === "dormant") {
      listEl.replaceChildren(el("div", "empty", `Telemetry dormant — no measurements,
        so no recommendations. Honest empty > fake cards.`));
      return;
    }
    const cards = d.cards || [];
    listEl.replaceChildren(cards.length
      ? frag(cards.map(recCardNode))
      : el("div", "empty", "No recommendations yet — the engine only speaks when it has measured evidence."));
    listEl.querySelectorAll("[data-stage]").forEach((b) =>
      b.addEventListener("click", () => stageRec(b.getAttribute("data-stage"), b)));
  } catch (e) {
    listEl.replaceChildren(el("div", "empty", "offline"));
  }
}

async function stageRec(id, btn) {
  const msg = btn.parentElement.querySelector(".recmsg");
  btn.disabled = true;
  try {
    const r = await api(
      `/v1/observatory/recommendations/${encodeURIComponent(id)}/stage?window=${encodeURIComponent(state.window)}`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const d = await r.json().catch(() => ({}));
    if (r.status === 409) {
      msg.textContent = "already staged";
      loadRecs();
    } else if (r.status === 404) {
      msg.textContent = "card expired — refreshing";
      loadRecs();
    } else if (!r.ok) {
      btn.disabled = false;
      msg.replaceChildren(el("span", "err", `failed (${r.status}): ${d.error || ""}`));
    } else {
      msg.textContent = "staged → approvals queue";
      loadRecs();
    }
  } catch (e) {
    btn.disabled = false;
    msg.replaceChildren(el("span", "err", "request failed"));
  }
}

/* ════════════════════════════════════════════════════════════════════════
 * 10. Bottom dock — station counts + recent gate verdicts + honesty footer
 * ════════════════════════════════════════════════════════════════════════ */

const recentVerdicts = [];

function renderDockStations() {
  const wrap = $("#stations");
  const names = (state.snapshot && state.snapshot.stations && state.snapshot.stations.nodes)
    || ["job", "navigator", "worker", "gate", "ledger"];
  const counts = {};
  for (const p of pipes.packets.values()) {
    const s = String(p.stage || "").toLowerCase();
    const key = names.includes(s) ? s
      : (s.includes("queue") || s.includes("pend") || s.includes("wait")) ? "job"
      : s.includes("run") ? "worker"
      : s.includes("approval") ? "gate" : null;
    if (key) counts[key] = (counts[key] || 0) + 1;
  }
  const queueDepth = (state.snapshot && state.snapshot.stations && state.snapshot.stations.queue_depth) || 0;
  const hotStations = new Set(
    heatEntriesFor("stage:").filter((h) => h.score != null && h.score > HEAT_GLOW_THRESHOLD)
      .map((h) => String(h.key).split(":")[1]));
  wrap.replaceChildren(...names.map((n, i) => el("span", "station",
    el("span", {
      class: "slot " + (hotStations.has(n) ? "hot" : (counts[n] ? "busy" : "")),
      title: n,
    }, n, el("b", "", `${counts[n] || 0}${n === "job" && queueDepth ? " +" + queueDepth + "q" : ""}`)),
    i < names.length - 1 ? el("span", "link") : null)));
}

function pushVerdict(d) {
  recentVerdicts.unshift(d);
  if (recentVerdicts.length > 4) recentVerdicts.pop();
  $("#dockevents").replaceChildren(...recentVerdicts.map((v) =>
    el("span", v.verdict === "fail" ? "fail" : "pass",
      `${v.gate}:${v.verdict} · ${v.job_id}`)));
}

function renderLayoutNote() {
  const g = state.snapshot && state.snapshot.graph;
  const parts = [];
  if (g && !g.status) {
    parts.push(`layout: ${g.layout_algo || "?"} · ${g.layout_status || "?"}`);
    parts.push(`clusters ${g.clusters ? g.clusters.length : 0}/${g.clusters_total ?? "?"}`);
    parts.push(`graph ${g.graph_version || "?"} (${g.node_count} nodes / ${g.edge_count} edges)`);
  } else if (g && g.status === "unavailable") {
    parts.push("graph cache not built — POST /v1/cockpit/graph/build");
  }
  parts.push(`window ${state.window}`);
  parts.push(frag(
    el("span", { style: "color:#7ae0ff" }, "●"), " code ",
    el("span", { style: "color:#b388ff" }, "●"), " docs ",
    el("span", { style: "color:#f5c451" }, "●"), " memory ",
    el("span", { style: "color:#5be3a0" }, "●"), " ledger"));
  $("#layoutnote").replaceChildren(
    ...parts.flatMap((p, i) => (i ? ["  ·  ", p] : [p])));
}

/* ════════════════════════════════════════════════════════════════════════
 * 11. Data loading + dormant dressing
 * ════════════════════════════════════════════════════════════════════════ */

function setTelemetryPill() {
  const el = $("#telemetry");
  el.textContent = "telemetry: " + (state.telemetryLive ? "live" : "dormant");
  el.style.color = state.telemetryLive ? "var(--ok)" : "var(--warn)";
}

function setConn(mode, text) {
  $("#conndot").className = "dot " + (mode || "");
  $("#conntext").textContent = text;
}

function updateDormantDressing() {
  const heroEl = $("#hero"), bannerEl = $("#dormantbanner");
  if (!state.graphAvailable && !state.telemetryLive) {
    heroEl.hidden = false; bannerEl.hidden = true;
  } else if (!state.telemetryLive) {
    heroEl.hidden = true;
    if (!bannerEl.dataset.dismissed) bannerEl.hidden = false;
  } else {
    heroEl.hidden = true; bannerEl.hidden = true;
  }
}
$("#dormantdismiss").addEventListener("click", () => {
  $("#dormantbanner").hidden = true;
  $("#dormantbanner").dataset.dismissed = "1";
});
$("#heroretry").addEventListener("click", () => refreshAll());

async function loadSnapshot() {
  try {
    const r = await api("/v1/observatory/snapshot");
    if (r.status === 401) { setConn("off", "unauthorized — set token"); return; }
    if (r.status === 503) {
      state.telemetryLive = false; state.graphAvailable = false;
      setTelemetryPill(); updateDormantDressing();
      return;
    }
    if (!r.ok) return;
    const snap = await r.json();
    state.snapshot = snap;
    const graph = snap.graph || {};
    state.graphAvailable = !graph.status && Array.isArray(graph.clusters) && graph.clusters.length > 0;
    const collector = (snap.metrics_rollup && snap.metrics_rollup.collector) || {};
    state.telemetryLive = (collector.events_recorded || 0) > 0;
    if (state.graphAvailable && graph.graph_version !== galaxy.graphVersion) buildGalaxy(graph);
    else if (state.graphAvailable) updateGalaxyHeat(graph.clusters);
    if (!state.graphAvailable) clearGalaxy();
    buildPipelines(snap.stations && snap.stations.nodes);
    for (const aj of (snap.stations && snap.stations.active_jobs) || [])
      upsertPacket(aj.job_id, aj.task_class, aj.stage);
    setLadderBrightness((snap.ladder && snap.ladder.tiers) || []);
    setTelemetryPill();
    updateDormantDressing();
    renderDockStations();
    renderLayoutNote();
  } catch (e) {
    setConn("off", "offline");
  }
}

async function loadMetrics() {
  try {
    const r = await api(`/v1/observatory/metrics?window=${encodeURIComponent(state.window)}`);
    if (!r.ok) return;
    state.metrics = await r.json();
    // Window-scoped tier brightness: prefer the metrics models rollup when
    // the snapshot's 1h ladder is empty.
    const tiers = ((state.snapshot && state.snapshot.ladder && state.snapshot.ladder.tiers) || []);
    if (!tiers.length && state.metrics.models && state.metrics.models.length) {
      const byTier = new Map();
      let total = 0;
      for (const m of state.metrics.models) {
        byTier.set(m.tier, (byTier.get(m.tier) || 0) + (m.calls || 0));
        total += m.calls || 0;
      }
      setLadderBrightness([...byTier].map(([tier, calls]) => ({
        tier, model: null, share_1h: total ? calls / total : null, n: calls,
        p50_latency_ms: null, p95_latency_ms: null,
      })));
    }
    renderDockStations();
    renderLayoutNote();
  } catch (e) { /* keep the last good rollup */ }
}

async function refreshAll() {
  await Promise.all([loadSnapshot(), loadMetrics(), loadRecs()]);
}

$("#winsel").addEventListener("change", () => {
  state.window = $("#winsel").value;
  loadMetrics();
  loadRecs();
  renderLayoutNote();
});

// Sacred-geometry layout select — rebuild the galaxy on the new lattice.
const _layoutSel = $("#layoutsel");
if (_layoutSel) {
  _layoutSel.addEventListener("change", () => {
    state.layout = _layoutSel.value;
    if (state.snapshot && state.snapshot.graph) buildGalaxy(state.snapshot.graph);
    renderLayoutNote();
  });
}

/* ════════════════════════════════════════════════════════════════════════
 * 12. SSE — fetch-streaming with Authorization + Last-Event-ID resume
 * ════════════════════════════════════════════════════════════════════════ */

// EventSource cannot attach the Authorization header, so (exactly like the
// cockpit page) we stream the SSE body through fetch() and parse frames
// ourselves. Resume rides the Last-Event-ID header; a server `resync` event
// (replay-ring gap or graph rebuild) triggers a full snapshot refetch.
let sseAbort = null;

function dispatchEvent_(event, data) {
  let d = null;
  if (data) { try { d = JSON.parse(data); } catch (e) { return; } }
  if (event === "resync") { refreshAll(); return; }
  if (!d) return;
  if (event === "job.stage") {
    upsertPacket(d.job_id, d.task_class, d.stage);
  } else if (event === "gate.verdict") {
    gateFlare(d.job_id, d.verdict);
    pushVerdict(d);
  } else if (event === "node.activate") {
    pulseCluster(d.cluster_id, d.weight);
  } else if (event === "route.decision") {
    routeStreak(d.tier);
    if (!state.telemetryLive) { state.telemetryLive = true; setTelemetryPill(); updateDormantDressing(); }
  }
}

async function subscribeStream(ctrl) {
  let backoff = 1000;
  while (!ctrl.signal.aborted && token) {
    try {
      const headers = authHeaders({ Accept: "text/event-stream" });
      if (state.lastEventId != null) headers["Last-Event-ID"] = String(state.lastEventId);
      const r = await fetch(apiBase + "/v1/observatory/stream", { headers, signal: ctrl.signal });
      if (!r.ok || !r.body) {
        if (r.status === 401) { setConn("off", "unauthorized — set token"); return; }
        if (r.status === 503) { setConn("warn", "collector unavailable"); throw new Error("503"); }
        throw new Error("stream status " + r.status);
      }
      setConn("live", "live");
      state.connLive = true;
      backoff = 1000;
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let sep;
        while ((sep = buf.indexOf("\n\n")) >= 0) {
          const frameTxt = buf.slice(0, sep);
          buf = buf.slice(sep + 2);
          let event = "message";
          const dataLines = [];
          for (const raw of frameTxt.split("\n")) {
            if (raw.startsWith(":")) continue;            // ": ping" heartbeat
            else if (raw.startsWith("id:")) {
              const idv = parseInt(raw.slice(3).trim(), 10);
              if (!Number.isNaN(idv)) state.lastEventId = idv;
            } else if (raw.startsWith("event:")) event = raw.slice(6).trim();
            else if (raw.startsWith("data:")) dataLines.push(raw.slice(5).replace(/^ /, ""));
            // "retry:" hints are accepted silently; our backoff governs.
          }
          if (dataLines.length) dispatchEvent_(event, dataLines.join("\n"));
        }
      }
      // Clean end (server duration cap) — reconnect promptly with resume id.
    } catch (e) {
      if (ctrl.signal.aborted) return;
    }
    state.connLive = false;
    setConn("warn", "reconnecting…");
    if (ctrl.signal.aborted || !token) return;
    await new Promise((res) => setTimeout(res, backoff));
    backoff = Math.min(backoff * 2, 15000); // exponential, capped
  }
}

function startStream() {
  if (sseAbort) { try { sseAbort.abort(); } catch (e) {} sseAbort = null; }
  if (!token) { setConn("off", "no token"); return; }
  if (typeof ReadableStream === "undefined" || typeof AbortController === "undefined") {
    setConn("warn", "streaming unsupported");
    return;
  }
  const ctrl = new AbortController();
  sseAbort = ctrl;
  subscribeStream(ctrl);
}

/* Fused all-actions stream (/v1/observatory/actions) — every recorded system
 * action as a visual. Spatial kinds reuse the galaxy/pipeline/ladder helpers;
 * non-spatial pulses (owner/agent/skill/system/axiom) flash a brief, honest
 * full-frame tint so the wallpaper "sees everything". The id: line is an opaque
 * resume cursor (string), not the integer the observatory stream uses. */
let actionsAbort = null;

function actionFlash(severity) {
  const node = $("#actionflash");
  if (!node) return;
  node.dataset.sev = severity || "info";
  node.hidden = false;
  node.classList.remove("on");
  void node.offsetWidth; // restart the transition
  node.classList.add("on");
  clearTimeout(actionFlash._t);
  actionFlash._t = setTimeout(() => node.classList.remove("on"), 60);
}

function dispatchAction_(event, data) {
  let d = null;
  if (data) { try { d = JSON.parse(data); } catch (e) { return; } }
  if (!d) return;
  const target = d.target || {};
  switch (event) {
    case "cluster.spark": if (target.cluster_id) pulseCluster(target.cluster_id, d.weight); break;
    case "pipeline.packet": if (target.job_id) upsertPacket(target.job_id, null, d.label); break;
    case "gate.flare": if (target.job_id) gateFlare(target.job_id, d.severity === "error" ? "fail" : "pass"); break;
    case "ladder.streak": routeStreak(String(d.label || "").split("·")[0]); break;
    case "meta.resync": return; // control only
    default: actionFlash(d.severity); break; // owner/agent/skill/system/audit pulses
  }
  if (!state.telemetryLive) { state.telemetryLive = true; setTelemetryPill(); updateDormantDressing(); }
}

async function subscribeActions(ctrl) {
  let backoff = 1000;
  let lastId = null;
  while (!ctrl.signal.aborted && token) {
    try {
      const headers = authHeaders({ Accept: "text/event-stream" });
      if (lastId != null) headers["Last-Event-ID"] = String(lastId);
      const r = await fetch(apiBase + "/v1/observatory/actions", { headers, signal: ctrl.signal });
      if (!r.ok || !r.body) {
        if (r.status === 401 || r.status === 503) return; // unauth/dormant: stay silent
        throw new Error("actions status " + r.status);
      }
      backoff = 1000;
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let sep;
        while ((sep = buf.indexOf("\n\n")) >= 0) {
          const frameTxt = buf.slice(0, sep);
          buf = buf.slice(sep + 2);
          let event = "message";
          const dataLines = [];
          for (const raw of frameTxt.split("\n")) {
            if (raw.startsWith(":")) continue;             // ": ping" heartbeat
            else if (raw.startsWith("id:")) lastId = raw.slice(3).trim(); // opaque cursor
            else if (raw.startsWith("event:")) event = raw.slice(6).trim();
            else if (raw.startsWith("data:")) dataLines.push(raw.slice(5).replace(/^ /, ""));
          }
          if (dataLines.length) dispatchAction_(event, dataLines.join("\n"));
        }
      }
    } catch (e) {
      if (ctrl.signal.aborted) return;
    }
    if (ctrl.signal.aborted || !token) return;
    await new Promise((res) => setTimeout(res, backoff));
    backoff = Math.min(backoff * 2, 15000);
  }
}

function startActions() {
  if (actionsAbort) { try { actionsAbort.abort(); } catch (e) {} actionsAbort = null; }
  if (!token) return;
  if (typeof ReadableStream === "undefined" || typeof AbortController === "undefined") return;
  const ctrl = new AbortController();
  actionsAbort = ctrl;
  subscribeActions(ctrl);
}

/* ════════════════════════════════════════════════════════════════════════
 * 13. Token dialog + boot
 * ════════════════════════════════════════════════════════════════════════ */

$("#tokenbtn").addEventListener("click", () => {
  $("#tokenin").value = token;
  $("#tokendlg").showModal();
});
$("#tokensave").addEventListener("click", () => {
  token = $("#tokenin").value.trim();
  localStorage.setItem(TOKEN_KEY, token);
  $("#tokenbtn").textContent = token ? "Token ✓" : "Token";
  startStream();
  startActions();
  refreshAll();
});
$("#tokenbtn").textContent = token ? "Token ✓" : "Token";

setView("galaxy");
renderDockStations();
renderLayoutNote();
if (WALLPAPER) document.body.classList.add("wallpaper");
if (DEMO) {
  // Static snapshot mode: load the bundle, render once, no live streams.
  loadDemo().then(() => { refreshAll(); setConn("warn", "demo · static snapshot"); });
} else {
  refreshAll();
  startStream();
  startActions();
  if (!token) {
    setConn("off", "no token");
    $("#recslist").replaceChildren(el("div", "empty",
      "Pair this browser first — click ", el("b", "", "Token"),
      " and paste the cockpit token."));
  }
}
