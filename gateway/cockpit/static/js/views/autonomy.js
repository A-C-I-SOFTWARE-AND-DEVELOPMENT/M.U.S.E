// muse cockpit — Autonomy view.
//
// Shows the current autonomy posture and lets the owner change it.
//   GET  /v1/cockpit/autonomy
//     → { level, display_name, set_by, workspace_root,
//         capabilities: { auto_approved, requires_approval, always_deny } }
//   Apply:
//     - RAISING the level is owner-gated → ctx.api.ownerPost("/v1/cockpit/autonomy",
//         { level, workspace_path? })
//     - LOWERING the level is a plain postJSON("/v1/cockpit/autonomy", { level })
//   Revoke (danger): plain postJSON("/v1/cockpit/autonomy", { revoke: true }).
//
// workspace_path input is only shown for level "owner_high_autonomy_coding".
// Renders exclusively through ctx.components + cockpit.css classes. No raw
// fetch, no hand-rolled cards. Never throws uncaught — failures show a friendly
// card. Re-fetches on token change and on onShow.

// The ordered ladder of autonomy levels. Index = relative rank; raising means
// moving to a higher index (owner-gated), lowering = lower index (plain post).
const LEVELS = [
  { value: "read_only", label: "Read Only" },
  { value: "assisted", label: "Assisted" },
  { value: "autonomous", label: "Autonomous" },
  { value: "yolo", label: "YOLO" },
  { value: "owner_high_autonomy_coding", label: "Owner High-Autonomy Coding" },
];

const WORKSPACE_LEVEL = "owner_high_autonomy_coding";

function rankOf(value) {
  const i = LEVELS.findIndex((l) => l.value === value);
  return i < 0 ? -1 : i;
}

function labelOf(value) {
  const l = LEVELS.find((x) => x.value === value);
  return l ? l.label : (value == null ? "—" : String(value));
}

