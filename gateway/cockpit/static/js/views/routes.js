// muse cockpit — "Routes" view (model routing per task class).
//
// GET /v1/cockpit/model-routes → { routes: [{ task_class, chosen,
//   fallback_chain, owner_override, route_tier, why }] }. Each route renders as
// a .card: task class header, chosen model, fallback chain, the "why", and a
// <select> of candidate models + an Apply button that POSTs an override to
// /v1/cockpit/model-routes/override { task_class, model }. No owner phrase.
//
// Rendered exclusively through ctx.components + cockpit.css classes. Loading,
// empty, and error states are all handled gracefully — nothing throws uncaught.

export async function mount(container, ctx) {
  const { api, components } = ctx;
  const { el, card, pill, button, sectionHeader, emptyState } = components;

  // The single mount-root we replace on every (re)render.
  const root = el("div", { class: "view-routes" });
  container.replaceChildren(root);

  let loaded = false; // mount() loads once; onShow() refreshes thereafter.

  // ---- candidate-model derivation ---------------------------------------
  // Build a de-duped, ordered candidate list for a route's <select>. We prefer
  // the explicit chosen model first, then the fallback chain, then any owner
  // override — covering whatever the gateway happens to send back.
  function candidatesFor(route) {
    const out = [];
    const seen = new Set();
    const add = (m) => {
      if (!m) return;
      const s = String(m);
      if (seen.has(s)) return;
      seen.add(s);
      out.push(s);
    };
    add(route.chosen);
    const chain = Array.isArray(route.fallback_chain) ? route.fallback_chain : [];
    for (const m of chain) add(m);
    add(route.owner_override);
    return out;
  }

  // ---- one route card ----------------------------------------------------
  function routeCard(route) {
    const taskClass = route.task_class == null ? "—" : String(route.task_class);
    const chosen = route.chosen == null ? "" : String(route.chosen);
    const chain = Array.isArray(route.fallback_chain) ? route.fallback_chain : [];
    const candidates = candidatesFor(route);

    // Header: task class eyebrow + tier/override chips on the right.
    const chips = [];
    if (route.route_tier != null && String(route.route_tier) !== "") {
      chips.push(pill(String(route.route_tier), "accent"));
    }
    if (route.owner_override != null && String(route.owner_override) !== "") {
      chips.push(pill("OVERRIDE", "selected"));
    }
    const header = sectionHeader({
      eyebrow: "TASK CLASS",
      title: taskClass,
      trailing: chips.length ? el("div", { class: "row" }, chips) : null,
    });

    const lineStyle = {
      display: "flex",
      gap: "var(--space-3)",
      alignItems: "baseline",
      marginTop: "var(--space-3)",
    };
    const labelStyle = { minWidth: "72px", flex: "0 0 auto" };

    // Chosen model — the active routing decision.
    const chosenRow = el("div", { class: "row", style: lineStyle }, [
      el("span", { class: "muted", text: "Chosen", style: labelStyle }),
      el("span", { class: "mono", text: chosen || "—" }),
    ]);

    // Fallback chain.
    const chainRow = el("div", { class: "row", style: lineStyle }, [
      el("span", { class: "muted", text: "Fallback", style: labelStyle }),
      chain.length
        ? el("span", { class: "mono", text: chain.map(String).join("  →  ") })
        : el("span", { class: "muted", text: "none" }),
    ]);

    // The "why" rationale, when present.
    const whyText = route.why == null ? "" : String(route.why);
    const whyRow = whyText
      ? el("p", { class: "hint", text: whyText, style: { marginTop: "var(--space-3)" } })
      : null;

    // ---- override control: <select> of candidates + Apply ----------------
    const select = el("select", { class: "field" });
    if (candidates.length === 0) {
      select.appendChild(el("option", { value: "", text: "no candidates" }));
      select.disabled = true;
    } else {
      for (const m of candidates) {
        const opt = el("option", { value: m, text: m });
        if (m === chosen) opt.selected = true;
        select.appendChild(opt);
      }
    }

    // Per-card inline status line for apply feedback (no global throw).
    const status = el("span", { class: "hint", style: { marginTop: "0" } });
    const setStatus = (text, state) => {
      status.textContent = text || "";
      status.style.color =
        state === "ok" ? "var(--ok)" : state === "danger" ? "var(--danger)" : "var(--signal-mute)";
    };

    let applyBtn;
    async function apply() {
      const model = select.value;
      if (!model) return;
      applyBtn.disabled = true;
      select.disabled = true;
      setStatus("Applying…", "neutral");
      try {
        await api.postJSON("/v1/cockpit/model-routes/override", {
          task_class: route.task_class,
          model,
        });
        setStatus("Override applied", "ok");
        // Refresh from the gateway so chips/chosen reflect the new state.
        await load();
      } catch (err) {
        const msg =
          (err && (err.body?.detail || err.body?.message)) ||
          (err && err.message) ||
          "Apply failed";
        setStatus(String(msg), "danger");
        applyBtn.disabled = false;
        select.disabled = candidates.length === 0;
      }
    }

    applyBtn = button({
      label: "Apply",
      variant: "secondary",
      onClick: apply,
      disabled: candidates.length === 0,
      title: "Override the model for this task class",
    });

    const controls = el("div", { class: "row", style: { marginTop: "var(--space-4)" } }, [
      el("div", { class: "grow" }, [select]),
      applyBtn,
    ]);

    const kids = [header, chosenRow, chainRow];
    if (whyRow) kids.push(whyRow);
    kids.push(controls, status);
    return card(kids);
  }

  // ---- render states -----------------------------------------------------
  function renderLoading() {
    root.replaceChildren(
      el("div", { class: "view-routes" }, [
        sectionHeader({ eyebrow: "ORCHESTRATION", title: "Model Routes" }),
        card([el("p", { class: "muted", text: "Loading routes…" })]),
      ]),
    );
  }

  function renderError(err) {
    const unpaired = err && err.status === 401;
    const status = err && err.status ? ` (HTTP ${err.status})` : "";
    root.replaceChildren(
      el("div", { class: "view-routes" }, [
        sectionHeader({ eyebrow: "ORCHESTRATION", title: "Model Routes" }),
        card([
          el("h3", {
            text: unpaired ? "Not paired" : "Couldn’t load routes",
            style: { margin: "0 0 var(--space-2)", fontSize: "var(--type-title-size)" },
          }),
          el("p", {
            class: "muted",
            text: unpaired
              ? "Pair this cockpit from the header to view model routing."
              : "The gateway didn’t return model routes" + status + ". Try again.",
          }),
          el("div", { class: "row", style: { marginTop: "var(--space-3)" } }, [
            button({ label: "Retry", variant: "secondary", onClick: load }),
          ]),
        ]),
      ]),
    );
  }

  function renderEmpty() {
    root.replaceChildren(
      el("div", { class: "view-routes" }, [
        sectionHeader({ eyebrow: "ORCHESTRATION", title: "Model Routes" }),
        emptyState({
          title: "No routes configured",
          body: "Model routing decisions will appear here once the orchestrator registers task classes.",
          action: button({ label: "Refresh", variant: "secondary", onClick: load }),
        }),
      ]),
    );
  }

  function renderRoutes(routes) {
    const header = sectionHeader({
      eyebrow: "ORCHESTRATION",
      title: "Model Routes",
      trailing: button({ label: "Refresh", variant: "ghost", onClick: load }),
    });
    const cards = routes.map(routeCard);
    root.replaceChildren(
      el("div", { class: "view-routes" }, [
        header,
        el(
          "div",
          {
            style: {
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-4)",
              marginTop: "var(--space-4)",
            },
          },
          cards,
        ),
      ]),
    );
  }

  // ---- data load ---------------------------------------------------------
  async function load() {
    if (!api.getToken()) {
      renderError({ status: 401 });
      return;
    }
    renderLoading();
    try {
      const data = await api.getJSON("/v1/cockpit/model-routes");
      const routes = Array.isArray(data && data.routes) ? data.routes : [];
      if (routes.length === 0) renderEmpty();
      else renderRoutes(routes);
    } catch (err) {
      renderError(err);
    }
  }

  // ---- lifecycle ---------------------------------------------------------
  // Reload when the token changes (e.g. after pairing) while this view exists.
  ctx.onTokenChange(() => {
    if (loaded) load();
  });

  return {
    async onShow() {
      loaded = true;
      await load();
    },
  };
}
