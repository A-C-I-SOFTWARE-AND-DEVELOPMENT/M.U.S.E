// muse cockpit — Approvals view.
//
// Lists pending owner approvals from GET /v1/cockpit/approvals. Each item is a
// card: title/kind, summary, tier + status pills, and Approve (primary,
// owner-gated phrase) / Reject (danger, no phrase) actions.
//
// Renders exclusively through ctx.components helpers + cockpit.css classes.
// All network/auth flows through ctx.api. Self-contained; export mount().

export async function mount(container, ctx) {
  const { api, components } = ctx;
  const { el, card, pill, button, sectionHeader, emptyState } = components;

  // ---- view scaffold -----------------------------------------------------
  const list = el("div", { class: "approvals-list", style: { display: "grid", gap: "var(--space-4)" } });
  const header = sectionHeader({
    eyebrow: "GOVERNANCE",
    title: "Approvals",
    trailing: button({ label: "Refresh", variant: "ghost", onClick: () => refresh() }),
  });
  const root = el("div", {}, [
    header,
    el("div", { class: "approvals-body", style: { marginTop: "var(--space-4)" } }, [list]),
  ]);
  container.replaceChildren(root);

  // Map approval tier → pill state. Higher tiers lean toward warn/danger.
  function tierState(tier) {
    const t = String(tier == null ? "" : tier).toLowerCase();
    if (/(high|critical|severe|3|4|5)/.test(t)) return "danger";
    if (/(med|moderate|elevated|2)/.test(t)) return "warn";
    if (/(low|routine|1|0)/.test(t)) return "ok";
    return "accent";
  }

  // Map status → pill state.
  function statusState(status) {
    const s = String(status == null ? "" : status).toLowerCase();
    if (/(approved|done|accept|ok|complete)/.test(s)) return "ok";
    if (/(reject|denied|declin|fail)/.test(s)) return "danger";
    if (/(pending|await|review|open|queued)/.test(s)) return "warn";
    return "neutral";
  }

  function approvalId(item) {
    return item.id != null ? item.id
      : item.approval_id != null ? item.approval_id
      : item.request_id != null ? item.request_id
      : item.uuid != null ? item.uuid
      : null;
  }

  function approvalTitle(item) {
    return item.title || item.kind || item.type || item.name || "Approval request";
  }

  function approvalSummary(item) {
    return item.summary || item.proposed_action || item.description || item.detail || item.reason || "";
  }

  // ---- a single approval card -------------------------------------------
  function renderCard(item) {
    const id = approvalId(item);
    const kind = item.kind || item.type;
    const tier = item.tier != null ? item.tier : item.risk_tier != null ? item.risk_tier : item.risk;
    const stat = item.status || item.state;

    const pills = [];
    if (tier != null && String(tier).length) pills.push(pill(String(tier).toUpperCase(), tierState(tier)));
    if (stat != null && String(stat).length) pills.push(pill(String(stat).toUpperCase(), statusState(stat)));
    if (kind && kind !== approvalTitle(item)) pills.unshift(pill(String(kind), "neutral"));

    const titleRow = el("div", {
      class: "row",
      style: { justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-3)" },
    }, [
      el("h3", {
        text: approvalTitle(item),
        style: {
          margin: "0",
          fontSize: "var(--type-title-size)",
          fontWeight: "var(--type-title-weight)",
          lineHeight: "var(--type-title-line)",
        },
      }),
      pills.length
        ? el("div", { class: "row", style: { gap: "var(--space-2)", flexWrap: "wrap", justifyContent: "flex-end" } }, pills)
        : null,
    ]);

    const summary = approvalSummary(item);
    const body = summary
      ? el("p", {
          text: summary,
          class: "muted",
          style: {
            margin: "var(--space-3) 0 0",
            fontSize: "var(--type-body-size)",
            lineHeight: "var(--type-body-line)",
          },
        })
      : null;

    const idLine = id != null
      ? el("div", { class: "mono hint", style: { marginTop: "var(--space-2)" }, text: String(id) })
      : null;

    const status = el("div", { class: "hint", style: { marginTop: "var(--space-3)", minHeight: "1em" } });

    const approveBtn = button({
      label: "Approve",
      variant: "primary",
      disabled: id == null,
      onClick: () => decide("approve"),
    });
    const rejectBtn = button({
      label: "Reject",
      variant: "danger",
      disabled: id == null,
      onClick: () => decide("reject"),
    });

    const actions = el("div", {
      class: "row",
      style: { gap: "var(--space-3)", marginTop: "var(--space-4)", justifyContent: "flex-end" },
    }, [rejectBtn, approveBtn]);

    let busy = false;
    function setBusy(on) {
      busy = on;
      approveBtn.disabled = on || id == null;
      rejectBtn.disabled = on || id == null;
    }

    async function decide(decision) {
      if (busy || id == null) return;
      setBusy(true);
      status.textContent = decision === "approve" ? "Approving…" : "Rejecting…";
      status.className = "hint";
      try {
        if (decision === "approve") {
          // Owner-gated: ownerPost prompts for the phrase and retries once on 403.
          await api.ownerPost(
            "/v1/cockpit/approvals/" + encodeURIComponent(id),
            { decision: "approve" },
            "Approve " + approvalTitle(item),
          );
        } else {
          // Reject is not owner-gated — plain authenticated POST.
          await api.postJSON(
            "/v1/cockpit/approvals/" + encodeURIComponent(id),
            { decision: "reject" },
          );
        }
        // Success: drop the card and re-check empty.
        cardNode.remove();
        if (!list.querySelector(".card")) renderEmpty();
      } catch (err) {
        if (err && err.cancelled) {
          // Owner cancelled the phrase prompt — quietly reset.
          status.textContent = "";
          setBusy(false);
          return;
        }
        const code = err && err.status ? " (" + err.status + ")" : "";
        status.textContent =
          (decision === "approve" ? "Approve failed" : "Reject failed") + code + ". Please try again.";
        status.className = "hint";
        status.style.color = "var(--danger)";
        setBusy(false);
      }
    }

    const cardNode = card([titleRow, body, idLine, actions, status].filter(Boolean));
    return cardNode;
  }

  // ---- list states -------------------------------------------------------
  function renderLoading() {
    list.replaceChildren(card([el("p", { class: "muted", text: "Loading approvals…" })]));
  }

  function renderEmpty() {
    list.replaceChildren(
      emptyState({
        title: "Nothing awaiting approval",
        body: "When muse proposes an owner-gated action, it surfaces here for your review.",
      }),
    );
  }

  function renderError(err) {
    const unauth = err && (err.status === 401 || err.status === 403);
    const msg = unauth
      ? "This cockpit is not paired yet, or the session expired. Pair from the header to view approvals."
      : "Could not load approvals" + (err && err.status ? " (" + err.status + ")" : "") + ". Check the gateway and try again.";
    list.replaceChildren(
      card([
        el("h3", {
          text: "Couldn't load approvals",
          style: { margin: "0 0 var(--space-2)", fontSize: "var(--type-title-size)", fontWeight: "var(--type-title-weight)" },
        }),
        el("p", { class: "muted", text: msg, style: { margin: "0 0 var(--space-4)" } }),
        button({ label: "Retry", variant: "secondary", onClick: () => refresh() }),
      ]),
    );
  }

  function renderItems(items) {
    if (!items || !items.length) {
      renderEmpty();
      return;
    }
    const nodes = items.map(renderCard);
    list.replaceChildren(...nodes);
  }

  // ---- fetch + refresh ---------------------------------------------------
  let inflight = false;
  async function refresh() {
    if (inflight) return;
    if (!api.getToken()) {
      renderError({ status: 401 });
      return;
    }
    inflight = true;
    renderLoading();
    try {
      const data = await api.getJSON("/v1/cockpit/approvals");
      const items = Array.isArray(data)
        ? data
        : Array.isArray(data && data.approvals)
        ? data.approvals
        : Array.isArray(data && data.items)
        ? data.items
        : [];
      renderItems(items);
    } catch (err) {
      renderError(err);
    } finally {
      inflight = false;
    }
  }

  // Initial paint (mount runs once, lazily on first navigation).
  renderLoading();

  // Reload whenever the token changes (pair / unpair / re-pair).
  const unsubscribe = ctx.onTokenChange ? ctx.onTokenChange(() => refresh()) : null;

  return {
    onShow() {
      refresh();
    },
    onHide() {
      // No streams to tear down; nothing to do.
    },
  };
}
