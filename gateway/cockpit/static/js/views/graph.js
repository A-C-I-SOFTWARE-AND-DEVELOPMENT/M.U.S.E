// muse cockpit — Graph view (GraphRAG).
//
// A query box drives GET /v1/cockpit/graph/query?q=… (and falls back to
// /v1/cockpit/graph/related for a focused node). Returned nodes/edges render as
// a clean typed list grouped by type — value hierarchy, matte ring, no heavy
// canvas. A Rebuild button POSTs /v1/cockpit/graph/build behind a confirm().
//
// Renders exclusively through ctx.components + documented cockpit.css classes,
// and talks to the gateway only through ctx.api. Self-contained.

export async function mount(container, ctx) {
  const { api, components } = ctx;
  const { el, card, pill, button, sectionHeader, emptyState } = components;

  // ---- view state --------------------------------------------------------
  let lastQuery = "";
  let busy = false;

  // ---- shells we mutate as results arrive --------------------------------
  const input = el("input", {
    class: "field grow",
    type: "search",
    placeholder: "Ask the knowledge graph… (e.g. \"model routing\", \"ledger rollback\")",
    "aria-label": "Graph query",
    on: {
      keydown: (e) => { if (e.key === "Enter") { e.preventDefault(); runQuery(input.value); } },
    },
  });

  const searchBtn = button({ label: "Query", variant: "primary", onClick: () => runQuery(input.value) });
  const rebuildBtn = button({ label: "Rebuild graph", variant: "secondary", onClick: rebuild, title: "Re-index the GraphRAG knowledge graph (owner confirm)" });

  const results = el("div", { class: "graph-results" });

  // Initial help / empty state.
  showHelp();

  const queryRow = el("div", { class: "row", style: { gap: "var(--space-2)", alignItems: "stretch" } }, [
    input,
    searchBtn,
  ]);

  const header = sectionHeader({
    eyebrow: "GraphRAG",
    title: "Knowledge graph",
    trailing: rebuildBtn,
  });

  container.replaceChildren(
    el("div", { class: "view-stack", style: { display: "flex", flexDirection: "column", gap: "var(--space-4)" } }, [
      header,
      queryRow,
      results,
    ])
  );

  // ---- rendering states --------------------------------------------------
  function showHelp() {
    results.replaceChildren(
      emptyState({
        title: "Query the knowledge graph",
        body: "Search the GraphRAG index over repo code, docs, the Research Vault, Memory Tree, and ledgers. Results group into typed nodes and the edges that connect them.",
      })
    );
  }

  function showLoading(label) {
    results.replaceChildren(
      card([
        el("div", { class: "row", style: { alignItems: "center", gap: "var(--space-2)" } }, [
          components.statusDot("live"),
          el("span", { class: "muted", text: label || "Querying the graph…" }),
        ]),
      ])
    );
  }

  function showError(title, detail) {
    results.replaceChildren(
      card([
        sectionHeader({ eyebrow: "Error", title }),
        el("p", { class: "hint", text: detail || "The graph could not be reached. Check the gateway and your pairing, then try again." }),
      ])
    );
  }

  function showEmpty(q) {
    results.replaceChildren(
      emptyState({
        title: "No matches",
        body: q ? ("Nothing in the graph matched “" + q + "”. Try a broader term, or rebuild the index if it looks stale.") : "No nodes returned.",
      })
    );
  }

  // Normalize the various shapes the gateway might return into {nodes, edges}.
  function normalize(data) {
    const d = data || {};
    let nodes = d.nodes || d.results || d.matches || (Array.isArray(d) ? d : []) || [];
    let edges = d.edges || d.relations || d.links || [];
    if (!Array.isArray(nodes)) nodes = [];
    if (!Array.isArray(edges)) edges = [];
    return { nodes, edges };
  }

  function nodeId(n) {
    return n && (n.id != null ? n.id : (n.node_id != null ? n.node_id : (n.key != null ? n.key : (n.name != null ? n.name : ""))));
  }
  function nodeType(n) {
    return (n && (n.type || n.kind || n.category || n.label_type)) || "node";
  }
  function nodeTitle(n) {
    if (!n) return "(unnamed)";
    return String(n.title || n.name || n.label || nodeId(n) || "(unnamed)");
  }
  function nodeBody(n) {
    if (!n) return "";
    return String(n.summary || n.snippet || n.text || n.description || n.content || "");
  }
  function nodePath(n) {
    return n && (n.path || n.source || n.file || n.uri || "");
  }
  function nodeScore(n) {
    const s = n && (n.score != null ? n.score : n.relevance);
    return typeof s === "number" ? s : null;
  }

  function renderResults(q, data) {
    const { nodes, edges } = normalize(data);
    if (!nodes.length && !edges.length) { showEmpty(q); return; }

    const kids = [];

    // Summary line.
    const summary = sectionHeader({
      eyebrow: "Results",
      title: nodes.length + (nodes.length === 1 ? " node" : " nodes"),
      trailing: edges.length ? pill(edges.length + (edges.length === 1 ? " edge" : " edges"), "neutral") : null,
    });
    kids.push(summary);

    // Group nodes by type.
    const groups = new Map();
    for (const n of nodes) {
      const t = String(nodeType(n));
      if (!groups.has(t)) groups.set(t, []);
      groups.get(t).push(n);
    }

    for (const [type, list] of groups) {
      const groupKids = [
        el("div", { class: "row", style: { alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" } }, [
          el("span", { class: "eyebrow", text: type }),
          pill(String(list.length), "neutral"),
        ]),
      ];
      for (const n of list) groupKids.push(renderNodeCard(n));
      kids.push(el("div", { class: "graph-group" }, groupKids));
    }

    // Edges, if any, as a compact typed list.
    if (edges.length) {
      const nameById = new Map();
      for (const n of nodes) nameById.set(String(nodeId(n)), nodeTitle(n));
      const edgeRows = edges.map((e) => {
        const from = String(e.from != null ? e.from : (e.source != null ? e.source : (e.src != null ? e.src : "")));
        const to = String(e.to != null ? e.to : (e.target != null ? e.target : (e.dst != null ? e.dst : "")));
        const rel = String(e.rel || e.relation || e.type || e.label || "related");
        const fromName = nameById.get(from) || from || "?";
        const toName = nameById.get(to) || to || "?";
        return el("div", { class: "row", style: { gap: "var(--space-2)", alignItems: "center", padding: "var(--space-1) 0" } }, [
          el("span", { class: "mono", text: fromName }),
          pill(rel, "accent"),
          el("span", { class: "mono", text: toName }),
        ]);
      });
      kids.push(el("div", { class: "graph-group" }, [
        el("div", { class: "eyebrow", text: "Edges", style: { marginBottom: "var(--space-2)" } }),
        card(edgeRows),
      ]));
    }

    results.replaceChildren(el("div", { style: { display: "flex", flexDirection: "column", gap: "var(--space-4)" } }, kids));
  }

  function renderNodeCard(n) {
    const head = [el("span", { class: "section-title", text: nodeTitle(n) })];
    const score = nodeScore(n);
    const trailing = score != null ? pill(score.toFixed(2), "accent") : null;

    const body = nodeBody(n);
    const path = nodePath(n);
    const id = nodeId(n);

    const inner = [
      el("div", { class: "row", style: { justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-2)" } }, [
        el("div", {}, head),
        trailing,
      ]),
    ];
    if (body) inner.push(el("p", { class: "muted", style: { margin: "var(--space-2) 0 0" }, text: clip(body, 360) }));
    if (path) inner.push(el("p", { class: "hint mono", style: { margin: "var(--space-2) 0 0" }, text: String(path) }));

    // A "related" action to pivot the graph around this node.
    if (id) {
      inner.push(
        el("div", { class: "row", style: { marginTop: "var(--space-3)", gap: "var(--space-2)" } }, [
          button({ label: "Related", variant: "ghost", onClick: () => runRelated(id, nodeTitle(n)) }),
        ])
      );
    }
    return card(inner, { interactive: true });
  }

  function clip(s, max) {
    s = String(s);
    return s.length > max ? s.slice(0, max - 1).trimEnd() + "…" : s;
  }

  // ---- network actions ---------------------------------------------------
  async function runQuery(q) {
    q = (q || "").trim();
    if (!q) { input.focus(); return; }
    if (busy) return;
    if (!api.getToken()) { showError("Not paired", "Pair this cockpit from the header before querying the graph."); return; }
    lastQuery = q;
    input.value = q;
    busy = true; searchBtn.disabled = true;
    showLoading("Querying the graph for “" + q + "”…");
    try {
      const data = await api.getJSON("/v1/cockpit/graph/query?q=" + encodeURIComponent(q));
      renderResults(q, data);
    } catch (e) {
      if (e && e.status === 401) showError("Not authorized", "Your pairing was rejected (401). Re-pair from the header.");
      else showError("Query failed", "GET /v1/cockpit/graph/query returned " + (e && e.status ? e.status : "an error") + ".");
    } finally {
      busy = false; searchBtn.disabled = false;
    }
  }

  async function runRelated(id, title) {
    if (busy) return;
    if (!api.getToken()) { showError("Not paired", "Pair this cockpit from the header before querying the graph."); return; }
    busy = true;
    showLoading("Finding nodes related to “" + (title || id) + "”…");
    try {
      const data = await api.getJSON("/v1/cockpit/graph/related?id=" + encodeURIComponent(String(id)));
      renderResults(title || String(id), data);
    } catch (e) {
      showError("Related lookup failed", "GET /v1/cockpit/graph/related returned " + (e && e.status ? e.status : "an error") + ".");
    } finally {
      busy = false;
    }
  }

  async function rebuild() {
    if (busy) return;
    if (!api.getToken()) { showError("Not paired", "Pair this cockpit from the header before rebuilding the graph."); return; }
    if (!window.confirm("Rebuild the GraphRAG knowledge graph?\n\nThis re-indexes repo code, docs, the Research Vault, Memory Tree, and ledgers. It can take a while.")) return;
    busy = true; rebuildBtn.disabled = true;
    const prevLabel = rebuildBtn.textContent;
    rebuildBtn.textContent = "Rebuilding…";
    showLoading("Rebuilding the knowledge graph…");
    try {
      const out = await api.postJSON("/v1/cockpit/graph/build", {});
      const count = out && (out.nodes != null ? out.nodes : out.count);
      results.replaceChildren(
        card([
          sectionHeader({ eyebrow: "Rebuild", title: "Graph rebuilt", trailing: pill("OK", "ok") }),
          el("p", { class: "muted", style: { marginTop: "var(--space-2)" }, text: count != null ? ("Indexed " + count + " nodes. Run a query to explore.") : "The index was rebuilt. Run a query to explore." }),
          el("div", { class: "row", style: { marginTop: "var(--space-3)" } }, [
            button({ label: "Back to search", variant: "ghost", onClick: () => { lastQuery ? runQuery(lastQuery) : showHelp(); } }),
          ]),
        ])
      );
    } catch (e) {
      showError("Rebuild failed", "POST /v1/cockpit/graph/build returned " + (e && e.status ? e.status : "an error") + ".");
    } finally {
      busy = false; rebuildBtn.disabled = false; rebuildBtn.textContent = prevLabel;
    }
  }

  // Reconnect-ish: if the token changes while mounted and we have a prior
  // query, refresh it; otherwise show help.
  ctx.onTokenChange(() => {
    if (lastQuery && api.getToken()) runQuery(lastQuery);
    else if (!api.getToken()) showHelp();
  });

  return {
    onShow() {
      // Focus the query box on entry for fast keyboard use.
      try { input.focus(); } catch (e) { /* not focusable yet */ }
    },
  };
}
