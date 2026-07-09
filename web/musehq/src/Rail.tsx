import { For, Show, type JSX } from "solid-js"
import { store } from "./store"

interface Destination {
  label: string
  href: string
  icon: () => JSX.Element
  hint?: string
}

// Cockpit destinations. Singularity (Muse Omni) owns site root; this OpenCode
// chat shell lives under /chat/ and links out to the shared static surfaces.
const DESTINATIONS: Destination[] = [
  { label: "Muse Omni", href: "/", hint: "Full Singularity operations cockpit", icon: IconLegacy },
  { label: "Atlas", href: "/atlas/", hint: "3D systems atlas", icon: IconAtlas },
  { label: "Studio", href: "/studio.html", hint: "Generative studio", icon: IconStudio },
  { label: "Observatory", href: "/observatory.html", hint: "Live telemetry", icon: IconObs },
]

export function Rail(props: { onNavigate?: () => void }) {
  return (
    <nav class="muse-rail" aria-label="Cockpit destinations">
      <div class="muse-rail__brand">
        <span class="muse-orb" aria-hidden="true" />
        <span class="muse-wordmark">muse</span>
      </div>

      <button class="muse-rail__new" type="button" onClick={() => store.startNewSession()}>
        <IconPlus />
        <span>New conversation</span>
      </button>

      <div class="muse-rail__scroll">
        <Show when={store.state.sessions.length > 0}>
          <div class="muse-rail__section">Conversations</div>
          <For each={store.state.sessions}>
            {(s) => (
              <button
                class="muse-navlink"
                classList={{ "is-active": s.id === store.state.activeId }}
                type="button"
                onClick={() => {
                  store.selectSession(s.id)
                  props.onNavigate?.()
                }}
              >
                <IconChat />
                <span
                  style={{
                    overflow: "hidden",
                    "text-overflow": "ellipsis",
                    "white-space": "nowrap",
                  }}
                >
                  {s.title}
                </span>
              </button>
            )}
          </For>
        </Show>

        <div class="muse-rail__section">Cockpit</div>
        <For each={DESTINATIONS}>
          {(d) => (
            <a class="muse-navlink" href={d.href} title={d.hint}>
              <span class="muse-navlink__icon">{d.icon()}</span>
              <span>{d.label}</span>
            </a>
          )}
        </For>
      </div>

      <div class="muse-rail__footer">
        <span
          class="muse-status-dot"
          data-state={
            store.state.readiness === "ready" ? "ready" : store.state.readiness === "none" ? "error" : undefined
          }
        />
        <span>
          {store.state.readiness === "ready"
            ? "Connected"
            : store.state.readiness === "needs-key"
              ? "Needs a key"
              : store.state.readiness === "none"
                ? "Offline"
                : "…"}
        </span>
        <a href="/terms.html" style={{ "margin-left": "auto" }}>
          Terms
        </a>
        <a href="/privacy.html">Privacy</a>
      </div>
    </nav>
  )
}

function IconPlus() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
    </svg>
  )
}
function IconChat() {
  return (
    <svg class="muse-navlink__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 5h16v11H8l-4 4V5Z"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linejoin="round"
      />
    </svg>
  )
}
function IconAtlas() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6" />
      <path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" stroke="currentColor" stroke-width="1.2" />
    </svg>
  )
}
function IconStudio() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3l2.5 5 5.5.8-4 4 1 5.4L12 20l-5 2.6 1-5.4-4-4 5.5-.8L12 3Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
    </svg>
  )
}
function IconObs() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M3 18l5-6 4 3 4-7 5 10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  )
}
function IconLegacy() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.6" />
      <path d="M3 9h18" stroke="currentColor" stroke-width="1.6" />
    </svg>
  )
}
