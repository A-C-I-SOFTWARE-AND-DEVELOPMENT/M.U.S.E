// muse cockpit — Chat view.
//
// A conversation with muse over POST /v1/jarvis/chat. The gateway streams the
// reply as NDJSON lines ({role, content, error}); we accumulate them into the
// in-flight assistant message and keep the full history so each turn carries
// context forward. Rendered exclusively through ctx.components + cockpit.css —
// matte surfaces, value hierarchy, no neon, no shadows. The white core is the
// hero; spectral color stays a sparing accent (the assistant's name pill).

export async function mount(container, ctx) {
  const { api, components } = ctx;
  const { el, card, button, pill, emptyState, sectionHeader } = components;

  // ---- State -------------------------------------------------------------
  // history: the running [{role, content}] transcript sent back to the model.
  const history = [];
  let inFlight = false; // a stream is currently open
  let abort = null; // AbortController for the active stream

  // ---- DOM scaffold ------------------------------------------------------
  const log = el("div", { class: "chat-log" });

  const textarea = el("textarea", {
    class: "field grow chat-input",
    rows: "2",
    placeholder: "Message muse…",
    "aria-label": "Message muse",
  });

  const sendBtn = button({ label: "Send", variant: "primary", onClick: () => submit() });

  const composer = el("div", { class: "row chat-composer" }, [textarea, sendBtn]);

  const wrap = el("div", { class: "chat-view" }, [
    sectionHeader({ eyebrow: "Conversation", title: "Chat" }),
    log,
    composer,
  ]);

  container.replaceChildren(wrap);

  // ---- Rendering ---------------------------------------------------------
  // The empty state shows when there is no transcript yet.
  function renderEmpty() {
    log.replaceChildren(
      emptyState({
        title: "Start a conversation",
        body: "Ask muse anything. Your message and the reply stay in this session's history so each turn carries context forward.",
      })
    );
  }

  // Build a single message bubble as a matte card. The role is shown as a
  // small label/pill — the assistant gets the spectral accent, the user a
  // neutral chip. The body is plain text (never innerHTML — model output is
  // untrusted), with whitespace preserved.
  function bubble(role, content, { pending = false, error = false } = {}) {
    const isAssistant = role === "assistant";
    const tag = isAssistant
      ? pill("muse", error ? "danger" : "accent")
      : pill("You", "neutral");

    const bodyText = content && content.length
      ? content
      : pending
        ? "…"
        : "";

    const body = el("div", {
      class: "chat-body" + (error ? " chat-error" : ""),
      text: bodyText,
      style: { whiteSpace: "pre-wrap" },
    });

    const head = el("div", { class: "row chat-msg-head" }, [tag]);
    return card([head, body], {});
  }

  // Repaint the whole log from history (+ any in-flight assistant draft).
  function render() {
    if (!history.length && !inFlight) {
      renderEmpty();
      return;
    }
    const nodes = history.map((m) =>
      bubble(m.role, m.content, { error: m.role === "assistant" && m.error })
    );
    log.replaceChildren(...nodes);
    scrollToEnd();
  }

  function scrollToEnd() {
    // Defer so layout settles before we measure.
    requestAnimationFrame(() => {
      log.scrollTop = log.scrollHeight;
    });
  }

  function setBusy(busy) {
    inFlight = busy;
    sendBtn.disabled = busy;
    sendBtn.textContent = busy ? "Sending…" : "Send";
    textarea.disabled = busy;
  }

  // ---- Send / stream -----------------------------------------------------
  async function submit() {
    if (inFlight) return;

    const prompt = (textarea.value || "").trim();
    if (!prompt) return;

    // Gate on a paired token — show a friendly card rather than throwing a 401.
    if (!api.getToken()) {
      pushNotice(
        "Not paired yet",
        "Pair this cockpit from the header before chatting with muse."
      );
      return;
    }

    textarea.value = "";

    // Push the user turn and an empty assistant draft we'll accumulate into.
    history.push({ role: "user", content: prompt });
    const draft = { role: "assistant", content: "", error: false };
    history.push(draft);

    // Snapshot the history to SEND (everything before this draft turn).
    const sendHistory = history
      .slice(0, -1)
      .map((m) => ({ role: m.role, content: m.content }));

    setBusy(true);
    render();

    abort = new AbortController();
    let sawError = false;

    try {
      await api.streamNDJSON(
        "/v1/jarvis/chat",
        { prompt, history: sendHistory },
        {
          signal: abort.signal,
          onLine: (obj) => {
            if (!obj || typeof obj !== "object") return;
            if (obj.error) {
              sawError = true;
              draft.error = true;
              const msg = typeof obj.error === "string" ? obj.error : "The model returned an error.";
              draft.content = draft.content ? draft.content + "\n" + msg : msg;
            } else if (typeof obj.content === "string") {
              // Accumulate streamed tokens/segments into the draft.
              draft.content += obj.content;
            }
            render();
          },
        }
      );

      // Stream ended cleanly. If nothing arrived, leave a gentle placeholder.
      if (!sawError && !draft.content) {
        draft.content = "(no response)";
      }
    } catch (e) {
      // Never throw uncaught — surface a friendly inline error on the draft.
      draft.error = true;
      const code = e && e.status ? " (HTTP " + e.status + ")" : "";
      const reason =
        e && e.status === 401
          ? "Your session isn't authorized" + code + ". Re-pair from the header."
          : "Couldn't reach muse" + code + ". Check the gateway and try again.";
      draft.content = draft.content
        ? draft.content + "\n" + reason
        : reason;
    } finally {
      abort = null;
      setBusy(false);
      render();
    }
  }

  // Append a transient assistant-style notice card (e.g. "not paired") without
  // polluting the model history.
  function pushNotice(title, body) {
    const notice = card(
      [
        el("div", { class: "row chat-msg-head" }, [pill("muse", "warn")]),
        el("div", { class: "chat-body", text: title }),
        el("p", { class: "muted", text: body, style: { margin: "0" } }),
      ],
      {}
    );
    if (!history.length && !inFlight) log.replaceChildren(notice);
    else log.appendChild(notice);
    scrollToEnd();
  }

  // Enter sends; Shift+Enter inserts a newline.
  textarea.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      submit();
    }
  });

  // First paint.
  render();

  // ---- Lifecycle ---------------------------------------------------------
  // No background stream/poll runs when hidden; we only react to token changes
  // so a re-pair while the view is open clears any stale "not paired" notice.
  const unsubscribe = api && typeof ctx.onTokenChange === "function"
    ? ctx.onTokenChange(() => {
        // If we were showing the empty/notice state, refresh it.
        if (!inFlight) render();
      })
    : null;

  return {
    onShow() {
      // Keep the transcript; just put the cursor back in the composer.
      if (!inFlight) textarea.focus();
    },
    onHide() {
      // Abort any open stream so we don't accumulate into a hidden view.
      if (abort) {
        try { abort.abort(); } catch (e) { /* ignore */ }
        abort = null;
        setBusy(false);
      }
      if (typeof unsubscribe === "function") {
        try { unsubscribe(); } catch (e) { /* ignore */ }
      }
    },
  };
}
