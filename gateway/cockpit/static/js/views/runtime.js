// muse cockpit — Runtime view.
//
// Read-only runtime & diagnostics dashboard. Pulls four endpoints:
//   GET /v1/cockpit/runtime/status   — overall runtime status + gateway version
//   GET /v1/cockpit/runtime/workers  — worker pool rows
//   GET /v1/cockpit/diagnostics      — health/diagnostic checks
//   GET /v1/cockpit/capabilities     — feature/capability flags
// and renders them as a stat grid, worker rows, capability list and version
// using the shared component helpers + cockpit.css classes. White is the hero,
// the spectral ring is matte, hierarchy is by VALUE — no neon, no shadows.
//
// Lifecycle: mount() runs once. We poll runtime/status (the cheap, fast-moving
// part) every ~10s while the view is shown (onShow/onHide), and re-fetch the
// slower-moving lists (workers/diagnostics/capabilities) on each show and token
// change. Everything goes through ctx.api — never hand-rolled fetch/headers.

const POLL_MS = 10000;

export async function mount(container, ctx) {
  const { api, components } = ctx;
  const { el, card, pill, statusDot, sectionHeader, emptyState, button } = components;

  // ---- view scaffold ------------------------------------------------------
  const statusSlot = el("div", { class: "runtime-slot" });
  const workersSlot = el("div", { class: "runtime-slot" });
  const diagSlot = el("div", { class: "runtime-slot" });
  const capsSlot = el("div", { class: "runtime-slot" });

  const root = el("div", { class: "runtime-view", style: { display: "grid", gap: "var(--space-6, 24px)" } }, [
    statusSlot,
    workersSlot,
    diagSlot,
    capsSlot,
  ]);
  container.replaceChildren(root);

  // ---- local state --------------------------------------------------------
  let pollTimer = null;
  let visible = false;
  let inFlight = false;

  // ---- small render helpers (uniform look via tokens, no inline neon) ------
  const PILL_STATES = ["neutral", "ok", "warn", "danger", "accent", "selected"];

  // Map a free-form status/health string to one of the documented pill states.
  function stateForValue(v) {
    const s = String(v == null ? "" : v).toLowerCase().trim();
    if (["ok", "ready", "online", "up", "healthy", "pass", "passed", "good", "active", "live", "running", "true", "enabled", "available", "yes"].includes(s)) return "ok";
    if (["warn", "warning", "degraded", "pending", "starting", "busy", "partial", "stale"].includes(s)) return "warn";
    if (["danger", "error", "fail", "failed", "down", "offline", "unhealthy", "critical", "stopped", "false", "disabled", "unavailable", "no"].includes(s)) return "danger";
    if (["idle", "neutral", "unknown", "n/a", "na", "", "none"].includes(s)) return "neutral";
    return "accent";
  }

  function dotStateForValue(v) {
    const st = stateForValue(v);
    if (st === "ok") return "ok";
    if (st === "warn") return "warn";
    if (st === "danger") return "danger";
    return "off";
  }

  function titleCase(k) {
    return String(k)
      .replace(/[_\-.]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function fmtValue(v) {
    if (v == null) return "—";
    if (typeof v === "boolean") return v ? "Yes" : "No";
    if (typeof v === "number") return String(v);
    if (typeof v === "string") return v.length ? v : "—";
    if (Array.isArray(v)) return v.length ? v.map(fmtValue).join(", ") : "—";
    if (typeof v === "object") {
      try { return JSON.stringify(v); } catch (e) { return "—"; }
    }
    return String(v);
  }

  // A labeled stat tile: small dim eyebrow label + the prominent value.
  function statTile(label, value, opts) {
    const o = opts || {};
    const kids = [el("div", { class: "eyebrow", text: String(label).toUpperCase() })];
    if (o.pillState) {
      kids.push(el("div", { style: { marginTop: "var(--space-2, 8px)" } }, [pill(String(value), o.pillState)]));
    } else {
      kids.push(el("div", {
        class: o.mono ? "mono" : "",
        style: {
          marginTop: "var(--space-2, 8px)",
          fontSize: "var(--type-title-size, 22px)",
          fontWeight: "var(--type-title-weight, 600)",
          color: "var(--signal, #E8ECF4)",
          lineHeight: "var(--type-title-line, 1.2)",
          wordBreak: "break-word",
        },
        text: String(value),
      }));
    }
    return el("div", {
      style: {
        background: "var(--void-2)",
        border: "1px solid var(--edge)",
        borderRadius: "var(--radius-md, 12px)",
        padding: "var(--space-4, 16px)",
      },
    }, kids);
  }

  function statGrid(tiles) {
    return el("div", {
      style: {
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
        gap: "var(--space-3, 12px)",
      },
    }, tiles);
  }

  // A friendly error card (never throw uncaught; show this instead).
  function errorCard(title, err) {
    const status = err && err.status ? " (HTTP " + err.status + ")" : "";
    let line = "Could not load this section" + status + ".";
    if (err && err.status === 401) line = "Not paired yet — pair this cockpit from the header to view runtime data.";
    else if (err && err.status === 403) line = "This data is owner-gated and unavailable here.";
    else if (err && err.status === 404) line = "This endpoint is not available on the connected gateway.";
    return card([
      sectionHeader({ eyebrow: "Runtime", title }),
      el("p", { class: "muted", style: { marginTop: "var(--space-3, 12px)" }, text: line }),
    ]);
  }

  function loadingCard(title) {
    return card([
      sectionHeader({ eyebrow: "Runtime", title }),
      el("p", { class: "muted", style: { marginTop: "var(--space-3, 12px)" }, text: "Loading…" }),
    ]);
  }

  // Coerce assorted response shapes into a plain array of row objects.
  function asArray(data, ...keys) {
    if (Array.isArray(data)) return data;
    if (data && typeof data === "object") {
      for (const k of keys) {
        if (Array.isArray(data[k])) return data[k];
      }
      // {name: {...}} → [{name, ...}]
      const vals = Object.values(data);
      if (vals.length && vals.every((v) => v && typeof v === "object")) {
        return Object.entries(data).map(([k, v]) => Object.assign({ name: k }, v));
      }
    }
    return [];
  }

  // ---- STATUS section -----------------------------------------------------
  function renderStatus(data) {
    if (!data || typeof data !== "object") {
      statusSlot.replaceChildren(card([
        sectionHeader({ eyebrow: "Runtime", title: "Status" }),
        emptyState({ title: "No status reported", body: "The gateway returned no runtime status." }),
      ]));
      return;
    }

    const version =
      data.version || data.gateway_version || data.build || data.build_version ||
      (data.gateway && (data.gateway.version || data.gateway.build)) || null;
    const overall =
      data.status || data.state || data.health || (data.ok != null ? (data.ok ? "ok" : "down") : null);
    const uptime = data.uptime || data.uptime_human || data.uptime_seconds || data.started_at || null;

    const tiles = [];
    if (overall != null) tiles.push(statTile("Status", String(overall).toUpperCase(), { pillState: stateForValue(overall) }));
    if (version != null) tiles.push(statTile("Gateway Version", fmtValue(version), { mono: true }));
    if (uptime != null) tiles.push(statTile("Uptime", fmtValue(uptime)));

    // Surface any remaining scalar fields as stat tiles (skip nested objects we
    // don't have a dedicated slot for, and the ones we already showed).
    const shown = new Set([
      "version", "gateway_version", "build", "build_version", "gateway",
      "status", "state", "health", "ok", "uptime", "uptime_human",
      "uptime_seconds", "started_at",
    ]);
    for (const [k, v] of Object.entries(data)) {
      if (shown.has(k)) continue;
      if (v != null && typeof v === "object" && !Array.isArray(v)) continue;
      const looksStatus = /status|state|health|mode|enabled|active|online|ok|ready/i.test(k);
      tiles.push(statTile(titleCase(k), fmtValue(v), { pillState: looksStatus && typeof v !== "object" ? stateForValue(v) : null }));
    }

    const header = sectionHeader({
      eyebrow: "Runtime",
      title: "Status",
      trailing: overall != null ? pill(String(overall).toUpperCase(), stateForValue(overall)) : null,
    });

    statusSlot.replaceChildren(card([
      header,
      tiles.length
        ? el("div", { style: { marginTop: "var(--space-4, 16px)" } }, [statGrid(tiles)])
        : el("p", { class: "muted", style: { marginTop: "var(--space-3, 12px)" }, text: "No status fields reported." }),
    ]));
  }

  // ---- WORKERS section ----------------------------------------------------
  function renderWorkers(data) {
    const rows = asArray(data, "workers", "items", "pool", "list");
    const header = sectionHeader({ eyebrow: "Orchestration", title: "Workers" });

    if (!rows.length) {
      workersSlot.replaceChildren(card([
        header,
        emptyState({ title: "No workers", body: "No worker profiles are currently registered with the runtime." }),
      ]));
      return;
    }

    const rowNodes = rows.map((w) => {
      const name = w.name || w.id || w.profile || w.worker || w.label || "worker";
      const state = w.status || w.state || w.health || (w.alive != null ? (w.alive ? "ok" : "down") : null) || (w.busy ? "busy" : "idle");
      const meta = [];
      const active = w.active != null ? w.active : (w.in_flight != null ? w.in_flight : w.running);
      const cap = w.capacity != null ? w.capacity : (w.max != null ? w.max : w.slots);
      if (active != null && cap != null) meta.push(active + " / " + cap);
      else if (active != null) meta.push(fmtValue(active) + " active");
      if (w.model || w.task_class) meta.push(fmtValue(w.model || w.task_class));
      if (w.last_seen || w.heartbeat) meta.push("seen " + fmtValue(w.last_seen || w.heartbeat));

      const left = el("div", { class: "row", style: { gap: "var(--space-3, 12px)", alignItems: "center", minWidth: "0" } }, [
        statusDot(dotStateForValue(state)),
        el("div", { style: { minWidth: "0" } }, [
          el("div", { style: { fontWeight: "var(--type-body-weight, 400)", color: "var(--signal, #E8ECF4)" }, text: String(name) }),
          meta.length ? el("div", { class: "mono muted", style: { fontSize: "var(--type-label-size, 12px)", marginTop: "2px" }, text: meta.join("  ·  ") }) : false,
        ]),
      ]);
      const right = pill(String(state).toUpperCase(), stateForValue(state));

      return el("div", {
        class: "row",
        style: {
          justifyContent: "space-between",
          alignItems: "center",
          gap: "var(--space-3, 12px)",
          padding: "var(--space-3, 12px) 0",
          borderTop: "1px solid var(--edge)",
        },
      }, [left, right]);
    });

    workersSlot.replaceChildren(card([header, el("div", { style: { marginTop: "var(--space-2, 8px)" } }, rowNodes)]));
  }

  // ---- DIAGNOSTICS section ------------------------------------------------
  function renderDiagnostics(data) {
    const header = sectionHeader({ eyebrow: "Health", title: "Diagnostics" });
    let checks = asArray(data, "checks", "diagnostics", "items", "results");

    // Some gateways return a flat object of {check_name: status|{...}}.
    if (!checks.length && data && typeof data === "object" && !Array.isArray(data)) {
      checks = Object.entries(data).map(([k, v]) => {
        if (v && typeof v === "object") return Object.assign({ name: k }, v);
        return { name: k, status: v };
      });
    }

    if (!checks.length) {
      diagSlot.replaceChildren(card([
        header,
        emptyState({ title: "No diagnostics", body: "The gateway reported no diagnostic checks." }),
      ]));
      return;
    }

    const rowNodes = checks.map((c) => {
      const name = c.name || c.id || c.check || c.label || "check";
      const state = c.status || c.state || c.result || c.health || (c.ok != null ? (c.ok ? "ok" : "fail") : null) || (c.passed != null ? (c.passed ? "ok" : "fail") : "unknown");
      const detail = c.detail || c.message || c.description || c.info || null;

      const left = el("div", { class: "row", style: { gap: "var(--space-3, 12px)", alignItems: "center", minWidth: "0" } }, [
        statusDot(dotStateForValue(state)),
        el("div", { style: { minWidth: "0" } }, [
          el("div", { style: { color: "var(--signal, #E8ECF4)" }, text: titleCase(name) }),
          detail ? el("div", { class: "muted", style: { fontSize: "var(--type-label-size, 12px)", marginTop: "2px" }, text: fmtValue(detail) }) : false,
        ]),
      ]);
      const right = pill(String(state).toUpperCase(), stateForValue(state));

      return el("div", {
        class: "row",
        style: {
          justifyContent: "space-between",
          alignItems: "center",
          gap: "var(--space-3, 12px)",
          padding: "var(--space-3, 12px) 0",
          borderTop: "1px solid var(--edge)",
        },
      }, [left, right]);
    });

    diagSlot.replaceChildren(card([header, el("div", { style: { marginTop: "var(--space-2, 8px)" } }, rowNodes)]));
  }

  // ---- CAPABILITIES section -----------------------------------------------
  function renderCapabilities(data) {
    const header = sectionHeader({ eyebrow: "Platform", title: "Capabilities" });
    let caps = [];

    if (Array.isArray(data)) {
      caps = data.map((c) => {
        if (c && typeof c === "object") return { name: c.name || c.id || c.capability || c.key || "capability", enabled: c.enabled != null ? c.enabled : (c.available != null ? c.available : c.value) };
        return { name: String(c), enabled: true };
      });
    } else if (data && typeof data === "object") {
      const inner = data.capabilities || data.features || data.flags || data;
      if (Array.isArray(inner)) {
        caps = inner.map((c) => (c && typeof c === "object" ? { name: c.name || c.id || "capability", enabled: c.enabled != null ? c.enabled : c.available } : { name: String(c), enabled: true }));
      } else if (inner && typeof inner === "object") {
        caps = Object.entries(inner).map(([k, v]) => ({ name: k, enabled: v }));
      }
    }

    if (!caps.length) {
      capsSlot.replaceChildren(card([
        header,
        emptyState({ title: "No capabilities", body: "The gateway advertised no capability flags." }),
      ]));
      return;
    }

    const tiles = caps.map((c) => {
      const v = c.enabled;
      const isBool = typeof v === "boolean" || v == null;
      const label = isBool ? (v ? "ENABLED" : "DISABLED") : String(fmtValue(v)).toUpperCase();
      const st = isBool ? (v ? "ok" : "neutral") : stateForValue(v);
      return statTile(titleCase(c.name), label, { pillState: st });
    });

    capsSlot.replaceChildren(card([header, el("div", { style: { marginTop: "var(--space-4, 16px)" } }, [statGrid(tiles)])]));
  }

  // ---- loaders ------------------------------------------------------------
  async function loadStatus(showLoading) {
    if (showLoading) statusSlot.replaceChildren(loadingCard("Status"));
    try {
      const data = await api.getJSON("/v1/cockpit/runtime/status");
      renderStatus(data);
    } catch (err) {
      statusSlot.replaceChildren(errorCard("Status", err));
    }
  }

  async function loadWorkers() {
    workersSlot.replaceChildren(loadingCard("Workers"));
    try {
      renderWorkers(await api.getJSON("/v1/cockpit/runtime/workers"));
    } catch (err) {
      workersSlot.replaceChildren(errorCard("Workers", err));
    }
  }

  async function loadDiagnostics() {
    diagSlot.replaceChildren(loadingCard("Diagnostics"));
    try {
      renderDiagnostics(await api.getJSON("/v1/cockpit/diagnostics"));
    } catch (err) {
      diagSlot.replaceChildren(errorCard("Diagnostics", err));
    }
  }

  async function loadCapabilities() {
    capsSlot.replaceChildren(loadingCard("Capabilities"));
    try {
      renderCapabilities(await api.getJSON("/v1/cockpit/capabilities"));
    } catch (err) {
      capsSlot.replaceChildren(errorCard("Capabilities", err));
    }
  }

  // Load everything (used on first show + token changes). Guards re-entrancy.
  async function loadAll() {
    if (inFlight) return;
    inFlight = true;
    try {
      await Promise.all([
        loadStatus(true),
        loadWorkers(),
        loadDiagnostics(),
        loadCapabilities(),
      ]);
    } finally {
      inFlight = false;
    }
  }

  // If unpaired, show a single friendly prompt across all slots and skip fetch.
  function renderUnpaired() {
    statusSlot.replaceChildren(card([
      sectionHeader({ eyebrow: "Runtime", title: "Status" }),
      emptyState({
        title: "Not paired",
        body: "Pair this cockpit from the header to view runtime status, workers, diagnostics and capabilities.",
      }),
    ]));
    workersSlot.replaceChildren();
    diagSlot.replaceChildren();
    capsSlot.replaceChildren();
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(() => {
      if (!visible) return;
      if (!api.getToken()) return;
      // Only the fast-moving status is polled; lists refresh on show/token.
      loadStatus(false);
    }, POLL_MS);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  // React to pairing/unpairing while the view is alive.
  const unsubscribe = ctx.onTokenChange ? ctx.onTokenChange((token) => {
    if (!visible) return;
    if (token) loadAll();
    else { stopPolling(); renderUnpaired(); }
  }) : null;

  // Initial paint (in case onShow is delayed) — show a paired/unpaired hint.
  if (!api.getToken()) renderUnpaired();
  else {
    statusSlot.replaceChildren(loadingCard("Status"));
    workersSlot.replaceChildren(loadingCard("Workers"));
    diagSlot.replaceChildren(loadingCard("Diagnostics"));
    capsSlot.replaceChildren(loadingCard("Capabilities"));
  }

  return {
    async onShow() {
      visible = true;
      if (!api.getToken()) { renderUnpaired(); return; }
      await loadAll();
      startPolling();
    },
    onHide() {
      visible = false;
      stopPolling();
    },
  };
}
