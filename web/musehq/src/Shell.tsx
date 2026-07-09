import { Show, createSignal, onMount } from "solid-js"
import { Rail } from "./Rail"
import { Thread } from "./Thread"
import { Composer } from "./Composer"
import { store } from "./store"

export default function Shell() {
  const [railOpen, setRailOpen] = createSignal(false)

  onMount(() => {
    void store.probe()
  })

  return (
    <div class="muse-shell" data-rail={railOpen() ? "open" : "closed"}>
      <Rail onNavigate={() => setRailOpen(false)} />

      <div class="muse-main">
        <header class="muse-topbar">
          <div style={{ display: "flex", "align-items": "center", gap: "12px", "min-width": 0 }}>
            <button
              class="muse-rail__toggle"
              type="button"
              aria-label="Toggle navigation"
              onClick={() => setRailOpen((v) => !v)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
              </svg>
            </button>
            <span class="muse-topbar__title">{store.activeSession()?.title ?? "muse"}</span>
          </div>
          <a class="muse-chip" href="https://github.com/a-c-i-software-and-development/m.u.s.e" target="_blank" rel="noreferrer">
            <span class="muse-status-dot" data-state={store.state.readiness === "ready" ? "ready" : undefined} />
            muse
          </a>
        </header>

        <Show when={store.state.banner}>
          <div class="muse-banner" role="status">
            {store.state.banner}
          </div>
        </Show>

        <Thread />
        <Composer />
      </div>

      <Show when={railOpen()}>
        <button
          aria-label="Close navigation"
          onClick={() => setRailOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            "z-index": 30,
            background: "rgba(0,0,0,0.5)",
            border: 0,
          }}
        />
      </Show>
    </div>
  )
}
