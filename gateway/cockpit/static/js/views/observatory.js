// muse cockpit — Observatory view.
//
// Makes the Neural Observatory (the standalone Three.js app at
// /cockpit/observatory.html) first-class: a full-bleed, edge-bordered iframe
// that fills the view, fronted by a SectionHeader and an "open standalone"
// ghost link. We do NOT rewrite the 3D app — we embed it.
//
// Renders exclusively through ctx.components + cockpit.css classes (matte ring,
// value hierarchy, no neon/shadows). Loading, error, and empty states are all
// handled gracefully — nothing throws uncaught.

const OBSERVATORY_URL = "/cockpit/observatory.html";

export async function mount(container, ctx) {
  const { components } = ctx;
  const { el, button, sectionHeader, emptyState, card } = components;

  // --- header: eyebrow + "open standalone" ghost link -----------------------
  const openLink = button({
    label: "Open standalone",
    variant: "ghost",
    title: "Open the Neural Observatory in a new tab",
    onClick: () => {
      try {
        window.open(OBSERVATORY_URL, "_blank", "noopener");
      } catch (_) {
        // Pop-up blocked or unavailable — fall back to same-tab navigation.
        location.href = OBSERVATORY_URL;
      }
    },
  });

  const header = sectionHeader({
    eyebrow: "Neural Observatory",
    trailing: openLink,
  });

  // --- the embedded experience ----------------------------------------------
  // The iframe fills the remaining height (viewport minus the app header).
  // Tonal elevation (void-3 card surface) + 1px edge + radius-md — no shadow.
  const stage = el("div", {
    class: "card",
    style: {
      position: "relative",
      flex: "1 1 auto",
      minHeight: "0",
      padding: "0",
      overflow: "hidden",
    },
  });

  // Loading veil — shown until the iframe reports load, then faded out.
  const loading = el(
    "div",
    {
      style: {
        position: "absolute",
        inset: "0",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--void)",
        transition: "opacity var(--duration-standard) var(--easing-standard)",
        pointerEvents: "none",
        zIndex: "1",
      },
    },
    emptyState({
      title: "Awakening the Observatory",
      body: "Rendering the neural field…",
    })
  );

  const iframe = el("iframe", {
    src: OBSERVATORY_URL,
    title: "Neural Observatory",
    loading: "lazy",
    allow: "fullscreen; xr-spatial-tracking",
    style: {
      display: "block",
      width: "100%",
      height: "100%",
      border: "0",
      background: "var(--void)",
    },
  });

  let settled = false;
  const settle = (failed) => {
    if (settled) return;
    settled = true;
    clearTimeout(timer);
    if (failed) {
      // Friendly error card in place of the veil — never a blank screen.
      loading.replaceChildren(
        card([
          emptyState({
            title: "Observatory unavailable",
            body: "The neural field could not be loaded. Open it standalone to retry.",
            action: button({
              label: "Open standalone",
              variant: "secondary",
              onClick: () => {
                try {
                  window.open(OBSERVATORY_URL, "_blank", "noopener");
                } catch (_) {
                  location.href = OBSERVATORY_URL;
                }
              },
            }),
          }),
        ])
      );
      loading.style.pointerEvents = "auto";
      loading.style.opacity = "1";
    } else {
      loading.style.opacity = "0";
    }
  };

  iframe.addEventListener("load", () => settle(false));
  iframe.addEventListener("error", () => settle(true));

  // Safety net: if the iframe never fires load (blocked / 404 swallowed),
  // surface the friendly error rather than leaving the veil up forever.
  const timer = setTimeout(() => settle(true), 12000);

  stage.append(iframe, loading);

  // --- compose --------------------------------------------------------------
  // Column layout: header pinned, stage grows to fill the viewport below the
  // app header. The app-main already accounts for the header offset; we fill it.
  const root = el("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: "var(--space-4)",
      height: "calc(100vh - 88px)",
      minHeight: "0",
    },
  });
  root.append(header, stage);

  container.replaceChildren(root);

  // No streams or polling — the embedded app owns its own lifecycle. Nothing
  // to start/stop, so we return no onShow/onHide.
}
