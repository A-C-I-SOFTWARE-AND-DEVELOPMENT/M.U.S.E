// muse cockpit — Evidence view.
//
// Lists the evidence ledger (GET /v1/cockpit/evidence) with a search box that
// queries GET /v1/cockpit/evidence/search?q=. Each item renders as a .card with
// its claim/snippet, source, and confidence, plus the actions:
//   Verify  → POST   /v1/cockpit/evidence/verify
//   Promote → POST   /v1/cockpit/evidence/{id}/promote
//   Detail  → GET    /v1/cockpit/evidence/{id}
//   Demote  → DELETE /v1/cockpit/evidence/{id}
//
// Renders exclusively through ctx.components + the documented cockpit.css
// classes (matte ring, value hierarchy, no neon, no shadows). All network goes
// through ctx.api. Self-contained: export async function mount(container, ctx).

export async function mount(container, ctx) {
  const { api, components } = ctx;
  const { el, card, pill, button, sectionHeader, emptyState } = components;

  // ---- view state --------------------------------------------------------
  let query = "";          // current search term ("" = full list)
  let items = [];          // last loaded evidence items
  let loading = false;     // a list/search fetch is in flight
  let loadError = null;    // friendly error string, or null
  let token = 0;           // request token — only the latest load may render
  let started = false;     // onShow has run at least once

  // ---- DOM scaffold ------------------------------------------------------
  const searchInput = el("input", {
    class: "field grow",
    type: "search",
    placeholder: "Search claims, sources…",
    "aria-label": "Search evidence",
    value: "",
    on: {
      input: (e) => { query = e.target.value; },
      keydown: (e) => { if (e.key === "Enter") { e.preventDefault(); runSearch(); } },
    },
  });
  const searchBtn = button({ label: "Search", variant: "primary", onClick: () => runSearch() });
  const clearBtn = button({ label: "Clear", variant: "ghost", onClick: () => {
    query = "";
    searchInput.value = "";
    load();
  } });
  const refreshBtn = button({ label: "Refresh", variant: "secondary", onClick: () => load() });

  const header = sectionHeader({
    eyebrow: "Cognition",
    title: "Evidence",
    trailing: refreshBtn,
  });

  const controls = el("div", { class: "row", style: { gap: "var(--space-2)", marginBottom: "var(--space-4)" } }, [
    searchInput,
    searchBtn,
    clearBtn,
  ]);

  const listEl = el("div", { style: { display: "flex", flexDirection: "column", gap: "var(--space-3)" } });

  container.replaceChildren(header, controls, listEl);

  // ---- helpers -----------------------------------------------------------
  function fieldOf(obj, keys, fallback) {
    if (!obj || typeof obj !== "object") return fallback;
    for (const k of keys) {
      const v = obj[k];
      if (v != null && v !== "") return v;
    }
    return fallback;
  }

  function idOf(item) {
    const v = fieldOf(item, ["id", "evidence_id", "uid", "key", "hash"], null);
    return v == null ? null : String(v);
  }

  function confState(score) {
    const n = Number(score);
    if (!Number.isFinite(n)) return "neutral";
    if (n >= 0.75) return "ok";
    if (n >= 0.4) return "warn";
    return "danger";
  }

  function confLabel(item) {
    const raw = fieldOf(item, ["confidence", "score", "confidence_score"], null);
    if (raw == null) return null;
    const n = Number(raw);
    if (!Number.isFinite(n)) return { text: String(raw), state: "neutral" };
    // Accept both 0–1 and 0–100 scales.
    const pct = n <= 1 ? Math.round(n * 100) : Math.round(n);
    return { text: "Confidence " + pct + "%", state: confState(n <= 1 ? n : n / 100) };
  }

  function statusPill(item) {
    const st = fieldOf(item, ["status", "state", "verification"], null);
    if (!st) return null;
    const s = String(st).toLowerCase();
    let state = "neutral";
    if (s.includes("verif") || s.includes("promot") || s.includes("confirm")) state = "ok";
    else if (s.includes("pend") || s.includes("review") || s.includes("unverif")) state = "warn";
    else if (s.includes("reject") || s.includes("fail") || s.includes("disput")) state = "danger";
    return pill(String(st).toUpperCase(), state);
  }

  function asText(v) {
    if (v == null) return "";
    if (typeof v === "string") return v;
    try { return JSON.stringify(v, null, 2); } catch (e) { return String(v); }
  }

  // ---- detail dialog -----------------------------------------------------
  async function showDetail(id) {
    let data;
    try {
      data = await api.getJSON("/v1/cockpit/evidence/" + encodeURIComponent(id));
    } catch (e) {
      data = { error: friendly(e) };
    }
    const dlg = el("dialog", { class: "card" });
    const close = () => { if (dlg.open) dlg.close(); dlg.remove(); };
    const closeBtn = button({ label: "Close", variant: "secondary", onClick: close });
    dlg.appendChild(sectionHeader({ eyebrow: "Evidence", title: "Detail · " + id }));
    dlg.appendChild(el("pre", {
      class: "mono",
      style: {
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        marginTop: "var(--space-3)",
        maxHeight: "60vh",
        overflow: "auto",
      },
      text: asText(data),
    }));
    dlg.appendChild(el("div", { class: "dialog-actions" }, [closeBtn]));
    dlg.addEventListener("cancel", (e) => { e.preventDefault(); close(); });
    container.appendChild(dlg);
    if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
  }

  // ---- actions -----------------------------------------------------------
  function friendly(e) {
    if (e && e.cancelled) return "Cancelled.";
    if (e && e.status === 401) return "Not paired — pair this cockpit from the header first.";
    if (e && e.status === 403) return "Not authorized for this action.";
    if (e && e.status === 404) return "That evidence item no longer exists.";
    if (e && typeof e.status === "number") return "Request failed (" + e.status + ").";
    return "Network error — is the gateway reachable?";
  }

  async function withButtons(buttons, fn) {
    buttons.forEach((b) => { if (b) b.disabled = true; });
    try {
      return await fn();
    } finally {
      buttons.forEach((b) => { if (b) b.disabled = false; });
    }
  }

  function flash(noteEl, text, kind) {
    if (!noteEl) return;
    noteEl.textContent = text;
    noteEl.className = "hint" + (kind ? " " + kind : "");
  }

  async function doVerify(id, buttons, noteEl) {
    flash(noteEl, "Verifying…");
    await withButtons(buttons, async () => {
      try {
        await api.postJSON("/v1/cockpit/evidence/verify", { id });
        flash(noteEl, "Verification requested.", "ok");
        load();
      } catch (e) {
        flash(noteEl, friendly(e), "danger");
      }
    });
  }

  async function doPromote(id, buttons, noteEl) {
    flash(noteEl, "Promoting…");
    await withButtons(buttons, async () => {
      try {
        await api.postJSON("/v1/cockpit/evidence/" + encodeURIComponent(id) + "/promote", {});
        flash(noteEl, "Promoted.", "ok");
        load();
      } catch (e) {
        flash(noteEl, friendly(e), "danger");
      }
    });
  }

  async function doDemote(id, buttons, noteEl) {
    if (!window.confirm("Demote and remove this evidence item?\n\n" + id)) return;
    flash(noteEl, "Demoting…");
    await withButtons(buttons, async () => {
      try {
        const r = await api.api("/v1/cockpit/evidence/" + encodeURIComponent(id), { method: "DELETE" });
        if (!r.ok) { const err = new Error("delete"); err.status = r.status; throw err; }
        flash(noteEl, "Demoted.", "ok");
        load();
      } catch (e) {
        flash(noteEl, friendly(e), "danger");
      }
    });
  }

  // ---- item card ---------------------------------------------------------
  function renderItem(item) {
    const id = idOf(item);
    const claim = fieldOf(item, ["claim", "snippet", "text", "statement", "summary", "title"], "(no claim text)");
    const source = fieldOf(item, ["source", "origin", "url", "citation", "provenance"], null);
    const conf = confLabel(item);

    // Header row: status + confidence pills.
    const pills = [];
    const sp = statusPill(item);
    if (sp) pills.push(sp);
    if (conf) pills.push(pill(conf.text, conf.state));
    const pillRow = pills.length
      ? el("div", { class: "row", style: { gap: "var(--space-2)", marginBottom: "var(--space-2)", flexWrap: "wrap" } }, pills)
      : null;

    const claimEl = el("p", {
      style: {
        fontSize: "var(--type-body-size)",
        lineHeight: "var(--type-body-line)",
        color: "var(--signal)",
        margin: "0",
      },
      text: String(claim),
    });

    const sourceEl = source
      ? el("div", {
          class: "mono muted",
          style: { marginTop: "var(--space-2)", fontSize: "var(--type-label-size)", wordBreak: "break-word" },
          text: "source · " + String(source),
        })
      : null;

    const noteEl = el("div", { class: "hint", style: { marginTop: "var(--space-2)", minHeight: "1em" } });

    // Action buttons.
    const verifyBtn = button({ label: "Verify", variant: "secondary" });
    const promoteBtn = button({ label: "Promote", variant: "primary" });
    const detailBtn = button({ label: "Detail", variant: "ghost" });
    const demoteBtn = button({ label: "Demote", variant: "danger" });
    const all = [verifyBtn, promoteBtn, detailBtn, demoteBtn];

    if (id == null) {
      // No id — only the actions that don't need one stay live.
      [verifyBtn, promoteBtn, detailBtn, demoteBtn].forEach((b) => { b.disabled = true; });
      flash(noteEl, "No id on this item — actions unavailable.", "warn");
    } else {
      verifyBtn.addEventListener("click", () => doVerify(id, all, noteEl));
      promoteBtn.addEventListener("click", () => doPromote(id, all, noteEl));
      detailBtn.addEventListener("click", () => showDetail(id));
      demoteBtn.addEventListener("click", () => doDemote(id, all, noteEl));
    }

    const actions = el("div", {
      class: "row",
      style: { gap: "var(--space-2)", marginTop: "var(--space-3)", flexWrap: "wrap" },
    }, all);

    const body = [];
    if (pillRow) body.push(pillRow);
    body.push(claimEl);
    if (sourceEl) body.push(sourceEl);
    body.push(actions);
    body.push(noteEl);

    return card(body);
  }

  // ---- list rendering ----------------------------------------------------
  function render() {
    if (loading) {
      listEl.replaceChildren(card([
        el("div", { class: "row", style: { gap: "var(--space-2)", alignItems: "center" } }, [
          components.statusDot("live"),
          el("span", { class: "muted", text: query ? "Searching…" : "Loading evidence…" }),
        ]),
      ]));
      return;
    }

    if (loadError) {
      listEl.replaceChildren(card([
        el("h3", { style: { margin: "0 0 var(--space-2)", color: "var(--signal)" }, text: "Couldn't load evidence" }),
        el("p", { class: "muted", style: { margin: "0 0 var(--space-3)" }, text: loadError }),
        el("div", { class: "row", style: { gap: "var(--space-2)" } }, [
          button({ label: "Retry", variant: "secondary", onClick: () => load() }),
        ]),
      ]));
      return;
    }

    if (!items.length) {
      listEl.replaceChildren(emptyState({
        title: query ? "No matches" : "No evidence yet",
        body: query
          ? "Nothing matched “" + query + "”. Try a different query or clear the search."
          : "The evidence ledger is empty. Verified claims and their sources will appear here.",
        action: query
          ? button({ label: "Clear search", variant: "secondary", onClick: () => { query = ""; searchInput.value = ""; load(); } })
          : button({ label: "Refresh", variant: "secondary", onClick: () => load() }),
      }));
      return;
    }

    listEl.replaceChildren(...items.map(renderItem));
  }

  // ---- data loaders ------------------------------------------------------
  function extractItems(data) {
    if (Array.isArray(data)) return data;
    if (data && typeof data === "object") {
      for (const k of ["evidence", "items", "results", "data", "claims", "entries"]) {
        if (Array.isArray(data[k])) return data[k];
      }
    }
    return [];
  }

  async function load() {
    const my = ++token;
    loading = true;
    loadError = null;
    render();
    const q = query.trim();
    const path = q
      ? "/v1/cockpit/evidence/search?q=" + encodeURIComponent(q)
      : "/v1/cockpit/evidence";
    try {
      if (!api.getToken()) {
        if (my !== token) return;
        loading = false;
        loadError = "Not paired — pair this cockpit from the header first.";
        render();
        return;
      }
      const data = await api.getJSON(path);
      if (my !== token) return;
      items = extractItems(data);
      loading = false;
      render();
    } catch (e) {
      if (my !== token) return;
      loading = false;
      loadError = friendly(e);
      render();
    }
  }

  function runSearch() {
    query = (searchInput.value || "").trim();
    load();
  }

  // ---- lifecycle ---------------------------------------------------------
  // Reload on token change while the view is visible.
  let visible = false;
  ctx.onTokenChange(() => { if (visible) load(); });

  return {
    onShow() {
      visible = true;
      // Always refresh on show; first show also kicks the initial load.
      load();
      started = true;
    },
    onHide() {
      visible = false;
      // Cancel any in-flight render by bumping the token so late responses no-op.
      token++;
    },
  };
}
