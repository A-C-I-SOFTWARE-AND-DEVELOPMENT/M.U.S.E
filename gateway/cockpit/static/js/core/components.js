// muse cockpit — render helpers (the component catalog as DOM builders).
//
// Pure functions that BUILD DOM nodes using the cockpit.css classes. View
// modules render through these so the look stays uniform — never hand-roll a
// card/pill/button in a view. White is the hero; the spectral ring is matte.

// ---- el(): the base element factory --------------------------------------
// el(tag, props?, children?)
//   props: { class, text, html, dataset:{}, style:{}, on:{event:fn}, ...attrs }
//   children: a node, a string, or an array of either (strings become text).
// Returns the constructed HTMLElement.
export function el(tag, props, children) {
  const node = document.createElement(tag);
  const p = props || {};
  for (const [k, v] of Object.entries(p)) {
    if (v == null) continue;
    if (k === "class" || k === "className") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "dataset") for (const [dk, dv] of Object.entries(v)) node.dataset[dk] = dv;
    else if (k === "style" && typeof v === "object") Object.assign(node.style, v);
    else if (k === "on" && typeof v === "object") for (const [ev, fn] of Object.entries(v)) node.addEventListener(ev, fn);
    else node.setAttribute(k, v);
  }
  appendChildren(node, children);
  return node;
}

function appendChildren(node, children) {
  if (children == null) return;
  const list = Array.isArray(children) ? children : [children];
  for (const c of list) {
    if (c == null || c === false) continue;
    node.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

// ---- Glyph: the brand mark (matte ring, core bloom, optional spin) -------
// glyph({ size?, spin? }) → a .glyph span wrapping the SVG mark. spin only in
// the live header. Used internally by emptyState (dimmed, no spin).
export function glyph({ size = 30, spin = false } = {}) {
  const wrap = el("span", { class: "glyph" + (spin ? " spin" : "") });
  wrap.innerHTML = `
    <svg viewBox="0 0 48 48" width="${size}" height="${size}" aria-hidden="true">
      <defs><linearGradient id="rg-${Math.random().toString(36).slice(2, 8)}" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#7ae0ff"/><stop offset="1" stop-color="#b388ff"/>
      </linearGradient></defs>
      <g transform="rotate(-32 24 24)">
        <circle cx="24" cy="24" r="15" fill="none" stroke="url(#rg)" stroke-width="1.6"
                stroke-dasharray="66 28" stroke-linecap="round"/>
      </g>
      <circle cx="24" cy="24" r="3.1" fill="#fff"/>
    </svg>`;
  // Point the stroke at the per-instance gradient id we just generated.
  const grad = wrap.querySelector("linearGradient");
  const ring = wrap.querySelector("circle[stroke]");
  if (grad && ring) ring.setAttribute("stroke", `url(#${grad.id})`);
  return wrap;
}

// ---- card(content) -------------------------------------------------------
// card(children, { interactive? }) → a .card surface. children: node/string/array.
export function card(children, { interactive = false } = {}) {
  return el("div", { class: "card" + (interactive ? " interactive" : "") }, children);
}

// ---- pill(text, state) ---------------------------------------------------
// state ∈ "neutral" | "ok" | "warn" | "danger" | "accent" | "selected".
export function pill(text, state = "neutral") {
  return el("span", { class: "pill " + state, text: String(text == null ? "" : text) });
}

// ---- statusDot(state) ----------------------------------------------------
// state ∈ "ok" | "warn" | "danger" | "off" | "live" (anything else → idle/mute).
export function statusDot(state) {
  const s = state ? " " + state : "";
  return el("span", { class: "dot" + s });
}

// ---- phaseRail(phases) ---------------------------------------------------
// phases: [{ label, state }] with state ∈ "done" | "active" | "pending" | "failed".
// Renders a .phaserail with a 4px bar per segment + a label beneath.
export function phaseRail(phases) {
  const segs = (phases || []).map((p) => {
    const state = p.state || "pending";
    return el("div", { class: "phase " + state }, [
      el("div", { class: "bar" }),
      el("div", { class: "label", text: p.label == null ? "" : String(p.label) }),
    ]);
  });
  return el("div", { class: "phaserail" }, [el("div", { class: "segments" }, segs)]);
}

// ---- emptyState({ glyph, title, body, action }) --------------------------
// Centered zero-data placeholder. `glyph` defaults to true (dimmed mark, no
// spin); pass false to omit. `action` is an optional Button node (from
// button() below). title/body are strings.
export function emptyState({ glyph: showGlyph = true, title, body, action } = {}) {
  const children = [];
  if (showGlyph) children.push(glyph({ size: 56, spin: false }));
  if (title) children.push(el("h2", { class: "empty-title", text: title }));
  if (body) children.push(el("p", { class: "empty-body", text: body }));
  if (action) children.push(action);
  return el("div", { class: "empty" }, children);
}

// ---- sectionHeader({ eyebrow, title, trailing }) -------------------------
// `eyebrow` is the uppercase label; `title` an optional heading; `trailing` an
// optional node (Ghost button / chip) pinned to the right.
export function sectionHeader({ eyebrow, title, trailing } = {}) {
  const heads = [];
  if (eyebrow) heads.push(el("div", { class: "eyebrow", text: eyebrow }));
  if (title) heads.push(el("h2", { class: "section-title", text: title }));
  const kids = [el("div", { class: "heads" }, heads)];
  if (trailing) kids.push(el("div", { class: "trailing" }, trailing));
  return el("div", { class: "section-header" }, kids);
}

// ---- button({ label, variant, onClick, ...}) -----------------------------
// variant ∈ "primary" | "secondary" | "ghost" | "danger" (default secondary).
// Optional: disabled (bool), type (default "button"), title, dataset.
export function button({ label, variant = "secondary", onClick, disabled = false, type = "button", title, dataset } = {}) {
  const props = { class: "btn " + variant, type, text: label == null ? "" : String(label) };
  if (disabled) props.disabled = "disabled";
  if (title) props.title = title;
  if (dataset) props.dataset = dataset;
  if (onClick) props.on = { click: onClick };
  return el("button", props);
}
