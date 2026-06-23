// muse cockpit — Learning view.
//
// The learning queue: candidate traces awaiting curation. Each candidate is a
// card (trace summary, kind, status pill) with owner-gated Approve / Reject.
// A ghost Export pulls the curated dataset. White is the hero; the spectral
// ring stays matte; hierarchy is by value, not effects.
//
// Endpoints:
//   GET  /v1/cockpit/learning              -> { candidates: [...] } (or array)
//   POST /v1/cockpit/learning/{id} {decision:"approve"|"reject"}  (owner-gated)
//   GET  /v1/cockpit/learning/export       -> file (opened / downloaded)
//
// View interface: export async function mount(container, ctx) -> { onShow, onHide }.

export async function mount(container, ctx) {
  const { api, components } = ctx;
  const { el, card, pill, button, sectionHeader, emptyState } = components;

  // ---- local state -------------------------------------------------------
  let loaded = false;       // have we successfully loaded at least once?
  let loading = false;      // a load is in flight
  let pollTimer = null;     // setInterval handle (refresh while visible)
  let visible = false;      // onShow/onHide gate
  const busy = new Set();   // candidate ids with an in-flight decision

  // ---- DOM scaffold ------------------------------------------------------
  const listEl = el("div", { class: "learning-list" });

  const exportBtn = button({
    label: "Export",
    variant: "ghost",
    title: "Download the curated learning dataset",
    onClick: onExport,
  });

  const header = sectionHeader({
    eyebrow: "Intelligence",
    title: "Learning Queue",
    trailing: exportBtn,
  });

  const root = el("div", { class: "view-learning" }, [header, listEl]);
  container.replaceChildren(root);

  // ---- helpers -----------------------------------------------------------

  // Normalize the API payload into an array of candidate objects.
  function extractCandidates(data) {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.candidates)) return data.candidates;
    if (data && Array.isArray(data.items)) return data.items;
    if (data && Array.isArray(data.queue)) return data.queue;
    return [];
  }

  // Map a candidate status to a pill state.
  function statusState(status) {
    const s = String(status || "").toLowerCase();
    if (s === "approved" || s === "accepted" || s === "ok" || s === "done") return "ok";
    if (s === "rejected" || s === "failed" || s === "error") return "danger";
    if (s === "review" || s === "needs_review" || s === "warn") return "warn";
    if (s === "pending" || s === "queued" || s === "candidate" || s === "new") return "accent";
    return "neutral";
  }

  function candidateId(c) {
    return c && (c.id ?? c.candidate_id ?? c.trace_id ?? c.uid ?? null);
  }

  function summaryText(c) {
    return (
      (c && (c.summary ?? c.trace_summary ?? c.title ?? c.description ?? c.text)) ||
      "Learning candidate"
    );
  }

  function kindText(c) {
    return c && (c.kind ?? c.type ?? c.category ?? c.task_class);
  }

  // ---- rendering ---------------------------------------------------------

  function renderLoading() {
    listEl.replaceChildren(
      card([el("p", { class: "muted", text: "Loading learning queue…" })])
    );
  }

  function renderError(message) {
    const retry = button({ label: "Retry", variant: "secondary", onClick: () => load() });
    listEl.replaceChildren(
      card([
        el("p", { class: "section-title", text: "Couldn't load the learning queue" }),
        el("p", { class: "muted", text: message || "The gateway didn't respond. Try again." }),
        el("div", { class: "row", style: { marginTop: "var(--space-3)" } }, [retry]),
      ])
    );
  }

  function renderEmpty() {
    listEl.replaceChildren(
      emptyState({
        title: "Nothing to curate",
        body: "Validated, source-backed traces awaiting your review will appear here. Approve the strong ones into the dataset.",
      })
    );
  }

  function renderList(candidates) {
    if (!candidates.length) {
      renderEmpty();
      return;
    }
    listEl.replaceChildren(...candidates.map(renderCard));
  }

  function renderCard(c) {
    const id = candidateId(c);
    const kind = kindText(c);
    const isBusy = id != null && busy.has(String(id));

    // Header row: kind + status pill.
    const meta = el("div", { class: "row", style: { gap: "var(--space-2)", alignItems: "center" } }, [
      kind ? pill(String(kind), "neutral") : null,
      c && c.status != null ? pill(String(c.status), statusState(c.status)) : null,
    ]);

    const summary = el("p", { class: "section-title", text: summaryText(c) });

    // Optional secondary detail line (mono trace id / score).
    const detailBits = [];
    if (id != null) detailBits.push("#" + String(id));
    if (c && c.score != null) detailBits.push("score " + String(c.score));
    if (c && c.created_at) detailBits.push(String(c.created_at));
    const detail = detailBits.length
      ? el("p", { class: "muted mono", text: detailBits.join("  ·  ") })
      : null;

    const approveBtn = button({
      label: isBusy ? "Working…" : "Approve",
      variant: "primary",
      disabled: isBusy || id == null,
      onClick: () => decide(c, "approve"),
    });
    const rejectBtn = button({
      label: "Reject",
      variant: "danger",
      disabled: isBusy || id == null,
      onClick: () => decide(c, "reject"),
    });

    const actions = el("div", {
      class: "row",
      style: { gap: "var(--space-2)", marginTop: "var(--space-3)" },
    }, [approveBtn, rejectBtn]);

    return card([meta, summary, detail, actions]);
  }

  // ---- network -----------------------------------------------------------

  async function load() {
    if (loading) return;
    if (!api.getToken()) {
      // Unpaired — show a gentle prompt rather than an error.
      listEl.replaceChildren(
        emptyState({
          title: "Pair to view the learning queue",
          body: "Pair this cockpit from the header to load candidate traces awaiting curation.",
        })
      );
      return;
    }
    loading = true;
    if (!loaded) renderLoading();
    try {
      const data = await api.getJSON("/v1/cockpit/learning");
      const candidates = extractCandidates(data);
      loaded = true;
      renderList(candidates);
    } catch (err) {
      if (!loaded) {
        const msg = err && err.status ? `Request failed (HTTP ${err.status}).` : (err && err.message);
        renderError(msg);
      }
      // If we had data before, keep showing it across a transient blip.
    } finally {
      loading = false;
    }
  }

  async function decide(c, decision) {
    const id = candidateId(c);
    if (id == null) return;
    const key = String(id);
    if (busy.has(key)) return;
    busy.add(key);
    disableDecisionButtons();
    try {
      await api.ownerPost(
        "/v1/cockpit/learning/" + encodeURIComponent(id),
        { decision },
        (decision === "approve" ? "Approve" : "Reject") + " learning candidate " + id
      );
      busy.delete(key);
      // Refresh from source so the queue reflects the new state.
      await load();
    } catch (err) {
      busy.delete(key);
      if (err && err.cancelled) {
        // Owner cancelled the phrase prompt — silently restore the card.
        await load();
        return;
      }
      const msg = err && err.status ? `Action failed (HTTP ${err.status}).` : "Action failed.";
      // Surface a non-fatal banner-style notice via reload + alert-free card.
      flashError(msg);
      await load();
    }
  }

  // Lock every decision button while an owner-gated action is in flight, so the
  // queue can't be double-submitted before the post-action reload re-renders.
  function disableDecisionButtons() {
    listEl.querySelectorAll("button.btn.primary, button.btn.danger").forEach((b) => {
      b.setAttribute("disabled", "disabled");
    });
  }

  let errorNotice = null;
  function flashError(message) {
    if (errorNotice && errorNotice.parentNode) errorNotice.remove();
    errorNotice = el("div", { class: "banner offline show", text: message });
    root.insertBefore(errorNotice, listEl);
    setTimeout(() => {
      if (errorNotice && errorNotice.parentNode) {
        errorNotice.remove();
        errorNotice = null;
      }
    }, 4000);
  }

  async function onExport() {
    exportBtn.setAttribute("disabled", "disabled");
    try {
      // Fetch with auth (bearer must ride in the header), then hand the blob to
      // the browser as a download. A plain link can't carry the Authorization
      // header, so we go through the api helper.
      const resp = await api.api("/v1/cockpit/learning/export", {
        headers: api.authHeaders({ Accept: "application/octet-stream" }),
      });
      if (!resp.ok) {
        flashError(`Export failed (HTTP ${resp.status}).`);
        return;
      }
      const blob = await resp.blob();
      const cd = resp.headers.get("Content-Disposition") || "";
      let filename = "learning-dataset.jsonl";
      const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
      if (m && m[1]) filename = decodeURIComponent(m[1]);
      const url = URL.createObjectURL(blob);
      const a = el("a", { href: url, download: filename, style: { display: "none" } });
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Revoke after the click has had a chance to start the download.
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      flashError("Export failed. " + ((err && err.message) || ""));
    } finally {
      exportBtn.removeAttribute("disabled");
    }
  }

  // ---- lifecycle ---------------------------------------------------------

  function startPolling() {
    stopPolling();
    // Light refresh while the view is visible — the queue is human-paced.
    pollTimer = setInterval(() => {
      if (visible && !loading) load();
    }, 15000);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // Reconnect / reload when the token changes (pair / unpair).
  const unsubscribe = ctx.onTokenChange
    ? ctx.onTokenChange(() => {
        loaded = false;
        if (visible) load();
      })
    : null;

  return {
    onShow() {
      visible = true;
      load();
      startPolling();
    },
    onHide() {
      visible = false;
      stopPolling();
      if (typeof unsubscribe === "function") {
        // Keep the subscription alive across hides so reconnects still reload;
        // we only intend onHide to pause polling, not tear down the view.
      }
    },
  };
}
