// muse cockpit — Jobs view.
//
// Orchestration's live job board. On show it pulls an initial snapshot from
// GET /v1/cockpit/jobs, then subscribes to the SSE feed
// (GET /v1/cockpit/jobs/stream) for job.upsert / job.removed / heartbeat
// frames. When ReadableStream is unavailable it degrades to an ~8s poll.
// Heartbeats drive the header "live" dot via ctx.setLive. Reconnect uses
// exponential backoff 1s → 8s. onHide tears the stream/poll down.
//
// Rendering goes exclusively through ctx.components + the cockpit.css classes:
// one matte card per job (white-hero value hierarchy, no neon, no shadows),
// each with a phase rail mapped from job.status and a status pill.

export async function mount(container, ctx) {
  const { api, components } = ctx;
  const { el, card, pill, phaseRail, emptyState, sectionHeader, button } = components;

  // ---- view state --------------------------------------------------------
  const jobs = new Map();        // id → job object
  let active = false;            // between onShow and onHide
  let ctrl = null;              // AbortController for the live SSE stream
  let pollTimer = null;          // setInterval handle for the fallback poll
  let backoff = 1000;            // SSE reconnect backoff (1s → 8s)
  let reconnectTimer = null;     // setTimeout handle for the next reconnect
  let started = false;           // guards against double-start
  let usingPoll = false;         // true once we've fallen back to polling
  let lastError = "";            // last network error message (for the banner)
  let unsubToken = null;         // token-change unsubscribe (no-op; we restart)

  // ---- DOM scaffolding ---------------------------------------------------
  const listEl = el("div", { class: "jobs-list", style: { display: "grid", gap: "var(--space-3)" } });
  const headerHost = el("div");

  const root = el("div", { style: { display: "grid", gap: "var(--space-4)" } }, [headerHost, listEl]);
  container.replaceChildren(root);

  function renderHeader() {
    const count = jobs.size;
    const trailing = count
      ? pill(String(count) + (count === 1 ? " job" : " jobs"), "neutral")
      : null;
    headerHost.replaceChildren(
      sectionHeader({ eyebrow: "Orchestration", title: "Jobs", trailing })
    );
  }

  // ---- status → phase-rail + pill mapping --------------------------------
  // The orchestration lifecycle, as a fixed rail. We light segments up to the
  // job's current status; a terminal failure marks the reached segment failed.
  const RAIL = [
    { key: "queued", label: "Queued" },
    { key: "running", label: "Running" },
    { key: "validating", label: "Validating" },
    { key: "done", label: "Done" },
  ];

  // Normalize the many possible status strings the gateway may emit into one
  // of our rail stages (plus the terminal flavors).
  function classifyStatus(raw) {
    const s = String(raw || "").toLowerCase();
    if (/(fail|error|reject|denied)/.test(s)) return { stage: stageFromText(s), terminal: "failed" };
    if (/(cancel|abort|stopp?ed)/.test(s)) return { stage: stageFromText(s), terminal: "cancelled" };
    if (/(done|complete|success|finish|merged|passed)/.test(s)) return { stage: "done", terminal: "done" };
    if (/(validat|review|gate|verify|check)/.test(s)) return { stage: "validating", terminal: null };
    if (/(run|build|work|active|progress|execut)/.test(s)) return { stage: "running", terminal: null };
    if (/(queue|pending|wait|plan|new|created|scheduled)/.test(s)) return { stage: "queued", terminal: null };
    return { stage: "running", terminal: null };
  }

  // Best-effort guess at which stage a failure/cancel happened in.
  function stageFromText(s) {
    if (/(validat|review|gate|verify|check)/.test(s)) return "validating";
    if (/(queue|pending|wait|plan)/.test(s)) return "queued";
    return "running";
  }

  function railFor(raw) {
    const { stage, terminal } = classifyStatus(raw);
    const reachedIdx = RAIL.findIndex((r) => r.key === stage);
    return RAIL.map((r, i) => {
      let state = "pending";
      if (i < reachedIdx) state = "done";
      else if (i === reachedIdx) {
        if (terminal === "failed") state = "failed";
        else if (terminal === "done") state = "done";
        else state = "active";
      }
      return { label: r.label, state };
    });
  }

  function pillFor(raw) {
    const s = String(raw || "").toLowerCase();
    const text = String(raw || "unknown").toUpperCase();
    if (/(fail|error|reject|denied)/.test(s)) return pill(text, "danger");
    if (/(cancel|abort|stopp?ed|warn)/.test(s)) return pill(text, "warn");
    if (/(done|complete|success|finish|merged|passed)/.test(s)) return pill(text, "ok");
    if (/(run|build|work|active|progress|execut|validat|review)/.test(s)) return pill(text, "accent");
    return pill(text, "neutral");
  }

  // ---- per-job card ------------------------------------------------------
  function jobTitle(j) {
    return j.title || j.goal || j.name || j.summary || ("Job " + (j.id || ""));
  }

  function metaLine(j) {
    const parts = [];
    if (j.id != null) parts.push(el("span", { class: "mono", text: "#" + j.id }));
    const worker = j.worker || j.profile || j.assignee;
    if (worker) parts.push(el("span", { text: "worker: " + worker }));
    const branch = j.branch || j.ref;
    if (branch) parts.push(el("span", { class: "mono", text: branch }));
    if (!parts.length) return null;
    // Interleave with dim separators.
    const kids = [];
    parts.forEach((p, i) => {
      if (i) kids.push(el("span", { class: "muted", text: " · " }));
      kids.push(p);
    });
    return el("div", { class: "muted", style: { display: "flex", flexWrap: "wrap", alignItems: "center", gap: "2px", fontSize: "var(--type-label-size)" } }, kids);
  }

  function jobCard(j) {
    const top = el("div", {
      class: "row",
      style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-3)" },
    }, [
      el("div", { class: "grow", style: { display: "grid", gap: "var(--space-1)" } }, [
        el("div", { text: jobTitle(j), style: { fontSize: "var(--type-title-size)", fontWeight: "var(--type-title-weight)", lineHeight: "var(--type-title-line)" } }),
        metaLine(j),
      ]),
      pillFor(j.status),
    ]);

    const rail = el("div", { style: { marginTop: "var(--space-3)" } }, [phaseRail(railFor(j.status))]);

    return card([top, rail]);
  }

  // ---- render ------------------------------------------------------------
  function render() {
    renderHeader();

    if (lastError && jobs.size === 0) {
      listEl.replaceChildren(
        card([
          el("div", { text: "Couldn't reach the orchestration feed", style: { fontSize: "var(--type-title-size)", fontWeight: "var(--type-title-weight)", marginBottom: "var(--space-2)" } }),
          el("p", { class: "muted", text: lastError }),
          el("p", { class: "hint", text: api.getToken() ? "Retrying automatically…" : "Pair this device (Token) to view jobs." }),
        ])
      );
      return;
    }

    if (jobs.size === 0) {
      listEl.replaceChildren(
        emptyState({
          title: "No jobs running",
          body: "When you orchestrate a goal, every job shows up here live — queued, running, validating, done.",
        })
      );
      return;
    }

    // Newest-first when an ordering hint exists, else by id descending.
    const arr = [...jobs.values()].sort(orderJobs);
    listEl.replaceChildren(...arr.map(jobCard));
  }

  function orderJobs(a, b) {
    const ta = jobTime(a), tb = jobTime(b);
    if (ta !== tb) return tb - ta;
    return String(b.id || "").localeCompare(String(a.id || ""));
  }
  function jobTime(j) {
    const v = j.updated_at || j.created_at || j.started_at || j.ts;
    const n = typeof v === "number" ? v : Date.parse(v);
    return Number.isFinite(n) ? n : 0;
  }

  // ---- data: initial snapshot + fallback poll ----------------------------
  function ingestList(data) {
    // Accept either a bare array or {jobs:[...]} / {items:[...]} envelopes.
    const list = Array.isArray(data) ? data : (data && (data.jobs || data.items)) || [];
    jobs.clear();
    for (const j of list) if (j && j.id != null) jobs.set(String(j.id), j);
  }

  async function fetchSnapshot() {
    try {
      const data = await api.getJSON("/v1/cockpit/jobs");
      ingestList(data);
      lastError = "";
    } catch (e) {
      lastError = "GET /v1/cockpit/jobs failed (" + (e.status || e.message || e) + ").";
    }
    if (active) render();
  }

  function startPolling() {
    if (pollTimer) return;
    usingPoll = true;
    if (ctx.setLive) { try { ctx.setLive(false); } catch (e) {} }
    fetchSnapshot();
    pollTimer = setInterval(() => { if (active) fetchSnapshot(); }, 8000);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  // ---- data: the SSE live stream -----------------------------------------
  function handleEvent(event, raw) {
    if (event === "heartbeat") {
      if (ctx.setLive) { try { ctx.setLive(true); } catch (e) {} }
      return;
    }
    let data;
    try { data = raw ? JSON.parse(raw) : null; } catch (e) { return; }
    if (!data) return;

    if (event === "job.upsert") {
      const job = data.job || data; // tolerate {job:{...}} or the bare job
      if (job && job.id != null) {
        jobs.set(String(job.id), job);
        if (active) render();
      }
    } else if (event === "job.removed") {
      const id = data.id != null ? data.id : (data.job && data.job.id);
      if (id != null) { jobs.delete(String(id)); if (active) render(); }
    }
  }

  async function connectStream() {
    if (!active) return;
    if (!api.getToken()) {
      // Unpaired — nothing to stream; show the friendly hint and stop.
      lastError = lastError || "Not paired.";
      render();
      return;
    }
    ctrl = new AbortController();
    try {
      await api.streamSSE("/v1/cockpit/jobs/stream", {
        onEvent: handleEvent,
        signal: ctrl.signal,
      });
      // Stream ended cleanly (server closed) — treat as a disconnect.
      if (active) scheduleReconnect();
    } catch (e) {
      if (!active) return; // aborted by onHide — silent
      if (e && e.name === "AbortError") return;
      // Distinguish "feature unavailable" from a transient network error.
      if (typeof ReadableStream === "undefined") {
        startPolling();
        return;
      }
      lastError = "Stream error (" + (e.status || e.message || e) + ").";
      if (ctx.setLive) { try { ctx.setLive(false); } catch (e2) {} }
      render();
      scheduleReconnect();
    }
  }

  function scheduleReconnect() {
    if (!active || usingPoll) return;
    if (ctx.setLive) { try { ctx.setLive(false); } catch (e) {} }
    if (reconnectTimer) return;
    const wait = backoff;
    backoff = Math.min(backoff * 2, 8000); // 1s → 2s → 4s → 8s (cap)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      if (active) connectStream();
    }, wait);
  }

  function abortStream() {
    if (ctrl) { try { ctrl.abort(); } catch (e) {} ctrl = null; }
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  }

  // ---- lifecycle ---------------------------------------------------------
  async function start() {
    if (started) return;
    started = true;
    backoff = 1000;
    usingPoll = false;
    lastError = "";
    render(); // loading → empty/snapshot frame

    if (typeof ReadableStream === "undefined") {
      startPolling();
      return;
    }
    // Seed with a snapshot, then go live. The SSE upserts keep us current.
    await fetchSnapshot();
    if (active && !usingPoll) connectStream();
  }

  function stop() {
    started = false;
    abortStream();
    stopPolling();
    usingPoll = false;
    backoff = 1000;
    if (ctx.setLive) { try { ctx.setLive(false); } catch (e) {} }
  }

  // Reconnect on token change (a fresh pairing) while we're visible.
  if (ctx.onTokenChange) {
    unsubToken = ctx.onTokenChange(() => {
      if (!active) return;
      stop();
      active = true;
      start();
    });
  }

  return {
    onShow() {
      active = true;
      start();
    },
    onHide() {
      active = false;
      stop();
    },
  };
}
