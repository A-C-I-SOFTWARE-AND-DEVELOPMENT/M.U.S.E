// muse cockpit — Memory view.
//
// The Memory Tree surface. Renders memory entries as cards (text, source/
// citation, confidence, supersession), flags contradictions as their own
// section, surfaces a freshness stat, lists PROPOSED entries with Accept/Reject
// owner-gated decisions, and supports adding / deleting entries. Everything is
// drawn through ctx.components + the cockpit.css classes — white is the hero,
// the spectral ring stays matte, no shadows, value hierarchy only.

export async function mount(container, ctx) {
  const { api, components } = ctx;
  const { el, card, pill, button, sectionHeader, emptyState, statusDot } = components;

  // ---- view-local state ---------------------------------------------------
  let live = true;          // whether the section is currently shown
  let pollTimer = null;     // periodic refresh handle
  let inFlight = false;     // guard overlapping refreshes
  let unsub = null;         // token-change unsubscribe

  // Mounted shell: a single scrollable column we repaint into.
  const root = el("div", { class: "memory-view" });
  container.replaceChildren(root);

  // ---- tiny render helpers ------------------------------------------------
  const txt = (v) => (v == null ? "" : String(v));

  // Normalise the assorted shapes the gateway may return into a flat list.
  function asList(payload) {
    if (Array.isArray(payload)) return payload;
    if (!payload || typeof payload !== "object") return [];
    for (const key of ["entries", "items", "memories", "nodes", "tree", "results", "data"]) {
      if (Array.isArray(payload[key])) return payload[key];
    }
    return [];
  }

  // Confidence → a value-coded pill (no neon; status colors are UI-only).
  function confidencePill(entry) {
    let c = entry.confidence;
    if (c == null) c = entry.score;
    if (c == null) return null;
    let n = Number(c);
    if (!Number.isFinite(n)) return pill(txt(c), "neutral");
    if (n > 1) n = n / 100; // tolerate 0..100 scale
    const pct = Math.round(Math.max(0, Math.min(1, n)) * 100);
    const state = n >= 0.75 ? "ok" : n >= 0.4 ? "warn" : "danger";
    return pill("CONFIDENCE " + pct + "%", state);
  }

  function sourceLine(entry) {
    const src = entry.source || entry.citation || entry.provenance || entry.origin;
    if (!src) return null;
    return el("div", { class: "hint mono", text: "Source: " + txt(typeof src === "object" ? (src.url || src.title || JSON.stringify(src)) : src) });
  }

  function supersessionLine(entry) {
    const sup = entry.supersedes || entry.superseded_by || entry.supersession;
    if (!sup) return null;
    const label = entry.superseded_by
      ? "Superseded by " + txt(entry.superseded_by)
      : "Supersedes " + txt(entry.supersedes || sup);
    return el("div", { class: "row" }, [pill(label, "neutral")]);
  }

  // A single memory entry card (used by tree + flat list).
  function entryCard(entry, { proposed = false, contradiction = false } = {}) {
    const id = entry.id || entry.uid || entry.key || entry.memory_id;
    const text = entry.text || entry.content || entry.fact || entry.statement || entry.value || "(no text)";

    const headPills = [];
    if (proposed) headPills.push(pill("PROPOSED", "accent"));
    if (contradiction) headPills.push(pill("CONTESTED", "danger"));
    if (entry.type || entry.kind) headPills.push(pill(txt(entry.type || entry.kind), "neutral"));
    const conf = confidencePill(entry);
    if (conf) headPills.push(conf);

    const body = [];
    if (headPills.length) body.push(el("div", { class: "row" }, headPills));
    body.push(el("div", { class: "memory-text", text: txt(text) }));
    const sl = sourceLine(entry);
    if (sl) body.push(sl);
    const ss = supersessionLine(entry);
    if (ss) body.push(ss);
    if (id != null) body.push(el("div", { class: "hint mono", text: "id " + txt(id) }));

    // Actions row.
    const actions = [];
    if (proposed && id != null) {
      actions.push(button({
        label: "Accept", variant: "primary",
        onClick: () => decideProposed(id, "accept"),
      }));
      actions.push(button({
        label: "Reject", variant: "ghost",
        onClick: () => decideProposed(id, "reject"),
      }));
    } else if (id != null) {
      actions.push(button({
        label: "Delete", variant: "danger",
        onClick: () => deleteEntry(id),
      }));
    }
    if (actions.length) body.push(el("div", { class: "row dialog-actions" }, actions));

    return card(body);
  }

  // ---- network actions ----------------------------------------------------
  async function decideProposed(id, decision) {
    try {
      await api.ownerPost(
        "/v1/cockpit/memory/tree/" + encodeURIComponent(id) + "/decision",
        { decision },
        (decision === "accept" ? "Accept" : "Reject") + " proposed memory " + id,
      );
      await refresh();
    } catch (e) {
      if (e && e.cancelled) return; // owner cancelled the phrase prompt
      flash("Could not " + decision + " " + id + " (" + (e && e.status ? e.status : "error") + ").", true);
    }
  }

  async function deleteEntry(id) {
    if (!window.confirm("Delete memory entry " + id + "? This cannot be undone.")) return;
    try {
      const r = await api.api("/v1/cockpit/memory/" + encodeURIComponent(id), { method: "DELETE" });
      if (!r.ok) throw Object.assign(new Error("delete"), { status: r.status });
      await refresh();
    } catch (e) {
      flash("Could not delete " + id + " (" + (e && e.status ? e.status : "error") + ").", true);
    }
  }

  async function addMemory(text) {
    const t = (text || "").trim();
    if (!t) return;
    try {
      await api.postJSON("/v1/cockpit/memory", { text: t });
      await refresh();
    } catch (e) {
      flash("Could not add memory (" + (e && e.status ? e.status : "error") + ").", true);
    }
  }

  // ---- transient banner ---------------------------------------------------
  let banner = null;
  function flash(message, isError) {
    if (!banner) return;
    banner.textContent = message;
    banner.className = "banner show" + (isError ? " offline" : "");
    window.clearTimeout(flash._t);
    flash._t = window.setTimeout(() => { if (banner) banner.className = "banner"; }, 4000);
  }

  // ---- the add form (rendered once at the top) ----------------------------
  function buildAddForm() {
    const input = el("input", {
      class: "field grow",
      type: "text",
      placeholder: "Add a memory fact…",
      "aria-label": "New memory text",
    });
    const submit = () => { const v = input.value; input.value = ""; addMemory(v); };
    input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); submit(); } });
    const add = button({ label: "Add", variant: "primary", onClick: submit });
    return el("div", { class: "row" }, [input, add]);
  }

  // ---- the main repaint ---------------------------------------------------
  async function refresh() {
    if (inFlight) return;
    const token = api.getToken();
    if (!token) {
      paintUnpaired();
      return;
    }
    inFlight = true;
    // Fetch every facet independently so one failure doesn't blank the view.
    const [treeR, freshR, contraR, propR] = await Promise.allSettled([
      api.getJSON("/v1/cockpit/memory/tree").catch(() => api.getJSON("/v1/cockpit/memory")),
      api.getJSON("/v1/cockpit/memory/freshness"),
      api.getJSON("/v1/cockpit/memory/contradictions"),
      api.getJSON("/v1/cockpit/memory/tree/proposed"),
    ]);
    inFlight = false;

    // If the tree request hard-failed (auth/transport), show a friendly card.
    if (treeR.status === "rejected") {
      const st = treeR.reason && treeR.reason.status;
      if (st === 401 || st === 403) { paintUnpaired(); return; }
      paintError(st);
      return;
    }

    paint({
      tree: asList(treeR.value),
      freshness: freshR.status === "fulfilled" ? freshR.value : null,
      contradictions: contraR.status === "fulfilled" ? asList(contraR.value) : [],
      proposed: propR.status === "fulfilled" ? asList(propR.value) : [],
    });
  }

  function freshnessTrailing(freshness) {
    if (!freshness || typeof freshness !== "object") return null;
    let val = freshness.freshness != null ? freshness.freshness
      : freshness.score != null ? freshness.score
        : freshness.fresh != null ? freshness.fresh : null;
    let label;
    let state = "ok";
    if (val == null && freshness.stale != null) {
      label = txt(freshness.stale) + " stale";
      state = Number(freshness.stale) > 0 ? "warn" : "ok";
    } else if (val == null) {
      return null;
    } else {
      let n = Number(val);
      if (Number.isFinite(n)) {
        if (n > 1) n = n / 100;
        const pct = Math.round(Math.max(0, Math.min(1, n)) * 100);
        label = "FRESH " + pct + "%";
        state = n >= 0.75 ? "ok" : n >= 0.4 ? "warn" : "danger";
      } else {
        label = "FRESH " + txt(val);
      }
    }
    return el("div", { class: "row" }, [statusDot(state), pill(label, state)]);
  }

  // ---- full paints --------------------------------------------------------
  function shell(children) {
    banner = el("div", { class: "banner" });
    root.replaceChildren(banner, ...children);
  }

  function paintUnpaired() {
    shell([
      sectionHeader({ eyebrow: "Cognition", title: "Memory Tree" }),
      card([
        emptyState({
          title: "Not paired yet",
          body: "Pair this cockpit from the header to inspect and curate the Memory Tree.",
        }),
      ]),
    ]);
  }

  function paintError(status) {
    shell([
      sectionHeader({ eyebrow: "Cognition", title: "Memory Tree" }),
      card([
        emptyState({
          title: "Memory unavailable",
          body: "The memory service did not respond" + (status ? " (HTTP " + status + ")" : "") + ". It may be offline — this view will retry.",
          action: button({ label: "Retry", variant: "secondary", onClick: () => refresh() }),
        }),
      ]),
    ]);
  }

  function paint({ tree, freshness, contradictions, proposed }) {
    const sections = [];

    // Header with freshness stat pinned to the right.
    sections.push(sectionHeader({
      eyebrow: "Cognition",
      title: "Memory Tree",
      trailing: freshnessTrailing(freshness),
    }));

    // Add form.
    sections.push(card([buildAddForm()]));

    // Proposed (owner-gated Accept/Reject).
    if (proposed && proposed.length) {
      sections.push(sectionHeader({ eyebrow: "Awaiting review", title: "Proposed (" + proposed.length + ")" }));
      for (const p of proposed) sections.push(entryCard(p, { proposed: true }));
    }

    // Contradictions / contested entries.
    if (contradictions && contradictions.length) {
      sections.push(sectionHeader({ eyebrow: "Conflicts", title: "Contradictions (" + contradictions.length + ")" }));
      for (const c of contradictions) {
        // A contradiction record may bundle a pair, or be an entry itself.
        if (c && (Array.isArray(c.entries) || Array.isArray(c.pair))) {
          const pair = c.entries || c.pair;
          const body = [el("div", { class: "row" }, [pill("CONTESTED", "danger")])];
          if (c.reason || c.note) body.push(el("div", { class: "hint", text: txt(c.reason || c.note) }));
          for (const m of pair) body.push(entryCard(m, { contradiction: true }));
          sections.push(card(body));
        } else {
          sections.push(entryCard(c, { contradiction: true }));
        }
      }
    }

    // The tree / flat list of entries.
    sections.push(sectionHeader({ eyebrow: "Knowledge", title: "Entries (" + tree.length + ")" }));
    if (!tree.length) {
      sections.push(card([
        emptyState({
          title: "No memories yet",
          body: "muse hasn't recorded any durable facts. Add one above to seed the Memory Tree.",
        }),
      ]));
    } else {
      for (const entry of tree) sections.push(entryCard(entry));
    }

    shell(sections);
  }

  // ---- polling lifecycle --------------------------------------------------
  function startPolling() {
    stopPolling();
    if (!api.getToken()) { paintUnpaired(); return; }
    refresh();
    pollTimer = window.setInterval(() => { if (live) refresh(); }, 8000);
  }
  function stopPolling() {
    if (pollTimer != null) { window.clearInterval(pollTimer); pollTimer = null; }
  }

  // Reconnect/repaint whenever the token changes (pair/unpair).
  unsub = ctx.onTokenChange ? ctx.onTokenChange(() => { if (live) startPolling(); }) : null;

  // Initial loading state until first refresh lands.
  shell([
    sectionHeader({ eyebrow: "Cognition", title: "Memory Tree" }),
    card([emptyState({ glyph: true, title: "Loading memory…", body: "Fetching the Memory Tree from the gateway." })]),
  ]);

  return {
    onShow() {
      live = true;
      startPolling();
    },
    onHide() {
      live = false;
      stopPolling();
      if (typeof unsub === "function") { /* keep subscription; just stop polling */ }
    },
  };
}