export async function mount(container, ctx) {
  const { api, components: c } = ctx;
  const { el } = c;

  // Current server-side state (last successful GET). Null until first load.
  let state = null;
  // Local selection in the level <select>, may differ from state.level.
  let selected = null;
  let workspacePath = "";
  let busy = false;
  let unsub = null;

  // ---- network ----------------------------------------------------------
  async function load() {
    renderLoading();
    try {
      const data = await api.getJSON("/v1/cockpit/autonomy");
      state = data || {};
      selected = state.level || (LEVELS[0] && LEVELS[0].value);
      workspacePath = state.workspace_root || "";
      render();
    } catch (e) {
      if (e && (e.status === 401 || e.status === 403)) renderUnpaired();
      else renderError(e);
    }
  }

  async function applyLevel() {
    if (busy || !selected) return;
    const current = state ? state.level : null;
    if (selected === current && !needsWorkspaceChange()) {
      flash("Already at " + labelOf(selected) + ".", "neutral");
      return;
    }
    const raising = rankOf(selected) > rankOf(current);
    busy = true;
    render();
    try {
      if (raising) {
        const body = { level: selected };
        if (selected === WORKSPACE_LEVEL && workspacePath.trim()) {
          body.workspace_path = workspacePath.trim();
        }
        await api.ownerPost("/v1/cockpit/autonomy", body, "Raise autonomy to " + labelOf(selected));
      } else {
        // Lowering (or same-rank, e.g. workspace tweak) is not owner-gated.
        const body = { level: selected };
        if (selected === WORKSPACE_LEVEL && workspacePath.trim()) {
          body.workspace_path = workspacePath.trim();
        }
        await api.postJSON("/v1/cockpit/autonomy", body);
      }
      flash("Autonomy set to " + labelOf(selected) + ".", "ok");
      await load();
    } catch (e) {
      busy = false;
      if (e && e.cancelled) { flash("Cancelled — no change made.", "warn"); render(); return; }
      flash(friendlyError(e), "danger");
      render();
    }
  }

  async function revoke() {
    if (busy) return;
    busy = true;
    render();
    try {
      await api.postJSON("/v1/cockpit/autonomy", { revoke: true });
      flash("Autonomy revoked — reset to the safe default.", "ok");
      await load();
    } catch (e) {
      busy = false;
      flash(friendlyError(e), "danger");
      render();
    }
  }

  function needsWorkspaceChange() {
    if (selected !== WORKSPACE_LEVEL) return false;
    return workspacePath.trim() !== (state && state.workspace_root ? state.workspace_root : "");
  }

  function friendlyError(e) {
    if (!e) return "Something went wrong.";
    if (e.status === 401 || e.status === 403) return "Not authorized — pairing or owner phrase required.";
    if (e.body && e.body.detail) return String(e.body.detail);
    if (e.body && e.body.error) return String(e.body.error);
    if (e.status) return "Request failed (" + e.status + ").";
    return "Network error — could not reach the gateway.";
  }

  // ---- transient feedback banner ---------------------------------------
  let flashMsg = null;
  let flashState = "neutral";
  let flashTimer = null;
  function flash(msg, st) {
    flashMsg = msg;
    flashState = st || "neutral";
    if (flashTimer) clearTimeout(flashTimer);
    flashTimer = setTimeout(() => { flashMsg = null; if (state) render(); }, 6000);
  }

  // ---- rendering --------------------------------------------------------
  function header(trailing) {
    return c.sectionHeader({ eyebrow: "Governance", title: "Autonomy", trailing });
  }

  function renderLoading() {
    container.replaceChildren(
      header(),
      c.card([el("p", { class: "muted", text: "Loading autonomy posture…" })]),
    );
  }

  function renderUnpaired() {
    container.replaceChildren(
      header(),
      c.emptyState({
        title: "Pairing required",
        body: "Pair this cockpit from the header to view and change the autonomy posture.",
      }),
    );
  }

  function renderError(e) {
    container.replaceChildren(
      header(c.button({ label: "Retry", variant: "secondary", onClick: load })),
      c.card([
        el("h3", { class: "section-title", text: "Couldn't load autonomy" }),
        el("p", { class: "muted", text: friendlyError(e) }),
      ]),
    );
  }

  function capGroup(eyebrow, items, state) {
    const list = Array.isArray(items) ? items : [];
    let body;
    if (list.length === 0) {
      body = el("p", { class: "muted", text: "None." });
    } else {
      body = el("div", { class: "row", style: { flexWrap: "wrap", gap: "var(--space-2)" } },
        list.map((cap) => c.pill(String(cap), state)));
    }
    return c.card([
      c.sectionHeader({ eyebrow }),
      body,
    ]);
  }

  function statusLine() {
    if (!state) return null;
    const rows = [];
    rows.push(el("div", { class: "row", style: { alignItems: "center", gap: "var(--space-2)" } }, [
      c.statusDot("live"),
      el("span", { class: "section-title", text: state.display_name || labelOf(state.level) }),
      c.pill(state.level || "—", "accent"),
    ]));
    const meta = [];
    if (state.set_by) meta.push("Set by " + state.set_by);
    if (state.workspace_root) meta.push("Workspace: " + state.workspace_root);
    if (meta.length) {
      rows.push(el("p", { class: "muted mono", style: { marginTop: "var(--space-2)" }, text: meta.join("  ·  ") }));
    }
    return c.card(rows);
  }

  function controls() {
    // Level <select> styled as a .field.
    const options = LEVELS.map((l) =>
      el("option", { value: l.value, selected: l.value === selected ? "selected" : null }, l.label));
    const sel = el("select", {
      class: "field",
      disabled: busy ? "disabled" : null,
      on: {
        change: (ev) => {
          selected = ev.target.value;
          render();
        },
      },
    }, options);

    const kids = [
      c.sectionHeader({ eyebrow: "Change posture", title: "Set level" }),
      el("label", { class: "hint", text: "Autonomy level" }),
      sel,
    ];

    // Workspace path — only for owner_high_autonomy_coding.
    if (selected === WORKSPACE_LEVEL) {
      const input = el("input", {
        class: "field",
        type: "text",
        placeholder: "/path/to/workspace",
        value: workspacePath,
        disabled: busy ? "disabled" : null,
        on: { input: (ev) => { workspacePath = ev.target.value; } },
      });
      kids.push(el("label", { class: "hint", style: { marginTop: "var(--space-3)" }, text: "Workspace path" }));
      kids.push(input);
    }

    // Raising-vs-lowering hint.
    const curRank = rankOf(state ? state.level : null);
    const selRank = rankOf(selected);
    if (selRank > curRank) {
      kids.push(el("p", {
        class: "hint",
        style: { marginTop: "var(--space-2)" },
        text: "Raising autonomy is owner-gated — you'll be asked for the owner phrase.",
      }));
    }

    const apply = c.button({
      label: busy ? "Working…" : "Apply",
      variant: "primary",
      disabled: busy,
      onClick: applyLevel,
    });
    const revokeBtn = c.button({
      label: "Revoke",
      variant: "danger",
      disabled: busy,
      title: "Reset autonomy to the safe default",
      onClick: revoke,
    });
    kids.push(el("div", {
      class: "row",
      style: { marginTop: "var(--space-4)", gap: "var(--space-2)" },
    }, [apply, revokeBtn]));

    return c.card(kids);
  }

  function flashBanner() {
    if (!flashMsg) return null;
    return c.card([
      el("div", { class: "row", style: { alignItems: "center", gap: "var(--space-2)" } }, [
        c.statusDot(flashState === "danger" ? "danger" : flashState === "warn" ? "warn" : flashState === "ok" ? "ok" : "off"),
        el("span", { text: flashMsg }),
      ]),
    ]);
  }

  function render() {
    if (!state) return; // loading/error/unpaired states render themselves.
    const caps = state.capabilities || {};
    const children = [
      header(c.button({ label: "Refresh", variant: "ghost", disabled: busy, onClick: load })),
    ];
    const fb = flashBanner();
    if (fb) children.push(fb);
    children.push(statusLine());
    children.push(controls());
    children.push(capGroup("Auto approved", caps.auto_approved, "ok"));
    children.push(capGroup("Requires approval", caps.requires_approval, "warn"));
    children.push(capGroup("Always denied", caps.always_deny, "danger"));
    container.replaceChildren(...children.filter(Boolean));
  }

  // ---- lifecycle --------------------------------------------------------
  // Initial paint while we have no data.
  renderLoading();

  return {
    onShow() {
      // (Re)load whenever the view becomes visible. Gate on having a token.
      if (api.getToken()) load();
      else renderUnpaired();
      // Reconnect/reload on token change while visible.
      if (!unsub && typeof ctx.onTokenChange === "function") {
        unsub = ctx.onTokenChange(() => {
          if (api.getToken()) load();
          else renderUnpaired();
        });
      }
    },
    onHide() {
      if (flashTimer) { clearTimeout(flashTimer); flashTimer = null; }
      if (unsub) { try { unsub(); } catch (e) { /* ignore */ } unsub = null; }
    },
  };
}
